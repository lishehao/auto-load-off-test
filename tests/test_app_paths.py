from __future__ import annotations

import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.runtime.paths import APP_ROOT_ENV, AppPaths


class AppPathsTests(unittest.TestCase):
    def test_from_root_derives_runtime_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            paths = AppPaths.from_root(Path(td))

        self.assertEqual(paths.config_dir.name, "__config__")
        self.assertEqual(paths.data_dir.name, "__data__")
        self.assertEqual(paths.settings_path.name, "settings.json")
        self.assertEqual(paths.measurement_dir.name, "measurement")

    def test_default_uses_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {}, clear=True):
            previous = Path.cwd()
            try:
                os.chdir(td)
                paths = AppPaths.default()
            finally:
                os.chdir(previous)

        self.assertEqual(paths.root_dir, Path(td).resolve())

    def test_default_can_be_overridden_by_environment(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {APP_ROOT_ENV: td}, clear=True):
            paths = AppPaths.default()

        self.assertEqual(paths.root_dir, Path(td).resolve())


if __name__ == "__main__":
    unittest.main()
