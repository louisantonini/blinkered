# blinkered

Work on one node of a repository while the working tree shows only its dependency closure. The graph may grow arbitrarily large and deep.

Standalone command-line tool, installed outside the repositories it manages (`pipx install blinkered`, `uv tool install blinkered`). Language-neutral core; language-specific checks are optional plugins.

## Model

- **Node**: a directory other than the repository root containing `blinkered.toml`.
- **Id**: the node directory's path relative to `nodes_root` (e.g. `rvbr/pdr`); unique by construction. Grouping directories act as namespaces.
- **Short name**: the last segment of the id (e.g. `pdr`). Usable wherever an id is expected, as long as it is unique across the repository.
- **Tags**: free labels on a node.
- **Edges**: directed links to other nodes, with free kinds.
- No built-in semantics. Tags and edge kinds may appear or disappear as needed; their meaning belongs to the managed repository.

```toml
# blinkered.toml (in a node directory)
tags = ["transform"]

[edges]
reads = ["selection"]
joins = ["pipeline/lookup"]      # full id
uses = ["utils"]                 # short name, unique
```

- **References**: edge targets and command arguments accept a full id or a unique short name. A full id takes precedence over short names. An ambiguous short name is an error; the full id resolves it.
- Manifests are read from the working tree when present, otherwise from the index, so nodes outside the view remain part of the graph.
- Uncommitted manifest edits take effect immediately.

## Layout rules

- **No nesting**: no `blinkered.toml` below another node's directory. Cone mode includes directories recursively, so a parent would pull in its children, and a child would expose its parent's files.
- **Grouping directories**: strict ancestors of node directories that are not nodes, excluding the repository root. They hold no files except an allowlist (default `README.md`); cone mode checks out files directly inside every ancestor of an included directory, so such files are visible in every view below them.
- **Root**: files at the repository root are always visible. It holds globally visible files (configuration, README) and should stay small.
- **Nodes outside `nodes_root`**: not allowed; reported by `check`.
- **Non-node directories**: tracked directories containing no nodes disappear from every view unless they become nodes or are listed in `always`.

## Configuration

`blinkered.toml` at the repository root: repository configuration, not a node manifest. Its presence marks the repository as managed; it is always visible.

```toml
nodes_root = "nodes"              # ids are paths relative to this directory; default: repository root
always = ["lib"]                  # directories included in every view
grouping_allow = ["README.md"]    # files allowed in grouping directories

[plugins]
python_imports = true             # code imports must be covered by declared edges
```

## Commands

| Command | Behaviour |
| --- | --- |
| `blinkered closure <node> [--via kinds] [--tag tags] [--exclude-tag tags]` | Node and its transitive dependencies. |
| `blinkered workspace [<node> ...] [--tag tags] [--exclude-tag tags] [--force]` | Store the selection; set cone-mode sparse checkout to the union of the foci's closures plus `always`. Without arguments, resync the stored selection. |
| `blinkered workspace --all` | Disable sparse checkout; clear the selection. |
| `blinkered status` | Compare view with closure of the stored focus: missing, extra, leaks. Read-only; non-zero exit if out of sync. |
| `blinkered new <node>` | Create directory and `blinkered.toml`; add it to the current view. Refuses inside a node. |
| `blinkered graph [<node>] [--via kinds] [--tag tags] [--exclude-tag tags] [--indent n]` | Emit nodes and resolved edges as JSON; with `<node>`, only its closure. |
| `blinkered tags` | List tags and edge kinds in use, with counts. |
| `blinkered check` | Report manifest errors, unknown or ambiguous targets, cycles, layout-rule violations and plugin findings. |

## Behaviour

- **Closure**: start at the node, follow outgoing edges to their targets, repeat until no new node is reached. Manifests come from the working tree or the index, so the result is independent of the current view. Output: one full id per line. `--via` follows only the listed edge kinds; `--tag` keeps and `--exclude-tag` omits nodes with those tags in the output, without stopping traversal. Read-only; `workspace` uses the same computation.
- **Graph**: one neutral format, JSON; displaying it is up to the user. Nodes are selected by the closure of `<node>` (along `--via`) or all nodes, then filtered by `--tag`/`--exclude-tag`; an edge is emitted when its kind passes `--via` and both ends are emitted. Edges use full ids; unresolved references are omitted (`check` reports them). Output is sorted and compact unless `--indent` is given.

```json
{"version": 1,
 "nodes": [{"id": "rvbr/gbs", "directory": "src/rvbr/gbs", "tags": []}],
 "edges": [{"source": "rvbr/gbs", "target": "rvbr/population", "kind": "defined_on"}]}
```

- **Selection**: foci are the given nodes plus, when `--tag` or `--exclude-tag` is given, every node with (`--tag`) and without (`--exclude-tag`) those tags; `--exclude-tag` alone selects every node without them. The view is the union of the foci's closures, which is always closed under dependencies.
- **Exclusion conflicts**: a node with an excluded tag that a kept focus needs. Without `--force`, `workspace` refuses and lists each conflict with the foci needing it; with `--force`, the excluded nodes leave the view anyway and their dependants may break. `status` reports forced conflicts as `broken`.
- **State**: the selection (nodes, tags, excluded tags, force), stored under `.git/blinkered/`; a single node name written by earlier versions is still read. Patterns are always recomputed from manifests, so a resync picks up nodes newly matching the tags.
- **Guard**: `workspace` and `new` run `check` first and refuse on layout violations.
- **Clean-state rule**: before narrowing, list modified, staged, untracked or ignored paths leaving the view; refuse unless resolved, or `--force` for ignored-only paths. `--force` overrides refusals; it never overrides uncommitted work.
- **Leaks**: files git keeps on disk outside the cone (modifications, untracked, conflicts) are reported by `status`, not hidden.
- **Remote**: pulls update content within the view but not the pattern set; `status` detects drift, `workspace` resyncs.

## Git behaviour (git 2.50.1, Python 3.12, pytest 9)

Observed behaviour the guards are built on.

Narrowing (`git sparse-checkout set`) always exits 0; the tool must do its own checks.

| Path leaving the view | Git behaviour |
| --- | --- |
| Tracked, clean | Removed from disk. |
| Tracked, modified | Kept on disk with a warning; remains visible. |
| New file, staged | Removed from disk; content kept in the index; returns when widened. |
| Untracked | Kept on disk with a warning; remains visible. |
| Ignored, in a directory with no untracked files | Deleted without warning; not recoverable. |
| Ignored, next to untracked files | Kept. |
| Ignored, in a directory that never had tracked files | Kept. |

- Manifests outside the view are readable via `git ls-files` and `git show :path` (also `HEAD:path`), with or without sparse index. With sparse index, `ls-files` expands the index and prints hints.
- Pull: new files in included directories appear; new node directories do not; patterns unchanged.
- Conflict outside the view: file materialises; plain `git add` refuses; resolve with `git add --sparse`, commit, `git sparse-checkout reapply`.
- Python: nodes in view import normally; importing a node outside the view raises `ModuleNotFoundError`, including undeclared transitive imports.
- A package `__init__.py` importing its sibling nodes breaks every import in a partial tree. Node `__init__.py` files must not import siblings.
- pytest: whole-tree runs collect only tests in view; an explicit path outside the view errors with "file or directory not found".

Consequences for the clean-state rule: refuse narrowing when any modified, staged, untracked or ignored path would leave the view; ignored paths are the only case of silent loss.
