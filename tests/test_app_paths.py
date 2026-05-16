from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.runtime.paths import AppPaths


class AppPathsTests(unittest.TestCase):
    def test_from_root_derives_runtime_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            paths = AppPaths.from_root(Path(td))

        self.assertEqual(paths.config_dir.name, "__config__")
        self.assertEqual(paths.data_dir.name, "__data__")
        self.assertEqual(paths.settings_path.name, "settings.json")
        self.assertEqual(paths.measurement_dir.name, "measurement")


if __name__ == "__main__":
    unittest.main()

