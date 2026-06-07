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


def _collect_repair_metrics(ctx: ExecutionContext) -> dict[str, Any]:
    """Collect repair-specific metrics and developer impact from context and artifacts.
    
    Tracks:
    - Issues Found: Total issues detected
    - Auto Fixable: Issues classified as AUTO_FIXABLE
    - Patch Attempts: Number of patch operations attempted
    - Successful Patches: Patches that were successfully applied
    - Failed Patches: Patches that failed validation
    - Validated Patches: Patches that passed all validations
    - Rollbacks: Number of rollback operations triggered
    - Repair Rate: Percentage of auto-fixable issues successfully repaired
    - Validation Rate: Percentage of patches that passed validation
    
    Developer Impact Metrics:
    - Time Saved: Estimated minutes saved by auto-fixing (using per-issue effort estimates)
    - Manual Fixes Avoided: Count of issues that would have required manual effort
    - Files Cleaned: Count of unique files that were fixed
    - Validation Success Rate: Percentage of patches that passed validation
    """
    # Import fixability utilities lazily to avoid circular imports
    from importlib import import_module
    fixability_module = import_module('agira.utils.fixability')
    Fixability = fixability_module.Fixability
    summarize_fixability = fixability_module.summarize_fixability
    AUTO_FIX_TIME_ESTIMATES = fixability_module.AUTO_FIX_TIME_ESTIMATES
    
    store = ctx.artifact_store
    
    # Collect issues
    issues_art = store.latest("issues")
    issues = []
    if issues_art:
        d = issues_art.data
        issues = d.get("issues", d) if isinstance(d, dict) else (d if isinstance(d, list) else [])
    merged_art = store.latest("merged_findings")
    if merged_art and isinstance(merged_art.data, dict):
        issues = merged_art.data.get("merged", {}).get("issues", issues)
    
    # Count issues by fixability and calculate time estimates
    issues_found = len(issues)
    auto_fixable = 0
    auto_fix_time_seconds = 0.0
    
    for issue in issues:
        if isinstance(issue, dict):
            fixability = issue.get("fixability", "")
            pattern = issue.get("pattern", "")
            if fixability == Fixability.AUTO_FIXABLE.value:
                auto_fixable += 1
                # Use per-issue time estimate, default to 30 seconds
                time_est = AUTO_FIX_TIME_ESTIMATES.get(pattern, 30.0)
                auto_fix_time_seconds += time_est
    
    # Collect patch information
    patches = ctx.patches_applied or []
    patch_attempts = len(patches)
    
    # Count successful/failed patches and files cleaned
    validation_art = store.latest("validation_result")
    validation_data = validation_art.data if validation_art else {}
    
    validated_patches = 0
    failed_patches = 0
    rollbacks = 0
    files_cleaned: set[str] = set()
    
    # Check patch results
    for p in patches:
        if p.get("validated"):
            validated_patches += 1
            # Track unique files that were successfully patched
            if p.get("path"):
                files_cleaned.add(str(p.get("path")))
        elif p.get("failed"):
            failed_patches += 1
    
    # Check validation artifact for detailed metrics
    if isinstance(validation_data, dict):
        validated_patches = validation_data.get("validated_patches", validated_patches)
        failed_patches = validation_data.get("failed_patches", failed_patches)
        rollbacks = validation_data.get("rollbacks", rollbacks)
    
    # Calculate rates
    repair_rate = (validated_patches / auto_fixable * 100) if auto_fixable > 0 else 0.0
    validation_rate = (validated_patches / patch_attempts * 100) if patch_attempts > 0 else 0.0
    
    # Developer impact metrics
    # Time saved: use the auto-fix time estimates from issues that were successfully fixed
    # We estimate based on validated patches (successful fixes)
    # Scale time saved proportionally: (validated_patches / auto_fixable) * total_auto_fix_time
    if auto_fixable > 0 and auto_fix_time_seconds > 0:
        fix_ratio = validated_patches / auto_fixable
        time_saved_seconds = auto_fix_time_seconds * fix_ratio
    else:
        time_saved_seconds = validated_patches * 30.0  # Default 30 sec per fix
    
    time_saved_minutes = round(time_saved_seconds / 60, 1)
    time_saved_hours = round(time_saved_minutes / 60, 1)
    
    # Manual fixes avoided = validated patches (since we fixed them automatically)
    manual_fixes_avoided = validated_patches
    
    # Files cleaned = unique files with successful patches
    files_cleaned_count = len(files_cleaned)
    
    return {
        "issues_found": issues_found,
        "auto_fixable": auto_fixable,
        "patch_attempts": patch_attempts,
        "successful_patches": validated_patches,
        "failed_patches": failed_patches,
        "validated_patches": validated_patches,
        "rollbacks": rollbacks,
        "repair_rate": round(repair_rate, 1),
        "validation_rate": round(validation_rate, 1),
        "fixability_summary": summarize_fixability(issues) if issues else {},
        # Developer impact metrics
        "time_saved_minutes": time_saved_minutes,
        "time_saved_hours": time_saved_hours,
        "manual_fixes_avoided": manual_fixes_avoided,
        "files_cleaned": files_cleaned_count,
        "validation_success_rate": round(validation_rate, 1),
    }


