"""
New Project Creation Dialog for AI Movie Dubbing Studio.

Provides an authoritative, Premiere/Resolve-grade dialog to initialize
local-first .aidub project packages with strict domain validation.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from aidub.application.projects import (
    InvalidProjectPackageError,
    OpenedProject,
    ProjectAlreadyExistsError,
    ProjectPackageService,
)
from aidub.domain.project import PrivacyMode, ProjectSettings, QualityPreset
from aidub.domain.rights import SourceAuthorization
from aidub.domain.time import RationalRate
from aidub.infrastructure.catalog import ProjectCatalog, default_catalog_path

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False


if _QT:

    class NewProjectDialog(QDialog):
        """Authoritative modal dialog for creating and initializing an .aidub project package."""

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setWindowTitle("Create New Dubbing Project — AI Movie Dubbing Studio")
            self.setMinimumSize(620, 560)
            self.resize(640, 600)
            self.created_project: OpenedProject | None = None

            self.setStyleSheet(
                "QDialog { background: #0B0E14; color: #F8FAFC; }"
                "QLabel { color: #94A3B8; font-size: 11px; font-weight: 600; }"
                "QLineEdit, QComboBox {"
                "  background: #141822; color: #F8FAFC; border: 1px solid #232C3E;"
                "  border-radius: 6px; padding: 6px 10px; font-size: 12px;"
                "}"
                "QLineEdit:focus, QComboBox:focus { border-color: #38BDF8; }"
                "QComboBox::drop-down { border: none; }"
                "QComboBox QAbstractItemView {"
                "  background: #141822; color: #F8FAFC; selection-background-color: #2563EB;"
                "  border: 1px solid #232C3E; border-radius: 4px;"
                "}"
            )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(28, 24, 28, 24)
            layout.setSpacing(16)

            # Header
            header_layout = QVBoxLayout()
            header_layout.setSpacing(4)
            title = QLabel("New Dubbing Project", self)
            title.setStyleSheet("font-size: 20px; font-weight: 900; color: #F8FAFC;")
            subtitle = QLabel(
                "Configure your local-first audio dubbing project, localization target, and master settings.",
                self,
            )
            subtitle.setStyleSheet("font-size: 12px; font-weight: 400; color: #64748B;")
            subtitle.setWordWrap(True)
            header_layout.addWidget(title)
            header_layout.addWidget(subtitle)
            layout.addLayout(header_layout)

            # Card Container
            card = QFrame(self)
            card.setStyleSheet(
                "QFrame { background: #10141D; border: 1px solid #1C2433; border-radius: 10px; padding: 16px; }"
            )
            form_layout = QVBoxLayout(card)
            form_layout.setSpacing(12)

            # 1. Project Name
            form_layout.addWidget(QLabel("PROJECT NAME"))
            self.name_edit = QLineEdit(card)
            self.name_edit.setPlaceholderText("e.g., Bengali Feature Dub")
            self.name_edit.setText("Untitled Dubbing Project")
            self.name_edit.textChanged.connect(self._update_preview)
            form_layout.addWidget(self.name_edit)

            # 2. Storage Location
            form_layout.addWidget(QLabel("STORAGE DIRECTORY"))
            loc_layout = QHBoxLayout()
            loc_layout.setSpacing(8)
            default_dir = Path.home() / "Documents" / "AIDubStudioProjects"
            self.loc_edit = QLineEdit(str(default_dir), card)
            self.loc_edit.textChanged.connect(self._update_preview)
            loc_layout.addWidget(self.loc_edit, 1)

            browse_btn = QPushButton("Browse…", card)
            browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            browse_btn.setStyleSheet(
                "QPushButton { background: #1E2738; color: #F1F5F9; border: 1px solid #2B384E; border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { background: #2A364E; border-color: #38BDF8; }"
            )
            browse_btn.clicked.connect(self._on_browse)
            loc_layout.addWidget(browse_btn)
            form_layout.addLayout(loc_layout)

            # Destination Preview
            self.preview_lbl = QLabel("", card)
            self.preview_lbl.setStyleSheet("font-size: 10px; color: #38BDF8; font-weight: 500;")
            self.preview_lbl.setWordWrap(True)
            form_layout.addWidget(self.preview_lbl)

            # 3. Source & Target Languages
            lang_row = QHBoxLayout()
            lang_row.setSpacing(12)

            src_col = QVBoxLayout()
            src_col.setSpacing(4)
            src_col.addWidget(QLabel("SOURCE LANGUAGE"))
            self.src_lang_cb = QComboBox(card)
            self.src_lang_cb.addItem("English (US) [en-US]", "en-US")
            self.src_lang_cb.addItem("English (UK) [en-GB]", "en-GB")
            self.src_lang_cb.addItem("Spanish [es-ES]", "es-ES")
            self.src_lang_cb.addItem("Hindi [hi-IN]", "hi-IN")
            self.src_lang_cb.addItem("Japanese [ja-JP]", "ja-JP")
            self.src_lang_cb.addItem("Korean [ko-KR]", "ko-KR")
            self.src_lang_cb.addItem("French [fr-FR]", "fr-FR")
            self.src_lang_cb.addItem("German [de-DE]", "de-DE")
            src_col.addWidget(self.src_lang_cb)
            lang_row.addLayout(src_col)

            tgt_col = QVBoxLayout()
            tgt_col.setSpacing(4)
            tgt_col.addWidget(QLabel("TARGET LOCALIZATION"))
            self.tgt_lang_cb = QComboBox(card)
            self.tgt_lang_cb.addItem("Bengali (Bangladesh) [bn-BD]", "bn-BD")
            self.tgt_lang_cb.addItem("Bengali (India) [bn-IN]", "bn-IN")
            self.tgt_lang_cb.addItem("Hindi [hi-IN]", "hi-IN")
            self.tgt_lang_cb.addItem("Spanish (LatAm) [es-419]", "es-419")
            self.tgt_lang_cb.addItem("Japanese [ja-JP]", "ja-JP")
            self.tgt_lang_cb.addItem("German [de-DE]", "de-DE")
            tgt_col.addWidget(self.tgt_lang_cb)
            lang_row.addLayout(tgt_col)
            form_layout.addLayout(lang_row)

            # 4. Master Timebase & Quality Preset
            eng_row = QHBoxLayout()
            eng_row.setSpacing(12)

            rate_col = QVBoxLayout()
            rate_col.setSpacing(4)
            rate_col.addWidget(QLabel("MASTER FRAME RATE"))
            self.rate_cb = QComboBox(card)
            self.rate_cb.addItem("24 fps (Cinema Standard)", (24000, 1001))
            self.rate_cb.addItem("23.976 fps (NTSC Cinema)", (24000, 1001))
            self.rate_cb.addItem("25 fps (PAL / Broadcast)", (25, 1))
            self.rate_cb.addItem("29.97 fps (NTSC Video)", (30000, 1001))
            self.rate_cb.addItem("30 fps", (30, 1))
            self.rate_cb.addItem("60 fps", (60, 1))
            rate_col.addWidget(self.rate_cb)
            eng_row.addLayout(rate_col)

            preset_col = QVBoxLayout()
            preset_col.setSpacing(4)
            preset_col.addWidget(QLabel("MASTER QUALITY PRESET"))
            self.preset_cb = QComboBox(card)
            self.preset_cb.addItem("Professional Master (Recommended)", QualityPreset.PROFESSIONAL)
            self.preset_cb.addItem("Cinema 4K Mastering", QualityPreset.CINEMA)
            self.preset_cb.addItem("Draft / Rapid Review", QualityPreset.DRAFT)
            preset_col.addWidget(self.preset_cb)
            eng_row.addLayout(preset_col)
            form_layout.addLayout(eng_row)

            # 5. Privacy & Rights Authorization Basis
            auth_col = QVBoxLayout()
            auth_col.setSpacing(4)
            auth_col.addWidget(QLabel("RIGHTS / AUTHORIZATION BASIS"))
            self.auth_edit = QLineEdit(card)
            self.auth_edit.setText("Studio Authorized Internal Dubbing Production")
            auth_col.addWidget(self.auth_edit)
            form_layout.addLayout(auth_col)

            layout.addWidget(card)

            # Error Label
            self.error_lbl = QLabel("", self)
            self.error_lbl.setStyleSheet(
                "color: #EF4444; font-size: 11px; font-weight: 700; padding: 2px;"
            )
            self.error_lbl.setVisible(False)
            layout.addWidget(self.error_lbl)

            # Action Buttons
            btn_row = QHBoxLayout()
            btn_row.setSpacing(10)
            btn_row.addStretch()

            cancel_btn = QPushButton("Cancel", self)
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setStyleSheet(
                "QPushButton { background: #141822; color: #94A3B8; border: 1px solid #232C3E; border-radius: 6px; padding: 8px 18px; font-size: 12px; font-weight: 600; }"
                "QPushButton:hover { background: #1C2433; color: #FFF; }"
            )
            cancel_btn.clicked.connect(self.reject)
            btn_row.addWidget(cancel_btn)

            create_btn = QPushButton("Create Project", self)
            create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            create_btn.setStyleSheet(
                "QPushButton { background: #2563EB; color: #FFF; border: none; border-radius: 6px; padding: 8px 22px; font-size: 12px; font-weight: 700; }"
                "QPushButton:hover { background: #1D4ED8; }"
            )
            create_btn.clicked.connect(self._on_create)
            btn_row.addWidget(create_btn)
            layout.addLayout(btn_row)

            self._update_preview()

        def _update_preview(self) -> None:
            name = self.name_edit.text().strip() or "Untitled"
            clean_name = re.sub(r'[\\/*?:"<>|]', "", name)
            loc = Path(self.loc_edit.text().strip() or ".")
            target_path = loc / f"{clean_name}.aidub"
            self.preview_lbl.setText(f"Package destination: {target_path}")

        def _on_browse(self) -> None:
            selected = QFileDialog.getExistingDirectory(
                self,
                "Select Storage Directory for Project",
                self.loc_edit.text().strip() or str(Path.home()),
            )
            if selected:
                self.loc_edit.setText(selected)

        def _show_error(self, message: str) -> None:
            self.error_lbl.setText(f"⚠ {message}")
            self.error_lbl.setVisible(True)

        def _on_create(self) -> None:
            name = self.name_edit.text().strip()
            if not name:
                self._show_error("Please enter a project name.")
                return

            loc_text = self.loc_edit.text().strip()
            if not loc_text:
                self._show_error("Please specify a storage directory.")
                return

            loc_dir = Path(loc_text)
            try:
                loc_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self._show_error(f"Cannot create storage directory: {exc}")
                return

            clean_name = re.sub(r'[\\/*?:"<>|]', "", name)
            destination = loc_dir / clean_name
            target_package = loc_dir / f"{clean_name}.aidub"
            if target_package.exists():
                self._show_error(
                    f"A project package already exists at: {target_package.name}. Please choose a different name or location."
                )
                return

            rate_num, rate_den = self.rate_cb.currentData()
            src_lang = str(self.src_lang_cb.currentData())
            tgt_lang = str(self.tgt_lang_cb.currentData())
            raw_quality = self.preset_cb.currentData()
            quality = (
                QualityPreset(raw_quality)
                if not isinstance(raw_quality, QualityPreset)
                else raw_quality
            )
            auth_basis = self.auth_edit.text().strip() or "Internal Dubbing Production"

            settings = ProjectSettings(
                video_rate=RationalRate(numerator=rate_num, denominator=rate_den),
                source_language=src_lang,
                quality_preset=quality,
                privacy_mode=PrivacyMode.OFFLINE,
            )

            source_auth = SourceAuthorization(
                acknowledged=True,
                acknowledged_by="studio.operator",
                acknowledged_at=datetime.now(UTC),
                authority_basis=auth_basis,
                evidence_reference="internal://studio-authorization",
            )

            catalog = ProjectCatalog(default_catalog_path())
            try:
                catalog.initialize()
            except Exception as cat_exc:
                logger.debug("Catalog initialization notice: %s", cat_exc)

            service = ProjectPackageService(catalog=catalog)
            try:
                opened = service.create(
                    destination,
                    name=name,
                    settings=settings,
                    source_authorization=source_auth,
                    localization_locales=(tgt_lang,),
                    actor_id="studio.operator",
                )
            except (ProjectAlreadyExistsError, InvalidProjectPackageError, OSError) as exc:
                self._show_error(f"Project creation failed: {exc}")
                return

            self.created_project = opened
            self.accept()
