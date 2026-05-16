from __future__ import annotations

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
from app.presentation.tk import dialogs
from app.presentation.tk.app_window import AppWindow
from app.presentation.tk.view_model import ViewModel


class UiEventHandler:
    def __init__(self, *, window: AppWindow, vm: ViewModel) -> None:
        self._window = window
        self._vm = vm
        self._latest_result = SweepResult()

    @property
    def latest_result(self) -> SweepResult:
        return self._latest_result

    def prepare_for_sweep_start(self) -> None:
        self._window.btn_start.configure(state="disabled")
        self._window.btn_stop.configure(state="normal")
        self._vm.status_text.set("Sweep started")

    def set_result(self, result: SweepResult, *, refresh_plot: bool = True) -> None:
        self._latest_result = result
        if refresh_plot:
            self.refresh_plot()

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
            return

        if isinstance(event, SweepProgress):
            self._vm.status_text.set(f"Freq {event.freq_hz:.2f} Hz ({event.point_index}/{event.total_points})")
            return

        if isinstance(event, SweepDataUpdated):
            self.set_result(event.partial_result)
            return

        if isinstance(event, SweepWarning):
            if event.code in {"READY", "FREQ_MISMATCH", "AMP_MISMATCH"}:
                self._vm.status_text.set(event.message)
            else:
                dialogs.show_warning(self._window, event.message)
            return

        if isinstance(event, SweepFailed):
            self._vm.status_text.set(f"Sweep failed: {event.message}")
            self._window.btn_start.configure(state="normal")
            self._window.btn_stop.configure(state="disabled")
            dialogs.show_warning(self._window, event.message)
            return

        if isinstance(event, SweepStopped):
            self.set_result(event.result, refresh_plot=False)
            self._vm.status_text.set("Sweep stopped")
            self._window.btn_start.configure(state="normal")
            self._window.btn_stop.configure(state="disabled")
            return

        if isinstance(event, SweepCompleted):
            self.set_result(event.result)
            self._vm.status_text.set("Sweep completed")
            self._window.btn_start.configure(state="normal")
            self._window.btn_stop.configure(state="disabled")
