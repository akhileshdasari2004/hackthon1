#!/usr/bin/env python3
"""
Agira Sandbox Runner — Docker-based isolated code execution.

This script wraps arbitrary command execution inside a security-hardened
Docker container with:
  - No network access
  - Read-only root filesystem
  - CPU and memory limits
  - No new privileges

This is NOT a modification of the core sandbox — it's a production-hardened
alternative that can be enabled via environment variable.

Usage (standalone):
    python3 scripts/sandbox_runner.py -- command [args...]

Environment:
    AGIRA_SANDBOX_IMAGE   Docker image for sandbox (default: agira/sandbox:latest)
    AGIRA_SANDBOX_TIMEOUT Max execution time in seconds (default: 120)
    AGIRA_JOB_ID          Job ID for audit correlation
    AGIRA_NODE_NAME       DAG node name for audit correlation
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SandboxResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_ms: float
    job_id: str = ""
    node: str = ""
    trace_id: str = ""
    image: str = ""

    def to_dict(self) -> dict:
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
            "trace_id": self.trace_id,
            "image": self.image,
        }


def run_in_docker(
    command: list[str],
    *,
    timeout: float = 120.0,
    image: str = "agira/sandbox:latest",
    work_dir: str | Path | None = None,
) -> SandboxResult:
    """Execute a command inside a security-hardened Docker container.

    Security measures applied:
    - --network=none        : No network access
    - --read-only           : Read-only root filesystem
    - --tmpfs /tmp          : Writable /tmp only (no persistance)
    - --cpu-period + quota  : CPU limit
    - --memory             : Memory limit
    - --pids-limit         : Max processes
    - --cap-drop=ALL        : No Linux capabilities
    - --security-opt        : No new privileges
    - --user               : Runs as non-root (uid 1000)
    """
    start = time.monotonic()
    timed_out = False

    # Capture audit correlation IDs from environment
    job_id = os.environ.get("AGIRA_JOB_ID", "")
    node = os.environ.get("AGIRA_NODE_NAME", "")
    trace_id = os.environ.get("AGIRA_TRACE_ID", "")

    cmd = [
        "docker", "run",
        "--rm",                              # Remove container after exit
        "--network=none",                    # No network
        "--read-only",                       # Read-only root
        "--tmpfs", "/tmp:rw,noexec,nosuid",  # Writable /tmp only
        "--pids-limit", "64",                # Max 64 processes
        "--cap-drop=ALL",                    # Drop all capabilities
        "--security-opt=no-new-privileges",  # No privilege escalation
        "--cpu-quota=50000",                 # 0.5 CPU (50ms per 100ms)
        "--memory=256m",                     # 256MB max
        "--memory-swap=256m",                # No swap
        "-u", "1000:1000",                   # Run as non-root
        f"--workdir={work_dir or '/sandbox'}",
        "--log-driver=none",                 # No logging of command
        image,
        *command,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        returncode = -1
        timed_out = True

    duration_ms = (time.monotonic() - start) * 1000

    result = SandboxResult(
        command=" ".join(command),
        returncode=returncode,
        stdout=proc.stdout if not timed_out else "",
        stderr=proc.stderr if not timed_out else f"Timed out after {timeout}s",
        timed_out=timed_out,
        duration_ms=duration_ms,
        job_id=job_id,
        node=node,
        trace_id=trace_id,
        image=image,
    )

    # Write audit log entry
    _write_audit_log(result)

    return result


def _write_audit_log(result: SandboxResult) -> None:
    """Write audit log entry to /data/audit.log."""
    audit_path = os.environ.get("AGIRA_AUDIT_PATH", "/data/audit.log")
    if not audit_path:
        return
    try:
        audit_dir = os.path.dirname(audit_path)
        if audit_dir:
            os.makedirs(audit_dir, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "job_id": result.job_id,
            "node": result.node,
            "command": result.command,
            "image": result.image,
            "status": "timeout" if result.timed_out else ("success" if result.returncode == 0 else "failed"),
            "exit_code": result.returncode,
            "duration_ms": round(result.duration_ms, 2),
            "trace_id": result.trace_id,
        }
        # Filter empty strings
        entry = {k: v for k, v in entry.items() if v}
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
            f.flush()
    except Exception:
        pass  # Never fail due to audit logging


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run command in Docker sandbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 sandbox_runner.py -- pytest tests/ -v
    python3 sandbox_runner.py -- python3 -m py_compile app.py
    python3 sandbox_runner.py -- mypy src/ --ignore-missing-imports
        """,
    )
    parser.add_argument(
        "--timeout", "-t", type=float, default=120.0,
        help="Timeout in seconds (default: 120)"
    )
    parser.add_argument(
        "--image", "-i", default="agira/sandbox:latest",
        help="Sandbox Docker image (default: agira/sandbox:latest)"
    )
    parser.add_argument(
        "--workdir", "-w", default="/sandbox",
        help="Working directory inside container"
    )
    parser.add_argument(
        "--json", "-j", action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument("command", nargs="+", help="Command to execute")

    args = parser.parse_args()

    result = run_in_docker(
        args.command,
        timeout=args.timeout,
        image=args.image,
        work_dir=args.workdir,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        print(f"[sandbox] exit={result.returncode} duration={result.duration_ms:.0f}ms", file=sys.stderr)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())