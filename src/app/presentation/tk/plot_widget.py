from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from app.domain.plotting import choose_frequency_scale
from app.domain.models import SweepResult
from app.presentation.tk.view_model import ViewModel
from app.shared.cvt_tools import CvtTools
from app.shared.mapping import Mapping


PANEL_BG = "#f4f6f8"
CARD_BG = "#ffffff"
TEXT = "#1f2937"
MUTED = "#64748b"
BLUE = "#1d4ed8"
PHASE = Mapping.mapping_color_for_phase_line


class PlotWidget:
    def __init__(self, parent: tk.Misc, vm: ViewModel) -> None:
        self._vm = vm
        self._reference_coverage_hz: tuple[float, float] | None = None
        self._reference_spans: list[object] = []
        self.frame = tk.Frame(parent, bg=PANEL_BG)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_plots()

    def bind_controls(self, *, on_figure_change, on_mag_phase_change, on_plot_scale_change) -> None:
        self.cmb_figure.bind("<<ComboboxSelected>>", lambda _e: on_figure_change())
        self.cmb_mag_phase.bind("<<ComboboxSelected>>", lambda _e: on_mag_phase_change())
        self.cmb_plot_scale.bind("<<ComboboxSelected>>", lambda _e: on_plot_scale_change())

    def _build_header(self) -> None:
        header = tk.Frame(self.frame, bg=CARD_BG, highlightbackground="#d9e0e8", highlightthickness=1)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)

        left = tk.Frame(header, bg=CARD_BG)
        left.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        left.grid_columnconfigure(0, weight=1)

        tk.Label(
            left,
            text="Measurement Results Workbench",
            bg=CARD_BG,
            fg=TEXT,
            font=("TkDefaultFont", 15, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            left,
            textvariable=self._vm.data_source_text,
            bg=CARD_BG,
            fg=MUTED,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(3, 0))
        self._fixture_badge = tk.Label(
            left,
            textvariable=self._vm.fixture_badge_text,
            bg="#fff7ed",
            fg="#b45309",
            anchor="w",
            padx=6,
            pady=2,
        )
        self._fixture_badge_trace = self._vm.fixture_badge_text.trace_add("write", self._sync_fixture_badge)
        self._sync_fixture_badge()

        controls = tk.Frame(header, bg=CARD_BG)
        controls.grid(row=0, column=1, sticky="e", padx=12, pady=10)
        controls.grid_columnconfigure(1, weight=1)

        tk.Label(controls, text="Plot", bg=CARD_BG, fg=MUTED).grid(row=0, column=0, sticky="e", padx=(0, 6))
        self.cmb_figure = ttk.Combobox(
            controls,
            textvariable=self._vm.figure_mode,
            values=["gain", "gain_db"],
            width=10,
            state="readonly",
        )
        self.cmb_figure.grid(row=0, column=1, sticky="ew")

        tk.Label(controls, text="Display", bg=CARD_BG, fg=MUTED).grid(row=1, column=0, sticky="e", padx=(0, 6))
        self.cmb_mag_phase = ttk.Combobox(
            controls,
            textvariable=self._vm.magnitude_phase_mode,
            values=["magnitude", "phase", "magnitude_phase"],
            width=16,
            state="readonly",
        )
        self.cmb_mag_phase.grid(row=1, column=1, sticky="ew", pady=(5, 0))

        tk.Label(controls, text="X axis", bg=CARD_BG, fg=MUTED).grid(
            row=2,
            column=0,
            sticky="e",
            padx=(0, 6),
        )
        self.cmb_plot_scale = ttk.Combobox(
            controls,
            textvariable=self._vm.plot_scale,
            values=["auto", "linear", "log"],
            width=16,
            state="readonly",
        )
        self.cmb_plot_scale.grid(row=2, column=1, sticky="ew", pady=(5, 0))

        tk.Label(
            controls,
            textvariable=self._vm.point_count_text,
            bg=CARD_BG,
            fg=BLUE,
            font=("TkDefaultFont", 10, "bold"),
            anchor="e",
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(7, 0))

    def _build_plots(self) -> None:
        plot_card = tk.Frame(self.frame, bg=CARD_BG, highlightbackground="#d9e0e8", highlightthickness=1)
        plot_card.grid(row=1, column=0, sticky="nsew")
        plot_card.grid_rowconfigure(0, weight=1)
        plot_card.grid_columnconfigure(0, weight=1)

        self._fig_gain = self._figure()
        self._ax_gain = self._fig_gain.add_subplot(111)
        self._style_axes(self._ax_gain, "Gain", "Frequency")
        (self._line_gain,) = self._ax_gain.plot([], [], "-", color=BLUE, linewidth=1.7)

        self._ax_gain_right = self._ax_gain.twinx()
        self._ax_gain_right.set_ylabel("Phase (deg)")
        (self._line_phase_gain,) = self._ax_gain_right.plot([], [], ":", color=PHASE, linewidth=1.4)

        self._canvas_gain = FigureCanvasTkAgg(self._fig_gain, master=plot_card)
        self._canvas_gain.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self._fig_db = self._figure()
        self._ax_db = self._fig_db.add_subplot(111)
        self._style_axes(self._ax_db, "Gain (dB)", "Frequency")
        (self._line_db,) = self._ax_db.plot([], [], "-", color=BLUE, linewidth=1.7)

        self._ax_db_right = self._ax_db.twinx()
        self._ax_db_right.set_ylabel("Phase (deg)")
        (self._line_phase_db,) = self._ax_db_right.plot([], [], ":", color=PHASE, linewidth=1.4)

        self._canvas_db = FigureCanvasTkAgg(self._fig_db, master=plot_card)

    def _sync_fixture_badge(self, *_args) -> None:
        if self._vm.fixture_badge_text.get().strip():
            self._fixture_badge.grid(row=2, column=0, sticky="w", pady=(6, 0))
        else:
            self._fixture_badge.grid_remove()

    def _figure(self) -> Figure:
        fig = Figure(figsize=(8, 5), facecolor=CARD_BG)
        fig.subplots_adjust(left=0.08, right=0.9, top=0.94, bottom=0.12)
        return fig

    def _style_axes(self, ax, ylabel: str, xlabel: str) -> None:
        ax.set_facecolor("#fbfdff")
        ax.set_ylabel(ylabel)
        ax.set_xlabel(xlabel)
        ax.grid(True, color="#e2e8f0", linewidth=0.8)
        ax.tick_params(colors=TEXT)
        for spine in ax.spines.values():
            spine.set_color("#cbd5e1")

    def set_mode(self, mode: str) -> None:
        if mode == "gain_db":
            self._canvas_gain.get_tk_widget().grid_remove()
            self._canvas_db.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        else:
            self._canvas_db.get_tk_widget().grid_remove()
            self._canvas_gain.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def set_reference_coverage(self, minimum_hz: float, maximum_hz: float) -> None:
        self._reference_coverage_hz = (min(minimum_hz, maximum_hz), max(minimum_hz, maximum_hz))

    def update_result(self, result: SweepResult, freq_unit: str, mag_phase_mode: str) -> None:
        freq_hz = np.array([p.freq_hz for p in result.points], dtype=float)
        gain = np.array([p.gain_linear for p in result.points], dtype=float)
        gain_db = np.array([p.gain_db for p in result.points], dtype=float)

        phase_x: list[float] = []
        phase_y: list[float] = []
        for p in result.points:
            if p.phase_deg is not None:
                phase_x.append(p.freq_hz)
                phase_y.append(p.phase_deg)

        scale = CvtTools.convert_general_unit(freq_unit)
        x = freq_hz / scale if len(freq_hz) else np.array([])
        px = np.array(phase_x, dtype=float) / scale if phase_x else np.array([])
        py = np.array(phase_y, dtype=float) if phase_y else np.array([])

        self._line_gain.set_data(x, gain)
        self._line_db.set_data(x, gain_db)
        self._line_phase_gain.set_data(px, py)
        self._line_phase_db.set_data(px, py)

        x_scale = choose_frequency_scale(
            freq_hz,
            requested=self._vm.plot_scale.get(),
            sweep_is_log=bool(self._vm.is_log.get()),
        )
        self._ax_gain.set_xscale(x_scale)
        self._ax_db.set_xscale(x_scale)

        if mag_phase_mode == "magnitude":
            self._line_gain.set_visible(True)
            self._line_db.set_visible(True)
            self._line_phase_gain.set_visible(False)
            self._line_phase_db.set_visible(False)
        elif mag_phase_mode == "phase":
            self._line_gain.set_visible(False)
            self._line_db.set_visible(False)
            self._line_phase_gain.set_visible(True)
            self._line_phase_db.set_visible(True)
        else:
            self._line_gain.set_visible(True)
            self._line_db.set_visible(True)
            self._line_phase_gain.set_visible(True)
            self._line_phase_db.set_visible(True)

        self._ax_gain.set_xlabel(f"Frequency ({freq_unit})")
        self._ax_db.set_xlabel(f"Frequency ({freq_unit})")

        self._update_reference_spans(freq_hz=freq_hz, unit_scale=scale)
        self._autoscale()
        self._canvas_gain.draw_idle()
        self._canvas_db.draw_idle()

    def _autoscale(self) -> None:
        for ax in (self._ax_gain, self._ax_gain_right, self._ax_db, self._ax_db_right):
            ax.relim()
            ax.autoscale_view()

    def _update_reference_spans(self, *, freq_hz: np.ndarray, unit_scale: float) -> None:
        for span in self._reference_spans:
            span.remove()
        self._reference_spans.clear()
        if self._reference_coverage_hz is None or freq_hz.size == 0:
            return

        data_min = float(np.min(freq_hz)) / unit_scale
        data_max = float(np.max(freq_hz)) / unit_scale
        ref_min = self._reference_coverage_hz[0] / unit_scale
        ref_max = self._reference_coverage_hz[1] / unit_scale
        left_end = min(ref_min, data_max)
        right_start = max(ref_max, data_min)

        for axis in (self._ax_gain, self._ax_db):
            if data_min < left_end:
                self._reference_spans.append(
                    axis.axvspan(data_min, left_end, color="#f59e0b", alpha=0.10, zorder=0)
                )
            if right_start < data_max:
                self._reference_spans.append(
                    axis.axvspan(right_start, data_max, color="#f59e0b", alpha=0.10, zorder=0)
                )

    def figures(self) -> dict[str, Figure]:
        return {"gain": self._fig_gain, "db": self._fig_db}
