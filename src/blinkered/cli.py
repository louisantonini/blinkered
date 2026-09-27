"""Command-line entry point."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import blinkered
from . import checks, config as configuration, git, state
from .config import FILENAME
from .manifest import discover, node_id
from .graph import Unresolved, closure, export, resolve


def csv(value: str) -> list[str]:
    return [item for item in value.split(',') if item]


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog='blinkered', description=blinkered.__doc__)
    commands = root.add_subparsers(dest='command', required=True)

    closure = commands.add_parser('closure', help='node and its transitive dependencies')
    closure.add_argument('node')
    closure.add_argument('--via', type=csv, help='edge kinds to follow, comma-separated')
    closure.add_argument('--tag', type=csv, help='output only nodes with these tags')
    closure.add_argument('--exclude-tag', type=csv, help='omit nodes with these tags from the output')

    workspace = commands.add_parser('workspace', help='narrow the working tree to the closures of foci')
    workspace.add_argument('nodes', nargs='*', help='foci; omit everything to resync the stored selection')
    workspace.add_argument('--tag', type=csv, help='also focus on every node with these tags')
    workspace.add_argument('--exclude-tag', type=csv,
                           help='focus on every node without these tags (with --tag: among those) and keep them out')
    workspace.add_argument('--all', action='store_true', help='restore the full working tree')
    workspace.add_argument('--force', action='store_true',
                           help='exclude needed nodes anyway; allow ignored-only paths to leave the view')

    commands.add_parser('status', help='compare the view with the closure of the focus')

    new = commands.add_parser('new', help='create a node and add it to the view')
    new.add_argument('directory')

    graph = commands.add_parser('graph', help='nodes and edges as JSON')
    graph.add_argument('node', nargs='?', help='restrict to the closure of this node')
    graph.add_argument('--via', type=csv, help='edge kinds to follow and emit, comma-separated')
    graph.add_argument('--tag', type=csv, help='emit only nodes with these tags')
    graph.add_argument('--exclude-tag', type=csv, help='omit nodes with these tags')
    graph.add_argument('--indent', type=int, help='pretty-print with this indent')

    commands.add_parser('tags', help='tags and edge kinds in use, with counts')
    commands.add_parser('check', help='manifest, graph and layout validation')
    return root


class Failure(Exception):
    pass


def report(title, findings):
    print(title, file=sys.stderr)
    for finding in findings:
        print(f'  {finding}', file=sys.stderr)


def find(nodes, reference):
    try:
        return resolve(nodes, reference)
    except Unresolved as error:
        raise Failure(str(error)) from None


def run_closure(root, config, nodes, errors, args):
    print('\n'.join(closure(nodes, find(nodes, args.node), via=args.via, tags=args.tag,
                            exclude_tags=args.exclude_tag)))
    return 0


def plan(nodes, config, selection):
    """Foci, view directories and conflicts (excluded nodes needed by kept foci) of a selection."""
    foci = {find(nodes, node) for node in selection.nodes}
    if selection.by_tags:
        wanted = None if selection.tags is None else set(selection.tags)
        foci |= {id for id, node in nodes.items()
                 if (wanted is None or wanted & set(node.tags))
                 and not set(selection.exclude_tags) & set(node.tags)}
    if not foci:
        raise Failure(f'no node matches: {selection.describe()}')
    closures = {focus: set(closure(nodes, focus)) for focus in foci}
    ids = set().union(*closures.values())
    excluded = {id for id in ids if set(selection.exclude_tags) & set(nodes[id].tags)}
    conflicts = {id: sorted(f for f, members in closures.items() if id in members and f != id)
                 for id in sorted(excluded)}
    kept = ids - excluded if selection.force else ids
    directories = sorted({nodes[id].directory for id in kept} | set(config.always))
    return sorted(foci), directories, conflicts


def report_conflicts(conflicts, nodes, stream):
    for id, needed_by in conflicts.items():
        tags = ','.join(nodes[id].tags)
        print(f'  {id} ({tags}) ← needed by {", ".join(needed_by) or id}', file=stream)


def run_workspace(root, config, nodes, errors, args):
    if args.all:
        if git.sparse_patterns(root) is not None:
            git.sparse_disable(root)
        state.write_selection(root, None)
        print('full working tree')
        return 0
    if args.nodes or args.tag is not None or args.exclude_tag:
        selection = state.Selection(nodes=tuple(args.nodes),
                                    tags=None if args.tag is None else tuple(args.tag),
                                    exclude_tags=tuple(args.exclude_tag or ()), force=args.force)
    else:
        selection = state.read_selection(root)
        if selection is None:
            raise Failure('no focus: give a node or a tag selection')
        selection = state.Selection(selection.nodes, selection.tags, selection.exclude_tags,
                                    selection.force or args.force)
    blocking = list(errors) + checks.layout(root, config, nodes)
    if blocking:
        report('refusing: fix these first (blinkered check)', blocking)
        return 1
    foci, keep, conflicts = plan(nodes, config, selection)
    if conflicts and not selection.force:
        print('refusing: excluded nodes are needed by kept ones', file=sys.stderr)
        report_conflicts(conflicts, nodes, sys.stderr)
        print('rerun with --force to exclude them anyway (their dependants may break)', file=sys.stderr)
        return 1
    work, ignored = checks.leaving(root, keep)
    if work or (ignored and not args.force):
        report('refusing: these paths would leave the view', work + ignored)
        if ignored and not work:
            print('ignored files only: rerun with --force to delete them', file=sys.stderr)
        return 1
    git.sparse_set(root, keep)
    state.write_selection(root, selection)
    print(f'focus: {selection.describe()}')
    if conflicts:
        print('excluded although needed:')
        report_conflicts(conflicts, nodes, sys.stdout)
    print('\n'.join(f'  {d}' for d in keep))
    return 0


def run_status(root, config, nodes, errors, args):
    selection = state.read_selection(root)
    current = git.sparse_patterns(root)
    if selection is None:
        print('focus: none')
        print('view: full' if current is None else f'view: sparse, {len(current)} directories')
        return 0 if current is None else 1
    _, directories, conflicts = plan(nodes, config, selection)
    expected, current = set(directories), set(current or [])
    missing, extra = sorted(expected - current), sorted(current - expected)
    leaked = checks.leaks(root, sorted(current)) if current else []
    print(f'focus: {selection.describe()}')
    for label, items in (('missing', missing), ('extra', extra)):
        for item in items:
            print(f'{label}: {item}')
    for finding in leaked:
        print(f'leak: {finding.path} ({finding.message})')
    for id, needed_by in conflicts.items():
        label = 'broken' if selection.force else 'conflict'
        print(f'{label}: {id} excluded but needed by {", ".join(needed_by) or id}')
    unforced = bool(conflicts) and not selection.force
    if missing or extra or leaked or unforced:
        if unforced:
            print('→ excluded nodes became needed: change the selection or rerun with --force')
        elif missing or extra:
            print('→ run `blinkered workspace` to resync')
        else:
            print('→ resolve leaks')
        return 1
    print('in sync')
    return 0


def run_new(root, config, nodes, errors, args):
    directory = (Path.cwd() / args.directory).resolve().relative_to(root.resolve()).as_posix()
    if directory in ('', '.'):
        raise Failure('the repository root cannot be a node')
    id = node_id(directory, config.nodes_root)
    if id is None:
        raise Failure(f'outside nodes_root {config.nodes_root}')
    if id in nodes:
        raise Failure(f'node {id} already exists')
    for node in nodes.values():
        if directory.startswith(node.directory + '/'):
            raise Failure(f'inside node {node.id}')
        if node.directory.startswith(directory + '/'):
            raise Failure(f'would contain node {node.id}')
    path = root / directory
    path.mkdir(parents=True, exist_ok=True)
    (path / FILENAME).write_text('tags = []\n\n[edges]\n')
    if git.sparse_patterns(root) is not None:
        git.sparse_add(root, [directory])
    print(f'created {directory}/{FILENAME}')
    return 0


def run_graph(root, config, nodes, errors, args):
    start = None if args.node is None else find(nodes, args.node)
    data = export(nodes, start, via=args.via, tags=args.tag, exclude_tags=args.exclude_tag)
    separators = (',', ':') if args.indent is None else None
    print(json.dumps(data, indent=args.indent, separators=separators, ensure_ascii=False))
    return 0


def run_tags(root, config, nodes, errors, args):
    tags = Counter(tag for node in nodes.values() for tag in node.tags)
    kinds = Counter(kind for node in nodes.values() for kind, targets in node.edges.items()
                    for _ in targets)
    for title, counts in (('tags', tags), ('edge kinds', kinds)):
        print(f'{title}:')
        for item, count in counts.most_common():
            print(f'  {count:>4}  {item}')
    return 0


def run_check(root, config, nodes, errors, args):
    findings = checks.check(root, config, nodes, errors)
    for finding in findings:
        print(finding)
    print(f'{len(nodes)} nodes, {len(findings)} findings')
    return 1 if findings else 0


COMMANDS = {'closure': run_closure, 'workspace': run_workspace, 'status': run_status,
            'new': run_new, 'graph': run_graph, 'tags': run_tags, 'check': run_check}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == 'workspace' and args.all and (args.nodes or args.tag or args.exclude_tag):
        parser().error('workspace: give foci or --all, not both')
    try:
        git.require_version(Path.cwd())
        root = git.repo_root(Path.cwd())
        config = configuration.load(root)
        nodes, errors = discover(root, config.nodes_root)
        return COMMANDS[args.command](root, config, nodes, errors, args)
    except (Failure, git.GitError, configuration.NotManaged, ValueError) as error:
        print(f'blinkered: {error}', file=sys.stderr)
        return 2
