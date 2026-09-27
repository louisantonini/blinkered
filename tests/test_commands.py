import os
import subprocess
import sys

import pytest
from conftest import git

FULL_CLOSURE = ['report', 'selection', 'lookup', 'feature_a', 'subset', 'filter', 'source',
                'utils']


def lines(text):
    return text.strip().splitlines()


def on_disk(repo, node):
    return (repo / 'src' / 'nodes' / node).exists()


def python(repo, statement):
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    return subprocess.run([sys.executable, '-c', statement], cwd=repo, env=env,
                          capture_output=True, text=True)


# Read-only commands


def test_check_passes_on_valid_repository(blinkered):
    code, out, _ = blinkered('check')
    assert code == 0
    assert '9 nodes, 0 findings' in out


def test_tags_counts_tags_and_edge_kinds(blinkered):
    code, out, _ = blinkered('tags')
    assert code == 0
    assert '5  transform' in out and '3  dataset' in out and '1  infra' in out
    assert '5  reads' in out and '2  derived_from' in out


def test_closure_lists_node_and_dependencies(blinkered):
    code, out, _ = blinkered('closure', 'report')
    assert code == 0
    assert lines(out) == FULL_CLOSURE


def test_closure_via_and_tag(blinkered):
    _, out, _ = blinkered('closure', 'report', '--via', 'reads,derived_from')
    assert set(lines(out)) == {'report', 'selection', 'feature_a', 'subset', 'filter',
                               'source'}
    _, out, _ = blinkered('closure', 'report', '--tag', 'dataset')
    assert set(lines(out)) == {'selection', 'subset', 'source'}


def test_closure_of_unknown_node_fails(blinkered):
    code, _, err = blinkered('closure', 'missing')
    assert code == 2 and 'unknown node missing' in err


def test_unmanaged_repository_fails(repo, blinkered):
    (repo / 'blinkered.toml').unlink()
    code, _, err = blinkered('check')
    assert code == 2 and 'no blinkered.toml' in err


# Workspace


def test_status_without_focus_reports_full_view(blinkered):
    code, out, _ = blinkered('status')
    assert code == 0
    assert 'focus: none' in out and 'view: full' in out


def test_workspace_narrows_to_closure_and_always(repo, blinkered):
    code, out, _ = blinkered('workspace', 'report')
    assert code == 0
    assert not on_disk(repo, 'feature_b')
    assert all(on_disk(repo, node) for node in FULL_CLOSURE)
    assert (repo / 'lib' / 'helpers.py').exists()
    assert (repo / 'README.md').exists() and (repo / 'blinkered.toml').exists()
    code, out, _ = blinkered('status')
    assert code == 0 and 'in sync' in out


def test_python_imports_follow_the_view(repo, blinkered):
    blinkered('workspace', 'report')
    inside = python(repo, 'import src.nodes.report.model as m; print(m.VALUE)')
    assert inside.returncode == 0 and inside.stdout.strip() == 'report'
    outside = python(repo, 'import src.nodes.feature_b.model')
    assert outside.returncode != 0 and 'ModuleNotFoundError' in outside.stderr


def test_workspace_without_node_requires_focus(blinkered):
    code, _, err = blinkered('workspace')
    assert code == 2 and 'no focus' in err


def test_workspace_all_restores_full_tree(repo, blinkered):
    blinkered('workspace', 'feature_a')
    code, out, _ = blinkered('workspace', '--all')
    assert code == 0 and on_disk(repo, 'feature_b')
    _, out, _ = blinkered('status')
    assert 'focus: none' in out and 'view: full' in out


def test_workspace_rejects_node_with_all(blinkered):
    with pytest.raises(SystemExit) as exit:
        blinkered('workspace', 'feature_a', '--all')
    assert exit.value.code == 2


# Guards


def test_refuses_when_modified_or_untracked_files_would_leave(repo, blinkered):
    lookup = repo / 'src' / 'nodes' / 'lookup'
    with open(lookup / 'model.py', 'a') as file:
        file.write('# edit\n')
    (lookup / 'notes.txt').write_text('draft\n')
    code, _, err = blinkered('workspace', 'feature_a')
    assert code == 1
    assert 'modified: src/nodes/lookup/model.py' in err
    assert 'untracked: src/nodes/lookup/notes.txt' in err
    assert on_disk(repo, 'feature_b')  # view unchanged


def test_refuses_staged_files_that_would_leave(repo, blinkered):
    (repo / 'src' / 'nodes' / 'lookup' / 'new.py').write_text('X = 1\n')
    git(repo, 'add', 'src/nodes/lookup/new.py')
    code, _, err = blinkered('workspace', 'feature_a')
    assert code == 1 and 'staged: src/nodes/lookup/new.py' in err


def test_ignored_files_need_force_and_are_deleted(repo, blinkered):
    cache = repo / 'src' / 'nodes' / 'lookup' / 'cache.bin'
    cache.write_text('data\n')
    code, _, err = blinkered('workspace', 'feature_a')
    assert code == 1 and 'ignored: src/nodes/lookup/cache.bin' in err and '--force' in err
    assert cache.exists()
    code, _, _ = blinkered('workspace', 'feature_a', '--force')
    assert code == 0 and not cache.exists()


def test_ignored_directory_never_tracked_is_not_at_risk(repo, blinkered):
    (repo / 'scratch').mkdir()
    (repo / 'scratch' / 'notes.md').write_text('keep\n')
    code, _, _ = blinkered('workspace', 'feature_a')
    assert code == 0 and (repo / 'scratch' / 'notes.md').exists()


# Drift


