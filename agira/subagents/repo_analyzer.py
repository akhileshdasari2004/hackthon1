"""RepoAnalyzerAgent — dynamic repo exploration."""

from __future__ import annotations

from typing import Any

from agira.subagents.base import AgentState, BaseSubagent, SubagentResult
from agira.tools.context import ExecutionContext


class RepoAnalyzerAgent(BaseSubagent):
    agent_type = "RepoAnalyzerAgent"
    allowed_tools = [
        "repo_tools.list_files",
        "repo_tools.get_repo_metadata",
        "repo_tools.find_entry_points",
        "repo_tools.extract_imports",
        "analysis_tools.build_dependency_graph",
        "analysis_tools.count_dependencies",
        "analysis_tools.analyze_api_surface",
        "analysis_tools.compute_complexity_score",
        "analysis_tools.parse_ast",
        "analysis_tools.detect_circular_imports",
    ]

    TOOL_PRIORITY = [
        ("repo_tools.get_repo_metadata", {}),
        ("repo_tools.list_files", {}),
        ("repo_tools.find_entry_points", {}),
        ("analysis_tools.build_dependency_graph", {}),
        ("analysis_tools.count_dependencies", {}),
        ("analysis_tools.detect_circular_imports", {}),
        ("analysis_tools.analyze_api_surface", {}),
        ("analysis_tools.compute_complexity_score", {}),
    ]

    def think(
        self, state: AgentState, ctx: ExecutionContext, task: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        done_tools = {o["tool"] for o in state.observations}
        for tool_name, params in self.TOOL_PRIORITY:
            if tool_name not in done_tools:
                dep_id = ctx.artifact_store.latest_id("dependency_graph")
                if tool_name == "analysis_tools.count_dependencies" and dep_id:
                    params = {"dependency_graph_artifact_id": dep_id}
                if tool_name == "analysis_tools.detect_circular_imports" and dep_id:
                    params = {"dependency_graph_artifact_id": dep_id}
                return tool_name, params
        files: list[str] = []
        for obs in state.observations:
            art = ctx.artifact_store.get(obs["artifact_id"])
            if art and isinstance(art.data, dict) and "files" in art.data:
                files = art.data["files"]
                break
        if files and "analysis_tools.parse_ast" not in done_tools:
            py_files = [f for f in files if f.endswith(".py")][:3]
            for f in py_files:
                if f not in state.hypotheses:
                    state.hypotheses.append(f)
                    return "analysis_tools.parse_ast", {"path": f}
        return None

    def observe(
        self, state: AgentState, tool_name: str, result: dict[str, Any], artifact_id: str
    ) -> AgentState:
        state.observations.append({"tool": tool_name, "artifact_id": artifact_id, "summary": _summarize(result)})
        state.artifacts_produced.append(artifact_id)
        return state

    def finalize(
        self, state: AgentState, ctx: ExecutionContext, result: SubagentResult
    ) -> SubagentResult:
        result.analysis = {
            "observations": len(state.observations),
            "artifacts": state.artifacts_produced,
            "metadata": ctx.artifact_store.latest("repo_metadata"),
            "dependency_graph": ctx.artifact_store.latest_id("dependency_graph"),
        }
        result.success = len(state.observations) >= 4
        return result


def _summarize(result: dict) -> str:
    if "count" in result:
        return f"count={result['count']}"
    if "files" in result:
        return f"files={result.get('count', len(result['files']))}"
    return "ok"
