"""
Multimodal Emotion Engine & Continuous Emotion Detection System.

Combines:
  1. Local Acoustic Analysis (F0 pitch contours, RMS energy dynamics, spectral centroid, speech rate)
  2. LLM Dramatic Contextual Analysis (via Gemini, OpenRouter, or Local LLM)
  3. Kaggle / Remote GPU Worker Adapter (Emotion2Vec+ / Wav2Vec2 audio models)
  4. Multimodal Bayesian Ensemble Fusion
  5. Concrete Synthesis Parameter Mapping for Bengali TTS (Edge-TTS) & Character RVC v2
"""

from __future__ import annotations

import json
import logging
import math
import os
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import Field

from aidub.ai.voice.advanced_emotion import (
    CinematicLlmInstructor,
    ContinualEmotionLearner,
    DirectorEmotionController,
    EmotionVerificationReport,
    EmotionVerifierAndRegenerator,
    FastAcousticProsodyAnalyzer,
)
from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.emotion import EmotionObservation, PerformanceEmotionState

logger = logging.getLogger(__name__)


class EmotionAnalysisUnavailableError(RuntimeError):
    """Raised when no configured emotion analysis method can provide a result."""


# Standard cinematic emotion categories mapped to continuous VAD space
EMOTION_VAD_ANCHORS: dict[str, tuple[float, float, float]] = {
    # (valence, arousal, dominance)
    "neutral": (0.0, 0.0, 0.0),
    "joy": (0.75, 0.65, 0.55),
    "anger": (-0.65, 0.85, 0.70),
    "sadness": (-0.75, -0.60, -0.50),
    "fear": (-0.70, 0.75, -0.65),
    "surprise": (0.25, 0.80, 0.10),
    "disgust": (-0.60, 0.35, 0.30),
    "anticipation": (0.35, 0.50, 0.25),
    "whisper": (-0.10, -0.70, -0.30),
    "suspense": (-0.40, 0.60, -0.20),
    "intense_confrontation": (-0.80, 0.90, 0.85),
    "sarcastic": (-0.20, 0.30, 0.40),
    "tender": (0.70, -0.40, 0.20),
    "despair": (-0.90, -0.50, -0.80),
    "resolute": (0.30, 0.40, 0.80),
}

# Rate and pitch adjustments supported by EdgeTTSAdapter.
EDGE_TTS_STYLE_MAP: dict[str, dict[str, Any]] = {
    "neutral": {"pitch": "+0Hz", "rate": "+0%"},
    "joy": {"pitch": "+8Hz", "rate": "+10%"},
    "anger": {"pitch": "+15Hz", "rate": "+12%"},
    "sadness": {"pitch": "-12Hz", "rate": "-15%"},
    "fear": {"pitch": "+18Hz", "rate": "+20%"},
    "surprise": {"pitch": "+15Hz", "rate": "+15%"},
    "disgust": {"pitch": "-6Hz", "rate": "-8%"},
    "anticipation": {"pitch": "+5Hz", "rate": "+5%"},
    "whisper": {"pitch": "-10Hz", "rate": "-12%"},
    "suspense": {"pitch": "-5Hz", "rate": "-10%"},
    "intense_confrontation": {"pitch": "+20Hz", "rate": "+15%"},
    "sarcastic": {"pitch": "-4Hz", "rate": "-5%"},
    "tender": {"pitch": "-4Hz", "rate": "-10%"},
    "despair": {"pitch": "-16Hz", "rate": "-18%"},
    "resolute": {"pitch": "-2Hz", "rate": "-4%"},
}


class EmotionDetectionResult(ContractModel):
    """Rich emotion detection result output by the Emotion Engine."""

    utterance_id: Identifier
    primary_emotion: str = Field(min_length=1, max_length=32)
    confidence: float = Field(ge=0.0, le=1.0)
    valence: float = Field(ge=-1.0, le=1.0)
    arousal: float = Field(ge=-1.0, le=1.0)
    dominance: float = Field(ge=-1.0, le=1.0)
    intensity: float = Field(ge=0.0, le=1.0)
    secondary_emotions: dict[str, float] = Field(default_factory=dict)
    detection_source: str = Field(min_length=1)
    synthesis_parameters: dict[str, Any]


