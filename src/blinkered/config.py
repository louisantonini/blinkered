"""Repository configuration: `blinkered.toml` at the repository root."""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

FILENAME = 'blinkered.toml'


class NotManaged(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    nodes_root: str = ''
    always: tuple[str, ...] = ()
    grouping_allow: tuple[str, ...] = ('README.md',)
    plugins: dict[str, dict] = field(default_factory=dict)


def load(root: Path) -> Config:
    """Read the root configuration; its absence means the repository is not managed."""
    path = root / FILENAME
    if not path.is_file():
        raise NotManaged(f'no {FILENAME} at {root}')
    data = tomllib.loads(path.read_text())
    unknown = set(data) - {'nodes_root', 'always', 'grouping_allow', 'plugins'}
    if unknown:
        raise ValueError(f'{FILENAME}: unknown keys {sorted(unknown)}')
    plugins = {}
    for name, value in data.get('plugins', {}).items():
        if value is False:
            continue
        if value is not True and not isinstance(value, dict):
            raise ValueError(f'{FILENAME}: plugins.{name} must be true, false or a table of settings')
        from .plugins import PLUGINS
        if name not in PLUGINS:
            raise ValueError(f'{FILENAME}: unknown plugin {name}')
        settings = {} if value is True else dict(value)
        unknown = set(settings) - PLUGINS[name].SETTINGS
        if unknown:
            raise ValueError(f'{FILENAME}: plugins.{name}: unknown settings {sorted(unknown)}')
        plugins[name] = settings
    return Config(nodes_root=data.get('nodes_root', '').strip('/'),
                  always=tuple(item.strip('/') for item in data.get('always', ())),
                  grouping_allow=tuple(data.get('grouping_allow', Config.grouping_allow)),
                  plugins=plugins)
