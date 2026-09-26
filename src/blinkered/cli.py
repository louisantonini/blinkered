"""Command-line entry point."""
import argparse
import sys

import blinkered


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

    commands.add_parser('tags', help='tags and edge kinds in use, with counts')
    commands.add_parser('check', help='manifest, graph and layout validation')
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == 'workspace' and args.all and args.node:
        parser().error('workspace: give a node or --all, not both')
    print(f'blinkered {args.command}: not implemented', file=sys.stderr)
    return 2
