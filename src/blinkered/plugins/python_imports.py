"""Python code imports must be covered by declared edges."""
from pathlib import Path

from ..checks import Finding
from ..manifest import Node


def check(root: Path, nodes: dict[str, Node]) -> list[Finding]:
    """Imports of another node's directory that the importing node does not declare as an edge."""
    raise NotImplementedError
