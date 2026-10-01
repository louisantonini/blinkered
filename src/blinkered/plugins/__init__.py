"""Optional language-specific plugins, enabled under `[plugins]` in the root configuration.

A plugin module provides `NAME` (its configuration key), `SETTINGS` (accepted setting keys) and
`check(root, nodes, settings)`; it may also provide `COMMAND`, `HELP`, `arguments(parser)` and
`run(root, config, nodes, settings, args)` to add a subcommand.
"""
from . import python_imports

PLUGINS = {plugin.NAME: plugin for plugin in (python_imports,)}
COMMANDS = {plugin.COMMAND: plugin for plugin in PLUGINS.values() if hasattr(plugin, 'COMMAND')}
