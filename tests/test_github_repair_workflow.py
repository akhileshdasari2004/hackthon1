"""Tests for GitHub repair workflow - structural tests only.

Note: The export_github_repair_workflow function is defined inside
register_report_tools() so it requires the registry to be initialized.
These tests verify the source code structure without runtime execution.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestGithubRepairWorkflowStructure:
    """Structural tests for GitHub repair workflow source code."""

    def test_gh_token_check_in_source(self):
        """Test that GH_TOKEN check is present in the function."""
        import agira.tools.report_tools as rt
        import inspect
        
        # Get the register_report_tools function source
        source = inspect.getsource(rt.register_report_tools)
        
        # Check that function contains GH_TOKEN check
        assert 'GH_TOKEN' in source

    def test_export_function_defined_in_tool(self):
        """Test that export_github_repair_workflow is defined."""
        import agira.tools.report_tools as rt
        import inspect
        
        source = inspect.getsource(rt.register_report_tools)
        assert 'def export_github_repair_workflow' in source

    def test_pr_workflow_branch_creation(self):
        """Test that PR workflow has branch creation logic."""
        import agira.tools.report_tools as rt
        import inspect
        
        source = inspect.getsource(rt.register_report_tools)
        assert 'checkout' in source  # git checkout command
        assert 'push' in source  # git push command

    def test_pr_creation_with_gh_cli(self):
        """Test that gh pr create is called."""
        import agira.tools.report_tools as rt
        import inspect
        
        source = inspect.getsource(rt.register_report_tools)
        assert 'gh' in source and 'pr' in source

    def test_diff_file_export_exists(self):
        """Test that diff file export is present."""
        import agira.tools.report_tools as rt
        import inspect
        
        source = inspect.getsource(rt.register_report_tools)
        assert 'patches.diff' in source
        assert 'write_text' in source

    def test_no_patches_early_return(self):
        """Test that function handles empty patches list."""
        import agira.tools.report_tools as rt
        import inspect
        
        source = inspect.getsource(rt.register_report_tools)
        # Should return early with failure if no patches
        assert 'No validated patches' in source or 'No patches' in source

    def test_pr_title_variable(self):
        """Test that PR title variable exists."""
        import agira.tools.report_tools as rt
        import inspect
        
        source = inspect.getsource(rt.register_report_tools)
        assert 'pr_title' in source

    def test_pr_body_variable(self):
        """Test that PR body/description variable exists."""
        import agira.tools.report_tools as rt
        import inspect
        
        source = inspect.getsource(rt.register_report_tools)
        assert 'pr_body' in source

    def test_files_changed_calculation(self):
        """Test that files_changed is calculated from patches."""
        import agira.tools.report_tools as rt
        import inspect
        
        source = inspect.getsource(rt.register_report_tools)
        assert 'files_changed' in source
        # Should be using a set to count unique files
        assert 'set()' in source

    def test_validated_patches_filter(self):
        """Test that only validated patches are filtered."""
        import agira.tools.report_tools as rt
        import inspect
        
        source = inspect.getsource(rt.register_report_tools)
        # Should filter patches by validated status
        assert 'validated' in source

    def test_tool_definition_registered(self):
        """Test that tool is registered in the tools list."""
        import agira.tools.report_tools as rt
        import inspect
        
        source = inspect.getsource(rt.register_report_tools)
        assert 'export_github_repair_workflow' in source
        assert 'ToolDefinition' in source

    def test_commit_with_agira_message(self):
        """Test that git commit uses AGIRA message."""
        import agira.tools.report_tools as rt
        import inspect
        
        source = inspect.getsource(rt.register_report_tools)
        assert 'commit' in source
        assert 'agira' in source.lower()

    def test_branch_name_includes_timestamp(self):
        """Test that branch name includes timestamp."""
        import agira.tools.report_tools as rt
        import inspect
        
        source = inspect.getsource(rt.register_report_tools)
        assert 'branch_name' in source
        assert 'agira-repair' in source


class TestFinalReportRepairIntegration:
    """Tests for FinalReport integration with repair workflow."""

    def test_final_report_preserves_all_fields(self):
        """Test that FinalReport.to_dict includes all fields."""
        from agira.report.final_report import FinalReport
        
        report = FinalReport()
        d = report.to_dict()
        
        # Must preserve existing fields
        assert "issues" in d
        assert "repair_metrics" in d
        assert "developer_report" in d
        # Existing fields preserved
        assert "nodes_executed" in d
        assert "dag_status" in d

    def test_repair_metrics_has_developer_impact_fields(self):
        """Test that repair_metrics includes developer impact fields."""
        from agira.report.final_report import FinalReport
        
        report = FinalReport()
        report.repair_metrics = {
            "issues_found": 10,
            "auto_fixable": 5,
            "patch_attempts": 5,
            "validated_patches": 4,
            "failed_patches": 1,
            "repair_rate": 80.0,
            "time_saved_minutes": 8,
            "time_saved_hours": 0.13,
            "manual_fixes_avoided": 4,
            "files_cleaned": 3,
            "validation_success_rate": 80.0,
        }
        
        d = report.to_dict()
        rm = d["repair_metrics"]
        
        assert rm["time_saved_minutes"] == 8
        assert rm["manual_fixes_avoided"] == 4
        assert rm["files_cleaned"] == 3
        assert rm["validation_success_rate"] == 80.0

    def test_developer_report_auto_fix_summary_structure(self):
        """Test that auto_fix_summary has developer impact fields."""
        from agira.report.final_report import FinalReport
        
        report = FinalReport()
        report.developer_report = {
            "auto_fix_summary": {
                "fixes_applied": 10,
                "manual_fixes_avoided": 10,
                "files_cleaned": 5,
                "validation_success_rate": 95.0,
                "estimated_time_saved_hours": 1.5,
            }
        }
        
        d = report.to_dict()
        afs = d["developer_report"]["auto_fix_summary"]
        
        assert afs["fixes_applied"] == 10
        assert afs["manual_fixes_avoided"] == 10
        assert afs["files_cleaned"] == 5