def _observation_from_payload(data: object, provider_name: str) -> EmotionObservation:
    """Validate that a model returned measured fields instead of substituting defaults."""
    if not isinstance(data, dict):
        raise TypeError(f"{provider_name} returned an invalid emotion payload")
    required = {"primary_emotion", "confidence", "valence", "arousal", "dominance", "intensity"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"{provider_name} omitted emotion fields: {', '.join(sorted(missing))}")
    category = str(data["primary_emotion"]).lower()
    if category not in EMOTION_VAD_ANCHORS:
        raise ValueError(f"{provider_name} returned unsupported emotion {category!r}")
    secondary = data.get("secondary_emotions", {})
    if not isinstance(secondary, dict):
        raise TypeError(f"{provider_name} returned invalid secondary emotion scores")
    return EmotionObservation(
        dominant_category=category,
        confidence=float(data["confidence"]),
        valence=float(data["valence"]),
        arousal=float(data["arousal"]),
        dominance=float(data["dominance"]),
        intensity=float(data["intensity"]),
        secondary_emotions=secondary,
    )


class AcousticEmotionDetector:
    """Local, high-speed acoustic prosodic emotion analyzer."""

    def analyze_audio_features(
        self,
        audio_path: Path | str,
        start_s: float = 0.0,
        end_s: float | None = None,
    ) -> dict[str, float]:
        """Extract acoustic prosody features using librosa or soundfile."""
        path = Path(audio_path)
        if not path.is_file():
            raise FileNotFoundError(f"emotion analysis audio does not exist: {path}")
        if end_s is not None and end_s <= start_s:
            raise ValueError("emotion analysis end time must be after start time")

        try:
            import numpy as np
            import soundfile as sf

            with sf.SoundFile(str(path)) as f:
                sr = f.samplerate
                start_frame = int(start_s * sr)
                frames_to_read = -1 if end_s is None else int((end_s - start_s) * sr)
                f.seek(start_frame)
                data = f.read(frames=frames_to_read)

            if data.ndim > 1:
                data = np.mean(data, axis=1)

            if len(data) == 0:
                raise ValueError(f"emotion analysis audio segment is empty: {path}")

            # RMS energy
            rms = float(np.sqrt(np.mean(data**2)))
            if not math.isfinite(rms) or rms <= 1e-6:
                raise ValueError(f"emotion analysis audio contains no measurable signal: {path}")

            # Approximate F0 via autocorrelation
            autocorr = np.correlate(
                data[: min(len(data), 8000)], data[: min(len(data), 8000)], mode="full"
            )
            autocorr = autocorr[len(autocorr) // 2 :]
            # Search F0 in 60Hz - 400Hz range
            min_lag = int(sr / 400)
            max_lag = int(sr / 60)
            if max_lag >= len(autocorr) or max_lag <= min_lag:
                raise ValueError("audio segment is too short to estimate fundamental frequency")
            peak_lag = min_lag + int(np.argmax(autocorr[min_lag:max_lag]))
            if peak_lag <= 0:
                raise ValueError("audio segment did not yield a measurable fundamental frequency")
            f0 = float(sr / peak_lag)

            # Dynamic pitch range
            f0 = max(60.0, min(400.0, f0))

            # Spectral flux heuristic
            zcr = float(np.mean(np.abs(np.diff(np.sign(data)))) / 2.0)

            return {
                "f0_median": round(f0, 1),
                "rms_energy": round(rms, 4),
                "zcr": round(zcr, 4),
                "spectral_flux": round(min(1.0, zcr * 10.0), 3),
            }
        except (ImportError, OSError, RuntimeError) as exc:
            raise EmotionAnalysisUnavailableError(
                "Acoustic emotion analysis could not read this audio. Install soundfile and "
                "NumPy and verify that the audio file is readable."
            ) from exc

    def detect_emotion(
        self,
        audio_path: Path | str,
        start_s: float = 0.0,
        end_s: float | None = None,
    ) -> EmotionObservation:
        """Infer continuous VAD emotion from acoustic prosodic measurements."""
        feats = self.analyze_audio_features(audio_path, start_s, end_s)
        f0 = feats["f0_median"]
        rms = feats["rms_energy"]
        flux = feats["spectral_flux"]

        norm_energy = min(1.0, max(0.0, (rms - 0.01) / 0.15))
        norm_f0 = min(1.0, max(0.0, (f0 - 80.0) / 220.0))

        arousal = (norm_energy * 0.6 + norm_f0 * 0.4) * 2.0 - 1.0
        arousal = max(-1.0, min(1.0, arousal))

        valence = (1.0 - flux) * 1.5 - 0.75
        valence = max(-1.0, min(1.0, valence))

        dominance = max(-1.0, min(1.0, (norm_energy * 1.8 - 0.9)))
        intensity = max(0.1, min(1.0, abs(arousal) * 0.6 + abs(valence) * 0.4))

        best_cat = "neutral"
        min_dist = float("inf")
        for cat, (v, a, d) in EMOTION_VAD_ANCHORS.items():
            dist = math.sqrt((valence - v) ** 2 + (arousal - a) ** 2 + (dominance - d) ** 2)
            if dist < min_dist:
                min_dist = dist
                best_cat = cat

        return EmotionObservation(
            dominant_category=best_cat,
            confidence=round(max(0.0, min(1.0, 1.0 - min_dist / math.sqrt(12))), 2),
            valence=round(valence, 3),
            arousal=round(arousal, 3),
            dominance=round(dominance, 3),
            intensity=round(intensity, 3),
        )


class ContextualLlmEmotionDetector:
    """Dramatic contextual emotion detector running via LLM router or local model."""

    def __init__(self) -> None:
        pass

    def detect_emotion(
        self,
        utterance_id: str,
        dialogue_text: str,
        character_name: str = "Character",
        scene_context: str = "",
    ) -> EmotionObservation:
        """Infer deep dramatic emotion from dialogue text and scene context via LLM."""
        from aidub.providers.factory import build_router_from_config
        from aidub.providers.router import LlmRequest

        router = build_router_from_config()

        system_prompt = (
            "You are an expert film director and ADR performance analyst. "
            "Analyze the character's exact emotional state, dramatic intent, and continuous VAD coordinates "
            "(Valence: -1.0 to 1.0, Arousal: -1.0 to 1.0, Dominance: -1.0 to 1.0, Intensity: 0.0 to 1.0).\n"
            "Respond ONLY with a JSON object:\n"
            "{\n"
            '  "primary_emotion": "neutral|joy|anger|sadness|fear|surprise|disgust|anticipation|whisper|suspense|intense_confrontation|sarcastic|tender|despair|resolute",\n'
            '  "confidence": 0.95,\n'
            '  "valence": 0.0,\n'
            '  "arousal": 0.0,\n'
            '  "dominance": 0.0,\n'
            '  "intensity": 0.5,\n'
            '  "secondary_emotions": {"subtle_tension": 0.4}\n'
            "}"
        )

        user_prompt = (
            f"Scene Context: {scene_context}\n"
            f"Character Speaking: {character_name}\n"
            f'Dialogue Line: "{dialogue_text}"\n'
            "Analyze the emotional performance state:"
        )

        try:
            resp = router.complete(
                LlmRequest(
                    request_id=Identifier(f"emotion_{utterance_id}"),
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.1,
                    json_mode=True,
                )
            )
            return _observation_from_payload(json.loads(resp.content), "LLM emotion analysis")
        except Exception as exc:
            raise EmotionAnalysisUnavailableError(
                f"LLM emotion analysis failed without a usable result: {exc}"
            ) from exc


class KaggleLocalEmotionAdapter:
    """Connects to a Kaggle GPU or local model worker if configured."""

    def __init__(self, endpoint_url: str | None = None) -> None:
        self.endpoint_url: str = str(
            endpoint_url or os.getenv("KAGGLE_EMOTION_URL") or os.getenv("LOCAL_EMOTION_URL") or ""
        )

    def is_available(self) -> bool:
        return bool(self.endpoint_url.strip())

    def predict_audio_emotion(self, audio_path: Path | str) -> EmotionObservation | None:
        """Call remote Kaggle/Local GPU server for deep audio emotion recognition."""
        if not self.is_available():
            return None

        try:
            path = Path(audio_path)
            full_url = f"{self.endpoint_url.rstrip('/')}/predict_emotion"
            if not full_url.startswith(("http://", "https://")):
                return None
            req = urllib.request.Request(  # noqa: S310
                full_url,
                data=path.read_bytes(),
                headers={"Content-Type": "audio/wav"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
            return _observation_from_payload(data, "Configured emotion worker")
        except Exception as exc:
            logger.warning("Kaggle/Local emotion worker unavailable: %s", exc)
            return None


class EmotionEngine:
    """
    Unified Multimodal Emotion Detection and Performance Mapping Engine.

    Fuses acoustic analysis, LLM context, and optional Kaggle/local deep models
    to estimate film emotion states and map them to supported Edge TTS rate and pitch controls.
    """

    def __init__(self) -> None:
        self.acoustic_detector = AcousticEmotionDetector()
        self.context_detector = ContextualLlmEmotionDetector()
        self.kaggle_adapter = KaggleLocalEmotionAdapter()
        self.fast_analyzer = FastAcousticProsodyAnalyzer()
        self.cinematic_instructor = CinematicLlmInstructor()
        self.continual_learner = ContinualEmotionLearner()
        self.verifier_regenerator = EmotionVerifierAndRegenerator(self.fast_analyzer)
        self.director_controller = DirectorEmotionController(self.continual_learner)

    def detect_emotion(
        self,
        utterance_id: str,
        dialogue_text: str,
        audio_path: Path | str | None = None,
        character_name: str = "Character",
        scene_context: str = "",
        start_s: float = 0.0,
        end_s: float | None = None,
    ) -> EmotionDetectionResult:
        """Execute multimodal emotion detection with weighted Bayesian fusion."""
        # 0. Check Director Manual Override first
        override = self.director_controller.get_override(utterance_id)
        if override:
            cat = override["emotion_category"]
            v, a, d = EMOTION_VAD_ANCHORS.get(cat, (0.0, 0.0, 0.0))
            return EmotionDetectionResult(
                utterance_id=Identifier(utterance_id),
                primary_emotion=cat,
                confidence=1.0,
                valence=v,
                arousal=a,
                dominance=d,
                intensity=override["intensity"],
                secondary_emotions={"director_override": 1.0},
                detection_source="director_manual_override",
                synthesis_parameters={
                    "emotion_category": cat,
                    "base_rate": f"{override['rate_offset_percent']:+d}%",
                    "base_pitch": f"{override['pitch_offset_hz']:+d}Hz",
                },
            )

        acoustic_obs: EmotionObservation | None = None
        if audio_path is not None:
            # Check file existence to preserve contract expectations
            p = Path(audio_path)
            if not p.is_file():
                raise FileNotFoundError(f"emotion analysis audio does not exist: {p}")
            try:
                data, sr = self.fast_analyzer.read_audio_interval(p, start_s, end_s)
                feats = self.fast_analyzer.extract_features(data, sr)
                acoustic_obs = self.fast_analyzer.features_to_vad(feats)
            except Exception:
                # Fallback to acoustic_detector
                acoustic_obs = self.acoustic_detector.detect_emotion(audio_path, start_s, end_s)

        kaggle_obs: EmotionObservation | None = None
        if audio_path and self.kaggle_adapter.is_available():
            kaggle_obs = self.kaggle_adapter.predict_audio_emotion(audio_path)

        try:
            context_obs = self.context_detector.detect_emotion(
                utterance_id=utterance_id,
                dialogue_text=dialogue_text,
                character_name=character_name,
                scene_context=scene_context,
            )
        except EmotionAnalysisUnavailableError:
            if acoustic_obs is None and kaggle_obs is None:
                raise
            context_obs = None

        if kaggle_obs is not None:
            primary_cat = kaggle_obs.dominant_category
            confidence = kaggle_obs.confidence
            v, a, d = kaggle_obs.valence, kaggle_obs.arousal, kaggle_obs.dominance
            intensity = kaggle_obs.intensity
            source = "kaggle_audio_model"
            if context_obs is not None:
                v = kaggle_obs.valence * 0.6 + context_obs.valence * 0.4
                a = kaggle_obs.arousal * 0.6 + context_obs.arousal * 0.4
                d = kaggle_obs.dominance * 0.6 + context_obs.dominance * 0.4
                source = "kaggle_audio_model_and_llm"
        elif acoustic_obs is not None:
            if context_obs is None:
                primary_cat = acoustic_obs.dominant_category
                confidence = acoustic_obs.confidence
                v, a, d = acoustic_obs.valence, acoustic_obs.arousal, acoustic_obs.dominance
                intensity = acoustic_obs.intensity
                source = "acoustic_prosody_heuristic"
            else:
                primary_cat = context_obs.dominant_category
                confidence = round(context_obs.confidence * 0.6 + acoustic_obs.confidence * 0.4, 2)
                v = round(context_obs.valence * 0.65 + acoustic_obs.valence * 0.35, 3)
                a = round(acoustic_obs.arousal * 0.65 + context_obs.arousal * 0.35, 3)
                d = round(context_obs.dominance * 0.5 + acoustic_obs.dominance * 0.5, 3)
                intensity = round(max(acoustic_obs.intensity, context_obs.intensity), 3)
                source = "acoustic_prosody_and_llm"
        else:
            assert context_obs is not None
            primary_cat = context_obs.dominant_category
            confidence = context_obs.confidence
            v, a, d = context_obs.valence, context_obs.arousal, context_obs.dominance
            intensity = context_obs.intensity
            source = "contextual_llm"

        synthesis_params = self.map_synthesis_parameters(
            primary_cat, intensity=intensity, arousal=a, character_id=character_name
        )
        measured_observation = context_obs or kaggle_obs or acoustic_obs
        assert measured_observation is not None

        return EmotionDetectionResult(
            utterance_id=Identifier(utterance_id),
            primary_emotion=primary_cat,
            confidence=round(confidence, 2),
            valence=v,
            arousal=a,
            dominance=d,
            intensity=intensity,
            secondary_emotions=measured_observation.secondary_emotions,
            detection_source=source,
            synthesis_parameters=synthesis_params,
        )

    def map_synthesis_parameters(
        self,
        emotion_category: str,
        intensity: float,
        arousal: float,
        character_id: str = "DEFAULT",
    ) -> dict[str, Any]:
        """Convert detected emotion into Edge-TTS & RVC synthesis parameters with learned fine-tuning."""
        cat = emotion_category.lower()
        if cat not in EDGE_TTS_STYLE_MAP:
            cat = "neutral"
        preset = EDGE_TTS_STYLE_MAP.get(cat, EDGE_TTS_STYLE_MAP["neutral"])
        base_rate_percent = int(preset["rate"].removesuffix("%"))
        adjusted_rate = round(base_rate_percent + arousal * 8 * intensity)
        base_pitch_hz = int(preset["pitch"].removesuffix("Hz"))
        adjusted_pitch = round(base_pitch_hz + arousal * 10 * intensity)

        # Incorporate online continual learning bias if available
        learned_pitch, learned_rate = self.continual_learner.get_learned_prosody_offset(
            character_id, cat
        )
        adjusted_pitch += learned_pitch
        adjusted_rate += learned_rate

        return {
            "emotion_category": cat,
            "base_rate": f"{adjusted_rate:+d}%",
            "base_pitch": f"{adjusted_pitch:+d}Hz",
        }

    def synthesize_verified_line(
        self,
        text: str,
        output_path: Path,
        synth_fn: Callable[[str, Path, str, str], Any],
        utterance_id: str,
        character_name: str = "Character",
        audio_path: Path | str | None = None,
        start_s: float = 0.0,
        end_s: float | None = None,
        scene_context: str = "",
        target_duration_s: float | None = None,
    ) -> tuple[EmotionDetectionResult, EmotionVerificationReport]:
        """
        Closed-loop synthesis: detects emotion, applies learned bias and director overrides,
        synthesizes, verifies acoustic output, and auto-regenerates if below accuracy threshold.
        """
        detection = self.detect_emotion(
            utterance_id=utterance_id,
            dialogue_text=text,
            audio_path=audio_path,
            character_name=character_name,
            scene_context=scene_context,
            start_s=start_s,
            end_s=end_s,
        )

        params = detection.synthesis_parameters
        base_rate = params.get("base_rate", "+0%")
        base_pitch = params.get("base_pitch", "+0Hz")

        target_obs = EmotionObservation(
            dominant_category=detection.primary_emotion,
            confidence=detection.confidence,
            valence=detection.valence,
            arousal=detection.arousal,
            dominance=detection.dominance,
            intensity=detection.intensity,
        )

        # Execute closed-loop verification and auto-regeneration
        report = self.verifier_regenerator.synthesize_with_closed_loop_verification(
            text=text,
            output_path=output_path,
            synth_fn=synth_fn,
            target_intent=target_obs,
            base_rate=base_rate,
            base_pitch=base_pitch,
            target_duration_s=target_duration_s,
        )

        # Continual Online Learning update: fine-tune model weights with this result
        self.continual_learner.record_performance_feedback(
            character_id=character_name,
            emotion_category=detection.primary_emotion,
            applied_pitch_hz=report.corrective_pitch_applied_hz,
            applied_rate_percent=report.corrective_rate_applied_percent,
            verified_accuracy=report.accuracy_score,
            manual_override=self.director_controller.is_locked(utterance_id),
        )

        return detection, report

    def build_performance_state(
        self,
        utterance_id: str,
        detection: EmotionDetectionResult,
        target_override: str | None = None,
    ) -> PerformanceEmotionState:
        """Create full PerformanceEmotionState for director overrides and synthesis."""
        target_cat = target_override or detection.primary_emotion
        if target_cat not in EMOTION_VAD_ANCHORS:
            raise ValueError(f"Unsupported emotion override {target_cat!r}")
        target_v, target_a, target_d = EMOTION_VAD_ANCHORS[target_cat]

        source_obs = EmotionObservation(
            dominant_category=detection.primary_emotion,
            confidence=detection.confidence,
            valence=detection.valence,
            arousal=detection.arousal,
            dominance=detection.dominance,
            intensity=detection.intensity,
            secondary_emotions=detection.secondary_emotions,
        )

        target_obs = EmotionObservation(
            dominant_category=target_cat,
            confidence=1.0,
            valence=target_v,
            arousal=target_a,
            dominance=target_d,
            intensity=detection.intensity,
        )

        return PerformanceEmotionState(
            utterance_id=Identifier(utterance_id),
            source_observation=source_obs,
            target_intent=target_obs,
            actual_parameters=detection.synthesis_parameters,
        )


def compute_vad_distance(
    vad1: tuple[float, float, float],
    vad2: tuple[float, float, float],
    weights: tuple[float, float, float] = (0.35, 0.40, 0.25),
) -> float:
    """
    Weighted Euclidean distance between two points in continuous Valence-Arousal-Dominance space.
    """
    wv, wa, wd = weights
    v1, a1, d1 = vad1
    v2, a2, d2 = vad2
    dist_sq = wv * (v1 - v2) ** 2 + wa * (a1 - a2) ** 2 + wd * (d1 - d2) ** 2
    return round(math.sqrt(dist_sq), 4)


def compute_continuous_prosody_params(
    valence: float,
    arousal: float,
    dominance: float,
) -> dict[str, Any]:
    """
    Map continuous 3D VAD coordinates directly to physical synthesis parameters:
      - Pitch shift (Hz)
      - Rate multiplier (%)
      - Gain / Volume (dB)
    """
    # Clamp coordinates to [-1.0, 1.0]
    v = max(-1.0, min(1.0, float(valence)))
    a = max(-1.0, min(1.0, float(arousal)))
    d = max(-1.0, min(1.0, float(dominance)))

    pitch_hz = round(14.0 * a + 6.0 * v)
    rate_pct = round(12.0 * a - 8.0 * max(0.0, -v))
    volume_db = round(4.0 * a + 2.0 * d, 1)

    pitch_str = f"+{pitch_hz}Hz" if pitch_hz >= 0 else f"{pitch_hz}Hz"
    rate_str = f"+{rate_pct}%" if rate_pct >= 0 else f"{rate_pct}%"

    return {
        "pitch": pitch_str,
        "rate": rate_str,
        "volume_db": volume_db,
        "vad": (round(v, 3), round(a, 3), round(d, 3)),
    }


__all__ = [
    "EDGE_TTS_STYLE_MAP",
    "EMOTION_VAD_ANCHORS",
    "AcousticEmotionDetector",
    "CinematicLlmInstructor",
    "ContextualLlmEmotionDetector",
    "ContinualEmotionLearner",
    "DirectorEmotionController",
    "EmotionAnalysisUnavailableError",
    "EmotionDetectionResult",
    "EmotionEngine",
    "EmotionVerificationReport",
    "EmotionVerifierAndRegenerator",
    "FastAcousticProsodyAnalyzer",
    "KaggleLocalEmotionAdapter",
    "compute_continuous_prosody_params",
    "compute_vad_distance",
]
