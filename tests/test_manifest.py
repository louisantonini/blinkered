import tomllib

import pytest

from blinkered.manifest import parse


def test_parse_reads_tags_and_edges():
    node = parse('src/nodes/report', 'tags = ["transform"]\n\n[edges]\n'
                                   'reads = ["selection"]\njoins = ["lookup"]\n')
    assert node.id == 'src/nodes/report'  # without nodes_root, the id is the directory
    assert node.directory == 'src/nodes/report'
    assert node.tags == ('transform',)
    assert node.edges == {'reads': ('selection',), 'joins': ('lookup',)}


def test_parse_accepts_empty_manifest():
    node = parse('a/b', '')
    assert node.tags == () and node.edges == {}


@pytest.mark.parametrize('text, message', [
    ('name = "x"\n', 'unknown keys'),
    ('tags = "transform"\n', 'tags must be a list'),
    ('edges = ["x"]\n', 'edges must be a table'),
    ('[edges]\nuses = "x"\n', 'edges.uses'),
])
def test_parse_rejects_malformed_manifests(text, message):
    with pytest.raises(ValueError, match=message):
        parse('a/b', text)


def test_parse_rejects_invalid_toml():
    with pytest.raises(tomllib.TOMLDecodeError):
        parse('a/b', 'tags = [\n')


def test_parse_uses_given_id():
    node = parse('nodes/rvbr/pdr', '', id='rvbr/pdr')
    assert node.id == 'rvbr/pdr' and node.short == 'pdr' and node.directory == 'nodes/rvbr/pdr'


# Setting an edge

from blinkered.manifest import set_edge


def test_set_edge_replaces_inserts_and_removes():
    text = 'tags = ["x"]\n\n[edges]\nuses = ["a"]\nimports = ["b"]\n'
    assert set_edge(text, 'imports', ['b', 'c']) == 'tags = ["x"]\n\n[edges]\nuses = ["a"]\nimports = ["b", "c"]\n'
    assert set_edge(text, 'imports', []) == 'tags = ["x"]\n\n[edges]\nuses = ["a"]\n'
    assert set_edge('tags = []\n\n[edges]\nuses = ["a"]\n', 'imports', ['b']) == \
        'tags = []\n\n[edges]\nuses = ["a"]\nimports = ["b"]\n'


def test_set_edge_handles_missing_section_and_multiline_arrays():
    assert set_edge('tags = []\n', 'imports', ['b']) == 'tags = []\n\n[edges]\nimports = ["b"]\n'
    assert set_edge('tags = []\n', 'imports', []) == 'tags = []\n'
    text = 'tags = []\n\n[edges]\nimports = [\n  "a",\n  "b",\n]\nuses = ["c"]\n'
    assert set_edge(text, 'imports', ['a']) == 'tags = []\n\n[edges]\nimports = ["a"]\nuses = ["c"]\n'
