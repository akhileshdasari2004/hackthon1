"""File-based checkpoint persistence for resumable execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CheckpointManager:
    def __init__(self, checkpoint_dir: str | Path | None = None) -> None:
        self.checkpoint_dir = Path(checkpoint_dir or Path.cwd() / ".agira_checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, plan_id: str) -> Path:
        return self.checkpoint_dir / f"{plan_id}.json"

    def save(self, plan_id: str, state: dict[str, Any]) -> Path:
        path = self.path_for(plan_id)
        path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        return path

    def load(self, plan_id: str) -> dict[str, Any] | None:
        path = self.path_for(plan_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def latest(self) -> dict[str, Any] | None:
        files = sorted(self.checkpoint_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not files:
            return None
        return json.loads(files[-1].read_text(encoding="utf-8"))
