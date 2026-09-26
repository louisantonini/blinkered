# blinkered

Work on one node of a repository while the working tree shows only its dependency closure.

Each node is a directory with a `blinkered.toml` manifest declaring free-form tags and edges to other nodes. `blinkered workspace <node>` narrows the working tree, through git's cone-mode sparse checkout, to that node and everything it depends on. The graph can grow arbitrarily large and deep while each piece of work stays small.

## Usage

```toml
# blinkered.toml at the repository root: configuration
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
blinkered status              # compare the view with the closure after pulls or edits
blinkered workspace           # resync the stored focus
blinkered workspace --all     # restore the full working tree
```

See [SPEC.md](SPEC.md) for the model, layout rules and full behaviour.

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
