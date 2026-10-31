"""Voice consistency checker across takes."""
from __future__ import annotations

from aidub.application.voice.speaker_similarity import SpeakerSimilarity


class VoiceConsistencyChecker:
    def __init__(self, threshold: float = 0.85) -> None:
        self.threshold = threshold

    def check(self, embeddings: list[list[float]]) -> dict:
        if len(embeddings) < 2:
            return {"consistent": True, "min_similarity": 1.0, "pairs": []}
        sims = []
        pairs = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                s = SpeakerSimilarity.cosine(embeddings[i], embeddings[j])
                sims.append(s)
                pairs.append((i, j, s))
        min_sim = min(sims) if sims else 1.0
        return {
            "consistent": min_sim >= self.threshold,
            "min_similarity": round(min_sim, 4),
            "pairs": pairs,
        }


__all__ = ["VoiceConsistencyChecker"]
