from __future__ import annotations

import os
import sys
from pathlib import Path

# Force offscreen rendering for headless capture
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from aidub.ui.dub_dialog import DubbingErrorDialog
from aidub.ui.studio_window import AIDubStudioWindow


def capture_all() -> None:
    print("Initializing QApplication...", flush=True)
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    out_dir = Path("docs/handoff/screens")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Instantiating AIDubStudioWindow...", flush=True)
    window = AIDubStudioWindow()
    window.resize(1600, 960)
    window.show()
    window.show_studio()
    app.processEvents()

    # 1. Idle state
    print("Capturing idle.png...", flush=True)
    pix_idle = window.grab()
    idle_path = out_dir / "idle.png"
    pix_idle.save(str(idle_path), "PNG")
    print(f"Saved: {idle_path} ({idle_path.stat().st_size} bytes)", flush=True)

    # 2. Running state
    print("Capturing running.png...", flush=True)
    window.update_dub_progress("ASR", 35, "Transcribing dialogue with Whisper (Large-v3)...")
    window.studio.ai_overlay.set_progress("[ASR] Transcribing dialogue with Whisper (Large-v3)...", 35)
    window.studio._show_status("Stage: ASR (35%) · Transcribing dialogue with Whisper (Large-v3)...")
    app.processEvents()

    pix_running = window.grab()
    running_path = out_dir / "running.png"
    pix_running.save(str(running_path), "PNG")
    print(f"Saved: {running_path} ({running_path.stat().st_size} bytes)", flush=True)

    # 3. Finished state
    print("Capturing finished.png...", flush=True)
    pixmap = QPixmap(640, 360)
    pixmap.fill(QColor("#080D1A"))
    p = QPainter(pixmap)
    p.setPen(QColor("#38BDF8"))
    font = p.font()
    font.setPointSize(15)
    font.setBold(True)
    p.setFont(font)
    p.drawText(
        pixmap.rect(),
        Qt.AlignmentFlag.AlignCenter,
        "🎬 Inception (বাংলা ডাবিং)\nBengali Dubbed Master · 1080p · High Quality Audio",
    )
    p.end()

    window.studio.monitor_panel._video_widget.setPixmap(pixmap)
    window.studio.monitor_panel.media_stack.setCurrentWidget(
        window.studio.monitor_panel._video_widget
    )
    window.studio.monitor_panel.prog_title_lbl.setText("Program: Inception (Bengali Dubbed)")
    window.studio.monitor_panel.source_lbl.setText("Source: inception_bangla_dubbed.mp4")
    window.studio.monitor_panel.dur_overlay.setText("00:02:30:000")

    window.set_dub_completed(True, "Dubbing completed successfully.")
    window.studio.ai_overlay.set_complete("Bengali Dubbing Complete (Quality Profile)")
    window.studio.stage_bar._buttons["Review"].setChecked(True)
    window.studio.stage_bar._buttons["Dubbing"].setChecked(False)
    app.processEvents()

    pix_finished = window.grab()
    finished_path = out_dir / "finished.png"
    pix_finished.save(str(finished_path), "PNG")
    print(f"Saved: {finished_path} ({finished_path.stat().st_size} bytes)", flush=True)

    # 4. Error state
    print("Capturing error.png...", flush=True)
    error_dialog = DubbingErrorDialog(
        window,
        title="Dubbing Pipeline Failed",
        message="TTS synthesis worker encountered CUDA Out of Memory (OOM) on batch generation.",
        details=(
            "Traceback (most recent call last):\n"
            "  File 'aidub/pipeline/engine.py', line 352, in run\n"
            "    audio_segments = tts_adapter.synthesize_batch(translated_cues, voice='bn_female_1')\n"
            "  File 'aidub/adapters/voice/chatterbox_adapter.py', line 118, in synthesize_batch\n"
            "    return model.generate(**inputs)\n"
            "  File 'torch/utils/_contextlib.py', line 115, in decorate_context\n"
            "    return func(*args, **kwargs)\n"
            "torch.cuda.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.40 GiB "
            "(GPU 0; 8.00 GiB total capacity; 6.85 GiB already allocated; 480.00 MiB free)"
        ),
    )
    error_dialog.resize(580, 420)
    error_dialog.show()
    app.processEvents()

    # Composite modal dialog over dimmed window
    pix_base = window.grab()
    pix_dlg = error_dialog.grab()

    painter = QPainter(pix_base)
    # Dim overlay
    painter.fillRect(pix_base.rect(), QColor(0, 0, 0, 140))
    # Draw centered dialog
    dx = (pix_base.width() - pix_dlg.width()) // 2
    dy = (pix_base.height() - pix_dlg.height()) // 2
    painter.drawPixmap(dx, dy, pix_dlg)
    painter.end()

    error_path = out_dir / "error.png"
    pix_base.save(str(error_path), "PNG")
    print(f"Saved: {error_path} ({error_path.stat().st_size} bytes)", flush=True)

    error_dialog.close()
    window.close()
    app.processEvents()
    print("All screenshots successfully captured!", flush=True)
    os._exit(0)


if __name__ == "__main__":
    capture_all()
