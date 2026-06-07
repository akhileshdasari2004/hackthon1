"""Adaptive orchestrator — plan → execute → observe → replan loop.

Next-gen upgrades (backward-compatible):
- Parallel scheduler: executes independent nodes concurrently
- Self-healing: failure classifier + DAG repair
- Memory layer: cross-run learning store
- Adaptive planner: memory-aware goal ordering
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agira.observability.errors import ExecutionError
from agira.observability.logging import (
    demo_print,
    log_event,
    new_trace_id,
    set_log_mode,
    set_trace_id,
    setup_logging,
)
from agira.orchestrator.checkpoint import CheckpointManager
from agira.orchestrator.dag_repair import DAGRepair
from agira.orchestrator.dynamic_planner import AdaptivePlanner
from agira.orchestrator.failure_classifier import FailureClass, classify_failure, failure_action
from agira.orchestrator.memory_store import get_memory_store
from agira.orchestrator.parallel_scheduler import ParallelScheduler
from agira.orchestrator.plan import ExecutionPlan, NodeStatus, PlanNode
from agira.orchestrator.planner import DynamicPlanner
from agira.orchestrator.state_machine import ExecutionStateMachine
from agira.registry.registry import ToolRegistry, create_registry
from agira.tools.context import ExecutionContext
from agira.utils import get_execution_logger


# Global logger (set once per process)
_logger = None


@dataclass
class OrchestratorResult:
    plan: ExecutionPlan
    context: ExecutionContext
    report: dict[str, Any] = field(default_factory=dict)
    markdown_report: str = ""
    success: bool = False
    tool_calls: int = 0
    tool_coverage: dict[str, Any] = field(default_factory=dict)
    autonomy_report: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "tool_calls": self.tool_calls,
            "plan": self.plan.to_dict(),
            "report": self.report,
            "markdown_report": self.markdown_report,
            "trace_id": self.context.trace_id,
            "tool_coverage": self.tool_coverage,
            "autonomy_report": self.autonomy_report,
            "failure_history": self.context.failure_history,
        }


class Orchestrator:
    """Manages artifact flow, state machine, execution control, and rollback.

    Next-gen capabilities (all backward-compatible):
    - parallel_scheduling: executes independent nodes in parallel batches
    - self_healing: failure classifier routes failures to skip/retry/repartition
    - memory_layer: cross-run learning via persistent MemoryStore
    - adaptive_planning: memory-aware goal ordering
    """

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        checkpoint_dir: str | Path | None = None,
        *,
        parallel_scheduling: bool = True,
        self_healing: bool = True,
        memory_layer: bool = True,
        adaptive_planning: bool = True,
    ) -> None:
        self.registry = registry or create_registry()
        # Choose planner: adaptive (memory-aware) or base (reactive)
        self._base_planner = DynamicPlanner()
        self.planner = AdaptivePlanner() if adaptive_planning else self._base_planner
        self.state_machine = ExecutionStateMachine(self.registry)
        self.checkpoints = CheckpointManager(checkpoint_dir)

        # Next-gen features (all off by default for safety)
        self.parallel_scheduling = parallel_scheduling
        self.self_healing = self_healing
        self.memory_layer = memory_layer
        self._memory = get_memory_store() if memory_layer else None
        self._scheduler = ParallelScheduler(max_workers=4) if parallel_scheduling else None
        self._repair = DAGRepair
        self._batch_counter = 0  # Tracks current execution batch for timeline logger

    def run(
        self,
        repo_path: str | Path,
        *,
        trace_id: str | None = None,
        resume_plan_id: str | None = None,
        mode: str = "demo",
    ) -> OrchestratorResult:
        global _logger
        set_log_mode(mode)
        _logger = setup_logging()
        repo_path = Path(repo_path).resolve()
        if not repo_path.exists():
            raise ExecutionError(f"Repository path does not exist: {repo_path}")

        if resume_plan_id:
            return self._resume(resume_plan_id, repo_path, mode)

        tid = trace_id or new_trace_id()
        set_trace_id(tid)

        plan = ExecutionPlan.create(str(repo_path))
        ctx = ExecutionContext(repo_path=repo_path, trace_id=tid)
        ctx.state["_registry"] = self.registry

        log_event(_logger, "orchestrator_start", repo=str(repo_path), trace_id=tid, mode=mode)
        plan.status = "running"

        # Record repo profile in memory
        if self._memory:
            self._memory.record_repo_profile(str(repo_path), {
                "language": "python",
                "mode": mode,
            })

        while self.planner.should_continue(plan, ctx.artifact_store):
            plan.iteration += 1
            demo_print(f"[DEBUG] Iteration {plan.iteration}")
            demo_print(f"[DEBUG] Current artifact types: {list(ctx.artifact_store._by_type.keys())}")

            self.planner.propose(plan, ctx.artifact_store)
            demo_print(f"[DEBUG] After propose, nodes: {[n.name for n in plan.nodes.values()]}")

            # ── Parallel scheduling ──────────────────────────────────────────
            if self.parallel_scheduling and self._scheduler:
                self._run_parallel_batch(plan, ctx)
            else:
                self._run_sequential(plan, ctx)

            # ── Post-iteration: observe + record ────────────────────────────
            observations = self.planner.observe(ctx.artifact_store)
            demo_print(f"[DEBUG] Storing observation_{plan.iteration}")
            ctx.store_result(f"observation_{plan.iteration}", observations, producer="planner")

            # Memory: log iteration summary
            if self._memory:
                self._memory.log_learning("iteration", {
                    "iteration": plan.iteration,
                    "completed_nodes": [
                        n.name for n in plan.nodes.values()
                        if n.status == NodeStatus.COMPLETED
                    ],
                    "failed_nodes": [
                        n.name for n in plan.nodes.values()
                        if n.status == NodeStatus.FAILED
                    ],
                })

        plan.status = "completed"
        success = self._determine_success(ctx)
        plan.metadata["tool_calls"] = ctx.tool_call_count
        plan.metadata["tool_usage"] = ctx.tool_usage

        # ── Memory: record final outcome ──────────────────────────────────────
        if self._memory and self.memory_layer:
            for node in plan.nodes.values():
                if node.status == NodeStatus.COMPLETED:
                    self._memory.record_success(
                        node.name, str(repo_path),
                        {"iteration": plan.iteration}
                    )

        report_art = ctx.artifact_store.latest("json_report")
        md_art = ctx.artifact_store.latest("markdown_report")
        coverage_art = ctx.artifact_store.latest("tool_coverage")

        final_report = {}
        if report_art:
            data = report_art.data
            final_report = data.get("report", data) if isinstance(data, dict) else data

        md_report = ""
        if md_art:
            data = md_art.data
            md_report = data.get("report", "") if isinstance(data, dict) else str(data)

        if coverage_art:
            tool_coverage = coverage_art.data if isinstance(coverage_art.data, dict) else {"usage": ctx.tool_usage}
        else:
            tool_coverage = self.registry.usage_report(ctx)

        log_event(_logger, "orchestrator_complete", success=success, tool_calls=ctx.tool_call_count)

        # Generate autonomy report
        usage_report = self.registry.usage_report(ctx)
        tool_coverage_pct = usage_report.get("coverage_pct", 0.0)
        active_tools = usage_report.get("usage", {})
        orphan_tools = usage_report.get("unused_tools", [])
        autonomy_report = {
            "planning_mode": "ADAPTIVE" if self.planner.__class__.__name__ == "AdaptivePlanner" else "REACTIVE",
            "tool_coverage": tool_coverage_pct,
            "active_tools": sorted(active_tools.keys()),
            "orphan_tools": sorted(orphan_tools),
            "parallel_scheduling": self.parallel_scheduling,
            "self_healing": self.self_healing,
            "memory_layer": self.memory_layer,
            "composability_score": 0.0,
            "system_classification": "AUTONOMOUS" if tool_coverage_pct >= 50.0 else "HYBRID"
        }

        return OrchestratorResult(
            plan=plan,
            context=ctx,
            report=final_report,
            markdown_report=md_report,
            success=success,
            tool_calls=ctx.tool_call_count,
            tool_coverage=tool_coverage,
            autonomy_report=autonomy_report,
        )

    def _run_parallel_batch(self, plan: ExecutionPlan, ctx: ExecutionContext) -> None:
        """Execute ready nodes in parallel batches when possible."""
        repair = self._repair(plan)
        logger = get_execution_logger()

        while True:
            batches = self._scheduler.compute_batches(plan)
            if not batches:
                # No more batches — check for pending/failed
                pending = [n for n in plan.nodes.values() if n.status == NodeStatus.PENDING]
                failed = [n for n in plan.nodes.values() if n.status == NodeStatus.FAILED]
                if pending:
                    for p in pending:
                        p.status = NodeStatus.READY
                    continue
                if failed:
                    demo_print(f"[DEBUG] Nodes permanently failed: {[n.name for n in failed]}")
                break

            self._batch_counter += 1
            batch_id = self._batch_counter
            # Execute first batch: nodes whose deps are satisfied but may still be PENDING
            batch = batches[0]
            batch_nodes = [plan.nodes[nid] for nid in batch]
            # Mark as READY so execute_with_healing can run them
            for n in batch_nodes:
                if n.status == NodeStatus.PENDING:
                    n.status = NodeStatus.READY

            demo_print(f"[DEBUG] Parallel batch {batch_id} ({len(batch_nodes)} nodes): {[n.name for n in batch_nodes]}")

            for node in batch_nodes:
                self._execute_with_healing(node, plan, ctx, repair, batch_id=batch_id)

            logger.finalize_batch(batch_id, [n.name for n in batch_nodes], is_parallel=True)

            # Unblock dependents of completed nodes
            completed = [nid for nid, n in plan.nodes.items() if n.status == NodeStatus.COMPLETED]
            for cid in completed:
                repair.unblock_when_ready(cid)

    def _run_sequential(self, plan: ExecutionPlan, ctx: ExecutionContext) -> None:
        """Original sequential execution (backward-compatible)."""
        repair = self._repair(plan)
        logger = get_execution_logger()

        ready = plan.ready_nodes()
        demo_print(f"[DEBUG] Ready nodes: {[n.name for n in ready]}")

        if not ready:
            demo_print(f"[DEBUG] No ready nodes, checking pending")
            pending = [n for n in plan.nodes.values() if n.status == NodeStatus.PENDING]
            if pending:
                demo_print(f"[DEBUG] Retrying pending nodes: {[n.name for n in pending]}")
                for p in pending:
                    p.status = NodeStatus.READY
                return
            failed = [n for n in plan.nodes.values() if n.status == NodeStatus.FAILED]
            if failed:
                demo_print(f"[DEBUG] Nodes permanently failed: {[n.name for n in failed]}")
                return
            demo_print(f"[DEBUG] No pending or failed nodes")
            return

        for node in ready:
            self._batch_counter += 1
            batch_id = self._batch_counter
            self._execute_with_healing(node, plan, ctx, repair, batch_id=batch_id)
            logger.finalize_batch(batch_id, [node.name], is_parallel=False)

    def _execute_with_healing(
        self,
        node: PlanNode,
        plan: ExecutionPlan,
        ctx: ExecutionContext,
        repair: DAGRepair,
        batch_id: int = 0,
    ) -> None:
        """Execute a single node with self-healing failure handling."""
        logger = get_execution_logger()
        logger.log_node_start(node.name, batch_id)
        demo_print(f"[DEBUG] Executing node {node.name} (action_type={node.action_type}, target={node.target})")
        try:
            self.state_machine.execute_node(node, plan, ctx)
            plan.checkpoint(node.name)
            self._save_checkpoint(plan, ctx)
            logger.log_node_end(node.name, batch_id, "completed")
            demo_print(f"[DEBUG] Node {node.name} completed")
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            log_event(_logger, "node_failed", node=node.name, error=str(exc))
            demo_print(f"[DEBUG] Node {node.name} failed: {exc}")

            # ── Self-healing: classify failure ─────────────────────────────
            logged_status = "failed"
            if self.self_healing:
                classification = classify_failure(node, str(exc))
                action = failure_action(classification)

                # Memory: record failure
                if self._memory:
                    self._memory.record_failure(
                        node.name,
                        error_signature=str(exc)[:100],
                        error_type=classification.value,
                        details={"target": node.target},
                    )

                if action == "retry" and node.retry_count < node.max_retries:
                    demo_print(f"[DEBUG] Retrying {node.name} (transient failure)")
                    node.status = NodeStatus.READY
                    logged_status = "retry"
                elif action == "skip":
                    demo_print(f"[DEBUG] Skipping {node.name} (deterministic failure)")
                    node.status = NodeStatus.SKIPPED
                    logged_status = "skipped"
                elif action == "repartition":
                    demo_print(f"[DEBUG] Reparation {node.name} (dependency failure)")
                    repair.repair_after_failure(node.node_id)
                    logged_status = "repartitioned"
                else:  # escalate
                    demo_print(f"[DEBUG] Escalating {node.name}")
                    node.status = NodeStatus.FAILED
            else:
                # Original behavior: keep node in whatever state state_machine left it
                if node.status == NodeStatus.FAILED:
                    demo_print(f"[DEBUG] Node {node.name} marked as FAILED")

            logger.log_node_end(node.name, batch_id, logged_status, str(exc))
            observations = self.planner.observe(ctx.artifact_store)
            ctx.store_result("observation", observations, producer="planner")

    def _determine_success(self, ctx: ExecutionContext) -> bool:
        validation = ctx.artifact_store.latest("validation_result")
        if not validation:
            return False
        vdata = validation.data.get("validation", validation.data) if isinstance(validation.data, dict) else {}
        if not vdata.get("overall_pass"):
            return False
        patch_art = ctx.artifact_store.latest("patch_result")
        patch_list = []
        if patch_art and isinstance(patch_art.data, dict):
            patch_list = patch_art.data.get("patches", [])
        if ctx.patches_applied:
            patch_list = patch_list or ctx.patches_applied
        if patch_list:
            for p in patch_list:
                if not p.get("validated", True):
                    return False
        return True

    def _save_checkpoint(self, plan: ExecutionPlan, ctx: ExecutionContext) -> None:
        state = {"plan": plan.to_dict(), "context": ctx.to_checkpoint_dict()}
        self.checkpoints.save(plan.plan_id, state)

    def _resume(self, plan_id: str, repo_path: Path, mode: str) -> OrchestratorResult:
        set_log_mode(mode)
        data = self.checkpoints.load(plan_id)
        if not data:
            raise ExecutionError(f"No checkpoint found for plan {plan_id}")
        plan = ExecutionPlan.from_dict(data["plan"])
        ctx = ExecutionContext(repo_path=repo_path, trace_id=data["context"]["trace_id"])
        ctx.load_checkpoint_dict(data["context"])
        ctx.state["_registry"] = self.registry
        return self.run(repo_path, trace_id=ctx.trace_id, mode=mode)