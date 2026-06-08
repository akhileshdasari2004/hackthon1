#!/usr/bin/env python3
"""Thin job runner for frontend API — does not modify agira internals."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── File locking and atomic writes ───────────────────────────────────────────

try:
    from agira.core.file_lock import JobLock, acquire_lock, cleanup_stale_locks
except ImportError:
    JobLock = None
    acquire_lock = None
    cleanup_stale_locks = None

# ── GitHub / GitLab clone support ─────────────────────────────────────────────

import re
import subprocess as _subprocess

_GIT_URL_RE = re.compile(r"^(https?://|git@|ssh://git@|git:)")


def _is_git_url(value: str) -> bool:
    return bool(_GIT_URL_RE.match(value.strip()))


def _strip_git_prefix(value: str) -> str:
    """Strip 'git:' prefix if present, returning the bare URL."""
    return value.strip()[4:] if value.strip().startswith("git:") else value.strip()


def _clone_repository(url: str, target_dir: Path, timeout: int = 120) -> None:
    """Clone a git repository (GitHub, GitLab, etc.) into target_dir.

    Handles:
    - Public repositories (anonymous clone)
    - GitHub tokens embedded in URL (ghp_xxx, github_pat_xxx)
    - GitLab tokens embedded in URL (glpat-xxx)
    - Shallow clones (--depth 1) for speed

    Raises:
        ValueError: If the URL is malformed or clone fails.
    """
    url = url.strip()
    if not url:
        raise ValueError("Empty repository URL")

    target_dir.mkdir(parents=True, exist_ok=True)

    result = _subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", url, str(target_dir)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        # Retry without shallow clone if the repo is shallow-clone-unfriendly
        result = _subprocess.run(
            ["git", "clone", url, str(target_dir)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise ValueError(f"Git clone failed: {result.stderr.strip() or result.stdout.strip()}")


def write_json_atomic(path: Path, data: dict) -> None:
    """Write JSON atomically using temp file + rename.

    Ensures no partial overwrites on crash. Uses os.rename() which is atomic
    on POSIX systems when the source and destination are on the same filesystem.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def write_json(path: Path, data: dict) -> None:
    """Legacy alias for backward compatibility."""
    write_json_atomic(path, data)


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: job_runner.py <job_dir> <repo_path> [settings_json]"}))
        return 1

    job_dir = Path(sys.argv[1])
    repo_input = sys.argv[2]
    settings = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    job_id = job_dir.name  # job_id is the directory name

    # Set up audit logging
    _setup_audit_logging(job_id)

    # ── File locking: prevent duplicate execution ──────────────────────────
    jobs_dir = job_dir.parent
    lock = None
    if acquire_lock is not None:
        lock_result = acquire_lock(job_id, str(jobs_dir), timeout=0.0)
        if not lock_result.acquired:
            # Another instance is already running this job
            print(json.dumps({"error": f"Job {job_id} is already running or locked"}))
            return 1

    # Cleanup stale locks from previous crashed runs
    if cleanup_stale_locks is not None:
        cleanup_stale_locks(str(jobs_dir))

    try:
        job_dir.mkdir(parents=True, exist_ok=True)
        # Atomic write: mark job as running
        write_json_atomic(job_dir / "status.json", {"status": "running", "progress": 0, "nodes": [], "logs": []})
        _log_audit("job_state", job_id, state="running")

        # Prepare repo — supports local paths AND git URLs
        work_dir = Path(tempfile.mkdtemp(prefix="agira_job_"))
        try:
            if _is_git_url(repo_input):
                _clone_repository(_strip_git_prefix(repo_input), work_dir)
            else:
                repo_path = Path(repo_input)
                if not repo_path.is_absolute():
                    repo_path = ROOT / repo_path
                if repo_path.exists():
                    shutil.copytree(repo_path, work_dir, dirs_exist_ok=True)
                else:
                    _fail_job(job_dir, job_id, f"Repository not found: {repo_input}")
                    return 1
        except ValueError as exc:
            _fail_job(job_dir, job_id, str(exc))
            return 1

        # Run the orchestrator
        start_time = time.time()
        run_result = _run_orchestrator(work_dir, job_dir, settings, job_id)

        if run_result is None:
            return 1  # Error already handled and logged

        result, orch, logger, payload = run_result
        logger.end_execution()

        # ── Atomic write: complete result.json and status.json ──────────────
        write_json_atomic(job_dir / "result.json", payload)
        write_json_atomic(job_dir / "status.json", {
            **_build_status(result.plan, result.context),
            "status": payload["status"],
            "progress": 100,
        })
        _log_audit("job_state", job_id, state=payload["status"])
        return 0

    except Exception as exc:
        _fail_job(job_dir, job_id, str(exc))
        return 1
    finally:
        if lock is not None and hasattr(lock, "lock") and lock.lock is not None:
            lock.lock.release()
        shutil.rmtree(work_dir, ignore_errors=True)


