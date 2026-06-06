#!/usr/bin/env python3
"""Demonstrate adaptive AGIRA pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agira.eval.harness import EvaluationHarness
from agira.orchestrator.engine import Orchestrator
from agira.registry.registry import create_registry


def main() -> int:
    examples = ROOT / "examples" / "buggy_calculator"
    if not examples.exists():
        print("No example repo found.")
        return 1

    registry = create_registry()
    print(f"Tools: {registry.count()} | Mode: adaptive plan→execute→observe→replan")

    result = Orchestrator(registry).run(examples, mode="demo")

    print(f"\nSuccess: {result.success}")
    print(f"Tool calls: {result.tool_calls}")
    print(f"Issues: {len(result.report.get('issues', []))}")
    print(f"Patches: {len(result.context.patches_applied)}")
    print(f"Coverage: {result.tool_coverage.get('coverage_pct', 0)}%")

    harness = EvaluationHarness(ROOT / "examples")
    summary = harness.run_and_export(ROOT / "output" / "eval_summary.json")
    print(f"\nEval: repair_quality={summary.avg_repair_quality:.0%} test_pass={summary.test_pass_rate:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
