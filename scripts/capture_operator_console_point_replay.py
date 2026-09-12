from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "images" / "desktop-workflow-replay"
FIXTURE = ROOT / "demo_data" / "hyperframe_simulated_fixture.mat"
REFERENCE = ROOT / "demo_data" / "hyperframe_reference_fixture.mat"
FRAME_RATE = 12
DEMO_SIZE = "1440x810+20+40"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.bootstrap import build_desktop_app  # noqa: E402
from app.demo.hyperframe_fixture import build_fixture_settings  # noqa: E402
from app.presentation.tk.mapper import settings_to_vm  # noqa: E402
from app.runtime.paths import AppPaths  # noqa: E402

from capture_operator_console_demo import (  # noqa: E402
    _capture_window,
    _ffmpeg_executable,
    _find_window_id,
    _raise_window,
    _require_tools,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Capture a real Tk controller-driven fixture replay")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory for the new desktop-workflow-replay MP4/poster",
    )
    args = parser.parse_args(argv)
    _require_tools()
    _require_file(FIXTURE)
    _require_file(REFERENCE)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    poster = output_dir / "auto-load-off-test-desktop-workflow-replay.png"
    video = output_dir / "auto-load-off-test-desktop-workflow-replay.mp4"

    with tempfile.TemporaryDirectory(prefix="auto-load-off-test-runtime-") as runtime_dir:
        runtime_root = Path(runtime_dir)
        demo_dir = runtime_root / "demo_data"
        demo_dir.mkdir()
        shutil.copy2(FIXTURE, demo_dir / FIXTURE.name)
        shutil.copy2(REFERENCE, demo_dir / REFERENCE.name)
        app = build_desktop_app(paths=AppPaths.from_root(runtime_root))
        app.controller.initialize()
        fixture_settings = build_fixture_settings()
        fixture_settings.freq_unit = "KHz"
        settings_to_vm(fixture_settings, app.window.vm)
        app.window.geometry(DEMO_SIZE)
        app.window.update()
        _raise_window(app.window)
        window_id = _find_window_id(app.window.title())
        print(f"window_id: {window_id}")
        with tempfile.TemporaryDirectory(prefix="auto-load-off-test-frames-") as frame_dir:
            session = ControllerReplayCaptureSession(
                app=app,
                frame_dir=Path(frame_dir),
                window_id=window_id,
                poster=poster,
                video=video,
            )
            session.run()


class ControllerReplayCaptureSession:
    def __init__(self, *, app, frame_dir: Path, window_id: int, poster: Path, video: Path) -> None:
        self.app = app
        self.window = app.window
        self.vm = app.window.vm
        self.frame_dir = frame_dir
        self.window_id = window_id
        self.poster = poster
        self.video = video
        self.frame_index = 1
        self._started_replay = False
        self._final_frames = 0

    def run(self) -> None:
        self._set_initial_state()
        self.window.after(1000, self._capture_initial)
        self.window.mainloop()

    def _set_initial_state(self) -> None:
        # This is an honest source receipt before data is loaded, not a fabricated
        # measurement. The controller still owns every data transition below.
        self.vm.source_mode.set("fixture")
        self.vm.data_source_text.set("Fixture replay ready · hyperframe_simulated_fixture.mat")
        self.vm.fixture_badge_text.set("No hardware - simulated fixture")
        self.vm.validation_receipt_text.set("Ready for simulated fixture replay; not live hardware validation")
        self.vm.status_text.set("Ready to load simulated fixture (no hardware)")
        self.vm.run_state_text.set("Ready")
        self.vm.point_count_text.set("0 points")
        self.vm.progress_text.set("0 / 0")
        self.vm.latest_frequency_text.set("-")
        self.vm.elapsed_text.set("00:00")
        self.window.set_connection_idle()

    def _capture_initial(self) -> None:
        _raise_window(self.window)
        self._capture_frames(12, self._press_load_demo)

    def _press_load_demo(self) -> None:
        self.window.run_panel.btn_load_demo_fixture.invoke()
        self._wait_for_loaded_fixture()

    def _wait_for_loaded_fixture(self) -> None:
        state = self.vm.operation_mode.get()
        replay_state = self.window.run_panel.btn_replay_fixture.cget("state")
        if state in {"loading", "analyzing", "exporting"} or replay_state == "disabled":
            self.window.after(100, self._wait_for_loaded_fixture)
            return
        self._capture_frames(8, self._press_replay)

    def _press_replay(self) -> None:
        self.window.run_panel.btn_replay_fixture.invoke()
        self._started_replay = True
        self.window.after(100, self._capture_replay_frame)

    def _capture_replay_frame(self) -> None:
        _capture_window(self.window_id, self.frame_dir / f"frame_{self.frame_index:04d}.png")
        self.frame_index += 1
        if self._replay_finished():
            self._final_frames += 1
            if self._final_frames >= 24:
                self._finish()
            else:
                self.window.after(int(1000 / FRAME_RATE), self._capture_replay_frame)
            return
        self.window.after(int(1000 / FRAME_RATE), self._capture_replay_frame)

    def _replay_finished(self) -> bool:
        progress = self.vm.progress_text.get()
        return self._started_replay and self.vm.operation_mode.get() == "idle" and progress.startswith("72 / 72")

    def _capture_frames(self, remaining: int, done) -> None:
        if remaining <= 0:
            done()
            return
        _capture_window(self.window_id, self.frame_dir / f"frame_{self.frame_index:04d}.png")
        self.frame_index += 1
        self.window.after(int(1000 / FRAME_RATE), lambda: self._capture_frames(remaining - 1, done))

    def _finish(self) -> None:
        if self.vm.fixture_badge_text.get() != "No hardware - simulated fixture":
            raise RuntimeError("Capture lost the no-hardware simulated-fixture label")
        if "72" not in self.vm.point_count_text.get():
            raise RuntimeError(f"Capture did not finish 72-point replay: {self.vm.point_count_text.get()}")
        _capture_window(self.window_id, self.poster)
        _write_video(self.frame_dir, self.video)
        print(f"poster: {self.poster}")
        print(f"video: {self.video}")
        print(f"point_count: {self.vm.point_count_text.get()}")
        print(f"source: {self.vm.data_source_text.get()}")
        print(f"badge: {self.vm.fixture_badge_text.get()}")
        print(f"validation: {self.vm.validation_receipt_text.get()}")
        print(f"window: {self.window.winfo_geometry()}")
        self.app.controller.on_close()


def _write_video(frame_dir: Path, output_path: Path) -> None:
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
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _require_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Required file not found: {path}")


if __name__ == "__main__":
    main()
