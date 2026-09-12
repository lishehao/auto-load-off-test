from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import savemat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.dto import SaveArtifacts
from app.application.services.calibration_receipts import build_analysis_reference_receipt
from app.application.services.measurement_workspace import MeasurementWorkspace, save_displayed_data
from app.application.use_cases.load_measurement import LoadMeasurementUseCase
from app.application.use_cases.load_reference import LoadReferenceUseCase
from app.application.use_cases.save_measurement import SaveMeasurementUseCase
from app.domain.models import ReferenceCurve, SweepPoint, SweepResult
from app.infrastructure.persistence.measurement_loader import MeasurementLoader
from app.infrastructure.persistence.measurement_repo_mat_csv import MatCsvMeasurementRepository
from app.infrastructure.persistence.reference_repo_mat import MatReferenceRepository


ROOT = Path(__file__).resolve().parents[1]


def _workspace() -> MeasurementWorkspace:
    repository = MatCsvMeasurementRepository()
    return MeasurementWorkspace(
        LoadMeasurementUseCase(repository),
        LoadReferenceUseCase(MatReferenceRepository()),
    )


class MeasurementWorkspaceTests(unittest.TestCase):
    def test_document_is_loaded_from_snapshot_after_original_is_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            original = Path(td) / "measurement.csv"
            original.write_text("freq_hz,gain_db\n1000,0\n2000,6.020599913279624\n", encoding="utf-8")
            with _workspace() as workspace:
                loaded, original_path, snapshot = workspace.read_document(original)
                original.unlink()

                self.assertEqual(original_path, original.resolve())
                self.assertTrue(snapshot.is_file())
                self.assertEqual(len(loaded.result.points), 2)
                self.assertEqual(loaded.result.meta["reference_correction"], "none")
                self.assertEqual(loaded.result.meta["dataset"], "canonical")
                self.assertEqual(len(MeasurementLoader().load(str(snapshot)).result.points), 2)

    def test_reference_is_loaded_from_snapshot_after_original_is_deleted(self) -> None:
        source = ROOT / "demo_data" / "hyperframe_reference_fixture.mat"
        with tempfile.TemporaryDirectory() as td:
            original = Path(td) / source.name
            original.write_bytes(source.read_bytes())
            with _workspace() as workspace:
                curve, interpolator, original_path, snapshot = workspace.read_reference(original)
                original.unlink()

                self.assertEqual(original_path, original.resolve())
                self.assertTrue(snapshot.is_file())
                values = interpolator(np.array([1_000.0, 2_000.0]))
                self.assertEqual(curve.freq_hz.size, 72)
                self.assertEqual(values.shape, (2,))
                self.assertTrue(np.all(np.isfinite(values)))

    def test_snapshot_result_is_stable_mat_in_same_workspace(self) -> None:
        source = ROOT / "demo_data" / "hyperframe_simulated_fixture.mat"
        repository = MatCsvMeasurementRepository()
        loaded = LoadMeasurementUseCase(repository).execute(str(source))
        partial = SweepResult(points=loaded.result.points[:3], meta=dict(loaded.result.meta))
        save = SaveMeasurementUseCase(repository)

        with _workspace() as workspace:
            first = workspace.snapshot_result(partial, None, save)
            second = workspace.snapshot_result(partial, None, save)
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_file())
            self.assertTrue(second.is_file())
            self.assertEqual(len(MeasurementLoader().load(str(first)).result.points), 3)
            self.assertEqual(len(MeasurementLoader().load(str(second)).result.points), 3)
            workspace_root = workspace.root

        self.assertFalse(workspace_root.exists())

    def test_analysis_reference_receipt_uses_result_frequencies_and_declares_no_apply(self) -> None:
        curve = ReferenceCurve(
            freq_hz=np.array([100.0, 200.0]),
            gain_db=np.array([0.0, 1.0]),
            phase_deg=np.array([1.0, 2.0]),
        )
        result = SweepResult(
            points=[
                SweepPoint(freq_hz=50.0, gain_linear=1.0, gain_db=0.0),
                SweepPoint(freq_hz=250.0, gain_linear=1.0, gain_db=0.0),
            ],
            meta={"reference_correction": "none"},
        )

        receipt = build_analysis_reference_receipt(
            path=Path("/tmp/reference.mat"),
            curve=curve,
            result=result,
            requested_correction="magnitude",
            coverage="clamp",
        )

        self.assertIn("Reference: reference.mat", receipt.summary)
        self.assertIn("outside 2", receipt.summary)
        self.assertIn("requested magnitude", receipt.summary)
        self.assertIn("current result none", receipt.summary)
        self.assertIn("Coverage policy: clamp", receipt.summary)
        self.assertIn("current plot unchanged", receipt.summary)
        self.assertTrue(any("2 result points" in warning for warning in receipt.warnings))

    def test_same_named_inputs_keep_independent_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            first_dir = Path(td) / "first"
            second_dir = Path(td) / "second"
            first_dir.mkdir()
            second_dir.mkdir()
            first = first_dir / "same.csv"
            second = second_dir / "same.csv"
            first.write_text("freq_hz,gain_db\n1000,0\n", encoding="utf-8")
            second.write_text("freq_hz,gain_db\n2000,6\n", encoding="utf-8")
            with _workspace() as workspace:
                first_loaded, _, first_snapshot = workspace.read_document(first)
                second_loaded, _, second_snapshot = workspace.read_document(second)

                self.assertNotEqual(first_snapshot, second_snapshot)
                self.assertEqual(first_loaded.result.points[0].freq_hz, 1000.0)
                self.assertEqual(second_loaded.result.points[0].freq_hz, 2000.0)
                self.assertEqual(MeasurementLoader().load(str(first_snapshot)).result.points[0].freq_hz, 1000.0)

    def test_same_named_references_keep_independent_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            first_dir = Path(td) / "first"
            second_dir = Path(td) / "second"
            first_dir.mkdir()
            second_dir.mkdir()
            first = first_dir / "ref.mat"
            second = second_dir / "ref.mat"
            savemat(first, {"freq_hz": [100.0, 200.0], "gain_db": [0.0, 1.0]})
            savemat(second, {"freq_hz": [100.0, 200.0], "gain_db": [10.0, 11.0]})
            with _workspace() as workspace:
                first_curve, _, _, first_snapshot = workspace.read_reference(first)
                second_curve, _, _, second_snapshot = workspace.read_reference(second)

                self.assertNotEqual(first_snapshot, second_snapshot)
                self.assertEqual(first_curve.gain_db[0], 0.0)
                self.assertEqual(second_curve.gain_db[0], 10.0)
                self.assertEqual(first_snapshot.read_bytes(), first.read_bytes())

    def test_save_displayed_data_publishes_three_files_exclusively(self) -> None:
        result = SweepResult(
            points=[SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0)],
            meta={"source": "display"},
        )
        save = SaveMeasurementUseCase(MatCsvMeasurementRepository())
        with tempfile.TemporaryDirectory() as td:
            artifacts = save_displayed_data(result, None, Path(td) / "displayed", save)
            self.assertTrue(artifacts.mat_path.is_file())
            self.assertTrue(artifacts.csv_path.is_file())
            self.assertTrue(artifacts.txt_path.is_file())

    def test_save_displayed_data_rolls_back_when_second_file_conflicts(self) -> None:
        result = SweepResult(
            points=[SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0)],
            meta={"source": "display"},
        )
        save = SaveMeasurementUseCase(MatCsvMeasurementRepository())
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            conflict = root / "displayed.csv"
            conflict.write_text("keep this file", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                save_displayed_data(result, None, root / "displayed", save)

            self.assertEqual(conflict.read_text(encoding="utf-8"), "keep this file")
            self.assertFalse((root / "displayed.mat").exists())
            self.assertFalse((root / "displayed.txt").exists())

    def test_save_displayed_data_does_not_follow_existing_symlink(self) -> None:
        result = SweepResult(
            points=[SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0)],
            meta={"source": "display"},
        )
        save = SaveMeasurementUseCase(MatCsvMeasurementRepository())
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sentinel = root / "sentinel.txt"
            sentinel.write_text("keep this file", encoding="utf-8")
            link = root / "displayed.csv"
            link.symlink_to(sentinel)
            with self.assertRaises(FileExistsError):
                save_displayed_data(result, None, root / "displayed", save)

            self.assertTrue(link.is_symlink())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep this file")
            self.assertFalse((root / "displayed.mat").exists())

    def test_save_displayed_data_rolls_back_destination_when_copy_fails(self) -> None:
        result = SweepResult(
            points=[SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0)],
            meta={"source": "display"},
        )
        save = SaveMeasurementUseCase(MatCsvMeasurementRepository())
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch(
                "app.application.services.measurement_workspace.shutil.copyfileobj",
                side_effect=OSError("copy failed"),
            ):
                with self.assertRaisesRegex(OSError, "copy failed"):
                    save_displayed_data(result, None, root / "displayed", save)

            self.assertEqual(list(root.iterdir()), [])

    def test_save_displayed_data_keeps_optional_plot_fields_aligned(self) -> None:
        result = SweepResult(
            points=[SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0)],
            meta={"source": "display"},
        )

        class DbOnlySave:
            def execute(self, *, result, settings, target) -> SaveArtifacts:
                del result, settings
                target.base_path.parent.mkdir(parents=True, exist_ok=True)
                mat = target.base_path.with_suffix(".mat")
                csv = target.base_path.with_suffix(".csv")
                txt = target.base_path.with_suffix(".txt")
                db = target.base_path.parent / f"{target.base_path.name}_gain_db.png"
                for path in (mat, csv, txt, db):
                    path.write_bytes(path.name.encode("ascii"))
                return SaveArtifacts(mat, csv, txt, None, db)

        with tempfile.TemporaryDirectory() as td:
            artifacts = save_displayed_data(result, None, Path(td) / "displayed", DbOnlySave())
            self.assertIsNone(artifacts.gain_plot_path)
            self.assertIsNotNone(artifacts.db_plot_path)
            self.assertEqual(artifacts.db_plot_path.name, "displayed_gain_db.png")


if __name__ == "__main__":
    unittest.main()
