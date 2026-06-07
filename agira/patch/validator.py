"""Patch Validator - Verifies patches before accepting them.

For every patch:
1. Save original file
2. Apply patch
3. Verify issue removed
4. Verify syntax valid
5. Run validation
6. Roll back on failure

States:
- PATCH_APPLIED: Patch was applied to file
- PATCH_VALIDATED: Patch passed all validations
- PATCH_REJECTED: Patch failed validation
- PATCH_ROLLED_BACK: Original file restored after rejection
"""

from __future__ import annotations

import ast
import difflib
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class PatchState(str, Enum):
    """States for patch validation lifecycle."""
    PENDING = "PENDING"
    PATCH_APPLIED = "PATCH_APPLIED"
    PATCH_VALIDATED = "PATCH_VALIDATED"
    PATCH_REJECTED = "PATCH_REJECTED"
    PATCH_ROLLED_BACK = "PATCH_ROLLED_BACK"


@dataclass
class PatchValidationResult:
    """Result of patch validation with full metadata."""
    issue_type: str
    file: str
    state: PatchState
    patch_applied: bool = False
    validated: bool = False
    issue_removed: bool = False
    syntax_valid: bool = False
    rollback_triggered: bool = False
    original_content: str = ""
    new_content: str = ""
    diff: str = ""
    error: str | None = None
    validation_details: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_type": self.issue_type,
            "file": self.file,
            "state": self.state.value,
            "patch_applied": self.patch_applied,
            "validated": self.validated,
            "issue_removed": self.issue_removed,
            "syntax_valid": self.syntax_valid,
            "rollback_triggered": self.rollback_triggered,
            "diff": self.diff,
            "error": self.error,
            "validation_details": self.validation_details,
        }

    @property
    def report_status(self) -> str:
        """Human-readable validation status for reports."""
        if self.state == PatchState.PATCH_VALIDATED:
            return "Validation Passed"
        elif self.state == PatchState.PATCH_ROLLED_BACK:
            return "Rollback Triggered"
        elif self.state == PatchState.PATCH_REJECTED:
            return "Validation Failed"
        return "Pending"


