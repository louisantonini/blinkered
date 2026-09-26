"""Problems reported by checks."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    message: str

    def __str__(self) -> str:
        return f'{self.kind}: {self.path}: {self.message}'