def test_status_detects_missing_and_workspace_resyncs(repo, blinkered):
    blinkered('workspace', 'feature_a')
    with open(repo / 'src' / 'nodes' / 'feature_a' / 'blinkered.toml', 'a') as file:
        file.write('uses = ["feature_b"]\n')
    code, out, _ = blinkered('status')
    assert code == 1 and 'missing: src/nodes/feature_b' in out
    code, _, _ = blinkered('workspace')
    assert code == 0 and on_disk(repo, 'feature_b')
    code, out, _ = blinkered('status')
    assert code == 0 and 'in sync' in out


def test_status_detects_extra(repo, blinkered):
    blinkered('workspace', 'feature_a')
    git(repo, 'sparse-checkout', 'add', 'src/nodes/feature_b')
    code, out, _ = blinkered('status')
    assert code == 1 and 'extra: src/nodes/feature_b' in out


def test_status_reports_leaks(repo, blinkered):
    blinkered('workspace', 'feature_a')
    stray = repo / 'src' / 'nodes' / 'feature_b' / 'notes.txt'
    stray.parent.mkdir()
    stray.write_text('draft\n')
    code, out, _ = blinkered('status')
    assert code == 1 and 'leak: src/nodes/feature_b/notes.txt' in out


def test_manifest_outside_view_still_read(repo, blinkered):
    blinkered('workspace', 'feature_a')
    assert not on_disk(repo, 'lookup')
    _, out, _ = blinkered('closure', 'report')
    assert lines(out) == FULL_CLOSURE


# Layout


def test_file_in_grouping_directory_is_flagged_and_blocks_workspace(repo, blinkered):
    (repo / 'src' / 'nodes' / 'stray.py').write_text('X = 1\n')
    code, out, _ = blinkered('check')
    assert code == 1 and 'layout: src/nodes/stray.py: file in grouping directory' in out
    code, _, err = blinkered('workspace', 'feature_a')
    assert code == 1 and 'stray.py' in err


def test_readme_allowed_in_grouping_directory(repo, blinkered):
    (repo / 'src' / 'nodes' / 'README.md').write_text('nodes\n')
    code, _, _ = blinkered('check')
    assert code == 0


def test_nested_node_is_flagged(repo, blinkered):
    inner = repo / 'src' / 'nodes' / 'feature_a' / 'inner'
    inner.mkdir()
    (inner / 'blinkered.toml').write_text('')
    code, out, _ = blinkered('check')
    assert code == 1 and 'nested inside node src/nodes/feature_a' in out


# Manifests and graph


def test_unknown_edge_target_and_cycle_are_flagged(repo, blinkered):
    with open(repo / 'src' / 'nodes' / 'source' / 'blinkered.toml', 'a') as file:
        file.write('joins = ["ghost", "subset"]\n')
    code, out, _ = blinkered('check')
    assert code == 1
    assert 'joins → unknown node ghost' in out
    assert 'cycle:' in out


def test_malformed_manifest_is_flagged(repo, blinkered):
    (repo / 'src' / 'nodes' / 'feature_b' / 'blinkered.toml').write_text('tags = "x"\n')
    code, out, _ = blinkered('check')
    assert code == 1 and 'manifest: src/nodes/feature_b/blinkered.toml' in out


def test_undeclared_import_is_flagged(repo, blinkered):
    with open(repo / 'src' / 'nodes' / 'feature_a' / 'model.py', 'a') as file:
        file.write('from src.nodes.feature_b import model\n')
    code, out, _ = blinkered('check')
    assert code == 1 and 'import: src/nodes/feature_a/model.py: imports feature_b' in out


# New


def test_new_creates_node_and_adds_it_to_view(repo, blinkered):
    blinkered('workspace', 'feature_a')
    code, _, _ = blinkered('new', 'src/nodes/tdi')
    assert code == 0
    assert (repo / 'src' / 'nodes' / 'tdi' / 'blinkered.toml').exists()
    assert 'src/nodes/tdi' in git(repo, 'sparse-checkout', 'list')
    code, out, _ = blinkered('check')
    assert code == 0 and '10 nodes' in out


def test_new_refuses_inside_node_duplicate_or_root(blinkered):
    assert blinkered('new', 'src/nodes/feature_a/inner')[2].strip().endswith('inside node feature_a')
    assert 'already exists' in blinkered('new', 'src/nodes/feature_a')[2]
    assert 'outside nodes_root' in blinkered('new', 'other/thing')[2]
    assert 'outside nodes_root' in blinkered('new', 'src')[2]
    assert 'root cannot be a node' in blinkered('new', '.')[2]


# Graph

import json


def test_graph_emits_compact_json(blinkered):
    code, out, _ = blinkered('graph')
    assert code == 0 and '\n' not in out.strip()
    data = json.loads(out)
    assert data['version'] == 1 and len(data['nodes']) == 9
    assert {'source': 'report', 'target': 'lookup', 'kind': 'joins'} in data['edges']


def test_graph_closure_filters_and_indent(blinkered):
    code, out, _ = blinkered('graph', 'report', '--via', 'reads,joins', '--exclude-tag', 'infra',
                             '--indent', '2')
    assert code == 0 and out.count('\n') > 5
    data = json.loads(out)
    # derived_from is not followed, so the walk stops at selection and subset
    assert {n['id'] for n in data['nodes']} == {'report', 'selection', 'lookup', 'subset'}
    assert all(e['kind'] in ('reads', 'joins') for e in data['edges'])
    assert len(data['edges']) == 3


def test_graph_of_unknown_node_fails(blinkered):
    code, _, err = blinkered('graph', 'missing')
    assert code == 2 and 'unknown node missing' in err
