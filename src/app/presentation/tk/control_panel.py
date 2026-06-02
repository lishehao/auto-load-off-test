from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.presentation.tk.view_model import ViewModel
from app.shared.mapping import Mapping


PANEL_BG = "#f4f6f8"
CARD_BG = "#ffffff"
TEXT = "#1f2937"
MUTED = "#64748b"
GREEN = "#15803d"
AMBER = "#b45309"
RED = "#b91c1c"


class ControlPanel(tk.Frame):
    def __init__(self, parent: tk.Misc, vm: ViewModel) -> None:
        super().__init__(parent, bg=PANEL_BG)
        self._vm = vm
        self._trace_ids: list[tuple[tk.StringVar, str]] = []
        self._build()

    def bind_actions(
        self,
        *,
        on_save_settings,
        on_load_settings,
    ) -> None:
        self.btn_save_settings.configure(command=on_save_settings)
        self.btn_load_settings.configure(command=on_load_settings)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        tk.Label(
            self,
            text="Setup",
            bg=PANEL_BG,
            fg=TEXT,
            font=("TkDefaultFont", 14, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self._build_instruments(1)
        self._build_sweep(2)
        self._build_channels(3)
        self._build_settings_actions(4)

    def _section(self, title: str, row: int) -> ttk.LabelFrame:
        section = ttk.LabelFrame(self, text=title, padding=(8, 6))
        section.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        section.grid_columnconfigure(1, weight=1)
        return section

    def _build_instruments(self, row: int) -> None:
        section = self._section("Instruments", row)
        self._combo(section, "AWG model", self._vm.awg_model, Mapping.values_awg, 0)
        self._combo(section, "OSC model", self._vm.osc_model, Mapping.values_osc, 1)
        self._combo(section, "AWG conn", self._vm.awg_connect_mode, ["auto", "lan"], 2, width=10)
        self._entry(section, "AWG VISA", self._vm.awg_visa, 3)
        self._entry(section, "AWG IP", self._vm.awg_ip, 4)
        self._combo(section, "OSC conn", self._vm.osc_connect_mode, ["auto", "lan"], 5, width=10)
        self._entry(section, "OSC VISA", self._vm.osc_visa, 6)
        self._entry(section, "OSC IP", self._vm.osc_ip, 7)

        chips = ttk.Frame(section)
        chips.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        chips.grid_columnconfigure((0, 1), weight=1)
        self.awg_connection_chip = self._status_chip(chips, self._vm.awg_connection_text, 0)
        self.osc_connection_chip = self._status_chip(chips, self._vm.osc_connection_text, 1)

    def _build_sweep(self, row: int) -> None:
        section = self._section("Sweep", row)
        self._combo(section, "Unit", self._vm.freq_unit, Mapping.values_freq_unit, 0, width=10)
        self._entry(section, "Start", self._vm.start_freq, 1, width=12)
        self._entry(section, "Stop", self._vm.stop_freq, 2, width=12)
        self._entry(section, "Step", self._vm.step_freq, 3, width=12)
        self._entry(section, "Points", self._vm.step_count, 4, width=12)
        ttk.Checkbutton(section, text="Log sweep", variable=self._vm.is_log).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(3, 4)
        )
        self._entry(section, "AWG Vpp", self._vm.awg_amp, 6, width=12)
        self._combo(section, "AWG imp", self._vm.awg_imp, ["50", "INF"], 7, width=10)
        self._entry(section, "OSC range", self._vm.osc_range, 8, width=12)
        self._entry(section, "OSC offset", self._vm.osc_offset, 9, width=12)
        self._entry(section, "OSC points", self._vm.osc_points, 10, width=12)
        self._combo(section, "OSC imp", self._vm.osc_imp, ["50", "INF"], 11, width=10)
        self._combo(section, "Coupling", self._vm.osc_coupling, ["DC", "AC"], 12, width=10)

    def _build_channels(self, row: int) -> None:
        section = self._section("Channels / Correction", row)
        self._entry(section, "AWG ch", self._vm.awg_ch, 0, width=8)
        self._entry(section, "Test ch", self._vm.osc_test_ch, 1, width=8)
        self._entry(section, "Ref ch", self._vm.osc_ref_ch, 2, width=8)
        self._entry(section, "Trig ch", self._vm.osc_trig_ch, 3, width=8)
        self._combo(section, "Correction", self._vm.correction_mode, ["none", "single", "dual"], 4)
        self._combo(section, "Trigger", self._vm.trigger_mode, ["free_run", "triggered"], 5)

        toggles = ttk.Frame(section)
        toggles.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        for idx, (label, variable) in enumerate(
            (
                ("Auto range", self._vm.auto_range),
                ("Auto reset", self._vm.auto_reset),
                ("Calibration", self._vm.calibration_enabled),
                ("Auto save", self._vm.auto_save_data),
            )
        ):
            ttk.Checkbutton(toggles, text=label, variable=variable).grid(
                row=idx // 2,
                column=idx % 2,
                sticky="w",
                padx=(0, 10),
                pady=1,
            )

    def _build_settings_actions(self, row: int) -> None:
        actions = ttk.Frame(self)
        actions.grid(row=row, column=0, sticky="ew")
        actions.grid_columnconfigure((0, 1), weight=1)
        self.btn_save_settings = ttk.Button(actions, text="Save Settings")
        self.btn_save_settings.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_load_settings = ttk.Button(actions, text="Load Settings")
        self.btn_load_settings.grid(row=0, column=1, sticky="ew")

    def _combo(
        self,
        parent: tk.Misc,
        label: str,
        variable: tk.StringVar,
        values: list[str] | tuple[str, ...],
        row: int,
        *,
        width: int = 16,
        label_col: int = 0,
    ) -> ttk.Combobox:
        self._label(parent, label, row, label_col=label_col)
        combo = ttk.Combobox(parent, textvariable=variable, values=values, width=width, state="readonly")
        combo.grid(row=row, column=label_col + 1, sticky="ew", pady=1)
        return combo

    def _entry(
        self,
        parent: tk.Misc,
        label: str,
        variable: tk.StringVar,
        row: int,
        *,
        width: int = 18,
        label_col: int = 0,
    ) -> ttk.Entry:
        self._label(parent, label, row, label_col=label_col)
        entry = ttk.Entry(parent, textvariable=variable, width=width)
        entry.grid(row=row, column=label_col + 1, sticky="ew", pady=1)
        return entry

    def _label(self, parent: tk.Misc, text: str, row: int, *, label_col: int = 0) -> None:
        tk.Label(parent, text=text, bg=CARD_BG, fg=MUTED, anchor="w").grid(
            row=row,
            column=label_col,
            sticky="w",
            padx=(0 if label_col == 0 else 10, 5),
            pady=1,
        )

    def _status_chip(self, parent: tk.Misc, variable: tk.StringVar, column: int) -> tk.Label:
        label = tk.Label(
            parent,
            textvariable=variable,
            bg="#fef2f2",
            fg=RED,
            anchor="center",
            padx=6,
            pady=3,
        )
        label.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))

        def sync_chip(*_args) -> None:
            bg, fg = _connection_chip_colors(variable.get())
            label.configure(bg=bg, fg=fg)

        trace_id = variable.trace_add("write", sync_chip)
        self._trace_ids.append((variable, trace_id))
        sync_chip()
        return label


def _connection_chip_colors(text: str) -> tuple[str, str]:
    normalized = text.lower()
    if "online" in normalized or "connected" in normalized:
        return "#ecfdf5", GREEN
    if "checking" in normalized or "connecting" in normalized or "scan" in normalized:
        return "#fff7ed", AMBER
    return "#fef2f2", RED
