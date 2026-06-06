"""Tool registry base types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class ToolSchema:
    type: str = "object"
    properties: dict[str, Any] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "properties": self.properties,
            "required": self.required,
        }


@dataclass
class ToolDefinition:
    name: str
    namespace: str
    description: str
    input_schema: ToolSchema
    output_schema: ToolSchema
    error_type: str
    handler: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]

    @property
    def qualified_name(self) -> str:
        return f"{self.namespace}.{self.name}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "namespace": self.namespace,
            "qualified_name": self.qualified_name,
            "description": self.description,
            "input_schema": self.input_schema.to_dict(),
            "output_schema": self.output_schema.to_dict(),
            "error_type": self.error_type,
        }
