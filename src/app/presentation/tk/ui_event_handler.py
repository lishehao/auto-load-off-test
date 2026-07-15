from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.application.events import (
    ConnectionStatusUpdated,
    SweepCompleted,
    SweepDataUpdated,
    SweepFailed,
    SweepProgress,
    SweepStarted,
    SweepStopped,
    SweepWarning,
)
from app.domain.models import SweepResult

if TYPE_CHECKING:
    from app.presentation.tk.app_window import AppWindow
    from app.presentation.tk.view_model import ViewModel


class UiEventHandler:
    def __init__(self, *, window: AppWindow, vm: ViewModel) -> None:
        self._window = window
        self._vm = vm
        self._latest_result = SweepResult()
        self._started_at: float | None = None
        self._event_history: list[str] = []

    @property
    def latest_result(self) -> SweepResult:
        return self._latest_result

    def prepare_for_sweep_start(self) -> None:
        self._window.btn_start.configure(state="disabled")
        self._window.btn_stop.configure(state="normal")
        self._started_at = time.monotonic()
        self._vm.status_text.set("Sweep started")
        self._vm.run_state_text.set("Running")
        self._vm.elapsed_text.set("00:00")
        self._vm.latest_frequency_text.set("-")
        self._vm.export_receipt_text.set("No export yet")
        self.set_live_source()
        self.record_event("Sweep started")

    def set_result(self, result: SweepResult, *, refresh_plot: bool = True) -> None:
        self._latest_result = result
        self._vm.point_count_text.set(f"{len(result.points)} points")
        if refresh_plot:
            self.refresh_plot()

    def set_live_source(self) -> None:
        self._vm.source_mode.set("live")
        self._vm.data_source_text.set("Live instrument path")
        self._vm.fixture_badge_text.set("")
        self._vm.validation_receipt_text.set("Live run requires operator hardware checks")

    def set_fixture_source(self, *, label: str, path_name: str) -> None:
        point_count = len(self._latest_result.points)
        self._vm.source_mode.set("fixture")
        self._vm.figure_mode.set("gain_db")
        self._vm.magnitude_phase_mode.set("magnitude_phase")
        self._vm.plot_scale.set("log")
        self._vm.data_source_text.set(f"Fixture replay · {path_name}")
        self._vm.fixture_badge_text.set("No hardware - simulated fixture")
        self._vm.validation_receipt_text.set(f"{label}; not live hardware validation")
        self._vm.export_receipt_text.set("Fixture loaded; Save Data exports the current result")
        self._vm.run_state_text.set("Fixture ready")
        if point_count:
            self._vm.progress_text.set(f"{point_count} / {point_count}")
            self._vm.latest_frequency_text.set(_format_frequency(self._latest_result.points[-1].freq_hz))
            self._vm.elapsed_text.set("00:00")
        self._window.set_connection_idle()
        self._window.plot_widget.set_mode("gain_db")
        self.refresh_plot()
        self.record_event(f"Loaded simulated fixture: {path_name}")

    def set_loaded_source(self, *, path_name: str) -> None:
        self._vm.source_mode.set("loaded")
        self._vm.data_source_text.set(f"Loaded measurement · {path_name}")
        self._vm.fixture_badge_text.set("")
        self._vm.validation_receipt_text.set("Loaded file; live hardware state not implied")
        self._vm.export_receipt_text.set("Loaded measurement; Save Data exports the current result")
        self._vm.run_state_text.set("Data loaded")
        self._window.set_connection_idle()
        self.record_event(f"Loaded measurement: {path_name}")

    def set_reference_loaded(
        self,
        *,
        receipt_text: str,
        warnings: tuple[str, ...] = (),
        record: bool = True,
    ) -> None:
        self._vm.reference_receipt_text.set(receipt_text)
        if record:
            self.record_event("Reference receipt updated")
            for warning in warnings:
                self.record_event(warning, level="Warning")

    def set_export_saved(self, *, receipt_text: str) -> None:
        self._vm.export_receipt_text.set(receipt_text)
        self.record_event("Export artifacts saved")

    def record_event(self, message: str, *, level: str = "Info") -> None:
        line = f"{level}: {message}"
        self._event_history.append(line)
        self._event_history = self._event_history[-5:]
        self._vm.event_history_text.set("\n".join(self._event_history))

    def refresh_plot(self) -> None:
        self._window.plot_widget.update_result(
            self._latest_result,
            self._vm.freq_unit.get(),
            self._vm.magnitude_phase_mode.get(),
        )

    def handle(self, event: object) -> None:
        if isinstance(event, ConnectionStatusUpdated):
            self._window.set_connection_status(event.awg_connected, event.osc_connected)
            return

        if isinstance(event, SweepStarted):
            self._vm.status_text.set(f"Sweep started ({event.total_points} points)")
            self._vm.run_state_text.set("Running")
            self._vm.progress_text.set(f"0 / {event.total_points}")
            self._vm.point_count_text.set(f"0 / {event.total_points} points")
            return

        if isinstance(event, SweepProgress):
            self._vm.status_text.set(f"Freq {event.freq_hz:.2f} Hz ({event.point_index}/{event.total_points})")
            self._vm.progress_text.set(f"{event.point_index} / {event.total_points}")
            self._vm.latest_frequency_text.set(_format_frequency(event.freq_hz))
            self._vm.elapsed_text.set(_format_elapsed(self._started_at))
            return

        if isinstance(event, SweepDataUpdated):
            self.set_result(event.partial_result)
            return

        if isinstance(event, SweepWarning):
            self.record_event(event.message, level="Warning")
            if event.code in {"READY", "FREQ_MISMATCH", "AMP_MISMATCH"}:
                self._vm.status_text.set(event.message)
            else:
                _show_warning(self._window, event.message)
            return

        if isinstance(event, SweepFailed):
            self._vm.status_text.set(f"Sweep failed: {event.message}")
            self._vm.run_state_text.set("Failed")
            self._window.btn_start.configure(state="normal")
            self._window.btn_stop.configure(state="disabled")
            self.record_event(event.message, level="Error")
            _show_warning(self._window, event.message)
            return

        if isinstance(event, SweepStopped):
            self.set_result(event.result, refresh_plot=False)
            self._vm.status_text.set("Sweep stopped")
            self._vm.run_state_text.set("Stopped")
            self._vm.elapsed_text.set(_format_elapsed(self._started_at))
            self._window.btn_start.configure(state="normal")
            self._window.btn_stop.configure(state="disabled")
            self.record_event("Sweep stopped")
            return

        if isinstance(event, SweepCompleted):
            self.set_result(event.result)
            self._vm.status_text.set("Sweep completed")
            self._vm.run_state_text.set("Completed")
            self._vm.progress_text.set(f"{len(event.result.points)} / {len(event.result.points)}")
            self._vm.elapsed_text.set(_format_elapsed(self._started_at))
            self._window.btn_start.configure(state="normal")
            self._window.btn_stop.configure(state="disabled")
            self.record_event("Sweep completed")


def _format_elapsed(started_at: float | None) -> str:
    if started_at is None:
        return "00:00"
    seconds = max(0, int(time.monotonic() - started_at))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _format_frequency(freq_hz: float) -> str:
    if abs(freq_hz) >= 1_000_000:
        return f"{freq_hz / 1_000_000:.3g} MHz"
    if abs(freq_hz) >= 1_000:
        return f"{freq_hz / 1_000:.3g} kHz"
    return f"{freq_hz:.3g} Hz"


def _show_warning(window: object, message: str) -> None:
    from app.presentation.tk import dialogs

    dialogs.show_warning(window, message)
