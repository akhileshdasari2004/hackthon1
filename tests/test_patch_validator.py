"""Tests for patch validator."""

import pytest
import tempfile
from pathlib import Path

from agira.patch.validator import (
    PatchState,
    PatchValidationResult,
    PatchValidator,
    create_patch_validator,
)


class TestPatchState:
    """Test PatchState enum values."""

    def test_patch_state_values(self):
        assert PatchState.PENDING.value == "PENDING"
        assert PatchState.PATCH_APPLIED.value == "PATCH_APPLIED"
        assert PatchState.PATCH_VALIDATED.value == "PATCH_VALIDATED"
        assert PatchState.PATCH_REJECTED.value == "PATCH_REJECTED"
        assert PatchState.PATCH_ROLLED_BACK.value == "PATCH_ROLLED_BACK"


class TestPatchValidationResult:
    """Test PatchValidationResult dataclass."""

    def test_default_values(self):
        result = PatchValidationResult(
            issue_type="wrong_except",
            file="test.py",
            state=PatchState.PENDING,
        )
        assert result.issue_type == "wrong_except"
        assert result.file == "test.py"
        assert result.state == PatchState.PENDING
        assert result.patch_applied is False
        assert result.validated is False
        assert result.rollback_triggered is False

    def test_to_dict(self):
        result = PatchValidationResult(
            issue_type="unused_import",
            file="test.py",
            state=PatchState.PATCH_VALIDATED,
            patch_applied=True,
            validated=True,
            syntax_valid=True,
            issue_removed=True,
        )
        d = result.to_dict()
        assert d["issue_type"] == "unused_import"
        assert d["state"] == "PATCH_VALIDATED"
        assert d["patch_applied"] is True
        assert d["validated"] is True

    def test_report_status(self):
        result = PatchValidationResult(
            issue_type="test",
            file="test.py",
            state=PatchState.PATCH_VALIDATED,
        )
        assert result.report_status == "Validation Passed"

        result.state = PatchState.PATCH_ROLLED_BACK
        assert result.report_status == "Rollback Triggered"

        result.state = PatchState.PATCH_REJECTED
        assert result.report_status == "Validation Failed"


class TestPatchValidator:
    """Test PatchValidator with full validation pipeline."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create a temporary repository path."""
        return tmp_path

    @pytest.fixture
    def validator(self, temp_repo):
        """Create a PatchValidator instance."""
        return create_patch_validator(temp_repo)


class TestSyntaxValidation:
    """Tests for syntax validation."""

    def test_valid_python_passes(self, tmp_path):
        """Valid Python syntax passes validation."""
        content = '''def func():
    pass
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "unused_import",
            content,
        )

        assert result.syntax_valid is True
        assert result.state == PatchState.PATCH_VALIDATED

    def test_invalid_python_fails(self, tmp_path):
        """Invalid Python syntax fails validation."""
        original = '''def func():
    pass
