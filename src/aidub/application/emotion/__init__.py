"""
Emotion Studio Application Package.
"""

from __future__ import annotations

from aidub.application.emotion.emotion_editor import EmotionEditorService
from aidub.application.emotion.emotion_transfer import EmotionTransferService

__all__ = [
    "EmotionEditorService",
    "EmotionTransferService",
]
