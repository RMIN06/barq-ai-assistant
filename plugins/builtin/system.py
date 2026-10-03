"""
Built-in system plugin for app launching and system commands.
"""
from plugins import BasePlugin, PluginManifest, HookPoint, PluginContext


class SystemPlugin(BasePlugin):
    """System operations - app launching, process management."""

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="system",
            version="1.0.0",
            description="System operations - launch apps, manage processes",
            author="Barq",
            hooks=[HookPoint.PRE_COMMAND, HookPoint.POST_COMMAND],
            permissions=["system"],
            config_schema={
                "app_shortcuts": {
                    "calculator": "calc",
                    "notepad": "notepad",
                    "paint": "mspaint",
                    "explorer": "explorer",
                    "taskmgr": "taskmgr",
                    "settings": "ms-settings:"
                }
            }
        )

    async def pre_command(self, ctx: PluginContext) -> bool:
        return True

    async def post_command(self, ctx: PluginContext):
        pass


def create_plugin():
    return SystemPlugin()