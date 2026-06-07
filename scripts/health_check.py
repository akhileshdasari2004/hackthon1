#!/usr/bin/env python3
"""Agira health check script — used by Docker HEALTHCHECK and k8s probes."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Verify the agira package is importable
try:
    import agira
    from agira.orchestrator.engine import Orchestrator
    from agira.registry.registry import create_registry
    from agira.version import __version__ as version
except ImportError as e:
    print(f"IMPORT_ERROR: {e}", file=sys.stderr)
    sys.exit(1)

# Verify data directories are writable
jobs_dir = os.environ.get("AGIRA_JOBS_DIR", "/data/jobs")
memory_path = os.environ.get("AGIRA_MEMORY_PATH", "/data/memory_store.json")

paths_to_check = [jobs_dir, memory_path]
for p in paths_to_check:
    path = Path(p)
    try:
        path.mkdir(parents=True, exist_ok=True)
        # Test write
        test_file = path / ".health_check"
        test_file.write_text("ok")
        test_file.unlink()
    except PermissionError:
        print(f"PERMISSION_ERROR: cannot write to {p}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

print(json.dumps({
    "status": "ok",
    "service": "agira-backend",
    "version": getattr(agira, "__version__", "0.1.0"),
    "python_version": sys.version,
    "jobs_dir": jobs_dir,
    "tools_count": create_registry().count(),
}))
sys.exit(0)