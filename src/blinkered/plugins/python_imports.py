"""Python code imports must be covered by declared edges.

Only files present in the working tree are inspected, so nodes outside the view are not checked.
"""
import ast
from pathlib import Path

from ..findings import Finding
from ..manifest import Node


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


def check(root: Path, nodes: dict[str, Node]) -> list[Finding]:
    """Imports of another node's directory that the importing node does not declare as an edge."""
    findings = []
    for node in nodes.values():
        allowed = set(node.targets())
        for file in sorted((root / node.directory).rglob('*.py')):
            relative = file.relative_to(root).as_posix()
            for path in imported_paths(file, relative):
                target = owner(path, nodes)
                if target and target.name != node.name and target.name not in allowed:
                    findings.append(Finding('import', relative,
                                            f'imports {target.name} without a declared edge'))
    return findings
