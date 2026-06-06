"""TestValidationAgent — validate patches with rollback on failure."""

from __future__ import annotations

from typing import Any

from agira.subagents.base import AgentState, BaseSubagent, SubagentResult
from agira.tools.context import ExecutionContext


class TestValidationAgent(BaseSubagent):
    agent_type = "TestValidationAgent"
    allowed_tools = [
        "execution_tools.run_tests",
        "execution_tools.run_linter",
        "execution_tools.run_import_check",
        "execution_tools.run_typechecker",
        "patch_tools.validate_patch",
        "patch_tools.rollback_patch",
        "execution_tools.capture_env_info",
    ]

    VALIDATION_SEQUENCE = [
        "execution_tools.capture_env_info",
        "execution_tools.run_linter",
        "execution_tools.run_import_check",
        "patch_tools.validate_patch",
        "execution_tools.run_tests",
        "execution_tools.run_typechecker",
    ]

    def think(
        self, state: AgentState, ctx: ExecutionContext, task: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        done = {o["tool"] for o in state.observations}
        patches = self._get_patches(ctx, task)

        for tool in self.VALIDATION_SEQUENCE:
            if tool not in done:
                params: dict[str, Any] = {}
                if tool == "patch_tools.validate_patch":
                    if not patches:
                        continue
                    for p in patches:
                        rel = p.get("rel_path") or p.get("file", "")
                        if rel and rel not in state.hypotheses:
                            state.hypotheses.append(rel)
                            return tool, {"path": rel}
                    continue
                return tool, params

        if state.observations:
            tests = next((o for o in reversed(state.observations) if o["tool"] == "execution_tools.run_tests"), None)
            if tests and not tests.get("result", {}).get("success") and "patch_tools.rollback_patch" not in done:
                for p in patches:
                    return "patch_tools.rollback_patch", {"path": p.get("rel_path") or p.get("file", "")}
        return None

    def observe(
        self, state: AgentState, tool_name: str, result: dict[str, Any], artifact_id: str
    ) -> AgentState:
        state.observations.append({"tool": tool_name, "artifact_id": artifact_id, "result": result})
        state.artifacts_produced.append(artifact_id)
        return state

    def finalize(
        self, state: AgentState, ctx: ExecutionContext, result: SubagentResult
    ) -> SubagentResult:
        lint = next((o["result"] for o in state.observations if o["tool"] == "execution_tools.run_linter"), {})
        tests = next((o["result"] for o in state.observations if o["tool"] == "execution_tools.run_tests"), {})
        imports = next((o["result"] for o in state.observations if o["tool"] == "execution_tools.run_import_check"), {})
        rollback = next((o["result"] for o in state.observations if o["tool"] == "patch_tools.rollback_patch"), None)

        overall = (
            lint.get("passed", False)
            and tests.get("success", False)
            and imports.get("passed", True)
            and rollback is None
        )

        result.validation = {
            "linter": lint,
            "tests": tests,
            "imports": imports,
            "rollback": rollback,
            "overall_pass": overall,
        }
        result.success = overall
        return result

    def _evaluate_success(self, result: SubagentResult) -> bool:
        return bool(result.validation and result.validation.get("overall_pass"))

    def _get_patches(self, ctx: ExecutionContext, task: dict) -> list[dict]:
        for source in (
            ctx.state.get("input_patches"),
            ctx.artifact_store.latest("patch_result").data if ctx.artifact_store.latest("patch_result") else None,
        ):
            if isinstance(source, dict):
                return source.get("patches", [])
        return ctx.patches_applied
