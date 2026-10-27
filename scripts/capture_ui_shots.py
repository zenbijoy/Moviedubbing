"""Offscreen screenshot capture harness for AI Dubbing Studio."""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication

from aidub.ui.application import DesktopApplication


def pump_events(app: QApplication, count: int = 15) -> None:
    for _ in range(count):
        app.processEvents()


def capture_all(output_dir: str = "docs/ui/shots/before") -> None:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    resolutions = [
        (1280, 800),
        (1600, 960),
        (1920, 1080),
    ]

    themes = [
        "studio_dark",
        "broadcast_gray",
        "cyber_dark",
        "high_contrast",
        "light_studio",
    ]

    locales = ["en", "bn-BD"]

    for loc in locales:
        print(f"Creating application for locale {loc}...")
        desktop = DesktopApplication([], locale=loc)
        app = desktop.application
        win = desktop.window
        win.show()
        pump_events(app, 10)

        for theme_name in themes:
            print(f"  Rendering theme: {theme_name}")
            win._set_theme(theme_name)
            pump_events(app, 8)

            for w, h in resolutions:
                win.resize(w, h)
                pump_events(app, 8)

                # 1. Home View
                win.show_home()
                pump_events(app, 8)
                home_file = out_path / f"home_{loc}_{theme_name}_{w}x{h}.png"
                pix_home = win.grab()
                pix_home.save(str(home_file))

                # 2. Studio View
                win.show_studio()
                pump_events(app, 8)
                studio_file = out_path / f"studio_{loc}_{theme_name}_{w}x{h}.png"
                pix_studio = win.grab()
                pix_studio.save(str(studio_file))

        if hasattr(win, "_telemetry_worker") and win._telemetry_worker.isRunning():
            win._telemetry_worker.wait(1500)
        win.close()
        pump_events(app, 5)

    print(f"Captured all screenshots successfully to {out_path.resolve()}")
    os._exit(0)


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "docs/ui/shots/before"
    capture_all(out_dir)
