"""
Lip-Sync Viseme Mapping, Syllable Kinematics, and ITU-R BT.1359 Synchronization Engine.

Provides frame-accurate viseme classification, grapheme-to-viseme (G2V) conversion
for English and Bengali dialogue, mouth kinematics calculation, and slip-and-slide
synchronization scoring.
"""

from __future__ import annotations

import enum
import logging
import math
import re
from dataclasses import dataclass, field
from typing import ClassVar

logger = logging.getLogger(__name__)


class VisemeGroup(enum.Enum):
    """
    Standard Disney / MPEG-4 visual mouth shape groups (Visemes).
    """

    SILENCE = "silence"            # Mouth resting, lips closed or slightly parted
    BILABIAL = "bilabial"          # B, P, M (lips firmly closed together)
    LABIODENTAL = "labiodental"    # F, V (upper incisors on lower lip)
    DENTAL_ALVEOLAR = "dental"     # T, D, S, Z, N, L (teeth close, tongue to alveolar ridge)
    VELAR_PALATAL = "velar"        # K, G, NG, SH, CH, J (mid/back tongue arching)
    OPEN_VOWEL = "open_vowel"      # AA, AH, AY, AW (jaw open, maximum vertical aperture)
    ROUNDED_VOWEL = "rounded_vowel"# OO, UW, OW, W (lips rounded, puckered aperture)
    SPREAD_VOWEL = "spread_vowel"  # EE, IH, EY (horizontal lip corner retraction)


@dataclass
class VisemeGeometry:
    """Normalized mouth geometric aperture coordinates (0.0 to 1.0)."""

    openness: float    # 0.0 = completely shut, 1.0 = fully open jaw
    width: float       # 0.0 = puckered / rounded, 1.0 = wide smile / spread
    lip_protrusion: float  # 0.0 = flat, 1.0 = fully protruded puckered lips
    teeth_visible: bool    # True if upper or lower dentition is exposed


# Static anatomical mouth geometry definitions per viseme group
VISEME_GEOMETRIES: dict[VisemeGroup, VisemeGeometry] = {
    VisemeGroup.SILENCE: VisemeGeometry(openness=0.05, width=0.50, lip_protrusion=0.05, teeth_visible=False),
    VisemeGroup.BILABIAL: VisemeGeometry(openness=0.00, width=0.52, lip_protrusion=0.10, teeth_visible=False),
    VisemeGroup.LABIODENTAL: VisemeGeometry(openness=0.15, width=0.58, lip_protrusion=0.12, teeth_visible=True),
    VisemeGroup.DENTAL_ALVEOLAR: VisemeGeometry(openness=0.20, width=0.65, lip_protrusion=0.08, teeth_visible=True),
    VisemeGroup.VELAR_PALATAL: VisemeGeometry(openness=0.35, width=0.55, lip_protrusion=0.15, teeth_visible=False),
    VisemeGroup.OPEN_VOWEL: VisemeGeometry(openness=0.88, width=0.62, lip_protrusion=0.10, teeth_visible=True),
    VisemeGroup.ROUNDED_VOWEL: VisemeGeometry(openness=0.45, width=0.25, lip_protrusion=0.85, teeth_visible=False),
    VisemeGroup.SPREAD_VOWEL: VisemeGeometry(openness=0.30, width=0.88, lip_protrusion=0.02, teeth_visible=True),
}


@dataclass
class VisemeCue:
    """Time-stamped viseme segment within a dialogue line."""

    viseme: VisemeGroup
    start_s: float
    end_s: float
    label: str
    geometry: VisemeGeometry = field(init=False)

    def __post_init__(self) -> None:
        self.geometry = VISEME_GEOMETRIES.get(self.viseme, VISEME_GEOMETRIES[VisemeGroup.SILENCE])

    @property
    def duration_s(self) -> float:
        return max(0.001, self.end_s - self.start_s)


@dataclass
class LipSyncComplianceReport:
    """ITU-R BT.1359-1 Compliance and slip-and-slide alignment metric report."""

    offset_ms: float                # Applied audio offset in milliseconds
    compliance_score: float         # 0.0 to 1.0 (1.0 = flawless alignment)
    is_broadcast_compliant: bool   # Within ITU-R BT.1359-1 (-45ms to +125ms)
    lead_lag_status: str            # "In Sync", "Audio Leading Video", "Audio Lagging Video"
    total_visemes: int
    open_mouth_duration_s: float
    remediation_advice: str


