"""Tests for deterministic fixer registry."""

import pytest
import tempfile
from pathlib import Path

from agira.patch.fixer_registry import FixerRegistry, PatchMetadata, create_fixer_registry


class TestPatchMetadata:
    """Test PatchMetadata dataclass."""

    def test_patch_metadata_to_dict(self):
        meta = PatchMetadata(
            issue_type="wrong_except",
            file="test.py",
            patch_applied=True,
            lines_changed=2,
            diff="--- a/test.py\n+++ b/test.py",
            dry_run=False,
        )
        result = meta.to_dict()
        assert result["issue_type"] == "wrong_except"
        assert result["file"] == "test.py"
        assert result["patch_applied"] is True
        assert result["lines_changed"] == 2
        assert "diff" in result


class TestFixerRegistry:
    """Test FixerRegistry with all supported fixers."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create a temporary repository path."""
        return tmp_path

    @pytest.fixture
    def registry(self, temp_repo):
        """Create a FixerRegistry instance."""
        return create_fixer_registry(temp_repo)

    @pytest.fixture
    def sample_file(self, temp_repo):
        """Create a sample Python file for testing."""
        content = '''"""Sample module for testing fixers."""

import os
import sys
from typing import List

def example():
    except Exception:
        pass

def debug_func():
    print("debug info")

    TODO add more code
'''  # noqa: E501
        path = temp_repo / "sample.py"
        path.write_text(content, encoding="utf-8")
        return path


class TestWrongExceptFixer:
    """Tests for wrong_except fixer."""

    def test_fix_wrong_except_dry_run(self, tmp_path):
        """Test dry-run mode for wrong_except fixer."""
        content = '''def func():
    try:
        x = 1
    except Exception:
        pass
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "wrong_except", dry_run=True)

        assert result.issue_type == "wrong_except"
        assert result.file == "test.py"
        assert result.dry_run is True
        assert result.patch_applied is False  # Dry run doesn't apply
        assert "except Exception as e:" in result.new_content
        assert "except Exception:" not in result.new_content
        # Original file should be unchanged
        assert path.read_text(encoding="utf-8") == content

    def test_fix_wrong_except_apply(self, tmp_path):
        """Test applying wrong_except fixer."""
        content = '''def func():
    try:
        x = 1
    except Exception:
        pass
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "wrong_except", dry_run=False)

        assert result.patch_applied is True
        assert result.lines_changed > 0
        assert "except Exception as e:" in path.read_text(encoding="utf-8")

    def test_fix_wrong_except_no_match(self, tmp_path):
        """Test wrong_except fixer when no pattern found."""
        content = '''def func():
    try:
        x = 1
    except Exception as e:
        pass
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "wrong_except")

        assert result.patch_applied is False
        assert result.error is not None
        assert "no wrong except" in result.error.lower() or "not found" in result.error.lower()


class TestPrintDebugFixer:
    """Tests for print_debug fixer."""

    def test_fix_print_debug_dry_run(self, tmp_path):
        """Test dry-run mode for print_debug fixer."""
        content = '''def func():
    print("debug info")
    print("normal output")
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "print_debug", dry_run=True)

        assert result.issue_type == "print_debug"
        assert result.dry_run is True
        assert result.patch_applied is False
        assert "# print(" in result.new_content
        assert path.read_text(encoding="utf-8") == content  # Unchanged

    def test_fix_print_debug_apply(self, tmp_path):
        """Test applying print_debug fixer."""
        content = '''def func():
    print("debug info")
    x = 1
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "print_debug", dry_run=False)

        assert result.patch_applied is True
        assert result.lines_changed > 0
        new_content = path.read_text(encoding="utf-8")
        # When there's another statement after, it should be commented out
        assert "# print(" in new_content

    def test_fix_print_debug_no_match(self, tmp_path):
        """Test print_debug fixer when no pattern found."""
        content = '''def func():
    print("normal output")
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "print_debug")

        assert result.patch_applied is False


