from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OUT_DIR = ROOT / "docs" / "images"
FIXTURE = ROOT / "demo_data" / "hyperframe_simulated_fixture.mat"
REFERENCE = ROOT / "demo_data" / "hyperframe_reference_fixture.mat"
POSTER = OUT_DIR / "auto-load-off-test-point-replay-demo.png"
VIDEO = OUT_DIR / "auto-load-off-test-point-replay-demo.mp4"
FRAME_RATE = 12
DEMO_SIZE = "1440x810+20+40"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.application.dto import SaveTarget  # noqa: E402
from app.application.services.export_receipts import build_export_receipt  # noqa: E402
from app.bootstrap import build_desktop_app  # noqa: E402
from app.demo.hyperframe_fixture import DEMO_LABEL, build_fixture_settings  # noqa: E402
from app.domain.models import SweepResult  # noqa: E402
from app.presentation.tk.mapper import settings_to_vm  # noqa: E402
from app.runtime.paths import AppPaths  # noqa: E402

from capture_operator_console_demo import (  # noqa: E402
    _capture_window,
    _ffmpeg_executable,
    _find_window_id,
    _raise_window,
    _require_tools,
)


def main() -> None:
    _require_tools()
    _require_file(FIXTURE)
    _require_file(REFERENCE)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    app = build_desktop_app(paths=AppPaths.from_root(ROOT))
    fixture_settings = build_fixture_settings()
    fixture_settings.freq_unit = "KHz"
    settings_to_vm(fixture_settings, app.window.vm)
    app.window.geometry(DEMO_SIZE)
    app.window.update()
    _raise_window(app.window)
    window_id = _find_window_id(app.window.title())
    print(f"window_id: {window_id}")

    loaded = app.controller.load_measurement_use_case.execute(str(FIXTURE))
    app.controller.load_reference_from_path(REFERENCE)
    with tempfile.TemporaryDirectory(prefix="auto-load-off-test-point-replay-") as td:
        session = PointReplayCaptureSession(
            app=app,
            frame_dir=Path(td),
            window_id=window_id,
            full_result=loaded.result,
        )
        session.run()


