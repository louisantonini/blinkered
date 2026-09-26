import pytest

from blinkered.checks import ancestors, in_view

KEEP = ['src/nodes/feature_a', 'lib']


def test_ancestors_are_strict_and_exclude_root():
    assert ancestors('src/nodes/feature_a') == ['src', 'src/nodes']
    assert ancestors('README.md') == []


@pytest.mark.parametrize('path, expected', [
    ('README.md', True),                      # root files are always checked out
    ('src/nodes/feature_a/model.py', True),   # inside a kept directory
    ('src/nodes/feature_a/deep/x.py', True),  # recursively
    ('src/nodes/feature_a/', True),
    ('lib/helpers.py', True),
    ('src/nodes/stray.py', True),             # file directly in an ancestor of a kept directory
    ('src/top.py', True),
    ('src/nodes/', True),                     # ancestor directories exist
    ('src/nodes/feature_b/model.py', False),
    ('src/nodes/feature_b/', False),
    ('scratch/', False),                      # root-level directories are not root files
    ('scratch/notes.md', False),
    ('src/nodes/feature_ax/model.py', False), # prefix of a name is not containment
])
def test_in_view_follows_cone_mode(path, expected):
    assert in_view(path, KEEP) is expected
