"""Dynamic planner — proposes next actions from artifact observations."""

from __future__ import annotations

from typing import Any

from agira.artifacts.store import ArtifactStore
from agira.orchestrator.plan import ExecutionPlan, PlanNode, NodeStatus


class DynamicPlanner:
    """
    Observes artifact store and proposes plan nodes.
    No hardcoded workflow — goals emerge from missing artifacts.
    """

    # Define all possible goals and their dependencies
    GOALS = {
        "repo_metadata",
        "file_list",
        "dependency_graph",
        "repo_analysis",
        "bug_detection",
        "merge_findings",
        "initial_validation",
        "patch_generation",
        "test_validation",
        "rollback_on_failure",
        "health_score",
        "json_report",
        "markdown_report",
        "pr_summary",
        "tool_coverage",
    }

    GOAL_DEPENDENCIES = {
        "repo_metadata": [],
        "file_list": ["repo_metadata"],
        "dependency_graph": ["file_list"],
        "repo_analysis": ["dependency_graph"],
        "bug_detection": ["dependency_graph"],
        "merge_findings": ["repo_analysis", "bug_detection"],
        "initial_validation": ["merge_findings"],
        "patch_generation": ["merge_findings"],
        "test_validation": ["patch_generation"],
        "rollback_on_failure": ["patch_result"],  # only added if there are patches and validation failed
        "health_score": ["test_validation"],
        "json_report": ["health_score"],
        "markdown_report": ["json_report"],
        "pr_summary": ["markdown_report"],
        "tool_coverage": ["pr_summary"],
    }

    def __init__(self) -> None:
        # We no longer need the mapping from name to id
        pass

    def propose(self, plan: ExecutionPlan, store: ArtifactStore) -> list[PlanNode]:
        """Add missing goal nodes based on artifact observations."""
        # Determine which goals are already satisfied (by artifact or by completed node)
        satisfied = set()
        # Check artifacts
        for goal in self.GOALS:
            artifact_key = self._artifact_for_goal(goal)
            if artifact_key and store.has_type(artifact_key):
                satisfied.add(goal)
        # Check completed nodes
        for node in plan.nodes.values():
            if node.status == NodeStatus.COMPLETED:
                satisfied.add(node.name)

        existing_names = {n.name for n in plan.nodes.values()}
        new_nodes: list[PlanNode] = []

        for goal in self.GOALS:
            if goal in existing_names:
                # We already have a node for this goal (regardless of status), skip adding a new one.
                continue
            if goal in satisfied:
                # This goal is already satisfied, skip.
                continue
            # Check if dependencies are satisfied (by artifact or by completed node)
            deps = self.GOAL_DEPENDENCIES.get(goal, [])
            if not all(dep in satisfied for dep in deps):
                # Dependencies not satisfied yet, skip.
                continue

            # Special handling for rollback_on_failure
            if goal == "rollback_on_failure":
                validation = store.latest("validation_result")
                if validation and validation.data.get("overall_pass"):
                    continue
                patches = store.latest("patch_result")
                if not patches or not patches.data.get("patches"):
                    continue

            artifact_key = self._artifact_for_goal(goal)
            if artifact_key and store.has_type(artifact_key):
                # This should not happen because we checked satisfied, but just in case.
                continue

            # Collect dependency node IDs: only for dependencies that have a node in the plan
            dep_ids = []
            for dep in deps:
                # Look for a node in the plan with the name equal to the dependency goal
                for node in plan.nodes.values():
                    if node.name == dep:
                        dep_ids.append(node.node_id)
                        break
                # If we don't find a node for this dependency, it means the dependency is satisfied by an artifact
                # (since we already checked that dep is in satisfied). In that case, we don't add a dependency edge.

            target = self._target_for_goal(goal)
            # Subagents have targets ending with "Agent" (e.g., "BugHunterAgent")
            action_type = "subagent" if target.endswith("Agent") else "tool"
            node = plan.add_node(
                goal,
                action_type,
                target,
                depends_on=dep_ids,
            )
            new_nodes.append(node)

        return new_nodes

    def should_continue(self, plan: ExecutionPlan, store: ArtifactStore) -> bool:
        if plan.iteration >= plan.max_iterations:
            return False
        # Continue if we don't have the final report (json_report)
        if not store.has_type("json_report"):
            return True
        return False

    def observe(self, store: ArtifactStore) -> dict[str, Any]:
        return {
            "artifacts": list(store._by_type.keys()),
            "issues": (store.latest("issues") or {}).data if store.latest("issues") else [],
            "patches": (store.latest("patch_result") or {}).data if store.latest("patch_result") else {},
            "validation": (store.latest("validation_result") or {}).data if store.latest("validation_result") else {},
        }

    def _artifact_for_goal(self, goal: str) -> str | None:
        mapping = {
            "repo_metadata": "repo_metadata",
            "file_list": "file_list",
            "dependency_graph": "dependency_graph",
            "repo_analysis": "repo_analysis",
            "bug_detection": "issues",
            "merge_findings": "merged_findings",
            "initial_validation": "test_results",
            "patch_generation": "patch_result",
            "test_validation": "validation_result",
            "health_score": "health_score",
            "json_report": "json_report",
            "markdown_report": "markdown_report",
            "pr_summary": "pr_summary",
            "tool_coverage": "tool_coverage",
        }
        return mapping.get(goal)

    def _target_for_goal(self, goal: str) -> str:
        mapping = {
            "repo_metadata": "repo_tools.get_repo_metadata",
            "file_list": "repo_tools.list_files",
            "dependency_graph": "analysis_tools.build_dependency_graph",
            "repo_analysis": "RepoAnalyzerAgent",
            "bug_detection": "BugHunterAgent",
            "merge_findings": "agent_tools.merge_agent_output",
            "initial_validation": "execution_tools.run_tests",
            "patch_generation": "PatchGeneratorAgent",
            "test_validation": "TestValidationAgent",
            "rollback_on_failure": "patch_tools.rollback_all",
            "health_score": "report_tools.repo_health_score",
            "json_report": "report_tools.generate_json_report",
            "markdown_report": "report_tools.generate_markdown_report",
            "pr_summary": "report_tools.generate_pr_summary",
            "tool_coverage": "observability_tools.tool_coverage_report",
        }
        return mapping.get(goal, "")

    def _input_artifacts(self, goal: str, store: ArtifactStore) -> list[str]:
        inputs: dict[str, list[str]] = {
            "bug_detection": [store.latest_id("dependency_graph")] if store.latest_id("dependency_graph") else [],
            "patch_generation": [store.latest_id("issues")] if store.latest_id("issues") else [],
            "test_validation": (
                ([store.latest_id("patch_result")] if store.latest_id("patch_result") else [])
            ),
            "merge_findings": [
                aid for aid in [
                    store.latest_id("repo_analysis"),
                    store.latest_id("issues"),
                ] if aid
            ],
            "rollback_on_failure": (
                [store.latest_id("patch_result")] if store.latest_id("patch_result") else []
            ),
        }
        return [a for a in inputs.get(goal, []) if a]

    def _find_node_id(self, plan: ExecutionPlan, name: str) -> str:
        for node in plan.nodes.values():
            if node.name == name:
                return node.node_id
        return ""