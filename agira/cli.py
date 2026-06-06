"""AGIRA command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agira.eval.harness import EvaluationHarness
from agira.observability.logging import demo_print, set_log_mode, setup_logging
from agira.orchestrator.engine import Orchestrator
from agira.registry.registry import create_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AGIRA — Autonomous GitHub Repo Intelligence & Repair Agent"
    )
    parser.add_argument("--mode", choices=["demo", "debug"], default="demo", help="Output mode")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run adaptive repair pipeline on a repo")
    run_parser.add_argument("repo_path", help="Path to repository")
    run_parser.add_argument("--output", "-o", help="Output JSON report path")
    run_parser.add_argument("--markdown", "-m", help="Output markdown report path")
    run_parser.add_argument("--resume", help="Resume from checkpoint plan_id")
    run_parser.add_argument("--mode", choices=["demo", "debug"], default="demo")

    eval_parser = sub.add_parser("eval", help="Run evaluation harness")
    eval_parser.add_argument("--output", "-o", default="eval_results.json")
    eval_parser.add_argument("--examples", help="Path to examples directory")
    eval_parser.add_argument("--mode", choices=["demo", "debug"], default="demo")

    list_parser = sub.add_parser("tools", help="List registered tools")
    list_parser.add_argument("--namespace", help="Filter by namespace")

    args = parser.parse_args(argv)
    mode = getattr(args, "mode", "demo")
    set_log_mode(mode)
    setup_logging()

    if args.command == "run":
        import shutil
        import tempfile

        repo = Path(args.repo_path).resolve()
        work_dir = Path(tempfile.mkdtemp(prefix="agira_run_"))
        shutil.copytree(repo, work_dir, dirs_exist_ok=True)

        orchestrator = Orchestrator()
        result = orchestrator.run(
            work_dir, resume_plan_id=args.resume, mode=mode,
        )
        output = result.to_dict()

        if mode == "demo":
            demo_print(f"\nAGIRA Run Complete")
            demo_print(f"  Success: {result.success}")
            demo_print(f"  Tool calls: {result.tool_calls}")
            demo_print(f"  Trace: {result.context.trace_id}")
            issues = result.report.get("issues", [])
            demo_print(f"  Issues found: {len(issues)}")
            for issue in issues[:5]:
                if isinstance(issue, dict):
                    demo_print(f"    - {issue.get('pattern', '?')} in {issue.get('file', '?')}")
            demo_print(f"  Patches applied: {len(result.context.patches_applied)}")
            demo_print(f"  Tool coverage: {result.tool_coverage.get('coverage_pct', '?')}%")
            if result.markdown_report:
                demo_print(f"\n--- Report Preview ---\n{result.markdown_report[:800]}")
        else:
            print(json.dumps(output, indent=2, default=str))

        if args.output:
            Path(args.output).write_text(json.dumps(output, indent=2, default=str))
        if args.markdown and result.markdown_report:
            Path(args.markdown).write_text(result.markdown_report)
        return 0 if result.success else 1

    if args.command == "eval":
        harness = EvaluationHarness(args.examples)
        summary = harness.run_and_export(args.output)
        if mode == "demo":
            demo_print(json.dumps(summary.to_dict(), indent=2))
        else:
            print(json.dumps(summary.to_dict(), indent=2))
        return 0

    if args.command == "tools":
        registry = create_registry()
        tools = registry.list_tools(args.namespace) if args.namespace else registry.list_tools()
        print(f"Total tools: {registry.count()}")
        print(f"Namespaces: {registry.namespaces()}")
        for t in tools:
            print(f"  {t['qualified_name']}: {t['description']}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
