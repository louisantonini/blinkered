"""Thin wrappers around the git commands blinkered relies on."""
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def run(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(['git', '-C', str(root), '-c', 'advice.sparseIndexExpanded=false',
                             *args], capture_output=True, text=True)
    if check and result.returncode:
        raise GitError(result.stderr.strip() or f'git {args[0]} failed')
    return result.stdout


def repo_root(start: Path) -> Path:
    """Top-level directory of the repository containing `start`."""
    return Path(run(start, 'rev-parse', '--show-toplevel').strip())


def git_dir(root: Path) -> Path:
    """The repository's `.git` directory."""
    return Path(run(root, 'rev-parse', '--absolute-git-dir').strip())


def tracked_paths(root: Path) -> list[str]:
    """All paths in the index, including those outside the sparse view."""
    return [path for path in run(root, 'ls-files', '-z').split('\0') if path]


def untracked_paths(root: Path) -> list[str]:
    """Untracked, non-ignored files present in the working tree."""
    return [path for path in run(root, 'ls-files', '-z', '--others', '--exclude-standard')
            .split('\0') if path]


def read_file(root: Path, path: str) -> str:
    """Working-tree content when present, otherwise the index version."""
    file = root / path
    if file.is_file():
        return file.read_text()
    return run(root, 'show', f':{path}')


def status(root: Path) -> list[tuple[str, str]]:
    """(code, path) pairs from `git status --porcelain --ignored`; directories end with `/`."""
    fields = run(root, 'status', '--porcelain=v1', '-z', '--ignored',
                 '--untracked-files=all').split('\0')
    entries, i = [], 0
    while i < len(fields):
        field = fields[i]
        i += 1
        if not field:
            continue
        code, path = field[:2], field[3:]
        entries.append((code, path))
        if code[0] in 'RC':
            i += 1  # the original path of a rename or copy follows
    return entries


def sparse_patterns(root: Path) -> list[str] | None:
    """Current cone-mode directories, or None when sparse checkout is disabled."""
    if run(root, 'config', '--bool', 'core.sparseCheckout', check=False).strip() != 'true':
        return None
    return run(root, 'sparse-checkout', 'list').splitlines()


def sparse_set(root: Path, directories: list[str]) -> None:
    """Apply a cone-mode sparse checkout of `directories`."""
    run(root, 'sparse-checkout', 'set', '--cone', '--', *directories)


def sparse_add(root: Path, directories: list[str]) -> None:
    run(root, 'sparse-checkout', 'add', '--', *directories)


def sparse_disable(root: Path) -> None:
    """Restore the full working tree."""
    run(root, 'sparse-checkout', 'disable')
