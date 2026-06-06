"""Report generation tools."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from agira.registry.base import ToolDefinition, ToolSchema
from agira.tools.context import ExecutionContext


def _schema(props: dict, required: list[str] | None = None) -> ToolSchema:
    return ToolSchema(properties=props, required=required or [])


def _out(props: dict) -> ToolSchema:
    return ToolSchema(properties=props)


def register_report_tools() -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []

    def _collect_report_data(ctx: ExecutionContext) -> dict[str, Any]:
        store = ctx.artifact_store
        issues_art = store.latest("issues")
        issues = []
        if issues_art:
            d = issues_art.data
            issues = d.get("issues", d) if isinstance(d, dict) else (d if isinstance(d, list) else [])
        merged_art = store.latest("merged_findings")
        if merged_art and isinstance(merged_art.data, dict):
            issues = merged_art.data.get("merged", {}).get("issues", issues)
        validation_art = store.latest("validation_result")
        validation = validation_art.data if validation_art else {}
        return {
            "repo": str(ctx.repo_path),
            "trace_id": ctx.trace_id,
            "tool_calls": ctx.tool_call_count,
            "issues": issues,
            "patches": ctx.patches_applied,
            "validation": validation,
            "dependency_graph": store.latest("dependency_graph"),
            "test_results": store.latest("test_results"),
            "tool_coverage": store.latest("tool_coverage"),
        }

    def generate_markdown_report(params: dict, ctx: ExecutionContext) -> dict:
        data = _collect_report_data(ctx)
        lines = [
            f"# AGIRA Report: {data['repo']}",
            f"\n**Generated:** {datetime.now(timezone.utc).isoformat()}",
            f"**Trace ID:** {data['trace_id']}",
            f"**Tool Calls:** {data['tool_calls']}",
            "\n## Issues Detected\n",
        ]
        issues = data["issues"]
        if issues:
            for issue in issues[:20]:
                if isinstance(issue, dict):
                    lines.append(f"- **{issue.get('pattern', issue.get('type', 'issue'))}** "
                                 f"in `{issue.get('file', 'unknown')}`: "
                                 f"{issue.get('description', '')}")
                else:
                    lines.append(f"- {issue}")
        else:
            lines.append("No issues detected.")
        lines.append("\n## Patches Applied\n")
        if data["patches"]:
            for p in data["patches"]:
                lines.append(f"- Patch `{p.get('id', '?')}` on `{p.get('path', '?')}`")
        else:
            lines.append("No patches applied.")
        lines.append("\n## Test Results\n")
        tr = data.get("test_results")
        if tr:
            tr_data = tr.data if hasattr(tr, "data") else tr
            if isinstance(tr_data, dict) and "data" in tr_data:
                tr_data = tr_data["data"]
            lines.append(f"- Success: **{tr_data.get('success', 'N/A') if isinstance(tr_data, dict) else 'N/A'}**")
            if isinstance(tr_data, dict):
                lines.append(f"- Return code: {tr_data.get('returncode', 'N/A')}")
        else:
            lines.append("Tests not run.")
        report = "\n".join(lines)
        ref = ctx.store_artifact("markdown_report", report)
        return {"report": report, "format": "markdown", "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "generate_markdown_report", "report_tools", "Generate markdown analysis report",
            _schema({}, []), _out({"report": {"type": "string"}}), "ToolError", generate_markdown_report,
        )
    )

    def generate_json_report(params: dict, ctx: ExecutionContext) -> dict:
        data = _collect_report_data(ctx)
        health = repo_health_score({}, ctx)
        report = {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo": data["repo"],
            "trace_id": data["trace_id"],
            "tool_calls": data["tool_calls"],
            "health_score": health["score"],
            "issues": data["issues"],
            "patches": data["patches"],
            "validation": data.get("validation"),
            "test_results": data.get("test_results"),
            "tool_coverage": data.get("tool_coverage"),
        }
        ref = ctx.store_artifact("json_report", report)
        return {"report": report, "format": "json", "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "generate_json_report", "report_tools", "Generate JSON analysis report",
            _schema({}, []), _out({"report": {"type": "object"}}), "ToolError", generate_json_report,
        )
    )

    def repo_health_score(params: dict, ctx: ExecutionContext) -> dict:
        score = 100.0
        deductions = []
        issues = ctx.get_artifact("anti_patterns") or []
        vulns = ctx.get_artifact("vulnerabilities") or []
        syntax = ctx.get_artifact("syntax_errors") or []
        test_results = ctx.get_artifact("test_results")

        if issues:
            d = min(len(issues) * 5, 30)
            score -= d
            deductions.append({"reason": "anti_patterns", "points": d})
        if vulns:
            d = min(len(vulns) * 10, 30)
            score -= d
            deductions.append({"reason": "vulnerabilities", "points": d})
        if syntax:
            d = min(len(syntax) * 15, 40)
            score -= d
            deductions.append({"reason": "syntax_errors", "points": d})
        if test_results and not test_results.get("success"):
            score -= 20
            deductions.append({"reason": "test_failures", "points": 20})

        score = max(0.0, score)
        grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"
        result = {"score": round(score, 1), "grade": grade, "deductions": deductions}
        ctx.store_artifact("health_score", result)
        return result

    tools.append(
        ToolDefinition(
            "repo_health_score", "report_tools", "Compute repository health score",
            _schema({}, []), _out({"score": {"type": "number"}, "grade": {"type": "string"}}),
            "ToolError", repo_health_score,
        )
    )

    def generate_pr_summary(params: dict, ctx: ExecutionContext) -> dict:
        patches = ctx.patches_applied
        issues = ctx.state.get("merged_output", {}).get("issues", [])
        summary = {
            "title": f"AGIRA: Fix {len(issues)} issue(s) in {ctx.repo_path.name}",
            "body": (
                f"## Summary\n"
                f"Automated repair by AGIRA detected and fixed issues.\n\n"
                f"## Issues ({len(issues)})\n"
                + "\n".join(f"- {i.get('pattern', i.get('type', 'issue'))} in `{i.get('file', '?')}`"
                            for i in issues[:10])
                + f"\n\n## Patches ({len(patches)})\n"
                + "\n".join(f"- `{p.get('path', '?')}`" for p in patches)
            ),
            "files_changed": len(patches),
        }
        ref = ctx.store_artifact("pr_summary", summary)
        return {"summary": summary, "artifact_ref": ref}

    tools.append(
        ToolDefinition(
            "generate_pr_summary", "report_tools", "Generate PR-style summary",
            _schema({}, []), _out({"summary": {"type": "object"}}), "ToolError", generate_pr_summary,
        )
    )

    def export_report_file(params: dict, ctx: ExecutionContext) -> dict:
        fmt = params.get("format", "json")
        dest = params.get("dest", f"agira_report.{fmt}")
        if fmt == "json":
            report_data = generate_json_report({}, ctx)["report"]
            content = json.dumps(report_data, indent=2, default=str)
        else:
            content = generate_markdown_report({}, ctx)["report"]
        from pathlib import Path
        out_path = Path(dest)
        if not out_path.is_absolute():
            out_path = ctx.repo_path.parent / out_path
        out_path.write_text(content, encoding="utf-8")
        return {"path": str(out_path), "format": fmt, "written": True}

    tools.append(
        ToolDefinition(
            "export_report_file", "report_tools", "Export report to file",
            _schema({"format": {"type": "string"}, "dest": {"type": "string"}}, []),
            _out({"path": {"type": "string"}}), "ToolError", export_report_file,
        )
    )

    def generate_diff_summary(params: dict, ctx: ExecutionContext) -> dict:
        diffs = []
        for p in ctx.patches_applied:
            diffs.append({"patch_id": p.get("id"), "path": p.get("path"), "diff_lines": p.get("diff", "").count("\n")})
        return {"diffs": diffs, "total_patches": len(diffs)}

    tools.append(
        ToolDefinition(
            "generate_diff_summary", "report_tools", "Summarize all generated diffs",
            _schema({}, []), _out({"diffs": {"type": "array"}}), "ToolError", generate_diff_summary,
        )
    )

    return tools
