"""Tests for adaptive orchestrator.

Integration tests — require Docker available for sandbox execution.
These tests run the full orchestrator with sandbox enforcement enabled.
Skipped if Docker is not available (AGIRA_SANDBOX_MODE=docker requires Docker).
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from agira.orchestrator.engine import Orchestrator
from agira.orchestrator.plan import NodeStatus
from agira.registry.registry import create_registry

EXAMPLES = Path(__file__).parent.parent / "examples" / "buggy_calculator"


def _docker_available() -> bool:
    """Check if Docker is available and agira-sandbox image exists."""
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        if r.returncode != 0:
            return False
        # Check if sandbox image exists
        r2 = subprocess.run(
            ["docker", "image", "ls", "-q", "agira/sandbox:latest"],
            capture_output=True, timeout=5,
        )
        return r2.returncode == 0 and bool(r2.stdout.strip())
    except Exception:
        return False


needs_docker = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker or agira-sandbox image not available. "
           "Build with: docker build --target sandbox -t agira/sandbox:latest .")


def _copy_fixture() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="agira_test_"))
    shutil.copytree(EXAMPLES, tmp, dirs_exist_ok=True)
    return tmp


def _run_orchestrator(**kwargs):
    """Run orchestrator with sandbox mode enforced."""
    # Set sandbox mode for these integration tests
    old_mode = os.environ.get("AGIRA_SANDBOX_MODE", "")
    os.environ["AGIRA_SANDBOX_MODE"] = "docker"
    try:
        orch = Orchestrator(create_registry())
        result = orch.run(**kwargs)
        return result
    finally:
        if old_mode:
            os.environ["AGIRA_SANDBOX_MODE"] = old_mode
        else:
            os.environ.pop("AGIRA_SANDBOX_MODE", None)


@needs_docker
def test_orchestrator_dynamic_execution():
    if not EXAMPLES.exists():
        return
    result = _run_orchestrator(_copy_fixture(), mode="debug")
    # tool_calls counts only top-level tool invocations, not subagent-internal calls
    # With deterministic no-retry execution, this should be reasonable (7 for this example)
    assert result.tool_calls >= 5  # At least some top-level work
    assert len(result.plan.nodes) >= 10  # Full DAG execution
    assert result.success  # System should complete successfully


@needs_docker
def test_plan_has_dag_nodes():
    if not EXAMPLES.exists():
        return
    result = _run_orchestrator(_copy_fixture(), mode="debug")
    assert result.plan.plan_id
    completed = [n for n in result.plan.nodes.values() if n.status == NodeStatus.COMPLETED]
    assert len(completed) >= 5


@needs_docker
def test_artifact_store_populated():
    if not EXAMPLES.exists():
        return
    result = _run_orchestrator(_copy_fixture(), mode="debug")
    store = result.context.artifact_store
    assert store.has_type("repo_metadata") or store.has_type("issues")


@needs_docker
def test_success_requires_validation():
    if not EXAMPLES.exists():
        return
    result = _run_orchestrator(_copy_fixture(), mode="debug")
    if result.success:
        validation = result.context.artifact_store.latest("validation_result")
        assert validation is not None
