"""
Built-in code execution plugin using Open Interpreter.
"""
from plugins import BasePlugin, PluginManifest, HookPoint, PluginContext


class CodeExecPlugin(BasePlugin):
    """Code execution capabilities via Open Interpreter."""

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="code_exec",
            version="1.0.0",
            description="Execute code and scripts via Open Interpreter",
            author="Barq",
            hooks=[HookPoint.PRE_COMMAND, HookPoint.POST_COMMAND],
            permissions=["system", "network"],
            config_schema={
                "auto_run": True,
                "timeout_seconds": 60,
                "allowed_languages": ["python", "bash", "javascript"]
            }
        )

    async def pre_command(self, ctx: PluginContext) -> bool:
        command = ctx.get("command", "").lower()
        intent = ctx.get("intent", "")

        # Could intercept code execution commands here
        if intent == "system" and any(kw in command for kw in ["run", "execute", "script", "code"]):
            pass
        return True

    async def post_command(self, ctx: PluginContext):
        pass


def create_plugin():
    return CodeExecPlugin()