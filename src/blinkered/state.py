"""Focus state, stored under `.git/blinkered/`."""
from pathlib import Path


def read_focus(root: Path) -> str | None:
    raise NotImplementedError


def write_focus(root: Path, node: str | None) -> None:
    """Store the focus node name; None clears it."""
    raise NotImplementedError