def _setup_audit_logging(job_id: str) -> None:
    """Set up environment variables for audit logging."""
    os.environ["AGIRA_JOB_ID"] = job_id
    os.environ["AGIRA_TRACE_ID"] = os.environ.get("AGIRA_TRACE_ID", job_id)


def _log_audit(event: str, job_id: str, **kwargs) -> None:
    """Log to audit log if available."""
    audit_path = os.environ.get("AGIRA_AUDIT_PATH", "/data/audit.log")
    if not audit_path:
        return
    try:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "job_id": job_id,
            "event": event,
            **kwargs,
        }
        entry = {k: v for k, v in entry.items() if v}
        os.makedirs(os.path.dirname(audit_path), exist_ok=True)
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass


def _fail_job(job_dir: Path, job_id: str, error: str) -> None:
    """Atomically write failed status and partial result."""
    try:
        partial = {
            "status": "failed",
            "error": error,
            "progress": 0,
            "nodes": [],
            "logs": [],
        }
        write_json_atomic(job_dir / "status.json", partial)
        _log_audit("job_state", job_id, state="failed", error=error)
    except Exception:
        pass


def _run_orchestrator(work_dir: Path, job_dir: Path, settings: dict, job_id: str):
    """Run the orchestrator with error handling and partial result preservation."""
    from agira.orchestrator.engine import Orchestrator
    from agira.orchestrator.plan import NodeStatus
    from agira.registry.registry import create_registry
    from agira.report.final_report import build_report_from_orchestrator
    from agira.utils import get_execution_logger, reset_execution_logger

    reset_execution_logger()
    logger = get_execution_logger()
    logger.start_execution()

    orch = Orchestrator(
        registry=create_registry(),
        parallel_scheduling=settings.get("parallel_scheduling", True),
        self_healing=settings.get("self_healing", True),
        memory_layer=settings.get("memory_layer", True),
        adaptive_planning=settings.get("adaptive_planning", True),
    )

    # Hook node execution for live status with atomic writes
    original_execute = orch.state_machine.execute_node

    def tracked_execute(node, plan, ctx):
        # Atomic write for node start
        write_json_atomic(job_dir / "status.json", _build_status(plan, ctx, node.name, "running"))
        _log_audit("dag_node_start", job_id, node=node.name, batch=getattr(node, "batch_id", 0))
        result = original_execute(node, plan, ctx)
        # Atomic write for node end
        write_json_atomic(job_dir / "status.json", _build_status(plan, ctx, node.name, node.status.value))
        _log_audit("dag_node_end", job_id, node=node.name, status=node.status.value)
        return result

    orch.state_machine.execute_node = tracked_execute  # type: ignore

    start = time.time()
    _log_audit("dag_start", job_id)

    try:
        result = orch.run(work_dir, mode="demo")
    except Exception as exc:
        # Save partial result if possible
        partial = {
            "status": "failed",
            "error": str(exc),
            "progress": 0,
            "nodes": [],
            "logs": [],
        }
        if hasattr(orch, "plan") and orch.plan:
            partial["nodes"] = [
                {"name": n.name, "status": n.status.value, "error": n.error}
                for n in orch.plan.nodes.values()
            ]
            partial["progress"] = sum(1 for n in orch.plan.nodes.values() if n.status == NodeStatus.COMPLETED) / max(len(orch.plan.nodes), 1) * 100
        write_json_atomic(job_dir / "status.json", partial)
        raise

    # Extract issues from artifact store after run completes
    issues_art = result.context.artifact_store.latest("issues")
    classified_issues = []
    if issues_art:
        data = issues_art.data
        raw_issues = data.get("issues", data) if isinstance(data, dict) else data
        classified_issues = raw_issues if isinstance(raw_issues, list) else []

    report = build_report_from_orchestrator(result, logger, memory_store=orch._memory, issues=classified_issues)
    timeline = logger.to_dict()

    patches = result.context.patches_applied or []

    validation_art = result.context.artifact_store.latest("validation_result")
    validation = validation_art.data if validation_art else {}

    health_art = result.context.artifact_store.latest("health_score")
    health_score = 0
    if health_art and isinstance(health_art.data, dict):
        health_score = health_art.data.get("score", 0)

    duration_ms = round((time.time() - start) * 1000, 2)

    payload = {
        "status": "completed" if result.success else "failed",
        "success": result.success,
        "duration_ms": duration_ms,
        "report": report.to_dict(),
        "timeline": timeline,
        "issues": classified_issues,
        "patches": patches,
        "validation": validation,
        "health_score": health_score,
        "markdown_report": result.markdown_report,
        "repo_info": _repo_info(work_dir),
        "nodes": _nodes_from_plan(result),
        "progress": 100,
    }

    _log_audit("dag_end", job_id, success=result.success, duration_ms=duration_ms)
    return result, orch, logger, payload


