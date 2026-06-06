"""Repository manipulation tools."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agira.registry.base import ToolDefinition, ToolSchema
from agira.tools.context import ExecutionContext


def _schema(props: dict, required: list[str] | None = None) -> ToolSchema:
    return ToolSchema(properties=props, required=required or [])


def _out(props: dict) -> ToolSchema:
    return ToolSchema(properties=props)


def register_repo_tools() -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []

    def clone_repo(params: dict, ctx: ExecutionContext) -> dict:
        ctx.rate_limiter.acquire()
        url = params["url"]
        dest = Path(params.get("dest", ctx.repo_path))
        if dest.exists() and list(dest.iterdir()):
            return {"cloned": False, "path": str(dest), "reason": "already_exists"}
        dest.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True,
            text=True,
        )
        return {
            "cloned": result.returncode == 0,
            "path": str(dest),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    tools.append(
        ToolDefinition(
            "clone_repo", "repo_tools", "Clone a GitHub repository",
            _schema({"url": {"type": "string"}, "dest": {"type": "string"}}, ["url"]),
            _out({"cloned": {"type": "boolean"}, "path": {"type": "string"}}),
            "ToolError", clone_repo,
        )
    )

    def list_files(params: dict, ctx: ExecutionContext) -> dict:
        root = Path(params.get("path", ctx.repo_path))
        pattern = params.get("pattern", "**/*")
        max_files = params.get("max_files", 500)
        files = []
        for p in sorted(root.glob(pattern)):
            if p.is_file() and ".git" not in p.parts:
                files.append(str(p.relative_to(root)))
                if len(files) >= max_files:
                    break
        return {"files": files, "count": len(files), "root": str(root)}

    tools.append(
        ToolDefinition(
            "list_files", "repo_tools", "List files in repository",
            _schema({"path": {"type": "string"}, "pattern": {"type": "string"}}, []),
            _out({"files": {"type": "array"}, "count": {"type": "integer"}}),
            "ToolError", list_files,
        )
    )

    def read_file(params: dict, ctx: ExecutionContext) -> dict:
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        content = path.read_text(encoding="utf-8", errors="replace")
        return {"path": str(path), "content": content, "lines": content.count("\n") + 1}

    tools.append(
        ToolDefinition(
            "read_file", "repo_tools", "Read file contents",
            _schema({"path": {"type": "string"}}, ["path"]),
            _out({"content": {"type": "string"}, "lines": {"type": "integer"}}),
            "ToolError", read_file,
        )
    )

    def write_file(params: dict, ctx: ExecutionContext) -> dict:
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(params["content"], encoding="utf-8")
        return {"path": str(path), "written": True, "bytes": len(params["content"])}

    def edit_file(params: dict, ctx: ExecutionContext) -> dict:
        """Deterministic exact-match file editing.
        
        Pipeline:
        1. Read file content
        2. Extract exact oldText from content (no guessing)
        3. Validate oldText exists exactly in file
        4. Apply replacement
        5. Verify patch was applied
        
        Fails fast on mismatch - no reasoning loops.
        """
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        
        if not path.exists():
            return {"success": False, "error": "FILE_NOT_FOUND", "path": str(path)}
        
        # Step 1: Read exact content from file
        content = path.read_text(encoding="utf-8")
        
        # Step 2: Get exact oldText (must be extracted from file, not constructed)
        old_text = params.get("oldText")
        new_text = params.get("newText")
        
        if not old_text:
            return {"success": False, "error": "OLD_TEXT_REQUIRED", "path": str(path)}
        if not new_text:
            return {"success": False, "error": "NEW_TEXT_REQUIRED", "path": str(path)}
        
        # Step 3: Exact match validation - FAIL FAST if not found
        if old_text not in content:
            return {
                "success": False, 
                "error": "OLD_TEXT_NOT_FOUND_EXACT_MATCH",
                "path": str(path),
                "hint": "oldText must be extracted exactly from file content - no partial matches"
            }
        
        # Step 4: Apply edit (deterministic string replacement)
        new_content = content.replace(old_text, new_text, 1)  # 1 = single occurrence
        
        # Step 5: Write and verify
        path.write_text(new_content, encoding="utf-8")
        
        # Verify: re-read and confirm patch applied
        verified_content = path.read_text(encoding="utf-8")
        if old_text in verified_content:
            return {
                "success": False,
                "error": "PATCH_VERIFICATION_FAILED",
                "path": str(path),
                "reason": "oldText still present after edit - patch did not apply"
            }
        if new_text not in verified_content:
            return {
                "success": False,
                "error": "PATCH_VERIFICATION_FAILED",
                "path": str(path),
                "reason": "newText not found after edit - patch did not apply"
            }
        
        return {
            "success": True,
            "path": str(path),
            "oldText_length": len(old_text),
            "newText_length": len(new_text),
            "verified": True
        }

    tools.append(
        ToolDefinition(
            "write_file", "repo_tools", "Write content to a file",
            _schema({"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
            _out({"written": {"type": "boolean"}}),
            "ToolError", write_file,
        )
    )

    def search_code(params: dict, ctx: ExecutionContext) -> dict:
        query = params["query"]
        root = Path(params.get("path", ctx.repo_path))
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

    tools.append(
        ToolDefinition(
            "search_code", "repo_tools", "Search code for pattern",
            _schema({"query": {"type": "string"}, "regex": {"type": "boolean"}}, ["query"]),
            _out({"matches": {"type": "array"}, "count": {"type": "integer"}}),
            "ToolError", search_code,
        )
    )

    def git_diff(params: dict, ctx: ExecutionContext) -> dict:
        args = ["git", "-C", str(ctx.repo_path), "diff"]
        if params.get("staged"):
            args.append("--staged")
        if params.get("path"):
            args.append("--")
            args.append(params["path"])
        result = subprocess.run(args, capture_output=True, text=True)
        return {"diff": result.stdout, "has_changes": bool(result.stdout.strip())}

    tools.append(
        ToolDefinition(
            "git_diff", "repo_tools", "Get git diff for repository",
            _schema({"staged": {"type": "boolean"}, "path": {"type": "string"}}, []),
            _out({"diff": {"type": "string"}, "has_changes": {"type": "boolean"}}),
            "ToolError", git_diff,
        )
    )

    def create_branch(params: dict, ctx: ExecutionContext) -> dict:
        name = params["name"]
        result = subprocess.run(
            ["git", "-C", str(ctx.repo_path), "checkout", "-b", name],
            capture_output=True, text=True,
        )
        return {"branch": name, "created": result.returncode == 0, "stderr": result.stderr}

    tools.append(
        ToolDefinition(
            "create_branch", "repo_tools", "Create and checkout a git branch",
            _schema({"name": {"type": "string"}}, ["name"]),
            _out({"branch": {"type": "string"}, "created": {"type": "boolean"}}),
            "ToolError", create_branch,
        )
    )

    def get_repo_metadata(params: dict, ctx: ExecutionContext) -> dict:
        root = ctx.repo_path
        py_files = list(root.rglob("*.py"))
        total_lines = 0
        for f in py_files:
            if ".git" not in f.parts:
                total_lines += f.read_text(encoding="utf-8", errors="ignore").count("\n")
        has_git = (root / ".git").exists()
        return {
            "path": str(root),
            "python_files": len(py_files),
            "total_lines": total_lines,
            "has_git": has_git,
            "name": root.name,
        }

    tools.append(
        ToolDefinition(
            "get_repo_metadata", "repo_tools", "Collect repository metadata",
            _schema({}, []), _out({"python_files": {"type": "integer"}}), "ToolError", get_repo_metadata,
        )
    )

    def count_lines(params: dict, ctx: ExecutionContext) -> dict:
        path = Path(params.get("path", "."))
        if not path.is_absolute():
            path = ctx.repo_path / path
        if path.is_file():
            lines = path.read_text(encoding="utf-8", errors="ignore").count("\n") + 1
            return {"path": str(path), "lines": lines}
        total = 0
        for f in path.rglob("*"):
            if f.is_file():
                total += f.read_text(encoding="utf-8", errors="ignore").count("\n") + 1
        return {"path": str(path), "lines": total}

    tools.append(
        ToolDefinition(
            "count_lines", "repo_tools", "Count lines in file or directory",
            _schema({"path": {"type": "string"}}, []),
            _out({"lines": {"type": "integer"}}), "ToolError", count_lines,
        )
    )

    def file_exists(params: dict, ctx: ExecutionContext) -> dict:
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        return {"path": str(path), "exists": path.exists(), "is_file": path.is_file()}

    tools.append(
        ToolDefinition(
            "file_exists", "repo_tools", "Check if file exists",
            _schema({"path": {"type": "string"}}, ["path"]),
            _out({"exists": {"type": "boolean"}}), "ToolError", file_exists,
        )
    )

    def get_git_status(params: dict, ctx: ExecutionContext) -> dict:
        result = subprocess.run(
            ["git", "-C", str(ctx.repo_path), "status", "--porcelain"],
            capture_output=True, text=True,
        )
        lines = [l for l in result.stdout.strip().split("\n") if l]
        return {"status_lines": lines, "dirty": len(lines) > 0, "change_count": len(lines)}

    tools.append(
        ToolDefinition(
            "get_git_status", "repo_tools", "Get git working tree status",
            _schema({}, []), _out({"dirty": {"type": "boolean"}}), "ToolError", get_git_status,
        )
    )

    def list_branches(params: dict, ctx: ExecutionContext) -> dict:
        result = subprocess.run(
            ["git", "-C", str(ctx.repo_path), "branch", "--list"],
            capture_output=True, text=True,
        )
        branches = [b.strip().lstrip("* ") for b in result.stdout.strip().split("\n") if b.strip()]
        return {"branches": branches, "count": len(branches)}

    tools.append(
        ToolDefinition(
            "list_branches", "repo_tools", "List git branches",
            _schema({}, []), _out({"branches": {"type": "array"}}), "ToolError", list_branches,
        )
    )

    def extract_imports(params: dict, ctx: ExecutionContext) -> dict:
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        content = path.read_text(encoding="utf-8", errors="ignore")
        imports = re.findall(r"^(?:from|import)\s+([\w.]+)", content, re.MULTILINE)
        return {"file": str(path), "imports": imports, "count": len(imports)}

    tools.append(
        ToolDefinition(
            "extract_imports", "repo_tools", "Extract import statements from a file",
            _schema({"path": {"type": "string"}}, ["path"]),
            _out({"imports": {"type": "array"}}), "ToolError", extract_imports,
        )
    )

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

    tools.append(
        ToolDefinition(
            "find_entry_points", "repo_tools", "Find Python entry point files",
            _schema({}, []), _out({"entry_points": {"type": "array"}}), "ToolError", find_entry_points,
        )
    )

    def copy_file(params: dict, ctx: ExecutionContext) -> dict:
        src = Path(params["source"])
        dst = Path(params["dest"])
        if not src.is_absolute():
            src = ctx.repo_path / src
        if not dst.is_absolute():
            dst = ctx.repo_path / dst
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return {"source": str(src), "dest": str(dst), "copied": True}

    tools.append(
        ToolDefinition(
            "copy_file", "repo_tools", "Copy a file within the repository",
            _schema({"source": {"type": "string"}, "dest": {"type": "string"}}, ["source", "dest"]),
            _out({"copied": {"type": "boolean"}}), "ToolError", copy_file,
        )
    )

    tools.append(
        ToolDefinition(
            "edit_file", "repo_tools", "Deterministic exact-match file editing",
            _schema({"path": {"type": "string"}, "oldText": {"type": "string"}, "newText": {"type": "string"}}, ["path", "oldText", "newText"]),
            _out({"success": {"type": "boolean"}}), "ToolError", edit_file,
        )
    )

    return tools
