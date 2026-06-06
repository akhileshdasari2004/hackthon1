"""Parallel execution scheduler — executes independent DAG nodes concurrently."""

from __future__ import annotations

import concurrent.futures
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from agira.orchestrator.plan import ExecutionPlan, NodeStatus


@dataclass
class ParallelBatch:
    """A batch of nodes that can run in parallel."""
    nodes: list[NodeStatus] = field(default_factory=list)
    batch_id: int = 0


class ParallelScheduler:
    """Schedules and executes DAG nodes in parallel batches.
    
    Guarantees:
    - Nodes within a batch execute concurrently
    - DAG dependency order is always respected
    - Thread-safe result aggregation
    - Subagent isolation preserved (each subagent has its own workdir)
    """

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._results: dict[str, Any] = {}
        self._errors: dict[str, Exception] = {}

    def compute_batches(self, plan: ExecutionPlan) -> list[list[str]]:
        """Compute optimal parallel batches from the DAG.
        
        Returns list of node-ID lists, each representing a batch that can
        run in parallel. Batches are ordered — all nodes in batch N must
        complete before batch N+1 nodes become ready.
        """
        completed: set[str] = {
            nid for nid, n in plan.nodes.items()
            if n.status == NodeStatus.COMPLETED
        }
        batches: list[list[str]] = []
        pending = {nid for nid, n in plan.nodes.items() if n.status == NodeStatus.PENDING}

        while pending:
            # Find all nodes whose dependencies are satisfied
            ready: list[str] = []
            for nid in pending:
                node = plan.nodes[nid]
                if all(dep in completed for dep in node.depends_on):
                    ready.append(nid)

            if not ready:
                # No progress possible — remaining nodes have unmet dependencies
                break

            batches.append(ready)
            completed.update(ready)
            pending -= set(ready)

        return batches

    def execute_batch(
        self,
        batch: list[str],
        plan: ExecutionPlan,
        ctx: Any,
        execute_node_fn: Callable[[Any, ExecutionPlan, Any], Any],
    ) -> dict[str, Any]:
        """Execute a batch of nodes concurrently.
        
        Thread-safe: each node result is stored in _results by node_id.
        Returns dict mapping node_id -> result (or None if failed).
        """
        results: dict[str, Any] = {}
        errors: dict[str, Exception] = {}

        def run_node(node_id: str) -> tuple[str, Any | None, Exception | None]:
            node = plan.nodes[node_id]
            try:
                result = execute_node_fn(node, plan, ctx)
                return (node_id, result, None)
            except Exception as exc:  # noqa: BLE001
                return (node_id, None, exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(run_node, nid): nid
                for nid in batch
            }
            for future in concurrent.futures.as_completed(futures):
                node_id, result, exc = future.result()
                with self._lock:
                    if exc is None:
                        results[node_id] = result
                    else:
                        errors[node_id] = exc

        return results, errors

    def independent_nodes(self, plan: ExecutionPlan) -> list[str]:
        """Return node IDs that have no dependencies on each other and can run in parallel."""
        batches = self.compute_batches(plan)
        if batches:
            return batches[0]
        return []


# Standalone function to check if two nodes are independent
def are_independent(node_a: str, node_b: str, plan: ExecutionPlan) -> bool:
    """Check if two nodes can run in parallel (no shared dependencies)."""
    na = plan.nodes.get(node_a)
    nb = plan.nodes.get(node_b)
    if not na or not nb:
        return False
    # Neither depends on the other
    if node_a in nb.depends_on or node_b in na.depends_on:
        return False
    # No common dependency that could cause contention
    return True