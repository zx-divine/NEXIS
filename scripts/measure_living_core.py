"""Equivalent native-widget benchmark. Synthetic states, no audio capture or playback."""
import argparse
import importlib.util
import json
from pathlib import Path
import platform
import site
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
site.addsitedir(str(ROOT / ".dev-deps"))
sys.path.insert(0, str(ROOT / "src"))
from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from nexis.platform.system import process_working_set_mb  # noqa: E402
from nexis.ui.themes import apply  # noqa: E402


def wait(milliseconds):
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.baseline:
        spec = importlib.util.spec_from_file_location("baseline_reactor", args.baseline)
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
    else:
        import nexis.ui.reactor as renderer
    app = QApplication([])
    apply("og")
    class MeasuredCore(renderer.ReactorWidget):
        def __init__(self):
            super().__init__()
            self.frame_times = []

        def paintEvent(self, event):
            self.frame_times.append(time.perf_counter())
            super().paintEvent(event)

    widget = MeasuredCore()
    widget.resize(450, 450)
    widget.show()
    wait(300)
    results = []
    for state in ("IDLE", "PROCESSING", "SPEAKING", "MINIMIZED", "REDUCED"):
        widget.showNormal()
        widget.set_reduced_motion(state == "REDUCED")
        widget.set_state(state if state not in {"MINIMIZED", "REDUCED"} else "IDLE")
        if state == "MINIMIZED":
            widget.set_paused(True)
            widget.showMinimized()
        else:
            widget.set_paused(False)
        wait(400)
        samples = []
        timer = QTimer()
        timer.setInterval(20)
        timer.timeout.connect(lambda: samples.append(time.perf_counter()))
        timer.start()
        paints, painting = widget.paint_count, widget.paint_seconds
        frame_start = len(widget.frame_times)
        started, cpu = time.perf_counter(), time.process_time()
        wait(3000)
        elapsed, used = time.perf_counter() - started, time.process_time() - cpu
        timer.stop()
        gaps = sorted((b - a) * 1000 for a, b in zip(samples, samples[1:]))
        frames = widget.paint_count - paints
        measured_frames = widget.frame_times[frame_start:]
        frame_gaps = sorted((b - a) * 1000 for a, b in zip(measured_frames, measured_frames[1:]))
        results.append({"state": state, "seconds": round(elapsed, 3),
            "cpu_percent_one_core": round(used / elapsed * 100, 2),
            "working_set_mb": process_working_set_mb(),
            "paints_per_second": round(frames / elapsed, 2),
            "mean_paint_ms": round((widget.paint_seconds - painting) * 1000 / max(frames, 1), 3),
            "event_loop_gap_p95_ms": round(gaps[int(.95 * (len(gaps) - 1))], 3) if gaps else None,
            "timer_active": widget.timer.isActive()})
        results[-1]["frame_gap_p95_ms"] = round(frame_gaps[int(.95 * (len(frame_gaps) - 1))], 3) if frame_gaps else None
    widget.set_reduced_motion(False)
    widget.set_paused(False)
    widget.showNormal()
    started = time.perf_counter()
    for size in range(220, 601, 20):
        widget.resize(size, size)
        app.processEvents()
    resize_ms = (time.perf_counter() - started) * 1000 / 20
    widget.close()
    report = {"renderer": "previous reactor" if args.baseline else "living particle core",
        "platform": platform.platform(), "qt_platform": app.platformName(),
        "viewport": [450, 450], "device_pixel_ratio": widget.devicePixelRatioF(),
        "stimulus": "Synthetic application states; SPEAKING has no amplitude input",
        "limits": "Current host, single widget. Event-loop gap is a responsiveness proxy, not measured human input latency. Hardware identity is recorded separately. Full AI/audio workload unqualified.",
        "mean_resize_event_ms": round(resize_ms, 3), "states": results}
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
