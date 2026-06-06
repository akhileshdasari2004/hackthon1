"""Static analysis tools."""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from agira.registry.base import ToolDefinition, ToolSchema
from agira.tools.context import ExecutionContext


def _schema(props: dict, required: list[str] | None = None) -> ToolSchema:
    return ToolSchema(properties=props, required=required or [])


def _out(props: dict) -> ToolSchema:
    return ToolSchema(properties=props)


def _py_files(ctx: ExecutionContext, subpath: str = "") -> list[Path]:
    root = ctx.repo_path / subpath if subpath else ctx.repo_path
    return [f for f in root.rglob("*.py") if f.is_file() and ".git" not in f.parts]


def register_analysis_tools() -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []

    def parse_ast(params: dict, ctx: ExecutionContext) -> dict:
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
        nodes = {
            "functions": [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)],
            "classes": [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)],
            "imports": [
                n.names[0].name if n.names else ""
                for n in ast.walk(tree)
                if isinstance(n, (ast.Import, ast.ImportFrom))
            ],
        }
        ref = ctx.store_artifact(f"ast:{path.name}", nodes)
        return {"file": str(path), "nodes": nodes, "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "parse_ast", "analysis_tools", "Parse Python AST and extract symbols",
            _schema({"path": {"type": "string"}}, ["path"]),
            _out({"nodes": {"type": "object"}}), "ToolError", parse_ast,
        )
    )

    def build_dependency_graph(params: dict, ctx: ExecutionContext) -> dict:
        graph: dict[str, list[str]] = defaultdict(list)
        for fp in _py_files(ctx):
            rel = str(fp.relative_to(ctx.repo_path))
            try:
                tree = ast.parse(fp.read_text(encoding="utf-8"), filename=str(fp))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        graph[rel].append(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    graph[rel].append(node.module.split(".")[0])
        graph_dict = {k: sorted(set(v)) for k, v in graph.items()}
        ref = ctx.store_artifact("dependency_graph", graph_dict)
        return {"graph": graph_dict, "file_count": len(graph_dict), "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "build_dependency_graph", "analysis_tools", "Build import dependency graph",
            _schema({}, []), _out({"graph": {"type": "object"}}), "ToolError", build_dependency_graph,
        )
    )

    def detect_circular_imports(params: dict, ctx: ExecutionContext) -> dict:
        graph = params.get("dependency_graph")
        if isinstance(graph, dict) and "graph" in graph:
            graph = graph["graph"]
        if not graph:
            graph = ctx.get_artifact("dependency_graph")
        if isinstance(graph, dict) and "graph" in graph:
            graph = graph["graph"]
        if not graph:
            graph = build_dependency_graph({}, ctx)["graph"]
        module_map: dict[str, str] = {}
        for fp in _py_files(ctx):
            rel = str(fp.relative_to(ctx.repo_path))
            mod = rel.replace("/", ".").replace("\\", ".").removesuffix(".py")
            module_map[mod.split(".")[-1]] = mod
        cycles = []
        for file_mod, deps in graph.items():
            src_mod = file_mod.replace("/", ".").replace("\\", ".").removesuffix(".py")
            for dep in deps:
                if dep in module_map and module_map[dep] in graph:
                    if src_mod.split(".")[-1] in graph.get(
                        module_map[dep].replace(".", "/") + ".py", []
                    ) or src_mod.split(".")[-1] in graph.get(
                        module_map[dep], []
                    ):
                        cycles.append({"from": src_mod, "to": module_map[dep]})
        ref = ctx.store_artifact("circular_imports", cycles)
        return {"cycles": cycles, "count": len(cycles), "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "detect_circular_imports", "analysis_tools", "Detect circular import patterns",
            _schema({}, []), _out({"cycles": {"type": "array"}}), "ToolError", detect_circular_imports,
        )
    )

    def compute_complexity_score(params: dict, ctx: ExecutionContext) -> dict:
        scores = []
        for fp in _py_files(ctx):
            try:
                tree = ast.parse(fp.read_text(encoding="utf-8"), filename=str(fp))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    complexity = 1
                    for child in ast.walk(node):
                        if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                            complexity += 1
                    scores.append({
                        "file": str(fp.relative_to(ctx.repo_path)),
                        "function": node.name,
                        "complexity": complexity,
                    })
        avg = sum(s["complexity"] for s in scores) / max(len(scores), 1)
        ref = ctx.store_artifact("complexity_scores", scores)
        return {"scores": scores, "average": round(avg, 2), "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "compute_complexity_score", "analysis_tools", "Compute cyclomatic complexity",
            _schema({}, []), _out({"scores": {"type": "array"}}), "ToolError", compute_complexity_score,
        )
    )

    def dead_code_detection(params: dict, ctx: ExecutionContext) -> dict:
        defined: set[str] = set()
        referenced: set[str] = set()
        for fp in _py_files(ctx):
            try:
                tree = ast.parse(fp.read_text(encoding="utf-8"), filename=str(fp))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    defined.add(node.name)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    referenced.add(node.id)
        dead = sorted(defined - referenced - {"main", "__init__"})
        ref = ctx.store_artifact("dead_code", dead)
        return {"dead_functions": dead, "count": len(dead), "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "dead_code_detection", "analysis_tools", "Detect unreferenced function definitions",
            _schema({}, []), _out({"dead_functions": {"type": "array"}}), "ToolError", dead_code_detection,
        )
    )

    def vulnerability_scan_stub(params: dict, ctx: ExecutionContext) -> dict:
        findings = []
        patterns = {
            "eval_usage": r"\beval\s*\(",
            "exec_usage": r"\bexec\s*\(",
            "pickle_load": r"pickle\.loads?\s*\(",
            "shell_true": r"shell\s*=\s*True",
        }
        for fp in _py_files(ctx):
            text = fp.read_text(encoding="utf-8", errors="ignore")
            for vuln, pat in patterns.items():
                if re.search(pat, text):
                    findings.append({
                        "file": str(fp.relative_to(ctx.repo_path)),
                        "type": vuln,
                        "severity": "high" if vuln in ("eval_usage", "exec_usage") else "medium",
                    })
        ref = ctx.store_artifact("vulnerabilities", findings)
        return {"findings": findings, "count": len(findings), "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "vulnerability_scan_stub", "analysis_tools", "Stub vulnerability pattern scanner",
            _schema({}, []), _out({"findings": {"type": "array"}}), "ToolError", vulnerability_scan_stub,
        )
    )

    def pattern_analyzer(params: dict, ctx: ExecutionContext) -> dict:
        anti_patterns = []
        checks = {
            "bare_except": (r"except\s*:", "Bare except clause"),
            "mutable_default": (r"def\s+\w+\([^)]*=\s*(\[\]|\{\})", "Mutable default argument"),
            "print_debug": (r"print\s*\([^)]*debug", "Debug print statement"),
            "todo_fixme": (r"(TODO|FIXME|HACK|XXX)", "Unresolved TODO/FIXME"),
        }
        for fp in _py_files(ctx):
            text = fp.read_text(encoding="utf-8", errors="ignore")
            for key, (pat, desc) in checks.items():
                if re.search(pat, text, re.IGNORECASE):
                    anti_patterns.append({
                        "file": str(fp.relative_to(ctx.repo_path)),
                        "pattern": key,
                        "description": desc,
                    })
        ref = ctx.store_artifact("anti_patterns", anti_patterns)
        return {"patterns": anti_patterns, "count": len(anti_patterns), "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "pattern_analyzer", "analysis_tools", "Detect code anti-patterns",
            _schema({}, []), _out({"patterns": {"type": "array"}}), "ToolError", pattern_analyzer,
        )
    )

    def find_unused_imports(params: dict, ctx: ExecutionContext) -> dict:
        unused = []
        for fp in _py_files(ctx):
            try:
                tree = ast.parse(fp.read_text(encoding="utf-8"), filename=str(fp))
            except SyntaxError:
                continue
            imported = set()
            used = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported.add(alias.asname or alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imported.add(alias.asname or alias.name)
                elif isinstance(node, ast.Name):
                    used.add(node.id)
            for imp in imported - used:
                unused.append({"file": str(fp.relative_to(ctx.repo_path)), "import": imp})
        ref = ctx.store_artifact("unused_imports", unused)
        return {"unused": unused, "count": len(unused), "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "find_unused_imports", "analysis_tools", "Find unused import statements",
            _schema({}, []), _out({"unused": {"type": "array"}}), "ToolError", find_unused_imports,
        )
    )

    def detect_long_functions(params: dict, ctx: ExecutionContext) -> dict:
        threshold = params.get("threshold", 50)
        long_funcs = []
        for fp in _py_files(ctx):
            try:
                tree = ast.parse(fp.read_text(encoding="utf-8"), filename=str(fp))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.end_lineno:
                    length = node.end_lineno - node.lineno
                    if length >= threshold:
                        long_funcs.append({
                            "file": str(fp.relative_to(ctx.repo_path)),
                            "function": node.name,
                            "lines": length,
                        })
        ref = ctx.store_artifact("long_functions", long_funcs)
        return {"functions": long_funcs, "count": len(long_funcs), "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "detect_long_functions", "analysis_tools", "Detect functions exceeding line threshold",
            _schema({"threshold": {"type": "integer"}}, []),
            _out({"functions": {"type": "array"}}), "ToolError", detect_long_functions,
        )
    )

    def analyze_test_coverage_stub(params: dict, ctx: ExecutionContext) -> dict:
        test_files = [f for f in _py_files(ctx) if "test" in f.name.lower()]
        src_files = [f for f in _py_files(ctx) if "test" not in f.name.lower()]
        ratio = len(test_files) / max(len(src_files), 1)
        return {
            "test_files": len(test_files),
            "source_files": len(src_files),
            "estimated_coverage_ratio": round(min(ratio, 1.0), 2),
            "stub": True,
        }

    tools.append(
        ToolDefinition(
            "analyze_test_coverage_stub", "analysis_tools", "Estimate test coverage from file ratio",
            _schema({}, []), _out({"estimated_coverage_ratio": {"type": "number"}}),
            "ToolError", analyze_test_coverage_stub,
        )
    )

    def extract_symbols(params: dict, ctx: ExecutionContext) -> dict:
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        symbols = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                symbols.append({"name": node.name, "type": type(node).__name__, "line": node.lineno})
        return {"file": str(path), "symbols": symbols, "count": len(symbols)}

    tools.append(
        ToolDefinition(
            "extract_symbols", "analysis_tools", "Extract top-level symbols from a file",
            _schema({"path": {"type": "string"}}, ["path"]),
            _out({"symbols": {"type": "array"}}), "ToolError", extract_symbols,
        )
    )

    def count_dependencies(params: dict, ctx: ExecutionContext) -> dict:
        graph = params.get("dependency_graph")
        if isinstance(graph, dict) and "graph" in graph:
            graph = graph["graph"]
        if not graph:
            graph = ctx.get_artifact("dependency_graph")
        if isinstance(graph, dict) and "graph" in graph:
            graph = graph["graph"]
        if not graph:
            graph = build_dependency_graph({}, ctx)["graph"]
        all_deps: set[str] = set()
        for deps in graph.values():
            all_deps.update(deps)
        stdlib = {"os", "sys", "re", "json", "pathlib", "typing", "ast", "subprocess", "collections"}
        external = sorted(all_deps - stdlib)
        return {"total": len(all_deps), "external": external, "external_count": len(external)}

    tools.append(
        ToolDefinition(
            "count_dependencies", "analysis_tools", "Count unique dependencies",
            _schema({}, []), _out({"total": {"type": "integer"}}), "ToolError", count_dependencies,
        )
    )

    def find_duplicate_code_stub(params: dict, ctx: ExecutionContext) -> dict:
        line_hashes: dict[str, list[str]] = defaultdict(list)
        for fp in _py_files(ctx):
            for i, line in enumerate(fp.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                stripped = line.strip()
                if len(stripped) > 40:
                    line_hashes[stripped].append(f"{fp.relative_to(ctx.repo_path)}:{i}")
        duplicates = [
            {"line": k, "locations": v}
            for k, v in line_hashes.items()
            if len(v) > 1
        ]
        return {"duplicates": duplicates[:20], "count": len(duplicates)}

    tools.append(
        ToolDefinition(
            "find_duplicate_code_stub", "analysis_tools", "Detect duplicate code lines",
            _schema({}, []), _out({"duplicates": {"type": "array"}}), "ToolError", find_duplicate_code_stub,
        )
    )

    def detect_hardcoded_secrets(params: dict, ctx: ExecutionContext) -> dict:
        secret_patterns = {
            "api_key": r"(?i)(api[_-]?key|apikey)\s*=\s*['\"][^'\"]+['\"]",
            "password": r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]+['\"]",
            "token": r"(?i)(token|secret)\s*=\s*['\"][^'\"]+['\"]",
        }
        findings = []
        for fp in _py_files(ctx):
            text = fp.read_text(encoding="utf-8", errors="ignore")
            for stype, pat in secret_patterns.items():
                if re.search(pat, text):
                    findings.append({
                        "file": str(fp.relative_to(ctx.repo_path)),
                        "type": stype,
                    })
        ref = ctx.store_artifact("hardcoded_secrets", findings)
        return {"findings": findings, "count": len(findings), "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "detect_hardcoded_secrets", "analysis_tools", "Detect hardcoded secrets",
            _schema({}, []), _out({"findings": {"type": "array"}}), "ToolError", detect_hardcoded_secrets,
        )
    )

    def analyze_api_surface(params: dict, ctx: ExecutionContext) -> dict:
        public_api = []
        for fp in _py_files(ctx):
            if fp.name == "__init__.py":
                continue
            try:
                tree = ast.parse(fp.read_text(encoding="utf-8"), filename=str(fp))
            except SyntaxError:
                continue
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
                    public_api.append({
                        "file": str(fp.relative_to(ctx.repo_path)),
                        "name": node.name,
                        "type": type(node).__name__,
                    })
        ref = ctx.store_artifact("api_surface", public_api)
        return {"api": public_api, "count": len(public_api), "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "analyze_api_surface", "analysis_tools", "Analyze public API surface",
            _schema({}, []), _out({"api": {"type": "array"}}), "ToolError", analyze_api_surface,
        )
    )

    def detect_syntax_errors(params: dict, ctx: ExecutionContext) -> dict:
        errors = []
        for fp in _py_files(ctx):
            try:
                ast.parse(fp.read_text(encoding="utf-8"), filename=str(fp))
            except SyntaxError as e:
                errors.append({
                    "file": str(fp.relative_to(ctx.repo_path)),
                    "line": e.lineno,
                    "message": e.msg,
                })
        ref = ctx.store_artifact("syntax_errors", errors)
        return {"errors": errors, "count": len(errors), "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "detect_syntax_errors", "analysis_tools", "Detect Python syntax errors",
            _schema({}, []), _out({"errors": {"type": "array"}}), "ToolError", detect_syntax_errors,
        )
    )

    return tools
