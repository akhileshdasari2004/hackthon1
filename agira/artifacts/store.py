"""Typed versioned artifact store for compositional tool execution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Artifact:
    artifact_id: str
    artifact_type: str
    data: Any
    version: int = 1
    producer: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "version": self.version,
            "producer": self.producer,
            "created_at": self.created_at,
            "dependencies": self.dependencies,
            "data": self.data,
        }


class ArtifactStore:
    """Central artifact registry — all tool I/O flows through artifact IDs."""

    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}
        self._by_type: dict[str, list[str]] = {}

    def put(
        self,
        artifact_type: str,
        data: Any,
        *,
        producer: str = "",
        dependencies: list[str] | None = None,
        artifact_id: str | None = None,
    ) -> str:
        aid = artifact_id or str(uuid.uuid4())
        existing = self._artifacts.get(aid)
        version = (existing.version + 1) if existing else 1
        artifact = Artifact(
            artifact_id=aid,
            artifact_type=artifact_type,
            data=data,
            version=version,
            producer=producer,
            dependencies=dependencies or [],
        )
        self._artifacts[aid] = artifact
        self._by_type.setdefault(artifact_type, []).append(aid)
        return aid

    def get(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    def get_data(self, artifact_id: str) -> Any:
        artifact = self.get(artifact_id)
        if artifact is None:
            raise KeyError(f"Artifact not found: {artifact_id}")
        return artifact.data

    def latest(self, artifact_type: str) -> Artifact | None:
        ids = self._by_type.get(artifact_type, [])
        if not ids:
            return None
        return self._artifacts[ids[-1]]

    def latest_id(self, artifact_type: str) -> str | None:
        artifact = self.latest(artifact_type)
        return artifact.artifact_id if artifact else None

    def has_type(self, artifact_type: str) -> bool:
        return bool(self._by_type.get(artifact_type))

    def resolve_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Resolve artifact_id references in tool params."""
        resolved = dict(params)
        for key, value in params.items():
            if key.endswith("_artifact_id") and isinstance(value, str):
                data_key = key.replace("_artifact_id", "")
                resolved[data_key] = self.get_data(value)
            elif key == "artifact_id" and isinstance(value, str):
                resolved["_artifact_data"] = self.get_data(value)
        return resolved

    def to_dict(self) -> dict[str, Any]:
        return {aid: a.to_dict() for aid, a in self._artifacts.items()}

    def from_dict(self, data: dict[str, Any]) -> None:
        for aid, raw in data.items():
            self._artifacts[aid] = Artifact(
                artifact_id=raw["artifact_id"],
                artifact_type=raw["artifact_type"],
                data=raw["data"],
                version=raw.get("version", 1),
                producer=raw.get("producer", ""),
                created_at=raw.get("created_at", ""),
                dependencies=raw.get("dependencies", []),
            )
            self._by_type.setdefault(raw["artifact_type"], []).append(aid)
