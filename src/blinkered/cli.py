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

    workspace = commands.add_parser('workspace', help='narrow the working tree to a closure')
    workspace.add_argument('node', nargs='?', help='new focus; omit to resync the stored focus')
    workspace.add_argument('--all', action='store_true', help='restore the full working tree')
    workspace.add_argument('--force', action='store_true', help='allow ignored-only paths to leave the view')

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


def view(nodes, config, focus):
    return sorted({nodes[id].directory for id in closure(nodes, find(nodes, focus))}
                  | set(config.always))


def run_closure(root, config, nodes, errors, args):
    print('\n'.join(closure(nodes, find(nodes, args.node), via=args.via, tags=args.tag)))
    return 0


def run_workspace(root, config, nodes, errors, args):
    if args.all:
        if git.sparse_patterns(root) is not None:
            git.sparse_disable(root)
        state.write_focus(root, None)
        print('full working tree')
        return 0
    focus = args.node or state.read_focus(root)
    if focus is None:
        raise Failure('no focus: give a node')
    focus = find(nodes, focus)
    blocking = list(errors) + checks.layout(root, config, nodes)
    if blocking:
        report('refusing: fix these first (blinkered check)', blocking)
        return 1
    keep = view(nodes, config, focus)
    work, ignored = checks.leaving(root, keep)
    if work or (ignored and not args.force):
        report('refusing: these paths would leave the view', work + ignored)
        if ignored and not work:
            print('ignored files only: rerun with --force to delete them', file=sys.stderr)
        return 1
    git.sparse_set(root, keep)
    state.write_focus(root, focus)
    print(f'focus: {focus}')
    print('\n'.join(f'  {d}' for d in keep))
    return 0


def run_status(root, config, nodes, errors, args):
    focus = state.read_focus(root)
    current = git.sparse_patterns(root)
    if focus is None:
        print('focus: none')
        print('view: full' if current is None else f'view: sparse, {len(current)} directories')
        return 0 if current is None else 1
    expected = set(view(nodes, config, focus))
    current = set(current or [])
    missing, extra = sorted(expected - current), sorted(current - expected)
    leaked = checks.leaks(root, sorted(current)) if current else []
    print(f'focus: {focus}')
    for label, items in (('missing', missing), ('extra', extra)):
        for item in items:
            print(f'{label}: {item}')
    for finding in leaked:
        print(f'leak: {finding.path} ({finding.message})')
    if missing or extra or leaked:
        print('→ run `blinkered workspace` to resync' if missing or extra else '→ resolve leaks')
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
    if args.command == 'workspace' and args.all and args.node:
        parser().error('workspace: give a node or --all, not both')
    try:
        git.require_version(Path.cwd())
        root = git.repo_root(Path.cwd())
        config = configuration.load(root)
        nodes, errors = discover(root, config.nodes_root)
        return COMMANDS[args.command](root, config, nodes, errors, args)
    except (Failure, git.GitError, configuration.NotManaged, ValueError) as error:
        print(f'blinkered: {error}', file=sys.stderr)
        return 2
