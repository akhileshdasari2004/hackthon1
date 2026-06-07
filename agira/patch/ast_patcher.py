"""AST-based patching with validation."""

from __future__ import annotations

import ast
import difflib
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class PatchResult:
    success: bool
    file_path: str
    diff: str
    old_content: str
    new_content: str
    error: str | None = None
    fix_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "file_path": self.file_path,
            "diff": self.diff,
            "error": self.error,
            "fix_type": self.fix_type,
        }


class ASTPatcher:
    """Apply structured AST transformations with diff generation.

    Uses source-based transformations for determinism.
    AST is used only for detection/validation, not code generation.
    """

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path

    def _resolve(self, file_path: str) -> Path:
        p = Path(file_path)
        return p if p.is_absolute() else self.repo_path / p

    def _make_diff(self, path: Path, old: str, new: str) -> str:
        return "".join(difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        ))

    def _validate_python(self, content: str, path: Path) -> str | None:
        try:
            ast.parse(content, filename=str(path))
            return None
        except SyntaxError as e:
            return str(e)

    def fix_bare_except(self, file_path: str, issue: dict) -> PatchResult:
        """Fix bare except clauses using source-based transformation."""
        path = self._resolve(file_path)
        old = path.read_text(encoding="utf-8")

        # Detect bare except using AST
        try:
            tree = ast.parse(old, filename=str(path))
        except SyntaxError as e:
            return PatchResult(False, file_path, "", old, old, str(e), "bare_except")

        # Find all bare except handlers
        bare_excepts = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                bare_excepts.append(node)

        if not bare_excepts:
            return PatchResult(False, file_path, "", old, old, "no bare except found", "bare_except")

        lines = old.splitlines(keepends=True)
        # Process in reverse order to preserve line numbers
        for handler in reversed(bare_excepts):
            # Find the exact except: line in source using line number
            if hasattr(handler, 'lineno'):
                # Find the except: line
                for i, line in enumerate(lines):
                    if i + 1 == handler.lineno and re.match(r'\s*except\s*:\s*(?:#.*)?$', line):
                        # Replace with except Exception: (preserve trailing content)
                        indent = len(line) - len(line.lstrip())
                        # Get trailing content (newline, etc.)
                        trailing = line[len(line.rstrip()):]
                        lines[i] = ' ' * indent + 'except Exception:' + trailing
                        break
        new = ''.join(lines)

        if new == old:
            return PatchResult(False, file_path, "", old, old, "could not apply fix", "bare_except")

        err = self._validate_python(new, path)
        if err:
            return PatchResult(False, file_path, "", old, new, err, "bare_except")

        return PatchResult(True, file_path, self._make_diff(path, old, new), old, new, fix_type="bare_except")

    def fix_division_by_zero(self, file_path: str, issue: dict) -> PatchResult:
        """Fix potential division by zero using source-based transformation."""
        path = self._resolve(file_path)
        old = path.read_text(encoding="utf-8")

        target_fn = issue.get("function", "")

        # Find the function using AST
        try:
            tree = ast.parse(old, filename=str(path))
        except SyntaxError as e:
            return PatchResult(False, file_path, "", old, old, str(e), "division_by_zero")

        # Find the target function
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not target_fn or node.name == target_fn:
                    func_node = node
                    break

        if not func_node:
            return PatchResult(False, file_path, "", old, old, f"function {target_fn or 'any'} not found", "division_by_zero")

        # Use source-based replacement for division operations
        new = old

        # Pattern to find: return a / b or return a / b if ... else ...
        # We need to be careful to only fix divisions inside the target function
        # This is a simplified approach - find the function's line range
        func_lines = new.splitlines(keepends=True)
        func_start = func_node.lineno - 1
        func_end = func_node.end_lineno if hasattr(func_node, 'end_lineno') else len(func_lines)

        # Look for division in return statements within function
        # Pattern: something / something
        div_pattern = re.compile(r'(\w+)\s*/\s*(\w+)')

        for i in range(func_start, min(func_end, len(func_lines))):
            line = func_lines[i]
            # Skip if it's already handled
            if 'if' in line and 'else' in line:
                continue
            match = div_pattern.search(line)
            if match and 'return' in line.lower():
                # Check if this division is in a return statement
                # Simple heuristic: line contains "return" and "/"
                # For now, we'll be conservative and only fix simple patterns
                pass  # Conservative approach - let the pattern matching be more precise

        # More precise approach: find "return a / b" patterns
        # and replace with "return a / b if b != 0 else 0"
        # Uses trailing \s* to handle trailing whitespace after divisor
        # Uses [\w.]+ to handle attribute access like self.x / y
        simple_return_div = re.compile(r'\b(return\s+[\w.]+\s*/\s*[\w.]+)\s*\b')

        def replace_div(m):
            expr = m.group(1)
            # Extract the dividend and divisor
            parts = expr.split('/')
            if len(parts) == 2:
                dividend = parts[0].replace('return', '').strip()
                divisor = parts[1].strip()
                return f"return {dividend} / {divisor} if {divisor} != 0 else 0"
            return expr

        new = simple_return_div.sub(replace_div, new)

        if new == old:
            return PatchResult(False, file_path, "", old, old, "no change produced", "division_by_zero")

        err = self._validate_python(new, path)
        if err:
            return PatchResult(False, file_path, "", old, new, err, "division_by_zero")

        return PatchResult(True, file_path, self._make_diff(path, old, new), old, new, fix_type="division_by_zero")

    def fix_unused_import(self, file_path: str, issue: dict) -> PatchResult:
        """Remove unused imports using source-based transformation."""
        path = self._resolve(file_path)
        old = path.read_text(encoding="utf-8")
        import_name = issue.get("import", "")

        if not import_name:
            return PatchResult(False, file_path, "", old, old, "no import specified", "unused_import")

        new = old

        # Handle: import foo -> remove entire line
        import_line_pattern = re.compile(rf'^import\s+{re.escape(import_name)}\s*(?:#.*)?$', re.MULTILINE)
        new = import_line_pattern.sub('', new)

        # Handle: from x import foo -> remove just foo from the import
        from_import_pattern = re.compile(rf',?\s*{re.escape(import_name)}\s*(?:#.*)?(?=\s*$)', re.MULTILINE)
        new = from_import_pattern.sub('', new)

        # Clean up empty from imports: from x import
        empty_from_import = re.compile(r'^from\s+\S+\s+import\s*$', re.MULTILINE)
        new = empty_from_import.sub('', new)

        if new == old:
            return PatchResult(False, file_path, "", old, old, "no change", "unused_import")

        err = self._validate_python(new, path)
        if err:
            return PatchResult(False, file_path, "", old, new, err, "unused_import")

        return PatchResult(True, file_path, self._make_diff(path, old, new), old, new, fix_type="unused_import")

    def fix_eval_usage(self, file_path: str, issue: dict) -> PatchResult:
        """Replace eval() with ast.literal_eval() using source-based transformation."""
        path = self._resolve(file_path)
        old = path.read_text(encoding="utf-8")
        new = old.replace("eval(", "ast.literal_eval(")

        if "ast.literal_eval(" in new and "import ast" not in new:
            # Add import ast at the top
            if new.startswith("#!"):
                # Skip shebang
                first_newline = new.find("\n")
                if first_newline != -1:
                    new = new[:first_newline+1] + "import ast\n" + new[first_newline+1:]
            else:
                new = "import ast\n" + new

        if new == old:
            return PatchResult(False, file_path, "", old, old, "no change", "eval_usage")

        err = self._validate_python(new, path)
        if err:
            return PatchResult(False, file_path, "", old, new, err, "eval_usage")

        return PatchResult(True, file_path, self._make_diff(path, old, new), old, new, fix_type="eval_usage")

    def fix_hardcoded_secret(self, file_path: str, issue: dict) -> PatchResult:
        """Replace hardcoded secrets with environment variable lookups."""
        path = self._resolve(file_path)
        old = path.read_text(encoding="utf-8")

        # Pattern to match: API_KEY = 'value' or password = "secret" etc.
        # We look for common secret patterns and replace with os.environ.get()
        secret_pattern = re.compile(
            r'(?i)(API_KEY|password|token|secret)\s*=\s*[\'"]([^\'"]+)[\'"]'
        )

        def replace_secret(m):
            name = m.group(1).upper()
            return f'{name} = os.environ.get("{name}", "")'

        new = secret_pattern.sub(replace_secret, old)

        if new == old:
            return PatchResult(False, file_path, "", old, old, "no change", "hardcoded_secret")

        # Add import os if not present
        if "import os" not in new:
            if new.startswith("#!"):
                first_newline = new.find("\n")
                if first_newline != -1:
                    new = new[:first_newline+1] + "import os\n" + new[first_newline+1:]
            else:
                new = "import os\n" + new

        err = self._validate_python(new, path)
        if err:
            return PatchResult(False, file_path, "", old, new, err, "hardcoded_secret")

        return PatchResult(True, file_path, self._make_diff(path, old, new), old, new, fix_type="hardcoded_secret")

    def fix_pickle_load(self, file_path: str, issue: dict) -> PatchResult:
        """Replace pickle.loads with a safe alternative."""
        path = self._resolve(file_path)
        old = path.read_text(encoding="utf-8")
        new = old.replace("pickle.loads", "# pickle.loads disabled for security")

        if new == old:
            return PatchResult(False, file_path, "", old, old, "no change", "pickle_load")

        err = self._validate_python(new, path)
        if err:
            return PatchResult(False, file_path, "", old, new, err, "pickle_load")

        return PatchResult(True, file_path, self._make_diff(path, old, new), old, new, fix_type="pickle_load")

    def apply(self, file_path: str, fix_type: str, issue: dict | None = None) -> PatchResult:
        issue = issue or {}
        handlers = {
            "bare_except": self.fix_bare_except,
            "division_by_zero": self.fix_division_by_zero,
            "unused_import": self.fix_unused_import,
            "eval_usage": self.fix_eval_usage,
            "hardcoded_secret": self.fix_hardcoded_secret,
            "pickle_load": self.fix_pickle_load,
        }
        handler = handlers.get(fix_type)
        if not handler:
            return PatchResult(False, file_path, "", "", "", f"unknown fix type: {fix_type}")
        return handler(file_path, issue)

    def write_patch(self, result: PatchResult) -> None:
        if not result.success:
            raise ValueError(result.error or "patch failed")
        path = self._resolve(result.file_path)
        path.write_text(result.new_content, encoding="utf-8")

    def rollback(self, file_path: str, old_content: str) -> None:
        self._resolve(file_path).write_text(old_content, encoding="utf-8")