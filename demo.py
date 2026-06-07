#!/usr/bin/env python3
"""Agira Hackathon Demo — One-click autonomous repository intelligence.

Run with:
    python demo.py [path-to-repo]

If no path is given, uses the built-in buggy_calculator example.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

# ── ANSI color codes for rich output ─────────────────────────────────────────
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"
DIM = "\033[2m"


def c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def print_banner() -> None:
    banner = f"""
{BOLD}{CYAN}
╔══════════════════════════════════════════════════════════╗
║          AGIRA — AUTONOMOUS REPOSITORY INTELLIGENCE      ║
║              Next-Gen Self-Healing DAG Engine            ║
╚══════════════════════════════════════════════════════════╝
{RESET}
"""
    print(banner)


def print_dag_structure() -> None:
    """Print a visual representation of the 11-node DAG."""
    print(f"\n{BOLD}DAG STRUCTURE (11 NODES){RESET}")
    print(f"{DIM}{'─' * 50}{RESET}")

    # Node definitions with batch assignment
    batches = [
        ("Batch 1 (PARALLEL)", [
            ("repo_metadata", "Tool", "repo_tools.get_repo_metadata"),
            ("file_list", "Tool", "repo_tools.list_files"),
            ("dependency_graph", "Tool", "analysis_tools.build_dependency_graph"),
        ]),
        ("Batch 2 (PARALLEL — INDEPENDENT)", [
            ("bug_detection", "Subagent", "BugHunterAgent"),
            ("repo_analysis", "Subagent", "RepoAnalyzerAgent"),
        ]),
        ("Batch 3 (SEQUENTIAL)", [
            ("merge_findings", "Tool", "agent_tools.merge_agent_output"),
        ]),
        ("Batch 4 (PARALLEL)", [
            ("initial_validation", "Tool", "execution_tools.run_tests"),
            ("patch_generation", "Subagent", "PatchGeneratorAgent"),
        ]),
        ("Batch 5 (SEQUENTIAL)", [
            ("test_validation", "Subagent", "TestValidationAgent"),
        ]),
        ("Batch 6 → Final (SEQUENTIAL)", [
            ("health_score", "Tool", "report_tools.repo_health_score"),
            ("json_report", "Tool", "report_tools.generate_json_report"),
        ]),
    ]

    for batch_name, nodes in batches:
        is_parallel = "PARALLEL" in batch_name
        marker = f"{GREEN}∥{RESET}" if is_parallel else f"{YELLOW}→{RESET}"
        print(f"\n  {marker} {BOLD}{batch_name}{RESET}")
        for name, kind, target in nodes:
            kind_color = BLUE if kind == "Tool" else CYAN
            print(f"      {DIM}└──{RESET} [{kind_color}{kind}{RESET}] {name}")
            print(f"              {DIM}{target}{RESET}")

    print(f"\n{DIM}{'─' * 50}{RESET}")
    print(f"  {GREEN}∥{RESET} = parallel execution   {YELLOW}→{RESET} = sequential dependency")
    print(f"  {CYAN}[Subagent]{RESET} = isolated copy-on-write agent")
    print(f"  {BLUE}[Tool]{RESET}      = direct registry invocation")


def run_demo(repo_path: Path) -> None:
    """Run the full demo pipeline."""
    from agira.orchestrator.engine import Orchestrator
    from agira.registry.registry import create_registry
    from agira.utils import get_execution_logger, reset_execution_logger
    from agira.report import build_report_from_orchestrator

    # Reset logger for fresh run
    reset_execution_logger()
    logger = get_execution_logger()
    logger.start_execution()

    print(f"\n{GREEN}▶ Initializing orchestrator with next-gen capabilities...{RESET}")
    print(f"  {DIM}parallel_scheduling=True  self_healing=True  memory_layer=True{RESET}")

    orch = Orchestrator(
        registry=create_registry(),
        parallel_scheduling=True,
        self_healing=True,
        memory_layer=True,
        adaptive_planning=True,
    )

    print(f"\n{GREEN}▶ Running autonomous DAG pipeline...{RESET}\n")

    result = orch.run(
        repo_path,
        mode="demo",
    )

    logger.end_execution()

    # Extract issues from artifact store for reporting
    issues_art = result.context.artifact_store.latest("issues")
    if issues_art:
        data = issues_art.data
        issues = data.get("issues", data) if isinstance(data, dict) else data
    else:
        issues = None

    # Build and display report
    report = build_report_from_orchestrator(
        result,
        logger,
        memory_store=orch._memory,
        issues=issues,
    )

    # Print timeline
    logger.print_timeline_report()

    # Print final report
    report.print_human_summary()

    # Save JSON report
    report_path = Path("output") / "final_report.json"
    report_path.parent.mkdir(exist_ok=True)
    report.save_json(report_path)
    print(f"  {GREEN}✔ Report saved:{RESET} {report_path}")

    # Save to output dir
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    logger_path = output_dir / "execution_timeline.json"
    logger_path.write_text(
        __import__("json").dumps(logger.to_dict(), indent=2, default=str),
        encoding="utf-8",
    )
    print(f"  {GREEN}✔ Timeline saved:{RESET} {logger_path}")


def main() -> None:
    print_banner()

    # Determine repo path
    if len(sys.argv) > 1:
        repo_path = Path(sys.argv[1]).resolve()
        if not repo_path.exists():
            print(f"{RED}✗ Error: path does not exist: {repo_path}{RESET}")
            sys.exit(1)
        print(f"  Using repo: {repo_path}")
        is_temp = False
    else:
        examples_dir = Path(__file__).parent / "examples" / "buggy_calculator"
        if not examples_dir.exists():
            print(f"{RED}✗ Error: examples/buggy_calculator not found.{RESET}")
            print(f"  Run with: python demo.py <path-to-repo>")
            sys.exit(1)
        # Copy to temp dir so demo is non-destructive
        tmp = Path(tempfile.mkdtemp(prefix="agira_demo_"))
        shutil.copytree(examples_dir, tmp, dirs_exist_ok=True)
        repo_path = tmp
        print(f"  Using example repo (temp): {repo_path}")
        is_temp = True

    print_dag_structure()

    try:
        run_demo(repo_path)
    finally:
        if is_temp:
            shutil.rmtree(repo_path, ignore_errors=True)


if __name__ == "__main__":
    main()