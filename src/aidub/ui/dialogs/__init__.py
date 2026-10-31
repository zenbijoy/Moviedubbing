"""Dialogs package for AI Movie Dubbing Studio."""

from __future__ import annotations

from aidub.ui.dialogs.audio_review_panel import AudioReviewDialog
from aidub.ui.dialogs.broadcast_export_dialog import BroadcastExportDialog as BroadcastExportMasterDialog
from aidub.ui.dialogs.character_casting_dialog import CharacterCastingStudioDialog
from aidub.ui.dialogs.character_classification_studio_dialog import (
    CharacterClassificationStudioDialog,
)
from aidub.ui.dialogs.cloud_accelerator_dialog import KaggleAcceleratorDialog as CloudAcceleratorDialog
from aidub.ui.dialogs.cubase_audio_align_dialog import CubaseAudioAlignmentDialog
from aidub.ui.dialogs.cubase_control_room_dialog import CubaseControlRoomDialog
from aidub.ui.dialogs.cubase_crossfade_dialog import CubaseCrossfadeDialog
from aidub.ui.dialogs.cubase_dop_dialog import CubaseDopDialog
from aidub.ui.dialogs.cubase_variaudio_dialog import CubaseVariAudioDialog
from aidub.ui.dialogs.lipsync_inspector_dialog import LipSyncInspectorDialog
from aidub.ui.dialogs.new_project_dialog import NewProjectDialog
from aidub.ui.dialogs.pro_emotion_studio_dialog import ProEmotionStudioDialog
from aidub.ui.dialogs.pro_voice_editor_dialog import ProVoiceEditorDialog
from aidub.ui.dialogs.voice_exchanger_dialog import VoiceExchangerDialog
from aidub.ui.dialogs.adr_punch_in_dialog import AdrPunchInDialog
from aidub.ui.dialogs.audio_dsp_tools_dialog import AudioDspToolsDialog
from aidub.ui.dialogs.bangla_dub_studio_dialog import BanglaDubStudioDialog
from aidub.ui.dialogs.batch_dub_runner_dialog import BatchDubRunnerDialog
from aidub.ui.dialogs.command_palette_dialog import CommandPaletteDialog
from aidub.ui.dialogs.export_delivery_dialog import ExportDeliveryDialog
from aidub.ui.dialogs.isochronic_dialogue_adapter_dialog import IsochronicDialogueAdapterDialog
from aidub.ui.dialogs.neural_lipsync_studio_dialog import NeuralLipSyncStudioDialog
from aidub.ui.dialogs.prosody_transfer_dialog import ProsodyTransferDialog
from aidub.ui.dialogs.subtitle_caption_studio_dialog import SubtitleCaptionStudioDialog
from aidub.ui.dialogs.voice_clone_studio_dialog import VoiceCloneStudioDialog
from aidub.ui.dialogs.voice_model_dialog import VoiceModelDialog
from aidub.ui.dialogs.voice_studio_dialog import VoiceStudioDialog

__all__ = [
    "AdrPunchInDialog",
    "AudioDspToolsDialog",
    "AudioReviewDialog",
    "BanglaDubStudioDialog",
    "BatchDubRunnerDialog",
    "BroadcastExportMasterDialog",
    "CharacterCastingStudioDialog",
    "CharacterClassificationStudioDialog",
    "CloudAcceleratorDialog",
    "CommandPaletteDialog",
    "CubaseAudioAlignmentDialog",
    "CubaseControlRoomDialog",
    "CubaseCrossfadeDialog",
    "CubaseDopDialog",
    "CubaseVariAudioDialog",
    "ExportDeliveryDialog",
    "IsochronicDialogueAdapterDialog",
    "LipSyncInspectorDialog",
    "NeuralLipSyncStudioDialog",
    "NewProjectDialog",
    "ProEmotionStudioDialog",
    "ProVoiceEditorDialog",
    "ProsodyTransferDialog",
    "SubtitleCaptionStudioDialog",
    "VoiceCloneStudioDialog",
    "VoiceExchangerDialog",
    "VoiceModelDialog",
    "VoiceStudioDialog",
]