class TestUnusedImportFixer:
    """Tests for unused_import fixer."""

    def test_fix_unused_import_simple(self, tmp_path):
        """Test removing unused import."""
        content = '''import os
print("hello")
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "unused_import", dry_run=False, import_name="os")

        assert result.patch_applied is True
        assert "import os" not in path.read_text(encoding="utf-8")

    def test_fix_unused_import_dry_run(self, tmp_path):
        """Test dry-run mode for unused_import fixer."""
        content = '''import os
print("hello")
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "unused_import", dry_run=True, import_name="os")

        assert result.patch_applied is False
        assert result.dry_run is True
        assert path.read_text(encoding="utf-8") == content  # Unchanged

    def test_fix_unused_import_from(self, tmp_path):
        """Test removing unused 'from x import y'."""
        content = '''from typing import List
print("hello")
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "unused_import", dry_run=False, import_name="List")

        assert result.patch_applied is True
        assert "import List" not in path.read_text(encoding="utf-8")

    def test_fix_unused_import_no_import_name(self, tmp_path):
        """Test unused_import fixer without import name."""
        path = tmp_path / "test.py"
        path.write_text("import os\n", encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "unused_import")

        assert result.patch_applied is False
        assert "import" in result.error.lower()


class TestDuplicateImportFixer:
    """Tests for duplicate_import fixer."""

    def test_fix_duplicate_import(self, tmp_path):
        """Test removing duplicate import."""
        content = '''import os
import sys
import os  # duplicate
print("hello")
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "duplicate_import", import_pattern="os")

        assert result.patch_applied is True
        assert result.lines_changed > 0
        # Count occurrences of "import os" - should be 1
        assert path.read_text(encoding="utf-8").count("import os") == 1

    def test_fix_duplicate_import_dry_run(self, tmp_path):
        """Test dry-run mode for duplicate_import fixer."""
        content = '''import os
import os
print("hello")
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "duplicate_import", dry_run=True, import_pattern="os")

        assert result.patch_applied is False
        assert result.dry_run is True
        assert path.read_text(encoding="utf-8").count("import os") == 2  # Unchanged


class TestTrailingWhitespaceFixer:
    """Tests for trailing_whitespace fixer."""

    def test_fix_trailing_whitespace(self, tmp_path):
        """Test removing trailing whitespace."""
        content = "def func():\n    pass   \nnext line\n"
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "trailing_whitespace", dry_run=False)

        assert result.patch_applied is True
        new_content = path.read_text(encoding="utf-8")
        assert "pass   \n" not in new_content

    def test_fix_trailing_whitespace_dry_run(self, tmp_path):
        """Test dry-run mode for trailing_whitespace fixer."""
        content = "def func():\n    pass   \n"
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "trailing_whitespace", dry_run=True)

        assert result.patch_applied is False
        assert result.dry_run is True
        assert path.read_text(encoding="utf-8") == content  # Unchanged

    def test_fix_trailing_whitespace_no_change_needed(self, tmp_path):
        """Test when no trailing whitespace exists."""
        content = "def func():\n    pass\n"
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "trailing_whitespace")

        assert result.patch_applied is False


class TestMissingNewlineEofFixer:
    """Tests for missing_newline_eof fixer."""

    def test_fix_missing_newline_eof(self, tmp_path):
        """Test adding missing newline at EOF."""
        content = "def func():\n    pass"
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "missing_newline_eof", dry_run=False)

        assert result.patch_applied is True
        assert path.read_text(encoding="utf-8").endswith("\n")

    def test_fix_missing_newline_eof_dry_run(self, tmp_path):
        """Test dry-run mode for missing_newline_eof fixer."""
        content = "def func():\n    pass"
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "missing_newline_eof", dry_run=True)

        assert result.patch_applied is False
        assert result.dry_run is True
        assert not path.read_text(encoding="utf-8").endswith("\n")  # Unchanged

    def test_fix_missing_newline_eof_already_has_newline(self, tmp_path):
        """Test when file already has trailing newline."""
        content = "def func():\n    pass\n"
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "missing_newline_eof")

        assert result.patch_applied is False
        assert "newline" in result.error.lower()


class TestTodoFixmeFixer:
    """Tests for todo_fixme fixer."""

    def test_fix_todo_fixme(self, tmp_path):
        """Test formatting TODO/FIXME in comments."""
        content = '''def func():
    # TODO add something
    x = 1
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "todo_fixme", dry_run=False)

        assert result.patch_applied is True
        new_content = path.read_text(encoding="utf-8")
        assert "TODO:" in new_content

    def test_fix_todo_fixme_dry_run(self, tmp_path):
        """Test dry-run mode for todo_fixme fixer."""
        content = '''def func():
    # TODO add something
    x = 1
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "todo_fixme", dry_run=True)

        assert result.patch_applied is False
        assert result.dry_run is True
        assert path.read_text(encoding="utf-8") == content  # Unchanged

    def test_fix_todo_fixme_already_formatted(self, tmp_path):
        """Test when TODO/FIXME already properly formatted."""
        content = '''def func():
    # TODO: add something
    x = 1
