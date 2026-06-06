"""Test and command execution tools."""

from __future__ import annotations

import sys
from pathlib import Path

from agira.registry.base import ToolDefinition, ToolSchema
from agira.tools.context import ExecutionContext


def _schema(props: dict, required: list[str] | None = None) -> ToolSchema:
    return ToolSchema(properties=props, required=required or [])


def _out(props: dict) -> ToolSchema:
    return ToolSchema(properties=props)


def register_execution_tools() -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []

    def _run_inline_tests(ctx: ExecutionContext) -> dict:
        import importlib.util

        tests_dir = ctx.repo_path / "tests"
        if not tests_dir.exists():
            return {"success": True, "passed": 0, "failed": 0, "runner": "inline", "note": "no tests dir"}

        passed = failed = 0
        errors: list[str] = []
        import sys as _sys
        repo_str = str(ctx.repo_path)
        if repo_str not in _sys.path:
            _sys.path.insert(0, repo_str)

        for tf in sorted(tests_dir.glob("test_*.py")):
            spec = importlib.util.spec_from_file_location(tf.stem, tf)
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for name in dir(mod):
                if not name.startswith("test_"):
                    continue
                fn = getattr(mod, name, None)
                if not callable(fn):
                    continue
                try:
                    fn()
                    passed += 1
                except Exception as exc:
                    failed += 1
                    errors.append(f"{tf.name}::{name}: {exc}")

        return {
            "success": failed == 0 and passed > 0,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "runner": "inline",
            "returncode": 0 if failed == 0 else 1,
        }

    def run_tests(params: dict, ctx: ExecutionContext) -> dict:
        timeout = params.get("timeout", 120)
        args = params.get("args", [])
        cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short", *args]
        result = ctx.sandbox.run(cmd, cwd=ctx.repo_path, timeout=timeout)
        if "No module named pytest" in result.stderr or result.returncode == 5:
            out = _run_inline_tests(ctx)
        else:
            out = result.to_dict()
        ref = ctx.store_artifact("test_results", out)
        return {**out, "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "run_tests", "execution_tools", "Run pytest test suite",
            _schema({"timeout": {"type": "number"}, "args": {"type": "array"}}, []),
            _out({"success": {"type": "boolean"}, "stdout": {"type": "string"}}),
            "ToolError", run_tests,
        )
    )

    def run_linter(params: dict, ctx: ExecutionContext) -> dict:
        target = params.get("target", ".")
        cmd = [sys.executable, "-m", "py_compile"]
        errors = []
        root = ctx.repo_path / target if target != "." else ctx.repo_path
        for fp in root.rglob("*.py"):
            if ".git" in fp.parts:
                continue
            result = ctx.sandbox.run(cmd + [str(fp)], cwd=ctx.repo_path, timeout=30)
            if result.returncode != 0:
                errors.append({"file": str(fp.relative_to(ctx.repo_path)), "stderr": result.stderr})
        return {"passed": len(errors) == 0, "errors": errors, "files_checked": "all"}

    tools.append(
        ToolDefinition(
            "run_linter", "execution_tools", "Run basic Python syntax lint via py_compile",
            _schema({"target": {"type": "string"}}, []),
            _out({"passed": {"type": "boolean"}}), "ToolError", run_linter,
        )
    )

    def run_typechecker(params: dict, ctx: ExecutionContext) -> dict:
        target = params.get("target", ".")
        cmd = [sys.executable, "-m", "mypy", target, "--ignore-missing-imports", "--no-error-summary"]
        result = ctx.sandbox.run(cmd, cwd=ctx.repo_path, timeout=params.get("timeout", 60))
        return {
            **result.to_dict(),
            "available": result.returncode in (0, 1),
            "note": "mypy optional; falls back gracefully if not installed",
        }

    tools.append(
        ToolDefinition(
            "run_typechecker", "execution_tools", "Run mypy type checker",
            _schema({"target": {"type": "string"}}, []),
            _out({"returncode": {"type": "integer"}}), "ToolError", run_typechecker,
        )
    )

    def sandbox_exec(params: dict, ctx: ExecutionContext) -> dict:
        command = params["command"]
        if isinstance(command, str):
            command = command.split()
        result = ctx.sandbox.run(
            command, cwd=ctx.repo_path, timeout=params.get("timeout", 60)
        )
        return result.to_dict()

    tools.append(
        ToolDefinition(
            "sandbox_exec", "execution_tools", "Execute command in sandbox",
            _schema({"command": {"type": "array"}, "timeout": {"type": "number"}}, ["command"]),
            _out({"returncode": {"type": "integer"}}), "ToolError", sandbox_exec,
        )
    )

    def run_script(params: dict, ctx: ExecutionContext) -> dict:
        script = params["script"]
        path = Path(script)
        if not path.is_absolute():
            path = ctx.repo_path / path
        result = ctx.sandbox.run_script_file(
            path, args=params.get("args"), cwd=ctx.repo_path, timeout=params.get("timeout", 60)
        )
        return result.to_dict()

    tools.append(
        ToolDefinition(
            "run_script", "execution_tools", "Run a Python script file",
            _schema({"script": {"type": "string"}, "args": {"type": "array"}}, ["script"]),
            _out({"returncode": {"type": "integer"}}), "ToolError", run_script,
        )
    )

    def run_module(params: dict, ctx: ExecutionContext) -> dict:
        module = params["module"]
        cmd = [sys.executable, "-m", module, *params.get("args", [])]
        result = ctx.sandbox.run(cmd, cwd=ctx.repo_path, timeout=params.get("timeout", 60))
        return result.to_dict()

    tools.append(
        ToolDefinition(
            "run_module", "execution_tools", "Run a Python module with -m",
            _schema({"module": {"type": "string"}, "args": {"type": "array"}}, ["module"]),
            _out({"returncode": {"type": "integer"}}), "ToolError", run_module,
        )
    )

    def capture_env_info(params: dict, ctx: ExecutionContext) -> dict:
        result = ctx.sandbox.run(
            [sys.executable, "-c", "import sys,platform; print(sys.version); print(platform.platform())"],
            cwd=ctx.repo_path, timeout=10,
        )
        lines = result.stdout.strip().split("\n")
        return {
            "python_version": lines[0] if lines else "unknown",
            "platform": lines[1] if len(lines) > 1 else "unknown",
        }

    tools.append(
        ToolDefinition(
            "capture_env_info", "execution_tools", "Capture Python environment info",
            _schema({}, []), _out({"python_version": {"type": "string"}}), "ToolError", capture_env_info,
        )
    )

    def run_import_check(params: dict, ctx: ExecutionContext) -> dict:
        module = params.get("module", "")
        results = []
        for fp in ctx.repo_path.rglob("*.py"):
            if ".git" in fp.parts or "test" in fp.name:
                continue
            rel = fp.relative_to(ctx.repo_path)
            mod_path = str(rel).replace("/", ".").replace("\\", ".").removesuffix(".py")
            if module and module not in mod_path:
                continue
            result = ctx.sandbox.run(
                [sys.executable, "-c", f"import importlib; importlib.import_module('{mod_path}')"],
                cwd=ctx.repo_path, timeout=15,
            )
            results.append({
                "module": mod_path,
                "success": result.returncode == 0,
                "stderr": result.stderr[:200],
            })
        return {"imports": results, "passed": all(r["success"] for r in results)}

    tools.append(
        ToolDefinition(
            "run_import_check", "execution_tools", "Verify modules can be imported",
            _schema({"module": {"type": "string"}}, []),
            _out({"passed": {"type": "boolean"}}), "ToolError", run_import_check,
        )
    )

    return tools
