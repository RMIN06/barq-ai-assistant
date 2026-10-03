"""
Built-in vision plugin for screen analysis.
"""
from plugins import BasePlugin, PluginManifest, HookPoint, PluginContext


class VisionPlugin(BasePlugin):
    """Screen vision - analyze screenshots via Groq Vision."""

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="vision",
            version="1.0.0",
            description="Screen analysis and visual understanding",
            author="Barq",
            hooks=[HookPoint.PRE_COMMAND, HookPoint.POST_COMMAND],
            permissions=["screen_capture"],
            config_schema={
                "model": "llama-3.2-90b-vision-preview",
                "max_width": 1100
            }
        )

    async def pre_command(self, ctx: PluginContext) -> bool:
        command = ctx.get("command", "").lower()
        intent = ctx.get("intent", "")

        if intent == "screen" or "screen" in command or "see" in command or "look" in command:
            pass
        return True

    async def post_command(self, ctx: PluginContext):
        pass


def create_plugin():
    return VisionPlugin()