"""Safe subprocess execution sandbox.

Production enforcement:
    AGIRA_SANDBOX_MODE must be set to "docker" in production.
    If not set, the system fails fast with a clear error message.
    No fallback to bare subprocess.run() in production builds.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agira.observability.errors import TimeoutError as AgiraTimeoutError


# Default safety limits
DEFAULT_TIMEOUT = float(os.environ.get("AGIRA_SANDBOX_TIMEOUT", "120"))
DEFAULT_MAX_REPO_SIZE_MB = int(os.environ.get("AGIRA_MAX_REPO_SIZE_MB", "200"))
DEFAULT_GLOBAL_JOB_TIMEOUT = float(os.environ.get("AGIRA_GLOBAL_JOB_TIMEOUT", "3600"))  # 1 hour


@dataclass
class SandboxResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_ms: float = 0.0
    job_id: str | None = None
    node: str | None = None
    image: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "duration_ms": self.duration_ms,
            "success": self.returncode == 0 and not self.timed_out,
            "job_id": self.job_id,
            "node": self.node,
            "image": self.image,
        }


# Sentinel for unconfigured mode
_UNSET = object()


class SandboxExecutor:
    """Deterministic subprocess wrapper with timeout and output capture.

    Production mode (AGIRA_SANDBOX_MODE=docker):
        All commands execute inside a security-hardened Docker container
        via scripts/sandbox_runner.py, with:
            --network=none  --read-only  --tmpfs /tmp
            --memory=256m   --pids-limit=64  --cap-drop=ALL
            --no-new-privileges  -u 1000:1000

    If AGIRA_SANDBOX_MODE is not set to "docker", the executor raises
    RuntimeError immediately — there is no fallback subprocess path in
    production. This enforces sandbox isolation at the execution layer.
    """

    def __init__(
        self,
        default_timeout: float = DEFAULT_TIMEOUT,
        max_repo_size_mb: int = DEFAULT_MAX_REPO_SIZE_MB,
        global_job_timeout: float = DEFAULT_GLOBAL_JOB_TIMEOUT,
    ) -> None:
        self.default_timeout = default_timeout
        self.max_repo_size_mb = max_repo_size_mb
        self.global_job_timeout = global_job_timeout
        self._job_start_time: float | None = None

    def run(
        self,
        command: list[str],
        *,
        cwd: str | Path | None = None,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
        job_id: str | None = None,
        node: str | None = None,
    ) -> SandboxResult:
        sandbox_mode = os.environ.get("AGIRA_SANDBOX_MODE", "").strip()

        if sandbox_mode != "docker":
            raise RuntimeError(
                f"SANDBOX ISOLATION REQUIRED IN PRODUCTION.\n"
                f"Set AGIRA_SANDBOX_MODE=docker to enable Docker-based sandbox.\n"
                f"Current value: '{sandbox_mode or '(not set)'}'.\n"
                f"No host-level subprocess execution is permitted in production."
            )

        # Check global job timeout
        if self._job_start_time is None:
            self._job_start_time = time.monotonic()
        elapsed = time.monotonic() - self._job_start_time
        if elapsed > self.global_job_timeout:
            raise AgiraTimeoutError(
                f"Global job timeout exceeded: {elapsed:.1f}s > {self.global_job_timeout}s",
                details={"elapsed_s": elapsed, "limit_s": self.global_job_timeout},
            )

        # Check per-node timeout
        effective_timeout = min(timeout or self.default_timeout, self.default_timeout)

        result = self._run_via_sandbox_runner(
            command, cwd=cwd, timeout=effective_timeout, env=env,
        )
        result.job_id = job_id
        result.node = node
        return result

    def _run_via_sandbox_runner(
        self,
        command: list[str],
        *,
        cwd: str | Path | None = None,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        """Execute via scripts/sandbox_runner.py — Docker sandbox only.

        The sandbox_runner.py script is invoked as a subprocess. It accepts
        the target command as positional arguments after a "--" separator
        and runs everything inside a security-hardened container.
        """
        timeout = timeout or self.default_timeout
        start = time.monotonic()

        image = os.environ.get(
            "AGIRA_SANDBOX_IMAGE",
            "ghcr.io/akhileshdasari2004/hackthon1/sandbox:latest",
        )

        # Build the sandbox_runner.py invocation
        # The target command is appended after "--"
        sandbox_cmd = [
            sys.executable,
            str(Path(__file__).parent.parent / "scripts" / "sandbox_runner.py"),
            "--timeout", str(int(timeout)),
            "--image", image,
        ]
        if cwd:
            sandbox_cmd.extend(["--workdir", str(cwd)])
        sandbox_cmd.append("--")
        sandbox_cmd.extend(command)

        try:
            proc = subprocess.run(
                sandbox_cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 10,  # outer timeout slightly larger than sandbox's
                env=env,
            )
            duration = (time.monotonic() - start) * 1000
            timed_out = "Timed out after" in proc.stderr
            result = SandboxResult(
                command=command,
                returncode=proc.returncode if not timed_out else -1,
                stdout=proc.stdout,
                stderr=proc.stderr,
                timed_out=timed_out,
                duration_ms=duration,
                image=image,
            )
            return result
        except subprocess.TimeoutExpired:
            duration = (time.monotonic() - start) * 1000
            raise AgiraTimeoutError(
                f"Sandbox outer timeout after {timeout + 10}s: {' '.join(command)}",
                details={"command": command, "duration_ms": duration},
            ) from None

    def run_python(
        self,
        script: str,
        *,
        cwd: str | Path | None = None,
        timeout: float | None = None,
        job_id: str | None = None,
        node: str | None = None,
    ) -> SandboxResult:
        result = self.run(
            [sys.executable, "-c", script],
            cwd=cwd,
            timeout=timeout,
            job_id=job_id,
            node=node,
        )
        return result

    def run_script_file(
        self,
        script_path: str | Path,
        args: list[str] | None = None,
        *,
        cwd: str | Path | None = None,
        timeout: float | None = None,
        job_id: str | None = None,
        node: str | None = None,
    ) -> SandboxResult:
        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)
        return self.run(cmd, cwd=cwd, timeout=timeout, job_id=job_id, node=node)

    def check_repo_size(self, repo_path: str | Path) -> bool:
        """Check if repo size is within limits. Returns True if OK, False if over limit."""
        repo_path = Path(repo_path)
        if not repo_path.exists():
            return True  # Will be caught elsewhere
        total_bytes = 0
        for entry in repo_path.rglob("*"):
            if entry.is_file():
                try:
                    total_bytes += entry.stat().st_size
                except OSError:
                    pass
        size_mb = total_bytes / (1024 * 1024)
        return size_mb <= self.max_repo_size_mb

    def reset_job_timer(self) -> None:
        """Reset the global job timer. Call at job start."""
        self._job_start_time = time.monotonic()
