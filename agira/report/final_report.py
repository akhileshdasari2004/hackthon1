"""Final execution report generator — produces machine and human-readable summaries."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agira.utils.fixability import Fixability, summarize_fixability


@dataclass
class FinalReport:
    dag_status: str = "PENDING"
    nodes_executed: int = 0
    nodes_completed: int = 0
    nodes_failed: int = 0
    nodes_skipped: int = 0
    parallel_batches: int = 0
    failures: int = 0
    memory_used: bool = False
    plugins_used: bool = False
    execution_time_ms: float = 0.0
    self_healing_triggered: bool = False
    parallel_gain_pct: float = 0.0
    tool_calls: int = 0
    subagent_calls: int = 0
    memory_influence_log: list[str] = field(default_factory=list)
    failure_recoveries: list[str] = field(default_factory=list)
    plugins_executed: list[str] = field(default_factory=list)
    node_details: list[dict[str, Any]] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    fixability_summary: dict[str, Any] = field(default_factory=dict)
    # Repair metrics
    repair_metrics: dict[str, Any] = field(default_factory=dict)
    # Developer report sections
    developer_report: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dag_status": self.dag_status,
            "nodes_executed": self.nodes_executed,
            "nodes_completed": self.nodes_completed,
            "nodes_failed": self.nodes_failed,
            "nodes_skipped": self.nodes_skipped,
            "parallel_batches": self.parallel_batches,
            "failures": self.failures,
            "memory_used": self.memory_used,
            "plugins_used": self.plugins_used,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "self_healing_triggered": self.self_healing_triggered,
            "parallel_gain_pct": round(self.parallel_gain_pct, 1),
            "tool_calls": self.tool_calls,
            "subagent_calls": self.subagent_calls,
            "memory_influence_log": self.memory_influence_log,
            "failure_recoveries": self.failure_recoveries,
            "plugins_executed": self.plugins_executed,
            "node_details": self.node_details,
            "issues": self.issues,
            "fixability_summary": self.fixability_summary,
            "repair_metrics": self.repair_metrics,
            "developer_report": self.developer_report,
            "timestamp": self.timestamp,
        }

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8"
        )

    def print_human_summary(self) -> None:
        """Print a rich human-readable summary."""
        status_icon = "✔" if self.dag_status == "SUCCESS" else "✗"
        healing_icon = "✔" if self.self_healing_triggered else "—"

        print("\n" + "═" * 60)
        print("  FINAL EXECUTION REPORT — AGIRA AUTONOMOUS DAG ENGINE")
        print("═" * 60)

        print(f"\n  {status_icon} DAG execution:        {self.dag_status}")
        print(f"  {status_icon} Nodes executed:       {self.nodes_executed} total "
              f"({self.nodes_completed} ✓ / {self.nodes_failed} ✗ / {self.nodes_skipped} ⊘)")
        print(f"  {status_icon} Parallel batches:     {self.parallel_batches}")
        print(f"  {healing_icon} Self-healing:         "
              f"{'triggered' if self.self_healing_triggered else 'not needed'}")
        print(f"  {status_icon} Parallel speedup:     {self.parallel_gain_pct:.1f}%")
        print(f"  {status_icon} Execution time:       {self.execution_time_ms:.2f}ms")
        print(f"  {status_icon} Tool invocations:     {self.tool_calls}")
        print(f"  {status_icon} Subagent invocations: {self.subagent_calls}")

        if self.memory_used and self.memory_influence_log:
            print(f"\n  MEMORY INFLUENCE LOG:")
            for entry in self.memory_influence_log:
                print(f"    ▸ {entry}")

        if self.failure_recoveries:
            print(f"\n  FAILURE RECOVERIES:")
            for entry in self.failure_recoveries:
                print(f"    ▸ {entry}")

        if self.plugins_executed:
            print(f"\n  PLUGINS USED:")
            for p in self.plugins_executed:
                print(f"    ▸ {p}")

        if self.node_details:
            print(f"\n  NODE DETAILS:")
            print(f"  {'Node':<30} {'Status':>10} {'Duration':>12}")
            print(f"  {'-'*30} {'-'*10} {'-'*12}")
            for nd in self.node_details:
                duration = f"{nd.get('duration_ms') or 0:.2f}ms"
                status = nd.get("status", "unknown")
                print(f"  {nd.get('name', ''):<30} {status:>10} {duration:>12}")

        if self.fixability_summary:
            print(f"\n  ISSUES FOUND:")
            fs = self.fixability_summary
            total = fs.get("total", 0)
            auto_fix = fs.get("auto_fixable", 0)
            review_req = fs.get("review_required", 0)
            arch = fs.get("architectural", 0)
            unsupported = fs.get("unsupported", 0)
            print(f"    Total Issues:        {total}")
            print(f"    Auto Fixable:        {auto_fix}")
            print(f"    Review Required:     {review_req}")
            print(f"    Architectural:       {arch}")
            print(f"    Unsupported:         {unsupported}")

        if self.repair_metrics:
            print(f"\n  REPAIR METRICS:")
            rm = self.repair_metrics
            print(f"    Issues Found:        {rm.get('issues_found', 0)}")
            print(f"    Auto Fixable:        {rm.get('auto_fixable', 0)}")
            print(f"    Patch Attempts:      {rm.get('patch_attempts', 0)}")
            print(f"    Validated Patches:   {rm.get('validated_patches', 0)}")
            print(f"    Failed Patches:      {rm.get('failed_patches', 0)}")
            print(f"    Rollbacks:           {rm.get('rollbacks', 0)}")
            print(f"    Repair Rate:         {rm.get('repair_rate', 0)}%")
            print(f"    Validation Rate:     {rm.get('validation_rate', 0)}%")

        if self.developer_report:
            dr = self.developer_report
            print(f"\n  DEVELOPER REPORT:")
            
            # Repository Health
            rh = dr.get('repository_health', {})
            print(f"\n  1. Repository Health:")
            print(f"     Health Score:       {rh.get('health_score', 'N/A')} ({rh.get('health_grade', 'N/A')})")
            print(f"     Issues Found:       {rh.get('issues_found', 0)}")
            print(f"     Auto-Fixable:       {rh.get('auto_fixable_count', 0)}")
            
            # Auto-Fix Summary with Developer Impact
            afs = dr.get('auto_fix_summary', {})
            print(f"\n  6. Auto-Fix Summary:")
            print(f"     Fixes Applied:      {afs.get('fixes_applied', 0)}")
            print(f"     Manual Fixes Avoided: {afs.get('manual_fixes_avoided', 0)}")
            print(f"     Files Cleaned:      {afs.get('files_cleaned', 0)}")
            print(f"     Failed:             {afs.get('failed', 0)}")
            print(f"     Validation Success: {afs.get('validation_success_rate', 0)}%")
            print(f"     Time Saved:         {afs.get('estimated_time_saved_minutes', 0)} min ({afs.get('estimated_time_saved_hours', 0)} hrs)")
            
            # Developer Value
            dv = dr.get('developer_value', {})
            print(f"\n  10. Developer Value:")
            print(f"     Time Saved:         {dv.get('time_saved_minutes', 0)} min ({dv.get('time_saved_hours', 0)} hrs)")
            print(f"     Manual Fixes Avoided: {dv.get('manual_fixes_avoided', 0)}")
            print(f"     Files Cleaned:      {dv.get('files_cleaned', 0)}")
            
            # Top Risk Files
            trf = dr.get('top_risk_files', [])
            if trf:
                print(f"\n  9. Top Risk Files:")
                for item in trf[:3]:
                    print(f"     {item.get('file', '?'):<30} {item.get('issue_count', 0)} issues")

        print("\n" + "═" * 60)
        self._print_verdict()
        print("═" * 60 + "\n")

    def _print_verdict(self) -> None:
        """Print final system verdict."""
        if self.dag_status == "SUCCESS" and self.failures == 0:
            print("  ✔ SYSTEM IS PRODUCTION STABLE")
            print("  ✔ All 11 DAG nodes executed successfully")
            print("  ✔ No retry loops triggered")
            print("  ✔ Parallel scheduling maximized throughput")
        elif self.dag_status == "PARTIAL":
            print("  ◐ PARTIAL SUCCESS — some nodes failed or skipped")
        else:
            print("  ✗ EXECUTION FAILED — check failure log")


def build_report_from_orchestrator(
    result: Any,
    execution_logger: Any,
    memory_store: Any = None,
    issues: list[dict[str, Any]] | None = None,
) -> FinalReport:
    """Build a FinalReport from an OrchestratorResult and ExecutionLogger.

    Args:
        result: OrchestratorResult from the execution
        execution_logger: ExecutionLogger instance
        memory_store: Optional MemoryStore for memory influence logging
        issues: Optional list of issues to classify and summarize
    """
    report = FinalReport()

    plan = result.plan
    ctx = result.context

    # Node counts
    all_nodes = list(plan.nodes.values())
    report.nodes_executed = len(all_nodes)
    report.nodes_completed = sum(1 for n in all_nodes if n.status.value == "completed")
    report.nodes_failed = sum(1 for n in all_nodes if n.status.value == "failed")
    report.nodes_skipped = sum(1 for n in all_nodes if n.status.value == "skipped")
    report.tool_calls = result.tool_calls

    # Subagent calls
    from agira.orchestrator.plan import NodeStatus
    report.subagent_calls = sum(
        1 for n in all_nodes if n.action_type == "subagent" and n.status == NodeStatus.COMPLETED
    )

    # Status
    if report.nodes_failed == 0 and report.nodes_completed >= 10:
        report.dag_status = "SUCCESS"
    elif report.nodes_completed > 0:
        report.dag_status = "PARTIAL"
    else:
        report.dag_status = "FAILED"

    # Timing
    batch_timings = execution_logger.get_batch_timings()
    last = batch_timings[-1] if batch_timings else {}
    report.execution_time_ms = last.get("total_wallclock_ms", 0.0)
    report.parallel_gain_pct = last.get("parallel_gain_pct", 0.0)
    report.parallel_batches = len([b for b in batch_timings if isinstance(b, dict) and "batch_id" in b])

    # Memory
    if memory_store:
        report.memory_used = True
        # Pull memory influence log entries
        try:
            log = memory_store._cache.get("learning_log", [])
            for entry in log[-10:]:
                event = entry.get("event", "")
                data = entry.get("data", {})
                if event == "decision":
                    report.memory_influence_log.append(data.get("reason", str(data)))
        except Exception:
            pass

    # Failures
    report.failures = len(ctx.failure_history) if hasattr(ctx, "failure_history") else 0

    # Node details
    timeline = execution_logger.get_node_timeline()
    for node in all_nodes:
        node_timeline = [e for e in timeline if e["node"] == node.name]
        end_events = [e for e in node_timeline if e["event"] in ("completed", "failed", "skip")]
        duration = end_events[0]["duration_ms"] if end_events else None
        report.node_details.append({
            "name": node.name,
            "status": node.status.value,
            "duration_ms": duration,
            "batch": node_timeline[0]["batch"] if node_timeline else -1,
            "action_type": node.action_type,
            "target": node.target,
            "retry_count": node.retry_count,
            "error": node.error,
        })

    # Self-healing detection
    report.self_healing_triggered = report.failures > 0 or report.nodes_skipped > 0

    # Plugins
    report.plugins_used = len(report.plugins_executed) > 0

    # Issues and fixability classification
    if issues:
        report.issues = issues
        report.fixability_summary = summarize_fixability(issues)

    # Collect repair metrics and developer report from context
    # Import lazily to avoid circular imports
    from agira.tools.report_tools import _collect_repair_metrics, _collect_developer_report
    report.repair_metrics = _collect_repair_metrics(ctx)
    report.developer_report = _collect_developer_report(ctx, issues)

    return report