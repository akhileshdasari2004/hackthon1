"""Safe subprocess execution sandbox."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agira.observability.errors import TimeoutError as AgiraTimeoutError


@dataclass
class SandboxResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "duration_ms": self.duration_ms,
            "success": self.returncode == 0 and not self.timed_out,
        }


class SandboxExecutor:
    """Deterministic subprocess wrapper with timeout and output capture."""

    def __init__(self, default_timeout: float = 120.0) -> None:
        self.default_timeout = default_timeout

    def run(
        self,
        command: list[str],
        *,
        cwd: str | Path | None = None,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        import time

        timeout = timeout or self.default_timeout
        start = time.monotonic()
        try:
            proc = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            duration = (time.monotonic() - start) * 1000
            return SandboxResult(
                command=command,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=duration,
            )
        except subprocess.TimeoutExpired as exc:
            duration = (time.monotonic() - start) * 1000
            raise AgiraTimeoutError(
                f"Command timed out after {timeout}s: {' '.join(command)}",
                details={"command": command, "duration_ms": duration},
            ) from exc

    def run_python(
        self,
        script: str,
        *,
        cwd: str | Path | None = None,
        timeout: float | None = None,
    ) -> SandboxResult:
        return self.run(
            [sys.executable, "-c", script],
            cwd=cwd,
            timeout=timeout,
        )

    def run_script_file(
        self,
        script_path: str | Path,
        args: list[str] | None = None,
        *,
        cwd: str | Path | None = None,
        timeout: float | None = None,
    ) -> SandboxResult:
        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)
        return self.run(cmd, cwd=cwd, timeout=timeout)
