"""Tests for subagent system."""

from pathlib import Path

from agira.subagents import get_subagent
from agira.tools.context import ExecutionContext

EXAMPLES = Path(__file__).parent.parent / "examples" / "buggy_calculator"


def test_spawn_all_subagent_types():
    ctx = ExecutionContext(repo_path=EXAMPLES)
    for agent_type in [
        "RepoAnalyzerAgent",
        "BugHunterAgent",
        "PatchGeneratorAgent",
        "TestValidationAgent",
    ]:
        agent = get_subagent(agent_type)
        result = agent.run({}, ctx)
        assert result["agent_type"] == agent_type
        assert "success" in result


def test_bug_hunter_finds_issues():
    if not EXAMPLES.exists():
        return
    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="agira_test_"))
    shutil.copytree(EXAMPLES, tmp, dirs_exist_ok=True)
    ctx = ExecutionContext(repo_path=tmp)
    agent = get_subagent("BugHunterAgent")
    result = agent.run({}, ctx)
    patterns = {i.get("pattern") for i in result.get("issues", [])}
    # buggy_calculator has two issues:
    #   1. division_by_zero: safe_divide does a / b without zero check
    #   2. wrong_except: divide uses 'except Exception:' (qualified, not bare)
    assert "division_by_zero" in patterns or "wrong_except" in patterns or "bare_except" in patterns
    assert len(result.get("issues", [])) >= 1
