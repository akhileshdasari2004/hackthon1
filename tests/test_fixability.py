"""Tests for fixability classification layer."""

import pytest

from agira.utils.fixability import (
    Fixability,
    FixabilityResult,
    classify_fixability,
    classify_issues,
    summarize_fixability,
)


class TestClassifyFixability:
    """Test fixability classification for various issue patterns."""

    def test_wrong_except_is_auto_fixable(self):
        issue = {"pattern": "wrong_except", "file": "test.py", "line": 10}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.AUTO_FIXABLE
        assert result.estimated_fix_time_seconds == 30.0

    def test_print_debug_is_auto_fixable(self):
        issue = {"pattern": "print_debug", "file": "test.py", "line": 5}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.AUTO_FIXABLE
        assert result.estimated_fix_time_seconds == 15.0

    def test_unused_import_is_auto_fixable(self):
        issue = {"pattern": "unused_import", "file": "test.py", "line": 3}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.AUTO_FIXABLE
        assert result.estimated_fix_time_seconds == 20.0

    def test_duplicate_import_is_auto_fixable(self):
        issue = {"pattern": "duplicate_import", "file": "test.py", "line": 7}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.AUTO_FIXABLE
        assert result.estimated_fix_time_seconds == 20.0

    def test_trailing_whitespace_is_auto_fixable(self):
        issue = {"pattern": "trailing_whitespace", "file": "test.py", "line": 12}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.AUTO_FIXABLE
        assert result.estimated_fix_time_seconds == 10.0

    def test_missing_newline_eof_is_auto_fixable(self):
        issue = {"pattern": "missing_newline_eof", "file": "test.py"}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.AUTO_FIXABLE
        assert result.estimated_fix_time_seconds == 5.0

    def test_todo_fixme_is_auto_fixable(self):
        issue = {"pattern": "todo_fixme", "file": "test.py", "line": 20}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.AUTO_FIXABLE
        assert result.estimated_fix_time_seconds == 45.0

    def test_bare_except_is_auto_fixable(self):
        issue = {"pattern": "bare_except", "file": "test.py", "line": 8}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.AUTO_FIXABLE
        assert result.estimated_fix_time_seconds == 30.0

    def test_division_by_zero_requires_review(self):
        issue = {"pattern": "division_by_zero", "file": "test.py", "line": 15}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.REVIEW_REQUIRED
        assert result.estimated_fix_time_seconds == 120.0

    def test_logic_bug_requires_review(self):
        issue = {"pattern": "logic_bug", "file": "test.py", "line": 25}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.REVIEW_REQUIRED
        assert result.estimated_fix_time_seconds == 180.0

    def test_type_mismatch_requires_review(self):
        issue = {"pattern": "type_mismatch", "file": "test.py", "line": 30}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.REVIEW_REQUIRED
        assert result.estimated_fix_time_seconds == 150.0

    def test_eval_usage_requires_review(self):
        issue = {"pattern": "eval_usage", "file": "test.py", "line": 5}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.REVIEW_REQUIRED
        assert result.estimated_fix_time_seconds == 90.0

    def test_circular_import_is_architectural(self):
        issue = {"pattern": "circular_import", "file": "test.py"}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.ARCHITECTURAL
        assert result.estimated_fix_time_seconds == 300.0

    def test_dependency_cycle_is_architectural(self):
        issue = {"pattern": "dependency_cycle", "file": "test.py"}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.ARCHITECTURAL
        assert result.estimated_fix_time_seconds == 300.0

    def test_dead_code_is_architectural(self):
        issue = {"pattern": "dead_code", "file": "test.py"}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.ARCHITECTURAL
        assert result.estimated_fix_time_seconds == 200.0

    def test_long_function_is_architectural(self):
        issue = {"pattern": "long_function", "file": "test.py"}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.ARCHITECTURAL
        assert result.estimated_fix_time_seconds == 240.0

    def test_design_flaw_is_architectural(self):
        issue = {"pattern": "design_flaw", "file": "test.py"}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.ARCHITECTURAL
        assert result.estimated_fix_time_seconds == 600.0

    def test_unknown_pattern_is_unsupported(self):
        issue = {"pattern": "unknown_pattern", "file": "test.py", "line": 1}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.UNSUPPORTED
        assert result.estimated_fix_time_seconds == 0.0

    def test_circular_in_text_is_architectural(self):
        issue = {"pattern": "circular_dependency", "file": "test.py"}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.ARCHITECTURAL

    def test_uses_type_key_when_pattern_missing(self):
        issue = {"type": "wrong_except", "file": "test.py"}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.AUTO_FIXABLE

    def test_uses_issue_type_key(self):
        issue = {"issue_type": "print_debug", "file": "test.py"}
        result = classify_fixability(issue)
        assert result.fixability == Fixability.AUTO_FIXABLE


