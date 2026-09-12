"""Opt-in real Tk smoke. Requires a graphical desktop, never uses instruments."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--screenshots", action="store_true", help="Capture this Tk window on macOS using Quartz")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    from app.bootstrap import build_desktop_app
    from app.runtime.paths import AppPaths

    checks, screenshots = [], []
    with tempfile.TemporaryDirectory(prefix="auto-desktop-smoke-") as runtime:
        with patch("app.bootstrap.create_instrument_ports", side_effect=AssertionError("No hardware in desktop smoke")):
            app = build_desktop_app(AppPaths.from_root(Path(runtime)))
        window, controller, vm = app.window, app.controller, app.window.vm

        def wait_for(predicate, timeout=20):
            deadline = time.monotonic() + timeout
            errors = []

            def poll():
                if predicate():
                    window.quit()
                    return
                if time.monotonic() >= deadline:
                    errors.append(TimeoutError(f"Desktop smoke timed out: {vm.status_text.get()}"))
                    window.quit()
                    return
                window.after(10, poll)

            window.after(0, poll)
            window.mainloop()
            if errors:
                raise errors[0]
            window.update_idletasks()

        def capture(name):
            window.update_idletasks()
            # Let Cocoa present the pending native frame before reading pixels.
            window.after(80, window.quit)
            window.mainloop()
            if args.screenshots:
                from capture_operator_console_demo import _capture_window_with_quartz, _find_window_id_with_quartz
                window_id = _find_window_id_with_quartz(window.title())
                if window_id is None or not _capture_window_with_quartz(window_id, output / name):
                    raise RuntimeError("Native window capture unavailable; check Screen Recording permission")
                screenshots.append(name)

        def assert_inside(widget):
            left = widget.winfo_rootx() - window.winfo_rootx()
            top = widget.winfo_rooty() - window.winfo_rooty()
            assert widget.winfo_ismapped(), str(widget)
            assert 0 <= left and left + widget.winfo_width() <= window.winfo_width(), (str(widget), left)
            assert 0 <= top and top + widget.winfo_height() <= window.winfo_height(), (str(widget), top)

        try:
            controller.initialize()
            window.geometry("1440x810+20+40")
            window.update()
            assert window.winfo_ismapped()
            assert str(window.btn_load_demo_fixture.cget("state")) == "normal"
            assert str(window.btn_replay_fixture.cget("state")) == "disabled"
            checks.append("initial mapped window; independent demo/replay actions")
            window.btn_load_demo_fixture.invoke()
            wait_for(lambda: controller._operation == "idle")
            assert len(controller._ui_handler.latest_result.points) == 72
            assert "No hardware" in vm.fixture_badge_text.get()
            assert not vm.calibration_enabled.get()
            checks.append("normal demo load; 72 points; no hardware badge; correction not silently enabled")
            vm.replay_speed.set("4x")
            window.btn_replay_fixture.invoke()
            assert controller._ui_handler.latest_result.is_empty
            assert str(window.btn_load_data.cget("state")) == "disabled"
            capture("replay-early.png")
            wait_for(lambda: len(controller._ui_handler.latest_result.points) >= 12)
            window.btn_stop.invoke()
            partial = len(controller._ui_handler.latest_result.points)
            assert 0 < partial < 72
            assert controller._ui_handler.latest_result.meta["run_status"] == "stopped"
            capture("replay-partial.png")
            checks.append(f"normal Replay/Stop retained {partial}/72 points; conflicting buttons disabled")
            window.btn_replay_fixture.invoke()
            wait_for(lambda: controller._operation == "idle")
            assert vm.progress_text.get() == "72 / 72"
            assert len(window.plot_widget._line_db.get_xdata()) == 72
            capture("console-1440.png")
            checks.append("restart completed 72/72; actual Matplotlib line populated")
            window.geometry("1280x760+20+40")
            window.update()
            for widget in (window.btn_load_demo_fixture, window.btn_replay_fixture, window.btn_start,
                           window.plot_widget.frame, window.run_panel.notebook,
                           window.cmb_figure, window.cmb_mag_phase, window.cmb_plot_scale, window.btn_fit_plot):
                assert_inside(widget)
            capture("console-1280.png")
            window.run_panel.notebook.select(window.run_panel.analysis_tab)
            vm.analysis_dataset.set("raw")
            vm.analysis_correction.set("complex")
            window.btn_apply_analysis.invoke()
            wait_for(lambda: controller._operation == "idle")
            assert controller._ui_handler.latest_result.meta["reference_correction"] == "complex"
            for widget in (window.btn_apply_analysis, window.btn_export_report, window.btn_open_output):
                assert_inside(widget)
            capture("analysis-1280.png")
            checks.append("1280x760 Run/Analysis main controls within window; explicit raw/complex analysis")
            controller.save_data_to_path(output / "displayed.mat")
            wait_for(lambda: controller._operation == "idle")
            controller.export_report_to_path(output / "report")
            wait_for(lambda: controller._operation == "idle")
            assert (output / "report" / "report.html").is_file()
            assert (output / "displayed.mat").is_file()
            assert "manifest.json" in vm.export_receipt_text.get()
            capture("export-1280.png")
            window.run_panel.notebook.select(window.run_panel.history_tab)
            window.update()
            capture("history-1280.png")
            checks.append("real Tk callbacks saved MAT/CSV/TXT and reproducible report; no native chooser test")
            receipt = {"status": "passed", "checks": checks, "screenshots": screenshots,
                       "point_count": 72, "source": vm.data_source_text.get(), "badge": vm.fixture_badge_text.get(),
                       "live_hardware_used": False, "native_dialogs_tested": False,
                       "python": sys.version, "tk": window.tk.call("info", "patchlevel")}
            (output / "desktop-smoke.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(json.dumps(receipt, indent=2), flush=True)
        finally:
            controller.on_close()
            deadline = time.monotonic() + 10
            while not controller._destroyed and time.monotonic() < deadline:
                window.update()
                time.sleep(0.01)
            if not controller._destroyed:
                raise TimeoutError("Desktop failed to close cleanly")


if __name__ == "__main__":
    main()
