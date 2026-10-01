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
    assert data['version'] == 2
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


def ids(data):
    return {n['id'] for n in data['nodes']}


def test_export_follows_dependents_as_well_as_dependencies():
    assert ids(export(NODES, 'source')) == {'source', 'feature_a', 'lookup', 'selection', 'report'}
    assert ids(export(NODES, 'lookup')) == {'lookup', 'source', 'lib', 'report'}


def test_export_depths_limit_each_direction():
    assert ids(export(NODES, 'source', dependents=1)) == {'source', 'feature_a', 'lookup'}
    assert ids(export(NODES, 'lookup', dependencies=0)) == {'lookup', 'report'}
    assert ids(export(NODES, 'lookup', dependencies=0, dependents=0)) == {'lookup'}
    assert ids(export(NODES, 'report', dependencies=1, dependents=0)) == {'report', 'selection', 'lookup'}


def test_export_filters_apply_before_traversal():
    # feature_a is a transform: without it, selection no longer reaches source
    assert ids(export(NODES, 'selection', exclude_tags=['transform'])) == {'selection'}
    with pytest.raises(ValueError, match='excluded by the tag filters'):
        export(NODES, 'report', exclude_tags=['transform'])
    assert ids(export(NODES, 'report', via=['joins', 'uses'])) == {'report', 'lookup', 'lib'}


def test_export_exclude_via_drops_edge_kinds():
    data = export(NODES, exclude_via=['reads'])
    assert edge_set(data) == {('lookup', 'lib', 'uses'), ('selection', 'feature_a', 'derived_from'),
                              ('report', 'lookup', 'joins')}


def test_export_flags_edges_implied_by_another_path():
    nodes = {n.id: n for n in [node('a', uses=['b', 'c'], reads=['c']), node('b', uses=['c']), node('c')]}
    flags = {(e['source'], e['target'], e['kind']): e['implied'] for e in export(nodes)['edges']}
    assert flags == {('a', 'b', 'uses'): False, ('b', 'c', 'uses'): False,
                     ('a', 'c', 'uses'): True, ('a', 'c', 'reads'): True}
    # without b, the direct edges are the only paths
    assert not any(e['implied'] for e in export(nodes, exclude_via=['uses'])['edges'])


def test_export_omits_unresolved_references():
    nodes = {n.id: n for n in [node('a', uses=['ghost', 'b']), node('b')]}
    assert edge_set(export(nodes)) == {('a', 'b', 'uses')}


def test_exclude_tags_filters_output_without_stopping_traversal():
    # lib is reached through lookup; source through the excluded transforms
    result = closure(NODES, 'report', exclude_tags=['transform'])
    assert set(result) == {'selection', 'source', 'lib'}
    assert set(closure(NODES, 'report', tags=['dataset', 'infra'], exclude_tags=['infra'])) == {'selection', 'source'}
