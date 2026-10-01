# blinkered

Work on one node of a repository while the working tree shows only its dependency closure.

Each node is a directory with a `blinkered.toml` manifest declaring free-form tags and edges to other nodes. A node's id is its path below `nodes_root` (e.g. `rvbr/pdr`), so directories that group nodes act as namespaces; edges may use the full id or, when unique, the last segment. `blinkered workspace <node>` narrows the working tree, through git's cone-mode sparse checkout, to that node and everything it depends on. The graph can grow arbitrarily large and deep while each piece of work stays small.

## Requirements

Python 3.11 or later and git 2.35 or later. Tested with git 2.50.

## Installation

```sh
pipx install blinkered    # or: uv tool install blinkered, pip install blinkered
```

## Usage

```toml
# blinkered.toml at the repository root: configuration
nodes_root = "src/nodes"
always = ["lib"]

[plugins]
python_imports = true
```

```toml
# src/nodes/report/blinkered.toml: a node
tags = ["transform"]

[edges]
reads = ["selection"]
joins = ["lookup"]
```

```sh
blinkered check               # validate manifests, graph and layout
blinkered closure report      # report and its transitive dependencies
blinkered workspace report    # narrow the working tree to that closure
blinkered workspace a b       # union of several closures
blinkered workspace --exclude-tag legacy   # everything except legacy nodes
blinkered status              # compare the view with the closure after pulls or edits
blinkered workspace           # resync the stored selection
blinkered workspace --all     # restore the full working tree
blinkered graph               # nodes and edges as JSON
```

See [SPEC.md](https://github.com/louisantonini/blinkered/blob/main/SPEC.md) for the model, layout rules and full behaviour.

## Example

A repository with six nodes, each a directory with a manifest:

```text
blinkered.toml            # root configuration: nodes_root = "nodes"
nodes/
├── utils/                # tags = ["infra"]
├── source/               # uses = ["utils"]
├── cleaned/              # reads = ["source"]
├── lookup/               # reads = ["source"]
├── report/               # reads = ["cleaned"], joins = ["lookup"]
└── sketch/               # reads = ["source"]
```

`report` depends on everything except `sketch`:

```console
$ blinkered closure report
report
cleaned
lookup
source
utils
```

Focusing on `report` removes `sketch` from the working tree; the other nodes and root files stay:

```console
$ blinkered workspace report
focus: report
  nodes/cleaned
  nodes/lookup
  nodes/report
  nodes/source
  nodes/utils
```

Uncommitted work never disappears silently. With an edit in `sketch`, narrowing is refused:

```console
$ blinkered workspace report
refusing: these paths would leave the view
  modified: nodes/sketch/sketch.py: would stay on disk outside the view
```

When an edit or a pull changes the graph, `status` reports the drift and `workspace` resyncs. After adding `uses = ["sketch"]` to `report`:

```console
$ blinkered status
focus: report
missing: nodes/sketch
→ run `blinkered workspace` to resync

$ blinkered workspace
focus: report
  nodes/cleaned
  nodes/lookup
  nodes/report
  nodes/sketch
  nodes/source
  nodes/utils
```

## Graph

`blinkered graph` emits the graph as JSON (`version`, `nodes`, `edges`) for any tool to display. Filters on tags and edge kinds come first; a node then restricts it to what it depends on and what depends on it, each to a number of steps:

```sh
blinkered graph report --via reads,joins --exclude-tag infra --indent 2   # filtered, around report
blinkered graph subset --dependencies 0 --dependents 1                   # direct dependents only
```

Each edge is flagged `implied` when another path joins the same nodes. For example, a Mermaid flowchart with `jq`, without implied edges:

```sh
blinkered graph | jq -r '"flowchart LR", (.edges[] | select(.implied | not) |
  "  \(.source | gsub("/"; "_"))[\(.source)] -- \(.kind) --> \(.target | gsub("/"; "_"))[\(.target)]")'
```

## Scope

blinkered manages what the working tree shows. It does not run tests, install git hooks, use worktrees, cache data or execute nodes.

## Caveats

- `workspace --force` deletes ignored files inside nodes leaving the view; git removes them and they cannot be recovered. Without `--force`, blinkered refuses and lists them.
- Merge conflicts in files outside the view appear on disk; resolve them with `git add --sparse`, commit, then `blinkered workspace`.
- Package `__init__.py` files must not import sibling nodes, or every import fails in a partial tree.
- Nodes cannot nest, and directories that group nodes may only hold a `README.md` by default (`grouping_allow`); other files there would be visible in every view.

## Development

```sh
pip install -e '.[dev]'
pytest -q
```
