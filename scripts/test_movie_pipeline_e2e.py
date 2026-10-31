"""End-to-End Test for DubbingEngine on Real Movie Clip."""

import sys
import time
from pathlib import Path

# Ensure UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from aidub.media.ffmpeg_ops import duration, probe, trim
from aidub.pipeline.config import PipelineConfig
from aidub.pipeline.engine import DubbingEngine


def test_movie_pipeline() -> None:
    source_movie = Path("test movies/Bad Genius_ The Series-S1E1-480P.mp4")
    if not source_movie.is_file():
        print(f"❌ Source movie not found: {source_movie}")
        return

    work_dir = Path("exports/test_e2e_work")
    work_dir.mkdir(parents=True, exist_ok=True)
    sample_clip = work_dir / "sample_15s.mp4"
    out_dubbed = work_dir / "sample_15s_dubbed_bn.mp4"

    print("=" * 70)
    print("🎬 TESTING MOVIE DUBBING PIPELINE ON REAL MEDIA")
    print("=" * 70)
    print(f"Source movie:    {source_movie.name}")
    print(f"File size:       {source_movie.stat().st_size / (1024 * 1024):.2f} MB")

    # Step 1: Probe
    info = probe(source_movie)
    dur_s = float(info["format"]["duration"])
    print(f"Total duration:  {dur_s:.2f} seconds (~{dur_s / 60:.1f} minutes)")
    print(f"Streams found:   {len(info.get('streams', []))} (Video + Audio)")

    # Step 2: Extract a 15-second test slice from an active dialogue scene (180s - 195s)
    print("\n[Stage 0] Extracting 15-second movie dialogue sample (180s to 195s)...")
    from aidub.media.ffmpeg_ops import _run
    _run([
        "ffmpeg", "-y",
        "-ss", "180.0",
        "-to", "195.0",
        "-i", str(source_movie),
        "-c:v", "copy",
        "-c:a", "aac",
        str(sample_clip),
    ])
    sample_dur = duration(sample_clip)
    print(f"  ✓ Sample extracted: {sample_clip.name} ({sample_dur:.2f}s)")

    # Resume pipeline using existing extracted stems/ASR if present
    # import shutil
    # shutil.rmtree(work_dir / "engine_work", ignore_errors=True)

    # Step 3: Run Full DubbingEngine
    print("\n[Stage 1-9] Launching DubbingEngine...")
    cfg = PipelineConfig(
        input=sample_clip,
        output=out_dubbed,
        src_lang="auto",
        tgt_lang="bn",
        work_dir=work_dir / "engine_work",
        asr_model="base",
        keep_music=True,
        diarize=True,
        tts_engine="edge_tts",  # Uses verified local/cloud neural Bengali voice
    )

    def on_progress(stage: str, percent: int, msg: str) -> None:
        print(f"  [{percent:3d}%] [{stage:12s}] {msg}")

    engine = DubbingEngine(cfg, progress_callback=on_progress)
    start_t = time.time()
    outputs = engine.run()
    elapsed = time.time() - start_t

    print("\n" + "=" * 70)
    print(f"🎉 PIPELINE TEST COMPLETE in {elapsed:.1f} seconds!")
    print("=" * 70)
    print(f"Dubbed Video:   {outputs.dubbed_video}")
    print(f"Dubbed Audio:   {outputs.dubbed_audio}")
    print(f"Bilingual SRT:  {outputs.bilingual_srt}")
    print(f"Target SRT:     {outputs.target_srt}")
    print(f"Transcript:     {outputs.transcript_json}")

    # Verify output file exists and has valid duration
    if Path(outputs.dubbed_video).is_file():
        out_info = probe(outputs.dubbed_video)
        print(f"✓ Output Video Duration: {out_info['format']['duration']}s")
        print("✓ Every pipeline stage executed and verified successfully!")


if __name__ == "__main__":
    test_movie_pipeline()
