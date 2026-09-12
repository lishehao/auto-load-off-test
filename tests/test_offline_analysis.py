from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import loadmat, savemat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.dto import LoadedMeasurement
from app.application.use_cases.analyze_measurement import AnalysisOptions, AnalyzeMeasurementUseCase
from app.domain.data_validation import DataValidationError
from app.domain.models import ReferenceCurve, SweepPoint, SweepResult
from app.infrastructure.persistence.measurement_loader import MeasurementLoader
from app.offline import run_offline_analysis


ROOT = Path(__file__).resolve().parents[1]


def measurement(freq=(100.0, 1000.0), phase=(30.0, 60.0)) -> LoadedMeasurement:
    points = [
        SweepPoint(float(f), 2.0, float(20 * np.log10(2)), p,
                   None if p is None else complex(2 * np.exp(1j * np.deg2rad(p))))
        for f, p in zip(freq, phase, strict=True)
    ]
    return LoadedMeasurement(SweepResult(points), {})


class OfflineAnalysisTests(unittest.TestCase):
    def test_analytic_complex_correction_and_input_immutability(self) -> None:
        loaded = measurement()
        reference = ReferenceCurve(np.array([100.0, 1000.0]), np.full(2, 20 * np.log10(2)), np.full(2, 10.0))
        analysis = AnalyzeMeasurementUseCase().execute(
            loaded, reference=reference, options=AnalysisOptions(correction="complex"),
        )
        np.testing.assert_allclose(analysis.measurement.gain_array(), [1.0, 1.0])
        np.testing.assert_allclose(analysis.measurement.phase_array(), [20.0, 50.0])
        np.testing.assert_allclose(loaded.result.gain_array(), [2.0, 2.0])
        self.assertNotIn("reference_correction", loaded.result.meta)

    def test_partial_phase_is_kept_missing_and_complex_mode_rejects_it(self) -> None:
        loaded = measurement(phase=(None, 60.0))
        reference = ReferenceCurve(np.array([100.0, 1000.0]), np.zeros(2), np.zeros(2))
        analysis = AnalyzeMeasurementUseCase().execute(
            loaded, reference=reference, options=AnalysisOptions(correction="magnitude"),
        )
        self.assertIsNone(analysis.measurement.points[0].phase_deg)
        self.assertTrue(any("incomplete" in warning for warning in analysis.warnings))
        with self.assertRaisesRegex(DataValidationError, "every input point"):
            AnalyzeMeasurementUseCase().execute(loaded, reference=reference, options=AnalysisOptions("complex"))

    def test_reference_requires_explicit_correction_and_phase(self) -> None:
        reference = ReferenceCurve(np.array([100.0, 1000.0]), np.zeros(2))
        for options, ref in ((AnalysisOptions(), reference), (AnalysisOptions("magnitude"), None)):
            with self.subTest(options=options):
                with self.assertRaisesRegex(DataValidationError, "supplied together"):
                    AnalyzeMeasurementUseCase().execute(measurement(), reference=ref, options=options)
        with self.assertRaisesRegex(DataValidationError, "reference phase"):
            AnalyzeMeasurementUseCase().execute(measurement(), reference=reference, options=AnalysisOptions("complex"))

    def test_reference_coverage_rejected_by_default_and_clamp_counted(self) -> None:
        reference = ReferenceCurve(np.array([200.0, 500.0]), np.zeros(2))
        with self.assertRaisesRegex(DataValidationError, "2 measurement points"):
            AnalyzeMeasurementUseCase().execute(measurement(), reference=reference, options=AnalysisOptions("magnitude"))
        analysis = AnalyzeMeasurementUseCase().execute(
            measurement(), reference=reference, options=AnalysisOptions("magnitude", "clamp"),
        )
        self.assertEqual(analysis.outside_reference_count, 2)
        self.assertTrue(any("edge-clamped" in warning for warning in analysis.warnings))

    def test_canonical_fixture_cannot_be_reference_corrected_twice(self) -> None:
        reference = ReferenceCurve(np.array([1e3, 1e6]), np.zeros(2), np.zeros(2))
        for extension in ("mat", "csv"):
            with self.subTest(extension=extension):
                loaded = MeasurementLoader().load(str(ROOT / f"demo_data/hyperframe_simulated_fixture.{extension}"))
                with self.assertRaisesRegex(DataValidationError, "already reference-corrected"):
                    AnalyzeMeasurementUseCase().execute(loaded, reference=reference, options=AnalysisOptions("complex"))
                analysis = AnalyzeMeasurementUseCase().execute(loaded)
                self.assertEqual(analysis.measurement.meta["reference_correction"], "fixture_corrected")

    def test_raw_selection_never_silently_uses_canonical(self) -> None:
        with self.assertRaisesRegex(DataValidationError, "explicit raw gain"):
            AnalyzeMeasurementUseCase().execute(measurement(), options=AnalysisOptions(dataset="raw"))

    def test_csv_fixture_passthrough_preserves_correction_guard_on_reload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "analysis"
            run_offline_analysis(ROOT / "demo_data/hyperframe_simulated_fixture.csv", output)
            for extension in ("mat", "csv"):
                loaded = MeasurementLoader().load(str(output / f"measurement.{extension}"))
                self.assertEqual(loaded.result.meta["reference_correction"], "fixture_corrected")
                with self.assertRaisesRegex(DataValidationError, "already reference-corrected"):
                    AnalyzeMeasurementUseCase().execute(
                        loaded, reference=ReferenceCurve(np.array([1e3, 1e6]), np.zeros(2)),
                        options=AnalysisOptions("magnitude"),
                    )

    def test_full_fixture_bundle_matches_expected_and_hashes_snapshot(self) -> None:
        fixture = ROOT / "demo_data/hyperframe_simulated_fixture.mat"
        reference = ROOT / "demo_data/hyperframe_reference_fixture.mat"
        expected = loadmat(fixture)
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "analysis"
            receipt = run_offline_analysis(fixture, output, reference_path=reference,
                                           options=AnalysisOptions("complex", "reject", "raw"))
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(receipt["point_count"], 72)
            self.assertFalse(manifest["live_hardware_used"])
            self.assertEqual(manifest["reference_correction"], "complex")
            self.assertEqual(manifest["options"]["dataset"], "raw")
            for item in manifest["inputs"] + manifest["artifacts"]:
                content = (output / item["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(content).hexdigest(), item["sha256"])
                self.assertEqual(len(content), item["bytes"])
            for extension in ("mat", "csv"):
                loaded = MeasurementLoader().load(str(output / f"measurement.{extension}"))
                np.testing.assert_allclose(loaded.result.gain_db_array(), expected["gain_db_corrected"].ravel(), atol=1e-8)
                delta = (loaded.result.phase_array() - expected["phase_deg_corrected"].ravel() + 180) % 360 - 180
                np.testing.assert_allclose(delta, np.zeros(72), atol=1e-8)
                self.assertEqual(loaded.result.meta["reference_correction"], "complex")
                self.assertEqual(loaded.result.meta["analysis_id"], manifest["analysis_id"])
                with self.assertRaisesRegex(DataValidationError, "already reference-corrected"):
                    AnalyzeMeasurementUseCase().execute(
                        loaded, reference=ReferenceCurve(np.array([1e3, 1e6]), np.zeros(2)),
                        options=AnalysisOptions("magnitude"),
                    )
            mat_metadata = json.loads(str(loadmat(output / "measurement.mat")["metadata_json"].ravel()[0]))
            self.assertNotIn("setup", mat_metadata)
            self.assertGreater((output / "bode.png").stat().st_size, 10000)
            self.assertIn("No hardware - simulated fixture", (output / "report.html").read_text())
            self.assertNotIn(str(ROOT), (output / "report.html").read_text())

    def test_existing_output_is_not_overwritten_even_when_empty(self) -> None:
        fixture = ROOT / "demo_data/hyperframe_simulated_fixture.mat"
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileExistsError):
                run_offline_analysis(fixture, Path(td))
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_failed_bundle_has_no_output_or_lock(self) -> None:
        fixture = ROOT / "demo_data/hyperframe_simulated_fixture.mat"
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "analysis"
            with patch("app.infrastructure.persistence.analysis_bundle._write_plot", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    run_offline_analysis(fixture, output)
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_csv_report_escapes_input_metadata_and_preserves_unknown_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "input.csv"
            source.write_text("freq_hz,gain_db,source\n100,0,<script>alert(1)</script>\n1000,6,<script>alert(1)</script>\n")
            output = Path(td) / "result"
            run_offline_analysis(source, output)
            html = (output / "report.html").read_text()
            self.assertNotIn("<script>", html)
            self.assertIn("&lt;script&gt;", html)
            self.assertIn("acquisition source unverified", html)
            self.assertEqual(json.loads((output / "manifest.json").read_text())["summary"]["phase_point_count"], 0)

    def test_source_snapshot_is_what_is_analyzed_even_if_original_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "input.csv"
            source.write_text("freq_hz,gain_db\n100,0\n1000,0\n")
            original = source.read_bytes()
            real_loader = MeasurementLoader.load

            def mutate_original(loader, snapshot):
                source.write_text("now corrupted")
                return real_loader(loader, snapshot)

            with patch.object(MeasurementLoader, "load", new=mutate_original):
                run_offline_analysis(source, Path(td) / "output")
            snapshot = Path(td) / "output/inputs/measurement.csv"
            self.assertEqual(snapshot.read_bytes(), original)

    def test_simulation_declaration_survives_without_source_field(self) -> None:
        for field in ("demo_label", "validation_boundary"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as td:
                source = Path(td) / "input.csv"
                source.write_text(f"freq_hz,gain_db,{field}\n100,0,No hardware - simulated fixture\n")
                output = Path(td) / "result"
                run_offline_analysis(source, output)
                manifest = json.loads((output / "manifest.json").read_text())
                self.assertTrue(manifest["simulated_input_declared"])
                self.assertEqual(manifest["input_provenance"][field], "No hardware - simulated fixture")
                self.assertIn("No hardware - simulated fixture", (output / "report.html").read_text())
                for extension in ("mat", "csv"):
                    loaded = MeasurementLoader().load(str(output / f"measurement.{extension}"))
                    self.assertIn("simulated fixture", loaded.result.meta["validation_boundary"])

    def test_cli_success_failure_and_import_boundary_in_real_subprocess(self) -> None:
        guard = (
            "import sys; import main; code=main.main(sys.argv[1:]); "
            "assert not any(m in sys.modules for m in ('tkinter','pyvisa','equips','app.bootstrap')); "
            "raise SystemExit(code)"
        )
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "input.csv"
            source.write_text("freq_hz,gain_db\n100,0\n1000,-3\n")
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            command = [sys.executable, "-c", guard, "analyze", str(source), "--output", str(Path(td) / "result")]
            passed = subprocess.run(command, cwd=td, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertEqual(json.loads(passed.stdout)["point_count"], 2)
            failed = subprocess.run(command, cwd=td, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(json.loads(failed.stderr)["error_type"], "FileExistsError")
            help_result = subprocess.run([sys.executable, str(ROOT / "src/main.py"), "--help"],
                                         cwd=td, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(help_result.returncode, 0)
            self.assertIn("analyze", help_result.stdout)

    def test_legacy_minimal_mat_without_acquisition_settings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "legacy.mat"
            savemat(source, {"freq": [10.0, 100.0], "gain_db": [0.0, -6.0]})
            run_offline_analysis(source, Path(td) / "result")
            manifest = json.loads((Path(td) / "result/manifest.json").read_text())
            self.assertEqual(manifest["input_source_claim"], "unknown")
            self.assertEqual(manifest["reference_correction"], "none")


if __name__ == "__main__":
    unittest.main()