'''
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "todo_fixme")

        assert result.patch_applied is False


class TestFixerRegistryIntegration:
    """Integration tests for FixerRegistry."""

    def test_list_supported_fixes(self, tmp_path):
        """Test listing supported fix types."""
        registry = create_fixer_registry(tmp_path)
        fixes = registry.list_supported_fixes()

        assert "wrong_except" in fixes
        assert "print_debug" in fixes
        assert "unused_import" in fixes
        assert "duplicate_import" in fixes
        assert "trailing_whitespace" in fixes
        assert "missing_newline_eof" in fixes
        assert "todo_fixme" in fixes
        assert len(fixes) == 7

    def test_unknown_issue_type(self, tmp_path):
        """Test handling of unknown issue type."""
        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "unknown_type")

        assert result.patch_applied is False
        assert "unknown" in result.error.lower()

    def test_all_fixers_produce_valid_python(self, tmp_path):
        """Test that all applied fixes produce valid Python."""
        registry = create_fixer_registry(tmp_path)

        # Test cases that should produce valid Python
        test_cases = [
            ("wrong_except", "def f():\n    try:\n        x = 1\n    except Exception:\n        pass\n"),
            ("print_debug", 'def f():\n    print("debug")\n'),
            ("todo_fixme", "def f():\n    # TODO fix this\n    pass\n"),
            ("missing_newline_eof", "def f():\n    pass"),
            ("trailing_whitespace", "def f():\n    pass   \n"),
        ]

        for issue_type, content in test_cases:
            path = tmp_path / f"test_{issue_type}.py"
            path.write_text(content, encoding="utf-8")

            result = registry.apply_fix(path.name, issue_type, dry_run=False)
            assert result.patch_applied, f"Failed to apply {issue_type}"

            # Validate syntax
            new_content = path.read_text(encoding="utf-8")
            import ast
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                pytest.fail(f"Fixer {issue_type} produced invalid Python: {e}")

    def test_patch_metadata_contains_required_fields(self, tmp_path):
        """Test that PatchMetadata contains all required fields."""
        content = "def f():\n    pass"
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "missing_newline_eof", dry_run=True)

        assert "issue_type" in result.to_dict()
        assert "file" in result.to_dict()
        assert "patch_applied" in result.to_dict()
        assert "lines_changed" in result.to_dict()
        assert "diff" in result.to_dict()
        assert "dry_run" in result.to_dict()


class TestEdgeCases:
    """Test edge cases for fixers."""

    def test_empty_file(self, tmp_path):
        """Test fixer on empty file."""
        path = tmp_path / "test.py"
        path.write_text("", encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "missing_newline_eof")

        # Empty file already ends with newline conceptually
        assert result.patch_applied is False

    def test_file_with_only_comments(self, tmp_path):
        """Test fixer on file with only comments."""
        content = "# TODO: fix this\n"
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "todo_fixme")

        assert result.patch_applied is False

    def test_multiline_string_with_pattern(self, tmp_path):
        """Test that fixers don't affect patterns in strings."""
        content = 'def f():\n    x = """TODO: in string"""\n'
        path = tmp_path / "test.py"
        path.write_text(content, encoding="utf-8")

        registry = create_fixer_registry(tmp_path)
        result = registry.apply_fix("test.py", "todo_fixme")

        # Should not change TODO inside string
        new_content = path.read_text(encoding="utf-8")
        assert '"""TODO: in string"""' in new_content