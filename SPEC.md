# blinkered

Work on one node of a repository while the working tree shows only its dependency closure. The graph may grow arbitrarily large and deep.

Standalone command-line tool, installed outside the repositories it manages (`pipx install blinkered`, `uv tool install blinkered`). Language-neutral core; language-specific checks are optional plugins.

## Model

- **Node**: a directory other than the repository root containing `blinkered.toml`. Name = directory name, unique across the repository.
- **Tags**: free labels on a node.
- **Edges**: directed links to other nodes, with free kinds.
- No built-in semantics. Tags and edge kinds may appear or disappear as needed; their meaning belongs to the managed repository.

```toml
# blinkered.toml (in a node directory)
tags = ["measurement"]

[edges]
defined_on = ["pdr_high"]
computed_from = ["agv"]
uses = ["research"]
```

- Manifests are read from the working tree when present, otherwise from the index, so nodes outside the view remain part of the graph.
- Uncommitted manifest edits take effect immediately.

## Layout rules

- **No nesting**: no `blinkered.toml` below another node's directory. Cone mode includes directories recursively, so a parent would pull in its children, and a child would expose its parent's files.
- **Grouping directories**: strict ancestors of node directories that are not nodes, excluding the repository root. They hold no files except an allowlist (default `README.md`); cone mode checks out files directly inside every ancestor of an included directory, so such files are visible in every view below them.
- **Root**: files at the repository root are always visible. It holds globally visible files (configuration, README) and should stay small.
- **Non-node directories**: tracked directories containing no nodes disappear from every view unless they become nodes or are listed in `always`.

## Configuration

`blinkered.toml` at the repository root: repository configuration, not a node manifest. Its presence marks the repository as managed; it is always visible.

```toml
always = ["lib"]                  # directories included in every view
grouping_allow = ["README.md"]    # files allowed in grouping directories

[plugins]
python_imports = true             # code imports must be covered by declared edges
```

## Commands

| Command | Behaviour |
| --- | --- |
| `blinkered closure <node> [--via kinds] [--tag tags]` | Node and its transitive dependencies. |
| `blinkered workspace [<node>]` | Store focus; set cone-mode sparse checkout to the closure's directories plus `always`. Without `<node>`, resync the stored focus. |
| `blinkered workspace --all` | Disable sparse checkout; clear focus. |
| `blinkered status` | Compare view with closure of the stored focus: missing, extra, leaks. Read-only; non-zero exit if out of sync. |
| `blinkered new <node>` | Create directory and `blinkered.toml`; add it to the current view. Refuses inside a node. |
| `blinkered tags` | List tags and edge kinds in use, with counts. |
| `blinkered check` | Report manifest errors, unknown targets, cycles, layout-rule violations and plugin findings. |

## Behaviour

- **Closure**: start at the node, follow outgoing edges to their targets, repeat until no new node is reached. Manifests come from the working tree or the index, so the result is independent of the current view. Output: one node per line. `--via` follows only the listed edge kinds; `--tag` filters the output to nodes with those tags without stopping traversal. Read-only; `workspace` uses the same computation.
- **State**: the focus node name only, stored under `.git/blinkered/`. Patterns are always recomputed from manifests.
- **Guard**: `workspace` and `new` run `check` first and refuse on layout violations.
- **Clean-state rule**: before narrowing, list modified, staged, untracked or ignored paths leaving the view; refuse unless resolved, or `--force` for ignored-only paths.
- **Leaks**: files git keeps on disk outside the cone (modifications, untracked, conflicts) are reported by `status`, not hidden.
- **Remote**: pulls update content within the view but not the pattern set; `status` detects drift, `workspace` resyncs.

## Non-goals

Tests, git hooks, worktrees, data caching, execution of nodes.

## Validated (git 2.50.1, Python 3.12, pytest 9)

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

## To validate

- Editor behaviour in a partial tree (not testable from the shell).
- First real use: a research chain in quant-research (grid → eligibility → RVBR → PDR → pdr_high → agv_rank_pdr_high).
