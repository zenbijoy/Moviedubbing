"""
Cloud GPU Accelerator & Live Synchronization Dialog for AIDub Studio.

Enables seamless offloading of heavy dubbing workloads to free cloud GPUs:
  1. Kaggle GPU (NVIDIA T4 x2 / P100 - 30 hrs/week): Automated notebook dispatch,
     background execution polling, and automatic 1-click deliverable download.
  2. Google Colab Free T4 GPU: 1-click Colab input bundle preparation,
     direct master bundle import (.zip / Google Drive), and local HTTP webhook bridge.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from aidub.cloud.cloud_sync_bridge import (
    DEFAULT_BRIDGE_PORT,
    CloudSyncEngine,
    CloudSyncResult,
    ColabLiveWebhookServer,
)
from aidub.cloud.colab_accelerator import ColabNotebookBuilder
from aidub.cloud.kaggle_accelerator import (
    KaggleClient,
    KaggleNotebookBuilder,
    load_kaggle_credentials,
    save_kaggle_credentials,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QThread, QUrl, Signal
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import (
        QDialog,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False


if _QT:

    class _KaggleSyncWorker(QThread):
        progress_signal = Signal(int, str)
        completed_signal = Signal(object)
        failed_signal = Signal(str)

        def __init__(
            self,
            client: KaggleClient,
            kernel_slug: str,
            project_work_dir: Path,
        ) -> None:
            super().__init__()
            self.client = client
            self.kernel_slug = kernel_slug
            self.project_work_dir = project_work_dir
            self._canceled = False

        def cancel(self) -> None:
            self._canceled = True

        def run(self) -> None:
            try:

                def _progress_cb(pct: int, msg: str) -> None:
                    self.progress_signal.emit(pct, msg)

                def _should_cancel() -> bool:
                    return self._canceled

                res = CloudSyncEngine.poll_and_sync_kaggle_job(
                    client=self.client,
                    kernel_slug=self.kernel_slug,
                    project_work_dir=self.project_work_dir,
                    progress_cb=_progress_cb,
                    should_cancel=_should_cancel,
                )
                if res.success:
                    self.completed_signal.emit(res)
                else:
                    self.failed_signal.emit(res.error_message or "Kaggle cloud sync failed")
            except Exception as exc:
                logger.exception("Kaggle sync worker error: %s", exc)
                self.failed_signal.emit(str(exc))

    class KaggleAcceleratorDialog(QDialog):
        """Clean, professional 2-Tab dialog to configure, dispatch, and auto-sync Cloud GPU jobs."""

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
            self.setWindowTitle("Cloud GPU Accelerator — Kaggle & Google Colab")
            self.setMinimumSize(700, 620)
            self.movie_path = movie_path
            self.target_language = target_language
            self.voice_engine = voice_engine
            self.enable_lipsync = enable_lipsync

            self._sync_result: CloudSyncResult | None = None
            self._worker: _KaggleSyncWorker | None = None
            self._webhook_server: ColabLiveWebhookServer | None = None

            self.setStyleSheet(
                "QDialog { background: #0B0E14; color: #E2E8F0; font-family: 'Segoe UI', system-ui, sans-serif; }"
                "QLabel { color: #E2E8F0; }"
                "QLineEdit {"
                "  background: #111622; color: #F8FAFC; border: 1px solid #1E293B;"
                "  border-radius: 6px; padding: 8px 12px; font-size: 12px;"
                "}"
                "QLineEdit:focus { border: 1px solid #38BDF8; background: #162032; }"
                "QTabWidget::pane { border: 1px solid #1E293B; background: #0F1420; border-radius: 8px; }"
                "QTabBar::tab {"
                "  background: #111622; color: #94A3B8; padding: 10px 22px; font-weight: 700; font-size: 12px;"
                "  border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px;"
                "}"
                "QTabBar::tab:selected { background: #0F1420; color: #38BDF8; border-bottom: 2px solid #38BDF8; }"
                "QTabBar::tab:hover { color: #F8FAFC; background: #1A2234; }"
            )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 20, 24, 20)
            layout.setSpacing(14)

            # Header Banner
            hdr_layout = QHBoxLayout()
            icon_lbl = QLabel("☁️", self)
            icon_lbl.setStyleSheet("font-size: 32px;")
            hdr_layout.addWidget(icon_lbl)

            hdr_text = QVBoxLayout()
            title = QLabel("Cloud GPU Accelerator & Live Sync Hub", self)
            title.setStyleSheet("font-size: 17px; font-weight: 800; color: #38BDF8;")
            subtitle = QLabel(
                "Accelerate heavy Demucs stems, Chatterbox voice cloning, and MuseTalk Lip-Sync on free NVIDIA GPUs.",
                self,
            )
            subtitle.setStyleSheet("font-size: 11px; color: #94A3B8;")
            hdr_text.addWidget(title)
            hdr_text.addWidget(subtitle)
            hdr_layout.addLayout(hdr_text)
            hdr_layout.addStretch()
            layout.addLayout(hdr_layout)

            # Project Summary Card
            info_frame = QFrame(self)
            info_frame.setStyleSheet(
                "QFrame { background: #111726; border: 1px solid #1E293B; border-radius: 8px; padding: 10px; }"
            )
            info_grid = QGridLayout(info_frame)
            info_grid.setContentsMargins(12, 8, 12, 8)
            info_grid.setHorizontalSpacing(16)
            info_grid.setVerticalSpacing(6)

            m_name = Path(self.movie_path).name if self.movie_path else "Active Timeline Movie"
            lang_label = (
                "বাংলা (Bengali)" if self.target_language == "bn" else self.target_language.upper()
            )

            info_grid.addWidget(QLabel("<span style='color:#64748B;'>Target Video:</span>"), 0, 0)
            info_grid.addWidget(QLabel(f"<b>{m_name}</b>"), 0, 1)

            info_grid.addWidget(QLabel("<span style='color:#64748B;'>Language:</span>"), 0, 2)
            info_grid.addWidget(
                QLabel(f"<span style='color:#38BDF8;'><b>{lang_label}</b></span>"), 0, 3
            )

            info_grid.addWidget(
                QLabel("<span style='color:#64748B;'>AI Voice Engine:</span>"), 1, 0
            )
            info_grid.addWidget(
                QLabel(f"<b>{self.voice_engine.upper()} (Neural Voice Clone)</b>"), 1, 1
            )

            lipsync_status = (
                "<span style='color:#22C55E;'><b>Active (NVIDIA Cloud Accelerated)</b></span>"
                if self.enable_lipsync
                else "<span style='color:#94A3B8;'>Audio Only</span>"
            )
            info_grid.addWidget(QLabel("<span style='color:#64748B;'>Lip-Sync Mode:</span>"), 1, 2)
            info_grid.addWidget(QLabel(lipsync_status), 1, 3)

            layout.addWidget(info_frame)

            # 2-Tab Cloud Hub
            self.tabs = QTabWidget(self)

            # ─────────────────────────────────────────────────────────────
            # TAB 1: Kaggle Cloud GPU (Automated Dispatch & 1-Click Sync)
            # ─────────────────────────────────────────────────────────────
            kaggle_tab = QWidget()
            kt_lay = QVBoxLayout(kaggle_tab)
            kt_lay.setContentsMargins(18, 16, 18, 16)
            kt_lay.setSpacing(12)

            # Info pill
            k_intro = QLabel(
                "⚡ <b>Kaggle GPU:</b> Offers 30 hours/week of free NVIDIA Tesla T4 x2 or P100 GPUs. "
                "AIDub will automatically dispatch your project notebook, monitor live execution, and download completed video deliverables.",
                kaggle_tab,
            )
            k_intro.setWordWrap(True)
            k_intro.setStyleSheet("font-size: 11px; color: #94A3B8; line-height: 1.4;")
            kt_lay.addWidget(k_intro)

            # Kaggle Credentials Group
            try:
                saved = load_kaggle_credentials()
            except Exception:
                saved = None
            u_init = saved.username if saved else ""
            k_init = saved.key if saved else ""

            cred_card = QFrame(kaggle_tab)
            cred_card.setStyleSheet(
                "QFrame { background: #131A2B; border: 1px solid #1E293B; border-radius: 8px; padding: 10px; }"
            )
            cc_lay = QVBoxLayout(cred_card)
            cc_lay.setSpacing(8)

            c_header = QLabel("Kaggle API Credentials", cred_card)
            c_header.setStyleSheet("font-weight: 700; font-size: 11px; color: #CBD5E1;")
            cc_lay.addWidget(c_header)

            u_row = QHBoxLayout()
            u_lbl = QLabel("Username:", cred_card)
            u_lbl.setFixedWidth(75)
            self.u_edit = QLineEdit(u_init, cred_card)
            self.u_edit.setPlaceholderText("e.g. johndoe")
            u_row.addWidget(u_lbl)
            u_row.addWidget(self.u_edit)
            cc_lay.addLayout(u_row)

            k_row = QHBoxLayout()
            k_lbl = QLabel("API Key:", cred_card)
            k_lbl.setFixedWidth(75)
            self.k_edit = QLineEdit(k_init, cred_card)
            self.k_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.k_edit.setPlaceholderText("From ~/.kaggle/kaggle.json")
            k_row.addWidget(k_lbl)
            k_row.addWidget(self.k_edit)
            cc_lay.addLayout(k_row)

            save_row = QHBoxLayout()
            cred_tip = QLabel("Get your key at: kaggle.com ➔ Account ➔ Create New Token", cred_card)
            cred_tip.setStyleSheet("font-size: 10px; color: #64748B;")
            save_row.addWidget(cred_tip, 1)

            save_btn = QPushButton("Save Credentials", cred_card)
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #38BDF8; border: 1px solid #334155;"
                "border-radius: 5px; padding: 5px 14px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #2D3D54; color: #FFF; }"
            )
            save_btn.clicked.connect(self._save_creds)
            save_row.addWidget(save_btn)
            cc_lay.addLayout(save_row)

            kt_lay.addWidget(cred_card)

            # Master Kaggle Launch Button
            self.push_btn = QPushButton("⚡ Launch & Auto-Sync on Kaggle Cloud GPU", kaggle_tab)
            self.push_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.push_btn.setFixedHeight(42)
            self.push_btn.setStyleSheet(
                "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16A34A, stop:1 #22C55E);"
                "color: #FFF; border: none; border-radius: 8px; font-size: 13px; font-weight: 800; }"
                "QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22C55E, stop:1 #4ADE80); }"
                "QPushButton:disabled { background: #334155; color: #64748B; }"
            )
            self.push_btn.clicked.connect(self._push_and_run_kaggle)
            kt_lay.addWidget(self.push_btn)

            # Secondary Kaggle actions
            k_sub_row = QHBoxLayout()
            self.gen_btn = QPushButton("📥 Export .ipynb Notebook", kaggle_tab)
            self.gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.gen_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #94A3B8; border: 1px solid #334155;"
                "border-radius: 6px; padding: 7px 14px; font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { background: #2563EB; color: #FFF; border-color: #3B82F6; }"
            )
            self.gen_btn.clicked.connect(self._generate_notebook)
            k_sub_row.addWidget(self.gen_btn)

            open_k_btn = QPushButton("🌐 Open Kaggle Code", kaggle_tab)
            open_k_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_k_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #94A3B8; border: 1px solid #334155;"
                "border-radius: 6px; padding: 7px 14px; font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { background: #0284C7; color: #FFF; border-color: #0EA5E9; }"
            )
            open_k_btn.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl("https://www.kaggle.com/code"))
            )
            k_sub_row.addWidget(open_k_btn)
            kt_lay.addLayout(k_sub_row)

            kt_lay.addStretch()
            self.tabs.addTab(kaggle_tab, "🚀 Kaggle GPU (Free 30 hrs/wk)")

            # ─────────────────────────────────────────────────────────────
            # TAB 2: Google Colab Free T4 GPU
            # ─────────────────────────────────────────────────────────────
            colab_tab = QWidget()
            ct_lay = QVBoxLayout(colab_tab)
            ct_lay.setContentsMargins(18, 16, 18, 16)
            ct_lay.setSpacing(12)

            c_intro = QLabel(
                "⚡ <b>Google Colab:</b> Run dubbing in your browser on free NVIDIA T4 GPUs with zero setup. "
                "Follow the 3-step workflow below to process high-resolution videos without heating your local laptop.",
                colab_tab,
            )
            c_intro.setWordWrap(True)
            c_intro.setStyleSheet("font-size: 11px; color: #94A3B8; line-height: 1.4;")
            ct_lay.addWidget(c_intro)

            # 3-Step Guided Cards
            steps_card = QFrame(colab_tab)
            steps_card.setStyleSheet(
                "QFrame { background: #131A2B; border: 1px solid #1E293B; border-radius: 8px; padding: 12px; }"
            )
            sc_lay = QVBoxLayout(steps_card)
            sc_lay.setSpacing(10)

            # Step 1
            s1_row = QHBoxLayout()
            s1_badge = QLabel("1", steps_card)
            s1_badge.setFixedSize(22, 22)
            s1_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s1_badge.setStyleSheet(
                "background: #0284C7; color: #FFF; font-weight: 800; border-radius: 11px; font-size: 11px;"
            )
            s1_row.addWidget(s1_badge)
            s1_txt = QLabel(
                "<b>Pack Project Input:</b> Creates a compressed package of your source media and cues.",
                steps_card,
            )
            s1_txt.setStyleSheet("font-size: 11px; color: #CBD5E1;")
            s1_row.addWidget(s1_txt, 1)
            self.colab_pack_btn = QPushButton("📦 Pack Input (.zip)", steps_card)
            self.colab_pack_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.colab_pack_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #38BDF8; border: 1px solid #334155;"
                "border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #0284C7; color: #FFF; }"
            )
            self.colab_pack_btn.clicked.connect(self._pack_colab_input)
            s1_row.addWidget(self.colab_pack_btn)
            sc_lay.addLayout(s1_row)

            # Step 2
            s2_row = QHBoxLayout()
            s2_badge = QLabel("2", steps_card)
            s2_badge.setFixedSize(22, 22)
            s2_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s2_badge.setStyleSheet(
                "background: #D97706; color: #FFF; font-weight: 800; border-radius: 11px; font-size: 11px;"
            )
            s2_row.addWidget(s2_badge)
            s2_txt = QLabel(
                "<b>Export Colab Notebook:</b> Generates customized .ipynb script for Colab T4 runtime.",
                steps_card,
            )
            s2_txt.setStyleSheet("font-size: 11px; color: #CBD5E1;")
            s2_row.addWidget(s2_txt, 1)
            self.colab_btn = QPushButton("⚡ Export Notebook", steps_card)
            self.colab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.colab_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #F59E0B; border: 1px solid #334155;"
                "border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #D97706; color: #FFF; }"
            )
            self.colab_btn.clicked.connect(self._generate_colab_notebook)
            s2_row.addWidget(self.colab_btn)
            open_colab_link = QPushButton("🌐 Open Colab", steps_card)
            open_colab_link.setCursor(Qt.CursorShape.PointingHandCursor)
            open_colab_link.setStyleSheet(
                "QPushButton { background: transparent; color: #94A3B8; border: 1px solid #334155;"
                "border-radius: 6px; padding: 6px 10px; font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { color: #FFF; border-color: #64748B; }"
            )
            open_colab_link.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl("https://colab.research.google.com/"))
            )
            s2_row.addWidget(open_colab_link)
            sc_lay.addLayout(s2_row)

            # Step 3
            s3_row = QHBoxLayout()
            s3_badge = QLabel("3", steps_card)
            s3_badge.setFixedSize(22, 22)
            s3_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s3_badge.setStyleSheet(
                "background: #059669; color: #FFF; font-weight: 800; border-radius: 11px; font-size: 11px;"
            )
            s3_row.addWidget(s3_badge)
            s3_txt = QLabel(
                "<b>Import Deliverables:</b> Load finished video, stem audio & subtitles back into Timeline.",
                steps_card,
            )
            s3_txt.setStyleSheet("font-size: 11px; color: #CBD5E1;")
            s3_row.addWidget(s3_txt, 1)
            self.import_colab_btn = QPushButton("📥 1-Click Import", steps_card)
            self.import_colab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.import_colab_btn.setStyleSheet(
                "QPushButton { background: #059669; color: #FFF; border: none;"
                "border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #10B981; }"
            )
            self.import_colab_btn.clicked.connect(self._import_colab_output_bundle)
            s3_row.addWidget(self.import_colab_btn)
            sc_lay.addLayout(s3_row)

            ct_lay.addWidget(steps_card)

            # Webhook Bridge Card
            wb_card = QFrame(colab_tab)
            wb_card.setStyleSheet(
                "QFrame { background: #0E1524; border: 1px solid #1E293B; border-radius: 8px; padding: 10px; }"
            )
            wb_lay = QHBoxLayout(wb_card)
            wb_lay.setSpacing(12)

            self.webhook_toggle_btn = QPushButton("🔌 Enable Local Webhook Bridge", wb_card)
            self.webhook_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.webhook_toggle_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #38BDF8; border: 1px solid #334155;"
                "border-radius: 6px; padding: 8px 14px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #263346; color: #FFF; }"
            )
            self.webhook_toggle_btn.clicked.connect(self._toggle_webhook_server)
            wb_lay.addWidget(self.webhook_toggle_btn)

            self.webhook_status_lbl = QLabel(
                "Bridge server: Inactive (enable for zero-click direct sync from Colab)", wb_card
            )
            self.webhook_status_lbl.setStyleSheet("font-size: 10px; color: #94A3B8;")
            self.webhook_status_lbl.setWordWrap(True)
            wb_lay.addWidget(self.webhook_status_lbl, 1)

            ct_lay.addWidget(wb_card)
            ct_lay.addStretch()
            self.tabs.addTab(colab_tab, "⚡ Google Colab GPU (Free T4)")

            layout.addWidget(self.tabs, 1)

            # Live Progress & Status Indicator
            self.prog_bar = QProgressBar(self)
            self.prog_bar.setRange(0, 100)
            self.prog_bar.setValue(0)
            self.prog_bar.setTextVisible(True)
            self.prog_bar.setStyleSheet(
                "QProgressBar { background: #0F172A; border: 1px solid #1E293B; border-radius: 6px;"
                "height: 18px; text-align: center; color: #FFF; font-size: 11px; font-weight: 700; }"
                "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16A34A, stop:1 #22C55E); border-radius: 5px; }"
            )
            self.prog_bar.setVisible(False)
            layout.addWidget(self.prog_bar)

            self.status_lbl = QLabel("", self)
            self.status_lbl.setStyleSheet(
                "font-size: 11px; color: #38BDF8; font-weight: 600; padding: 2px 4px;"
            )
            self.status_lbl.setVisible(False)
            layout.addWidget(self.status_lbl)

            # Bottom Close Button
            close_row = QHBoxLayout()
            self.cancel_sync_btn = QPushButton("Cancel Job", self)
            self.cancel_sync_btn.setStyleSheet(
                "QPushButton { background: #7F1D1D; color: #FCA5A5; border: 1px solid #991B1B;"
                "border-radius: 6px; padding: 8px 16px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #991B1B; color: #FFF; }"
            )
            self.cancel_sync_btn.setVisible(False)
            self.cancel_sync_btn.clicked.connect(self._cancel_sync_worker)
            close_row.addWidget(self.cancel_sync_btn)

            close_row.addStretch()
            close_btn = QPushButton("Close", self)
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #CBD5E1; border: 1px solid #334155;"
                "border-radius: 6px; padding: 8px 24px; font-weight: 600; font-size: 12px; }"
                "QPushButton:hover { color: #FFF; background: #334155; }"
            )
            close_btn.clicked.connect(self.accept)
            close_row.addWidget(close_btn)
            layout.addLayout(close_row)

        def get_sync_result(self) -> CloudSyncResult | None:
            """Return the imported deliverables if a cloud sync was completed."""
            return self._sync_result

        def _save_creds(self) -> None:
            user = self.u_edit.text().strip()
            key = self.k_edit.text().strip()
            if not user or not key:
                QMessageBox.warning(
                    self, "Invalid Credentials", "Please enter both Kaggle Username and API Key."
                )
                return

            save_kaggle_credentials(user, key)
            QMessageBox.information(
                self,
                "Credentials Saved",
                "✓ Kaggle credentials successfully saved to ~/.kaggle/kaggle.json and active in environment.",
            )

        def _push_and_run_kaggle(self) -> None:
            client = KaggleClient()
            if not client.is_configured:
                QMessageBox.warning(
                    self,
                    "Credentials Required",
                    "Please enter and save your Kaggle Username and API Key before launching a cloud job.",
                )
                return

            raw_title = Path(self.movie_path).stem if self.movie_path else "feature"
            slug = re.sub(r"[^a-z0-9-]", "", f"aidub-{raw_title}".lower())[:50] or "aidub-job"
            title = f"AIDub GPU - {raw_title[:40]}"

            nb_data = KaggleNotebookBuilder.create_dubbing_notebook(
                movie_filename=Path(self.movie_path).name if self.movie_path else "movie.mp4",
                target_language=self.target_language,
                voice_engine=self.voice_engine,
                enable_lipsync=self.enable_lipsync,
            )

            self.status_lbl.setVisible(True)
            self.status_lbl.setText("Pushing notebook kernel to Kaggle Cloud API...")
            self.prog_bar.setVisible(True)
            self.prog_bar.setValue(10)

            ok, res = client.push_kernel(
                kernel_slug=slug,
                title=title,
                notebook_data=nb_data,
                enable_gpu=True,
                is_private=True,
            )
            if not ok:
                self.prog_bar.setVisible(False)
                self.status_lbl.setVisible(False)
                QMessageBox.critical(
                    self, "Launch Failed", f"Could not push job to Kaggle API:\n{res}"
                )
                return

            # Start Auto-Sync Polling Worker
            w_dir = Path(self.movie_path).parent if self.movie_path else Path.cwd()
            self.push_btn.setEnabled(False)
            self.cancel_sync_btn.setVisible(True)
            self.status_lbl.setText(
                f"✓ Job dispatched! Live Cloud URL: {res}\nPolling Kaggle GPU status..."
            )

            self._worker = _KaggleSyncWorker(client, slug, w_dir)
            self._worker.progress_signal.connect(self._on_sync_progress)
            self._worker.completed_signal.connect(self._on_sync_completed)
            self._worker.failed_signal.connect(self._on_sync_failed)
            self._worker.start()

        def _on_sync_progress(self, pct: int, msg: str) -> None:
            self.prog_bar.setValue(pct)
            self.status_lbl.setText(msg)

        def _on_sync_completed(self, res: CloudSyncResult) -> None:
            self.prog_bar.setValue(100)
            self.status_lbl.setText(
                f"✓ Cloud Deliverables Synced ({res.total_files} files, {res.total_bytes / (1024 * 1024):.1f} MB)!"
            )
            self.push_btn.setEnabled(True)
            self.cancel_sync_btn.setVisible(False)
            self._sync_result = res

            msg = (
                f"✓ Cloud GPU Dubbing Job Completed & Synced!\n\n"
                f"• Video: {res.dubbed_video_path.name if res.dubbed_video_path else 'None'}\n"
                f"• Audio: {res.dubbed_audio_path.name if res.dubbed_audio_path else 'None'}\n"
                f"• Subtitles: {res.subtitle_path.name if res.subtitle_path else 'None'}\n"
                f"• Segments: {res.utterances_path.name if res.utterances_path else 'None'}\n\n"
                "The active timeline project will now reload with these cloud assets."
            )
            QMessageBox.information(self, "Cloud Master Synced", msg)
            self.accept()

        def _on_sync_failed(self, err_msg: str) -> None:
            self.push_btn.setEnabled(True)
            self.cancel_sync_btn.setVisible(False)
            self.status_lbl.setText(f"Cloud execution error: {err_msg}")
            QMessageBox.critical(
                self, "Cloud Execution Error", f"Kaggle Cloud Job Failed:\n{err_msg}"
            )

        def _cancel_sync_worker(self) -> None:
            if self._worker:
                self._worker.cancel()
                self.status_lbl.setText("Canceling cloud monitor...")
                self.cancel_sync_btn.setEnabled(False)

        def _pack_colab_input(self) -> None:
            w_dir = Path(self.movie_path).parent if self.movie_path else Path.cwd()
            try:
                pkg_zip = CloudSyncEngine.create_colab_input_bundle(
                    work_dir=w_dir,
                    movie_path=self.movie_path,
                    target_language=self.target_language,
                    voice_engine=self.voice_engine,
                )
                QMessageBox.information(
                    self,
                    "Colab Input Bundle Packed",
                    f"✓ Prepared project input archive for Google Colab:\n{pkg_zip}\n\n"
                    "Upload this .zip directly to Google Drive or Colab file browser.",
                )
            except Exception as exc:
                QMessageBox.critical(
                    self, "Packaging Error", f"Could not create input bundle:\n{exc}"
                )

        def _import_colab_output_bundle(self) -> None:
            chosen, _ = QFileDialog.getOpenFileName(
                self,
                "Select Colab Output Deliverables (.zip / .mp4)",
                str(Path.home() / "Downloads"),
                "Colab Deliverables (*.zip *.mp4 *.mkv);;All Files (*)",
            )
            if not chosen:
                return

            w_dir = Path(self.movie_path).parent if self.movie_path else Path.cwd()
            res = CloudSyncEngine.import_cloud_output_bundle(chosen, w_dir)
            if res.success:
                self._on_sync_completed(res)
            else:
                QMessageBox.critical(
                    self,
                    "Import Error",
                    f"Could not import Colab deliverables:\n{res.error_message}",
                )

        def _toggle_webhook_server(self) -> None:
            if self._webhook_server and self._webhook_server.is_running:
                self._webhook_server.stop()
                self._webhook_server = None
                self.webhook_toggle_btn.setText("🔌 Enable Local Webhook Bridge")
                self.webhook_status_lbl.setText("Bridge server: Inactive")
                return

            w_dir = Path(self.movie_path).parent if self.movie_path else Path.cwd()

            def _on_colab_push_received(res: CloudSyncResult) -> None:
                self._on_sync_completed(res)

            self._webhook_server = ColabLiveWebhookServer(
                target_work_dir=w_dir,
                port=DEFAULT_BRIDGE_PORT,
                on_bundle_received=_on_colab_push_received,
            )
            started = self._webhook_server.start()
            if started:
                token = self._webhook_server.auth_token
                url = f"http://127.0.0.1:{DEFAULT_BRIDGE_PORT}/api/colab/sync"
                self.webhook_toggle_btn.setText("🛑 Stop Webhook Bridge")
                self.webhook_status_lbl.setText(
                    f"Active: {url}\nToken: {token[:8]}... (Paste into Colab cell 6 for instant zero-click auto sync!)"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Bridge Error",
                    f"Could not start webhook server on port {DEFAULT_BRIDGE_PORT}.",
                )

        def _generate_notebook(self) -> None:
            default_name = (
                f"dubbing_gpu_{Path(self.movie_path).stem if self.movie_path else 'movie'}.ipynb"
            )
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Kaggle Dubbing Notebook",
                default_name,
                "Jupyter Notebook (*.ipynb);;All Files (*)",
            )
            if not save_path:
                return

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
            default_name = (
                f"colab_dubbing_{Path(self.movie_path).stem if self.movie_path else 'movie'}.ipynb"
            )
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
                QMessageBox.critical(
                    self, "Export Failed", f"Could not create Colab notebook:\n{exc}"
                )


__all__ = ["KaggleAcceleratorDialog"]
