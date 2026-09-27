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
            tags: Iterable[str] | None = None,
            exclude_tags: Iterable[str] | None = None) -> list[str]:
    """`start` and its transitive dependencies, as ids.

    `via` restricts the edge kinds followed; `tags` and `exclude_tags` filter the output without
    stopping traversal.
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
    tags = None if tags is None else set(tags)
    exclude_tags = set(exclude_tags or ())
    return [id for id in seen
            if (tags is None or tags & set(nodes[id].tags)) and not exclude_tags & set(nodes[id].tags)]


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


GRAPH_VERSION = 1


def export(nodes: dict[str, Node], start: str | None = None, *, via: Iterable[str] | None = None,
           tags: Iterable[str] | None = None, exclude_tags: Iterable[str] | None = None) -> dict:
    """Nodes and resolved edges as plain data, sorted for stable output.

    `start` restricts to its closure along `via`; `tags` and `exclude_tags` filter nodes, and an
    edge is kept only when both ends are kept. Unresolved references are omitted.
    """
    via = None if via is None else set(via)
    ids = closure(nodes, start, via=via) if start is not None else list(nodes)
    tags = None if tags is None else set(tags)
    exclude_tags = set(exclude_tags or ())
    kept = {id for id in ids
            if (tags is None or tags & set(nodes[id].tags)) and not exclude_tags & set(nodes[id].tags)}
    index = shorts(nodes)
    edges = set()
    for id in kept:
        for kind, references in nodes[id].edges.items():
            if via is not None and kind not in via:
                continue
            for reference in references:
                try:
                    target = resolve(nodes, reference, index)
                except Unresolved:
                    continue
                if target in kept:
                    edges.add((id, target, kind))
    return {
        'version': GRAPH_VERSION,
        'nodes': [{'id': id, 'directory': nodes[id].directory, 'tags': sorted(nodes[id].tags)}
                  for id in sorted(kept)],
        'edges': [{'source': s, 'target': t, 'kind': k} for s, t, k in sorted(edges)],
    }
