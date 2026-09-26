"""Traversal over the node graph."""
from collections.abc import Iterable

from .manifest import Node


def closure(nodes: dict[str, Node], start: str, *, via: Iterable[str] | None = None,
            tags: Iterable[str] | None = None) -> list[str]:
    """`start` and its transitive dependencies.

    `via` restricts the edge kinds followed; `tags` filters the output without stopping traversal.
    """
    raise NotImplementedError


def cycles(nodes: dict[str, Node]) -> list[list[str]]:
    """Dependency cycles, each as a list of node names."""
    raise NotImplementedError
