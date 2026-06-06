"""Tests for adaptive orchestrator."""

import shutil
import tempfile
from pathlib import Path

from agira.orchestrator.engine import Orchestrator
from agira.orchestrator.plan import NodeStatus
from agira.registry.registry import create_registry

EXAMPLES = Path(__file__).parent.parent / "examples" / "buggy_calculator"


def _copy_fixture() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="agira_test_"))
    shutil.copytree(EXAMPLES, tmp, dirs_exist_ok=True)
    return tmp


def test_orchestrator_dynamic_execution():
    if not EXAMPLES.exists():
        return
    orch = Orchestrator(create_registry())
    result = orch.run(_copy_fixture(), mode="debug")
    # tool_calls counts only top-level tool invocations, not subagent-internal calls
    # With deterministic no-retry execution, this should be reasonable (7 for this example)
    assert result.tool_calls >= 5  # At least some top-level work
    assert len(result.plan.nodes) >= 10  # Full DAG execution
    assert result.success  # System should complete successfully


def test_plan_has_dag_nodes():
    if not EXAMPLES.exists():
        return
    orch = Orchestrator(create_registry())
    result = orch.run(_copy_fixture(), mode="debug")
    assert result.plan.plan_id
    completed = [n for n in result.plan.nodes.values() if n.status == NodeStatus.COMPLETED]
    assert len(completed) >= 5


def test_artifact_store_populated():
    if not EXAMPLES.exists():
        return
    orch = Orchestrator(create_registry())
    result = orch.run(_copy_fixture(), mode="debug")
    store = result.context.artifact_store
    assert store.has_type("repo_metadata") or store.has_type("issues")


def test_success_requires_validation():
    if not EXAMPLES.exists():
        return
    orch = Orchestrator(create_registry())
    result = orch.run(_copy_fixture(), mode="debug")
    if result.success:
        validation = result.context.artifact_store.latest("validation_result")
        assert validation is not None
