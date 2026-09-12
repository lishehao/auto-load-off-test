from __future__ import annotations

import sys
from pathlib import Path
import threading
import unittest
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.dto import StartSweepCommand
from app.application.events import (
    SweepCompleted,
    SweepDataUpdated,
    SweepFailed,
    SweepProgress,
    SweepStarted,
    SweepStopped,
)
from app.application.use_cases.start_sweep import StartSweepUseCase
from app.domain.data_validation import validate_sweep_result
from app.domain.enums import (
    ConnectionMode,
    CorrectionMode,
    CouplingMode,
    ImpedanceMode,
    MagnitudePhaseMode,
    TriggerMode,
)
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


class MockAwg:
    def __init__(self) -> None:
        self.freq = 1_000.0
        self.amp = 1.0
        self.calls: list[tuple] = []

    def reset(self) -> None:
        self.calls.append(("reset",))

    def output_on(self, channel: int) -> None:
        self.calls.append(("output_on", channel))

    def output_off(self, channel: int) -> None:
        self.calls.append(("output_off", channel))

    def set_impedance(self, mode: str, channel: int) -> None:
        self.calls.append(("set_impedance", mode, channel))

    def set_frequency(self, hz: float, channel: int) -> None:
        self.calls.append(("set_frequency", hz, channel))
        self.freq = hz

    def get_frequency(self, channel: int) -> float:
        self.calls.append(("get_frequency", channel))
        return self.freq

    def set_amplitude_vpp(self, vpp: float, channel: int) -> None:
        self.calls.append(("set_amplitude_vpp", vpp, channel))
        self.amp = vpp

    def get_amplitude_vpp(self, channel: int) -> float:
        self.calls.append(("get_amplitude_vpp", channel))
        return self.amp

    def close(self) -> None:
        return None


class MockOsc:
    def __init__(self, awg: MockAwg) -> None:
        self._awg = awg
        self._range = 1.0
        self._offset = 0.0

    def reset(self) -> None:
        return None

    def output_on(self, channel: int) -> None:
        _ = channel

    def set_timebase(self, window_s: float, offset_s: float | None = None) -> None:
        _ = (window_s, offset_s)

    def set_vertical(self, channel: int, full_scale_v: float, offset_v: float) -> None:
        _ = channel
        self._range = full_scale_v
        self._offset = offset_v

    def get_vertical(self, channel: int) -> tuple[float, float]:
        _ = channel
        return self._range, self._offset

    def set_coupling(self, channel: int, mode: str) -> None:
        _ = (channel, mode)

    def set_impedance(self, channel: int, mode: str) -> None:
        _ = (channel, mode)

    def arm_trigger(self, channel: int, level_v: float) -> None:
        _ = (channel, level_v)

    def set_free_run(self) -> None:
        return None

    def single_acquire(self, triggered: bool) -> None:
        _ = triggered

    def read_waveform(self, channel: int, points: int | None) -> tuple[np.ndarray, np.ndarray]:
        _ = channel
        n = points or 5000
        sr = 200_000
        t = np.arange(0.0, n / sr, 1.0 / sr)
        volts = 0.5 * np.sin(2.0 * np.pi * self._awg.freq * t)
        return t, volts

    def get_sample_rate(self) -> float:
        return 200_000.0

    def close(self) -> None:
        return None


class Recorder:
    def __init__(self) -> None:
        self.events: list[object] = []

    def emit(self, event: object) -> None:
        self.events.append(event)


