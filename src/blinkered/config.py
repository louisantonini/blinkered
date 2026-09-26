"""Repository configuration: `blinkered.toml` at the repository root."""
from dataclasses import dataclass, field
from pathlib import Path

FILENAME = 'blinkered.toml'


@dataclass(frozen=True)
class Config:
    always: tuple[str, ...] = ()
    grouping_allow: tuple[str, ...] = ('README.md',)
    plugins: dict[str, bool] = field(default_factory=dict)


def load(root: Path) -> Config:
    """Read the root configuration; its absence means the repository is not managed."""
    raise NotImplementedError
