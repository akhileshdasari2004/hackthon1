from agira.registry.registry import ToolRegistry, create_registry
from agira.subagents.base import BaseSubagent, SubagentResult
from agira.subagents.bug_hunter import BugHunterAgent
from agira.subagents.patch_generator import PatchGeneratorAgent
from agira.subagents.repo_analyzer import RepoAnalyzerAgent
from agira.subagents.test_validation import TestValidationAgent

_SUBAGENT_TYPES: dict[str, type[BaseSubagent]] = {
    "RepoAnalyzerAgent": RepoAnalyzerAgent,
    "BugHunterAgent": BugHunterAgent,
    "PatchGeneratorAgent": PatchGeneratorAgent,
    "TestValidationAgent": TestValidationAgent,
}

_registry: ToolRegistry | None = None


def _get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = create_registry()
    return _registry


def get_subagent(agent_type: str) -> BaseSubagent:
    if agent_type not in _SUBAGENT_TYPES:
        raise ValueError(
            f"Unknown subagent: {agent_type}. Available: {list(_SUBAGENT_TYPES)}"
        )
    return _SUBAGENT_TYPES[agent_type](_get_registry())


__all__ = [
    "BaseSubagent",
    "SubagentResult",
    "RepoAnalyzerAgent",
    "BugHunterAgent",
    "PatchGeneratorAgent",
    "TestValidationAgent",
    "get_subagent",
]
