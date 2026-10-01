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


GRAPH_VERSION = 2


def _walk(start: str, step: dict[str, set[str]], depth: int | None) -> set[str]:
    """Nodes within `depth` steps of `start` along `step` (None: unlimited)."""
    seen, frontier, taken = {start}, {start}, 0
    while frontier and (depth is None or taken < depth):
        frontier = {target for id in frontier for target in step.get(id, ())} - seen
        seen |= frontier
        taken += 1
    return seen


def _implied(edges: set[tuple[str, str, str]]) -> set[tuple[str, str, str]]:
    """Edges whose source reaches their target through at least one other node."""
    out = {}
    for source, target, _ in edges:
        out.setdefault(source, set()).add(target)
    result = set()
    for source, target, kind in edges:
        stack = [id for id in out[source] if id != target]
        seen = set(stack)
        while stack:
            id = stack.pop()
            if target in out.get(id, ()):
                result.add((source, target, kind))
                break
            for next_id in out.get(id, ()):
                if next_id not in seen and next_id != target:
                    seen.add(next_id)
                    stack.append(next_id)
    return result


def export(nodes: dict[str, Node], start: str | None = None, *, dependencies: int | None = None,
           dependents: int | None = None, via: Iterable[str] | None = None,
           exclude_via: Iterable[str] | None = None, tags: Iterable[str] | None = None,
           exclude_tags: Iterable[str] | None = None) -> dict:
    """Nodes and resolved edges as plain data, sorted for stable output.

    Applied in order: `tags`/`exclude_tags` keep or drop nodes and `via`/`exclude_via` keep or drop edge kinds;
    from `start`, the walk then takes up to `dependencies` steps along edges and `dependents` steps against them
    (None: unlimited; 0: none) on what remains; without `start`, every remaining node. Each edge is flagged
    `implied` when its source reaches its target through other emitted nodes. Unresolved references are omitted.
    """
    index = shorts(nodes)
    tags = None if tags is None else set(tags)
    exclude_tags = set(exclude_tags or ())
    via = None if via is None else set(via)
    exclude_via = set(exclude_via or ())
    allowed = {id for id, node in nodes.items()
               if (tags is None or tags & set(node.tags)) and not exclude_tags & set(node.tags)}
    edges = set()
    for id in allowed:
        for kind, references in nodes[id].edges.items():
            if (via is not None and kind not in via) or kind in exclude_via:
                continue
            for reference in references:
                try:
                    target = resolve(nodes, reference, index)
                except Unresolved:
                    continue
                if target in allowed:
                    edges.add((id, target, kind))
    kept = allowed
    if start is not None:
        start = resolve(nodes, start, index)
        if start not in allowed:
            raise ValueError(f'{start} is excluded by the tag filters')
        down, up = {}, {}
        for source, target, _ in edges:
            down.setdefault(source, set()).add(target)
            up.setdefault(target, set()).add(source)
        kept = _walk(start, down, dependencies) | _walk(start, up, dependents)
    edges = {(s, t, k) for s, t, k in edges if s in kept and t in kept}
    implied = _implied(edges)
    return {
        'version': GRAPH_VERSION,
        'nodes': [{'id': id, 'directory': nodes[id].directory, 'tags': sorted(nodes[id].tags)}
                  for id in sorted(kept)],
        'edges': [{'source': s, 'target': t, 'kind': k, 'implied': (s, t, k) in implied}
                  for s, t, k in sorted(edges)],
    }
