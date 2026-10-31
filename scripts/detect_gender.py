import json
import sys
from pathlib import Path
import numpy as np
import soundfile as sf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def estimate_f0(audio: np.ndarray, sr: int) -> float:
    """Estimate fundamental frequency (pitch) using normalized autocorrelation."""
    if len(audio) < sr * 0.15:
        return 0.0
    # Center window
    start_idx = int(len(audio) * 0.15)
    end_idx = int(len(audio) * 0.85)
    frame = audio[start_idx:end_idx]
    if len(frame) < 1024:
        return 0.0

    # Remove DC offset
    frame = frame - np.mean(frame)

    # Autocorrelation
    corr = np.correlate(frame, frame, mode="full")
    corr = corr[len(corr) // 2:]

    # Human voice pitch search range: 80 Hz to 350 Hz
    min_lag = int(sr / 350)
    max_lag = int(sr / 80)
    if max_lag >= len(corr) or min_lag >= max_lag:
        return 0.0

    peak_lag = min_lag + np.argmax(corr[min_lag:max_lag])
    if peak_lag == 0:
        return 0.0
    f0 = sr / peak_lag
    return float(f0)


def classify_speaker_gender(audio_path: str, asr_json: str):
    origin, sr = sf.read(audio_path)
    if origin.ndim > 1:
        origin = origin.mean(axis=1)

    segs = json.loads(Path(asr_json).read_text(encoding="utf-8"))
    print("=" * 65, flush=True)
    print("🎙️ ACOUSTIC GENDER CLASSIFICATION (PITCH / F0 ANALYSIS)", flush=True)
    print("=" * 65, flush=True)

    results = []
    for i, s in enumerate(segs):
        st = int(s["start"] * sr)
        en = int(s["end"] * sr)
        chunk = origin[st:en]
        f0 = estimate_f0(chunk, sr)
        
        # Gender threshold: Male voices ~90-165Hz, Female voices ~175-270Hz
        gender = "FEMALE" if f0 > 175 else "MALE"
        confidence = "High" if (f0 < 150 or f0 > 190) else "Medium"
        voice_assigned = "bn-BD-NabanitaNeural (Female)" if gender == "FEMALE" else "bn-BD-PradeepNeural (Male)"
        
        results.append({
            "segment": i,
            "start": s["start"],
            "end": s["end"],
            "f0_hz": round(f0, 1),
            "gender": gender,
            "confidence": confidence,
            "voice": voice_assigned,
            "text": s.get("text", "")[:40],
        })
        print(f"Segment {i} ({s['start']:.1f}s - {s['end']:.1f}s): F0 = {f0:.1f} Hz [{gender}] -> {voice_assigned}", flush=True)
        print(f"  Dialogue: {s.get('text', '')[:50]}", flush=True)

    return results


if __name__ == "__main__":
    classify_speaker_gender(
        "exports/test_verified_work/origin_audio.wav",
        "exports/test_verified_work/asr_segments.json"
    )
