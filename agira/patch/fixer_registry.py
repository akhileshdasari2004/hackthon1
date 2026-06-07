"""Deterministic Fixer Registry for Auto-Fixable Issues.

Each fixer implements a deterministic transformation for a specific issue type.
All fixers support dry-run mode and return patch metadata.

Supported issue types:
- wrong_except: Fix bare exception types (add 'as' clause)
- print_debug: Remove or comment debug print statements
- unused_import: Remove unused import statements
- duplicate_import: Remove duplicate import statements
- trailing_whitespace: Remove trailing whitespace from lines
- missing_newline_eof: Ensure file ends with newline
- todo_fixme: Comment or flag TODO/FIXME comments
"""

from __future__ import annotations

import ast
import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class PatchMetadata:
    """Metadata returned by every fixer operation."""
    issue_type: str
    file: str
    patch_applied: bool
    lines_changed: int
    diff: str = ""
    dry_run: bool = False
    error: str | None = None
    original_content: str = ""
    new_content: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_type": self.issue_type,
            "file": self.file,
            "patch_applied": self.patch_applied,
            "lines_changed": self.lines_changed,
            "diff": self.diff,
            "dry_run": self.dry_run,
            "error": self.error,
        }


class FixerRegistry:
    """Registry of deterministic fixers for auto-fixable issues."""

    def __init__(self, repo_path: Path | str) -> None:
        self.repo_path = Path(repo_path)
        self._fixers: dict[str, Callable[[str, dict], PatchMetadata]] = {}
        self._register_default_fixers()

    def _resolve(self, file_path: str) -> Path:
        """Resolve relative path against repo_path."""
        p = Path(file_path)
        return p if p.is_absolute() else self.repo_path / p

    def _read_file(self, path: Path) -> str:
        """Read file content with UTF-8 encoding."""
        return path.read_text(encoding="utf-8", errors="replace")

    def _count_lines_changed(self, old: str, new: str) -> int:
        """Count number of lines that differ between old and new content."""
        if old == new:
            return 0
        diff = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            lineterm="",
        )
        return sum(1 for line in diff if line.startswith(("+", "-")) and not line.startswith(("---", "+++")))

    def _make_diff(self, path: Path, old: str, new: str) -> str:
        """Generate unified diff."""
        return "".join(difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        ))

    def _validate_python(self, content: str) -> str | None:
        """Validate Python syntax. Returns None if valid, error message if invalid."""
        try:
            ast.parse(content)
            return None
        except SyntaxError as e:
            return str(e)

    def _register_default_fixers(self) -> None:
        """Register all default deterministic fixers."""
        self._fixers["wrong_except"] = self._fix_wrong_except
        self._fixers["print_debug"] = self._fix_print_debug
        self._fixers["unused_import"] = self._fix_unused_import
        self._fixers["duplicate_import"] = self._fix_duplicate_import
        self._fixers["trailing_whitespace"] = self._fix_trailing_whitespace
        self._fixers["missing_newline_eof"] = self._fix_missing_newline_eof
        self._fixers["todo_fixme"] = self._fix_todo_fixme

    def apply_fix(
        self, file_path: str, issue_type: str, dry_run: bool = False, **kwargs: Any
    ) -> PatchMetadata:
        """Apply a fixer for the given issue type.

        Args:
            file_path: Path to the file to fix
            issue_type: Type of issue to fix
            dry_run: If True, don't write changes, just return preview
            **kwargs: Additional issue-specific parameters

        Returns:
            PatchMetadata with result of the fix operation
        """
        if issue_type not in self._fixers:
            return PatchMetadata(
                issue_type=issue_type,
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error=f"Unknown issue type: {issue_type}",
            )

        fixer = self._fixers[issue_type]
        return fixer(file_path, {"dry_run": dry_run, **kwargs})

    def _fix_wrong_except(self, file_path: str, params: dict) -> PatchMetadata:
        """Fix wrong except clauses.

        Transforms 'except Exception:' to 'except Exception as e:' to properly
        capture the exception instance.
        """
        path = self._resolve(file_path)
        old = self._read_file(path)
        dry_run = params.get("dry_run", False)

        # Pattern: except Exception: (without 'as')
        # We want to transform it to: except Exception as e:
        pattern = re.compile(r'\b(except\s+(\w+)\s*):')

        matches = list(pattern.finditer(old))
        if not matches:
            return PatchMetadata(
                issue_type="wrong_except",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error="No wrong except patterns found",
                original_content=old,
            )

        new = old
        # Process in reverse order to preserve positions
        for match in reversed(matches):
            old_text = match.group(0)
            exc_type = match.group(2)
            # Only fix if it doesn't already have 'as'
            if f"except {exc_type} as" not in new[max(0, match.start()-20):match.end()+20]:
                new_text = f"except {exc_type} as e:"
                new = new[:match.start()] + new_text + new[match.end():]

        if new == old:
            return PatchMetadata(
                issue_type="wrong_except",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error="Pattern found but no changes made",
                original_content=old,
            )

        # Validate Python syntax
        syntax_err = self._validate_python(new)
        if syntax_err:
            return PatchMetadata(
                issue_type="wrong_except",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error=f"Syntax error after fix: {syntax_err}",
                original_content=old,
                new_content=new,
            )

        lines_changed = self._count_lines_changed(old, new)
        diff = self._make_diff(path, old, new)

        if not dry_run:
            path.write_text(new, encoding="utf-8")

        return PatchMetadata(
            issue_type="wrong_except",
            file=file_path,
            patch_applied=not dry_run,
            lines_changed=lines_changed,
            diff=diff,
            dry_run=dry_run,
            original_content=old,
            new_content=new,
        )

    def _fix_print_debug(self, file_path: str, params: dict) -> PatchMetadata:
        """Remove debug print statements.

        Comments out print statements that contain 'debug' in their arguments.
        If the print is the only statement in a block, replaces it with 'pass'.
        """
        path = self._resolve(file_path)
        old = self._read_file(path)
        dry_run = params.get("dry_run", False)

        # Pattern: print(...) where ... contains 'debug' (case-insensitive)
        debug_print_pattern = re.compile(
            r'^(\s*)print\s*\([^)]*debug[^)]*\)\s*(?:#.*)?$',
            re.IGNORECASE | re.MULTILINE
        )

        matches = list(debug_print_pattern.finditer(old))
        if not matches:
            return PatchMetadata(
                issue_type="print_debug",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error="No debug print statements found",
                original_content=old,
            )

        new = old
        # Process in reverse order to preserve positions
        for match in reversed(matches):
            full_match = match.group(0)
            indent = match.group(1)
            # Check if this is the only statement in a block (need to replace with pass)
            # Look at the context: is there anything after this line in the same block?
            after_match = old[match.end():match.end()+20]
            before_match = old[max(0, match.start()-20):match.start()]
            
            # Simple heuristic: if line before ends with ':' (start of block) and
            # there's nothing meaningful after, we need 'pass'
            needs_pass = False
            parts = before_match.split('\n')
            # Get the non-empty last part for the line before the current line
            line_before = parts[-1] if parts[-1].strip() else (parts[-2] if len(parts) > 1 else before_match)
            remaining = after_match.strip()
            
            # Check if we're the only statement in an indented block
            if line_before.rstrip().endswith(':') and not remaining:
                needs_pass = True
            elif line_before.rstrip().endswith(':') and remaining.startswith('\n'):
                # Next line is empty or whitespace, might be the only statement
                next_line_match = re.match(r'\n(\s*)(\S)', after_match)
                if not next_line_match or not next_line_match.group(1).startswith(indent):
                    needs_pass = True
            
            if needs_pass:
                # Replace with pass instead of commenting
                new = new[:match.start()] + indent + "pass  # removed debug print" + new[match.end():]
            else:
                # Comment out the line
                new = new[:match.start()] + indent + "# " + full_match.strip() + new[match.end():]

        if new == old:
            return PatchMetadata(
                issue_type="print_debug",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error="Pattern found but no changes made",
                original_content=old,
            )

        lines_changed = self._count_lines_changed(old, new)
        diff = self._make_diff(path, old, new)

        if not dry_run:
            path.write_text(new, encoding="utf-8")

        return PatchMetadata(
            issue_type="print_debug",
            file=file_path,
            patch_applied=not dry_run,
            lines_changed=lines_changed,
            diff=diff,
            dry_run=dry_run,
            original_content=old,
            new_content=new,
        )

    def _fix_unused_import(self, file_path: str, params: dict) -> PatchMetadata:
        """Remove unused import statements.

        Handles:
        - 'import foo' (remove entire line)
        - 'from x import foo' (remove foo from import list)
        - 'from x import foo, bar' (handle comma-separated)
        """
        path = self._resolve(file_path)
        old = self._read_file(path)
        dry_run = params.get("dry_run", False)
        import_name = params.get("import_name", "")

        if not import_name:
            return PatchMetadata(
                issue_type="unused_import",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error="No import name specified",
                original_content=old,
            )

        new = old

        # Handle: import foo
        import_line_pattern = re.compile(
            rf'^(\s*)import\s+{re.escape(import_name)}\s*(?:#.*)?$',
            re.MULTILINE
        )
        new = import_line_pattern.sub('', new)

        # Handle: from x import foo
        from_import_single = re.compile(
            rf'^(\s*)from\s+\S+\s+import\s+{re.escape(import_name)}\s*(?:#.*)?$',
            re.MULTILINE
        )
        new = from_import_single.sub('', new)

        # Handle: from x import foo, bar -> from x import bar
        from_import_multi = re.compile(
            rf',?\s*{re.escape(import_name)}\s*(?=#.*$)?(?=\s*$)',
            re.MULTILINE
        )
        new = from_import_multi.sub('', new)

        # Clean up empty from imports: from x import
        empty_from = re.compile(r'^(\s*)from\s+\S+\s+import\s*$', re.MULTILINE)
        new = empty_from.sub('', new)

        # Clean up trailing commas before closing paren
        trailing_comma = re.compile(r',\s*(\s*\))')
        new = trailing_comma.sub(r'\1', new)

        if new == old:
            return PatchMetadata(
                issue_type="unused_import",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error="Import not found in file",
                original_content=old,
            )

        # Validate Python syntax
        syntax_err = self._validate_python(new)
        if syntax_err:
            return PatchMetadata(
                issue_type="unused_import",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error=f"Syntax error after fix: {syntax_err}",
                original_content=old,
                new_content=new,
            )

        lines_changed = self._count_lines_changed(old, new)
        diff = self._make_diff(path, old, new)

        if not dry_run:
            path.write_text(new, encoding="utf-8")

        return PatchMetadata(
            issue_type="unused_import",
            file=file_path,
            patch_applied=not dry_run,
            lines_changed=lines_changed,
            diff=diff,
            dry_run=dry_run,
            original_content=old,
            new_content=new,
        )

    def _fix_duplicate_import(self, file_path: str, params: dict) -> PatchMetadata:
        """Remove duplicate import statements.

        Removes subsequent occurrences of the same import, keeping only the first.
        """
        path = self._resolve(file_path)
        old = self._read_file(path)
        dry_run = params.get("dry_run", False)
        import_pattern = params.get("import_pattern", "")

        if not import_pattern:
            return PatchMetadata(
                issue_type="duplicate_import",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error="No import pattern specified",
                original_content=old,
            )

        lines = old.splitlines(keepends=True)
        seen_imports: set[str] = set()
        lines_to_remove: set[int] = set()

        for i, line in enumerate(lines):
            # Check if this line contains an import that matches our pattern
            for imp_type in ("import", "from"):
                if imp_type in line:
                    # Extract the import identifier
                    if imp_type == "import":
                        match = re.search(rf'{imp_type}\s+([^\s#]+)', line)
                    else:
                        match = re.search(rf'{imp_type}\s+\S+\s+import\s+([^\s#(]+)', line)

                    if match:
                        imp_id = match.group(1).strip()
                        if imp_id == import_pattern:
                            if imp_id in seen_imports:
                                lines_to_remove.add(i)
                            else:
                                seen_imports.add(imp_id)
                    break

        if not lines_to_remove:
            return PatchMetadata(
                issue_type="duplicate_import",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error="No duplicate imports found",
                original_content=old,
            )

        new_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
        new = "".join(new_lines)

        if new == old:
            return PatchMetadata(
                issue_type="duplicate_import",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error="Pattern found but no changes made",
                original_content=old,
            )

        lines_changed = self._count_lines_changed(old, new)
        diff = self._make_diff(path, old, new)

        if not dry_run:
            path.write_text(new, encoding="utf-8")

        return PatchMetadata(
            issue_type="duplicate_import",
            file=file_path,
            patch_applied=not dry_run,
            lines_changed=lines_changed,
            diff=diff,
            dry_run=dry_run,
            original_content=old,
            new_content=new,
        )

    def _fix_trailing_whitespace(self, file_path: str, params: dict) -> PatchMetadata:
        """Remove trailing whitespace from all lines."""
        path = self._resolve(file_path)
        old = self._read_file(path)
        dry_run = params.get("dry_run", False)

        # Pattern: any line ending with whitespace before newline
        lines = old.splitlines(keepends=True)
        new_lines = []
        changed = False

        for line in lines:
            stripped = line.rstrip()
            # Reconstruct the "fixed" version of this line
            if stripped.endswith("\n"):
                fixed_line = stripped  # already has newline
            else:
                fixed_line = stripped + "\n"
            
            if line != fixed_line:
                new_lines.append(fixed_line)
                changed = True
            else:
                new_lines.append(line)

        if not changed:
            return PatchMetadata(
                issue_type="trailing_whitespace",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error="No trailing whitespace found",
                original_content=old,
            )

        # Preserve final newline handling
        new = "".join(new_lines)
        if old.endswith("\n") and not new.endswith("\n"):
            new += "\n"
        elif not old.endswith("\n") and new.endswith("\n"):
            new = new.rstrip("\n")

        lines_changed = self._count_lines_changed(old, new)
        diff = self._make_diff(path, old, new)

        if not dry_run:
            path.write_text(new, encoding="utf-8")

        return PatchMetadata(
            issue_type="trailing_whitespace",
            file=file_path,
            patch_applied=not dry_run,
            lines_changed=lines_changed,
            diff=diff,
            dry_run=dry_run,
            original_content=old,
            new_content=new,
        )

    def _fix_missing_newline_eof(self, file_path: str, params: dict) -> PatchMetadata:
        """Ensure file ends with a newline character."""
        path = self._resolve(file_path)
        old = self._read_file(path)
        dry_run = params.get("dry_run", False)

        if old.endswith("\n") or old == "":
            return PatchMetadata(
                issue_type="missing_newline_eof",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error="File already ends with newline",
                original_content=old,
            )

        new = old + "\n"
        lines_changed = 1  # Adding newline to last line

        # Count lines properly
        old_lines = len(old.splitlines())
        new_lines = len(new.splitlines())
        lines_changed = max(0, new_lines - old_lines)

        diff = self._make_diff(path, old, new)

        if not dry_run:
            path.write_text(new, encoding="utf-8")

        return PatchMetadata(
            issue_type="missing_newline_eof",
            file=file_path,
            patch_applied=not dry_run,
            lines_changed=lines_changed,
            diff=diff,
            dry_run=dry_run,
            original_content=old,
            new_content=new,
        )

    def _fix_todo_fixme(self, file_path: str, params: dict) -> PatchMetadata:
        """Flag TODO/FIXME comments by converting to uppercase prefix.

        Only transforms TODO/FIXME in comment lines (starting with #).
        Adds colon suffix to make them consistently formatted.
        """
        path = self._resolve(file_path)
        old = self._read_file(path)
        dry_run = params.get("dry_run", False)

        lines = old.splitlines(keepends=True)
        new_lines = []
        changed = False

        for line in lines:
            stripped = line.lstrip()
            # Only process comment lines
            if stripped.startswith('#'):
                original_line = line
                # Transform TODO without colon in comments
                line = re.sub(r'\bTODO\b(?!\s*:)', 'TODO:', line, flags=re.IGNORECASE)
                # Transform FIXME without colon
                line = re.sub(r'\bFIXME\b(?!\s*:)', 'FIXME:', line, flags=re.IGNORECASE)
                # Transform XXX without colon
                line = re.sub(r'\bXXX\b(?!\s*:)', 'XXX:', line, flags=re.IGNORECASE)
                # Transform HACK without colon
                line = re.sub(r'\bHACK\b(?!\s*:)', 'HACK:', line, flags=re.IGNORECASE)
                if line != original_line:
                    changed = True
            new_lines.append(line)

        if not changed:
            return PatchMetadata(
                issue_type="todo_fixme",
                file=file_path,
                patch_applied=False,
                lines_changed=0,
                error="No unformatted TODO/FIXME found in comments",
                original_content=old,
            )

        new = "".join(new_lines)
        lines_changed = self._count_lines_changed(old, new)
        diff = self._make_diff(path, old, new)

        if not dry_run:
            path.write_text(new, encoding="utf-8")

        return PatchMetadata(
            issue_type="todo_fixme",
            file=file_path,
            patch_applied=not dry_run,
            lines_changed=lines_changed,
            diff=diff,
            dry_run=dry_run,
            original_content=old,
            new_content=new,
        )

    def list_supported_fixes(self) -> list[str]:
        """Return list of supported fix types."""
        return list(self._fixers.keys())


def create_fixer_registry(repo_path: Path | str) -> FixerRegistry:
    """Factory function to create a FixerRegistry instance."""
    return FixerRegistry(repo_path)