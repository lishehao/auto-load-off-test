from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.presentation.tk.control_panel import ControlPanel
from app.presentation.tk.plot_widget import PlotWidget
from app.presentation.tk.run_panel import RunPanel
from app.presentation.tk.view_model import ViewModel


class AppWindow(tk.Tk):
    def __init__(self, vm: ViewModel | None = None) -> None:
        super().__init__()
        self.vm = vm or ViewModel(self)
        self.title("Auto-Load-off-Test Operator Console")
        self.geometry("1440x810")
        self.minsize(1280, 760)
        self.configure(bg="#f4f6f8")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._configure_style()

        self._on_close = None

        container = tk.Frame(self, bg="#f4f6f8")
        container.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        container.grid_columnconfigure(0, weight=0, minsize=295)
        container.grid_columnconfigure(1, weight=1, minsize=640)
        container.grid_columnconfigure(2, weight=0, minsize=355)
        container.grid_rowconfigure(0, weight=1)

        left = tk.Frame(container, bg="#f4f6f8", width=300)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_propagate(False)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        center = tk.Frame(container, bg="#f4f6f8")
        center.grid(row=0, column=1, sticky="nsew", padx=(0, 12))
        center.grid_rowconfigure(0, weight=1)
        center.grid_columnconfigure(0, weight=1)

        right = tk.Frame(container, bg="#f4f6f8")
        right.grid(row=0, column=2, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.control_panel = self._build_sidebar(left)

        self.plot_widget = PlotWidget(center, self.vm)
        self.plot_widget.frame.grid(row=0, column=0, sticky="nsew")

        right_content = self._build_scrollable_content(right, width=340)
        self.run_panel = RunPanel(right_content, self.vm)
        self.run_panel.pack(fill=tk.BOTH, expand=True)
        self._alias_control_widgets()

        status_bar = tk.Frame(self, bg="#e5eaf0")
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.lb_status = tk.Label(
            status_bar,
            textvariable=self.vm.status_text,
            anchor="w",
            bg="#e5eaf0",
            fg="#1f2937",
            padx=10,
            pady=4,
        )
        self.lb_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.canvas_awg = tk.Canvas(status_bar, width=14, height=14, bg="#e5eaf0", highlightthickness=0)
        self.canvas_awg.pack(side=tk.RIGHT, padx=6)
        self.awg_light = self.canvas_awg.create_oval(2, 2, 12, 12, fill="red")
        tk.Label(status_bar, text="AWG", bg="#e5eaf0", fg="#1f2937").pack(side=tk.RIGHT)

        self.canvas_osc = tk.Canvas(status_bar, width=14, height=14, bg="#e5eaf0", highlightthickness=0)
        self.canvas_osc.pack(side=tk.RIGHT, padx=6)
        self.osc_light = self.canvas_osc.create_oval(2, 2, 12, 12, fill="red")
        tk.Label(status_bar, text="OSC", bg="#e5eaf0", fg="#1f2937").pack(side=tk.RIGHT)

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
        on_scan_resources,
        on_test_connect,
        on_close,
        on_figure_change,
        on_mag_phase_change,
        on_plot_scale_change,
    ) -> None:
        self.control_panel.bind_actions(
            on_save_settings=on_save_settings,
            on_load_settings=on_load_settings,
            on_scan_resources=on_scan_resources,
            on_test_connect=on_test_connect,
        )
        self.run_panel.bind_actions(
            on_start=on_start,
            on_stop=on_stop,
            on_save_data=on_save_data,
            on_load_data=on_load_data,
            on_load_demo_fixture=on_load_demo_fixture,
            on_load_ref=on_load_ref,
            on_save_settings=on_save_settings,
            on_load_settings=on_load_settings,
        )
        self.plot_widget.bind_controls(
            on_figure_change=on_figure_change,
            on_mag_phase_change=on_mag_phase_change,
            on_plot_scale_change=on_plot_scale_change,
        )
        self._on_close = on_close

    def set_connection_status(self, awg_connected: bool, osc_connected: bool) -> None:
        if self.vm.source_mode.get() != "live":
            self.set_connection_idle()
            return
        self.canvas_awg.itemconfig(self.awg_light, fill="green" if awg_connected else "red")
        self.canvas_osc.itemconfig(self.osc_light, fill="green" if osc_connected else "red")
        self.vm.awg_connection_text.set("AWG online" if awg_connected else "AWG offline")
        self.vm.osc_connection_text.set("OSC online" if osc_connected else "OSC offline")

    def set_connection_idle(self) -> None:
        self.canvas_awg.itemconfig(self.awg_light, fill="#94a3b8")
        self.canvas_osc.itemconfig(self.osc_light, fill="#94a3b8")
        self.vm.awg_connection_text.set("AWG not used")
        self.vm.osc_connection_text.set("OSC not used")

    def on_close(self) -> None:
        if self._on_close is not None:
            self._on_close()
        else:
            self.destroy()

    def _alias_control_widgets(self) -> None:
        self.btn_start = self.run_panel.btn_start
        self.btn_stop = self.run_panel.btn_stop
        self.btn_save_data = self.run_panel.btn_save_data
        self.btn_load_data = self.run_panel.btn_load_data
        self.btn_load_demo_fixture = self.run_panel.btn_load_demo_fixture
        self.btn_load_ref = self.run_panel.btn_load_ref
        self.btn_save_settings = self.control_panel.btn_save_settings
        self.btn_load_settings = self.control_panel.btn_load_settings
        self.btn_scan_resources = self.control_panel.btn_scan_resources
        self.btn_test_connect = self.control_panel.btn_test_connect
        self.cmb_figure = self.plot_widget.cmb_figure
        self.cmb_mag_phase = self.plot_widget.cmb_mag_phase
        self.cmb_plot_scale = self.plot_widget.cmb_plot_scale

    def _build_sidebar(self, parent: tk.Frame) -> ControlPanel:
        content = self._build_scrollable_content(parent, width=300)
        panel = ControlPanel(content, self.vm)
        panel.pack(fill=tk.BOTH, expand=True)
        return panel

    def _build_scrollable_content(self, parent: tk.Frame, *, width: int) -> tk.Frame:
        canvas = tk.Canvas(parent, bg="#f4f6f8", highlightthickness=0, width=width)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        content = tk.Frame(canvas, bg="#f4f6f8")
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        def resize_content(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(window_id, width=canvas.winfo_width())

        content.bind("<Configure>", resize_content)
        canvas.bind("<Configure>", resize_content)
        return content

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", font=("TkDefaultFont", 10))
        style.configure("TLabelframe", background="#ffffff", bordercolor="#d9e0e8")
        style.configure(
            "TLabelframe.Label",
            background="#ffffff",
            foreground="#1f2937",
            font=("TkDefaultFont", 10, "bold"),
        )
        style.configure("TFrame", background="#ffffff")
        style.configure("TButton", padding=(8, 5))
        style.configure("TCombobox", padding=2)
