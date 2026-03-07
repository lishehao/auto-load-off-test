from __future__ import annotations

import math
import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.dto import StartSweepCommand
from app.application.services.sweep.calibration_applier import CalibrationApplier
from app.application.services.sweep.models import AcquiredPointData
from app.application.services.sweep.point_measurement_service import PointMeasurementService
from app.domain.enums import ConnectionMode, CorrectionMode, CouplingMode, ImpedanceMode, MagnitudePhaseMode, TriggerMode
from app.domain.models import (
    AppSettings,
    AwgSettings,
    ChannelSelection,
    InstrumentEndpoint,
    InstrumentSetup,
    OscSettings,
    RunMode,
    SweepPoint,
    SweepSpec,
)


def build_settings(*, correction_mode: CorrectionMode, trigger_mode: TriggerMode) -> AppSettings:
    return AppSettings(
        schema_version=1,
        freq_unit="Hz",
        sweep=SweepSpec(start_hz=1_000.0, stop_hz=1_000.0, step_hz=1_000.0, step_count=None, is_log=False),
        run_mode=RunMode(
            correction_mode=correction_mode,
            trigger_mode=trigger_mode,
            auto_range=False,
            auto_reset=True,
        ),
        setup=InstrumentSetup(
            awg=InstrumentEndpoint(model="DSG4102", connect_mode=ConnectionMode.AUTO),
            osc=InstrumentEndpoint(model="MDO34", connect_mode=ConnectionMode.AUTO),
            channels=ChannelSelection(awg_ch=1, osc_test_ch=1, osc_ref_ch=2, osc_trig_ch=2),
            awg_settings=AwgSettings(amplitude_vpp=1.0, impedance=ImpedanceMode.R50),
            osc_settings=OscSettings(
                full_scale_v=1.0,
                offset_v=0.0,
                points=4000,
                impedance=ImpedanceMode.R50,
                coupling=CouplingMode.DC,
            ),
        ),
        magnitude_phase_mode=MagnitudePhaseMode.MAG,
        auto_save_data=False,
    )


class PointMeasurementServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PointMeasurementService()
        self.calibration = CalibrationApplier()

    def test_single_channel_triggered_returns_phase(self) -> None:
        fs = 200_000
        f0 = 2_000
        t = np.arange(0.0, 0.03, 1.0 / fs)
        volts = 0.5 * np.sin(2.0 * np.pi * f0 * t)

        point = self.service.measure(
            settings=build_settings(correction_mode=CorrectionMode.NONE, trigger_mode=TriggerMode.TRIGGERED),
            acquired=AcquiredPointData(
                actual_freq_hz=f0,
                read_amp_vpp=1.0,
                test_times=t,
                test_volts=volts,
            ),
        )

        self.assertAlmostEqual(point.gain_linear, 1.0, delta=0.05)
        self.assertIsNotNone(point.phase_deg)
        self.assertIsNotNone(point.gain_complex)

    def test_dual_channel_measurement_returns_ratio(self) -> None:
        fs = 200_000
        f0 = 5_000
        t = np.arange(0.0, 0.03, 1.0 / fs)
        ref = np.sin(2.0 * np.pi * f0 * t)
        test = 2.0 * np.sin(2.0 * np.pi * f0 * t + math.radians(30.0))

        point = self.service.measure(
            settings=build_settings(correction_mode=CorrectionMode.DUAL, trigger_mode=TriggerMode.FREE_RUN),
            acquired=AcquiredPointData(
                actual_freq_hz=f0,
                read_amp_vpp=1.0,
                test_times=t,
                test_volts=test,
                ref_times=t,
                ref_volts=ref,
            ),
        )

        self.assertAlmostEqual(point.gain_linear, 2.0, delta=0.1)
        self.assertAlmostEqual(point.phase_deg or 0.0, 30.0, delta=5.0)

    def test_calibration_applier_corrects_gain_and_phase(self) -> None:
        point = SweepPoint(
            freq_hz=5_000.0,
            gain_linear=2.0,
            gain_db=20.0 * math.log10(2.0),
            phase_deg=30.0,
            gain_complex=2.0 * np.exp(1j * np.deg2rad(30.0)),
        )
        cmd = StartSweepCommand(
            settings=build_settings(correction_mode=CorrectionMode.DUAL, trigger_mode=TriggerMode.TRIGGERED),
            calibration_enabled=True,
            reference_interpolator=lambda _xs: np.array([2.0 * np.exp(1j * np.deg2rad(10.0))]),
        )

        corrected = self.calibration.apply(point=point, cmd=cmd)
        self.assertAlmostEqual(corrected.gain_linear, 1.0, delta=1e-6)
        self.assertAlmostEqual(corrected.phase_deg or 0.0, 20.0, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
