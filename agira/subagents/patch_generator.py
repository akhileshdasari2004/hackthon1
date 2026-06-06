"""PatchGeneratorAgent — AST-based dynamic patching."""

from __future__ import annotations

from typing import Any

from agira.patch.ast_patcher import ASTPatcher
from agira.subagents.base import AgentState, BaseSubagent, SubagentResult
from agira.tools.context import ExecutionContext

FIXABLE = {
    "bare_except", "division_by_zero", "unused_import",
    "eval_usage", "hardcoded_secret", "pickle_load",
}


class PatchGeneratorAgent(BaseSubagent):
    agent_type = "PatchGeneratorAgent"
    allowed_tools = [
        "repo_tools.read_file",
        "repo_tools.edit_file",
        "patch_tools.generate_diff",
        "patch_tools.apply_patch",
        "patch_tools.preview_patch",
        "patch_tools.validate_patch",
        "patch_tools.ast_apply_fix",
        "patch_tools.apply_edit",
    ]

    def think(
        self, state: AgentState, ctx: ExecutionContext, task: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        issues = self._get_issues(ctx, task)
        patched = {o.get("issue_key") for o in state.observations if o.get("issue_key")}

        for issue in issues:
            pattern = issue.get("pattern", issue.get("type", ""))
            file_path = issue.get("file", "")
            if pattern not in FIXABLE or not file_path:
                continue
            key = f"{file_path}:{pattern}"
            if key in patched:
                continue
            state.hypotheses.append(key)
            return "patch_tools.ast_apply_fix", {"file": file_path, "fix_type": pattern, "issue": issue, "_issue_key": key}

        for obs in state.observations:
            if obs.get("needs_validation"):
                return "patch_tools.validate_patch", {"path": obs["file"], "artifact_id": obs.get("artifact_id")}

        return None

    def observe(
        self, state: AgentState, tool_name: str, result: dict[str, Any], artifact_id: str
    ) -> AgentState:
        entry: dict[str, Any] = {"tool": tool_name, "artifact_id": artifact_id, "result": result}
        if result.get("issue_key"):
            entry["issue_key"] = result["issue_key"]
        if result.get("applied"):
            entry["needs_validation"] = True
            entry["file"] = result.get("path", result.get("file"))
        state.observations.append(entry)
        state.artifacts_produced.append(artifact_id)
        return state

    def finalize(
        self, state: AgentState, ctx: ExecutionContext, result: SubagentResult
    ) -> SubagentResult:
        patches = []
        for obs in state.observations:
            if obs["tool"] == "patch_tools.ast_apply_fix" and obs.get("result", {}).get("applied"):
                p = obs["result"]
                patches.append({
                    "file": p.get("rel_path", p.get("file")),
                    "rel_path": p.get("rel_path", p.get("file")),
                    "pattern": p.get("fix_type"),
                    "diff": p.get("diff", ""),
                    "validated": p.get("validated", False),
                    "path": p.get("path"),
                })
        result.patches = patches
        result.analysis = {"patches_generated": len(patches), "issues_reviewed": len(state.hypotheses)}
        result.success = len(patches) > 0
        return result

    def _get_issues(self, ctx: ExecutionContext, task: dict) -> list[dict]:
        for source in (
            ctx.state.get("input_issues"),
            ctx.artifact_store.latest("issues").data if ctx.artifact_store.latest("issues") else None,
        ):
            if isinstance(source, dict) and "issues" in source:
                return source["issues"]
            if isinstance(source, list):
                return source
        if task.get("issues_artifact_id"):
            try:
                data = ctx.artifact_store.get_data(task["issues_artifact_id"])
                if isinstance(data, dict) and "issues" in data:
                    return data["issues"]
            except KeyError:
                pass
        return []
