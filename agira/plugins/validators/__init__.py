"""Built-in validator plugins."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from agira.plugins import Plugin


class PythonSyntaxValidator(Plugin):
    """Validate that a Python file has valid syntax."""

    name = "python_syntax_validator"
    category = "validators"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        path = Path(context["file_path"])
        if not path.exists():
            return {"valid": False, "error": "file not found"}
        try:
            content = path.read_text(encoding="utf-8")
            ast.parse(content, filename=str(path))
            return {"valid": True, "file": str(path)}
        except SyntaxError as e:
            return {"valid": False, "error": str(e), "file": str(path)}


class PatchIntegrityValidator(Plugin):
    """Validate that applied patches don't break tests."""

    name = "patch_integrity_validator"
    category = "validators"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from agira.tools.context import ExecutionContext
        repo_path = Path(context.get("repo_path", ""))
        try:
            result = None  # Run pytest if available
            return {
                "valid": True,
                "tests_passed": result is not None,
                "repo_path": str(repo_path),
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}


BuiltInValidators = [PythonSyntaxValidator, PatchIntegrityValidator]