#!/usr/bin/env python3
"""Thin job runner for frontend API — does not modify agira internals."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: job_runner.py <job_dir> <repo_path> [settings_json]"}))
        return 1

    job_dir = Path(sys.argv[1])
    repo_input = sys.argv[2]
    settings = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}

    job_dir.mkdir(parents=True, exist_ok=True)
    write_json(job_dir / "status.json", {"status": "running", "progress": 0, "nodes": [], "logs": []})

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
                write_json(job_dir / "status.json", {"status": "failed", "error": f"Repository not found: {repo_input}"})
                return 1
    except ValueError as exc:
        write_json(job_dir / "status.json", {"status": "failed", "error": str(exc)})
        return 1

    try:
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

        # Hook node execution for live status
        original_execute = orch.state_machine.execute_node

        def tracked_execute(node, plan, ctx):
            write_json(job_dir / "status.json", _build_status(plan, ctx, node.name, "running"))
            result = original_execute(node, plan, ctx)
            write_json(job_dir / "status.json", _build_status(plan, ctx, node.name, node.status.value))
            return result

        orch.state_machine.execute_node = tracked_execute  # type: ignore

        start = time.time()
        result = orch.run(work_dir, mode="demo")
        logger.end_execution()

        report = build_report_from_orchestrator(result, logger, memory_store=orch._memory)
        timeline = logger.to_dict()

        patches = result.context.patches_applied
        issues_art = result.context.artifact_store.latest("issues")
        issues = []
        if issues_art and isinstance(issues_art.data, dict):
            issues = issues_art.data.get("issues", [])

        validation_art = result.context.artifact_store.latest("validation_result")
        validation = validation_art.data if validation_art else {}

        health_art = result.context.artifact_store.latest("health_score")
        health_score = 0
        if health_art and isinstance(health_art.data, dict):
            health_score = health_art.data.get("score", 0)

        payload = {
            "status": "completed" if result.success else "failed",
            "success": result.success,
            "duration_ms": round((time.time() - start) * 1000, 2),
            "report": report.to_dict(),
            "timeline": timeline,
            "issues": issues,
            "patches": patches,
            "validation": validation,
            "health_score": health_score,
            "markdown_report": result.markdown_report,
            "repo_info": _repo_info(work_dir),
            "nodes": _nodes_from_plan(result),
            "progress": 100,
        }
        write_json(job_dir / "result.json", payload)
        write_json(job_dir / "status.json", {**_build_status(result.plan, result.context), "status": payload["status"], "progress": 100})
        return 0
    except Exception as exc:
        write_json(job_dir / "status.json", {"status": "failed", "error": str(exc), "progress": 0})
        return 1
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


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
            "duration_ms": None,
            "error": n.error,
            "retry_count": n.retry_count,
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
