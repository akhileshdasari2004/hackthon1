"""Execution context with artifact store, isolation, and audit trail."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agira.artifacts.store import ArtifactStore
from agira.observability.logging import get_trace_id
from agira.observability.rate_limiter import RateLimiter
from agira.sandbox.executor import SandboxExecutor


@dataclass
class ExecutionContext:
    repo_path: Path
    trace_id: str = field(default_factory=get_trace_id)
    sandbox: SandboxExecutor = field(default_factory=SandboxExecutor)
    rate_limiter: RateLimiter = field(default_factory=RateLimiter)
    artifact_store: ArtifactStore = field(default_factory=ArtifactStore)
    state: dict[str, Any] = field(default_factory=dict)
    patches_applied: list[dict[str, Any]] = field(default_factory=list)
    failure_history: list[dict[str, Any]] = field(default_factory=list)
    tool_usage: dict[str, int] = field(default_factory=dict)
    tool_call_count: int = 0
    isolated: bool = False
    parent_repo_path: Path | None = None
    pending_merge: list[dict[str, Any]] = field(default_factory=list)

    def store_result(
        self,
        artifact_type: str,
        data: Any,
        *,
        producer: str,
        dependencies: list[str] | None = None,
    ) -> str:
        return self.artifact_store.put(
            artifact_type, data, producer=producer, dependencies=dependencies or [],
        )

    def record_failure(self, source: str, error: str, details: dict | None = None) -> None:
        self.failure_history.append({
            "source": source, "error": error, "details": details or {},
        })

    def increment_tool_calls(self, tool_name: str) -> int:
        self.tool_call_count += 1
        self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1
        return self.tool_call_count

    def create_isolated_workdir(self) -> ExecutionContext:
        """Copy-on-write isolated workspace for subagent execution."""
        work_dir = Path(tempfile.mkdtemp(prefix="agira_agent_"))
        shutil.copytree(self.repo_path, work_dir, dirs_exist_ok=True)
        isolated = ExecutionContext(
            repo_path=work_dir,
            trace_id=f"{self.trace_id}:iso",
            sandbox=self.sandbox,
            rate_limiter=self.rate_limiter,
            isolated=True,
            parent_repo_path=self.repo_path,
        )
        isolated.state["_registry"] = self.state.get("_registry")
        dep_id = self.artifact_store.latest_id("dependency_graph")
        if dep_id:
            isolated.artifact_store.put(
                "dependency_graph",
                self.artifact_store.get_data(dep_id),
                producer="parent_context",
                dependencies=[dep_id],
            )
        return isolated

    def queue_merge(self, proposal: dict[str, Any]) -> None:
        self.pending_merge.append(proposal)

    def apply_approved_merge(self, proposal: dict[str, Any]) -> None:
        """Orchestrator-approved merge from subagent isolated workspace."""
        if proposal.get("type") == "patches":
            for patch in proposal.get("patches", []):
                src = Path(patch["path"])
                if self.parent_repo_path:
                    dst = self.parent_repo_path / patch.get("rel_path", src.name)
                    if src.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)
                self.patches_applied.append(patch)
        if proposal.get("type") == "artifacts":
            for aid, data in proposal.get("artifacts", {}).items():
                self.artifact_store.put(data["type"], data["data"], producer=data.get("producer", "merge"))

    def to_checkpoint_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "repo_path": str(self.repo_path),
            "artifacts": self.artifact_store.to_dict(),
            "failure_history": self.failure_history,
            "tool_usage": self.tool_usage,
            "tool_call_count": self.tool_call_count,
            "patches_applied": self.patches_applied,
            "state": {k: v for k, v in self.state.items() if k != "_registry"},
        }

    def load_checkpoint_dict(self, data: dict[str, Any]) -> None:
        self.trace_id = data.get("trace_id", self.trace_id)
        self.artifact_store.from_dict(data.get("artifacts", {}))
        self.failure_history = data.get("failure_history", [])
        self.tool_usage = data.get("tool_usage", {})
        self.tool_call_count = data.get("tool_call_count", 0)
        self.patches_applied = data.get("patches_applied", [])
        self.state.update(data.get("state", {}))

    @property
    def artifacts(self) -> dict[str, Any]:
        return {a.artifact_id: a.data for a in self.artifact_store._artifacts.values()}

    def store_artifact(self, key: str, value: Any) -> str:
        return self.artifact_store.put(key, value, producer="legacy")

    def get_artifact(self, key: str) -> Any:
        art = self.artifact_store.latest(key)
        return art.data if art else None
