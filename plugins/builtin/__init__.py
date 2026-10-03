"""Built-in plugins package."""
from .browser import create_plugin as create_browser_plugin
from .filesystem import create_plugin as create_filesystem_plugin
from .system import create_plugin as create_system_plugin
from .code_exec import create_plugin as create_code_exec_plugin
from .vision import create_plugin as create_vision_plugin
from .memory import create_plugin as create_memory_plugin

BUILTIN_PLUGINS = [
    create_browser_plugin,
    create_filesystem_plugin,
    create_system_plugin,
    create_code_exec_plugin,
    create_vision_plugin,
    create_memory_plugin,
]

__all__ = ["BUILTIN_PLUGINS"]