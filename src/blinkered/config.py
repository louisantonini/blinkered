"""Repository configuration: `blinkered.toml` at the repository root."""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

FILENAME = 'blinkered.toml'


class NotManaged(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    always: tuple[str, ...] = ()
    grouping_allow: tuple[str, ...] = ('README.md',)
    plugins: dict[str, bool] = field(default_factory=dict)


def load(root: Path) -> Config:
    """Read the root configuration; its absence means the repository is not managed."""
    path = root / FILENAME
    if not path.is_file():
        raise NotManaged(f'no {FILENAME} at {root}')
    data = tomllib.loads(path.read_text())
    unknown = set(data) - {'always', 'grouping_allow', 'plugins'}
    if unknown:
        raise ValueError(f'{FILENAME}: unknown keys {sorted(unknown)}')
    return Config(always=tuple(item.strip('/') for item in data.get('always', ())),
                  grouping_allow=tuple(data.get('grouping_allow', Config.grouping_allow)),
                  plugins=dict(data.get('plugins', {})))
