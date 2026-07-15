from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import main


class MainCliTests(unittest.TestCase):
    def test_package_smoke_failure_returns_nonzero_and_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with (
                patch.dict(os.environ, {"AUTO_LOAD_OFF_TEST_ROOT": td}),
                patch.object(sys, "argv", ["main.py", "--package-smoke"]),
                patch("app.demo.package_smoke.run_package_smoke", side_effect=RuntimeError("test failure")),
            ):
                exit_code = main.main()

            receipt_path = Path(td) / "__data__" / "package_smoke_receipt.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("RuntimeError: test failure", receipt["error"])
        self.assertFalse(receipt["live_hardware_used"])
        self.assertIn("not live hardware validation", receipt["validation_boundary"])


if __name__ == "__main__":
    unittest.main()
