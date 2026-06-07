"""Fixability Classification Layer for Agira issues.

Classifies detected issues into fixability categories:
- AUTO_FIXABLE: Issues that can be automatically resolved
- REVIEW_REQUIRED: Issues requiring human review (logic bugs, type mismatches)
- ARCHITECTURAL: Design-level issues (dependency cycles, design flaws)
- UNSUPPORTED: Unknown issue types
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Fixability(str, Enum):
    """Fixability classification for issues."""
    AUTO_FIXABLE = "AUTO_FIXABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ARCHITECTURAL = "ARCHITECTURAL"
    UNSUPPORTED = "UNSUPPORTED"


# Time estimates in seconds for auto-fixable issues
AUTO_FIX_TIME_ESTIMATES: dict[str, float] = {
    "wrong_except": 30.0,
    "print_debug": 15.0,
    "unused_import": 20.0,
    "duplicate_import": 20.0,
    "trailing_whitespace": 10.0,
    "missing_newline_eof": 5.0,
    "todo_fixme": 45.0,
    "bare_except": 30.0,
    "mutable_default": 40.0,
    "syntax_error": 60.0,
}

# REVIEW_REQUIRED time estimates
REVIEW_TIME_ESTIMATES: dict[str, float] = {
    "division_by_zero": 120.0,
    "logic_bug": 180.0,
    "type_mismatch": 150.0,
    "eval_usage": 90.0,
    "pickle_load": 120.0,
}

# ARCHITECTURAL time estimates
ARCHITECTURAL_TIME_ESTIMATES: dict[str, float] = {
    "circular_import": 300.0,
    "dependency_cycle": 300.0,
    "dead_code": 200.0,
    "long_function": 240.0,
    "design_flaw": 600.0,
}


@dataclass
class FixabilityResult:
    """Result of fixability classification."""
    fixability: Fixability
    estimated_fix_time_seconds: float
    confidence: float = 1.0
    reason: str = ""


# Auto-fixable pattern types
AUTO_FIXABLE_PATTERNS: set[str] = {
    "wrong_except",
    "print_debug",
    "unused_import",
    "duplicate_import",
    "trailing_whitespace",
    "missing_newline_eof",
    "todo_fixme",
    "bare_except",
    "mutable_default",
    "syntax_error",
}

# Review-required pattern types
REVIEW_REQUIRED_PATTERNS: set[str] = {
    "division_by_zero",
    "logic_bug",
    "type_mismatch",
    "eval_usage",
    "pickle_load",
    "hardcoded_secret",
}

# Architectural pattern types
ARCHITECTURAL_PATTERNS: set[str] = {
    "circular_import",
    "dependency_cycle",
    "dead_code",
    "long_function",
    "design_flaw",
    "vulnerability",
    "api_surface",
    "complexity",
}


def classify_fixability(issue: dict[str, Any]) -> FixabilityResult:
    """Classify an issue's fixability.

    Args:
        issue: Issue dictionary with at least 'pattern' or 'type' key

    Returns:
        FixabilityResult with classification and time estimate
    """
    pattern = issue.get("pattern") or issue.get("type") or issue.get("issue_type", "")
    category = issue.get("category", "")

    # Check auto-fixable first
    if pattern in AUTO_FIXABLE_PATTERNS:
        time_estimate = AUTO_FIX_TIME_ESTIMATES.get(pattern, 30.0)
        return FixabilityResult(
            fixability=Fixability.AUTO_FIXABLE,
            estimated_fix_time_seconds=time_estimate,
            confidence=1.0,
            reason=f"Pattern '{pattern}' is auto-fixable",
        )

    # Check review-required patterns
    if pattern in REVIEW_REQUIRED_PATTERNS:
        time_estimate = REVIEW_TIME_ESTIMATES.get(pattern, 120.0)
        return FixabilityResult(
            fixability=Fixability.REVIEW_REQUIRED,
            estimated_fix_time_seconds=time_estimate,
            confidence=1.0,
            reason=f"Pattern '{pattern}' requires human review",
        )

    # Check architectural patterns
    if pattern in ARCHITECTURAL_PATTERNS or category == "architectural":
        time_estimate = ARCHITECTURAL_TIME_ESTIMATES.get(pattern, 300.0)
        return FixabilityResult(
            fixability=Fixability.ARCHITECTURAL,
            estimated_fix_time_seconds=time_estimate,
            confidence=1.0,
            reason=f"Pattern '{pattern}' is architectural",
        )

    # Check for circular imports specifically
    if "circular" in pattern.lower() or "cycle" in pattern.lower():
        return FixabilityResult(
            fixability=Fixability.ARCHITECTURAL,
            estimated_fix_time_seconds=300.0,
            confidence=1.0,
            reason="Dependency cycle detected",
        )

    # Default to unsupported for unknown patterns
    return FixabilityResult(
        fixability=Fixability.UNSUPPORTED,
        estimated_fix_time_seconds=0.0,
        confidence=0.5,
        reason=f"Unknown issue type '{pattern}'",
    )


def classify_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify a list of issues and add fixability fields.

    Args:
        issues: List of issue dictionaries

    Returns:
        List of issues with fixability and estimated_fix_time_seconds fields added
    """
    classified = []
    for issue in issues:
        result = classify_fixability(issue)
        classified_issue = {
            **issue,
            "fixability": result.fixability.value,
            "estimated_fix_time_seconds": result.estimated_fix_time_seconds,
            "fixability_reason": result.reason,
            "fixability_confidence": result.confidence,
        }
        classified.append(classified_issue)
    return classified


def summarize_fixability(issues: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate a fixability summary from classified issues.

    Args:
        issues: List of issues (with or without fixability field)

    Returns:
        Summary dict with counts per fixability category
    """
    # Ensure issues are classified
    if issues and "fixability" not in issues[0]:
        issues = classify_issues(issues)

    summary = {
        "total": len(issues),
        "auto_fixable": 0,
        "review_required": 0,
        "architectural": 0,
        "unsupported": 0,
        "auto_fix_time_total_seconds": 0.0,
        "review_time_total_seconds": 0.0,
        "architectural_time_total_seconds": 0.0,
    }

    for issue in issues:
        fixability = issue.get("fixability", Fixability.UNSUPPORTED.value)
        time_est = issue.get("estimated_fix_time_seconds", 0.0)

        if fixability == Fixability.AUTO_FIXABLE.value:
            summary["auto_fixable"] += 1
            summary["auto_fix_time_total_seconds"] += time_est
        elif fixability == Fixability.REVIEW_REQUIRED.value:
            summary["review_required"] += 1
            summary["review_time_total_seconds"] += time_est
        elif fixability == Fixability.ARCHITECTURAL.value:
            summary["architectural"] += 1
            summary["architectural_time_total_seconds"] += time_est
        else:
            summary["unsupported"] += 1

    return summary