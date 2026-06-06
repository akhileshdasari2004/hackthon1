"""Typed error hierarchy for AGIRA."""

from __future__ import annotations

from typing import Any


class AgiraError(Exception):
    """Base error for all AGIRA failures."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": type(self).__name__,
            "message": self.message,
            "details": self.details,
        }


class ToolError(AgiraError):
    """Raised when a tool invocation fails."""


class SubagentError(AgiraError):
    """Raised when a subagent fails."""


class ExecutionError(AgiraError):
    """Raised when orchestrator execution fails."""


class TimeoutError(AgiraError):
    """Raised when an operation exceeds its time limit."""
