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
POSTER = OUT_DIR / "auto-load-off-test-point-replay-demo.png"
VIDEO = OUT_DIR / "auto-load-off-test-point-replay-demo.mp4"
FRAME_RATE = 12
DEMO_SIZE = "1366x768+40+60"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.bootstrap import build_desktop_app  # noqa: E402
from app.domain.models import SweepResult  # noqa: E402
from app.runtime.paths import AppPaths  # noqa: E402

from capture_operator_console_demo import (  # noqa: E402
    _capture_window,
    _find_window_id,
    _raise_window,
    _require_tools,
)


def main() -> None:
    _require_tools()
    _require_file(FIXTURE)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    app = build_desktop_app(paths=AppPaths.from_root(ROOT))
    app.window.geometry(DEMO_SIZE)
    app.window.update()
    window_id = _find_window_id(app.window.title())
    print(f"window_id: {window_id}")

    loaded = app.controller.load_measurement_use_case.execute(str(FIXTURE))
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
        self._capture_frames(12, self._press_demo_button)

    def _press_demo_button(self) -> None:
        self.window.run_panel.btn_load_demo_fixture.configure(relief="sunken")
        self._capture_frames(4, self._start_replay)

    def _start_replay(self) -> None:
        self.window.run_panel.btn_load_demo_fixture.configure(relief="flat")
        self.replay_index = 0
        self._set_replay_state(0)
        self._capture_replay_step()

    def _capture_replay_step(self) -> None:
        if self.replay_index >= self.total_points:
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
        self.app.controller._ui_handler.set_result(SweepResult(), refresh_plot=True)
        self.vm.data_source_text.set("Live instrument path")
        self.vm.fixture_badge_text.set("")
        self.vm.validation_receipt_text.set("Live run requires operator hardware checks")
        self.vm.export_receipt_text.set("No export yet")
        self.vm.run_state_text.set("Idle")
        self.vm.progress_text.set("0 / 0")
        self.vm.point_count_text.set("0 points")
        self.vm.latest_frequency_text.set("-")
        self.vm.status_text.set("Ready")

    def _set_replay_state(self, point_count: int) -> None:
        partial = SweepResult(
            points=list(self.full_result.points[:point_count]),
            meta=dict(self.full_result.meta),
        )
        self.app.controller._ui_handler.set_result(partial, refresh_plot=True)
        self.vm.data_source_text.set(f"Fixture replay · {FIXTURE.name}")
        self.vm.fixture_badge_text.set("No hardware - simulated fixture")
        self.vm.validation_receipt_text.set(
            "Point-by-point simulated fixture replay; not live hardware validation"
        )
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
            "ffmpeg",
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
