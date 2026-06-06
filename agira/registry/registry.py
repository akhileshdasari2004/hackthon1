"""Central tool registry with schema validation and usage audit."""

from __future__ import annotations

import time
from typing import Any

from agira.observability.errors import ToolError
from agira.observability.logging import log_event, new_span_id, setup_logging, span_id_var
from agira.registry.base import ToolDefinition
from agira.tools.analysis_tools import register_analysis_tools
from agira.tools.agent_tools import register_agent_tools
from agira.tools.context import ExecutionContext
from agira.tools.execution_tools import register_execution_tools
from agira.tools.observability_tools import register_observability_tools
from agira.tools.patch_tools import register_patch_tools
from agira.tools.repo_tools import register_repo_tools
from agira.tools.report_tools import register_report_tools

_logger = setup_logging()


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._by_namespace: dict[str, list[str]] = {}
        self._register_all()

    def _register_all(self) -> None:
        for registrar in [
            register_repo_tools,
            register_analysis_tools,
            register_execution_tools,
            register_patch_tools,
            register_agent_tools,
            register_observability_tools,
            register_report_tools,
        ]:
            for tool in registrar():
                self.register(tool)

    def register(self, tool: ToolDefinition) -> None:
        if tool.qualified_name in self._tools:
            raise ToolError(f"Duplicate tool: {tool.qualified_name}")
        self._tools[tool.qualified_name] = tool
        self._by_namespace.setdefault(tool.namespace, []).append(tool.qualified_name)

    def get(self, qualified_name: str) -> ToolDefinition:
        if qualified_name not in self._tools:
            short = qualified_name.split(".")[-1]
            matches = [k for k in self._tools if k.endswith(f".{short}")]
            if len(matches) == 1:
                return self._tools[matches[0]]
            raise ToolError(f"Unknown tool: {qualified_name}")
        return self._tools[qualified_name]

    def list_tools(self, namespace: str | None = None) -> list[dict[str, Any]]:
        if namespace:
            return [self._tools[n].to_dict() for n in self._by_namespace.get(namespace, [])]
        return [t.to_dict() for t in self._tools.values()]

    def all_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def namespaces(self) -> dict[str, int]:
        return {ns: len(names) for ns, names in self._by_namespace.items()}

    def count(self) -> int:
        return len(self._tools)

    def _validate_params(self, tool: ToolDefinition, params: dict[str, Any]) -> None:
        required = tool.input_schema.required
        missing = [r for r in required if r not in params]
        if missing:
            raise ToolError(
                f"Missing required params for {tool.qualified_name}: {missing}",
                details={"required": required, "got": list(params.keys())},
            )

    def invoke(
        self,
        qualified_name: str,
        params: dict[str, Any],
        ctx: ExecutionContext,
    ) -> dict[str, Any]:
        tool = self.get(qualified_name)
        clean_params = {k: v for k, v in params.items() if not k.startswith("_")}
        resolved = ctx.artifact_store.resolve_params(clean_params)
        self._validate_params(tool, clean_params)

        span_id_var.set(new_span_id())
        ctx.increment_tool_calls(tool.qualified_name)
        start = time.monotonic()
        try:
            result = tool.handler(resolved, ctx)
            duration_ms = (time.monotonic() - start) * 1000
            log_event(_logger, "tool_invoked", tool=tool.qualified_name, duration_ms=round(duration_ms, 2), success=True)
            ctx.state.setdefault("traces", []).append({
                "trace_id": ctx.trace_id,
                "span_id": span_id_var.get(),
                "tool": tool.qualified_name,
                "duration_ms": round(duration_ms, 2),
                "success": True,
            })
            if "artifact_id" not in result:
                result["artifact_id"] = ctx.store_result(
                    f"tool:{tool.name}", result, producer=tool.qualified_name,
                )
            return result
        except ToolError:
            raise
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            log_event(_logger, "tool_failed", tool=tool.qualified_name, duration_ms=round(duration_ms, 2), error=str(exc))
            raise ToolError(f"Tool {tool.qualified_name} failed: {exc}", details={"tool": tool.qualified_name}) from exc

    def invoke_pipeline(
        self,
        steps: list[dict[str, Any]],
        ctx: ExecutionContext,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for step in steps:
            params = dict(step.get("params", {}))
            if "input_artifact_id" in step:
                params["artifact_id"] = step["input_artifact_id"]
            elif "input_from" in step:
                prior = results[step["input_from"]]
                if "artifact_id" in prior:
                    params["artifact_id"] = prior["artifact_id"]
                for key, src_key in step.get("map", {}).items():
                    if src_key in prior:
                        params[key] = prior[src_key]
            result = self.invoke(step["tool"], params, ctx)
            results.append(result)
        return results

    def usage_report(self, ctx: ExecutionContext) -> dict[str, Any]:
        all_tools = set(self.all_tool_names())
        used = set(ctx.tool_usage.keys())
        unused = sorted(all_tools - used)
        return {
            "total_tools": len(all_tools),
            "used_tools": len(used),
            "unused_tools": unused,
            "usage": ctx.tool_usage,
            "coverage_pct": round(len(used) / max(len(all_tools), 1) * 100, 1),
        }


def create_registry() -> ToolRegistry:
    return ToolRegistry()
