"""Built-in analyzer plugins."""

from __future__ import annotations

from typing import Any

from agira.plugins import Plugin


class SecurityAuditAnalyzer(Plugin):
    """Audit code for common security vulnerabilities."""

    name = "security_audit"
    category = "analyzers"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from pathlib import Path
        repo_path = Path(context.get("repo_path", ""))
        issues = []
        for py_file in repo_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                if "eval(" in content:
                    issues.append({"file": str(py_file), "type": "eval_usage"})
                if "pickle.loads" in content:
                    issues.append({"file": str(py_file), "type": "pickle_load"})
                if "os.system" in content:
                    issues.append({"file": str(py_file), "type": "os_system"})
            except Exception:
                pass
        return {"success": True, "issues": issues, "count": len(issues)}


class ComplexityAnalyzer(Plugin):
    """Analyze cyclomatic complexity of Python files."""

    name = "complexity_analyzer"
    category = "analyzers"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        import ast
        from pathlib import Path
        repo_path = Path(context.get("repo_path", ""))
        results = []
        for py_file in repo_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        complexity = self._compute_cyclomatic(node)
                        if complexity > 10:
                            results.append({
                                "file": str(py_file),
                                "function": node.name,
                                "complexity": complexity,
                            })
            except Exception:
                pass
        return {"success": True, "results": results, "count": len(results)}

    def _compute_cyclomatic(self, node: ast.FunctionDef) -> int:
        import ast
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            if isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity


BuiltInAnalyzers = [SecurityAuditAnalyzer, ComplexityAnalyzer]