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
    id: str
    directory: str
    tags: tuple[str, ...] = ()
    edges: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def short(self) -> str:
        return self.id.rsplit('/', 1)[-1]

    def references(self, via=None) -> list[str]:
        """Edge targets as written: full ids or short names."""
        return [target for kind, targets in self.edges.items()
                if via is None or kind in via for target in targets]


def node_id(directory: str, nodes_root: str) -> str | None:
    """Path of `directory` relative to `nodes_root`; None when outside it."""
    if not nodes_root:
        return directory
    if directory.startswith(nodes_root + '/'):
        return directory[len(nodes_root) + 1:]
    return None


def discover(root: Path, nodes_root: str = '') -> tuple[dict[str, Node], list[Finding]]:
    """All nodes by id, read from the working tree or the index, independent of the view."""
    paths = sorted(set(git.tracked_paths(root)) | set(git.untracked_paths(root)))
    nodes, errors = {}, []
    for path in paths:
        directory, name = posixpath.split(path)
        if name != FILENAME or not directory:
            continue
        id = node_id(directory, nodes_root)
        if id is None:
            where = 'at' if directory == nodes_root else 'outside'
            errors.append(Finding('layout', path, f'node {where} nodes_root {nodes_root}'))
            continue
        try:
            node = parse(directory, git.read_file(root, path), id=id)
        except (ValueError, tomllib.TOMLDecodeError) as error:
            errors.append(Finding('manifest', path, str(error)))
            continue
        nodes[node.id] = node
    return nodes, errors


def parse(directory: str, text: str, id: str | None = None) -> Node:
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
    return Node(id=directory if id is None else id, directory=directory, tags=tuple(tags),
                edges={kind: tuple(targets) for kind, targets in edges.items()})
