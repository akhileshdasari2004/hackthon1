"""Subagent base with dynamic tool-selection reasoning loop."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from agira.observability.errors import SubagentError
from agira.observability.logging import log_event, setup_logging
from agira.registry.registry import ToolRegistry
from agira.tools.context import ExecutionContext

_logger = setup_logging()


@dataclass
class SubagentResult:
    agent_type: str
    agent_id: str
    success: bool
    issues: list[dict[str, Any]] = field(default_factory=list)
    patches: list[dict[str, Any]] = field(default_factory=list)
    analysis: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] | None = None
    tool_calls: int = 0
    reasoning_trace: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "agent_id": self.agent_id,
            "success": self.success,
            "issues": self.issues,
            "patches": self.patches,
            "analysis": self.analysis,
            "validation": self.validation,
            "tool_calls": self.tool_calls,
            "reasoning_trace": self.reasoning_trace,
            "error": self.error,
        }


@dataclass
class AgentState:
    done: bool = False
    observations: list[dict[str, Any]] = field(default_factory=list)
    artifacts_produced: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)


class BaseSubagent(ABC):
    agent_type: str = "base"
    allowed_tools: list[str] = []
    default_budget: int = 12

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self.agent_id = str(uuid.uuid4())[:8]

    def invoke_tool(
        self, tool_name: str, params: dict[str, Any], ctx: ExecutionContext
    ) -> tuple[dict[str, Any], str]:
        if self.allowed_tools:
            short = tool_name.split(".")[-1]
            allowed = [t for t in self.allowed_tools if t.endswith(f".{short}") or t == tool_name]
            if not allowed:
                raise SubagentError(f"Tool {tool_name} not allowed for {self.agent_type}")
            tool_name = allowed[0]
        result = self.registry.invoke(tool_name, params, ctx)
        artifact_id = ctx.store_result(
            f"{self.agent_type}:{short_name(tool_name)}",
            result,
            producer=f"{self.agent_type}:{tool_name}",
        )
        return result, artifact_id

    def run(self, task: dict[str, Any], parent_ctx: ExecutionContext) -> dict[str, Any]:
        ctx = parent_ctx.create_isolated_workdir()
        ctx.state["_registry"] = self.registry
        budget = task.get("budget", self.default_budget)
        state = AgentState()
        result = SubagentResult(agent_type=self.agent_type, agent_id=self.agent_id, success=False)

        if task.get("issues_artifact_id"):
            ctx.state["issues_artifact_id"] = task["issues_artifact_id"]
            try:
                parent_issues = parent_ctx.artifact_store.get_data(task["issues_artifact_id"])
                ctx.state["input_issues"] = parent_issues
                ctx.artifact_store.put("issues", parent_issues, producer="parent_feed", dependencies=[task["issues_artifact_id"]])
            except KeyError:
                pass
        if task.get("patch_artifact_id"):
            ctx.state["patch_artifact_id"] = task["patch_artifact_id"]
            try:
                parent_patches = parent_ctx.artifact_store.get_data(task["patch_artifact_id"])
                ctx.state["input_patches"] = parent_patches
                ctx.artifact_store.put("patch_result", parent_patches, producer="parent_feed", dependencies=[task["patch_artifact_id"]])
            except KeyError:
                pass

        log_event(_logger, "subagent_start", agent=self.agent_type, agent_id=self.agent_id)

        start_calls = ctx.tool_call_count
        try:
            while not state.done and budget > 0:
                action = self.think(state, ctx, task)
                if action is None:
                    state.done = True
                    break

                tool_name, params = action
                tool_result, artifact_id = self.invoke_tool(tool_name, params, ctx)
                state = self.observe(state, tool_name, tool_result, artifact_id)
                result.reasoning_trace.append({
                    "tool": tool_name,
                    "artifact_id": artifact_id,
                    "observation": state.observations[-1] if state.observations else {},
                })
                budget -= 1

            result = self.finalize(state, ctx, result)
            result.tool_calls = ctx.tool_call_count - start_calls
            result.success = self._evaluate_success(result)
            out = result.to_dict()
            out["work_dir"] = str(ctx.repo_path)
            log_event(_logger, "subagent_complete", agent=self.agent_type, success=result.success)
            return out

        except Exception as exc:
            log_event(_logger, "subagent_failed", agent=self.agent_type, error=str(exc))
            result.error = str(exc)
            result.tool_calls = ctx.tool_call_count - start_calls
            return result.to_dict()

    @abstractmethod
    def think(
        self, state: AgentState, ctx: ExecutionContext, task: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        """Choose next tool based on current observations."""
        ...

    @abstractmethod
    def observe(
        self,
        state: AgentState,
        tool_name: str,
        result: dict[str, Any],
        artifact_id: str,
    ) -> AgentState:
        ...

    @abstractmethod
    def finalize(
        self, state: AgentState, ctx: ExecutionContext, result: SubagentResult
    ) -> SubagentResult:
        ...

    def _evaluate_success(self, result: SubagentResult) -> bool:
        return result.success


def short_name(tool_name: str) -> str:
    return tool_name.split(".")[-1]