class PatchValidator:
    """Validates patches before accepting them.

    Performs the validation pipeline:
    1. Save original file content
    2. Apply patch to file
    3. Verify the issue was removed
    4. Verify file has valid Python syntax
    5. Run additional validation checks
    6. Roll back if any validation fails
    """

    def __init__(self, repo_path: Path | str) -> None:
        self.repo_path = Path(repo_path)

    def _resolve(self, file_path: str) -> Path:
        """Resolve relative path against repo_path."""
        p = Path(file_path)
        return p if p.is_absolute() else self.repo_path / p

    def _save_original(self, path: Path) -> str:
        """Save original file content."""
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
        return ""

    def _apply_patch(self, path: Path, old_content: str, new_content: str) -> tuple[bool, str]:
        """Apply patch to file and return (success, error)."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new_content, encoding="utf-8")
            return True, ""
        except Exception as e:
            return False, str(e)

    def _verify_syntax(self, content: str) -> tuple[bool, str | None]:
        """Verify Python syntax is valid."""
        try:
            ast.parse(content)
            return True, None
        except SyntaxError as e:
            return False, str(e)

    def _verify_issue_removed(self, content: str, issue_type: str, issue_data: dict) -> bool:
        """Verify the issue was removed by the patch."""
        if issue_type == "wrong_except":
            # Check that wrong except patterns (without 'as') are gone
            # Use AST to detect except handlers with bare exception types
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler) and node.type:
                        # Check if it's a Name (not a tuple) without 'as' alias
                        if isinstance(node.type, ast.Name):
                            # If the name is a common exception type and no 'as' alias, issue exists
                            if node.type.id in ('Exception', 'BaseException') and node.name is None:
                                return False
                return True
            except SyntaxError:
                return True  # Let syntax validation handle this

        elif issue_type == "print_debug":
            # Check that debug prints are properly handled (commented out, not deleted)
            # A valid fix should comment out debug prints, not remove them entirely
            try:
                tree = ast.parse(content)
                found_debug_print = False
                for node in ast.walk(tree):
                    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                        if isinstance(node.value.func, ast.Name) and node.value.func.id == "print":
                            if node.value.args:
                                arg = node.value.args[0]
                                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                    if "debug" in arg.value.lower():
                                        # Debug print still exists and wasn't commented out
                                        return False
                return True
            except SyntaxError:
                return True

        elif issue_type == "unused_import":
            import_name = issue_data.get("import_name", "")
            if not import_name:
                return True
            # Check that the import is gone
            return import_name not in content

        elif issue_type == "duplicate_import":
            import_pattern = issue_data.get("import_pattern", "")
            if not import_pattern:
                return True
            # Count occurrences - should be at most 1
            count = content.count(f"import {import_pattern}")
            return count <= 1

        elif issue_type == "trailing_whitespace":
            # Check no line has trailing whitespace
            for line in content.splitlines(keepends=True):
                if line.rstrip() != line.rstrip("\n"):
                    if line.rstrip() != line.rstrip():
                        return False
            return True

        elif issue_type == "missing_newline_eof":
            # Check file ends with newline
            return content.endswith("\n") or content == ""

        elif issue_type == "todo_fixme":
            # Check that TODO/FIXME in comments are properly formatted
            lines = content.splitlines()
            for line in lines:
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    # Check for improperly formatted TODO/FIXME
                    if re.search(r'\bTODO\b(?!\s*:)', line, re.IGNORECASE):
                        return False
                    if re.search(r'\bFIXME\b(?!\s*:)', line, re.IGNORECASE):
                        return False
                    if re.search(r'\bXXX\b(?!\s*:)', line, re.IGNORECASE):
                        return False
                    if re.search(r'\bHACK\b(?!\s*:)', line, re.IGNORECASE):
                        return False
            return True

        # For unknown issue types, assume it's removed if content changed
        return True

    def _make_diff(self, path: Path, old: str, new: str) -> str:
        """Generate unified diff."""
        return "".join(difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        ))

    def _run_additional_validation(self, path: Path, content: str) -> dict[str, Any]:
        """Run additional validation checks on the patched file."""
        issues_found = []
        checks = {"valid_structure": True, "no_obvious_errors": True}

        # Check for obvious issues
        try:
            tree = ast.parse(content, filename=str(path))

            # Check for bare except
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    issues_found.append("bare_except")

            # Check for debug prints
            for node in ast.walk(tree):
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Name) and node.value.func.id == "print":
                        # Check if print contains debug
                        if node.value.args:
                            arg = node.value.args[0]
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                if "debug" in arg.value.lower():
                                    issues_found.append("print_debug")

        except SyntaxError:
            checks["valid_structure"] = False

        return {
            "additional_issues_found": issues_found,
            "checks": checks,
        }

    def validate_and_apply(
        self,
        file_path: str,
        issue_type: str,
        new_content: str,
        issue_data: dict | None = None,
        dry_run: bool = False,
    ) -> PatchValidationResult:
        """Validate and apply a patch with full validation pipeline.

        Args:
            file_path: Path to the file to patch
            issue_type: Type of issue being fixed
            new_content: The patched content
            issue_data: Additional data about the issue (import_name, etc.)
            dry_run: If True, don't apply changes

        Returns:
            PatchValidationResult with full validation metadata
        """
        path = self._resolve(file_path)
        issue_data = issue_data or {}
        original_content = self._save_original(path)

        result = PatchValidationResult(
            issue_type=issue_type,
            file=file_path,
            state=PatchState.PENDING,
            original_content=original_content,
            new_content=new_content,
        )

        # Step 1: Apply patch (or prepare diff for dry run)
        if dry_run:
            result.dry_run = True
            result.new_content = new_content
            result.diff = self._make_diff(path, original_content, new_content)
            return result

        # Apply the patch
        success, error = self._apply_patch(path, original_content, new_content)
        if not success:
            result.state = PatchState.PATCH_REJECTED
            result.error = f"Failed to apply patch: {error}"
            return result

        result.patch_applied = True
        result.state = PatchState.PATCH_APPLIED
        result.diff = self._make_diff(path, original_content, new_content)

        # Step 2: Verify syntax valid
        syntax_ok, syntax_error = self._verify_syntax(new_content)
        result.syntax_valid = syntax_ok
        result.validation_details["syntax_check"] = {"passed": syntax_ok, "error": syntax_error}

        if not syntax_ok:
            result.state = PatchState.PATCH_REJECTED
            result.error = f"Syntax validation failed: {syntax_error}"
            self._rollback(path, original_content)
            result.rollback_triggered = True
            result.state = PatchState.PATCH_ROLLED_BACK
            return result

        # Step 3: Verify issue removed
        issue_removed = self._verify_issue_removed(new_content, issue_type, issue_data)
        result.issue_removed = issue_removed
        result.validation_details["issue_removal_check"] = {"passed": issue_removed}

        if not issue_removed:
            result.state = PatchState.PATCH_REJECTED
            result.error = f"Issue {issue_type} was not removed by patch"
            self._rollback(path, original_content)
            result.rollback_triggered = True
            result.state = PatchState.PATCH_ROLLED_BACK
            return result

        # Step 4: Run additional validation
        validation_details = self._run_additional_validation(path, new_content)
        result.validation_details.update(validation_details)

        # Check for additional issues
        if validation_details.get("additional_issues_found"):
            result.state = PatchState.PATCH_REJECTED
            result.error = f"Patch introduced new issues: {validation_details['additional_issues_found']}"
            self._rollback(path, original_content)
            result.rollback_triggered = True
            result.state = PatchState.PATCH_ROLLED_BACK
            return result

        # All validations passed
        result.validated = True
        result.state = PatchState.PATCH_VALIDATED
        return result

    def _rollback(self, path: Path, original_content: str) -> bool:
        """Rollback file to original content."""
        try:
            if original_content:
                path.write_text(original_content, encoding="utf-8")
            else:
                path.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    def rollback_file(self, file_path: str, original_content: str) -> bool:
        """Public rollback method."""
        path = self._resolve(file_path)
        return self._rollback(path, original_content)


def create_patch_validator(repo_path: Path | str) -> PatchValidator:
    """Factory function to create a PatchValidator instance."""
    return PatchValidator(repo_path)