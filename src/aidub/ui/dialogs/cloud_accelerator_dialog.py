"""
Cloud GPU Accelerator Dialog for AIDub Studio (Kaggle & Google Colab).

Allows users to offload heavy movie dubbing workloads (Demucs stem separation,
Whisper Large-v3, Chatterbox AI, and MuseTalk/LatentSync lip-sync) to free
cloud GPUs:
- Kaggle NVIDIA T4 / P100 GPUs (30 hours/week)
- Google Colab NVIDIA Tesla T4 Free GPU with 1-Click Google Drive integration
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aidub.cloud.colab_accelerator import ColabNotebookBuilder
from aidub.cloud.kaggle_accelerator import (
    KaggleNotebookBuilder,
    load_kaggle_credentials,
    save_kaggle_credentials,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QDesktopServices, QFont
    from PySide6.QtWidgets import (
        QDialog,
        QFileDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False


if _QT:

    class KaggleAcceleratorDialog(QDialog):
        """Dialog to configure and launch Kaggle GPU acceleration for movie dubbing."""

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            movie_path: str = "",
            target_language: str = "bn",
            voice_engine: str = "chatterbox",
            enable_lipsync: bool = True,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("Kaggle Cloud GPU Accelerator — Free 30h/week NVIDIA T4/P100")
            self.setMinimumSize(580, 480)
            self.movie_path = movie_path
            self.target_language = target_language
            self.voice_engine = voice_engine
            self.enable_lipsync = enable_lipsync

            self.setStyleSheet(
                "QDialog { background: #0B0E14; color: #E2E8F0; }"
                "QLabel { color: #E2E8F0; }"
                "QLineEdit {"
                "  background: #111622; color: #F8FAFC; border: 1px solid #1E293B;"
                "  border-radius: 4px; padding: 7px 10px; font-size: 12px;"
                "}"
                "QLineEdit:focus { border-color: #38BDF8; }"
            )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 20, 24, 20)
            layout.setSpacing(16)

            # Header Banner
            hdr_layout = QHBoxLayout()
            icon_lbl = QLabel("☁️", self)
            icon_lbl.setStyleSheet("font-size: 28px;")
            hdr_layout.addWidget(icon_lbl)

            hdr_text = QVBoxLayout()
            title = QLabel("Kaggle Cloud GPU Accelerator", self)
            title.setStyleSheet("font-size: 16px; font-weight: 800; color: #38BDF8;")
            subtitle = QLabel(
                "Execute Demucs, Whisper Large-v3, and Lip-Sync on free NVIDIA Tesla T4 GPUs.",
                self,
            )
            subtitle.setStyleSheet("font-size: 11px; color: #94A3B8;")
            hdr_text.addWidget(title)
            hdr_text.addWidget(subtitle)
            hdr_layout.addLayout(hdr_text)
            hdr_layout.addStretch()
            layout.addLayout(hdr_layout)

            # Project Summary Frame
            info_frame = QFrame(self)
            info_frame.setStyleSheet(
                "QFrame { background: #0F172A; border: 1px solid #1E293B; border-radius: 6px; padding: 10px; }"
            )
            info_lay = QVBoxLayout(info_frame)
            info_lay.setSpacing(4)
            m_name = Path(self.movie_path).name if self.movie_path else "Current Loaded Movie"
            info_lay.addWidget(QLabel(f"<b>Target Movie:</b> {m_name}"))
            info_lay.addWidget(QLabel(f"<b>Language:</b> {self.target_language} (Bengali / বাংলা)"))
            info_lay.addWidget(QLabel(f"<b>Voice Model:</b> {self.voice_engine.upper()}"))
            info_lay.addWidget(
                QLabel(f"<b>Lip-Sync:</b> {'Active (GPU Accelerated)' if self.enable_lipsync else 'Disabled'}")
            )
            layout.addWidget(info_frame)

            # Credentials Box
            cred_box = QGroupBox("Kaggle API Credentials (Optional for Direct Sync)", self)
            cred_box.setStyleSheet(
                "QGroupBox { font-size: 12px; font-weight: 700; color: #94A3B8; border: 1px solid #1E293B; "
                "border-radius: 6px; margin-top: 10px; padding-top: 15px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
            )
            cred_lay = QVBoxLayout(cred_box)
            cred_lay.setSpacing(8)

            from aidub.cloud.kaggle_accelerator import load_kaggle_credentials

            saved = load_kaggle_credentials()
            u_init = saved.username if saved else ""
            k_init = saved.key if saved else ""

            u_row = QHBoxLayout()
            u_row.addWidget(QLabel("Username:", self), 0)
            self.u_edit = QLineEdit(u_init, self)
            self.u_edit.setPlaceholderText("your-kaggle-username")
            u_row.addWidget(self.u_edit, 1)
            cred_lay.addLayout(u_row)

            k_row = QHBoxLayout()
            k_row.addWidget(QLabel("API Key:   ", self), 0)
            self.k_edit = QLineEdit(k_init, self)
            self.k_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.k_edit.setPlaceholderText("kaggle-api-key-token")
            k_row.addWidget(self.k_edit, 1)
            cred_lay.addLayout(k_row)

            save_btn = QPushButton("Save Kaggle Credentials", self)
            save_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #38BDF8; border: 1px solid #334155; "
                "border-radius: 4px; padding: 6px 12px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #334155; }"
            )
            save_btn.clicked.connect(self._save_creds)
            cred_lay.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)
            layout.addWidget(cred_box)

            # Action Buttons
            btn_box = QVBoxLayout()
            btn_box.setSpacing(10)

            # Kaggle Actions
            kaggle_row = QHBoxLayout()
            self.gen_btn = QPushButton("🚀  Generate Kaggle Notebook (.ipynb)", self)
            self.gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.gen_btn.setStyleSheet(
                "QPushButton { background: #2563EB; color: #FFF; border: none; "
                "border-radius: 5px; padding: 10px 14px; font-size: 12px; font-weight: 800; }"
                "QPushButton:hover { background: #3B82F6; }"
            )
            self.gen_btn.clicked.connect(self._generate_notebook)
            kaggle_row.addWidget(self.gen_btn, 1)

            open_kaggle_btn = QPushButton("🌐 Open Kaggle", self)
            open_kaggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_kaggle_btn.setStyleSheet(
                "QPushButton { background: #0284C7; color: #FFF; border: none; "
                "border-radius: 5px; padding: 10px 14px; font-size: 12px; font-weight: 700; }"
                "QPushButton:hover { background: #0EA5E9; }"
            )
            open_kaggle_btn.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl("https://www.kaggle.com/code"))
            )
            kaggle_row.addWidget(open_kaggle_btn)
            btn_box.addLayout(kaggle_row)

            # Google Colab Actions
            colab_row = QHBoxLayout()
            self.colab_btn = QPushButton("⚡  Generate Google Colab Notebook (.ipynb)", self)
            self.colab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.colab_btn.setStyleSheet(
                "QPushButton { background: #D97706; color: #FFF; border: none; "
                "border-radius: 5px; padding: 10px 14px; font-size: 12px; font-weight: 800; }"
                "QPushButton:hover { background: #F59E0B; }"
            )
            self.colab_btn.clicked.connect(self._generate_colab_notebook)
            colab_row.addWidget(self.colab_btn, 1)

            open_colab_btn = QPushButton("🌐 Open Colab", self)
            open_colab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_colab_btn.setStyleSheet(
                "QPushButton { background: #B45309; color: #FFF; border: none; "
                "border-radius: 5px; padding: 10px 14px; font-size: 12px; font-weight: 700; }"
                "QPushButton:hover { background: #D97706; }"
            )
            open_colab_btn.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl("https://colab.research.google.com/"))
            )
            colab_row.addWidget(open_colab_btn)
            btn_box.addLayout(colab_row)

            layout.addLayout(btn_box)

            # Bottom Close Button
            close_row = QHBoxLayout()
            close_row.addStretch()
            close_btn = QPushButton("Close", self)
            close_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #94A3B8; border: 1px solid #1E293B; "
                "border-radius: 4px; padding: 6px 16px; font-weight: 600; }"
                "QPushButton:hover { color: #FFF; background: #1E293B; }"
            )
            close_btn.clicked.connect(self.accept)
            close_row.addWidget(close_btn)
            layout.addLayout(close_row)

        def _save_creds(self) -> None:
            user = self.u_edit.text().strip()
            key = self.k_edit.text().strip()
            if not user or not key:
                QMessageBox.warning(self, "Invalid Credentials", "Please enter both Kaggle Username and API Key.")
                return
            from aidub.cloud.kaggle_accelerator import save_kaggle_credentials

            save_kaggle_credentials(user, key)
            QMessageBox.information(
                self,
                "Credentials Saved",
                "✓ Kaggle credentials successfully saved to ~/.kaggle/kaggle.json and active in environment.",
            )

        def _generate_notebook(self) -> None:
            default_name = f"dubbing_gpu_{Path(self.movie_path).stem if self.movie_path else 'movie'}.ipynb"
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Kaggle Dubbing Notebook",
                default_name,
                "Jupyter Notebook (*.ipynb);;All Files (*)",
            )
            if not save_path:
                return

            from aidub.cloud.kaggle_accelerator import KaggleNotebookBuilder

            try:
                KaggleNotebookBuilder.export_to_file(
                    save_path,
                    movie_filename=Path(self.movie_path).name if self.movie_path else "movie.mp4",
                    target_language=self.target_language,
                    voice_engine=self.voice_engine,
                    enable_lipsync=self.enable_lipsync,
                )
                QMessageBox.information(
                    self,
                    "Notebook Created",
                    f"✓ Kaggle GPU Dubbing Notebook saved to:\n{save_path}\n\n"
                    "Next Steps:\n"
                    "1. Open https://www.kaggle.com/code\n"
                    "2. Click 'New Notebook' -> 'File' -> 'Upload Notebook'\n"
                    "3. Turn on GPU: Settings -> Accelerator -> GPU T4 x 2\n"
                    "4. Click 'Run All' to produce your dubbed video at maximum cloud speed!",
                )
            except Exception as exc:
                logger.exception("Failed exporting Kaggle notebook: %s", exc)
                QMessageBox.critical(self, "Export Failed", f"Could not create notebook:\n{exc}")

        def _generate_colab_notebook(self) -> None:
            default_name = f"colab_dubbing_{Path(self.movie_path).stem if self.movie_path else 'movie'}.ipynb"
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Google Colab Dubbing Notebook",
                default_name,
                "Jupyter Notebook (*.ipynb);;All Files (*)",
            )
            if not save_path:
                return

            try:
                ColabNotebookBuilder.export_to_file(
                    save_path,
                    movie_filename=Path(self.movie_path).name if self.movie_path else "movie.mp4",
                    target_language=self.target_language,
                    voice_engine=self.voice_engine,
                    enable_lipsync=self.enable_lipsync,
                )
                QMessageBox.information(
                    self,
                    "Google Colab Notebook Created",
                    f"✓ Google Colab GPU Dubbing Notebook saved to:\n{save_path}\n\n"
                    "Next Steps:\n"
                    "1. Open https://colab.research.google.com/\n"
                    "2. Click 'File' -> 'Upload notebook' and select this file\n"
                    "3. Select 'Runtime' -> 'Change runtime type' -> Choose 'T4 GPU'\n"
                    "4. Run the cells to process your movie with full GPU power!",
                )
            except Exception as exc:
                logger.exception("Failed exporting Colab notebook: %s", exc)
                QMessageBox.critical(self, "Export Failed", f"Could not create Colab notebook:\n{exc}")



__all__ = ["KaggleAcceleratorDialog"]