def _collect_developer_report(ctx: ExecutionContext, issues: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the developer-focused report from context and issues.
    
    Args:
        ctx: ExecutionContext with artifact store
        issues: Pre-classified list of issues (with fixability field)
    """
    from agira.utils.fixability import summarize_fixability
    
    store = ctx.artifact_store
    repair = _collect_repair_metrics(ctx)
    
    health_art = store.latest("health_score")
    health_score = 0
    health_grade = "N/A"
    if health_art and isinstance(health_art.data, dict):
        health_score = health_art.data.get("score", 0)
        health_grade = health_art.data.get("grade", "N/A")
    elif health_art:
        health_score = getattr(health_art.data, "score", 0)
        health_grade = getattr(health_art.data, "grade", "N/A")
    
    # Categorize issues
    pattern_to_category = {
        "division_by_zero": "reliability",
        "wrong_except": "reliability",
        "bare_except": "reliability",
        "mutable_default": "reliability",
        "syntax_error": "reliability",
        "hardcoded_secret": "security",
        "eval_usage": "security",
        "pickle_load": "security",
        "api_key": "security",
        "password": "security",
        "long_function": "maintainability",
        "circular_import": "maintainability",
        "unused_import": "code_hygiene",
        "duplicate_import": "code_hygiene",
        "print_debug": "code_hygiene",
        "trailing_whitespace": "code_hygiene",
        "missing_newline_eof": "code_hygiene",
        "todo_fixme": "code_hygiene",
    }
    
    categories: dict[str, list] = {
        "reliability": [], "security": [], "maintainability": [],
        "code_hygiene": [], "technical_debt": [],
    }
    
    for issue in issues:
        if isinstance(issue, dict):
            pattern = issue.get("pattern", "")
            cat = pattern_to_category.get(pattern, "technical_debt")
            categories[cat].append(issue)
    
    validated = repair.get("validated_patches", 0)
    time_saved_minutes = repair.get("time_saved_minutes", validated * 2)
    time_saved_hours = repair.get("time_saved_hours", round(time_saved_minutes / 60, 1))
    manual_fixes_avoided = repair.get("manual_fixes_avoided", validated)
    files_cleaned = repair.get("files_cleaned", 0)
    validation_success_rate = repair.get("validation_success_rate", 0.0)
    issues_found = repair.get("issues_found", len(issues))
    auto_fixable_count = repair.get("auto_fixable", 0)
    
    # Top risk files
    file_issue_count: dict[str, int] = {}
    for issue in issues:
        if isinstance(issue, dict):
            f = issue.get("file", "unknown")
            file_issue_count[f] = file_issue_count.get(f, 0) + 1
    top_risk_files = sorted(
        [{"file": f, "issue_count": c} for f, c in file_issue_count.items()],
        key=lambda x: -x["issue_count"]
    )[:5]
    
    return {
        "version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(ctx.repo_path),
        "trace_id": ctx.trace_id,
        "repository_health": {
            "health_score": health_score,
            "health_grade": health_grade,
            "issues_found": issues_found,
            "auto_fixable_count": auto_fixable_count,
            "auto_fixable_percent": round(auto_fixable_count / max(issues_found, 1) * 100, 1),
        },
        "reliability": {"count": len(categories["reliability"]), "issues": categories["reliability"][:10]},
        "security": {"count": len(categories["security"]), "issues": categories["security"][:10]},
        "maintainability": {"count": len(categories["maintainability"]), "issues": categories["maintainability"][:10]},
        "code_hygiene": {"count": len(categories["code_hygiene"]), "issues": categories["code_hygiene"][:10]},
        "auto_fix_summary": {
            "fixes_applied": validated,
            "manual_fixes_avoided": manual_fixes_avoided,
            "files_cleaned": files_cleaned,
            "failed": repair.get("failed_patches", 0),
            "rolled_back": repair.get("rollbacks", 0),
            "validation_success_rate": validation_success_rate,
            "success_rate": repair.get("repair_rate", 0.0),
            "estimated_time_saved_minutes": time_saved_minutes,
            "estimated_time_saved_hours": time_saved_hours,
        },
        "remaining_issues": {
            "count": issues_found - validated,
            "issues": [i for i in issues if isinstance(i, dict) and i.get("fixability") != "AUTO_FIXABLE"][:20],
        },
        "technical_debt": {"count": len(categories["technical_debt"]), "issues": categories["technical_debt"][:10]},
        "top_risk_files": top_risk_files,
        "developer_value": {
            "time_saved_minutes": time_saved_minutes,
            "time_saved_hours": time_saved_hours,
            "manual_fixes_avoided": manual_fixes_avoided,
            "files_cleaned": files_cleaned,
            "validation_success_rate": validation_success_rate,
            "focus_remaining_minutes": (issues_found - validated) * 5,
            "focus_remaining_hours": round((issues_found - validated) * 5 / 60, 1),
        },
    }


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
            "repair_metrics": _collect_repair_metrics(ctx),
        }

    def generate_markdown_report(params: dict, ctx: ExecutionContext) -> dict:
        """Generate developer-focused markdown report."""
        data = _collect_report_data(ctx)
        repair = data.get("repair_metrics", {})
        issues = data.get("issues", [])
        
        # Classify issues by category for new sections
        reliability_issues = []
        security_issues = []
        maintainability_issues = []
        code_hygiene_issues = []
        technical_debt_issues = []
        
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            pattern = issue.get('pattern', '')
            fixability = issue.get('fixability', '')
            
            # Categorize by pattern type
            if pattern in ('division_by_zero', 'logic_bug', 'type_mismatch', 'bare_except'):
                reliability_issues.append(issue)
            elif pattern in ('eval_usage', 'hardcoded_secret', 'pickle_load', 'vulnerability'):
                security_issues.append(issue)
            elif pattern in ('dead_code', 'long_function', 'complexity', 'circular_import'):
                maintainability_issues.append(issue)
            elif pattern in ('wrong_except', 'print_debug', 'unused_import', 'duplicate_import', 
                            'trailing_whitespace', 'missing_newline_eof', 'todo_fixme'):
                code_hygiene_issues.append(issue)
            else:
                technical_debt_issues.append(issue)
        
        # Use developer impact metrics from repair_metrics
        auto_fixable = repair.get('auto_fixable', 0)
        validated = repair.get('validated_patches', 0)
        time_saved_minutes = repair.get('time_saved_minutes', validated * 2)
        time_saved_hours = repair.get('time_saved_hours', round(time_saved_minutes / 60, 1))
        manual_fixes_avoided = repair.get('manual_fixes_avoided', validated)
        files_cleaned = repair.get('files_cleaned', 0)
        validation_success_rate = repair.get('validation_success_rate', 0.0)
        
        # Top risk files (files with most issues)
        file_issue_count: dict[str, int] = {}
        for issue in issues:
            if isinstance(issue, dict):
                f = issue.get('file', 'unknown')
                file_issue_count[f] = file_issue_count.get(f, 0) + 1
        top_risk_files = sorted(file_issue_count.items(), key=lambda x: -x[1])[:5]
        
        lines = [
            f"# AGIRA Analysis Report\n",
            f"**Repository:** `{data['repo']}`",
            f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
            f"**Trace ID:** `{data['trace_id']}`",
            
            "\n---\n",
            f"\n## 1. Repository Health\n",
            f"- **Health Score:** {repair.get('health_score', {}).get('score', 'N/A')}",
            f"- **Issues Found:** {repair.get('issues_found', 0)}",
            f"- **Auto-Fixable:** {auto_fixable} ({auto_fixable/repair.get('issues_found', 1)*100:.0f}%)",
            
            f"\n## 2. Reliability\n",
            f"Issues that may cause runtime errors or unexpected behavior.\n",
        ]
        if reliability_issues:
            lines.append(f"**{len(reliability_issues)} issue(s) found**\n")
            for issue in reliability_issues[:5]:
                lines.append(f"- `{issue.get('file', '?')}`: {issue.get('pattern', 'issue')}")
            if len(reliability_issues) > 5:
                lines.append(f"- _...and {len(reliability_issues) - 5} more_")
        else:
            lines.append("✔ No reliability issues detected.\n")
        
        lines.extend([
            f"\n## 3. Security\n",
            f"Potential security vulnerabilities and hardcoded secrets.\n",
        ])
        if security_issues:
            lines.append(f"**{len(security_issues)} issue(s) found**\n")
            for issue in security_issues[:5]:
                lines.append(f"- `{issue.get('file', '?')}`: {issue.get('pattern', 'issue')}")
            if len(security_issues) > 5:
                lines.append(f"- _...and {len(security_issues) - 5} more_")
        else:
            lines.append("✔ No security issues detected.\n")
        
        lines.extend([
            f"\n## 4. Maintainability\n",
            f"Design and architecture concerns that affect long-term maintainability.\n",
        ])
        if maintainability_issues:
            lines.append(f"**{len(maintainability_issues)} issue(s) found**\n")
            for issue in maintainability_issues[:5]:
                lines.append(f"- `{issue.get('file', '?')}`: {issue.get('pattern', 'issue')}")
            if len(maintainability_issues) > 5:
                lines.append(f"- _...and {len(maintainability_issues) - 5} more_")
        else:
            lines.append("✔ No maintainability issues detected.\n")
        
        lines.extend([
            f"\n## 5. Code Hygiene\n",
            f"Style and convention issues that affect code readability.\n",
        ])
        if code_hygiene_issues:
            lines.append(f"**{len(code_hygiene_issues)} issue(s) found**\n")
            for issue in code_hygiene_issues[:5]:
                lines.append(f"- `{issue.get('file', '?')}`: {issue.get('pattern', 'issue')}")
            if len(code_hygiene_issues) > 5:
                lines.append(f"- _...and {len(code_hygiene_issues) - 5} more_")
        else:
            lines.append("✔ No code hygiene issues detected.\n")
        
        lines.extend([
            f"\n## 6. Auto-Fix Summary\n",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Fixes Applied | {validated} |",
            f"| Manual Fixes Avoided | {manual_fixes_avoided} |",
            f"| Files Cleaned | {files_cleaned} |",
            f"| Failed / Rolled Back | {repair.get('failed_patches', 0)} |",
            f"| Validation Success | {validation_success_rate}% |",
            f"| **Time Saved** | **{time_saved_minutes} min ({time_saved_hours} hrs)** |",
        ])
        
        remaining = repair.get('issues_found', 0) - validated
        lines.extend([
            f"\n## 7. Remaining Issues\n",
            f"**{remaining} issue(s) require manual attention.**\n",
        ])
        manual_issues = [i for i in issues if isinstance(i, dict) and i.get('fixability') != 'AUTO_FIXABLE']
        if manual_issues:
            for issue in manual_issues[:10]:
                fix = issue.get('fixability', 'UNKNOWN')
                lines.append(f"- `{issue.get('file', '?')}`: {issue.get('pattern', 'issue')} [`{fix}`]")
            if len(manual_issues) > 10:
                lines.append(f"- _...and {len(manual_issues) - 10} more_")
        else:
            lines.append("✔ All issues have been auto-fixed!\n")
        
        lines.extend([
            f"\n## 8. Technical Debt\n",
            f"Issues that represent accumulated technical debt.\n",
        ])
        if technical_debt_issues:
            lines.append(f"**{len(technical_debt_issues)} issue(s) found**\n")
            for issue in technical_debt_issues[:5]:
                lines.append(f"- `{issue.get('file', '?')}`: {issue.get('pattern', 'issue')}")
        else:
            lines.append("✔ No technical debt identified.\n")
        
        lines.extend([
            f"\n## 9. Top Risk Files\n",
            f"Files with the highest concentration of issues.\n",
        ])
        if top_risk_files:
            lines.append(f"| File | Issues |")
            lines.append(f"|------|--------|")
            for fpath, count in top_risk_files:
                lines.append(f"| `{fpath}` | {count} |")
        else:
            lines.append("✔ No high-risk files identified.\n")
        
        remaining = repair.get('issues_found', 0) - validated
        lines.extend([
            f"\n## 10. Estimated Developer Value\n",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| **Time Saved** | **{time_saved_minutes} min ({time_saved_hours} hrs)** |",
            f"| Manual Fixes Avoided | {manual_fixes_avoided} |",
            f"| Files Cleaned | {files_cleaned} |",
            f"| Validation Success Rate | {validation_success_rate}% |",
            f"| Focus Remaining | ~{remaining * 5} min |",
        ])
        
        # Backward compatibility: legacy sections
        lines.extend([
            "\n---\n",
            f"\n## Legacy Data\n",
            f"**Tool Calls:** {data['tool_calls']}",
            f"**Patches Applied:** {len(data.get('patches', []))}",
        ])
        
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
        """Generate developer-focused JSON report with backward compatibility."""
        data = _collect_report_data(ctx)
        health = repo_health_score({}, ctx)
        repair = data.get("repair_metrics", {})
        issues = data.get("issues", [])
        
        # Classify issues by category
        categories = {
            "reliability": [],
            "security": [],
            "maintainability": [],
            "code_hygiene": [],
            "technical_debt": [],
        }
        pattern_to_category = {
            "division_by_zero": "reliability",
            "logic_bug": "reliability",
            "type_mismatch": "reliability",
            "bare_except": "reliability",
            "eval_usage": "security",
            "hardcoded_secret": "security",
            "pickle_load": "security",
            "vulnerability": "security",
            "dead_code": "maintainability",
            "long_function": "maintainability",
            "complexity": "maintainability",
            "circular_import": "maintainability",
            "wrong_except": "code_hygiene",
            "print_debug": "code_hygiene",
            "unused_import": "code_hygiene",
            "duplicate_import": "code_hygiene",
            "trailing_whitespace": "code_hygiene",
            "missing_newline_eof": "code_hygiene",
            "todo_fixme": "code_hygiene",
        }
        
        for issue in issues:
            if isinstance(issue, dict):
                pattern = issue.get('pattern', '')
                cat = pattern_to_category.get(pattern, 'technical_debt')
                categories[cat].append(issue)
        
        # Get developer impact metrics from repair_metrics
        validated = repair.get("validated_patches", 0)
        time_saved_minutes = repair.get("time_saved_minutes", validated * 2)
        time_saved_hours = repair.get("time_saved_hours", round(time_saved_minutes / 60, 1))
        manual_fixes_avoided = repair.get("manual_fixes_avoided", validated)
        files_cleaned = repair.get("files_cleaned", 0)
        validation_success_rate = repair.get("validation_success_rate", 0.0)
        
        # Top risk files
        file_issue_count: dict[str, int] = {}
        for issue in issues:
            if isinstance(issue, dict):
                f = issue.get('file', 'unknown')
                file_issue_count[f] = file_issue_count.get(f, 0) + 1
        top_risk_files = [
            {"file": f, "issue_count": c} 
            for f, c in sorted(file_issue_count.items(), key=lambda x: -x[1])[:5]
        ]
        
        # Build developer-focused report structure
        developer_report = {
            "version": "2.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo": data["repo"],
            "trace_id": data["trace_id"],
            # Section 1: Repository Health
            "repository_health": {
                "health_score": health["score"],
                "health_grade": health.get("grade", "N/A"),
                "issues_found": repair.get("issues_found", 0),
                "auto_fixable_count": repair.get("auto_fixable", 0),
                "auto_fixable_percent": round(repair.get("auto_fixable", 0) / max(repair.get("issues_found", 1), 1) * 100, 1),
            },
            # Section 2-5: Issue categories
            "reliability": {
                "count": len(categories["reliability"]),
                "issues": categories["reliability"][:10],
            },
            "security": {
                "count": len(categories["security"]),
                "issues": categories["security"][:10],
            },
            "maintainability": {
                "count": len(categories["maintainability"]),
                "issues": categories["maintainability"][:10],
            },
            "code_hygiene": {
                "count": len(categories["code_hygiene"]),
                "issues": categories["code_hygiene"][:10],
            },
            # Section 6: Auto-Fix Summary
            "auto_fix_summary": {
                "fixes_applied": validated,
                "manual_fixes_avoided": manual_fixes_avoided,
                "files_cleaned": files_cleaned,
                "failed": repair.get("failed_patches", 0),
                "rolled_back": repair.get("rollbacks", 0),
                "validation_success_rate": validation_success_rate,
                "success_rate": repair.get("repair_rate", 0.0),
                "estimated_time_saved_minutes": time_saved_minutes,
                "estimated_time_saved_hours": time_saved_hours,
            },
            # Section 7: Remaining Issues
            "remaining_issues": {
                "count": repair.get("issues_found", 0) - validated,
                "issues": [
                    i for i in issues 
                    if isinstance(i, dict) and i.get('fixability') != 'AUTO_FIXABLE'
                ][:20],
            },
            # Section 8: Technical Debt
            "technical_debt": {
                "count": len(categories["technical_debt"]),
                "issues": categories["technical_debt"][:10],
            },
            # Section 9: Top Risk Files
            "top_risk_files": top_risk_files,
            # Section 10: Developer Value
            "developer_value": {
                "time_saved_minutes": time_saved_minutes,
                "time_saved_hours": time_saved_hours,
                "manual_fixes_avoided": manual_fixes_avoided,
                "files_cleaned": files_cleaned,
                "validation_success_rate": validation_success_rate,
                "focus_remaining_minutes": (repair.get("issues_found", 0) - validated) * 5,
                "focus_remaining_hours": round((repair.get("issues_found", 0) - validated) * 5 / 60, 1),
            },
        }
        
        # Backward compatibility: include legacy fields
        report = {
            "version": "2.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo": data["repo"],
            "trace_id": data["trace_id"],
            "tool_calls": data["tool_calls"],
            "health_score": health["score"],
            # Legacy fields preserved
            "issues": data["issues"],
            "patches": data["patches"],
            "validation": data.get("validation"),
            "test_results": data.get("test_results"),
            "tool_coverage": data.get("tool_coverage"),
            "repair_metrics": repair,
            # New developer-focused sections
            "developer_report": developer_report,
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

    def export_github_repair_workflow(params: dict, ctx: ExecutionContext) -> dict:
        """Export repair workflow as GitHub PR or patches.diff file.
        
        If GH_TOKEN environment variable is set:
        - Creates a new branch
        - Commits all validated patches
        - Pushes branch to remote
        - Creates Pull Request with title and description
        
        If GH_TOKEN is not set:
        - Generates patches.diff file with unified diff format
        
        Does not affect the analysis workflow - this is a separate export step.
        """
        import os
        import subprocess
        from pathlib import Path
        
        gh_token = os.environ.get("GH_TOKEN", "")
        patches = ctx.patches_applied or []
        
        # Filter for validated/successful patches only
        validated_patches = [p for p in patches if p.get("validated") or p.get("diff")]
        
        if not validated_patches:
            return {
                "success": False,
                "reason": "No validated patches to export",
                "files_changed": 0,
                "commits_created": 0,
            }
        
        files_changed = set()
        for p in validated_patches:
            if p.get("path"):
                files_changed.add(p.get("path"))
        
        result = {
            "success": True,
            "files_changed": len(files_changed),
            "commits_created": 0,
            "patches_count": len(validated_patches),
        }
        
        if gh_token:
            # GitHub PR workflow
            try:
                # Detect default branch
                default_branch = subprocess.run(
                    ["git", "symbolic-ref", "refs/remotes/origin/HEAD", "--short"],
                    capture_output=True, text=True, cwd=str(ctx.repo_path)
                ).stdout.strip().replace("origin/", "") or "main"
                
                # Create unique branch name
                branch_name = f"agira-repair-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
                
                # Generate PR title and description
                repair_metrics = _collect_repair_metrics(ctx)
                issues_found = repair_metrics.get("issues_found", len(validated_patches))
                time_saved = repair_metrics.get("time_saved_minutes", 0)
                
                pr_title = f"chore(agira): Auto-fix {len(validated_patches)} issues ({time_saved} min saved)"
                
                pr_body_lines = [
                    "## AGIRA Automated Repair",
                    "",
                    f"**Issues Fixed:** {len(validated_patches)}",
                    f"**Files Changed:** {len(files_changed)}",
                    f"**Estimated Time Saved:** {time_saved} minutes",
                    "",
                    "### Summary",
                    "This PR applies automated fixes generated by AGIRA:",
                    "",
                ]
                
                for p in validated_patches[:20]:
                    path = p.get("path", "unknown")
                    pattern = p.get("pattern", p.get("fix_type", "fix"))
                    pr_body_lines.append(f"- `{path}`: {pattern}")
                
                if len(validated_patches) > 20:
                    pr_body_lines.append(f"- _...and {len(validated_patches) - 20} more_")
                
                pr_body_lines.extend([
                    "",
                    "### Files Changed",
                ])
                for f in sorted(files_changed):
                    pr_body_lines.append(f"- `{f}`")
                
                pr_body = "\n".join(pr_body_lines)
                
                # Checkout new branch
                subprocess.run(
                    ["git", "checkout", "-b", branch_name],
                    capture_output=True, cwd=str(ctx.repo_path)
                )
                
                # Stage and commit each patched file
                for p in validated_patches:
                    path = p.get("path", "")
                    if not path:
                        continue
                    file_path = ctx.repo_path / path
                    if file_path.exists():
                        subprocess.run(
                            ["git", "add", path],
                            capture_output=True, cwd=str(ctx.repo_path)
                        )
                
                # Commit changes
                commit_result = subprocess.run(
                    ["git", "commit", "-m", f"feat(agira): Apply {len(validated_patches)} auto-fixes"],
                    capture_output=True, text=True, cwd=str(ctx.repo_path),
                    env={**os.environ, "GIT_AUTHOR_NAME": "AGIRA", "GIT_AUTHOR_EMAIL": "agira@local",
                         "GIT_COMMITTER_NAME": "AGIRA", "GIT_COMMITTER_EMAIL": "agira@local",
                         "GIT_EDITOR": "true"}
                )
                
                if commit_result.returncode == 0:
                    result["commits_created"] = 1
                
                # Push branch
                push_result = subprocess.run(
                    ["git", "push", "-u", "origin", branch_name],
                    capture_output=True, text=True, cwd=str(ctx.repo_path),
                    env={**os.environ, "GH_TOKEN": gh_token}
                )
                
                if push_result.returncode != 0:
                    result["success"] = False
                    result["error"] = f"Push failed: {push_result.stderr}"
                    return result
                
                # Create PR using gh CLI
                pr_result = subprocess.run(
                    [
                        "gh", "pr", "create",
                        "--title", pr_title,
                        "--body", pr_body,
                        "--base", default_branch,
                    ],
                    capture_output=True, text=True, cwd=str(ctx.repo_path),
                    env={**os.environ, "GH_TOKEN": gh_token}
                )
                
                if pr_result.returncode == 0:
                    pr_url = pr_result.stdout.strip()
                    result["pr_url"] = pr_url
                    result["branch_name"] = branch_name
                else:
                    result["pr_error"] = pr_result.stderr
                
            except Exception as e:
                result["success"] = False
                result["error"] = str(e)
        else:
            # Generate patches.diff file
            diff_lines = ["# AGIRA Patches Diff",
                          f"# Generated: {datetime.now(timezone.utc).isoformat()}",
                          f"# Patches: {len(validated_patches)}",
                          f"# Files: {len(files_changed)}",
                          "",
                          "---",
                          ""]
            
            for p in validated_patches:
                diff = p.get("diff", "")
                if diff:
                    diff_lines.append(diff)
                    diff_lines.append("")
            
            diff_content = "\n".join(diff_lines)
            
            # Write patches.diff to repo parent directory
            diff_path = ctx.repo_path.parent / "patches.diff"
            diff_path.write_text(diff_content, encoding="utf-8")
            result["diff_file"] = str(diff_path)
            result["method"] = "patches.diff"
        
        return result

    tools.append(
        ToolDefinition(
            "export_github_repair_workflow", "report_tools", 
            "Export validated fixes as GitHub PR or patches.diff file",
            _schema({}, []),
            _out({"success": {"type": "boolean"}, "files_changed": {"type": "integer"},
                 "commits_created": {"type": "integer"}}), 
            "ToolError", export_github_repair_workflow,
        )
    )

    return tools
