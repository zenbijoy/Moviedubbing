"""Bangla movie dubbing toolkit part 1: text and timing helpers."""
from __future__ import annotations

import math
import re
from typing import Any

import numpy as np

BN_DIGITS = "০১২৩৪৫৬৭৮৯"
EN_DIGITS = "0123456789"


class BanglaDubbingToolkit:
    # ---- Text / Bangla ----
    @staticmethod
    def normalize_bangla_digits(text: str) -> str:
        table = str.maketrans(BN_DIGITS, EN_DIGITS)
        return text.translate(table)

    @staticmethod
    def to_bangla_digits(text: str) -> str:
        table = str.maketrans(EN_DIGITS, BN_DIGITS)
        return text.translate(table)

    @staticmethod
    def remove_extra_spaces(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def fix_bangla_punctuation(text: str) -> str:
        text = text.replace(" ,", ",").replace(" .", ".").replace(" ?", "?").replace(" !", "!")
        return BanglaDubbingToolkit.remove_extra_spaces(text)

    @staticmethod
    def count_syllables_bn(text: str) -> int:
        vowels = "অআইঈউঊঋএঐওঔািীুূৃেৈোৌ"
        count = 0
        prev_vowel = False
        for ch in text:
            is_v = ch in vowels
            if is_v and not prev_vowel:
                count += 1
            prev_vowel = is_v
        return max(1, count) if text.strip() else 0

    @staticmethod
    def estimate_speech_duration(text: str, chars_per_sec: float = 12.0) -> float:
        if chars_per_sec <= 0:
            return 0.0
        return len(text) / chars_per_sec

    @staticmethod
    def split_into_sentences_bn(text: str) -> list[str]:
        parts = re.split(r"(?<=[।!?])\s+", text.strip())
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def wrap_text(text: str, width: int = 40) -> list[str]:
        if width <= 0:
            return [text]
        lines = []
        cur = ""
        for word in text.split():
            if len(cur) + len(word) + 1 <= width:
                cur = (cur + " " + word).strip()
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    @staticmethod
    def detect_language(text: str) -> str:
        bn = sum(1 for c in text if "\u0980" <= c <= "\u09ff")
        en = sum(1 for c in text if c.isascii() and c.isalpha())
        if bn == 0 and en == 0:
            return "unknown"
        return "bn" if bn >= en else "en"

    @staticmethod
    def normalize_quotes(text: str) -> str:
        return text.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")

    # ---- Timing ----
    @staticmethod
    def ms_to_s(ms: float) -> float:
        return ms / 1000.0

    @staticmethod
    def s_to_ms(s: float) -> float:
        return s * 1000.0

    @staticmethod
    def clamp_time(t: float, lo: float = 0.0, hi: float = 1e9) -> float:
        return max(lo, min(hi, t))

    @staticmethod
    def snap_to_frame(t: float, fps: float = 25.0) -> float:
        if fps <= 0:
            return t
        return round(t * fps) / fps

    @staticmethod
    def frames_for_duration(dur_s: float, fps: float = 25.0) -> int:
        return int(round(dur_s * fps))

    @staticmethod
    def align_cue_to_shot(cue_start: float, shot_start: float, shot_end: float) -> float:
        if cue_start < shot_start:
            return shot_start
        if cue_start > shot_end:
            return shot_end
        return cue_start

    @staticmethod
    def compute_gap(a_end: float, b_start: float) -> float:
        return b_start - a_end

    @staticmethod
    def merge_overlapping_cues(cues):
        if not cues:
            return []
        sorted_c = sorted(cues, key=lambda c: c[0])
        merged = [list(sorted_c[0])]
        for s, e, t in sorted_c[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
                merged[-1][2] = merged[-1][2] + " " + t
            else:
                merged.append([s, e, t])
        return [(m[0], m[1], m[2]) for m in merged]

    @staticmethod
    def sort_cues(cues):
        return sorted(cues, key=lambda c: (c[0], c[1]))

    @staticmethod
    def validate_cue_order(cues):
        for i in range(len(cues) - 1):
            if cues[i][0] > cues[i + 1][0]:
                return False
        return True


    @staticmethod
    def transliterate_bn_to_latin(text):
        return text

    @staticmethod
    def zero_crossing_trim(samples):
        if samples.size == 0:
            return samples
        # trim leading/trailing to zero crossing
        i = 0
        while i < samples.size and abs(samples[i]) > 1e-4:
            i += 1
        j = samples.size - 1
        while j > i and abs(samples[j]) > 1e-4:
            j -= 1
        return samples[i:j+1]


    # ---- Audio ----
    @staticmethod
    def db_to_linear(db):
        return 10.0 ** (db / 20.0)

    @staticmethod
    def linear_to_db(x):
        if x <= 0:
            return -120.0
        return 20.0 * __import__("math").log10(x)

    @staticmethod
    def trim_silence(samples, threshold=0.01):
        if samples.size == 0:
            return samples
        mask = __import__("numpy").abs(samples) >= threshold
        if not mask.any():
            return __import__("numpy").array([], dtype=samples.dtype)
        idx = __import__("numpy").where(mask)[0]
        return samples[idx[0]:idx[-1] + 1]

    @staticmethod
    def peak_normalize(samples, target_peak=1.0):
        if samples.size == 0:
            return samples
        peak = float(__import__("numpy").max(__import__("numpy").abs(samples)))
        if peak < 1e-9:
            return samples
        return (samples * (target_peak / peak)).astype(samples.dtype)

    @staticmethod
    def rms(samples):
        if samples.size == 0:
            return 0.0
        return float(__import__("numpy").sqrt(__import__("numpy").mean(samples ** 2)))

    @staticmethod
    def snr_estimate(signal, noise):
        ps = BanglaDubbingToolkit.rms(signal)
        pn = BanglaDubbingToolkit.rms(noise)
        if pn < 1e-9:
            return 120.0
        return 20.0 * __import__("math").log10(ps / pn)

    @staticmethod
    def detect_clipping(samples, threshold=0.99):
        if samples.size == 0:
            return False
        return bool(__import__("numpy").max(__import__("numpy").abs(samples)) >= threshold)

    @staticmethod
    def channel_count(samples):
        if samples.ndim == 1:
            return 1
        return samples.shape[1] if samples.ndim > 1 else 1

    @staticmethod
    def lufs_approx(samples):
        r = BanglaDubbingToolkit.rms(samples)
        if r < 1e-9:
            return -120.0
        return 20.0 * __import__("math").log10(r) - 0.691

    @staticmethod
    def true_peak_approx(samples):
        if samples.size == 0:
            return -120.0
        up = __import__("numpy").interp(__import__("numpy").linspace(0, samples.size - 1, samples.size * 4), __import__("numpy").arange(samples.size), samples)
        peak = float(__import__("numpy").max(__import__("numpy").abs(up))) if up.size else 0.0
        if peak < 1e-9:
            return -120.0
        return 20.0 * __import__("math").log10(peak)

    @staticmethod
    def check_compliance(lufs, true_peak, target_lufs=-24.0, max_tp=-1.0):
        return abs(lufs - target_lufs) <= 1.0 and true_peak <= max_tp

    @staticmethod
    def suggest_gain(current_lufs, target_lufs):
        return target_lufs - current_lufs

    @staticmethod
    def silence_percent(samples, threshold=0.01):
        if samples.size == 0:
            return 100.0
        silent = __import__("numpy").sum(__import__("numpy").abs(samples) < threshold)
        return 100.0 * silent / samples.size

    @staticmethod
    def format_timecode(seconds, fps=25.0):
        if seconds < 0:
            seconds = 0.0
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        f = int(round((seconds - int(seconds)) * fps))
        return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

    @staticmethod
    def parse_timecode(tc, fps=25.0):
        parts = tc.split(":")
        if len(parts) != 4:
            return 0.0
        h, m, s, f = [int(p) for p in parts]
        return h * 3600 + m * 60 + s + f / fps

    @staticmethod
    def sanitize_filename(name):
        return __import__("re").sub(r"[^A-Za-z0-9._-]", "_", name)

    @staticmethod
    def generate_cue_id(index):
        return f"cue_{index:04d}"

    @staticmethod
    def hash_text(text):
        import hashlib
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    @staticmethod
    def color_for_track(track):
        palette = {"A1": "#4FC3F7", "A2": "#81C784", "V1": "#FFB74D", "default": "#B0BEC5"}
        return palette.get(track, palette["default"])

    @staticmethod
    def progress_percent(done, total):
        if total <= 0:
            return 100.0
        return 100.0 * done / total

    @staticmethod
    def eta_seconds(remaining, rate_per_sec):
        if rate_per_sec <= 0:
            return float("inf")
        return remaining / rate_per_sec

    @staticmethod
    def clamp_value(v, lo, hi):
        return max(lo, min(hi, v))

    @staticmethod
    def round_half_up(v, ndigits=0):
        factor = 10 ** ndigits
        return __import__("math").floor(v * factor + 0.5) / factor

    @staticmethod
    def safe_divide(a, b, default=0.0):
        if b == 0:
            return default
        return a / b

    @staticmethod
    def bytes_to_mb(b):
        return b / (1024 * 1024)

    @staticmethod
    def format_duration_human(seconds):
        if seconds < 60:
            return f"{seconds:.1f}s"
        m = int(seconds // 60)
        s = seconds % 60
        if m < 60:
            return f"{m}m {s:.0f}s"
        h = m // 60
        m = m % 60
        return f"{h}h {m}m"

    @staticmethod
    def is_valid_path(path):
        return isinstance(path, str) and len(path) > 0

    @staticmethod
    def version_string(major, minor, patch):
        return f"{major}.{minor}.{patch}"
