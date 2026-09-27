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


# Export

from blinkered.graph import export


def edge_set(data):
    return {(e['source'], e['target'], e['kind']) for e in data['edges']}


def test_export_whole_graph_is_sorted_and_versioned():
    data = export(NODES)
    assert data['version'] == 1
    assert [n['id'] for n in data['nodes']] == sorted(NODES)
    assert data['edges'] == sorted(data['edges'], key=lambda e: (e['source'], e['target'], e['kind']))
    assert ('report', 'lookup', 'joins') in edge_set(data)
    assert len(data['edges']) == 6


def test_export_closure_and_via():
    data = export(NODES, 'report', via=['reads', 'derived_from'])
    assert [n['id'] for n in data['nodes']] == ['feature_a', 'report', 'selection', 'source']
    assert edge_set(data) == {('report', 'selection', 'reads'), ('selection', 'feature_a', 'derived_from'),
                              ('feature_a', 'source', 'reads')}


def test_export_tag_filters_drop_edges_to_hidden_nodes():
    data = export(NODES, exclude_tags=['infra'])
    assert 'lib' not in {n['id'] for n in data['nodes']}
    assert not any(e['target'] == 'lib' for e in data['edges'])
    data = export(NODES, tags=['dataset'])
    assert [n['id'] for n in data['nodes']] == ['selection', 'source']
    assert data['edges'] == []


def test_export_omits_unresolved_references():
    nodes = {n.id: n for n in [node('a', uses=['ghost', 'b']), node('b')]}
    assert edge_set(export(nodes)) == {('a', 'b', 'uses')}
