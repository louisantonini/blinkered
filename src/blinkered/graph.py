"""Traversal over the node graph."""
from collections.abc import Iterable

from .manifest import Node


def closure(nodes: dict[str, Node], start: str, *, via: Iterable[str] | None = None,
            tags: Iterable[str] | None = None) -> list[str]:
    """`start` and its transitive dependencies.

    `via` restricts the edge kinds followed; `tags` filters the output without stopping traversal.
    Unknown targets are skipped; `check` reports them.
    """
    if start not in nodes:
        raise KeyError(start)
    via = None if via is None else set(via)
    seen, queue = [start], [start]
    while queue:
        for target in nodes[queue.pop(0)].targets(via):
            if target in nodes and target not in seen:
                seen.append(target)
                queue.append(target)
    if tags is None:
        return seen
    tags = set(tags)
    return [name for name in seen if tags & set(nodes[name].tags)]


def cycles(nodes: dict[str, Node]) -> list[list[str]]:
    """Dependency cycles, each as a list of node names."""
    state, stack, found = {}, [], []

    def visit(name):
        state[name] = 'open'
        stack.append(name)
        for target in nodes[name].targets():
            if target not in nodes:
                continue
            if state.get(target) == 'open':
                found.append(stack[stack.index(target):] + [target])
            elif target not in state:
                visit(target)
        stack.pop()
        state[name] = 'done'

    for name in nodes:
        if name not in state:
            visit(name)
    return found
