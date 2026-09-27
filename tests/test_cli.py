import pytest

from blinkered import git
from blinkered.cli import parser
from blinkered.git import parse_version


def test_closure_arguments():
    args = parser().parse_args(['closure', 'selection', '--via', 'reads,uses', '--tag', 'transform'])
    assert args.node == 'selection'
    assert args.via == ['reads', 'uses']
    assert args.tag == ['transform']


def test_workspace_without_node_resyncs():
    args = parser().parse_args(['workspace'])
    assert args.nodes == [] and args.tag is None and args.exclude_tag is None and not args.all


def test_unknown_command_rejected():
    with pytest.raises(SystemExit):
        parser().parse_args(['impact', 'x'])


@pytest.mark.parametrize('text, expected', [
    ('git version 2.50.1 (Apple Git-155)\n', (2, 50, 1)),
    ('git version 2.35.0\n', (2, 35, 0)),
    ('git version 2.39.2.windows.1\n', (2, 39, 2)),
])
def test_parse_git_version(text, expected):
    assert parse_version(text) == expected


def test_old_git_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(git, 'run', lambda root, *args, **kw: 'git version 2.34.1\n')
    with pytest.raises(git.GitError, match='2.35 or later required, found 2.34.1'):
        git.require_version(tmp_path)
