"""Thin wrappers around the git commands blinkered relies on."""
from pathlib import Path


def repo_root(start: Path) -> Path:
    """Top-level directory of the repository containing `start`."""
    raise NotImplementedError


def git_dir(root: Path) -> Path:
    """The repository's `.git` directory."""
    raise NotImplementedError


def tracked_paths(root: Path) -> list[str]:
    """All paths in the index, including those outside the sparse view."""
    raise NotImplementedError


def read_file(root: Path, path: str) -> str:
    """Working-tree content when present, otherwise the index version."""
    raise NotImplementedError


def status(root: Path) -> list[tuple[str, str]]:
    """(code, path) pairs from `git status --porcelain --ignored`."""
    raise NotImplementedError


def sparse_patterns(root: Path) -> list[str] | None:
    """Current cone-mode directories, or None when sparse checkout is disabled."""
    raise NotImplementedError


def sparse_set(root: Path, directories: list[str]) -> None:
    """Apply a cone-mode sparse checkout of `directories`."""
    raise NotImplementedError


def sparse_disable(root: Path) -> None:
    """Restore the full working tree."""
    raise NotImplementedError
