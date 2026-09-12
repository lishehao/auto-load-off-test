from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


APP_ROOT_ENV = "AUTO_LOAD_OFF_TEST_ROOT"
APP_NAME = "Auto-Load-off-Test"


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
        return cls.from_root(_user_data_root())

    @property
    def settings_path(self) -> Path:
        return self.config_dir / "settings.json"

    @property
    def measurement_dir(self) -> Path:
        return self.data_dir / "measurement"


def _user_data_root() -> Path:
    """Return the platform's per-user writable application-data location.

    Existing working-directory configs are intentionally left untouched. Users
    can opt into a specific runtime root with AUTO_LOAD_OFF_TEST_ROOT.
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Roaming") / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / APP_NAME
