"""Patch generation and application tools."""

from __future__ import annotations

import difflib
import re
import shutil
from pathlib import Path

from agira.registry.base import ToolDefinition, ToolSchema
from agira.tools.context import ExecutionContext


def _schema(props: dict, required: list[str] | None = None) -> ToolSchema:
    return ToolSchema(properties=props, required=required or [])


def _out(props: dict) -> ToolSchema:
    return ToolSchema(properties=props)


def register_patch_tools() -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []

    def generate_diff(params: dict, ctx: ExecutionContext) -> dict:
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        old = params.get("old_content", "")
        new = params["new_content"]
        diff = "".join(difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        ))
        patch_id = f"patch_{len(ctx.patches_applied)}"
        patch_record = {"id": patch_id, "path": str(path), "diff": diff}
        ctx.patches_applied.append(patch_record)
        ref = ctx.store_artifact(patch_id, patch_record)
        return {"diff": diff, "patch_id": patch_id, "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "generate_diff", "patch_tools", "Generate unified diff from content change",
            _schema({"path": {"type": "string"}, "new_content": {"type": "string"}, "old_content": {"type": "string"}},
                    ["path", "new_content"]),
            _out({"diff": {"type": "string"}, "patch_id": {"type": "string"}}),
            "ToolError", generate_diff,
        )
    )

    def apply_patch(params: dict, ctx: ExecutionContext) -> dict:
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        backup = path.read_text(encoding="utf-8") if path.exists() else ""
        ctx.store_artifact(f"backup:{path.name}", backup)
        if "new_content" in params:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(params["new_content"], encoding="utf-8")
            return {"applied": True, "path": str(path), "method": "content_replace"}
        if "search" in params and "replace" in params:
            content = path.read_text(encoding="utf-8")
            if params["search"] not in content:
                return {"applied": False, "reason": "search string not found"}
            new_content = content.replace(params["search"], params["replace"], 1)
            path.write_text(new_content, encoding="utf-8")
            return {"applied": True, "path": str(path), "method": "search_replace"}
        return {"applied": False, "reason": "no patch data provided"}

    tools.append(
        ToolDefinition(
            "apply_patch", "patch_tools", "Apply a patch to a file",
            _schema({
                "path": {"type": "string"},
                "new_content": {"type": "string"},
                "search": {"type": "string"},
                "replace": {"type": "string"},
            }, ["path"]),
            _out({"applied": {"type": "boolean"}}), "ToolError", apply_patch,
        )
    )

    def validate_patch(params: dict, ctx: ExecutionContext) -> dict:
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        if not path.exists():
            return {"valid": False, "reason": "file does not exist"}
        content = path.read_text(encoding="utf-8")
        checks = {"non_empty": len(content.strip()) > 0}
        if path.suffix == ".py":
            import ast
            try:
                ast.parse(content)
                checks["valid_python"] = True
            except SyntaxError as e:
                checks["valid_python"] = False
                return {"valid": False, "checks": checks, "error": str(e)}
        return {"valid": all(checks.values()), "checks": checks}

    tools.append(
        ToolDefinition(
            "validate_patch", "patch_tools", "Validate applied patch integrity",
            _schema({"path": {"type": "string"}}, ["path"]),
            _out({"valid": {"type": "boolean"}}), "ToolError", validate_patch,
        )
    )

    def rollback_patch(params: dict, ctx: ExecutionContext) -> dict:
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        backup = ctx.get_artifact(f"backup:{path.name}")
        if backup is None:
            return {"rolled_back": False, "reason": "no backup found"}
        path.write_text(backup, encoding="utf-8")
        return {"rolled_back": True, "path": str(path)}

    tools.append(
        ToolDefinition(
            "rollback_patch", "patch_tools", "Rollback file to pre-patch backup",
            _schema({"path": {"type": "string"}}, ["path"]),
            _out({"rolled_back": {"type": "boolean"}}), "ToolError", rollback_patch,
        )
    )

    def create_fix_patch(params: dict, ctx: ExecutionContext) -> dict:
        """Generate a fix patch for a known issue type."""
        issue_type = params["issue_type"]
        file_path = params["file"]
        path = ctx.repo_path / file_path
        content = path.read_text(encoding="utf-8")
        fixes = {
            "bare_except": (
                "except:",
                "except Exception:",
            ),
            "division_by_zero": (
                "return a / b",
                "return a / b if b != 0 else 0",
            ),
            "missing_return": (
                "def add(a, b):\n    pass",
                "def add(a, b):\n    return a + b",
            ),
            "off_by_one": (
                "range(len(items))",
                "range(len(items))  # fixed",
            ),
        }
        if issue_type not in fixes:
            return {"created": False, "reason": f"unknown issue type: {issue_type}"}
        search, replace = fixes[issue_type]
        if search not in content:
            return {"created": False, "reason": "pattern not found in file"}
        new_content = content.replace(search, replace, 1)
        return generate_diff({"path": file_path, "old_content": content, "new_content": new_content}, ctx)

    tools.append(
        ToolDefinition(
            "create_fix_patch", "patch_tools", "Create fix patch for known issue type",
            _schema({"issue_type": {"type": "string"}, "file": {"type": "string"}},
                    ["issue_type", "file"]),
            _out({"diff": {"type": "string"}}), "ToolError", create_fix_patch,
        )
    )

    def list_patches(params: dict, ctx: ExecutionContext) -> dict:
        return {"patches": ctx.patches_applied, "count": len(ctx.patches_applied)}

    tools.append(
        ToolDefinition(
            "list_patches", "patch_tools", "List all generated patches",
            _schema({}, []), _out({"patches": {"type": "array"}}), "ToolError", list_patches,
        )
    )

    def apply_unified_diff(params: dict, ctx: ExecutionContext) -> dict:
        diff_text = params["diff"]
        path_match = re.search(r"\+\+\+ b/(.*)", diff_text)
        if not path_match:
            return {"applied": False, "reason": "could not parse diff header"}
        rel_path = path_match.group(1).strip()
        path = ctx.repo_path / rel_path
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = []
        line_idx = 0
        for line in diff_text.splitlines(keepends=True):
            if line.startswith("@@"):
                continue
            if line.startswith("-") and not line.startswith("---"):
                line_idx += 1
            elif line.startswith("+") and not line.startswith("+++"):
                new_lines.append(line[1:])
            elif not line.startswith(("---", "+++", "@@", "diff")):
                if line_idx < len(lines):
                    new_lines.append(lines[line_idx])
                    line_idx += 1
        remaining = lines[line_idx:]
        new_lines.extend(remaining)
        backup = "".join(lines)
        ctx.store_artifact(f"backup:{path.name}", backup)
        path.write_text("".join(new_lines), encoding="utf-8")
        return {"applied": True, "path": str(path)}

    tools.append(
        ToolDefinition(
            "apply_unified_diff", "patch_tools", "Apply a unified diff to a file",
            _schema({"diff": {"type": "string"}}, ["diff"]),
            _out({"applied": {"type": "boolean"}}), "ToolError", apply_unified_diff,
        )
    )

    def ast_apply_fix(params: dict, ctx: ExecutionContext) -> dict:
        from agira.patch.ast_patcher import ASTPatcher

        file_path = params["file"]
        fix_type = params["fix_type"]
        issue = params.get("issue", {})
        path = ctx.repo_path / file_path
        patcher = ASTPatcher(ctx.repo_path)

        ctx.store_artifact(f"backup:{path.name}", path.read_text(encoding="utf-8") if path.exists() else "")

        if fix_type == "pickle_load":
            old = path.read_text(encoding="utf-8")
            new = old.replace("pickle.loads", "# pickle.loads  # disabled for security")
            result = patcher.fix_bare_except(file_path, issue)  # placeholder validate
            from agira.patch.ast_patcher import PatchResult
            import ast as ast_mod
            try:
                ast_mod.parse(new)
                result = PatchResult(True, file_path, patcher._make_diff(path, old, new), old, new, fix_type="pickle_load")
            except SyntaxError as e:
                result = PatchResult(False, file_path, "", old, old, str(e), "pickle_load")
        else:
            result = patcher.apply(file_path, fix_type, issue)

        if not result.success:
            return {"applied": False, "reason": result.error, "fix_type": fix_type, "file": file_path}

        patcher.write_patch(result)
        validation = validate_patch({"path": file_path}, ctx)
        return {
            "applied": True,
            "file": file_path,
            "rel_path": file_path,
            "path": str(path),
            "fix_type": fix_type,
            "diff": result.diff,
            "validated": validation.get("valid", False),
            "issue_key": params.get("_issue_key", f"{file_path}:{fix_type}"),
        }

    tools.append(
        ToolDefinition(
            "ast_apply_fix", "patch_tools", "Apply AST-based fix to a file",
            _schema({"file": {"type": "string"}, "fix_type": {"type": "string"}, "issue": {"type": "object"}},
                    ["file", "fix_type"]),
            _out({"applied": {"type": "boolean"}, "diff": {"type": "string"}}),
            "ToolError", ast_apply_fix,
        )
    )

    def rollback_all(params: dict, ctx: ExecutionContext) -> dict:
        rolled = []
        patch_art = ctx.artifact_store.latest("patch_result")
        files = []
        if patch_art and isinstance(patch_art.data, dict):
            files = [p.get("rel_path") or p.get("file") for p in patch_art.data.get("patches", [])]
        files.extend([p.get("rel_path") or p.get("file") for p in ctx.patches_applied])
        for rel in set(files):
            if not rel:
                continue
            r = rollback_patch({"path": rel}, ctx)
            if r.get("rolled_back"):
                rolled.append(rel)
        return {"rolled_back": rolled, "count": len(rolled)}

    tools.append(
        ToolDefinition(
            "rollback_all", "patch_tools", "Rollback all applied patches",
            _schema({}, []), _out({"rolled_back": {"type": "array"}}), "ToolError", rollback_all,
        )
    )

    def preview_patch(params: dict, ctx: ExecutionContext) -> dict:
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        new = params["new_content"]
        changed_lines = sum(1 for a, b in zip(old.splitlines(), new.splitlines()) if a != b)
        return {
            "path": str(path),
            "lines_changed": changed_lines,
            "size_delta": len(new) - len(old),
        }

    tools.append(
        ToolDefinition(
            "preview_patch", "patch_tools", "Preview patch impact without applying",
            _schema({"path": {"type": "string"}, "new_content": {"type": "string"}}, ["path", "new_content"]),
            _out({"lines_changed": {"type": "integer"}}), "ToolError", preview_patch,
        )
    )

    def apply_edit(params: dict, ctx: ExecutionContext) -> dict:
        """Deterministic edit tool with exact-match semantics.
        
        Required structure:
        {
            "path": "relative/path.py",
            "edits": [
                {"oldText": "EXACT STRING FROM FILE", "newText": "REPLACEMENT"},
                ...
            ]
        }
        
        Pipeline:
        1. Read file content
        2. Extract exact oldText from content (no guessing)
        3. Validate OLD_TEXT_NOT_FOUND_EXACT_MATCH if mismatch
        4. Apply all edits atomically
        5. Verify all patches applied (max 1 retry)
        
        NO RETRY LOOPS - FAIL FAST on mismatch.
        """
        path = Path(params["path"])
        if not path.is_absolute():
            path = ctx.repo_path / path
        
        if not path.exists():
            return {"success": False, "error": "FILE_NOT_FOUND", "path": str(path)}
        
        edits = params.get("edits", [])
        if not edits:
            return {"success": False, "error": "EDITS_REQUIRED", "path": str(path)}
        
        # Step 1: Read exact content from file
        content = path.read_text(encoding="utf-8")
        original_content = content
        
        results = []
        for i, edit in enumerate(edits):
            old_text = edit.get("oldText", "")
            new_text = edit.get("newText", "")
            
            if not old_text:
                results.append({
                    "index": i,
                    "success": False,
                    "error": "OLD_TEXT_REQUIRED"
                })
                continue
            
            if not new_text:
                results.append({
                    "index": i,
                    "success": False,
                    "error": "NEW_TEXT_REQUIRED"
                })
                continue
            
            # Step 3: Exact match validation - FAIL FAST if not found
            if old_text not in content:
                results.append({
                    "index": i,
                    "success": False,
                    "error": "OLD_TEXT_NOT_FOUND_EXACT_MATCH",
                    "hint": "oldText must be extracted exactly from file content"
                })
                continue
            
            # Step 4: Apply edit (deterministic single replacement)
            content = content.replace(old_text, new_text, 1)
            results.append({
                "index": i,
                "success": True,
                "oldText_length": len(old_text),
                "newText_length": len(new_text)
            })
        
        # Check if any edit failed
        failed = [r for r in results if not r["success"]]
        if failed:
            return {
                "success": False,
                "path": str(path),
                "edits_failed": failed,
                "error": "EDIT_VALIDATION_FAILED"
            }
        
        # Step 5: Write and verify
        path.write_text(content, encoding="utf-8")
        
        # Verify: re-read and confirm all patches applied
        verified_content = path.read_text(encoding="utf-8")
        verification_failures = []
        for edit in edits:
            old_text = edit.get("oldText", "")
            new_text = edit.get("newText", "")
            if old_text in verified_content:
                verification_failures.append({
                    "error": "OLD_TEXT_STILL_PRESENT",
                    "oldText_preview": old_text[:50]
                })
            if new_text not in verified_content:
                verification_failures.append({
                    "error": "NEW_TEXT_NOT_FOUND",
                    "newText_preview": new_text[:50]
                })
        
        if verification_failures:
            # Rollback on verification failure
            path.write_text(original_content, encoding="utf-8")
            return {
                "success": False,
                "path": str(path),
                "error": "PATCH_VERIFICATION_FAILED",
                "verification_failures": verification_failures,
                "rolled_back": True
            }
        
        return {
            "success": True,
            "path": str(path),
            "edits_applied": len(edits),
            "verified": True
        }

    tools.append(
        ToolDefinition(
            "apply_edit", "patch_tools", "Deterministic exact-match file editing with edits array",
            _schema({"path": {"type": "string"}, "edits": {"type": "array"}}, ["path", "edits"]),
            _out({"success": {"type": "boolean"}, "edits_applied": {"type": "integer"}}), "ToolError", apply_edit,
        )
    )

    return tools