class PointReplayCaptureSession:
    def __init__(self, *, app, frame_dir: Path, window_id: int, full_result: SweepResult) -> None:
        self.app = app
        self.window = app.window
        self.vm = app.window.vm
        self.frame_dir = frame_dir
        self.window_id = window_id
        self.full_result = full_result
        self.total_points = len(full_result.points)
        self.frame_index = 1
        self.replay_index = 0

    def run(self) -> None:
        self.window.run_panel.btn_load_demo_fixture.configure(command=self._start_replay)
        self.vm.magnitude_phase_mode.set("magnitude_phase")
        self.window.plot_widget.set_mode(self.vm.figure_mode.get())
        self.app.controller.on_mag_phase_change()
        self._set_initial_state()
        self.window.after(1200, self._capture_start)
        self.window.mainloop()

    def _capture_start(self) -> None:
        _raise_window(self.window)
        self.window.after(500, lambda: self._capture_frames(12, self._press_demo_button))

    def _press_demo_button(self) -> None:
        self.window.run_panel.btn_load_demo_fixture.configure(relief="sunken")
        self._capture_frames(4, self._start_replay)

    def _start_replay(self) -> None:
        self.window.run_panel.btn_load_demo_fixture.configure(relief="flat")
        self.replay_index = 0
        self.app.controller._ui_handler.set_result(SweepResult(), refresh_plot=False)
        self.app.controller._ui_handler.set_fixture_source(label=DEMO_LABEL, path_name=FIXTURE.name)
        self._set_replay_state(0)
        self._capture_replay_step()

    def _capture_replay_step(self) -> None:
        if self.replay_index >= self.total_points:
            self._record_demo_export()
            self._capture_frames(24, self._finish)
            return

        self.replay_index += 1
        self._set_replay_state(self.replay_index)
        _capture_window(self.window_id, self.frame_dir / f"frame_{self.frame_index:04d}.png")
        self.frame_index += 1
        self.window.after(int(1000 / FRAME_RATE), self._capture_replay_step)

    def _capture_frames(self, remaining: int, done: Callable[[], None]) -> None:
        if remaining <= 0:
            done()
            return
        _capture_window(self.window_id, self.frame_dir / f"frame_{self.frame_index:04d}.png")
        self.frame_index += 1
        self.window.after(int(1000 / FRAME_RATE), lambda: self._capture_frames(remaining - 1, done))

    def _set_initial_state(self) -> None:
        self.app.controller._ui_handler.set_result(SweepResult(), refresh_plot=False)
        self.vm.source_mode.set("fixture")
        self.vm.figure_mode.set("gain_db")
        self.vm.magnitude_phase_mode.set("magnitude_phase")
        self.vm.plot_scale.set("log")
        self.vm.data_source_text.set(f"Fixture replay ready · {FIXTURE.name}")
        self.vm.fixture_badge_text.set("No hardware - simulated fixture")
        self.vm.validation_receipt_text.set("Ready for simulated point replay; not live hardware validation")
        self.vm.export_receipt_text.set("No export yet")
        self.vm.run_state_text.set("Ready to replay")
        self.vm.progress_text.set(f"0 / {self.total_points}")
        self.vm.point_count_text.set(f"0 / {self.total_points} points")
        self.vm.latest_frequency_text.set("-")
        self.vm.status_text.set("Ready to replay simulated fixture (no hardware)")
        self.window.set_connection_idle()
        self.window.plot_widget.set_mode("gain_db")
        self.app.controller._ui_handler.refresh_plot()

    def _set_replay_state(self, point_count: int) -> None:
        partial = SweepResult(
            points=list(self.full_result.points[:point_count]),
            meta=dict(self.full_result.meta),
        )
        self.app.controller._ui_handler.set_result(partial, refresh_plot=True)
        self.vm.export_receipt_text.set("Replaying deterministic fixture points; no hardware connected")
        self.vm.run_state_text.set("Replaying fixture" if point_count < self.total_points else "Fixture ready")
        self.vm.progress_text.set(f"{point_count} / {self.total_points}")
        self.vm.point_count_text.set(f"{point_count} / {self.total_points} points")
        if point_count:
            latest = self.full_result.points[point_count - 1]
            self.vm.latest_frequency_text.set(_format_frequency(latest.freq_hz))
        else:
            self.vm.latest_frequency_text.set("-")
        self.vm.status_text.set(f"Fixture replay point {point_count}/{self.total_points} (no hardware)")

    def _record_demo_export(self) -> None:
        settings = build_fixture_settings()
        artifacts = self.app.controller.save_measurement_use_case.execute(
            result=self.app.controller._ui_handler.latest_result,
            settings=settings,
            target=SaveTarget(base_path=self.frame_dir / "demo_capture_export", figures={}),
        )
        receipt = build_export_receipt(
            artifacts=artifacts,
            settings=settings,
            result=self.app.controller._ui_handler.latest_result,
            source_text=self.vm.data_source_text.get(),
            fixture_badge_text=self.vm.fixture_badge_text.get(),
        )
        artifact_names = " · ".join(path.name for path in receipt.artifacts)
        self.vm.export_receipt_text.set(f"Export verified · {artifact_names}\nTemporary capture output · no hardware")
        self.vm.status_text.set("Fixture replay complete; export verified (no hardware)")

    def _finish(self) -> None:
        _capture_window(self.window_id, POSTER)
        _write_video(self.frame_dir)
        print(f"poster: {POSTER.relative_to(ROOT)}")
        print(f"video: {VIDEO.relative_to(ROOT)}")
        print(f"point_count: {self.vm.point_count_text.get()}")
        print(f"source: {self.vm.data_source_text.get()}")
        print(f"badge: {self.vm.fixture_badge_text.get()}")
        print(f"validation: {self.vm.validation_receipt_text.get()}")
        print(f"window: {self.window.winfo_geometry()}")
        self.window.destroy()


def _write_video(frame_dir: Path) -> None:
    subprocess.run(
        [
            _ffmpeg_executable(),
            "-y",
            "-framerate",
            str(FRAME_RATE),
            "-i",
            str(frame_dir / "frame_%04d.png"),
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(VIDEO),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _require_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Required file not found: {path}")


def _format_frequency(freq_hz: float) -> str:
    if abs(freq_hz) >= 1_000_000:
        return f"{freq_hz / 1_000_000:.3g} MHz"
    if abs(freq_hz) >= 1_000:
        return f"{freq_hz / 1_000:.3g} kHz"
    return f"{freq_hz:.3g} Hz"


if __name__ == "__main__":
    main()
