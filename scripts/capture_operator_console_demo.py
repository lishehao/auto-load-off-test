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
    _raise_window(app.window)
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
        self.window.after(500, lambda: self._capture_frames(14, self._press_demo_button))

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
    if shutil.which("screencapture") is None:
        raise RuntimeError("Missing capture tool: screencapture")
    _ffmpeg_executable()


def _raise_window(window) -> None:
    try:
        from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication

        current_app = NSRunningApplication.runningApplicationWithProcessIdentifier_(os.getpid())
        current_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
    except Exception:
        pass
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
    window.attributes("-topmost", False)
    window.update()


def _find_window_id(title: str) -> int:
    quartz_window_id = _find_window_id_with_quartz(title)
    if quartz_window_id is not None:
        return quartz_window_id

    script = _window_list_script_path()
    last_stdout = ""
    last_stderr = ""
    for _attempt in range(12):
        try:
            result = subprocess.run(
                ["swift", str(script), title],
                check=False,
                text=True,
                capture_output=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Precise window capture requires Quartz or the Swift CLI") from exc
        last_stdout = result.stdout
        last_stderr = result.stderr
        if "xcode license" in result.stderr.lower():
            raise RuntimeError(
                "Precise window capture requires the optional capture dependencies when Swift is unavailable. "
                "Install with: python -m pip install -e '.[capture]'"
            )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                return int(line)
        time.sleep(0.25)
    raise RuntimeError(
        f"Could not find Tk window id for title: {title}; "
        f"stdout={last_stdout!r}; stderr={last_stderr!r}"
    )


def _find_window_id_with_quartz(title: str) -> int | None:
    try:
        import Quartz
    except ImportError:
        return None

    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionAll,
        Quartz.kCGNullWindowID,
    )
    for info in windows:
        if int(info.get(Quartz.kCGWindowOwnerPID, -1)) != os.getpid():
            continue
        name = str(info.get(Quartz.kCGWindowName, ""))
        bounds = info.get(Quartz.kCGWindowBounds, {})
        width = float(bounds.get("Width", 0))
        height = float(bounds.get("Height", 0))
        if (name == title or "Auto-Load-off-Test" in name) and width > 0 and height > 0:
            return int(info[Quartz.kCGWindowNumber])
    return None


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


def _capture_window(window_id: int, output_path: Path) -> None:
    for _attempt in range(3):
        output_path.unlink(missing_ok=True)
        if _capture_window_with_quartz(window_id, output_path):
            _flatten_capture(output_path)
            if _capture_has_full_frame(output_path):
                return

        command = ["screencapture", "-x", "-o", "-l", str(window_id), str(output_path)]
        result = subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            _flatten_capture(output_path)
            if _capture_has_full_frame(output_path):
                return
        time.sleep(0.05)
    raise RuntimeError(f"Could not capture verified Tk window id {window_id}")


def _capture_window_with_quartz(window_id: int, output_path: Path) -> bool:
    try:
        import Quartz
        from Foundation import NSURL
    except ImportError:
        return False

    image = Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull,
        Quartz.kCGWindowListOptionIncludingWindow,
        window_id,
        Quartz.kCGWindowImageBoundsIgnoreFraming,
    )
    if image is None:
        return False
    destination = Quartz.CGImageDestinationCreateWithURL(
        NSURL.fileURLWithPath_(str(output_path)),
        "public.png",
        1,
        None,
    )
    if destination is None:
        return False
    Quartz.CGImageDestinationAddImage(destination, image, None)
    return bool(Quartz.CGImageDestinationFinalize(destination))


def _flatten_capture(output_path: Path) -> None:
    from PIL import Image

    with Image.open(output_path) as source:
        rgba = source.convert("RGBA")
        opaque = Image.new("RGB", rgba.size, "white")
        opaque.paste(rgba, mask=rgba.getchannel("A"))
        opaque.save(output_path)


def _capture_has_full_frame(output_path: Path) -> bool:
    from PIL import Image

    with Image.open(output_path) as source:
        sample = source.convert("RGB")
        sample.thumbnail((180, 120))
        pixels = list(sample.getdata())
    near_black = sum(1 for red, green, blue in pixels if max(red, green, blue) < 12)
    return bool(pixels) and near_black / len(pixels) < 0.12


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


def _ffmpeg_executable() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg is not None:
        probe = subprocess.run(
            [system_ffmpeg, "-version"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode == 0:
            return system_ffmpeg
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError(
            "No working ffmpeg executable found. Install capture dependencies with: "
            "python -m pip install -e '.[capture]'"
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


if __name__ == "__main__":
    main()