def _repo_info(repo_path: Path) -> dict:
    py_files = list(repo_path.rglob("*.py"))
    return {
        "name": repo_path.name,
        "path": str(repo_path),
        "language": "Python",
        "file_count": len(py_files),
        "lines": sum(f.read_text(errors="ignore").count("\n") for f in py_files[:50]),
    }


def _nodes_from_plan(result) -> list:
    return [
        {
            "name": n.name,
            "status": n.status.value,
            "action_type": n.action_type,
            "target": n.target,
            "duration_ms": getattr(n, "duration_ms", None),
            "error": n.error,
            "retry_count": n.retry_count,
            "started_at": getattr(n, "started_at", None),
            "completed_at": getattr(n, "completed_at", None),
        }
        for n in result.plan.nodes.values()
    ]


def _build_status(plan, ctx, current: str | None = None, event: str | None = None) -> dict:
    nodes = [
        {
            "name": n.name,
            "status": _map_status(n.status.value),
            "action_type": n.action_type,
            "target": n.target,
            "batch": _batch_for(n.name),
            "error": n.error,
        }
        for n in plan.nodes.values()
    ]
    completed = sum(1 for n in nodes if n["status"] in ("success", "failed", "skipped"))
    total = max(len(nodes), 1)
    return {
        "status": "running",
        "progress": round(completed / total * 100),
        "current_node": current,
        "last_event": event,
        "nodes": nodes,
        "logs": [{"message": f"{current or ''} {event or ''}".strip(), "timestamp": time.time()}] if current else [],
    }


def _map_status(s: str) -> str:
    return {"completed": "success", "failed": "failed", "skipped": "skipped", "running": "running"}.get(s, "pending")


def _batch_for(name: str) -> int:
    batches = {
        "repo_metadata": 1, "file_list": 1, "dependency_graph": 1,
        "bug_detection": 2, "repo_analysis": 2,
        "merge_findings": 3,
        "initial_validation": 4, "patch_generation": 4,
        "test_validation": 5,
        "health_score": 6, "json_report": 6, "markdown_report": 6,
    }
    return batches.get(name, 0)


if __name__ == "__main__":
    sys.exit(main())
