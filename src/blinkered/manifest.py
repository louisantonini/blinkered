"""Node manifests: `blinkered.toml` in any directory other than the repository root."""
import posixpath
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import git
from .config import FILENAME
from .findings import Finding


@dataclass(frozen=True)
class Node:
    name: str
    directory: str
    tags: tuple[str, ...] = ()
    edges: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def targets(self, via=None) -> list[str]:
        return [target for kind, targets in self.edges.items()
                if via is None or kind in via for target in targets]


def discover(root: Path) -> tuple[dict[str, Node], list[Finding]]:
    """All nodes by name, read from the working tree or the index, independent of the view."""
    paths = sorted(set(git.tracked_paths(root)) | set(git.untracked_paths(root)))
    nodes, errors = {}, []
    for path in paths:
        directory, name = posixpath.split(path)
        if name != FILENAME or not directory:
            continue
        try:
            node = parse(directory, git.read_file(root, path))
        except (ValueError, tomllib.TOMLDecodeError) as error:
            errors.append(Finding('manifest', path, str(error)))
            continue
        if node.name in nodes:
            errors.append(Finding('manifest', path,
                                  f'duplicate node name, also {nodes[node.name].directory}'))
            continue
        nodes[node.name] = node
    return nodes, errors


def parse(directory: str, text: str) -> Node:
    """Build a node from its manifest text."""
    data = tomllib.loads(text)
    unknown = set(data) - {'tags', 'edges'}
    if unknown:
        raise ValueError(f'unknown keys {sorted(unknown)}')
    tags = data.get('tags', [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError('tags must be a list of strings')
    edges = data.get('edges', {})
    if not isinstance(edges, dict):
        raise ValueError('edges must be a table')
    for kind, targets in edges.items():
        if not isinstance(targets, list) or not all(isinstance(t, str) for t in targets):
            raise ValueError(f'edges.{kind} must be a list of node names')
    return Node(name=posixpath.basename(directory), directory=directory, tags=tuple(tags),
                edges={kind: tuple(targets) for kind, targets in edges.items()})
