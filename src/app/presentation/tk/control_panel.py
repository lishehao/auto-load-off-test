from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.presentation.tk.view_model import ViewModel
from app.shared.mapping import Mapping


class ControlPanel(tk.Frame):
    def __init__(self, parent: tk.Misc, vm: ViewModel) -> None:
        super().__init__(parent)
        self._vm = vm
        self._build()

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
        on_figure_change,
        on_mag_phase_change,
    ) -> None:
        self.btn_start.configure(command=on_start)
        self.btn_stop.configure(command=on_stop)
        self.btn_save_data.configure(command=on_save_data)
        self.btn_load_data.configure(command=on_load_data)
        self.btn_load_ref.configure(command=on_load_ref)
        self.btn_save_settings.configure(command=on_save_settings)
        self.btn_load_settings.configure(command=on_load_settings)

        self.cmb_figure.bind("<<ComboboxSelected>>", lambda _e: on_figure_change())
        self.cmb_mag_phase.bind("<<ComboboxSelected>>", lambda _e: on_mag_phase_change())

    def _build(self) -> None:
        row = 0

        def add_label(text: str, r: int, c: int = 0) -> None:
            tk.Label(self, text=text).grid(row=r, column=c, sticky="w", padx=3, pady=2)

        add_label("AWG model", row)
        ttk.Combobox(self, textvariable=self._vm.awg_model, values=Mapping.values_awg, width=12).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        add_label("OSC model", row)
        ttk.Combobox(self, textvariable=self._vm.osc_model, values=Mapping.values_osc, width=12).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        add_label("AWG conn", row)
        ttk.Combobox(self, textvariable=self._vm.awg_connect_mode, values=["auto", "lan"], width=12).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        add_label("AWG VISA", row)
        tk.Entry(self, textvariable=self._vm.awg_visa, width=28).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("AWG IP", row)
        tk.Entry(self, textvariable=self._vm.awg_ip, width=28).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("OSC conn", row)
        ttk.Combobox(self, textvariable=self._vm.osc_connect_mode, values=["auto", "lan"], width=12).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        add_label("OSC VISA", row)
        tk.Entry(self, textvariable=self._vm.osc_visa, width=28).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("OSC IP", row)
        tk.Entry(self, textvariable=self._vm.osc_ip, width=28).grid(row=row, column=1, sticky="ew")
        row += 1

        self._separator(row)
        row += 1

        add_label("Freq unit", row)
        ttk.Combobox(self, textvariable=self._vm.freq_unit, values=Mapping.values_freq_unit, width=8).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        for label, variable in (
            ("Start", self._vm.start_freq),
            ("Stop", self._vm.stop_freq),
            ("Step", self._vm.step_freq),
            ("Step count", self._vm.step_count),
        ):
            add_label(label, row)
            tk.Entry(self, textvariable=variable).grid(row=row, column=1, sticky="ew")
            row += 1

        tk.Checkbutton(self, text="Log sweep", variable=self._vm.is_log).grid(
            row=row, column=0, columnspan=2, sticky="w"
        )
        row += 1

        self._separator(row)
        row += 1

        for label, variable in (
            ("AWG amp (Vpp)", self._vm.awg_amp),
            ("OSC range", self._vm.osc_range),
            ("OSC offset", self._vm.osc_offset),
            ("OSC points", self._vm.osc_points),
        ):
            if label == "OSC range":
                add_label("AWG imp", row)
                ttk.Combobox(self, textvariable=self._vm.awg_imp, values=["50", "INF"], width=8).grid(
                    row=row, column=1, sticky="ew"
                )
                row += 1
            add_label(label, row)
            tk.Entry(self, textvariable=variable).grid(row=row, column=1, sticky="ew")
            row += 1

        add_label("OSC imp", row)
        ttk.Combobox(self, textvariable=self._vm.osc_imp, values=["50", "INF"], width=8).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        add_label("OSC coup", row)
        ttk.Combobox(self, textvariable=self._vm.osc_coupling, values=["DC", "AC"], width=8).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        self._separator(row)
        row += 1

        for label, variable in (
            ("AWG ch", self._vm.awg_ch),
            ("OSC test ch", self._vm.osc_test_ch),
            ("OSC ref ch", self._vm.osc_ref_ch),
            ("OSC trig ch", self._vm.osc_trig_ch),
        ):
            add_label(label, row)
            tk.Entry(self, textvariable=variable).grid(row=row, column=1, sticky="ew")
            row += 1

        add_label("Correction", row)
        ttk.Combobox(self, textvariable=self._vm.correction_mode, values=["none", "single", "dual"], width=10).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        add_label("Trigger", row)
        ttk.Combobox(self, textvariable=self._vm.trigger_mode, values=["free_run", "triggered"], width=10).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        for label, variable in (
            ("Auto range", self._vm.auto_range),
            ("Auto reset", self._vm.auto_reset),
            ("Enable calibration", self._vm.calibration_enabled),
            ("Auto save data", self._vm.auto_save_data),
        ):
            tk.Checkbutton(self, text=label, variable=variable).grid(row=row, column=0, columnspan=2, sticky="w")
            row += 1

        add_label("Figure", row)
        self.cmb_figure = ttk.Combobox(self, textvariable=self._vm.figure_mode, values=["gain", "gain_db"], width=10)
        self.cmb_figure.grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("Display", row)
        self.cmb_mag_phase = ttk.Combobox(
            self,
            textvariable=self._vm.magnitude_phase_mode,
            values=["magnitude", "phase", "magnitude_phase"],
            width=14,
        )
        self.cmb_mag_phase.grid(row=row, column=1, sticky="ew")
        row += 1

        row = self._build_primary_buttons(row)
        self._build_secondary_buttons(row)
        self.grid_columnconfigure(1, weight=1)

    def _separator(self, row: int) -> None:
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)

    def _build_primary_buttons(self, row: int) -> int:
        buttons = tk.Frame(self)
        buttons.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)

        self.btn_start = tk.Button(buttons, text="Start", width=9)
        self.btn_start.pack(side=tk.LEFT, padx=2)
        self.btn_stop = tk.Button(buttons, text="Stop", width=9, state="disabled")
        self.btn_stop.pack(side=tk.LEFT, padx=2)

        self.btn_save_data = tk.Button(buttons, text="Save Data", width=9)
        self.btn_save_data.pack(side=tk.LEFT, padx=2)
        self.btn_load_data = tk.Button(buttons, text="Load Data", width=9)
        self.btn_load_data.pack(side=tk.LEFT, padx=2)
        return row + 1

    def _build_secondary_buttons(self, row: int) -> None:
        buttons = tk.Frame(self)
        buttons.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)

        self.btn_load_ref = tk.Button(buttons, text="Load Ref", width=9)
        self.btn_load_ref.pack(side=tk.LEFT, padx=2)
        self.btn_save_settings = tk.Button(buttons, text="Save Settings", width=11)
        self.btn_save_settings.pack(side=tk.LEFT, padx=2)
        self.btn_load_settings = tk.Button(buttons, text="Load Settings", width=11)
        self.btn_load_settings.pack(side=tk.LEFT, padx=2)

