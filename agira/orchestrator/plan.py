"""Dynamic execution plan with DAG nodes and dependency tracking."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class NodeStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class PlanNode:
    node_id: str
    name: str
    action_type: str  # "tool" | "subagent" | "goal"
    target: str
    status: NodeStatus = NodeStatus.PENDING
    depends_on: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    input_artifact_ids: list[str] = field(default_factory=list)
    output_artifact_id: str | None = None
    retry_count: int = 0
    max_retries: int = 2
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "action_type": self.action_type,
            "target": self.target,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "params": self.params,
            "input_artifact_ids": self.input_artifact_ids,
            "output_artifact_id": self.output_artifact_id,
            "retry_count": self.retry_count,
            "error": self.error,
        }


@dataclass
class ExecutionPlan:
    plan_id: str
    repo_path: str
    nodes: dict[str, PlanNode] = field(default_factory=dict)
    goals: list[str] = field(default_factory=list)
    status: str = "pending"
    last_checkpoint: str | None = None
    iteration: int = 0
    max_iterations: int = 30
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, repo_path: str) -> ExecutionPlan:
        return cls(plan_id=str(uuid.uuid4()), repo_path=repo_path)

    def add_node(
        self,
        name: str,
        action_type: str,
        target: str,
        *,
        depends_on: list[str] | None = None,
        params: dict[str, Any] | None = None,
        input_artifact_ids: list[str] | None = None,
    ) -> PlanNode:
        node = PlanNode(
            node_id=str(uuid.uuid4())[:8],
            name=name,
            action_type=action_type,
            target=target,
            depends_on=depends_on or [],
            params=params or {},
            input_artifact_ids=input_artifact_ids or [],
        )
        self.nodes[node.node_id] = node
        return node

    def ready_nodes(self) -> list[PlanNode]:
        completed = {nid for nid, n in self.nodes.items() if n.status == NodeStatus.COMPLETED}
        ready = []
        for node in self.nodes.values():
            if node.status != NodeStatus.PENDING:
                continue
            if all(dep in completed for dep in node.depends_on):
                node.status = NodeStatus.READY
                ready.append(node)
        return ready

    def checkpoint(self, label: str) -> None:
        self.last_checkpoint = label

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "repo_path": self.repo_path,
            "status": self.status,
            "goals": self.goals,
            "iteration": self.iteration,
            "last_checkpoint": self.last_checkpoint,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionPlan:
        plan = cls(
            plan_id=data["plan_id"],
            repo_path=data["repo_path"],
            status=data.get("status", "pending"),
            goals=data.get("goals", []),
            iteration=data.get("iteration", 0),
            last_checkpoint=data.get("last_checkpoint"),
            metadata=data.get("metadata", {}),
        )
        for raw in data.get("nodes", {}).values():
            plan.nodes[raw["node_id"]] = PlanNode(
                node_id=raw["node_id"],
                name=raw["name"],
                action_type=raw["action_type"],
                target=raw["target"],
                status=NodeStatus(raw.get("status", "pending")),
                depends_on=raw.get("depends_on", []),
                params=raw.get("params", {}),
                input_artifact_ids=raw.get("input_artifact_ids", []),
                output_artifact_id=raw.get("output_artifact_id"),
                retry_count=raw.get("retry_count", 0),
                error=raw.get("error"),
            )
        return plan
