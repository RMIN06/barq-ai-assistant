"""Tests for plugin system."""
import pytest
from plugins import (
    BasePlugin, PluginManifest, HookPoint, PluginContext,
    PluginRegistry, registry
)
from plugins.builtin import BUILTIN_PLUGINS


def test_plugin_manifest():
    manifest = PluginManifest(
        name="test",
        version="1.0.0",
        description="Test plugin",
        author="Test",
        hooks=[HookPoint.PRE_COMMAND],
        permissions=["test"]
    )
    assert manifest.name == "test"
    assert manifest.version == "1.0.0"
    assert HookPoint.PRE_COMMAND in manifest.hooks


def test_plugin_context():
    ctx = PluginContext(command="test", intent="conversation")
    assert ctx.get("command") == "test"
    assert ctx.get("intent") == "conversation"
    assert ctx.get("missing", "default") == "default"
    ctx.set("new_key", "value")
    assert ctx.get("new_key") == "value"


def test_base_plugin():
    class TestPlugin(BasePlugin):
        def get_manifest(self):
            return PluginManifest(
                name="test",
                version="1.0.0",
                description="Test",
                author="Test",
                hooks=[HookPoint.PRE_COMMAND],
                permissions=[]
            )

    plugin = TestPlugin({"config_key": "value"})
    # Name comes from manifest
    assert plugin.name == "test"
    assert plugin.enabled is True
    assert plugin.config["config_key"] == "value"

    plugin.disable()
    assert plugin.enabled is False

    plugin.enable()
    assert plugin.enabled is True


@pytest.mark.asyncio
async def test_registry_register():
    reg = PluginRegistry()

    class TestPlugin(BasePlugin):
        def get_manifest(self):
            return PluginManifest(
                name="test_plugin",
                version="1.0.0",
                description="Test",
                author="Test",
                hooks=[HookPoint.PRE_COMMAND, HookPoint.ON_WAKE],
                permissions=[]
            )

        async def pre_command(self, ctx):
            return True

        async def on_wake(self, ctx):
            pass

    plugin = TestPlugin()
    reg.register(plugin)

    assert reg.get("test_plugin") is plugin
    assert len(reg.list_plugins()) == 1
    assert reg.list_plugins()[0].name == "test_plugin"


@pytest.mark.asyncio
async def test_registry_hooks():
    reg = PluginRegistry()

    class TestPlugin(BasePlugin):
        def get_manifest(self):
            return PluginManifest(
                name="hook_test",
                version="1.0.0",
                description="Test",
                author="Test",
                hooks=[HookPoint.PRE_COMMAND],
                permissions=[]
            )

        pre_command_called = False

        async def pre_command(self, ctx):
            self.pre_command_called = True
            return True

    plugin = TestPlugin()
    reg.register(plugin)

    ctx = PluginContext(command="test")
    result = await reg.execute_hook(HookPoint.PRE_COMMAND, ctx)
    assert result is True
    assert plugin.pre_command_called is True


@pytest.mark.asyncio
async def test_registry_pre_command_block():
    reg = PluginRegistry()

    class BlockingPlugin(BasePlugin):
        def get_manifest(self):
            return PluginManifest(
                name="blocker",
                version="1.0.0",
                description="Blocks commands",
                author="Test",
                hooks=[HookPoint.PRE_COMMAND],
                permissions=[]
            )

        async def pre_command(self, ctx):
            return False  # Block

    class AllowingPlugin(BasePlugin):
        def get_manifest(self):
            return PluginManifest(
                name="allower",
                version="1.0.0",
                description="Allows commands",
                author="Test",
                hooks=[HookPoint.PRE_COMMAND],
                permissions=[]
            )

        pre_command_called = False

        async def pre_command(self, ctx):
            self.pre_command_called = True
            return True

    blocker = BlockingPlugin()
    allower = AllowingPlugin()
    reg.register(blocker)
    reg.register(allower)

    ctx = PluginContext(command="test")
    result = await reg.execute_hook(HookPoint.PRE_COMMAND, ctx)
    assert result is False  # Blocked by first plugin
    assert allower.pre_command_called is False  # Second not called


@pytest.mark.asyncio
async def test_builtin_plugins_load():
    """Test that all builtin plugins can be instantiated."""
    for create_fn in BUILTIN_PLUGINS:
        plugin = create_fn()
        assert isinstance(plugin, BasePlugin)
        manifest = plugin.get_manifest()
        assert manifest.name
        assert manifest.version
        assert isinstance(manifest.hooks, list)
        assert len(manifest.hooks) > 0


@pytest.mark.asyncio
async def test_registry_startup_shutdown():
    reg = PluginRegistry()

    class LifecyclePlugin(BasePlugin):
        def get_manifest(self):
            return PluginManifest(
                name="lifecycle",
                version="1.0.0",
                description="Test lifecycle",
                author="Test",
                hooks=[HookPoint.ON_STARTUP, HookPoint.ON_SHUTDOWN],
                permissions=[]
            )

        startup_called = False
        shutdown_called = False

        async def on_startup(self, ctx):
            self.startup_called = True

        async def on_shutdown(self, ctx):
            self.shutdown_called = True

    plugin = LifecyclePlugin()
    reg.register(plugin)

    await reg.startup()
    assert plugin.startup_called is True

    await reg.shutdown()
    assert plugin.shutdown_called is True