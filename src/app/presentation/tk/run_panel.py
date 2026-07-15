from __future__ import annotations

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


class RunPanel(tk.Frame):
    def __init__(self, parent: tk.Misc, vm: ViewModel) -> None:
        super().__init__(parent, bg=PANEL_BG)
        self._vm = vm
        self._build()

    def bind_actions(
        self,
        *,
        on_start,
        on_stop,
        on_save_data,
        on_load_data,
        on_load_demo_fixture,
        on_load_ref,
        on_save_settings,
        on_load_settings,
    ) -> None:
        self.btn_start.configure(command=on_start)
        self.btn_stop.configure(command=on_stop)
        self.btn_save_data.configure(command=on_save_data)
        self.btn_load_data.configure(command=on_load_data)
        self.btn_load_demo_fixture.configure(command=on_load_demo_fixture)
        self.btn_load_ref.configure(command=on_load_ref)
        self.btn_save_settings.configure(command=on_save_settings)
        self.btn_load_settings.configure(command=on_load_settings)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        self._title("Run / Status", 0)
        self._build_run_card(1)
        self._build_export_card(2)
        self._build_source_card(3)
        self._build_event_card(4)
        self._build_safety_card(5)

    def _title(self, text: str, row: int) -> None:
        label = tk.Label(
            self,
            text=text,
            bg=PANEL_BG,
            fg=TEXT,
            font=("TkDefaultFont", 14, "bold"),
            anchor="w",
        )
        label.grid(row=row, column=0, sticky="ew", pady=(0, 10))

    def _card(self, title: str, row: int) -> ttk.LabelFrame:
        card = ttk.LabelFrame(self, text=title, padding=(10, 8))
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)
        return card

    def _build_run_card(self, row: int) -> None:
        card = self._card("Sweep control", row)

        metrics = tk.Frame(card, bg=CARD_BG)
        metrics.grid(row=0, column=0, sticky="ew")
        metrics.grid_columnconfigure((0, 1), weight=1)

        self._metric(metrics, "State", self._vm.run_state_text, 0, 0, GREEN)
        self._metric(metrics, "Progress", self._vm.progress_text, 0, 1, AMBER)
        self._metric(metrics, "Elapsed", self._vm.elapsed_text, 1, 0, MUTED)
        self._metric(metrics, "Latest frequency", self._vm.latest_frequency_text, 1, 1, MUTED)

        buttons = ttk.Frame(card)
        buttons.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        buttons.grid_columnconfigure((0, 1), weight=1)

        self.btn_start = tk.Button(
            buttons,
            text="Start",
            bg=GREEN,
            fg="white",
            activebackground="#166534",
            activeforeground="white",
            relief=tk.FLAT,
            padx=10,
            pady=7,
        )
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.btn_stop = tk.Button(
            buttons,
            text="Stop",
            bg=RED,
            fg="white",
            activebackground="#991b1b",
            activeforeground="white",
            relief=tk.FLAT,
            padx=10,
            pady=7,
            state="disabled",
        )
        self.btn_stop.grid(row=0, column=1, sticky="ew")

    def _build_export_card(self, row: int) -> None:
        card = self._card("Data / Export", row)
        actions = ttk.Frame(card)
        actions.grid(row=0, column=0, sticky="ew")
        actions.grid_columnconfigure((0, 1), weight=1)

        self.btn_load_data = ttk.Button(actions, text="Load Data")
        self.btn_load_data.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 6))
        self.btn_save_data = ttk.Button(actions, text="Save Data")
        self.btn_save_data.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        self.btn_load_ref = ttk.Button(actions, text="Load Ref")
        self.btn_load_ref.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(0, 6))
        self.btn_load_demo_fixture = tk.Button(
            actions,
            text="Load Demo Fixture",
            bg=AMBER,
            fg="white",
            activebackground="#92400e",
            activeforeground="white",
            relief=tk.FLAT,
            padx=8,
            pady=5,
        )
        self.btn_load_demo_fixture.grid(row=1, column=1, sticky="ew", pady=(0, 6))

        self.btn_save_settings = ttk.Button(actions, text="Save Settings")
        self.btn_save_settings.grid(row=2, column=0, sticky="ew", padx=(0, 6))
        self.btn_load_settings = ttk.Button(actions, text="Load Settings")
        self.btn_load_settings.grid(row=2, column=1, sticky="ew")

        self._wrapped_label(card, self._vm.reference_receipt_text, 1, MUTED)
        self._wrapped_label(card, self._vm.export_receipt_text, 2, MUTED)

    def _build_source_card(self, row: int) -> None:
        card = self._card("Source receipt", row)
        self._wrapped_label(card, self._vm.data_source_text, 0, TEXT, bold=True)
        self._fixture_badge = tk.Label(
            card,
            textvariable=self._vm.fixture_badge_text,
            bg="#fff7ed",
            fg=AMBER,
            anchor="w",
            padx=6,
            pady=3,
        )
        self._fixture_badge_trace = self._vm.fixture_badge_text.trace_add("write", self._sync_fixture_badge)
        self._sync_fixture_badge()
        self._wrapped_label(card, self._vm.validation_receipt_text, 2, MUTED)

    def _build_safety_card(self, row: int) -> None:
        card = self._card("Operator safety", row)
        items = [
            "Model and address reviewed",
            "AWG amplitude and DUT limits checked",
            "Impedance and coupling confirmed",
            "Stop closes active AWG output",
        ]
        for idx, item in enumerate(items):
            line = ttk.Frame(card)
            line.grid(row=idx, column=0, sticky="ew", pady=2)
            tk.Label(line, text="□", bg=CARD_BG, fg=AMBER, width=2, anchor="w").pack(side=tk.LEFT)
            tk.Label(line, text=item, bg=CARD_BG, fg=TEXT, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _build_event_card(self, row: int) -> None:
        card = self._card("Event history", row)
        self._wrapped_label(card, self._vm.event_history_text, 0, MUTED)

    def _metric(
        self,
        parent: tk.Misc,
        label: str,
        variable: tk.StringVar,
        row: int,
        column: int,
        color: str,
    ) -> None:
        box = tk.Frame(parent, bg=CARD_BG, highlightbackground="#d9e0e8", highlightthickness=1)
        box.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0), pady=(0, 6))
        tk.Label(box, text=label, bg=CARD_BG, fg=MUTED, font=("TkDefaultFont", 9)).pack(anchor="w", padx=7, pady=(5, 0))
        tk.Label(
            box,
            textvariable=variable,
            bg=CARD_BG,
            fg=color,
            font=("TkDefaultFont", 11, "bold"),
        ).pack(anchor="w", padx=7, pady=(0, 6))

    def _wrapped_label(
        self,
        parent: tk.Misc,
        variable: tk.StringVar,
        row: int,
        color: str,
        *,
        bold: bool = False,
    ) -> None:
        tk.Label(
            parent,
            textvariable=variable,
            bg=CARD_BG,
            fg=color,
            justify=tk.LEFT,
            anchor="w",
            wraplength=250,
            font=("TkDefaultFont", 10, "bold" if bold else "normal"),
        ).grid(row=row, column=0, sticky="ew")

    def _sync_fixture_badge(self, *_args) -> None:
        if self._vm.fixture_badge_text.get().strip():
            self._fixture_badge.grid(row=1, column=0, sticky="ew", pady=(6, 4))
        else:
            self._fixture_badge.grid_remove()
