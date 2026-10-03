"""
Built-in filesystem plugin for file operations.
"""
from plugins import BasePlugin, PluginManifest, HookPoint, PluginContext


class FilesystemPlugin(BasePlugin):
    """Filesystem operations - read, write, list, search."""

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="filesystem",
            version="1.0.0",
            description="File operations - read, write, list, search",
            author="Barq",
            hooks=[HookPoint.PRE_COMMAND, HookPoint.POST_COMMAND],
            permissions=["filesystem"],
            config_schema={
                "allowed_paths": ["~/Documents", "~/Desktop", "~/Downloads"],
                "max_file_size_mb": 10
            }
        )

    async def pre_command(self, ctx: PluginContext) -> bool:
        command = ctx.get("command", "").lower()
        # Could add filesystem command detection here
        return True

    async def post_command(self, ctx: PluginContext):
        pass


def create_plugin():
    return FilesystemPlugin()