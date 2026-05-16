from __future__ import annotations

import tkinter as tk

from app.presentation.tk.control_panel import ControlPanel
from app.presentation.tk.plot_widget import PlotWidget
from app.presentation.tk.view_model import ViewModel


class AppWindow(tk.Tk):
    def __init__(self, vm: ViewModel | None = None) -> None:
        super().__init__()
        self.vm = vm or ViewModel(self)
        self.title("LoadoffTest - Decoupled")
        self.geometry("1400x900")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._on_close = None

        container = tk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(container)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)

        right = tk.Frame(container)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.control_panel = ControlPanel(left, self.vm)
        self.control_panel.pack(fill=tk.Y)
        self._alias_control_widgets()

        self.plot_widget = PlotWidget(right)
        self.plot_widget.frame.pack(fill=tk.BOTH, expand=True)

        status_bar = tk.Frame(self)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.lb_status = tk.Label(status_bar, textvariable=self.vm.status_text, anchor="w")
        self.lb_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.canvas_awg = tk.Canvas(status_bar, width=14, height=14)
        self.canvas_awg.pack(side=tk.RIGHT, padx=6)
        self.awg_light = self.canvas_awg.create_oval(2, 2, 12, 12, fill="red")
        tk.Label(status_bar, text="AWG").pack(side=tk.RIGHT)

        self.canvas_osc = tk.Canvas(status_bar, width=14, height=14)
        self.canvas_osc.pack(side=tk.RIGHT, padx=6)
        self.osc_light = self.canvas_osc.create_oval(2, 2, 12, 12, fill="red")
        tk.Label(status_bar, text="OSC").pack(side=tk.RIGHT)

    def bind_actions(
        self,
        *,
        on_start,
        on_stop,
        on_save_data,
        on_load_data,
        on_load_ref,
        on_save_settings,
        on_load_settings,
        on_close,
        on_figure_change,
        on_mag_phase_change,
    ) -> None:
        self.control_panel.bind_actions(
            on_start=on_start,
            on_stop=on_stop,
            on_save_data=on_save_data,
            on_load_data=on_load_data,
            on_load_ref=on_load_ref,
            on_save_settings=on_save_settings,
            on_load_settings=on_load_settings,
            on_figure_change=on_figure_change,
            on_mag_phase_change=on_mag_phase_change,
        )
        self._on_close = on_close

    def set_connection_status(self, awg_connected: bool, osc_connected: bool) -> None:
        self.canvas_awg.itemconfig(self.awg_light, fill="green" if awg_connected else "red")
        self.canvas_osc.itemconfig(self.osc_light, fill="green" if osc_connected else "red")

    def on_close(self) -> None:
        if self._on_close is not None:
            self._on_close()
        else:
            self.destroy()

    def _alias_control_widgets(self) -> None:
        self.btn_start = self.control_panel.btn_start
        self.btn_stop = self.control_panel.btn_stop
        self.btn_save_data = self.control_panel.btn_save_data
        self.btn_load_data = self.control_panel.btn_load_data
        self.btn_load_ref = self.control_panel.btn_load_ref
        self.btn_save_settings = self.control_panel.btn_save_settings
        self.btn_load_settings = self.control_panel.btn_load_settings
        self.cmb_figure = self.control_panel.cmb_figure
        self.cmb_mag_phase = self.control_panel.cmb_mag_phase
