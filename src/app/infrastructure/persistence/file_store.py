from __future__ import annotations

from pathlib import Path


class FileStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def exists(self) -> bool:
        return self.path.exists()

    def read_text(self, *, encoding: str = "utf-8") -> str:
        return self.path.read_text(encoding=encoding)

    def write_text(self, data: str, *, encoding: str = "utf-8") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(data, encoding=encoding)
