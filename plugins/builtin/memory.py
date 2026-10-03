"""
Built-in memory plugin for conversation persistence.
"""
from plugins import BasePlugin, PluginManifest, HookPoint, PluginContext


class MemoryPlugin(BasePlugin):
    """Persistent memory across sessions."""

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="memory",
            version="1.0.0",
            description="Conversation history and fact persistence",
            author="Barq",
            hooks=[HookPoint.ON_STARTUP, HookPoint.ON_SHUTDOWN, HookPoint.POST_COMMAND],
            permissions=[],
            config_schema={
                "max_history_turns": 12,
                "storage_path": "barq_data/memory.json"
            }
        )

    async def on_startup(self, ctx: PluginContext):
        self.logger.info("Memory plugin initialized")

    async def on_shutdown(self, ctx: PluginContext):
        self.logger.info("Memory plugin shutting down")

    async def post_command(self, ctx: PluginContext):
        pass


def create_plugin():
    return MemoryPlugin()