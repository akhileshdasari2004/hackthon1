"""Subagent orchestration tools."""

from __future__ import annotations

from typing import Any

from agira.registry.base import ToolDefinition, ToolSchema
from agira.tools.context import ExecutionContext


def _schema(props: dict, required: list[str] | None = None) -> ToolSchema:
    return ToolSchema(properties=props, required=required or [])


def _out(props: dict) -> ToolSchema:
    return ToolSchema(properties=props)


# Lazy import to avoid circular dependency
_SUBAGENT_REGISTRY: dict[str, Any] = {}


def register_subagent(agent_type: str, factory: Any) -> None:
    _SUBAGENT_REGISTRY[agent_type] = factory


def register_agent_tools() -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []

    def spawn_subagent(params: dict, ctx: ExecutionContext) -> dict:
        from agira.subagents import get_subagent

        agent_type = params["agent_type"]
        task = params.get("task", {})
        agent = get_subagent(agent_type)
        result = agent.run(task, ctx)
        ref = ctx.store_artifact(f"subagent:{agent_type}", result)
        ctx.state.setdefault("subagent_results", []).append(result)
        return {"agent_type": agent_type, "result": result, "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "spawn_subagent", "agent_tools", "Spawn isolated subagent with scoped tools",
            _schema({
                "agent_type": {"type": "string"},
                "task": {"type": "object"},
            }, ["agent_type"]),
            _out({"result": {"type": "object"}}), "SubagentError", spawn_subagent,
        )
    )

    def merge_agent_output(params: dict, ctx: ExecutionContext) -> dict:
        store = ctx.artifact_store
        merged: dict[str, Any] = {"agents": [], "issues": [], "patches": [], "validations": []}
        for art_type in ("repo_analysis", "issues", "patch_result", "validation_result"):
            art = store.latest(art_type)
            if not art:
                continue
            data = art.data
            merged["agents"].append(data.get("agent_type", art_type))
            if art_type == "issues":
                merged["issues"].extend(data.get("issues", []) if isinstance(data, dict) else [])
            if art_type == "patch_result":
                merged["patches"].extend(data.get("patches", []) if isinstance(data, dict) else [])
            if art_type == "validation_result" and isinstance(data, dict):
                merged["validations"].append(data.get("validation", data))
        if ctx.patches_applied:
            merged["patches"].extend(ctx.patches_applied)
        ctx.state["merged_output"] = merged
        return {"merged": merged}

    tools.append(
        ToolDefinition(
            "merge_agent_output", "agent_tools", "Merge outputs from all subagents",
            _schema({}, []), _out({"merged": {"type": "object"}}), "SubagentError", merge_agent_output,
        )
    )

    def isolate_context(params: dict, ctx: ExecutionContext) -> dict:
        keys = params.get("keys", [])
        isolated = {k: ctx.state.get(k) for k in keys if k in ctx.state}
        isolated.update({k: ctx.artifacts.get(k) for k in keys if k in ctx.artifacts})
        session_id = f"isolated_{len(ctx.state.get('isolated_sessions', []))}"
        ctx.state.setdefault("isolated_sessions", []).append({"id": session_id, "data": isolated})
        return {"session_id": session_id, "keys": list(isolated.keys()), "isolated": isolated}

    tools.append(
        ToolDefinition(
            "isolate_context", "agent_tools", "Isolate context slice for subagent",
            _schema({"keys": {"type": "array"}}, []),
            _out({"session_id": {"type": "string"}}), "SubagentError", isolate_context,
        )
    )

    def summarize_context(params: dict, ctx: ExecutionContext) -> dict:
        summary = {
            "repo": str(ctx.repo_path),
            "tool_calls": ctx.tool_call_count,
            "artifacts": list(ctx.artifacts.keys())[:20],
            "patches": len(ctx.patches_applied),
            "subagents_run": len(ctx.state.get("subagent_results", [])),
            "state_keys": list(ctx.state.keys()),
        }
        ref = ctx.store_artifact("context_summary", summary)
        return {"summary": summary, "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "summarize_context", "agent_tools", "Summarize current execution context",
            _schema({}, []), _out({"summary": {"type": "object"}}), "SubagentError", summarize_context,
        )
    )

    def delegate_task(params: dict, ctx: ExecutionContext) -> dict:
        return spawn_subagent(
            {"agent_type": params["agent_type"], "task": params.get("payload", {})}, ctx
        )

    tools.append(
        ToolDefinition(
            "delegate_task", "agent_tools", "Delegate a task to a specific subagent",
            _schema({"agent_type": {"type": "string"}, "payload": {"type": "object"}},
                    ["agent_type"]),
            _out({"result": {"type": "object"}}), "SubagentError", delegate_task,
        )
    )

    def collect_agent_metrics(params: dict, ctx: ExecutionContext) -> dict:
        results = ctx.state.get("subagent_results", [])
        metrics = {
            "total_agents": len(results),
            "total_issues": sum(len(r.get("issues", [])) for r in results),
            "total_patches": sum(len(r.get("patches", [])) for r in results),
            "agent_types": [r.get("agent_type") for r in results],
        }
        return {"metrics": metrics}

    tools.append(
        ToolDefinition(
            "collect_agent_metrics", "agent_tools", "Collect metrics from subagent runs",
            _schema({}, []), _out({"metrics": {"type": "object"}}), "SubagentError", collect_agent_metrics,
        )
    )

    return tools
