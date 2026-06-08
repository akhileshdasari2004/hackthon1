"""Audit logging for sandbox execution traceability.

Append-only log file at /data/audit.log capturing every sandbox execution
with job_id correlation, timing, and status.

Schema:
{
  "timestamp": "ISO8601",
  "job_id": "...",
  "node": "...",
  "command": "...",
  "image": "...",
  "status": "success|failed",
  "exit_code": 0,
  "duration_ms": 0
}

Usage:
    from agira.observability.audit_logger import AuditLogger, get_audit_logger

    audit = get_audit_logger()
    audit.log_sandbox_start(job_id="abc", node="bug_detection",
                            command=["pytest"], image="sandbox:latest")
    # ... execute ...
    audit.log_sandbox_end(job_id="abc", node="bug_detection",
                          exit_code=0, duration_ms=1500)
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Audit log path — mounted volume in Docker
DEFAULT_AUDIT_PATH = Path(os.environ.get("AGIRA_AUDIT_PATH", "/data/audit.log"))


@dataclass
class AuditEntry:
    """Single audit log entry."""

    timestamp: str
    job_id: str
    node: str
    command: str
    image: str
    status: str  # "started" | "success" | "failed" | "timeout"
    exit_code: int = 0
    duration_ms: float = 0.0
    error: str | None = None
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "job_id": self.job_id,
            "node": self.node,
            "command": self.command,
            "image": self.image,
            "status": self.status,
            "exit_code": self.exit_code,
            "duration_ms": round(self.duration_ms, 2),
            "error": self.error,
            "trace_id": self.trace_id,
        }


class AuditLogger:
    """Thread-safe, append-only audit logger.

    Uses file locking (fcntl) for safe concurrent writes from multiple
    processes/threads. Each write is atomic (single JSON line).

    The log file format:
        {"timestamp": "...", "job_id": "...", ...}
        {"timestamp": "...", "job_id": "...", ...}
        ...

    Usage:
        audit = AuditLogger()
        audit.log_sandbox_start(job_id="123", node="bug_detection", command=["pytest"])
        # ... execute sandbox ...
        audit.log_sandbox_end(job_id="123", node="bug_detection", exit_code=0, duration_ms=100)
    """

    def __init__(
        self,
        audit_path: str | Path = DEFAULT_AUDIT_PATH,
        thread_safe: bool = True,
    ) -> None:
        self.audit_path = Path(audit_path)
        self._thread_lock = threading.Lock() if thread_safe else None
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Create audit directory if it doesn't exist."""
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def _now_iso(self) -> str:
        """Return current UTC timestamp in ISO8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def _write_entry(self, entry: dict[str, Any]) -> None:
        """Write a single JSON line to audit log with file locking."""
        line = json.dumps(entry, default=str) + "\n"

        if self._thread_lock:
            self._thread_lock.acquire()
        try:
            with open(self.audit_path, "a", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(line)
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        finally:
            if self._thread_lock:
                self._thread_lock.release()

    def log_sandbox_start(
        self,
        job_id: str,
        node: str,
        command: str | list[str],
        image: str,
        trace_id: str | None = None,
    ) -> AuditEntry:
        """Log sandbox execution start."""
        if isinstance(command, list):
            command = " ".join(command)
        entry = AuditEntry(
            timestamp=self._now_iso(),
            job_id=job_id,
            node=node,
            command=command,
            image=image,
            status="started",
        )
        if trace_id:
            entry.trace_id = trace_id
        self._write_entry(entry.to_dict())
        return entry

    def log_sandbox_end(
        self,
        job_id: str,
        node: str,
        command: str | list[str],
        image: str,
        exit_code: int,
        duration_ms: float,
        status: str | None = None,
        error: str | None = None,
        trace_id: str | None = None,
    ) -> AuditEntry:
        """Log sandbox execution end."""
        if isinstance(command, list):
            command = " ".join(command)
        if status is None:
            if exit_code == -1 or (error and "Timed out" in str(error)):
                status = "timeout"
            elif exit_code == 0:
                status = "success"
            else:
                status = "failed"
        entry = AuditEntry(
            timestamp=self._now_iso(),
            job_id=job_id,
            node=node,
            command=command,
            image=image,
            status=status,
            exit_code=exit_code,
            duration_ms=duration_ms,
            error=error,
        )
        if trace_id:
            entry.trace_id = trace_id
        self._write_entry(entry.to_dict())
        return entry

    def log_dag_start(
        self,
        job_id: str,
        trace_id: str | None = None,
    ) -> AuditEntry:
        """Log DAG execution start."""
        entry = AuditEntry(
            timestamp=self._now_iso(),
            job_id=job_id,
            node="__dag__",
            command="",
            image="",
            status="started",
        )
        if trace_id:
            entry.trace_id = trace_id
        self._write_entry(entry.to_dict())
        return entry

    def log_dag_end(
        self,
        job_id: str,
        success: bool,
        duration_ms: float,
        trace_id: str | None = None,
    ) -> AuditEntry:
        """Log DAG execution end."""
        entry = AuditEntry(
            timestamp=self._now_iso(),
            job_id=job_id,
            node="__dag__",
            command="",
            image="",
            status="success" if success else "failed",
            exit_code=0 if success else 1,
            duration_ms=duration_ms,
        )
        if trace_id:
            entry.trace_id = trace_id
        self._write_entry(entry.to_dict())
        return entry

    def log_node_start(
        self,
        job_id: str,
        node: str,
        trace_id: str | None = None,
    ) -> AuditEntry:
        """Log DAG node start."""
        entry = AuditEntry(
            timestamp=self._now_iso(),
            job_id=job_id,
            node=node,
            command="",
            image="",
            status="started",
        )
        if trace_id:
            entry.trace_id = trace_id
        self._write_entry(entry.to_dict())
        return entry

    def log_node_end(
        self,
        job_id: str,
        node: str,
        status: str,
        duration_ms: float = 0.0,
        error: str | None = None,
        trace_id: str | None = None,
    ) -> AuditEntry:
        """Log DAG node end."""
        entry = AuditEntry(
            timestamp=self._now_iso(),
            job_id=job_id,
            node=node,
            command="",
            image="",
            status=status,
            duration_ms=duration_ms,
            error=error,
        )
        if trace_id:
            entry.trace_id = trace_id
        self._write_entry(entry.to_dict())
        return entry

    def log_job_state(
        self,
        job_id: str,
        state: str,
        trace_id: str | None = None,
    ) -> AuditEntry:
        """Log job state transition."""
        entry = AuditEntry(
            timestamp=self._now_iso(),
            job_id=job_id,
            node="__state__",
            command="",
            image="",
            status=state,  # "queued" | "running" | "done" | "failed"
        )
        if trace_id:
            entry.trace_id = trace_id
        self._write_entry(entry.to_dict())
        return entry

    def read_entries(
        self,
        job_id: str | None = None,
        limit: int | None = None,
    ) -> list[AuditEntry]:
        """Read audit log entries, optionally filtered by job_id.

        Note: This reads the entire log file. For production,
        use log slicing strategies if file grows large.
        """
        if not self.audit_path.exists():
            return []
        entries = []
        try:
            with open(self.audit_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if job_id is None or data.get("job_id") == job_id:
                            entries.append(AuditEntry(**data))
                            if limit and len(entries) >= limit:
                                break
                    except (json.JSONDecodeError, TypeError):
                        continue
        except OSError:
            pass
        return entries


# Global audit logger instance (per-process singleton)
_audit_logger: AuditLogger | None = None
_audit_lock = threading.Lock()


def get_audit_logger(
    audit_path: str | Path = DEFAULT_AUDIT_PATH,
) -> AuditLogger:
    """Get or create the global audit logger singleton."""
    global _audit_logger
    if _audit_logger is None:
        with _audit_lock:
            if _audit_logger is None:
                _audit_logger = AuditLogger(audit_path=audit_path)
    return _audit_logger


def reset_audit_logger() -> None:
    """Reset the global audit logger. For testing only."""
    global _audit_logger
    with _audit_lock:
        _audit_logger = None