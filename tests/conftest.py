import subprocess
from pathlib import Path

import pytest

from blinkered.cli import main

# name: (tags, edges, imported nodes)
CHAIN = {
    'utils': (['infra'], {}, []),
    'source': (['dataset'], {'uses': ['utils']}, ['utils']),
    'filter': (['transform'], {'reads': ['source']}, ['source']),
    'subset': (['dataset'], {'derived_from': ['filter']}, ['filter']),
    'feature_a': (['transform'], {'reads': ['subset']}, ['subset']),
    'feature_b': (['transform'], {'reads': ['subset']}, ['subset']),
    'lookup': (['transform'], {'reads': ['subset']}, ['subset']),
    'selection': (['dataset'], {'derived_from': ['feature_a']}, ['feature_a']),
    'report': (['transform'], {'reads': ['selection'], 'joins': ['lookup']},
               ['selection', 'lookup']),
}


def git(root: Path, *args: str) -> str:
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          capture_output=True, text=True).stdout


def manifest(tags, edges) -> str:
    lines = [f'tags = {tags!r}'.replace("'", '"'), '', '[edges]']
    lines += [f'{kind} = {targets!r}'.replace("'", '"') for kind, targets in edges.items()]
    return '\n'.join(lines) + '\n'


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Committed repository holding the demo chain, a `lib/` directory and root configuration."""
    root = tmp_path / 'repo'
    root.mkdir()
    git(root, 'init', '-q', '-b', 'main')
    git(root, 'config', 'user.email', 'test@example.com')
    git(root, 'config', 'user.name', 'test')
    for name, (tags, edges, imports) in CHAIN.items():
        directory = root / 'src' / 'nodes' / name
        directory.mkdir(parents=True)
        (directory / '__init__.py').write_text('')
        (directory / 'blinkered.toml').write_text(manifest(tags, edges))
        (directory / 'model.py').write_text(''.join(
            f'from src.nodes.{target} import model as _{target}\n' for target in imports)
            + f'VALUE = {name!r}\n')
    (root / 'lib').mkdir()
    (root / 'lib' / 'helpers.py').write_text('HELP = 1\n')
    (root / 'blinkered.toml').write_text(
        'nodes_root = "src/nodes"\nalways = ["lib"]\n\n[plugins]\npython_imports = true\n')
    (root / '.gitignore').write_text('__pycache__/\n*.bin\nscratch/\n')
    (root / 'README.md').write_text('demo\n')
    git(root, 'add', '-A')
    git(root, 'commit', '-q', '-m', 'init')
    return root


@pytest.fixture
def blinkered(repo, monkeypatch, capsys):
    """Run the CLI inside `repo`; return (exit code, stdout, stderr)."""
    monkeypatch.chdir(repo)

    def run(*args: str):
        code = main(list(args))
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return run
