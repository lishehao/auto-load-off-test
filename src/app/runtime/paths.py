from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


APP_ROOT_ENV = "AUTO_LOAD_OFF_TEST_ROOT"


@dataclass(frozen=True, slots=True)
class AppPaths:
    root_dir: Path
    config_dir: Path
    data_dir: Path

    @classmethod
    def from_root(cls, root_dir: Path) -> "AppPaths":
        root = root_dir.resolve()
        return cls(
            root_dir=root,
            config_dir=root / "__config__",
            data_dir=root / "__data__",
        )

    @classmethod
    def default(cls) -> "AppPaths":
        configured_root = os.environ.get(APP_ROOT_ENV)
        if configured_root:
            return cls.from_root(Path(configured_root))
        return cls.from_root(Path.cwd())

    @property
    def settings_path(self) -> Path:
        return self.config_dir / "settings.json"

    @property
    def measurement_dir(self) -> Path:
        return self.data_dir / "measurement"
