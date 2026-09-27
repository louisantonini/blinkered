import pytest

from blinkered.graph import closure, cycles
from blinkered.manifest import Node


def node(name, tags=(), **edges):
    return Node(name, f'nodes/{name}', tuple(tags),
                {kind: tuple(targets) for kind, targets in edges.items()})


NODES = {n.id: n for n in [
    node('source', ['dataset']),
    node('feature_a', ['transform'], reads=['source']),
    node('lookup', ['transform'], reads=['source'], uses=['lib']),
    node('lib', ['infra']),
    node('selection', ['dataset'], derived_from=['feature_a']),
    node('report', ['transform'], reads=['selection'], joins=['lookup']),
]}


def test_closure_follows_all_edges_transitively():
    assert set(closure(NODES, 'report')) == {'report', 'selection', 'feature_a', 'source', 'lookup', 'lib'}


def test_closure_starts_with_the_node():
    assert closure(NODES, 'report')[0] == 'report'


def test_via_restricts_edge_kinds():
    assert set(closure(NODES, 'report', via=['reads', 'derived_from'])) == {
        'report', 'selection', 'feature_a', 'source'}


def test_tag_filters_output_without_stopping_traversal():
    # source is reached only through transforms (feature_a, lookup), not through a dataset
    assert set(closure(NODES, 'report', tags=['dataset'])) == {'selection', 'source'}


def test_unknown_start_raises():
    with pytest.raises(KeyError):
        closure(NODES, 'missing')


def test_unknown_targets_are_skipped():
    nodes = {'a': node('a', uses=['ghost'])}
    assert closure(nodes, 'a') == ['a']


def test_acyclic_graph_has_no_cycles():
    assert cycles(NODES) == []


def test_cycle_is_reported():
    nodes = {n.id: n for n in [node('a', uses=['b']), node('b', uses=['c']),
                                 node('c', uses=['a'])]}
    [cycle] = cycles(nodes)
    assert cycle[0] == cycle[-1] and set(cycle) == {'a', 'b', 'c'}
