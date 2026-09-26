"""Validation of manifests, layout and working-tree state."""
import posixpath
from pathlib import Path

from . import git
from .config import Config
from .findings import Finding
from .graph import cycles
from .manifest import Node


def ancestors(path: str) -> list[str]:
    """Strict ancestor directories of `path`, excluding the repository root."""
    parts = path.strip('/').split('/')
    return ['/'.join(parts[:i]) for i in range(1, len(parts))]


def in_view(path: str, keep: list[str]) -> bool:
    """Whether cone mode checks out `path` (directories end with `/`) when the view is `keep`."""
    is_directory = path.endswith('/')
    path = path.rstrip('/')
    if any(path == d or path.startswith(d + '/') for d in keep):
        return True
    parents = {a for d in keep for a in ancestors(d)}
    if is_directory:
        return path in parents
    parent = posixpath.dirname(path)
    return parent == '' or parent in parents


def check(root: Path, config: Config, nodes: dict[str, Node],
          errors: list[Finding]) -> list[Finding]:
    """Manifest errors, unknown targets, cycles, layout-rule violations and plugin findings."""
    findings = list(errors)
    for node in nodes.values():
        for kind, targets in node.edges.items():
            findings += [Finding('edge', node.directory, f'{kind} → unknown node {target}')
                         for target in targets if target not in nodes]
    findings += [Finding('cycle', nodes[cycle[0]].directory, ' → '.join(cycle))
                 for cycle in cycles(nodes)]
    findings += layout(root, config, nodes)
    if config.plugins.get('python_imports'):
        from .plugins import python_imports
        findings += python_imports.check(root, nodes)
    return findings


def layout(root: Path, config: Config, nodes: dict[str, Node]) -> list[Finding]:
    """Nested nodes and files in grouping directories outside `grouping_allow`."""
    directories = {node.directory for node in nodes.values()}
    findings = [Finding('layout', node.directory, f'nested inside node {a}')
                for node in nodes.values() for a in ancestors(node.directory)
                if a in directories]
    grouping = {a for d in directories for a in ancestors(d)} - directories
    files = set(git.tracked_paths(root)) | set(git.untracked_paths(root))
    findings += [Finding('layout', path, 'file in grouping directory')
                 for path in sorted(files)
                 if posixpath.dirname(path) in grouping
                 and posixpath.basename(path) not in config.grouping_allow]
    return findings


def leaving(root: Path, keep: list[str]) -> tuple[list[Finding], list[Finding]]:
    """Paths that would leave a view limited to `keep`: (work at risk, ignored files git may delete).

    Ignored files are at risk only inside a directory outside the view that contains tracked files.
    """
    tracked = git.tracked_paths(root)
    work, ignored = [], []
    for code, path in git.status(root):
        if in_view(path, keep):
            continue
        if code == '!!':
            outside = [a for a in ancestors(path.rstrip('/') + '/x') if not in_view(a + '/', keep)]
            if any(t.startswith(a + '/') for a in outside for t in tracked):
                ignored.append(Finding('ignored', path, 'would be deleted'))
        elif code == '??':
            work.append(Finding('untracked', path, 'would stay on disk outside the view'))
        elif 'U' in code or code in ('AA', 'DD'):
            work.append(Finding('conflict', path, 'unresolved'))
        elif code[0] != ' ':
            work.append(Finding('staged', path, 'staged change outside the view'))
        else:
            work.append(Finding('modified', path, 'would stay on disk outside the view'))
    return work, ignored


def leaks(root: Path, keep: list[str]) -> list[Finding]:
    """Non-ignored paths on disk outside the current view."""
    return [Finding('leak', path, code.strip() or code) for code, path in git.status(root)
            if code != '!!' and not in_view(path, keep) and (root / path).exists()]
