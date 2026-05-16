from __future__ import annotations

import sys
from pathlib import Path
import threading
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.events import SweepCompleted, SweepWarning
from app.domain.models import SweepPoint, SweepResult
from app.infrastructure.persistence.settings_defaults import DefaultSettingsFactory
from app.application.services.sweep_task_runner import SweepTaskRunner


class FakeSaveMeasurementUseCase:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object, object]] = []

    def execute(self, result, settings, target):
        self.calls.append((result, settings, target))
        return SimpleNamespace(mat_path=Path("measurement.mat"))


class FakeEmitter:
    def __init__(self) -> None:
        self.events: list[object] = []

    def emit(self, event: object) -> None:
        self.events.append(event)


class FakePort:
    def __init__(self) -> None:
        self.closed = False
        self.output_off_channels: list[int] = []
        self.fail_close = False

    def output_off(self, channel: int) -> None:
        self.output_off_channels.append(channel)

    def close(self) -> None:
        if self.fail_close:
            raise RuntimeError("close failed")
        self.closed = True


class FakeStartUseCase:
    def __init__(self, result: SweepResult) -> None:
        self._result = result

    def run(self, cmd, emitter):
        emitter.emit(SweepCompleted(result=self._result))
        return self._result


class SweepTaskRunnerTests(unittest.TestCase):
    def test_runner_auto_saves_completed_result(self) -> None:
        settings = DefaultSettingsFactory().create()
        settings.auto_save_data = True
        save_use_case = FakeSaveMeasurementUseCase()
        emitter = FakeEmitter()
        awg = FakePort()
        osc = FakePort()
        result = SweepResult(points=[SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0)])

        def ports_factory(_setup):
            return SimpleNamespace(awg=awg, osc=osc, awg_address="A", osc_address="B")

        def use_case_factory(*, awg, osc, stop_event: threading.Event):
            _ = (awg, osc, stop_event)
            return FakeStartUseCase(result)

        runner = SweepTaskRunner(
            emitter=emitter,
            save_measurement_use_case=save_use_case,
            auto_save_dir=Path("."),
            ports_factory=ports_factory,
            use_case_factory=use_case_factory,
        )

        runner.start(settings=settings, calibration_enabled=False, reference_interpolator=None)
        runner.wait(timeout=1.0)

        self.assertEqual(len(save_use_case.calls), 1)
        self.assertEqual(awg.output_off_channels, [settings.setup.channels.awg_ch])
        self.assertTrue(awg.closed)
        self.assertTrue(osc.closed)
        self.assertTrue(any(isinstance(event, SweepCompleted) for event in emitter.events))

    def test_runner_emits_warning_when_port_close_fails(self) -> None:
        settings = DefaultSettingsFactory().create()
        save_use_case = FakeSaveMeasurementUseCase()
        emitter = FakeEmitter()
        awg = FakePort()
        osc = FakePort()
        awg.fail_close = True
        result = SweepResult(points=[SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0)])

        def ports_factory(_setup):
            return SimpleNamespace(awg=awg, osc=osc, awg_address="A", osc_address="B")

        def use_case_factory(*, awg, osc, stop_event: threading.Event):
            _ = (awg, osc, stop_event)
            return FakeStartUseCase(result)

        runner = SweepTaskRunner(
            emitter=emitter,
            save_measurement_use_case=save_use_case,
            auto_save_dir=Path("."),
            ports_factory=ports_factory,
            use_case_factory=use_case_factory,
        )

        runner.start(settings=settings, calibration_enabled=False, reference_interpolator=None)
        runner.wait(timeout=1.0)

        warnings = [event for event in emitter.events if isinstance(event, SweepWarning)]
        self.assertTrue(any(event.code == "AWG_CLOSE_FAILED" for event in warnings))


if __name__ == "__main__":
    unittest.main()
