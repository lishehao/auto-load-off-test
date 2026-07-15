from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.demo.package_smoke import RECEIPT_NAME, VALIDATION_BOUNDARY, run_package_smoke


class PackageSmokeTests(unittest.TestCase):
    def test_package_smoke_exports_and_reloads_fixture_without_hardware(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            runtime_root = Path(td)
            receipt_path = run_package_smoke(runtime_root=runtime_root, resource_root=repo_root)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

            self.assertEqual(receipt_path, (runtime_root / "__data__" / RECEIPT_NAME).resolve())
            self.assertEqual(receipt["status"], "passed")
            self.assertEqual(receipt["source"], "mock_fixture")
            self.assertEqual(receipt["point_count"], 72)
            self.assertFalse(receipt["live_hardware_used"])
            self.assertEqual(receipt["validation_boundary"], VALIDATION_BOUNDARY)
            self.assertEqual(len(receipt["artifacts"]), 3)
            for artifact in receipt["artifacts"]:
                path = Path(artifact)
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
