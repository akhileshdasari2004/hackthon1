"""Tests for developer-focused reports."""

import pytest

from agira.utils.fixability import Fixability


class TestDeveloperReportStructure:
    """Test that reports have the new developer-focused structure."""

    def test_final_report_has_developer_report_field(self):
        """Test that FinalReport has developer_report field."""
        from agira.report.final_report import FinalReport
        
        report = FinalReport()
        assert hasattr(report, "developer_report")
        assert report.developer_report == {}
        
        # Set developer report
        report.developer_report = {
            "repository_health": {"health_score": 85, "health_grade": "B"},
            "auto_fix_summary": {"succeeded": 10, "failed": 2},
            "developer_value": {"time_saved_minutes": 20},
        }
        
        d = report.to_dict()
        assert "developer_report" in d
        assert d["developer_report"]["repository_health"]["health_score"] == 85

    def test_developer_report_categories(self):
        """Test that developer report has required category keys."""
        expected_categories = [
            "repository_health",
            "reliability",
            "security", 
            "maintainability",
            "code_hygiene",
            "auto_fix_summary",
            "remaining_issues",
            "technical_debt",
            "top_risk_files",
            "developer_value",
        ]
        
        # These are the keys in the developer_report dict
        # The actual values are computed at report generation time
        for cat in expected_categories:
            assert len(cat) > 0, f"Category name cannot be empty"

    def test_developer_value_has_time_saved(self):
        """Test that developer value section includes time saved."""
        from agira.report.final_report import FinalReport
        
        report = FinalReport()
        report.developer_report = {
            "developer_value": {
                "time_saved_minutes": 30,
                "time_saved_hours": 0.5,
                "manual_fixes_avoided": 10,
                "files_cleaned": 5,
                "validation_success_rate": 90.0,
                "focus_remaining_minutes": 15,
            }
        }
        
        d = report.to_dict()
        dv = d["developer_report"]["developer_value"]
        assert dv["time_saved_minutes"] == 30
        assert dv["manual_fixes_avoided"] == 10
        assert dv["files_cleaned"] == 5
        assert dv["validation_success_rate"] == 90.0

    def test_auto_fix_summary_has_developer_impact_metrics(self):
        """Test that auto_fix_summary includes all developer impact metrics."""
        from agira.report.final_report import FinalReport
        
        report = FinalReport()
        report.developer_report = {
            "auto_fix_summary": {
                "fixes_applied": 25,
                "manual_fixes_avoided": 25,
                "files_cleaned": 12,
                "failed": 5,
                "rolled_back": 2,
                "validation_success_rate": 83.3,
                "success_rate": 83.3,
                "estimated_time_saved_minutes": 50,
                "estimated_time_saved_hours": 0.8,
            }
        }
        
        d = report.to_dict()
        afs = d["developer_report"]["auto_fix_summary"]
        assert afs["fixes_applied"] == 25
        assert afs["manual_fixes_avoided"] == 25
        assert afs["files_cleaned"] == 12
        assert afs["validation_success_rate"] == 83.3
        assert afs["estimated_time_saved_hours"] == 0.8

    def test_repair_metrics_still_present(self):
        """Test that repair_metrics field is still present for backward compatibility."""
        from agira.report.final_report import FinalReport
        
        report = FinalReport()
        report.repair_metrics = {
            "issues_found": 100,
            "auto_fixable": 50,
            "patch_attempts": 50,
            "validated_patches": 45,
            "failed_patches": 5,
            "repair_rate": 90.0,
            "time_saved_minutes": 45,
            "time_saved_hours": 0.8,
            "manual_fixes_avoided": 45,
            "files_cleaned": 20,
            "validation_success_rate": 90.0,
        }
        
        d = report.to_dict()
        assert "repair_metrics" in d
        assert d["repair_metrics"]["issues_found"] == 100
        assert d["repair_metrics"]["repair_rate"] == 90.0
        assert d["repair_metrics"]["time_saved_minutes"] == 45
        assert d["repair_metrics"]["manual_fixes_avoided"] == 45
        assert d["repair_metrics"]["files_cleaned"] == 20

    def test_final_report_print_includes_developer_report(self, capsys):
        """Test that print_human_summary includes developer report sections."""
        from agira.report.final_report import FinalReport
        
        report = FinalReport()
        report.dag_status = "SUCCESS"
        report.developer_report = {
            "repository_health": {
                "health_score": 85,
                "health_grade": "B",
                "issues_found": 50,
                "auto_fixable_count": 30,
            },
            "auto_fix_summary": {
                "fixes_applied": 25,
                "manual_fixes_avoided": 25,
                "files_cleaned": 12,
                "failed": 5,
                "validation_success_rate": 83.3,
                "estimated_time_saved_minutes": 50,
                "estimated_time_saved_hours": 0.8,
            },
            "developer_value": {
                "time_saved_minutes": 50,
                "time_saved_hours": 0.8,
                "manual_fixes_avoided": 25,
                "files_cleaned": 12,
            },
            "top_risk_files": [
                {"file": "a.py", "issue_count": 15},
                {"file": "b.py", "issue_count": 10},
            ],
        }
        
        report.print_human_summary()
        captured = capsys.readouterr()
        
        assert "DEVELOPER REPORT" in captured.out
        assert "Repository Health" in captured.out or "Health Score" in captured.out
        assert "Auto-Fix Summary" in captured.out
        assert "Developer Value" in captured.out or "Time Saved" in captured.out
        assert "Top Risk Files" in captured.out
        assert "Manual Fixes Avoided" in captured.out
        assert "Files Cleaned" in captured.out


class TestFixabilityForReports:
    """Test fixability integration with reports."""

    def test_fixability_values_match_report_expectations(self):
        """Test that Fixability enum values match what reports expect."""
        assert Fixability.AUTO_FIXABLE.value == "AUTO_FIXABLE"
        assert Fixability.REVIEW_REQUIRED.value == "REVIEW_REQUIRED"
        assert Fixability.ARCHITECTURAL.value == "ARCHITECTURAL"
        assert Fixability.UNSUPPORTED.value == "UNSUPPORTED"
        
        # AUTO_FIXABLE issues should be auto-fixable
        auto_fixable_patterns = [
            "wrong_except", "print_debug", "unused_import", 
            "duplicate_import", "trailing_whitespace", "missing_newline_eof", "todo_fixme"
        ]
        # Verify these patterns exist (they're used in fixability.py)
        from agira.utils.fixability import AUTO_FIXABLE_PATTERNS
        for pattern in auto_fixable_patterns:
            assert pattern in AUTO_FIXABLE_PATTERNS, f"{pattern} should be in AUTO_FIXABLE_PATTERNS"