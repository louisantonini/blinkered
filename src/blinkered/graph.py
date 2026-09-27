"""Reference resolution and traversal over the node graph."""
from collections.abc import Iterable

from .manifest import Node


class Unresolved(KeyError):
    """A reference that names no node, or a short name shared by several nodes."""

    def __str__(self) -> str:
        return self.args[0]


def shorts(nodes: dict[str, Node]) -> dict[str, list[str]]:
    """Ids by short name."""
    index = {}
    for id, node in nodes.items():
        index.setdefault(node.short, []).append(id)
    return index


def resolve(nodes: dict[str, Node], reference: str,
            index: dict[str, list[str]] | None = None) -> str:
    """Id named by `reference`: a full id, or a short name unique across the repository."""
    if reference in nodes:
        return reference
    candidates = (shorts(nodes) if index is None else index).get(reference, [])
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        raise Unresolved(f'ambiguous name {reference}: {", ".join(sorted(candidates))}')
    raise Unresolved(f'unknown node {reference}')


def targets(nodes: dict[str, Node], id: str, *, via=None, index=None) -> list[str]:
    """Resolved edge targets of `id`; unresolved references are skipped (`check` reports them)."""
    index = shorts(nodes) if index is None else index
    result = []
    for reference in nodes[id].references(via):
        try:
            result.append(resolve(nodes, reference, index))
        except Unresolved:
            continue
    return result


def closure(nodes: dict[str, Node], start: str, *, via: Iterable[str] | None = None,
            tags: Iterable[str] | None = None) -> list[str]:
    """`start` and its transitive dependencies, as ids.

    `via` restricts the edge kinds followed; `tags` filters the output without stopping traversal.
    """
    index = shorts(nodes)
    start = resolve(nodes, start, index)
    via = None if via is None else set(via)
    seen, queue = [start], [start]
    while queue:
        for target in targets(nodes, queue.pop(0), via=via, index=index):
            if target not in seen:
                seen.append(target)
                queue.append(target)
    if tags is None:
        return seen
    tags = set(tags)
    return [id for id in seen if tags & set(nodes[id].tags)]


def cycles(nodes: dict[str, Node]) -> list[list[str]]:
    """Dependency cycles, each as a list of ids."""
    index = shorts(nodes)
    state, stack, found = {}, [], []

    def visit(id):
        state[id] = 'open'
        stack.append(id)
        for target in targets(nodes, id, index=index):
            if state.get(target) == 'open':
                found.append(stack[stack.index(target):] + [target])
            elif target not in state:
                visit(target)
        stack.pop()
        state[id] = 'done'

    for id in nodes:
        if id not in state:
            visit(id)
    return found
