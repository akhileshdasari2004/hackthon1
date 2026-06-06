"""BugHunterAgent — dynamic hypothesis-driven bug detection."""

from __future__ import annotations

from typing import Any

from agira.subagents.base import AgentState, BaseSubagent, SubagentResult
from agira.tools.context import ExecutionContext


class BugHunterAgent(BaseSubagent):
    agent_type = "BugHunterAgent"
    allowed_tools = [
        "analysis_tools.pattern_analyzer",
        "analysis_tools.vulnerability_scan_stub",
        "analysis_tools.detect_syntax_errors",
        "analysis_tools.find_unused_imports",
        "analysis_tools.detect_hardcoded_secrets",
        "analysis_tools.dead_code_detection",
        "analysis_tools.detect_circular_imports",
        "analysis_tools.detect_long_functions",
        "repo_tools.search_code",
    ]

    DETECTION_TOOLS = [
        "analysis_tools.pattern_analyzer",
        "analysis_tools.vulnerability_scan_stub",
        "analysis_tools.detect_syntax_errors",
        "analysis_tools.find_unused_imports",
        "analysis_tools.detect_hardcoded_secrets",
        "analysis_tools.dead_code_detection",
        "analysis_tools.detect_long_functions",
    ]

    def think(
        self, state: AgentState, ctx: ExecutionContext, task: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        done = {o["tool"] for o in state.observations}
        dep_id = ctx.artifact_store.latest_id("dependency_graph")

        for tool in self.DETECTION_TOOLS:
            if tool not in done:
                params: dict[str, Any] = {}
                if tool == "analysis_tools.detect_circular_imports" and dep_id:
                    params["dependency_graph_artifact_id"] = dep_id
                return tool, params

        if "repo_tools.search_code" not in done:
            hypotheses = ["except:", "def safe_divide", "eval(", "pickle.loads"]
            for h in hypotheses:
                if h not in state.hypotheses:
                    state.hypotheses.append(h)
                    return "repo_tools.search_code", {"query": h}
        return None

    def observe(
        self, state: AgentState, tool_name: str, result: dict[str, Any], artifact_id: str
    ) -> AgentState:
        state.observations.append({"tool": tool_name, "artifact_id": artifact_id})
        state.artifacts_produced.append(artifact_id)
        return state

    def finalize(
        self, state: AgentState, ctx: ExecutionContext, result: SubagentResult
    ) -> SubagentResult:
        issues: list[dict[str, Any]] = []
        for obs in state.observations:
            art = ctx.artifact_store.get(obs["artifact_id"])
            if not art:
                continue
            data = art.data
            if "patterns" in data:
                issues.extend(data["patterns"])
            if "findings" in data:
                for f in data["findings"]:
                    issues.append({**f, "category": "vulnerability"})
            if "errors" in data:
                for e in data["errors"]:
                    issues.append({**e, "pattern": "syntax_error"})
            if "unused" in data:
                for u in data["unused"]:
                    issues.append({**u, "pattern": "unused_import"})
            if "matches" in data:
                for m in data["matches"]:
                    pattern = _match_to_pattern(m.get("text", ""))
                    if pattern:
                        issues.append({**m, "pattern": pattern, "category": "logic"})

        seen: set[str] = set()
        deduped = []
        for issue in issues:
            key = f"{issue.get('file')}:{issue.get('pattern', issue.get('type', ''))}"
            if key not in seen:
                seen.add(key)
                deduped.append(issue)
        result.issues = deduped
        result.analysis = {"total_issues": len(deduped), "tools_used": len(state.observations)}
        result.success = len(issues) >= 1 or len(state.observations) >= 5
        return result


def _match_to_pattern(text: str) -> str | None:
    if "safe_divide" in text:
        return "division_by_zero"
    if "eval(" in text:
        return "eval_usage"
    if "pickle" in text:
        return "pickle_load"
    if "except:" in text:
        return "bare_except"
    return None
