from __future__ import annotations

import ast
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_APP = PROJECT_ROOT / "src" / "app"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def py_files(base: Path) -> list[Path]:
    return [path for path in base.rglob("*.py") if "__pycache__" not in path.parts]


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_domain_stays_pure(self) -> None:
        forbidden_prefixes = ("tkinter", "pyvisa", "serial", "matplotlib", "app.infrastructure", "app.presentation")
        offenders = []
        for path in py_files(SRC_APP / "domain"):
            for module in imported_modules(path):
                if module.startswith(forbidden_prefixes):
                    offenders.append((path.relative_to(PROJECT_ROOT), module))

        self.assertEqual(offenders, [])

    def test_application_does_not_import_infrastructure_or_presentation(self) -> None:
        forbidden_prefixes = ("app.infrastructure", "app.presentation")
        offenders = []
        for path in py_files(SRC_APP / "application"):
            for module in imported_modules(path):
                if module.startswith(forbidden_prefixes):
                    offenders.append((path.relative_to(PROJECT_ROOT), module))

        self.assertEqual(offenders, [])

    def test_presentation_does_not_import_infrastructure(self) -> None:
        offenders = []
        for path in py_files(SRC_APP / "presentation"):
            for module in imported_modules(path):
                if module.startswith("app.infrastructure"):
                    offenders.append((path.relative_to(PROJECT_ROOT), module))

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()

