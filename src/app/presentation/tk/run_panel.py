from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk

from app.presentation.tk.view_model import ViewModel


PANEL_BG = "#f4f6f8"
CARD_BG = "#ffffff"
TEXT = "#1f2937"
MUTED = "#64748b"
GREEN = "#15803d"
AMBER = "#b45309"
RED = "#b91c1c"
BLUE = "#1d4ed8"


class RunPanel(tk.Frame):
    """Right-hand workflow surface; hardware behavior stays in the controller."""

    def __init__(self, parent: tk.Misc, vm: ViewModel) -> None:
        super().__init__(parent, bg=PANEL_BG)
        self._vm = vm
        self._operation_mode = "idle"
        self._safety_widgets: list[tk.Widget] = []
        self._build()
        # Kept as non-rendered aliases for legacy controller/capture callers;
        # visible settings actions remain in the left setup sidebar.
        self.btn_save_settings = ttk.Button(self, text="Save Settings")
        self.btn_load_settings = ttk.Button(self, text="Load Settings")
        self._progress_trace = self._vm.progress_text.trace_add("write", self._sync_progress)
        self._sync_progress()

    def bind_actions(
        self,
        *,
        on_start,
        on_stop,
        on_save_data,
        on_load_data,
        on_load_demo_fixture,
        on_load_ref,
        on_save_settings=None,
        on_load_settings=None,
        on_replay_fixture=None,
        on_apply_analysis=None,
        on_reset_analysis=None,
        on_clear_reference=None,
        on_export_report=None,
        on_open_output=None,
    ) -> None:
        self.btn_start.configure(command=on_start)
        self.btn_stop.configure(command=on_stop)
        self.btn_save_data.configure(command=on_save_data)
        self.btn_load_data.configure(command=on_load_data)
        self.btn_load_demo_fixture.configure(command=on_load_demo_fixture)
        self.btn_load_ref.configure(command=on_load_ref)
        self.btn_replay_fixture.configure(command=on_replay_fixture or on_load_demo_fixture)
        self.btn_save_settings.configure(command=on_save_settings)
        self.btn_load_settings.configure(command=on_load_settings)
        if on_apply_analysis is not None:
            self.btn_apply_analysis.configure(command=on_apply_analysis)
        if on_reset_analysis is not None:
            self.btn_reset_analysis.configure(command=on_reset_analysis)
        else:
            self.btn_reset_analysis.configure(command=self.reset_analysis)
        if on_clear_reference is not None:
            self.btn_clear_reference.configure(command=on_clear_reference)
        else:
            self.btn_clear_reference.configure(command=self.clear_reference)
        if on_export_report is not None:
            self.btn_export_report.configure(command=on_export_report)
        if on_open_output is not None:
            self.btn_open_output.configure(command=on_open_output)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self._build_source_card(0)
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)
        self.run_tab = tk.Frame(self.notebook, bg=PANEL_BG)
        self.analysis_tab = tk.Frame(self.notebook, bg=PANEL_BG)
        self.history_tab = tk.Frame(self.notebook, bg=PANEL_BG)
        self.notebook.add(self.run_tab, text="Run")
        self.notebook.add(self.analysis_tab, text="Analysis")
        self.notebook.add(self.history_tab, text="History")
        for tab in (self.run_tab, self.analysis_tab, self.history_tab):
            tab.grid_columnconfigure(0, weight=1)
        self._build_run_tab()
        self._build_analysis_tab()
        self._build_history_tab()

    def _build_source_card(self, row: int) -> None:
        card = ttk.LabelFrame(self, text="Source receipt", padding=(10, 7))
        card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)
        self._wrapped_label(card, self._vm.data_source_text, 0, TEXT, bold=True)
        self._fixture_badge = tk.Label(card, textvariable=self._vm.fixture_badge_text, bg="#fff7ed", fg=AMBER, anchor="w", padx=6, pady=3)
        self._fixture_badge_trace = self._vm.fixture_badge_text.trace_add("write", self._sync_fixture_badge)
        self._sync_fixture_badge()
        self._wrapped_label(card, self._vm.validation_receipt_text, 2, MUTED)
        self._wrapped_label(card, self._vm.point_count_text, 3, BLUE, bold=True)

    def _build_run_tab(self) -> None:
        self._title(self.run_tab, "Run / Status", 0)
        card = self._card(self.run_tab, "Sweep control", 1)
        metrics = tk.Frame(card, bg=CARD_BG)
        metrics.grid(row=0, column=0, sticky="ew")
        metrics.grid_columnconfigure((0, 1), weight=1)
        self._metric(metrics, "State", self._vm.run_state_text, 0, 0, GREEN)
        self._metric(metrics, "Progress", self._vm.progress_text, 0, 1, AMBER)
        self._metric(metrics, "Elapsed", self._vm.elapsed_text, 1, 0, MUTED)
        self._metric(metrics, "Latest frequency", self._vm.latest_frequency_text, 1, 1, MUTED)
        self.progressbar = ttk.Progressbar(card, orient="horizontal", mode="determinate", maximum=100)
        self.progressbar.grid(row=1, column=0, sticky="ew", pady=(2, 8))
        buttons = ttk.Frame(card)
        buttons.grid(row=2, column=0, sticky="ew")
        buttons.grid_columnconfigure((0, 1), weight=1)
        self.btn_start = ttk.Button(buttons, text="Start Hardware", style="Accent.TButton")
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_stop = ttk.Button(buttons, text="Stop", style="Danger.TButton", state="disabled")
        self.btn_stop.grid(row=0, column=1, sticky="ew")

        data_card = self._card(self.run_tab, "Data", 2)
        data_card.grid_columnconfigure(1, weight=1)
        tk.Label(data_card, text="Replay speed", bg=CARD_BG, fg=MUTED, anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 5)
        )
        self.cmb_replay_speed = ttk.Combobox(
            data_card, textvariable=self._vm.replay_speed, values=["1x", "2x", "4x"], state="readonly", width=8
        )
        self.cmb_replay_speed.grid(row=0, column=1, sticky="ew", pady=(0, 5))
        actions = ttk.Frame(data_card)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew")
        actions.grid_columnconfigure((0, 1), weight=1)
        self.btn_load_data = ttk.Button(actions, text="Load Data")
        self.btn_load_data.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 6))
        self.btn_save_data = ttk.Button(actions, text="Save Data")
        self.btn_save_data.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        self.btn_load_demo_fixture = ttk.Button(actions, text="Load Demo Fixture", style="Demo.TButton")
        self.btn_load_demo_fixture.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        self.btn_replay_fixture = ttk.Button(actions, text="Replay Fixture")
        self.btn_replay_fixture.grid(row=1, column=1, sticky="ew")
        self._wrapped_label(data_card, self._vm.export_receipt_text, 2, MUTED, columnspan=2)
        self._build_safety_card(self.run_tab, 3)

    def _build_analysis_tab(self) -> None:
        self._title(self.analysis_tab, "File analysis", 0)
        card = self._card(self.analysis_tab, "Analysis options", 1)
        card.grid_columnconfigure(1, weight=1)
        self.cmb_analysis_dataset = self._combo(card, "Dataset", self._vm.analysis_dataset, ["canonical", "raw"], 0)
        self.cmb_analysis_correction = self._combo(card, "Correction", self._vm.analysis_correction, ["none", "magnitude", "complex"], 1)
        self.cmb_analysis_coverage = self._combo(card, "Coverage", self._vm.analysis_coverage, ["reject", "clamp"], 2)
        ref_actions = ttk.Frame(card)
        ref_actions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        ref_actions.grid_columnconfigure((0, 1), weight=1)
        self.btn_load_ref = ttk.Button(ref_actions, text="Load Reference")
        self.btn_load_ref.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_clear_reference = ttk.Button(ref_actions, text="Clear Reference")
        self.btn_clear_reference.grid(row=0, column=1, sticky="ew")
        self.btn_apply_analysis = ttk.Button(card, text="Apply Analysis", style="Accent.TButton")
        self.btn_apply_analysis.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 4))
        self.btn_reset_analysis = ttk.Button(card, text="Reset Analysis")
        self.btn_reset_analysis.grid(row=5, column=0, columnspan=2, sticky="ew")
        self._wrapped_label(card, self._vm.reference_receipt_text, 6, MUTED, columnspan=2)
        self._wrapped_label(card, self._vm.analysis_status_text, 7, TEXT, bold=True, columnspan=2)
        export_card = self._card(self.analysis_tab, "Report output", 2)
        export_actions = ttk.Frame(export_card)
        export_actions.grid(row=0, column=0, sticky="ew")
        export_actions.grid_columnconfigure((0, 1), weight=1)
        self.btn_export_report = ttk.Button(export_actions, text="Export Report")
        self.btn_export_report.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_open_output = ttk.Button(export_actions, text="Open Output")
        self.btn_open_output.grid(row=0, column=1, sticky="ew")
        self._wrapped_label(export_card, self._vm.export_receipt_text, 1, MUTED)

    def _build_history_tab(self) -> None:
        self._title(self.history_tab, "History / validation", 0)
        self._build_safety_card(self.history_tab, 1)
        card = self._card(self.history_tab, "Event history", 2)
        history_frame = ttk.Frame(card)
        history_frame.grid(row=0, column=0, sticky="nsew")
        history_frame.grid_rowconfigure(0, weight=1)
        history_frame.grid_columnconfigure(0, weight=1)
        history = tk.Text(history_frame, height=9, wrap="word", bg=CARD_BG, fg=MUTED, relief=tk.FLAT, borderwidth=0)
        history.grid(row=0, column=0, sticky="nsew")
        history_scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=history.yview)
        history_scrollbar.grid(row=0, column=1, sticky="ns")
        history.configure(yscrollcommand=history_scrollbar.set)
        card.grid_rowconfigure(0, weight=1)
        self._history_text = history
        self._history_trace = self._vm.event_history_text.trace_add("write", self._sync_history)
        self._sync_history()

    def _build_safety_card(self, parent: tk.Misc, row: int) -> None:
        card = self._card(parent, "Operator safety", row)
        checks = (
            ("Model and address reviewed", self._vm.safety_connections_checked),
            ("AWG amplitude and DUT limits checked", self._vm.safety_limits_checked),
            ("Impedance and coupling confirmed", self._vm.safety_output_checked),
        )
        for idx, (label, variable) in enumerate(checks):
            checkbutton = ttk.Checkbutton(card, text=label, variable=variable)
            checkbutton.grid(row=idx, column=0, sticky="w", pady=2)
            self._safety_widgets.append(checkbutton)
        tk.Label(card, text="Stop action requests output-off; it is not a hardware guarantee.", bg=CARD_BG, fg=AMBER, justify=tk.LEFT, anchor="w", wraplength=280).grid(row=3, column=0, sticky="ew", pady=(5, 0))

    def set_operation_state(self, mode: str, *, has_data: bool = False, can_replay: bool = False, has_reference: bool = False, can_analyze: bool = False, has_output: bool = False) -> None:
        self._operation_mode = mode
        self._vm.operation_mode.set(mode)
        active = mode in {"live", "replay", "stopping"}
        busy = mode in {"loading", "analyzing", "exporting", "discovery"}
        self.btn_start.configure(state="normal" if mode == "idle" else "disabled")
        self.btn_stop.configure(state="normal" if active else "disabled")
        self.btn_load_demo_fixture.configure(state="normal" if mode == "idle" else "disabled")
        self.btn_replay_fixture.configure(state="normal" if mode == "idle" and can_replay else "disabled")
        self.cmb_replay_speed.configure(state="readonly" if mode == "idle" else "disabled")
        self.btn_load_data.configure(state="normal" if mode == "idle" else "disabled")
        self.btn_save_data.configure(state="normal" if mode == "idle" and has_data else "disabled")
        self.btn_load_ref.configure(state="normal" if mode == "idle" else "disabled")
        self.btn_clear_reference.configure(state="normal" if mode == "idle" and has_reference else "disabled")
        analysis_state = "readonly" if mode == "idle" else "disabled"
        self.cmb_analysis_dataset.configure(state=analysis_state)
        self.cmb_analysis_correction.configure(state=analysis_state)
        self.cmb_analysis_coverage.configure(state=analysis_state)
        self.btn_apply_analysis.configure(state="normal" if mode == "idle" and can_analyze else "disabled")
        self.btn_reset_analysis.configure(state="normal" if mode == "idle" and can_analyze else "disabled")
        self.btn_export_report.configure(state="normal" if mode == "idle" and has_data else "disabled")
        self.btn_open_output.configure(state="normal" if mode == "idle" and has_output else "disabled")
        for widget in self._safety_widgets:
            widget.configure(state="normal" if mode == "idle" else "disabled")
        if busy:
            self._vm.run_state_text.set(mode.capitalize())

    def reset_analysis(self) -> None:
        self._vm.analysis_dataset.set("canonical")
        self._vm.analysis_correction.set("none")
        self._vm.analysis_coverage.set("reject")
        self._vm.analysis_status_text.set("No file analysis applied")

    def clear_reference(self) -> None:
        self._vm.reference_receipt_text.set("No reference loaded")
        self._vm.analysis_status_text.set("Reference cleared")

    def _title(self, parent: tk.Misc, text: str, row: int) -> None:
        tk.Label(parent, text=text, bg=PANEL_BG, fg=TEXT, font=("TkDefaultFont", 12, "bold"), anchor="w").grid(row=row, column=0, sticky="ew", pady=(0, 7))

    def _card(self, parent: tk.Misc, title: str, row: int) -> ttk.LabelFrame:
        card = ttk.LabelFrame(parent, text=title, padding=(9, 7))
        card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)
        return card

    def _metric(self, parent: tk.Misc, label: str, variable: tk.StringVar, row: int, column: int, color: str) -> None:
        box = tk.Frame(parent, bg=CARD_BG, highlightbackground="#d9e0e8", highlightthickness=1)
        box.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0), pady=(0, 5))
        tk.Label(box, text=label, bg=CARD_BG, fg=MUTED, font=("TkDefaultFont", 8)).pack(anchor="w", padx=6, pady=(4, 0))
        tk.Label(box, textvariable=variable, bg=CARD_BG, fg=color, font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=6, pady=(0, 5))

    def _wrapped_label(
        self,
        parent: tk.Misc,
        variable: tk.StringVar,
        row: int,
        color: str,
        *,
        bold: bool = False,
        columnspan: int = 1,
    ) -> None:
        tk.Label(
            parent,
            textvariable=variable,
            bg=CARD_BG,
            fg=color,
            justify=tk.LEFT,
            anchor="w",
            wraplength=280,
            font=("TkDefaultFont", 9, "bold" if bold else "normal"),
        ).grid(row=row, column=0, columnspan=columnspan, sticky="ew", pady=(3, 0))

    def _combo(self, parent: tk.Misc, label: str, variable: tk.StringVar, values: list[str], row: int) -> ttk.Combobox:
        tk.Label(parent, text=label, bg=CARD_BG, fg=MUTED, anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=14)
        combo.grid(row=row, column=1, sticky="ew", pady=2)
        return combo

    def _sync_fixture_badge(self, *_args) -> None:
        if self._vm.fixture_badge_text.get().strip():
            self._fixture_badge.grid(row=1, column=0, sticky="ew", pady=(5, 2))
        else:
            self._fixture_badge.grid_remove()

    def _sync_progress(self, *_args) -> None:
        match = re.match(r"\s*(\d+)\s*/\s*(\d+)", self._vm.progress_text.get())
        if match and int(match.group(2)):
            self.progressbar.configure(value=min(100.0, int(match.group(1)) * 100.0 / int(match.group(2))))
        else:
            self.progressbar.configure(value=0)

    def _sync_history(self, *_args) -> None:
        self._history_text.configure(state="normal")
        self._history_text.delete("1.0", tk.END)
        self._history_text.insert("1.0", self._vm.event_history_text.get())
        self._history_text.configure(state="disabled")
