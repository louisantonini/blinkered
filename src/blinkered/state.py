"""Focus state, stored under `.git/blinkered/`."""
from pathlib import Path

from . import git


def _file(root: Path) -> Path:
    return git.git_dir(root) / 'blinkered' / 'focus'


def read_focus(root: Path) -> str | None:
    file = _file(root)
    return file.read_text().strip() or None if file.is_file() else None


def write_focus(root: Path, node: str | None) -> None:
    """Store the focus node name; None clears it."""
    file = _file(root)
    if node is None:
        file.unlink(missing_ok=True)
        return
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(node + '\n')
