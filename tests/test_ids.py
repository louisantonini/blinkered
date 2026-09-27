import pytest

from blinkered.graph import Unresolved, closure, resolve
from blinkered.manifest import Node, node_id
from conftest import git, manifest


def node(id, **edges):
    return Node(id, f'nodes/{id}', (), {kind: tuple(t) for kind, t in edges.items()})


NODES = {n.id: n for n in [
    node('base/population'),
    node('base/score', defined_on=['base/population']),
    node('subset/population', restricted_by=['base/score']),
    node('subset/score', defined_on=['subset/population'], computed_from=['base/score']),
    node('lookup', uses=['population']),
]}


def add_node(repo, directory, tags=(), edges=None):
    path = repo / directory
    path.mkdir(parents=True)
    (path / 'blinkered.toml').write_text(manifest(list(tags), edges or {}))


# Ids


@pytest.mark.parametrize('directory, root, expected', [
    ('nodes/rvbr/pdr', 'nodes', 'rvbr/pdr'),
    ('nodes/pdr', 'nodes', 'pdr'),
    ('src/pkg', '', 'src/pkg'),
    ('other/pdr', 'nodes', None),
    ('nodesx/pdr', 'nodes', None),
    ('nodes', 'nodes', None),
])
def test_node_id_is_path_below_nodes_root(directory, root, expected):
    assert node_id(directory, root) == expected


def test_short_name_is_last_segment():
    assert NODES['subset/score'].short == 'score'
    assert NODES['lookup'].short == 'lookup'


# Resolution


def test_full_id_resolves():
    assert resolve(NODES, 'subset/score') == 'subset/score'


def test_unique_short_name_resolves():
    assert resolve(NODES, 'lookup') == 'lookup'


def test_shared_short_name_is_ambiguous():
    with pytest.raises(Unresolved, match='ambiguous name score: base/score, subset/score'):
        resolve(NODES, 'score')


def test_unknown_reference_is_reported():
    with pytest.raises(Unresolved, match='unknown node ghost'):
        resolve(NODES, 'ghost')


def test_full_id_takes_precedence_over_short_names():
    nodes = {n.id: n for n in [node('pdr'), node('rvbr/pdr')]}
    assert resolve(nodes, 'pdr') == 'pdr'


def test_closure_follows_full_ids_and_skips_ambiguous_references():
    assert closure(NODES, 'subset/score') == [
        'subset/score', 'subset/population', 'base/score', 'base/population']
    assert closure(NODES, 'lookup') == ['lookup']  # `population` is ambiguous


# Commands


def test_default_root_uses_repository_relative_ids(repo, blinkered):
    config = repo / 'blinkered.toml'
    config.write_text(config.read_text().replace('nodes_root = "src/nodes"\n', ''))
    code, out, _ = blinkered('closure', 'report')
    assert code == 0 and out.splitlines()[0] == 'src/nodes/report'
    code, out, _ = blinkered('closure', 'src/nodes/report')
    assert code == 0 and out.splitlines()[0] == 'src/nodes/report'


def test_namespaces_allow_repeated_short_names(repo, blinkered):
    add_node(repo, 'src/nodes/alt/report', edges={'reads': ['subset']})
    code, out, _ = blinkered('check')
    assert code == 0 and '10 nodes, 0 findings' in out
    code, out, _ = blinkered('closure', 'alt/report')
    assert code == 0 and out.splitlines()[:2] == ['alt/report', 'subset']


def test_ambiguous_edge_is_flagged(repo, blinkered):
    add_node(repo, 'src/nodes/a/population')
    add_node(repo, 'src/nodes/b/population')
    add_node(repo, 'src/nodes/c/consumer', edges={'uses': ['population']})
    code, out, _ = blinkered('check')
    assert code == 1
    assert 'uses → ambiguous name population: a/population, b/population' in out


def test_ambiguous_argument_fails(repo, blinkered):
    add_node(repo, 'src/nodes/a/population')
    add_node(repo, 'src/nodes/b/population')
    code, _, err = blinkered('closure', 'population')
    assert code == 2 and 'ambiguous name population' in err
    code, out, _ = blinkered('closure', 'a/population')
    assert code == 0 and out.strip() == 'a/population'


def test_node_outside_nodes_root_is_flagged(repo, blinkered):
    add_node(repo, 'elsewhere/thing')
    code, out, _ = blinkered('check')
    assert code == 1 and 'node outside nodes_root src/nodes' in out


def test_workspace_stores_full_id(repo, blinkered):
    add_node(repo, 'src/nodes/alt/report', edges={'reads': ['subset']})
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', 'alt')
    code, out, _ = blinkered('workspace', 'alt/report')
    assert code == 0 and 'focus: alt/report' in out
    assert (repo / 'src/nodes/alt/report').exists()
    assert not (repo / 'src/nodes/report').exists()
    code, out, _ = blinkered('status')
    assert code == 0 and 'in sync' in out


def test_new_refuses_directory_containing_a_namespaced_node(repo, blinkered):
    add_node(repo, 'src/nodes/alt/report')
    code, _, err = blinkered('new', 'src/nodes/alt')
    assert code == 2 and 'would contain node alt/report' in err
