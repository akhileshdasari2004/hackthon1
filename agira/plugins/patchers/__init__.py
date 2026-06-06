"""Built-in patcher plugins."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agira.plugins import Plugin


class SafeEvalPatcher(Plugin):
    """Replace eval() with ast.literal_eval()."""

    name = "safe_eval_patcher"
    category = "patchers"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        path = Path(context["file_path"])
        if not path.exists():
            return {"success": False, "error": "file not found"}
        content = path.read_text(encoding="utf-8")
        original = content
        new = re.sub(r"\beval\(", "ast.literal_eval(", content)
        if new == original:
            return {"success": True, "applied": False, "reason": "no eval found"}
        path.write_text(new, encoding="utf-8")
        return {"success": True, "applied": True, "file": str(path)}


class HardcodedSecretPatcher(Plugin):
    """Replace hardcoded secrets with os.environ.get()."""

    name = "hardcoded_secret_patcher"
    category = "patchers"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        path = Path(context["file_path"])
        if not path.exists():
            return {"success": False, "error": "file not found"}
        content = path.read_text(encoding="utf-8")
        original = content

        def replace_secret(m):
            name = m.group(1).upper()
            return f'{name} = os.environ.get("{name}", "")'

        new = re.sub(
            r'(?i)(API_KEY|password|token|secret)\s*=\s*[\'"]([^\'"]+)[\'"]',
            replace_secret,
            content,
        )
        if new == original:
            return {"success": True, "applied": False, "reason": "no secrets found"}
        path.write_text(new, encoding="utf-8")
        return {"success": True, "applied": True, "file": str(path)}


BuiltInPatchers = [SafeEvalPatcher, HardcodedSecretPatcher]