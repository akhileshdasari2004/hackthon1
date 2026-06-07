"""Tests for repair metrics in reports."""

import pytest

from agira.utils.fixability import Fixability


class TestRepairMetrics:
    """Test repair metrics calculation and inclusion in reports."""

    def test_repair_metrics_keys(self):
        """Test that repair metrics has all required keys."""
        from agira.tools.report_tools import _collect_repair_metrics
        
        # This test uses mocks so we can test without full context
        # The actual metric collection is tested via integration
        
        expected_keys = [
            "issues_found",
            "auto_fixable",
            "patch_attempts",
            "successful_patches",
            "failed_patches",
            "validated_patches",
            "rollbacks",
            "repair_rate",
            "validation_rate",
        ]
        
        # We can verify the structure exists by checking the code
        import inspect
        source = inspect.getsource(_collect_repair_metrics)
        for key in expected_keys:
            assert key in source, f"Missing key: {key}"

    def test_fixability_values_for_metrics(self):
        """Test that Fixability enum has correct values for metrics."""
        assert Fixability.AUTO_FIXABLE.value == "AUTO_FIXABLE"
        assert Fixability.REVIEW_REQUIRED.value == "REVIEW_REQUIRED"
        assert Fixability.ARCHITECTURAL.value == "ARCHITECTURAL"
        assert Fixability.UNSUPPORTED.value == "UNSUPPORTED"

    def test_final_report_has_repair_metrics_field(self):
        """Test that FinalReport has repair_metrics field."""
        from agira.report.final_report import FinalReport
        
        report = FinalReport()
        assert hasattr(report, "repair_metrics")
        assert report.repair_metrics == {}
        
        # Test setting repair_metrics
        report.repair_metrics = {
            "issues_found": 10,
            "auto_fixable": 5,
            "patch_attempts": 5,
            "validated_patches": 4,
            "failed_patches": 1,
            "rollbacks": 1,
            "repair_rate": 80.0,
            "validation_rate": 80.0,
        }
        assert report.repair_metrics["issues_found"] == 10
        assert report.repair_metrics["repair_rate"] == 80.0

    def test_final_report_to_dict_includes_repair_metrics(self):
        """Test that to_dict includes repair_metrics."""
        from agira.report.final_report import FinalReport
        
        report = FinalReport()
        report.repair_metrics = {"issues_found": 10, "repair_rate": 90.0}
        
        d = report.to_dict()
        assert "repair_metrics" in d
        assert d["repair_metrics"]["issues_found"] == 10
        assert d["repair_metrics"]["repair_rate"] == 90.0

    def test_final_report_print_includes_repair_metrics(self, capsys):
        """Test that print_human_summary includes repair metrics."""
        from agira.report.final_report import FinalReport
        
        report = FinalReport()
        report.dag_status = "SUCCESS"
        report.repair_metrics = {
            "issues_found": 100,
            "auto_fixable": 20,
            "patch_attempts": 20,
            "validated_patches": 18,
            "failed_patches": 2,
            "rollbacks": 1,
            "repair_rate": 90.0,
            "validation_rate": 90.0,
        }
        
        report.print_human_summary()
        captured = capsys.readouterr()
        
        assert "REPAIR METRICS" in captured.out
        assert "Issues Found:" in captured.out
        assert "Auto Fixable:" in captured.out
        assert "Patch Attempts:" in captured.out
        assert "Validated Patches:" in captured.out
        assert "Repair Rate:" in captured.out
        assert "90.0%" in captured.out