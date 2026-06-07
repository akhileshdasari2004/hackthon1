"""Persistent cross-run memory store."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MemoryStore:
    """Persistent, thread-safe memory for cross-run learning.
    
    Stores:
    - previous failures (node name -> failure patterns)
    - successful patterns (what worked for what repo structure)
    - repo profiles (language, framework, complexity)
    - tool performance metrics (avg duration, success rate)
    """

    def __init__(self, storage_path: str | Path | None = None) -> None:
        base = Path.home() / ".agira" if not storage_path else Path(storage_path)
        base.mkdir(parents=True, exist_ok=True)
        self.storage_path = base / "memory_store.json"
        self._lock = threading.RLock()
        self._cache: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self._cache = data if isinstance(data, dict) else {}
            except (json.JSONDecodeError, IOError):
                self._cache = {}
        else:
            self._cache = self._default_memory()

    def _default_memory(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "failures": {},
            "successes": {},
            "repo_profiles": {},
            "tool_metrics": {},
            "learning_log": [],
        }

    def _save(self) -> None:
        self._cache["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.storage_path.write_text(
            json.dumps(self._cache, indent=2, default=str), encoding="utf-8"
        )

    # ─── Failure Memory ──────────────────────────────────────────────────────

    def record_failure(
        self,
        node_name: str,
        error_signature: str,
        error_type: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record a failure for cross-run learning."""
        with self._lock:
            if node_name not in self._cache["failures"]:
                self._cache["failures"][node_name] = {}
            bucket = self._cache["failures"][node_name]
            bucket[error_signature] = {
                "count": bucket.get(error_signature, {}).get("count", 0) + 1,
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "error_type": error_type,
                "details": details or {},
            }
            self._save()

    def get_known_failures(self, node_name: str) -> dict[str, Any]:
        """Return known failure patterns for a node."""
        with self._lock:
            return dict(self._cache["failures"].get(node_name, {}))

    # ─── Success Memory ───────────────────────────────────────────────────────

    def record_success(
        self,
        goal_name: str,
        repo_path: str,
        context: dict[str, Any],
    ) -> None:
        """Record a successful execution pattern."""
        with self._lock:
            key = f"{goal_name}:{Path(repo_path).name}"
            self._cache["successes"][key] = {
                "goal": goal_name,
                "repo": str(repo_path),
                "context": context,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._save()

    def get_success_pattern(self, goal_name: str, repo_name: str) -> dict[str, Any] | None:
        """Get a known successful pattern for similar context."""
        with self._lock:
            key = f"{goal_name}:{repo_name}"
            return self._cache["successes"].get(key)

    # ─── Repo Profiles ────────────────────────────────────────────────────────

    def record_repo_profile(self, repo_path: str, profile: dict[str, Any]) -> None:
        """Store repo characteristics for future optimization."""
        with self._lock:
            self._cache["repo_profiles"][repo_path] = {
                **profile,
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
            self._save()

    def get_repo_profile(self, repo_path: str) -> dict[str, Any] | None:
        """Get stored repo profile."""
        with self._lock:
            return self._cache["repo_profiles"].get(repo_path)

    # ─── Tool Metrics ─────────────────────────────────────────────────────────

    def record_tool_metrics(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
    ) -> None:
        """Record per-tool performance metrics."""
        with self._lock:
            if tool_name not in self._cache["tool_metrics"]:
                self._cache["tool_metrics"][tool_name] = {
                    "calls": 0,
                    "failures": 0,
                    "total_duration_ms": 0.0,
                    "avg_duration_ms": 0.0,
                }
            m = self._cache["tool_metrics"][tool_name]
            m["calls"] += 1
            m["total_duration_ms"] += duration_ms
            if not success:
                m["failures"] += 1
            m["avg_duration_ms"] = round(m["total_duration_ms"] / m["calls"], 2)
            self._save()

    def get_tool_metrics(self, tool_name: str) -> dict[str, Any]:
        """Get performance metrics for a tool."""
        with self._lock:
            return dict(self._cache["tool_metrics"].get(tool_name, {}))

    # ─── Learning Log ─────────────────────────────────────────────────────────

    def log_learning(self, event: str, data: dict[str, Any]) -> None:
        """Append a learning event to the log."""
        with self._lock:
            self._cache["learning_log"].append({
                "event": event,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data,
            })
            # Keep last 500 entries — truncate BEFORE save to avoid writing excess
            if len(self._cache["learning_log"]) > 500:
                self._cache["learning_log"] = self._cache["learning_log"][-500:]
            self._save()

    # ─── Decision Reason Log ──────────────────────────────────────────────

    def log_decision_reason(
        self,
        decision_type: str,
        target: str,
        reason: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log a planner/agent decision reason for explainability.
        
        Stores why the planner made a specific decision so the demo can
        show memory-influenced reasoning.
        
        Args:
            decision_type: one of "skip", "retry", "prioritize", "avoid", "success"
            target: node/goal/agent name
            reason: human-readable explanation of the decision
            context: additional context (e.g. failure count, error type)
        """
        with self._lock:
            self._cache.setdefault("decision_log", []).append({
                "decision_type": decision_type,
                "target": target,
                "reason": reason,
                "context": context or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            # Keep last 200 decision entries
            log = self._cache["decision_log"]
            if len(log) > 200:
                self._cache["decision_log"] = log[-200:]
            self._save()

    def get_decision_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent decision log entries."""
        with self._lock:
            return list(self._cache.get("decision_log", []))[-limit:]

    def get_memory_stats(self) -> dict[str, Any]:
        """Return memory store statistics."""
        with self._lock:
            return {
                "total_failures": sum(
                    len(v) for v in self._cache["failures"].values()
                ),
                "total_successes": len(self._cache["successes"]),
                "total_repos": len(self._cache["repo_profiles"]),
                "total_tools": len(self._cache["tool_metrics"]),
                "log_entries": len(self._cache["learning_log"]),
                "storage_path": str(self.storage_path),
            }


# Global singleton
_memory_store: MemoryStore | None = None
_memory_lock = threading.Lock()


def get_memory_store() -> MemoryStore:
    global _memory_store
    if _memory_store is None:
        with _memory_lock:
            if _memory_store is None:
                _memory_store = MemoryStore()
    return _memory_store