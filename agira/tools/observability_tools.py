"""Observability and resilience tools."""

from __future__ import annotations

import logging
import time
from typing import Any

from agira.observability.errors import AgiraError, ToolError
from agira.observability.logging import get_trace_id, log_event, setup_logging
from agira.observability.retry import retry_with_backoff
from agira.registry.base import ToolDefinition, ToolSchema
from agira.tools.context import ExecutionContext

_logger = setup_logging()


def _schema(props: dict, required: list[str] | None = None) -> ToolSchema:
    return ToolSchema(properties=props, required=required or [])


def _out(props: dict) -> ToolSchema:
    return ToolSchema(properties=props)


def register_observability_tools() -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []

    def log_event_tool(params: dict, ctx: ExecutionContext) -> dict:
        level_name = params.get("level", "INFO")
        level = getattr(logging, level_name.upper(), logging.INFO)
        entry = log_event(_logger, params["event"], level=level, **params.get("fields", {}))
        ctx.state.setdefault("log_events", []).append(entry)
        return {"logged": True, "entry": entry}

    tools.append(
        ToolDefinition(
            "log_event", "observability_tools", "Emit structured log event",
            _schema({"event": {"type": "string"}, "level": {"type": "string"}, "fields": {"type": "object"}},
                    ["event"]),
            _out({"logged": {"type": "boolean"}}), "ToolError", log_event_tool,
        )
    )

    def trace_tool_call(params: dict, ctx: ExecutionContext) -> dict:
        trace = {
            "trace_id": get_trace_id(),
            "tool": params["tool_name"],
            "duration_ms": params.get("duration_ms", 0),
            "success": params.get("success", True),
            "timestamp": time.time(),
        }
        ctx.state.setdefault("traces", []).append(trace)
        log_event(_logger, "tool_trace", tool=trace["tool"], duration_ms=trace["duration_ms"])
        return {"trace": trace}

    tools.append(
        ToolDefinition(
            "trace_tool_call", "observability_tools", "Record tool call trace",
            _schema({"tool_name": {"type": "string"}, "duration_ms": {"type": "number"}}, ["tool_name"]),
            _out({"trace": {"type": "object"}}), "ToolError", trace_tool_call,
        )
    )

    def retry_with_backoff_tool(params: dict, ctx: ExecutionContext) -> dict:
        tool_name = params["tool_name"]
        tool_params = params.get("params", {})
        from agira.registry.registry import ToolRegistry

        registry: ToolRegistry = ctx.state["_registry"]

        def _invoke() -> dict[str, Any]:
            return registry.invoke(tool_name, tool_params, ctx)

        result = retry_with_backoff(
            _invoke,
            max_retries=params.get("max_retries", 3),
            base_delay=params.get("base_delay", 0.5),
        )
        return {"result": result, "retried": True}

    tools.append(
        ToolDefinition(
            "retry_with_backoff", "observability_tools", "Retry a tool with exponential backoff",
            _schema({"tool_name": {"type": "string"}, "params": {"type": "object"},
                     "max_retries": {"type": "integer"}}, ["tool_name"]),
            _out({"result": {"type": "object"}}), "ToolError", retry_with_backoff_tool,
        )
    )

    def rate_limiter_tool(params: dict, ctx: ExecutionContext) -> dict:
        tokens = params.get("tokens", 1.0)
        ctx.rate_limiter.acquire(tokens)
        return {"acquired": True, "tokens": tokens}

    tools.append(
        ToolDefinition(
            "rate_limiter", "observability_tools", "Acquire rate limit tokens",
            _schema({"tokens": {"type": "number"}}, []),
            _out({"acquired": {"type": "boolean"}}), "ToolError", rate_limiter_tool,
        )
    )

    def error_classifier(params: dict, ctx: ExecutionContext) -> dict:
        error_msg = params["error"]
        classification = "unknown"
        if "timeout" in error_msg.lower():
            classification = "TimeoutError"
        elif "subagent" in error_msg.lower():
            classification = "SubagentError"
        elif "syntax" in error_msg.lower():
            classification = "SyntaxError"
        elif "not found" in error_msg.lower():
            classification = "NotFoundError"
        else:
            classification = "ToolError"
        return {"error": error_msg, "classification": classification}

    tools.append(
        ToolDefinition(
            "error_classifier", "observability_tools", "Classify error messages",
            _schema({"error": {"type": "string"}}, ["error"]),
            _out({"classification": {"type": "string"}}), "ToolError", error_classifier,
        )
    )

    def get_execution_stats(params: dict, ctx: ExecutionContext) -> dict:
        traces = ctx.state.get("traces", [])
        durations = [t["duration_ms"] for t in traces]
        return {
            "tool_calls": ctx.tool_call_count,
            "traces": len(traces),
            "avg_duration_ms": sum(durations) / max(len(durations), 1),
            "trace_id": get_trace_id(),
        }

    tools.append(
        ToolDefinition(
            "get_execution_stats", "observability_tools", "Get execution statistics",
            _schema({}, []), _out({"tool_calls": {"type": "integer"}}), "ToolError", get_execution_stats,
        )
    )

    def flush_logs(params: dict, ctx: ExecutionContext) -> dict:
        events = ctx.state.get("log_events", [])
        return {"flushed": len(events), "events": events[-params.get("last_n", 10):]}

    tools.append(
        ToolDefinition(
            "flush_logs", "observability_tools", "Flush recent log events",
            _schema({"last_n": {"type": "integer"}}, []),
            _out({"flushed": {"type": "integer"}}), "ToolError", flush_logs,
        )
    )

    def tool_coverage_report(params: dict, ctx: ExecutionContext) -> dict:
        from agira.registry.registry import ToolRegistry
        registry: ToolRegistry = ctx.state["_registry"]
        report = registry.usage_report(ctx)
        ctx.store_result("tool_coverage", report, producer="observability_tools.tool_coverage_report")
        return report

    tools.append(
        ToolDefinition(
            "tool_coverage_report", "observability_tools", "Report tool usage coverage per run",
            _schema({}, []), _out({"coverage_pct": {"type": "number"}}), "ToolError", tool_coverage_report,
        )
    )

    return tools
