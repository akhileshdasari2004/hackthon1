"""Tests for artifact store and composition."""

from agira.artifacts.store import ArtifactStore
from agira.registry.registry import create_registry
from agira.tools.context import ExecutionContext
import shutil
import tempfile
from pathlib import Path

EXAMPLES = Path(__file__).parent.parent / "examples" / "buggy_calculator"


def test_artifact_store_versioning():
    store = ArtifactStore()
    aid = store.put("test", {"value": 1}, producer="test")
    store.put("test", {"value": 2}, producer="test", artifact_id=aid)
    assert store.get(aid).version == 2


def test_invoke_pipeline_chaining():
    if not EXAMPLES.exists():
        return
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(EXAMPLES, tmp, dirs_exist_ok=True)
    ctx = ExecutionContext(repo_path=tmp)
    ctx.state["_registry"] = create_registry()
    registry = create_registry()

    results = registry.invoke_pipeline([
        {"tool": "repo_tools.get_repo_metadata", "params": {}},
        {"tool": "repo_tools.list_files", "params": {}, "input_from": 0, "map": {}},
        {"tool": "analysis_tools.build_dependency_graph", "params": {}, "input_from": 1},
    ], ctx)

    assert len(results) == 3
    assert results[0].get("python_files", 0) >= 0
    assert "artifact_id" in results[-1]
