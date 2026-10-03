"""
Plugin system for Barq - extensible capability framework.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging
from pathlib import Path
import importlib.util
import sys

from barqlog import get_logger

log = get_logger("plugins")


class HookPoint(Enum):
    """Extension points in the Barq lifecycle."""
    PRE_COMMAND = "pre_command"
    POST_COMMAND = "post_command"
    ON_WAKE = "on_wake"
    ON_SLEEP = "on_sleep"
    ON_ERROR = "on_error"
    ON_STARTUP = "on_startup"
    ON_SHUTDOWN = "on_shutdown"


@dataclass
class PluginManifest:
    """Plugin metadata."""
    name: str
    version: str
    description: str
    author: str
    hooks: List[HookPoint]
    permissions: List[str]  # Required permissions: "filesystem", "network", "system", "browser"
    config_schema: Dict[str, Any] = None


class PluginContext:
    """Context passed to plugin hooks."""
    def __init__(self, **kwargs):
        self.data = kwargs

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value


class BasePlugin(ABC):
    """Base class for all Barq plugins."""

    _manifest: PluginManifest = None

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._enabled = True
        # Initialize manifest
        if self._manifest is None:
            self._manifest = self.get_manifest()
        self.logger = get_logger(f"plugin.{self._manifest.name}")

    @abstractmethod
    def get_manifest(self) -> PluginManifest:
        """Return plugin metadata."""
        pass

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    @property
    def name(self) -> str:
        return self._manifest.name

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    # Hook implementations (override as needed)
    async def on_startup(self, ctx: PluginContext):
        """Called when Barq starts up."""
        pass

    async def on_shutdown(self, ctx: PluginContext):
        """Called when Barq shuts down."""
        pass

    async def on_wake(self, ctx: PluginContext):
        """Called when wake word is detected."""
        pass

    async def on_sleep(self, ctx: PluginContext):
        """Called when going to sleep."""
        pass

    async def pre_command(self, ctx: PluginContext) -> bool:
        """
        Called before processing a command.
        Return False to stop further processing.
        """
        return True

    async def post_command(self, ctx: PluginContext):
        """Called after command processing completes."""
        pass

    async def on_error(self, ctx: PluginContext):
        """Called when an error occurs."""
        pass


class PluginRegistry:
    """Manages plugin discovery, loading, and hook execution."""

    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._hooks: Dict[HookPoint, List[Callable]] = {h: [] for h in HookPoint}

    def register(self, plugin: BasePlugin) -> bool:
        """Register a plugin instance."""
        manifest = plugin.get_manifest()
        if manifest.name in self._plugins:
            log.warning(f"Plugin {manifest.name} already registered, replacing")
        self._plugins[manifest.name] = plugin
        self._rebuild_hooks()
        log.info(f"Registered plugin: {manifest.name} v{manifest.version}")
        return True

    def unregister(self, name: str) -> bool:
        """Unregister a plugin by name."""
        if name in self._plugins:
            del self._plugins[name]
            self._rebuild_hooks()
            log.info(f"Unregistered plugin: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> List[PluginManifest]:
        """List all registered plugin manifests."""
        return [p.get_manifest() for p in self._plugins.values()]

    def _rebuild_hooks(self):
        """Rebuild hook lists from registered plugins."""
        self._hooks = {h: [] for h in HookPoint}
        for plugin in self._plugins.values():
            if not plugin.enabled:
                continue
            manifest = plugin.get_manifest()
            for hook in manifest.hooks:
                method = getattr(plugin, hook.value, None)
                if method and callable(method):
                    self._hooks[hook].append(method)

    async def execute_hook(self, hook: HookPoint, ctx: PluginContext) -> bool:
        """Execute all callbacks for a hook point.
        Returns False if any pre_command hook returns False.
        """
        for callback in self._hooks.get(hook, []):
            try:
                if hook == HookPoint.PRE_COMMAND:
                    result = await callback(ctx)
                    if result is False:
                        return False
                else:
                    await callback(ctx)
            except Exception as e:
                log.error(f"Hook {hook.value} failed in {callback.__self__.name}: {e}")
                # Continue executing other hooks
        return True

    async def startup(self):
        """Call on_startup for all plugins."""
        ctx = PluginContext()
        await self.execute_hook(HookPoint.ON_STARTUP, ctx)

    async def shutdown(self):
        """Call on_shutdown for all plugins."""
        ctx = PluginContext()
        await self.execute_hook(HookPoint.ON_SHUTDOWN, ctx)


# Global registry instance
registry = PluginRegistry()


def load_plugin_from_file(path: Path) -> Optional[BasePlugin]:
    """Load a plugin from a Python file."""
    try:
        spec = importlib.util.spec_from_file_location("plugin_module", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["plugin_module"] = module
        spec.loader.exec_module(module)

        # Find plugin class (first BasePlugin subclass)
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, BasePlugin) and obj is not BasePlugin:
                return obj()
    except Exception as e:
        log.error(f"Failed to load plugin from {path}: {e}")
    return None


def discover_plugins(plugin_dirs: List[Path]) -> List[BasePlugin]:
    """Discover and load all plugins from directories."""
    plugins = []
    for dir_path in plugin_dirs:
        if not dir_path.exists():
            continue
        for file_path in dir_path.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            plugin = load_plugin_from_file(file_path)
            if plugin:
                plugins.append(plugin)
    return plugins