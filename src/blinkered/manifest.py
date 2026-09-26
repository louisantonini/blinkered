"""Node manifests: `blinkered.toml` in any directory other than the repository root."""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Node:
    name: str
    directory: str
    tags: tuple[str, ...] = ()
    edges: dict[str, tuple[str, ...]] = field(default_factory=dict)


def discover(root: Path) -> dict[str, Node]:
    """All nodes by name, read from the working tree or the index, independent of the view."""
    raise NotImplementedError


def parse(directory: str, text: str) -> Node:
    """Build a node from its manifest text."""
    raise NotImplementedError
