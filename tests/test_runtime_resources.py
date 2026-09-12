from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.runtime.resources import (
    MEASUREMENT_FIXTURE_NAME,
    REFERENCE_FIXTURE_NAME,
    bundled_fixture_path,
    bundled_reference_fixture,
    bundled_resource_root,
)


class RuntimeResourceTests(unittest.TestCase):
    def test_source_bundle_exposes_the_two_existing_fixture_files(self) -> None:
        root = bundled_resource_root()
        measurement = bundled_fixture_path(MEASUREMENT_FIXTURE_NAME)
        reference = bundled_reference_fixture()

        self.assertEqual(root / "demo_data" / MEASUREMENT_FIXTURE_NAME, measurement)
        self.assertEqual(root / "demo_data" / REFERENCE_FIXTURE_NAME, reference)
        self.assertTrue(measurement.is_file())
        self.assertTrue(reference.is_file())

    def test_package_fixture_copies_match_repository_fixture_bytes(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        for name in (MEASUREMENT_FIXTURE_NAME, REFERENCE_FIXTURE_NAME):
            with self.subTest(name=name):
                source = repo_root / "demo_data" / name
                package_copy = repo_root / "src" / "app" / "runtime" / "demo_data" / name
                self.assertEqual(_sha256(source), _sha256(package_copy))

    def test_frozen_resource_root_uses_meipass(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.object(sys, "_MEIPASS", td, create=True):
            self.assertEqual(bundled_resource_root(), Path(td).resolve())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
