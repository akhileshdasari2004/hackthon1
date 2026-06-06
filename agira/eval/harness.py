"""Evaluation harness with repair quality scoring."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agira.orchestrator.engine import Orchestrator
from agira.registry.registry import create_registry


@dataclass
class EvalResult:
    repo_name: str
    repo_path: str
    success: bool
    tool_calls: int
    issues_found: int
    issues_fixed: int
    patches_applied: int
    tests_passed: bool
    health_score: float
    repair_quality: float
    false_positive_rate: float
    patch_correctness: bool
    regression_safe: bool
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_name": self.repo_name,
            "success": self.success,
            "tool_calls": self.tool_calls,
            "issues_found": self.issues_found,
            "issues_fixed": self.issues_fixed,
            "repair_quality": round(self.repair_quality, 2),
            "false_positive_rate": round(self.false_positive_rate, 2),
            "patch_correctness": self.patch_correctness,
            "regression_safe": self.regression_safe,
            "tests_passed": self.tests_passed,
            "health_score": self.health_score,
            "details": self.details,
        }


@dataclass
class EvalSummary:
    total_repos: int
    results: list[EvalResult]
    avg_repair_quality: float
    avg_health_score: float
    patch_correctness_rate: float
    regression_safe_rate: float
    test_pass_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_repos": self.total_repos,
            "avg_repair_quality": round(self.avg_repair_quality, 2),
            "avg_health_score": round(self.avg_health_score, 2),
            "patch_correctness_rate": round(self.patch_correctness_rate, 2),
            "regression_safe_rate": round(self.regression_safe_rate, 2),
            "test_pass_rate": round(self.test_pass_rate, 2),
            "results": [r.to_dict() for r in self.results],
        }


class EvaluationHarness:
    EXPECTED_FIXABLE = {
        "buggy_calculator": {"bare_except", "division_by_zero"},
        "messy_utils": {"bare_except", "unused_import"},
        "insecure_app": {"hardcoded_secret", "eval_usage"},
    }

    def __init__(self, examples_dir: str | Path | None = None) -> None:
        self.examples_dir = Path(examples_dir or Path(__file__).parent.parent.parent / "examples")
        self.orchestrator = Orchestrator(create_registry())

    def discover_repos(self) -> list[Path]:
        if not self.examples_dir.exists():
            return []
        return sorted(
            p for p in self.examples_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".")
            and ((p / "src").exists() or list(p.glob("*.py")))
        )

    def _copy_repo(self, repo_path: Path) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix=f"agira_eval_{repo_path.name}_"))
        shutil.copytree(repo_path, tmp, dirs_exist_ok=True)
        return tmp

    def evaluate_repo(self, repo_path: Path) -> EvalResult:
        work_path = self._copy_repo(repo_path)
        result = self.orchestrator.run(work_path, mode="demo")
        ctx = result.context
        store = ctx.artifact_store

        issues_art = store.latest("issues")
        issues = issues_art.data.get("issues", []) if issues_art and isinstance(issues_art.data, dict) else []
        found_patterns = {i.get("pattern", i.get("type", "")) for i in issues}

        patch_art = store.latest("patch_result")
        patches = patch_art.data.get("patches", []) if patch_art and isinstance(patch_art.data, dict) else ctx.patches_applied
        fixed_patterns = {p.get("pattern") for p in patches if p.get("validated") or p.get("diff")}

        expected = self.EXPECTED_FIXABLE.get(repo_path.name, set())
        fixable_found = found_patterns & expected if expected else found_patterns
        issues_fixed = len(fixed_patterns & fixable_found)
        issues_found = len(fixable_found) or len(found_patterns)

        repair_quality = issues_fixed / max(issues_found, 1)
        false_positives = len(found_patterns - expected) if expected else 0
        false_positive_rate = false_positives / max(len(found_patterns), 1)

        validation = store.latest("validation_result")
        tests_passed = False
        regression_safe = False
        if validation and isinstance(validation.data, dict):
            v = validation.data.get("validation", validation.data)
            tests_passed = v.get("overall_pass", False)
            regression_safe = tests_passed and not v.get("rollback")

        patch_correctness = all(p.get("validated", False) or p.get("diff") for p in patches) if patches else False

        health_art = store.latest("health_score")
        health_score = health_art.data.get("score", 0) if health_art and isinstance(health_art.data, dict) else 0

        return EvalResult(
            repo_name=repo_path.name,
            repo_path=str(repo_path),
            success=result.success,
            tool_calls=result.tool_calls,
            issues_found=issues_found,
            issues_fixed=issues_fixed,
            patches_applied=len(patches),
            tests_passed=tests_passed,
            health_score=health_score,
            repair_quality=repair_quality,
            false_positive_rate=false_positive_rate,
            patch_correctness=patch_correctness,
            regression_safe=regression_safe,
            details={"found": list(found_patterns), "fixed": list(fixed_patterns), "expected": list(expected)},
        )

    def run_all(self) -> EvalSummary:
        repos = self.discover_repos()
        results = [self.evaluate_repo(r) for r in repos]
        n = max(len(results), 1)
        return EvalSummary(
            total_repos=len(results),
            results=results,
            avg_repair_quality=sum(r.repair_quality for r in results) / n,
            avg_health_score=sum(r.health_score for r in results) / n,
            patch_correctness_rate=sum(1 for r in results if r.patch_correctness) / n,
            regression_safe_rate=sum(1 for r in results if r.regression_safe) / n,
            test_pass_rate=sum(1 for r in results if r.tests_passed) / n,
        )

    def run_and_export(self, output_path: str | Path) -> EvalSummary:
        summary = self.run_all()
        Path(output_path).write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
        return summary