class TestClassifyIssues:
    """Test batch issue classification."""

    def test_classify_empty_list(self):
        issues = []
        result = classify_issues(issues)
        assert result == []

    def test_classify_adds_fixability_fields(self):
        issues = [
            {"pattern": "wrong_except", "file": "test.py"},
            {"pattern": "division_by_zero", "file": "test2.py"},
        ]
        result = classify_issues(issues)
        assert len(result) == 2
        for issue in result:
            assert "fixability" in issue
            assert "estimated_fix_time_seconds" in issue
            assert "fixability_reason" in issue
            assert "fixability_confidence" in issue

    def test_classify_preserves_original_fields(self):
        issues = [{"pattern": "unused_import", "file": "test.py", "line": 5, "extra": "data"}]
        result = classify_issues(issues)
        assert result[0]["file"] == "test.py"
        assert result[0]["line"] == 5
        assert result[0]["extra"] == "data"


class TestSummarizeFixability:
    """Test fixability summary generation."""

    def test_summarize_empty_list(self):
        summary = summarize_fixability([])
        assert summary["total"] == 0
        assert summary["auto_fixable"] == 0
        assert summary["review_required"] == 0
        assert summary["architectural"] == 0
        assert summary["unsupported"] == 0

    def test_summarize_all_auto_fixable(self):
        issues = [
            {"pattern": "wrong_except", "file": "test.py"},
            {"pattern": "unused_import", "file": "test.py"},
            {"pattern": "print_debug", "file": "test.py"},
        ]
        summary = summarize_fixability(issues)
        assert summary["total"] == 3
        assert summary["auto_fixable"] == 3
        assert summary["review_required"] == 0
        assert summary["architectural"] == 0
        assert summary["unsupported"] == 0
        # Time estimates: wrong_except=30, unused_import=20, print_debug=15
        assert summary["auto_fix_time_total_seconds"] == 65.0

    def test_summarize_mixed_issues(self):
        issues = [
            {"pattern": "wrong_except", "file": "test.py"},          # AUTO_FIXABLE: 30s
            {"pattern": "division_by_zero", "file": "test.py"},      # REVIEW_REQUIRED: 120s
            {"pattern": "circular_import", "file": "test.py"},       # ARCHITECTURAL: 300s
            {"pattern": "unknown_pattern", "file": "test.py"},       # UNSUPPORTED: 0s
        ]
        summary = summarize_fixability(issues)
        assert summary["total"] == 4
        assert summary["auto_fixable"] == 1
        assert summary["review_required"] == 1
        assert summary["architectural"] == 1
        assert summary["unsupported"] == 1
        assert summary["auto_fix_time_total_seconds"] == 30.0
        assert summary["review_time_total_seconds"] == 120.0
        assert summary["architectural_time_total_seconds"] == 300.0

    def test_summarize_all_review_required(self):
        issues = [
            {"pattern": "logic_bug", "file": "test.py"},
            {"pattern": "type_mismatch", "file": "test.py"},
        ]
        summary = summarize_fixability(issues)
        assert summary["total"] == 2
        assert summary["review_required"] == 2

    def test_summarize_all_architectural(self):
        issues = [
            {"pattern": "dead_code", "file": "test.py"},
            {"pattern": "dependency_cycle", "file": "test.py"},
        ]
        summary = summarize_fixability(issues)
        assert summary["total"] == 2
        assert summary["architectural"] == 2


class TestFixabilityResult:
    """Test FixabilityResult dataclass."""

    def test_fixability_result_defaults(self):
        result = FixabilityResult(
            fixability=Fixability.AUTO_FIXABLE,
            estimated_fix_time_seconds=30.0,
        )
        assert result.confidence == 1.0
        assert result.reason == ""

    def test_fixability_result_custom_values(self):
        result = FixabilityResult(
            fixability=Fixability.REVIEW_REQUIRED,
            estimated_fix_time_seconds=120.0,
            confidence=0.9,
            reason="Complex logic bug",
        )
        assert result.confidence == 0.9
        assert result.reason == "Complex logic bug"


class TestFixabilityEnum:
    """Test Fixability enum values."""

    def test_fixability_values(self):
        assert Fixability.AUTO_FIXABLE.value == "AUTO_FIXABLE"
        assert Fixability.REVIEW_REQUIRED.value == "REVIEW_REQUIRED"
        assert Fixability.ARCHITECTURAL.value == "ARCHITECTURAL"
        assert Fixability.UNSUPPORTED.value == "UNSUPPORTED"

    def test_fixability_is_string(self):
        assert isinstance(Fixability.AUTO_FIXABLE.value, str)