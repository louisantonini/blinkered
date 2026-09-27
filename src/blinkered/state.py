"""Workspace selection state, stored under `.git/blinkered/`."""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from . import git


@dataclass(frozen=True)
class Selection:
    """Foci of a view: explicit nodes plus nodes chosen by tags."""
    nodes: tuple[str, ...] = ()
    tags: tuple[str, ...] | None = None
    exclude_tags: tuple[str, ...] = ()
    force: bool = False

    @property
    def by_tags(self) -> bool:
        return self.tags is not None or bool(self.exclude_tags)

    def describe(self) -> str:
        """E.g. `report`, `report, tagged study`, `all except tagged legacy`."""
        chosen = list(self.nodes)
        if self.tags is not None:
            chosen.append('tagged ' + ','.join(self.tags))
        text = ', '.join(chosen) or 'all'
        if self.exclude_tags:
            text += ' except tagged ' + ','.join(self.exclude_tags)
        return text


def _file(root: Path) -> Path:
    return git.git_dir(root) / 'blinkered' / 'focus'


def read_selection(root: Path) -> Selection | None:
    file = _file(root)
    if not file.is_file():
        return None
    text = file.read_text().strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return Selection(nodes=(text,))  # single node name, as written by earlier versions
    tags = data.get('tags')
    return Selection(nodes=tuple(data.get('nodes', ())), tags=None if tags is None else tuple(tags),
                     exclude_tags=tuple(data.get('exclude_tags', ())), force=bool(data.get('force')))


def write_selection(root: Path, selection: Selection | None) -> None:
    """Store the selection; None clears it."""
    file = _file(root)
    if selection is None:
        file.unlink(missing_ok=True)
        return
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(asdict(selection)) + '\n')
