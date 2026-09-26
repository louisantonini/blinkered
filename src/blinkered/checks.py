"""Validation of manifests, layout and working-tree state."""
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .manifest import Node


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    message: str


def check(root: Path, config: Config, nodes: dict[str, Node]) -> list[Finding]:
    """Manifest errors, unknown targets, cycles, layout-rule violations and plugin findings."""
    raise NotImplementedError


def layout(root: Path, config: Config, nodes: dict[str, Node]) -> list[Finding]:
    """Nested nodes and files in grouping directories outside `grouping_allow`."""
    raise NotImplementedError


def leaving(root: Path, keep: list[str]) -> list[Finding]:
    """Modified, staged, untracked or ignored paths that would leave a view limited to `keep`."""
    raise NotImplementedError
