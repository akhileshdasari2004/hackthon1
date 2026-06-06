"""DAG repair logic — re-evaluates dependencies after failures."""

from __future__ import annotations

from typing import Any

from agira.orchestrator.plan import ExecutionPlan, NodeStatus


class DAGRepair:
    """Repairs and re-balances DAG after failures."""

    def __init__(self, plan: ExecutionPlan) -> None:
        self.plan = plan

    def repair_after_failure(self, failed_node_id: str) -> list[str]:
        """Handle a node failure — re-evaluate dependent nodes.
        
        Returns list of node IDs that need to be retried or re-proposed.
        """
        failed_node = self.plan.nodes.get(failed_node_id)
        if not failed_node:
            return []

        affected: list[str] = []
        dependents = self._find_dependents(failed_node_id)

        for dep_id in dependents:
            dep_node = self.plan.nodes.get(dep_id)
            if not dep_node:
                continue
            if dep_node.status == NodeStatus.FAILED:
                continue
            # Mark dependent as blocked so it can be retried
            dep_node.status = NodeStatus.PENDING
            affected.append(dep_id)

        return affected

    def _find_dependents(self, node_id: str) -> list[str]:
        """Find all nodes that depend on this node."""
        return [
            nid for nid, node in self.plan.nodes.items()
            if node_id in node.depends_on
        ]

    def unblock_when_ready(self, completed_node_id: str) -> list[str]:
        """When a node completes, unblock any nodes that were waiting on it."""
        unblocked: list[str] = []
        for node in self.plan.nodes.values():
            if node.status == NodeStatus.PENDING:
                if any(dep in self.plan.completed_node_ids() for dep in node.depends_on):
                    node.status = NodeStatus.READY
                    unblocked.append(node.node_id)
        return unblocked

    def rerank_failed(self, max_retries: int = 2) -> list[str]:
        """Find failed nodes eligible for retry."""
        candidates = [
            nid for nid, n in self.plan.nodes.items()
            if n.status == NodeStatus.FAILED and n.retry_count < max_retries
        ]
        for nid in candidates:
            self.plan.nodes[nid].status = NodeStatus.PENDING
        return candidates

    def should_skip_node(self, node_id: str) -> bool:
        """Determine if a node should be skipped given DAG state."""
        node = self.plan.nodes.get(node_id)
        if not node:
            return True
        # If all dependencies are satisfied (completed or skipped), allow to run
        completed = {nid for nid, n in self.plan.nodes.items() if n.status == NodeStatus.COMPLETED}
        skipped = {nid for nid, n in self.plan.nodes.items() if n.status == NodeStatus.SKIPPED}
        satisfied = completed | skipped
        return all(dep in satisfied for dep in node.depends_on)


# Monkey-patch onto ExecutionPlan for convenience
def completed_node_ids(self) -> set[str]:
    return {nid for nid, n in self.nodes.items() if n.status == NodeStatus.COMPLETED}


ExecutionPlan.completed_node_ids = completed_node_ids