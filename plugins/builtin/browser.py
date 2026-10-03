"""
Built-in browser plugin for tab management.
"""
from plugins import BasePlugin, PluginManifest, HookPoint, PluginContext


class BrowserPlugin(BasePlugin):
    """Browser tab management capabilities."""

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="browser",
            version="1.0.0",
            description="Manage browser tabs - close, open, list",
            author="Barq",
            hooks=[HookPoint.PRE_COMMAND, HookPoint.POST_COMMAND],
            permissions=["browser"],
            config_schema={
                "supported_browsers": ["chrome", "edge", "firefox", "brave", "vivaldi", "opera"]
            }
        )

    async def pre_command(self, ctx: PluginContext) -> bool:
        """Handle browser-related commands before they reach the LLM."""
        command = ctx.get("command", "").lower()
        intent = ctx.get("intent", "")

        # Only handle if intent is browser or command mentions browser
        if intent != "browser" and "tab" not in command and "browser" not in command:
            return True

        # This plugin enhances browser handling - actual execution
        # happens in screen_context.py but we can intercept here
        return True

    async def post_command(self, ctx: PluginContext):
        """Log browser actions."""
        intent = ctx.get("intent", "")
        if intent == "browser":
            action = ctx.get("action", "")
            subject = ctx.get("subject", "")
            self.logger.info(f"Browser action: {action} {subject}")


# Export for auto-discovery
def create_plugin():
    return BrowserPlugin()