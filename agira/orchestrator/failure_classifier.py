"""Failure intelligence — classify and route node failures."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agira.orchestrator.plan import PlanNode


class FailureClass(str, Enum):
    DETERMINISTIC = "deterministic"   # Exact-match failure, never retry
    TRANSIENT = "transient"            # I/O, network, timing — retry once
    DEPENDENCY = "dependency"          # Upstream dependency failed
    ESCALATE = "escalate"              # Unknown/error, mark failed and continue


# Tools that are deterministic — any failure is permanent
DETERMINISTIC_TOOLS = {
    "patch_tools.apply_edit",
    "patch_tools.apply_patch",
    "repo_tools.edit_file",
    "patch_tools.ast_apply_fix",
}

# Transient error patterns — may succeed on retry
TRANSIENT_PATTERNS = (
    "ConnectionError",
    "Timeout",
    "Temporary failure",
    "I/O operation",
    "file is busy",
    "resource temporarily unavailable",
    "permission denied",
    "No such file or directory",  # race condition on file creation
    "Address already in use",
)


def classify_failure(
    node: PlanNode,
    error: str,
) -> FailureClass:
    """Classify a node failure and return the recommended action."""
    # 1. Deterministic tools always fail fast
    if node.target in DETERMINISTIC_TOOLS:
        return FailureClass.DETERMINISTIC

    # 2. Check error message for transient patterns
    error_upper = error.lower()
    for pattern in TRANSIENT_PATTERNS:
        if pattern.lower() in error_upper:
            return FailureClass.TRANSIENT

    # 3. Check for dependency-style failures
    dependency_indicators = (
        "dependency",
        "upstream",
        "depends_on",
        "artifact not found",
        "missing input",
        "input_artifact",
    )
    for indicator in dependency_indicators:
        if indicator in error_upper:
            return FailureClass.DEPENDENCY

    # 4. Subagents with budget exhausted
    if node.action_type == "subagent" and node.retry_count >= node.max_retries:
        return FailureClass.DETERMINISTIC

    # 5. Unknown errors — escalate (mark failed, don't retry)
    return FailureClass.ESCALATE


def failure_action(classification: FailureClass) -> str:
    """Map classification to recommended action name."""
    return {
        FailureClass.DETERMINISTIC: "skip",
        FailureClass.TRANSIENT: "retry",
        FailureClass.DEPENDENCY: "repartition",
        FailureClass.ESCALATE: "escalate",
    }[classification]