from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OUT_DIR = ROOT / "docs" / "images"
POSTER = OUT_DIR / "auto-load-off-test-demo-capture.png"
VIDEO = OUT_DIR / "auto-load-off-test-demo-capture.mp4"
FRAME_RATE = 12

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.bootstrap import build_desktop_app  # noqa: E402
from app.runtime.paths import AppPaths  # noqa: E402


def main() -> None:
    _require_tools()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    app = build_desktop_app(paths=AppPaths.from_root(ROOT))
    app.window.geometry("1366x768+40+60")
    app.window.update()
    window_id = _find_window_id(app.window.title())
    print(f"window_id: {window_id}")
    with tempfile.TemporaryDirectory(prefix="auto-load-off-test-capture-") as td:
        session = CaptureSession(app=app, frame_dir=Path(td), window_id=window_id)
        session.run()


class CaptureSession:
    def __init__(self, *, app, frame_dir: Path, window_id: int) -> None:
        self.app = app
        self.window = app.window
        self.frame_dir = frame_dir
        self.frame_index = 1
        self.window_id = window_id

    def run(self) -> None:
        self.window.run_panel.btn_load_demo_fixture.configure(command=self.app.controller.on_load_demo_fixture)
        self.window.plot_widget.set_mode(self.window.vm.figure_mode.get())
        self.app.controller.on_mag_phase_change()
        self.window.after(1200, self._start)
        self.window.mainloop()

    def _start(self) -> None:
        _raise_window(self.window)
        self._capture_frames(14, self._press_demo_button)

    def _press_demo_button(self) -> None:
        self.window.run_panel.btn_load_demo_fixture.configure(relief="sunken")
        self._capture_frames(4, self._load_fixture)

    def _load_fixture(self) -> None:
        self.window.run_panel.btn_load_demo_fixture.configure(relief="flat")
        self.app.controller.on_load_demo_fixture()
        _raise_window(self.window)
        self._capture_frames(29, self._finish)

    def _capture_frames(self, remaining: int, done: Callable[[], None]) -> None:
        if remaining <= 0:
            done()
            return
        _capture_window(self.window_id, self.frame_dir / f"frame_{self.frame_index:04d}.png")
        self.frame_index += 1
        self.window.after(int(1000 / FRAME_RATE), lambda: self._capture_frames(remaining - 1, done))

    def _finish(self) -> None:
        _capture_window(self.window_id, POSTER)
        _write_video(self.frame_dir)

        print(f"poster: {POSTER.relative_to(ROOT)}")
        print(f"video: {VIDEO.relative_to(ROOT)}")
        print(f"point_count: {self.window.vm.point_count_text.get()}")
        print(f"source: {self.window.vm.data_source_text.get()}")
        print(f"badge: {self.window.vm.fixture_badge_text.get()}")
        print(f"validation: {self.window.vm.validation_receipt_text.get()}")
        print(f"window: {self.window.winfo_geometry()}")
        self.window.destroy()


def _require_tools() -> None:
    missing = [tool for tool in ("screencapture", "ffmpeg") if shutil.which(tool) is None]
    if missing:
        raise RuntimeError(f"Missing capture tool(s): {', '.join(missing)}")


def _raise_window(window) -> None:
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application "System Events" to set frontmost of first application process whose unix id is {os.getpid()} to true',
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
    window.lift()
    window.focus_force()
    window.attributes("-topmost", True)
    window.update()
    time.sleep(0.2)
    window.update()


def _find_window_id(title: str) -> int:
    script = _window_list_script_path()
    last_stdout = ""
    last_stderr = ""
    for _attempt in range(12):
        result = subprocess.run(
            ["swift", str(script), title],
            check=False,
            text=True,
            capture_output=True,
        )
        last_stdout = result.stdout
        last_stderr = result.stderr
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                return int(line)
        time.sleep(0.25)
    raise RuntimeError(
        f"Could not find Tk window id for title: {title}; "
        f"stdout={last_stdout!r}; stderr={last_stderr!r}"
    )


def _window_list_script_path() -> Path:
    script = Path(tempfile.gettempdir()) / "auto_load_off_test_window_id.swift"
    script.write_text(
        """
import CoreGraphics
import Darwin

let targetTitle = CommandLine.arguments.dropFirst().joined(separator: " ")
let options = CGWindowListOption(arrayLiteral: .optionAll)
var fallbackWindow: Int?
if let windows = CGWindowListCopyWindowInfo(options, CGWindowID(0)) as? [[String: Any]] {
    for window in windows {
        let owner = window[kCGWindowOwnerName as String] as? String ?? ""
        let name = window[kCGWindowName as String] as? String ?? ""
        let number = window[kCGWindowNumber as String] as? Int ?? 0
        let layer = window[kCGWindowLayer as String] as? Int ?? 0
        let isPython = owner.lowercased().contains("python")
        if isPython && name == targetTitle && layer == 0 {
            print(number)
            exit(0)
        }
        if isPython && name.contains("Auto-Load-off-Test") && layer == 0 {
            print(number)
            exit(0)
        }
        if isPython && layer == 0 && fallbackWindow == nil {
            fallbackWindow = number
        }
    }
}
if let fallback = fallbackWindow {
    print(fallback)
    exit(0)
}
exit(1)
""".strip()
    )
    return script


def _capture_window(window_id: int | None, output_path: Path) -> None:
    if window_id is None:
        raise RuntimeError("Capture window id is not set")
    subprocess.run(
        ["screencapture", "-x", "-l", str(window_id), str(output_path)],
        check=True,
    )


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


if __name__ == "__main__":
    main()
