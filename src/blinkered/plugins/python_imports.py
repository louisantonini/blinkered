"""Python imports between nodes, kept as edges of one kind (default `imports`) that only this plugin writes.

Only files present in the working tree are inspected, so nodes outside the view are neither checked nor written.
"""
import ast
from pathlib import Path

from ..config import FILENAME
from ..findings import Finding
from ..graph import Unresolved, resolve, shorts
from ..manifest import Node, set_edge

NAME = 'python_imports'
SETTINGS = {'kind'}
COMMAND = 'python-imports'
HELP = 'compare the imports edges with the code; --write rewrites them'
DEFAULT_KIND = 'imports'


def kind(settings: dict) -> str:
    value = settings.get('kind', DEFAULT_KIND)
    if not isinstance(value, str) or not value:
        raise ValueError(f'plugins.{NAME}.kind must be a non-empty string')
    return value


def owner(path: str, nodes: dict[str, Node]) -> Node | None:
    for node in nodes.values():
        if path == node.directory or path.startswith(node.directory + '/'):
            return node
    return None


def imported_paths(file: Path, relative: str) -> list[str]:
    """Repository-relative module paths imported by `file`."""
    package = relative.split('/')[:-1]
    result = []
    for statement in ast.walk(ast.parse(file.read_text(), filename=str(file))):
        if isinstance(statement, ast.Import):
            result += [alias.name.replace('.', '/') for alias in statement.names]
        elif isinstance(statement, ast.ImportFrom):
            if statement.level:
                base = package[:len(package) - statement.level + 1]
            else:
                base = []
            module = statement.module.split('.') if statement.module else []
            result.append('/'.join(base + module))
    return result


def imports(root: Path, node: Node, nodes: dict[str, Node]) -> dict[str, str]:
    """Other nodes imported by `node`'s files on disk, each with the first file importing it."""
    found = {}
    for file in sorted((root / node.directory).rglob('*.py')):
        relative = file.relative_to(root).as_posix()
        for path in imported_paths(file, relative):
            target = owner(path, nodes)
            if target and target.id != node.id:
                found.setdefault(target.id, relative)
    return found


def drift(root: Path, nodes: dict[str, Node], settings: dict) -> dict[str, tuple[dict[str, str], set[str]]]:
    """Per node on disk with differences: (imports missing from the edges with a file, edges without an import)."""
    edge, index, result = kind(settings), shorts(nodes), {}
    for node in nodes.values():
        if not (root / node.directory).is_dir():
            continue
        declared = set()
        for reference in node.edges.get(edge, ()):
            try:
                declared.add(resolve(nodes, reference, index))
            except Unresolved:
                continue
        actual = imports(root, node, nodes)
        missing = {target: file for target, file in actual.items() if target not in declared}
        stale = declared - set(actual)
        if missing or stale:
            result[node.id] = (missing, stale)
    return result


def check(root: Path, nodes: dict[str, Node], settings: dict) -> list[Finding]:
    """Imports without an edge of the plugin's kind, and edges of that kind without an import."""
    edge, findings = kind(settings), []
    for id, (missing, stale) in sorted(drift(root, nodes, settings).items()):
        findings += [Finding('import', file, f'imports {target} without an {edge} edge')
                     for target, file in sorted(missing.items())]
        findings += [Finding('import', f'{nodes[id].directory}/{FILENAME}', f'{edge} edge to {target} without an import')
                     for target in sorted(stale)]
    return findings


def arguments(parser) -> None:
    parser.add_argument('--write', action='store_true', help='rewrite the edges of nodes on disk to match the code')


def run(root: Path, config, nodes: dict[str, Node], settings: dict, args) -> int:
    edge, changes = kind(settings), drift(root, nodes, settings)
    if not changes:
        print(f'{edge} edges match the code')
        return 0
    for id, (missing, stale) in sorted(changes.items()):
        print(id)
        print(''.join(f'  + {target}\n' for target in sorted(missing)) + ''.join(f'  - {target}\n' for target in sorted(stale)), end='')
        if args.write:
            path = root / nodes[id].directory / FILENAME
            targets = sorted(imports(root, nodes[id], nodes))
            path.write_text(set_edge(path.read_text(), edge, targets))
    if args.write:
        print(f'wrote {len(changes)} manifest(s)')
        return 0
    return 1
