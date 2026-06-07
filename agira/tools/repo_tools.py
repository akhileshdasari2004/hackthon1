"""Repository manipulation tools."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agira.registry.base import ToolDefinition, ToolSchema
from agira.tools.context import ExecutionContext


# ── Path containment validator ────────────────────────────────────────────────

def _validate_path(path: Path, repo_path: Path) -> Path:
    """Resolve and validate path stays within repo_path.

    Raises:
        ValueError: If path escapes repo_path (path traversal attempt).
    """
    try:
        resolved = path.resolve().relative_to(repo_path.resolve())
        if resolved.parts and resolved.parts[0] == "..":
            raise ValueError(f"Path traversal rejected: {path}")
        return path
    except ValueError:
        raise ValueError(f"Path traversal rejected: {path}")


def _safe_join(repo_path: Path, user_path: str | Path) -> Path:
    """Join repo_path with user-provided relative path, then validate containment."""
    user = Path(user_path)
    if user.is_absolute():
        joined = user
    else:
        joined = repo_path / user
    return _validate_path(joined, repo_path)


def _schema(props: dict, required: list[str] | None = None) -> ToolSchema:
    return ToolSchema(properties=props, required=required or [])


def _out(props: dict) -> ToolSchema:
    return ToolSchema(properties=props)


def register_repo_tools() -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []

    # ── Internal helpers ────────────────────────────────────────────────────

    def clone_repo(params: dict, ctx: ExecutionContext) -> dict:
        ctx.rate_limiter.acquire()
        url = params["url"]
        dest = Path(params.get("dest", ctx.repo_path))
        _validate_path(dest.parent, ctx.repo_path.parent)
        if dest.exists() and list(dest.iterdir()):
            return {"cloned": False, "path": str(dest), "reason": "already_exists"}
        dest.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True, text=True,
        )
        return {
            "cloned": result.returncode == 0,
            "path": str(dest),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def list_files(params: dict, ctx: ExecutionContext) -> dict:
        root = _safe_join(ctx.repo_path, params.get("path", "."))
        pattern = params.get("pattern", "**/*")
        max_files = params.get("max_files", 500)
        files = []
        for p in sorted(root.glob(pattern)):
            if p.is_file() and ".git" not in p.parts:
                files.append(str(p.relative_to(root)))
                if len(files) >= max_files:
                    break
        return {"files": files, "count": len(files), "root": str(root)}

    def read_file(params: dict, ctx: ExecutionContext) -> dict:
        path = _safe_join(ctx.repo_path, params["path"])
        content = path.read_text(encoding="utf-8", errors="replace")
        return {"path": str(path), "content": content, "lines": content.count("\n") + 1}

    def write_file(params: dict, ctx: ExecutionContext) -> dict:
        path = _safe_join(ctx.repo_path, params["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(params["content"], encoding="utf-8")
        return {"path": str(path), "written": True, "bytes": len(params["content"])}

    def edit_file(params: dict, ctx: ExecutionContext) -> dict:
        path = _safe_join(ctx.repo_path, params["path"])
        if not path.exists():
            return {"success": False, "error": "FILE_NOT_FOUND", "path": str(path)}
        content = path.read_text(encoding="utf-8")
        old_text = params.get("oldText")
        new_text = params.get("newText")
        if not old_text:
            return {"success": False, "error": "OLD_TEXT_REQUIRED", "path": str(path)}
        if not new_text:
            return {"success": False, "error": "NEW_TEXT_REQUIRED", "path": str(path)}
        if old_text not in content:
            return {
                "success": False,
                "error": "OLD_TEXT_NOT_FOUND_EXACT_MATCH",
                "path": str(path),
                "hint": "oldText must be extracted exactly from file content",
            }
        new_content = content.replace(old_text, new_text, 1)
        path.write_text(new_content, encoding="utf-8")
        verified_content = path.read_text(encoding="utf-8")
        if old_text in verified_content or new_text not in verified_content:
            path.write_text(content, encoding="utf-8")  # rollback
            return {"success": False, "error": "PATCH_VERIFICATION_FAILED", "path": str(path)}
        return {"success": True, "path": str(path), "oldText_length": len(old_text), "newText_length": len(new_text), "verified": True}

    def search_code(params: dict, ctx: ExecutionContext) -> dict:
        query = params["query"]
        root = _safe_join(ctx.repo_path, params.get("path", "."))
        is_regex = params.get("regex", False)
        matches = []
        for fp in root.rglob("*"):
            if not fp.is_file() or ".git" in fp.parts:
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                found = re.search(query, line) if is_regex else query in line
                if found:
                    matches.append({"file": str(fp.relative_to(root)), "line": i, "text": line.strip()})
                    if len(matches) >= params.get("max_results", 50):
                        return {"matches": matches, "count": len(matches)}
        return {"matches": matches, "count": len(matches)}

    def git_diff(params: dict, ctx: ExecutionContext) -> dict:
        args = ["git", "-C", str(ctx.repo_path), "diff"]
        if params.get("staged"):
            args.append("--staged")
        if params.get("path"):
            path = _safe_join(ctx.repo_path, params["path"])
            args.extend(["--", str(path)])
        result = subprocess.run(args, capture_output=True, text=True)
        return {"diff": result.stdout, "has_changes": bool(result.stdout.strip())}

    def create_branch(params: dict, ctx: ExecutionContext) -> dict:
        name = params["name"]
        result = subprocess.run(
            ["git", "-C", str(ctx.repo_path), "checkout", "-b", name],
            capture_output=True, text=True,
        )
        return {"branch": name, "created": result.returncode == 0, "stderr": result.stderr}

    def get_repo_metadata(params: dict, ctx: ExecutionContext) -> dict:
        root = ctx.repo_path
        py_files = [f for f in root.rglob("*.py") if ".git" not in f.parts]
        total_lines = sum(
            f.read_text(encoding="utf-8", errors="ignore").count("\n")
            for f in py_files
        )
        return {
            "path": str(root),
            "python_files": len(py_files),
            "total_lines": total_lines,
            "has_git": (root / ".git").exists(),
            "name": root.name,
        }

    def count_lines(params: dict, ctx: ExecutionContext) -> dict:
        path = _safe_join(ctx.repo_path, params.get("path", "."))
        if path.is_file():
            lines = path.read_text(encoding="utf-8", errors="ignore").count("\n") + 1
            return {"path": str(path), "lines": lines}
        total = 0
        for f in path.rglob("*"):
            if f.is_file():
                total += f.read_text(encoding="utf-8", errors="ignore").count("\n") + 1
        return {"path": str(path), "lines": total}

    def file_exists(params: dict, ctx: ExecutionContext) -> dict:
        path = _safe_join(ctx.repo_path, params["path"])
        return {"path": str(path), "exists": path.exists(), "is_file": path.is_file()}

    def get_git_status(params: dict, ctx: ExecutionContext) -> dict:
        result = subprocess.run(
            ["git", "-C", str(ctx.repo_path), "status", "--porcelain"],
            capture_output=True, text=True,
        )
        lines = [l for l in result.stdout.strip().split("\n") if l]
        return {"status_lines": lines, "dirty": len(lines) > 0, "change_count": len(lines)}

    def list_branches(params: dict, ctx: ExecutionContext) -> dict:
        result = subprocess.run(
            ["git", "-C", str(ctx.repo_path), "branch", "--list"],
            capture_output=True, text=True,
        )
        branches = [b.strip().lstrip("* ") for b in result.stdout.strip().split("\n") if b.strip()]
        return {"branches": branches, "count": len(branches)}

    def extract_imports(params: dict, ctx: ExecutionContext) -> dict:
        path = _safe_join(ctx.repo_path, params["path"])
        content = path.read_text(encoding="utf-8", errors="ignore")
        imports = re.findall(r"^(?:from|import)\s+([\w.]+)", content, re.MULTILINE)
        return {"file": str(path), "imports": imports, "count": len(imports)}

    def find_entry_points(params: dict, ctx: ExecutionContext) -> dict:
        entry_points = []
        for name in ("main.py", "__main__.py", "app.py", "run.py"):
            p = ctx.repo_path / name
            if p.exists():
                entry_points.append(str(p.relative_to(ctx.repo_path)))
        for f in ctx.repo_path.rglob("*.py"):
            if ".git" in f.parts:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            if 'if __name__ == "__main__"' in text:
                rel = str(f.relative_to(ctx.repo_path))
                if rel not in entry_points:
                    entry_points.append(rel)
        return {"entry_points": entry_points, "count": len(entry_points)}

    def copy_file(params: dict, ctx: ExecutionContext) -> dict:
        src = _safe_join(ctx.repo_path, params["source"])
        dst = _safe_join(ctx.repo_path, params["dest"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return {"source": str(src), "dest": str(dst), "copied": True}

    # ── Tool registration ────────────────────────────────────────────────────

    tools.append(
        ToolDefinition(
            "clone_repo", "repo_tools", "Clone a GitHub repository",
            _schema({"url": {"type": "string"}, "dest": {"type": "string"}}, ["url"]),
            _out({"cloned": {"type": "boolean"}, "path": {"type": "string"}}),
            "ToolError", clone_repo,
        )
    )

    tools.append(
        ToolDefinition(
            "list_files", "repo_tools", "List files in repository",
            _schema({"path": {"type": "string"}, "pattern": {"type": "string"}}, []),
            _out({"files": {"type": "array"}, "count": {"type": "integer"}}),
            "ToolError", list_files,
        )
    )

    tools.append(
        ToolDefinition(
            "read_file", "repo_tools", "Read file contents",
            _schema({"path": {"type": "string"}}, ["path"]),
            _out({"content": {"type": "string"}, "lines": {"type": "integer"}}),
            "ToolError", read_file,
        )
    )

    tools.append(
        ToolDefinition(
            "write_file", "repo_tools", "Write content to a file",
            _schema({"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
            _out({"written": {"type": "boolean"}}),
            "ToolError", write_file,
        )
    )

    tools.append(
        ToolDefinition(
            "edit_file", "repo_tools", "Deterministic exact-match file editing",
            _schema({"path": {"type": "string"}, "oldText": {"type": "string"}, "newText": {"type": "string"}},
                    ["path", "oldText", "newText"]),
            _out({"success": {"type": "boolean"}}),
            "ToolError", edit_file,
        )
    )

    tools.append(
        ToolDefinition(
            "search_code", "repo_tools", "Search code for pattern",
            _schema({"query": {"type": "string"}, "regex": {"type": "boolean"}}, ["query"]),
            _out({"matches": {"type": "array"}, "count": {"type": "integer"}}),
            "ToolError", search_code,
        )
    )

    tools.append(
        ToolDefinition(
            "git_diff", "repo_tools", "Get git diff for repository",
            _schema({"staged": {"type": "boolean"}, "path": {"type": "string"}}, []),
            _out({"diff": {"type": "string"}, "has_changes": {"type": "boolean"}}),
            "ToolError", git_diff,
        )
    )

    tools.append(
        ToolDefinition(
            "create_branch", "repo_tools", "Create and checkout a git branch",
            _schema({"name": {"type": "string"}}, ["name"]),
            _out({"branch": {"type": "string"}, "created": {"type": "boolean"}}),
            "ToolError", create_branch,
        )
    )

    tools.append(
        ToolDefinition(
            "get_repo_metadata", "repo_tools", "Collect repository metadata",
            _schema({}, []), _out({"python_files": {"type": "integer"}}), "ToolError", get_repo_metadata,
        )
    )

    tools.append(
        ToolDefinition(
            "count_lines", "repo_tools", "Count lines in file or directory",
            _schema({"path": {"type": "string"}}, []),
            _out({"lines": {"type": "integer"}}), "ToolError", count_lines,
        )
    )

    tools.append(
        ToolDefinition(
            "file_exists", "repo_tools", "Check if file exists",
            _schema({"path": {"type": "string"}}, ["path"]),
            _out({"exists": {"type": "boolean"}}), "ToolError", file_exists,
        )
    )

    tools.append(
        ToolDefinition(
            "get_git_status", "repo_tools", "Get git working tree status",
            _schema({}, []), _out({"dirty": {"type": "boolean"}}), "ToolError", get_git_status,
        )
    )

    tools.append(
        ToolDefinition(
            "list_branches", "repo_tools", "List git branches",
            _schema({}, []), _out({"branches": {"type": "array"}}), "ToolError", list_branches,
        )
    )

    tools.append(
        ToolDefinition(
            "extract_imports", "repo_tools", "Extract import statements from a file",
            _schema({"path": {"type": "string"}}, ["path"]),
            _out({"imports": {"type": "array"}}), "ToolError", extract_imports,
        )
    )

    tools.append(
        ToolDefinition(
            "find_entry_points", "repo_tools", "Find Python entry point files",
            _schema({}, []), _out({"entry_points": {"type": "array"}}), "ToolError", find_entry_points,
        )
    )

    tools.append(
        ToolDefinition(
            "copy_file", "repo_tools", "Copy a file within the repository",
            _schema({"source": {"type": "string"}, "dest": {"type": "string"}}, ["source", "dest"]),
            _out({"copied": {"type": "boolean"}}), "ToolError", copy_file,
        )
    )

    return tools