'''
        bad_content = '''def func(
    pass
'''
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "unused_import",
            bad_content,
        )

        assert result.syntax_valid is False
        # After rollback, state is PATCH_ROLLED_BACK
        assert result.state == PatchState.PATCH_ROLLED_BACK
        assert result.rollback_triggered is True
        assert "Syntax" in result.error

    def test_rollback_restores_original(self, tmp_path):
        """Rollback restores original file content."""
        original = '''def func():
    pass
'''
        bad_content = '''def func(
    pass
'''
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "unused_import",
            bad_content,
        )

        # File should be restored to original
        assert path.read_text(encoding="utf-8") == original


class TestIssueRemovalValidation:
    """Tests for issue removal verification."""

    def test_wrong_except_removed(self, tmp_path):
        """Wrong except pattern is verified as removed."""
        original = '''def func():
    try:
        x = 1
    except Exception:
        pass
'''
        fixed = '''def func():
    try:
        x = 1
    except Exception as e:
        pass
'''
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "wrong_except",
            fixed,
        )

        assert result.issue_removed is True
        assert result.state == PatchState.PATCH_VALIDATED

    def test_wrong_except_still_present_fails(self, tmp_path):
        """Wrong except still present causes rejection."""
        original = '''def func():
    try:
        x = 1
    except Exception:
        pass
'''
        not_fixed = '''def func():
    try:
        x = 1
    except Exception:
        pass
'''
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "wrong_except",
            not_fixed,
        )

        assert result.issue_removed is False
        # After rollback, state is PATCH_ROLLED_BACK
        assert result.state == PatchState.PATCH_ROLLED_BACK
        assert result.rollback_triggered is True

    def test_print_debug_removed(self, tmp_path):
        """Debug print pattern is verified as removed."""
        original = '''def func():
    print("debug info")
'''
        fixed = '''def func():
    pass
'''
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "print_debug",
            fixed,
        )

        assert result.issue_removed is True
        assert result.state == PatchState.PATCH_VALIDATED

    def test_trailing_whitespace_removed(self, tmp_path):
        """Trailing whitespace is verified as removed."""
        original = "def func():\n    pass   \n"
        fixed = "def func():\n    pass\n"
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "trailing_whitespace",
            fixed,
        )

        assert result.issue_removed is True
        assert result.state == PatchState.PATCH_VALIDATED

    def test_missing_newline_fixed(self, tmp_path):
        """Missing newline at EOF is verified as fixed."""
        original = "def func():\n    pass"
        fixed = "def func():\n    pass\n"
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "missing_newline_eof",
            fixed,
        )

        assert result.issue_removed is True
        assert result.state == PatchState.PATCH_VALIDATED


class TestDryRunMode:
    """Tests for dry-run mode."""

    def test_dry_run_does_not_apply(self, tmp_path):
        """Dry-run mode doesn't apply changes to file."""
        original = '''def func():
    print("debug")
'''
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "print_debug",
            original,
            dry_run=True,
        )

        # File should be unchanged
        assert path.read_text(encoding="utf-8") == original
        # Result should indicate patch was not applied
        assert result.patch_applied is False
        assert result.state == PatchState.PENDING

    def test_dry_run_validates(self, tmp_path):
        """Dry-run mode still validates content."""
        valid_content = '''def func():
    pass
'''
        path = tmp_path / "test.py"
        path.write_text(valid_content, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "unused_import",
            valid_content,
            dry_run=True,
        )

        # In dry run, we can still check validity
        assert result.new_content == valid_content


class TestRollbackMechanism:
    """Tests for rollback on failure."""

    def test_rollback_on_syntax_error(self, tmp_path):
        """Syntax error triggers rollback."""
        original = "def func():\n    pass\n"
        bad_content = "def func(\n    pass\n"
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "unused_import",
            bad_content,
        )

        assert result.rollback_triggered is True
        assert result.state == PatchState.PATCH_ROLLED_BACK
        assert path.read_text(encoding="utf-8") == original

    def test_rollback_on_issue_not_removed(self, tmp_path):
        """Issue not removed triggers rollback."""
        original = "def func():\n    print('debug')\n"
        not_fixed = "def func():\n    print('debug')\n"
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "print_debug",
            not_fixed,
        )

        assert result.rollback_triggered is True
        assert result.state == PatchState.PATCH_ROLLED_BACK

    def test_rollback_restores_content(self, tmp_path):
        """Rollback properly restores original content."""
        original = "def func():\n    pass\n"
        bad_content = "def func(\n"
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "unused_import",
            bad_content,
        )

        assert path.read_text(encoding="utf-8") == original

    def test_manual_rollback(self, tmp_path):
        """Manual rollback method works correctly."""
        original = "def func():\n    pass\n"
        path = tmp_path / "test.py"
        path.write_text("# modified\n", encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        success = validator.rollback_file("test.py", original)

        assert success is True
        assert path.read_text(encoding="utf-8") == original


class TestValidationPipeline:
    """Integration tests for full validation pipeline."""

    def test_full_pipeline_success(self, tmp_path):
        """Full validation pipeline succeeds with valid patch."""
        original = '''import os
print("hello")
'''
        fixed = '''print("hello")
'''
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "unused_import",
            fixed,
            issue_data={"import_name": "os"},
        )

        assert result.patch_applied is True
        assert result.syntax_valid is True
        assert result.issue_removed is True
        assert result.validated is True
        assert result.state == PatchState.PATCH_VALIDATED
        assert result.report_status == "Validation Passed"

    def test_full_pipeline_failure(self, tmp_path):
        """Full validation pipeline fails gracefully with rollback."""
        original = '''def func():
    pass
'''
        # Bad fix: introduces syntax error
        bad_content = '''def func(
    pass
'''
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "unused_import",
            bad_content,
        )

        # Should fail because patch introduces syntax error
        assert result.patch_applied is True  # Patch was attempted
        assert result.state == PatchState.PATCH_ROLLED_BACK
        assert result.rollback_triggered is True
        assert result.report_status == "Rollback Triggered"
        # Original should be restored
        assert path.read_text(encoding="utf-8") == original

    def test_validation_details_populated(self, tmp_path):
        """Validation details are properly populated."""
        content = '''def func():
    pass
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "unused_import",
            content,
        )

        assert "syntax_check" in result.validation_details
        assert "issue_removal_check" in result.validation_details


class TestValidatorEdgeCases:
    """Test edge cases for the validator."""

    def test_nonexistent_file(self, tmp_path):
        """Validator handles nonexistent files."""
        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "nonexistent.py",
            "unused_import",
            "print('hello')\n",
        )

        # Should still work (creates new file)
        assert result.patch_applied is True

    def test_diff_generated(self, tmp_path):
        """Diff is generated for applied patches."""
        original = "def f():\n    pass\n"
        path = tmp_path / "test.py"
        path.write_text(original, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "missing_newline_eof",
            "def f():\n    pass",
        )

        assert result.diff is not None
        assert "---" in result.diff
        assert "+++" in result.diff

    def test_empty_issue_type(self, tmp_path):
        """Validator handles unknown issue types."""
        content = "def f():\n    pass\n"
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        validator = create_patch_validator(tmp_path)
        result = validator.validate_and_apply(
            "test.py",
            "unknown_issue",
            content,
        )

        # Unknown issue types are treated as removed
        assert result.issue_removed is True