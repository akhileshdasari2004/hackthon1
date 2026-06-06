"""Dynamic DAG planner — memory-aware, adaptive goal ordering."""

from __future__ import annotations

from typing import Any

from agira.artifacts.store import ArtifactStore
from agira.orchestrator.memory_store import get_memory_store
from agira.orchestrator.plan import ExecutionPlan, NodeStatus
from agira.orchestrator.planner import DynamicPlanner


class AdaptivePlanner(DynamicPlanner):
    """Memory-aware planner that adapts goal ordering based on history.
    
    Extends DynamicPlanner with:
    - Cross-run learning (skip known-failure patterns)
    - Repo-profile-based goal prioritization
    - Adaptive retry based on past failures
    """

    def __init__(self) -> None:
        super().__init__()  # Initialize DynamicPlanner base
        self._memory = get_memory_store()

    def propose(self, plan: ExecutionPlan, store: ArtifactStore) -> list:
        """Add missing goal nodes with memory-aware prioritization.
        
        Uses same GOALS/GOAL_DEPENDENCIES as base planner but filters:
        - Skip goals with known-permanent-failure patterns
        - Prioritize goals whose dependencies are already satisfied
        """
        satisfied = set()
        for goal in self.GOALS:
            artifact_key = self._artifact_for_goal(goal)
            if artifact_key and store.has_type(artifact_key):
                satisfied.add(goal)
        for node in plan.nodes.values():
            if node.status == NodeStatus.COMPLETED:
                satisfied.add(node.name)

        existing_names = {n.name for n in plan.nodes.values()}
        new_nodes = []

        # Sort goals by priority (dependencies-first, then memory-adjusted)
        goal_order = self._prioritize_goals(self.GOALS, plan, store)

        for goal in goal_order:
            if goal in existing_names:
                continue
            if goal in satisfied:
                continue

            deps = self.GOAL_DEPENDENCIES.get(goal, [])
            if not all(dep in satisfied for dep in deps):
                continue

            if self._is_known_permanent_failure(goal):
                continue

            artifact_key = self._artifact_for_goal(goal)
            if artifact_key and store.has_type(artifact_key):
                continue

            dep_ids = []
            for dep in deps:
                for node in plan.nodes.values():
                    if node.name == dep:
                        dep_ids.append(node.node_id)
                        break

            target = self._target_for_goal(goal)
            action_type = "subagent" if target.endswith("Agent") else "tool"
            node = plan.add_node(goal, action_type, target, depends_on=dep_ids)
            new_nodes.append(node)

        return new_nodes

    def _prioritize_goals(
        self,
        goals: set[str],
        plan: ExecutionPlan,
        store: ArtifactStore,
    ) -> list[str]:
        """Sort goals by a combination of dependency depth and memory hints."""
        def priority_score(goal: str) -> tuple[int, int]:
            # Tuple: (depth_from_leaves, memory_preference)
            depth = self._dependency_depth(goal, self.GOAL_DEPENDENCIES)
            mem_hint = self._memory_hint(goal, plan)
            return (depth, -mem_hint)

        return sorted(goals, key=priority_score)

    def _dependency_depth(self, goal: str, deps: dict[str, list[str]]) -> int:
        """Compute how deep a goal is in the dependency tree."""
        if goal not in deps or not deps[goal]:
            return 0
        return 1 + max(
            (self._dependency_depth(d, deps) for d in deps[goal]),
            default=0
        )

    def _memory_hint(self, goal: str, plan: ExecutionPlan) -> int:
        """Return a memory-based hint for goal prioritization (higher = prefer more)."""
        score = 0
        failures = self._memory.get_known_failures(goal)
        if failures:
            # Penalize goals with many failures
            score -= len(failures)
        return score

    def _is_known_permanent_failure(self, goal: str) -> bool:
        """Check if this goal has a known permanent failure pattern."""
        failures = self._memory.get_known_failures(goal)
        for sig, data in failures.items():
            count = data.get("count", 0)
            error_type = data.get("error_type", "")
            if count >= 3 and error_type == "deterministic":
                return True
        return False

    def observe(self, store: ArtifactStore) -> dict[str, Any]:
        return super().observe(store)