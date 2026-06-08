"""Execution state machine — executes plan nodes with artifact flow."""

from __future__ import annotations

import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agira.observability.errors import ExecutionError, ToolError
from agira.observability.retry import retry_with_backoff
from agira.orchestrator.plan import ExecutionPlan, NodeStatus, PlanNode
from agira.registry.registry import ToolRegistry
from agira.subagents import get_subagent
from agira.tools.context import ExecutionContext


class ExecutionStateMachine:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute_node(
        self,
        node: PlanNode,
        plan: ExecutionPlan,
        ctx: ExecutionContext,
    ) -> str | None:
        node.status = NodeStatus.RUNNING
        node.started_at = datetime.now(timezone.utc).isoformat()
        node.start_time_ms = time.perf_counter() * 1000

        try:
            if node.action_type == "tool":
                artifact_id = self._execute_tool(node, ctx)
            elif node.action_type == "subagent":
                artifact_id = self._execute_subagent(node, ctx)
            else:
                raise ExecutionError(f"Unknown action type: {node.action_type}")

            node.output_artifact_id = artifact_id
            node.status = NodeStatus.COMPLETED
            node.completed_at = datetime.now(timezone.utc).isoformat()
            node.end_time_ms = time.perf_counter() * 1000
            node.duration_ms = round(node.end_time_ms - node.start_time_ms, 2) if node.start_time_ms else None
            return artifact_id

        except (KeyboardInterrupt, SystemExit):
            node.end_time_ms = time.perf_counter() * 1000
            node.duration_ms = round(node.end_time_ms - node.start_time_ms, 2) if node.start_time_ms else None
            raise
        except Exception as exc:
            node.retry_count += 1
            node.error = str(exc)
            ctx.record_failure(node.name, str(exc), {"target": node.target})

            if node.retry_count <= node.max_retries:
                node.status = NodeStatus.PENDING
                raise
            node.status = NodeStatus.FAILED
            node.completed_at = datetime.now(timezone.utc).isoformat()
            node.end_time_ms = time.perf_counter() * 1000
            node.duration_ms = round(node.end_time_ms - node.start_time_ms, 2) if node.start_time_ms else None
            return None

    def _resolve_input_artifacts(self, node: PlanNode, ctx: ExecutionContext) -> list[str]:
        from agira.orchestrator.planner import DynamicPlanner
        planner = DynamicPlanner()
        return planner._input_artifacts(node.name, ctx.artifact_store)

    def _build_params(self, node: PlanNode, ctx: ExecutionContext) -> dict[str, Any]:
        params = dict(node.params)
        input_ids = self._resolve_input_artifacts(node, ctx) or node.input_artifact_ids
        node.input_artifact_ids = input_ids
        for aid in input_ids:
            artifact = ctx.artifact_store.get(aid)
            if artifact:
                params[f"{artifact.artifact_type}_artifact_id"] = aid
        return ctx.artifact_store.resolve_params(params)

    # Tools that are deterministic and must NOT be retried
    DETERMINISTIC_TOOLS = {
        "patch_tools.apply_edit",
        "patch_tools.apply_patch",
        "repo_tools.edit_file",
        "patch_tools.ast_apply_fix",
    }

    def _execute_tool(self, node: PlanNode, ctx: ExecutionContext) -> str:
        params = self._build_params(node, ctx)
        if node.name == "rollback_on_failure":
            return self._conditional_rollback(node, ctx)

        # Use fail-fast for deterministic edit tools (no retry loops)
        if node.target in self.DETERMINISTIC_TOOLS:
            result = self.registry.invoke(node.target, params, ctx)
        else:
            # Non-edit tools can retry once to handle transient failures
            result = retry_with_backoff(
                self.registry.invoke, node.target, params, ctx, max_retries=1, base_delay=0.3,
            )
        artifact_type = self._artifact_type_for_tool(node.name, result)
        deps = list(node.input_artifact_ids)
        if "artifact_ref" in result and isinstance(result["artifact_ref"], str):
            deps.append(result["artifact_ref"])
        return ctx.store_result(artifact_type, result, producer=node.target, dependencies=deps)

    def _conditional_rollback(self, node: PlanNode, ctx: ExecutionContext) -> str:
        validation = ctx.artifact_store.latest("validation_result")
        if validation and validation.data.get("overall_pass"):
            return ctx.store_result("rollback_result", {"rolled_back": False, "reason": "tests passed"}, producer="rollback")
        patch_art = ctx.artifact_store.latest("patch_result")
        if not patch_art:
            return ctx.store_result("rollback_result", {"rolled_back": False}, producer="rollback")
        result = self.registry.invoke("patch_tools.rollback_all", {}, ctx)
        return ctx.store_result("rollback_result", result, producer="patch_tools.rollback_all")

    def _execute_subagent(self, node: PlanNode, ctx: ExecutionContext) -> str:
        params = self._build_params(node, ctx)
        task: dict[str, Any] = {"budget": 12}
        if "issues" in params:
            task["issues_artifact_id"] = node.input_artifact_ids[0] if node.input_artifact_ids else None
        if "issues_artifact_id" in params:
            task["issues_artifact_id"] = params.get("issues_artifact_id")
        input_ids = self._resolve_input_artifacts(node, ctx)
        if node.target == "PatchGeneratorAgent" and input_ids:
            task["issues_artifact_id"] = input_ids[0]
        if node.target == "TestValidationAgent" and input_ids:
            task["patch_artifact_id"] = input_ids[0]

        agent = get_subagent(node.target)
        result = agent.run(task, ctx)

        merge_proposal = {
            "type": "patches",
            "patches": result.get("patches", []),
            "work_dir": result.get("work_dir"),
        }
        ctx.queue_merge(merge_proposal)
        self._apply_merge(ctx, merge_proposal)

        artifact_type = {
            "RepoAnalyzerAgent": "repo_analysis",
            "BugHunterAgent": "issues",
            "PatchGeneratorAgent": "patch_result",
            "TestValidationAgent": "validation_result",
        }.get(node.target, "subagent_result")

        return ctx.store_result(
            artifact_type, result, producer=node.target, dependencies=node.input_artifact_ids,
        )

    def _apply_merge(self, ctx: ExecutionContext, proposal: dict) -> None:
        work_dir = Path(proposal.get("work_dir") or ctx.repo_path)
        for patch in proposal.get("patches", []):
            rel = patch.get("rel_path") or patch.get("file", "")
            if not rel:
                continue
            src = work_dir / rel
            dst = ctx.repo_path / rel
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            patch["path"] = str(dst)
            ctx.patches_applied.append(patch)

    def _artifact_type_for_tool(self, node_name: str, result: dict) -> str:
        mapping = {
            "repo_metadata": "repo_metadata",
            "file_list": "file_list",
            "dependency_graph": "dependency_graph",
            "merge_findings": "merged_findings",
            "initial_validation": "test_results",
            "health_score": "health_score",
            "json_report": "json_report",
            "markdown_report": "markdown_report",
            "pr_summary": "pr_summary",
            "tool_coverage": "tool_coverage",
            "rollback_on_failure": "rollback_result",
        }
        return mapping.get(node_name, "tool_result")