class StartSweepUseCaseTests(unittest.TestCase):
    def test_invalid_or_nonincreasing_point_preserves_exportable_partial_result(self):
        for bad_point in (SweepPoint(2000.0, float("nan"), float("nan")),
                          SweepPoint(1000.0, 1.0, 0.0), SweepPoint(900.0, 1.0, 0.0)):
            with self.subTest(point=bad_point):
                awg = MockAwg()
                points = iter([SweepPoint(1000.0, 1.0, 0.0), bad_point])
                measurement = SimpleNamespace(measure=lambda **_: next(points))
                use_case = StartSweepUseCase(awg=awg, osc=MockOsc(awg), stop_event=threading.Event(),
                                             measurement_service=measurement)
                recorder = Recorder()
                result = use_case.run(StartSweepCommand(settings=self._build_settings()), recorder)
                self.assertEqual(len(result.points), 1)
                self.assertEqual(result.meta["run_status"], "failed")
                self.assertEqual(result.meta["error_stage"], "point_validation")
                self.assertTrue(any(isinstance(e, SweepFailed) for e in recorder.events))
                self.assertFalse(any(isinstance(e, SweepCompleted) for e in recorder.events))
                validate_sweep_result(result)

    def _build_settings(self) -> AppSettings:
        return AppSettings(
            schema_version=1,
            freq_unit="Hz",
            sweep=SweepSpec(start_hz=1000.0, stop_hz=3000.0, step_hz=1000.0, step_count=None, is_log=False),
            run_mode=RunMode(
                correction_mode=CorrectionMode.NONE,
                trigger_mode=TriggerMode.FREE_RUN,
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

    def test_run_emits_started_progress_completed(self) -> None:
        awg = MockAwg()
        osc = MockOsc(awg)
        stop_event = threading.Event()

        use_case = StartSweepUseCase(awg=awg, osc=osc, stop_event=stop_event)
        recorder = Recorder()

        result = use_case.run(StartSweepCommand(settings=self._build_settings()), recorder)

        self.assertFalse(result.is_empty)
        self.assertTrue(any(isinstance(e, SweepStarted) for e in recorder.events))
        self.assertTrue(any(isinstance(e, SweepCompleted) for e in recorder.events))

        progress_count = sum(1 for e in recorder.events if isinstance(e, SweepProgress))
        self.assertEqual(progress_count, 3)

    def test_run_can_be_stopped(self) -> None:
        awg = MockAwg()
        osc = MockOsc(awg)
        stop_event = threading.Event()
        stop_event.set()

        use_case = StartSweepUseCase(awg=awg, osc=osc, stop_event=stop_event)
        recorder = Recorder()

        result = use_case.run(StartSweepCommand(settings=self._build_settings()), recorder)

        self.assertTrue(any(isinstance(e, SweepStopped) for e in recorder.events))
        self.assertTrue(result.is_empty or len(result.points) >= 0)

    def test_awg_output_waits_for_amplitude_and_frequency(self) -> None:
        awg = MockAwg()
        osc = MockOsc(awg)
        stop_event = threading.Event()

        use_case = StartSweepUseCase(awg=awg, osc=osc, stop_event=stop_event)
        recorder = Recorder()

        use_case.run(StartSweepCommand(settings=self._build_settings()), recorder)

        first_output_on = awg.calls.index(("output_on", 1))
        first_set_amp = awg.calls.index(("set_amplitude_vpp", 1.0, 1))
        first_set_freq = awg.calls.index(("set_frequency", 1000.0, 1))
        self.assertLess(first_set_amp, first_output_on)
        self.assertLess(first_set_freq, first_output_on)

    def test_validation_failure_emits_failed_event(self) -> None:
        settings = self._build_settings()
        settings.setup.osc_settings.coupling = CouplingMode.AC
        awg = MockAwg()
        osc = MockOsc(awg)
        use_case = StartSweepUseCase(awg=awg, osc=osc, stop_event=threading.Event())
        recorder = Recorder()

        result = use_case.run(StartSweepCommand(settings=settings), recorder)

        failures = [event for event in recorder.events if isinstance(event, SweepFailed)]
        self.assertTrue(result.is_empty)
        self.assertEqual(failures[0].error_code, "VALIDATION")
        self.assertIn("ValidationError", failures[0].message)

    def test_runtime_failure_emits_exception_type(self) -> None:
        class FailingConfigurator:
            def configure(self, settings):
                _ = settings
                raise RuntimeError("configure failed")

        awg = MockAwg()
        osc = MockOsc(awg)
        use_case = StartSweepUseCase(
            awg=awg,
            osc=osc,
            stop_event=threading.Event(),
            configurator=FailingConfigurator(),
        )
        recorder = Recorder()

        result = use_case.run(StartSweepCommand(settings=self._build_settings()), recorder)

        failures = [event for event in recorder.events if isinstance(event, SweepFailed)]
        self.assertTrue(result.is_empty)
        self.assertEqual(failures[0].error_code, "SWEEP_RUNTIME")
        self.assertIn("RuntimeError", failures[0].message)

    def test_second_point_failure_preserves_first_point_and_failure_metadata(self) -> None:
        class Planner:
            def plan(self, settings):
                _ = settings
                return SimpleNamespace(freq_points=[1000.0, 2000.0, 3000.0], total_points=3)

        class Acquirer:
            def __init__(self):
                self.calls = 0

            def acquire(self, *, target_freq_hz, settings):
                _ = (target_freq_hz, settings)
                self.calls += 1
                if self.calls == 2:
                    raise TimeoutError("second point timeout")
                return SimpleNamespace(warnings=[])

        class Measurement:
            def measure(self, *, settings, acquired):
                _ = (settings, acquired)
                return SweepPoint(freq_hz=1000.0, gain_linear=1.0, gain_db=0.0)

        class Calibration:
            def apply(self, *, point, cmd):
                _ = cmd
                return point

        class Configurator:
            def configure(self, settings):
                _ = settings

        recorder = Recorder()
        result = StartSweepUseCase(
            awg=MockAwg(),
            osc=MockOsc(MockAwg()),
            stop_event=threading.Event(),
            planner=Planner(),
            configurator=Configurator(),
            acquirer=Acquirer(),
            measurement_service=Measurement(),
            calibration_applier=Calibration(),
        ).run(StartSweepCommand(settings=self._build_settings()), recorder)

        self.assertEqual(len(result.points), 1)
        self.assertEqual(result.meta["run_status"], "failed")
        self.assertEqual(result.meta["completed_points"], 1)
        self.assertEqual(result.meta["error_stage"], "acquire")
        self.assertEqual(result.meta["error_point_index"], 2)
        failure = next(event for event in recorder.events if isinstance(event, SweepFailed))
        self.assertIsNotNone(failure.result)
        self.assertEqual(len(failure.result.points), 1)

    def test_published_partial_results_are_independent_snapshots(self) -> None:
        recorder = Recorder()
        result = StartSweepUseCase(awg=MockAwg(), osc=MockOsc(MockAwg()), stop_event=threading.Event()).run(
            StartSweepCommand(settings=self._build_settings()), recorder
        )

        updates = [event for event in recorder.events if isinstance(event, SweepDataUpdated)]
        self.assertEqual([len(event.partial_result.points) for event in updates], [1, 2, 3])
        self.assertEqual([event.partial_result.meta["completed_points"] for event in updates], [1, 2, 3])
        result.meta["completed_points"] = 99
        self.assertEqual(updates[-1].partial_result.meta["completed_points"], 3)

    def test_stop_after_point_published_retains_that_point(self) -> None:
        stop_event = threading.Event()

        class StopAfterData(Recorder):
            def emit(self, event):
                super().emit(event)
                if isinstance(event, SweepDataUpdated):
                    stop_event.set()

        recorder = StopAfterData()
        result = StartSweepUseCase(awg=MockAwg(), osc=MockOsc(MockAwg()), stop_event=stop_event).run(
            StartSweepCommand(settings=self._build_settings()), recorder
        )

        self.assertEqual(len(result.points), 1)
        self.assertEqual(result.meta["run_status"], "stopped")
        self.assertEqual(result.meta["completed_points"], 1)
        stopped = next(event for event in recorder.events if isinstance(event, SweepStopped))
        self.assertEqual(len(stopped.result.points), 1)

    def test_stop_before_configuration_does_not_configure(self) -> None:
        stop_event = threading.Event()
        stop_event.set()
        configured = []

        class Configurator:
            def configure(self, settings):
                configured.append(settings)

        recorder = Recorder()
        result = StartSweepUseCase(
            awg=MockAwg(),
            osc=MockOsc(MockAwg()),
            stop_event=stop_event,
            configurator=Configurator(),
        ).run(StartSweepCommand(settings=self._build_settings()), recorder)

        self.assertEqual(configured, [])
        self.assertEqual(result.meta["run_status"], "stopped")


if __name__ == "__main__":
    unittest.main()
