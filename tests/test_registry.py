"""Tests for tool registry."""

from agira.registry.registry import create_registry


def test_tool_count_meets_minimum():
    registry = create_registry()
    assert registry.count() >= 50


def test_all_namespaces_present():
    registry = create_registry()
    namespaces = registry.namespaces()
    required = [
        "repo_tools",
        "analysis_tools",
        "execution_tools",
        "patch_tools",
        "agent_tools",
        "observability_tools",
        "report_tools",
    ]
    for ns in required:
        assert ns in namespaces, f"Missing namespace: {ns}"
        assert namespaces[ns] >= 5, f"Namespace {ns} has too few tools"


def test_tool_has_schema():
    registry = create_registry()
    tool = registry.get("repo_tools.read_file")
    d = tool.to_dict()
    assert "input_schema" in d
    assert "output_schema" in d
    assert d["error_type"] == "ToolError"
