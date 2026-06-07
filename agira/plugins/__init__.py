"""Plugin system for extensible analyzers, patchers, validators, and subagents."""

from __future__ import annotations

import importlib
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class Plugin(ABC):
    """Base class for all plugins."""

    name: str = "base"
    version: str = "1.0.0"
    category: str = "general"

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the plugin with the given context.
        
        Args:
            context: Dict with 'repo_path', 'artifacts', 'config', etc.
            
        Returns:
            Dict with 'success', 'result', 'artifacts' keys.
        """
        ...

    def validate(self) -> bool:
        """Return True if plugin configuration is valid."""
        return True


class PluginRegistry:
    """Central registry for all plugins.
    
    Loads plugins from:
    - Built-in agira.plugins.analyzers / patchers / validators / subagents
    - External plugin paths registered via register_plugin_path()
    """

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._by_category: dict[str, list[str]] = {}
        self._plugin_paths: list[Path] = []

    def register(self, plugin: Plugin) -> None:
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin already registered: {plugin.name}")
        self._plugins[plugin.name] = plugin
        self._by_category.setdefault(plugin.category, []).append(plugin.name)

    def unregister(self, name: str) -> None:
        if name not in self._plugins:
            return
        plugin = self._plugins.pop(name)
        self._by_category[plugin.category].remove(name)

    def get(self, name: str) -> Plugin | None:
        return self._plugins.get(name)

    def list_plugins(self, category: str | None = None) -> list[dict[str, str]]:
        if category:
            names = self._by_category.get(category, [])
            return [
                {"name": self._plugins[n].name, "version": self._plugins[n].version}
                for n in names
            ]
        return [
            {"name": p.name, "version": p.version, "category": p.category}
            for p in self._plugins.values()
        ]

    def execute(self, name: str, context: dict[str, Any]) -> dict[str, Any]:
        plugin = self.get(name)
        if not plugin:
            return {"success": False, "error": f"Plugin not found: {name}"}
        try:
            result = plugin.execute(context)
            return {"success": True, "result": result}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc), "plugin": name}

    def register_plugin_path(self, path: str | Path) -> None:
        """Register an external plugin directory."""
        p = Path(path).resolve()
        if p not in self._plugin_paths:
            self._plugin_paths.append(p)
            if str(p.parent) not in sys.path:
                sys.path.insert(0, str(p.parent))

    def load_external_plugins(self) -> int:
        """Discover and load external plugins from registered paths."""
        loaded = 0
        for plugin_path in self._plugin_paths:
            if not plugin_path.exists():
                continue
            for subdir in ["analyzers", "patchers", "validators", "subagents"]:
                plugin_dir = plugin_path / subdir
                if not plugin_dir.is_dir():
                    continue
                for py_file in plugin_dir.glob("*.py"):
                    if py_file.name.startswith("_"):
                        continue
                    module_name = f"{plugin_path.name}.{subdir}.{py_file.stem}"
                    try:
                        mod = importlib.import_module(module_name)
                        for attr_name in dir(mod):
                            attr = getattr(mod, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, Plugin)
                                and attr is not Plugin
                            ):
                                self.register(attr())
                                loaded += 1
                    except Exception as exc:  # noqa: BLE001
                        # Plugin file failed to load — report but continue
                        import sys as _sys
                        print(f"[agira] plugin skip {py_file.name}: {exc}", file=_sys.stderr)
        return loaded


# Global singleton
_plugin_registry: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    global _plugin_registry
    if _plugin_registry is None:
        _plugin_registry = PluginRegistry()
        _load_builtin_plugins()
    return _plugin_registry


def _load_builtin_plugins() -> None:
    """Load built-in plugins from agira.plugins subdirectories."""
    from agira.plugins.analyzers import BuiltInAnalyzers
    from agira.plugins.patchers import BuiltInPatchers
    from agira.plugins.validators import BuiltInValidators

    for plugin_cls in BuiltInAnalyzers:
        get_plugin_registry().register(plugin_cls())
    for plugin_cls in BuiltInPatchers:
        get_plugin_registry().register(plugin_cls())
    for plugin_cls in BuiltInValidators:
        get_plugin_registry().register(plugin_cls())


# ─── Built-in plugin categories ──────────────────────────────────────────────
# These are populated by scanning the agira/plugins/<category>/ directory
# for Python files that define Plugin subclasses.