class LipSyncVisemeEngine:
    """
    Automated Grapheme-to-Viseme (G2V) Kinematic Modeling and Alignment Engine.
    """

    # English Phoneme/Grapheme patterns -> Viseme
    EN_PATTERNS: ClassVar[list[tuple[re.Pattern[str], VisemeGroup, str]]] = [
        (re.compile(r"\b(p|b|m)", re.IGNORECASE), VisemeGroup.BILABIAL, "B/P/M"),
        (re.compile(r"\b(f|v|ph)", re.IGNORECASE), VisemeGroup.LABIODENTAL, "F/V"),
        (re.compile(r"\b(t|d|s|z|th)", re.IGNORECASE), VisemeGroup.DENTAL_ALVEOLAR, "T/D/S"),
        (re.compile(r"\b(k|g|ng|ch|j|sh)", re.IGNORECASE), VisemeGroup.VELAR_PALATAL, "K/G/SH"),
        (re.compile(r"\b(oo|u|w|ow)", re.IGNORECASE), VisemeGroup.ROUNDED_VOWEL, "OO/UW"),
        (re.compile(r"\b(ee|ea|i|y)", re.IGNORECASE), VisemeGroup.SPREAD_VOWEL, "EE/IH"),
        (re.compile(r"\b(a|ah|aw|o)", re.IGNORECASE), VisemeGroup.OPEN_VOWEL, "AA/AH"),
    ]

    # Bengali Phoneme/Glyph mappings -> Viseme
    BN_PATTERNS: ClassVar[list[tuple[re.Pattern[str], VisemeGroup, str]]] = [
        (re.compile(r"[পফবভম]"), VisemeGroup.BILABIAL, "ব/প/ম"),
        (re.compile(r"[তথদধনলসশষ]"), VisemeGroup.DENTAL_ALVEOLAR, "ত/দ/স"),
        (re.compile(r"[টঠডঢণরড়ঢ়]"), VisemeGroup.DENTAL_ALVEOLAR, "ট/ড/র"),
        (re.compile(r"[কখগঘঙচছজঝঞ]"), VisemeGroup.VELAR_PALATAL, "ক/গ/চ"),
        (re.compile(r"[উঊুূওোৌ]"), VisemeGroup.ROUNDED_VOWEL, "উ/ও"),
        (re.compile(r"[ইঈিীএেঐৈ]"), VisemeGroup.SPREAD_VOWEL, "ই/এ"),
        (re.compile(r"[অআইাআ]"), VisemeGroup.OPEN_VOWEL, "আ/অ"),
    ]

    @classmethod
    def generate_viseme_timeline(
        cls,
        text: str,
        start_time_s: float,
        duration_s: float,
        language: str = "bn",
    ) -> list[VisemeCue]:
        """
        Generate time-aligned sequence of mouth visemes for a dialogue line.

        Distributes visemes evenly across available duration with realistic
        speech coarticulation transitions and closing bilabials.
        """
        dur = max(0.1, duration_s)
        clean_text = text.strip()
        if not clean_text:
            return [VisemeCue(VisemeGroup.SILENCE, start_time_s, start_time_s + dur, "Silence")]

        is_bn = language.lower().startswith("bn")
        tokens = re.findall(r"\w+", clean_text)
        if not tokens:
            tokens = [clean_text]

        extracted_visemes: list[tuple[VisemeGroup, str]] = []

        # Map each token or character
        patterns = cls.BN_PATTERNS if is_bn else cls.EN_PATTERNS
        for token in tokens:
            matched_for_token = False
            for pat, vis, lbl in patterns:
                if pat.search(token):
                    extracted_visemes.append((vis, lbl))
                    matched_for_token = True
            if not matched_for_token:
                # Default open vowel for vocalized vowels, dental for consonants
                extracted_visemes.append((VisemeGroup.OPEN_VOWEL, "AA"))

        if not extracted_visemes:
            extracted_visemes = [(VisemeGroup.OPEN_VOWEL, "AA"), (VisemeGroup.BILABIAL, "M")]

        # Calculate time slots with pre-roll and post-roll resting phases
        pre_roll = 0.05
        post_roll = 0.05
        active_dur = max(0.05, dur - (pre_roll + post_roll))
        slot_dur = active_dur / len(extracted_visemes)

        cues: list[VisemeCue] = []
        # Pre-roll initial silence
        cues.append(
            VisemeCue(
                VisemeGroup.SILENCE,
                start_time_s,
                start_time_s + pre_roll,
                "Rest",
            )
        )

        cursor = start_time_s + pre_roll
        for vis, lbl in extracted_visemes:
            cues.append(VisemeCue(vis, cursor, cursor + slot_dur, lbl))
            cursor += slot_dur

        # Post-roll final rest
        cues.append(
            VisemeCue(
                VisemeGroup.SILENCE,
                cursor,
                start_time_s + dur,
                "Rest",
            )
        )

        return cues

    @classmethod
    def evaluate_lip_sync_compliance(
        cls,
        cues: list[VisemeCue],
        offset_ms: float = 0.0,
    ) -> LipSyncComplianceReport:
        """
        Evaluate Lip-Sync compliance against ITU-R BT.1359-1 standards.

        ITU-R BT.1359-1 broadcast tolerance limits:
        - Audio Leading Video: -45 ms (imperceptible)
        - Audio Lagging Video: +125 ms (imperceptible)
        - Noticeable threshold: < -90 ms or > +185 ms
        """
        # Score decay with offset
        # Gaussian envelope centered at 0ms, asymmetrical for lead vs lag
        if offset_ms < 0:
            # Audio leads video (stricter: 45ms sigma)
            sigma = 45.0
            status = "Audio Leading Video" if abs(offset_ms) > 10 else "In Sync"
        else:
            # Audio lags video (more lenient: 95ms sigma)
            sigma = 95.0
            status = "Audio Lagging Video" if offset_ms > 10 else "In Sync"

        gaussian_score = math.exp(-pow(offset_ms / (sigma * 1.414), 2))
        compliance_score = max(0.0, min(1.0, round(gaussian_score, 3)))

        is_compliant = (-45.0 <= offset_ms <= 125.0)

        open_dur = sum(
            c.duration_s for c in cues
            if c.viseme in {VisemeGroup.OPEN_VOWEL, VisemeGroup.SPREAD_VOWEL, VisemeGroup.ROUNDED_VOWEL}
        )

        if is_compliant:
            advice = (
                f"✓ Broadcast Compliant (ITU-R BT.1359-1): Audio timing offset ({offset_ms:+.1f}ms) "
                f"is within the imperceptible broadcast lip-sync window."
            )
        elif offset_ms < -45.0:
            advice = (
                f"⚠ Noticeable Audio Lead ({offset_ms:.1f}ms): Audio begins before actor's lips move. "
                f"Slip audio forward by {abs(offset_ms):.1f}ms."
            )
        else:
            advice = (
                f"⚠ Noticeable Audio Lag (+{offset_ms:.1f}ms): Actor's lips open before dialogue starts. "
                f"Slip audio backward by {offset_ms:.1f}ms."
            )

        return LipSyncComplianceReport(
            offset_ms=offset_ms,
            compliance_score=compliance_score,
            is_broadcast_compliant=is_compliant,
            lead_lag_status=status,
            total_visemes=len(cues),
            open_mouth_duration_s=round(open_dur, 2),
            remediation_advice=advice,
        )

    @classmethod
    def interpolate_mouth_geometry(cls, cues: list[VisemeCue], playhead_s: float) -> VisemeGeometry:
        """
        Compute smooth coarticulated mouth geometry for any arbitrary playhead time.
        """
        if not cues:
            return VISEME_GEOMETRIES[VisemeGroup.SILENCE]

        # Find current and adjacent cue for linear interpolation
        for i, cue in enumerate(cues):
            if cue.start_s <= playhead_s <= cue.end_s:
                target_geom = cue.geometry
                # Smooth transition from previous cue near boundary
                progress = (playhead_s - cue.start_s) / max(0.001, cue.duration_s)
                if i > 0 and progress < 0.20:
                    prev_geom = cues[i - 1].geometry
                    factor = progress / 0.20
                    return VisemeGeometry(
                        openness=(1.0 - factor) * prev_geom.openness + factor * target_geom.openness,
                        width=(1.0 - factor) * prev_geom.width + factor * target_geom.width,
                        lip_protrusion=(1.0 - factor) * prev_geom.lip_protrusion + factor * target_geom.lip_protrusion,
                        teeth_visible=target_geom.teeth_visible or prev_geom.teeth_visible,
                    )
                return target_geom

        if playhead_s < cues[0].start_s:
            return cues[0].geometry
        return cues[-1].geometry


__all__ = [
    "VISEME_GEOMETRIES",
    "LipSyncComplianceReport",
    "LipSyncVisemeEngine",
    "VisemeCue",
    "VisemeGeometry",
    "VisemeGroup",
]
