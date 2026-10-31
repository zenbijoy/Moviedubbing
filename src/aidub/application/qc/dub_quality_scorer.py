"""Dub quality scorer: heuristic score 0-100."""
from __future__ import annotations

import math


class DubQualityScorer:
    @staticmethod
    def score(sync_error_ms: float, loudness_diff_lu: float, peak_dbtp: float, clipping: bool) -> dict:
        sync_score = max(0.0, 100.0 - abs(sync_error_ms) / 5.0)
        loud_score = max(0.0, 100.0 - abs(loudness_diff_lu) * 10.0)
        peak_score = 100.0 if peak_dbtp <= -1.0 else max(0.0, 100.0 - (peak_dbtp + 1.0) * 20.0)
        clip_pen = 0.0 if not clipping else 30.0
        total = (sync_score * 0.4 + loud_score * 0.3 + peak_score * 0.3) - clip_pen
        total = max(0.0, min(100.0, total))
        grade = "A" if total >= 90 else "B" if total >= 75 else "C" if total >= 60 else "D"
        return {"score": round(total, 2), "grade": grade, "sync_score": round(sync_score, 2),
                "loudness_score": round(loud_score, 2), "peak_score": round(peak_score, 2)}


__all__ = ["DubQualityScorer"]
