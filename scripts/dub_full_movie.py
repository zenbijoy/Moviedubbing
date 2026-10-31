"""Full Movie Dubbing Execution Script using Kaggle Bangla Chatterbox."""

import argparse
import sys
import time
from pathlib import Path

# Ensure UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from aidub.media.ffmpeg_ops import duration, probe
from aidub.pipeline.config import PipelineConfig
from aidub.pipeline.engine import DubbingEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Dub movie using Kaggle Bangla Chatterbox")
    parser.add_argument(
        "--input",
        type=str,
        default="test movies/Bad Genius_ The Series-S1E1-480P.mp4",
        help="Path to source movie file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="exports/Bad_Genius_Full_Dubbed_BN.mp4",
        help="Path to output dubbed movie file",
    )
    parser.add_argument(
        "--chatterbox-url",
        type=str,
        default="https://defend-rick-seattle-incidence.trycloudflare.com",
        help="Kaggle Chatterbox Cloudflare URL",
    )
    parser.add_argument(
        "--tts-engine",
        type=str,
        default="chatterbox",
        choices=["chatterbox", "edge_tts"],
        help="TTS engine to use",
    )
    parser.add_argument(
        "--keep-music",
        action="store_true",
        default=False,
        help="Preserve background music via Demucs stem separation (Note: takes several hours on CPU)",
    )
    parser.add_argument(
        "--asr-model",
        type=str,
        default="base",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper model size",
    )
    parser.add_argument(
        "--start",
        type=float,
        default=0.0,
        help="Start time in seconds from where to begin dubbing (e.g. 180 for minute 3)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional duration limit in seconds for testing (e.g. 60 or 300; omit for full movie)",
    )
    parser.add_argument(
        "--work-dir",
        type=str,
        default="exports/bad_genius_full_work",
        help="Working directory for intermediate files",
    )

    args = parser.parse_args()

    source_path = Path(args.input)
    if not source_path.is_file():
        print(f"❌ Source video file not found: {source_path}")
        sys.exit(1)

    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    info = probe(source_path)
    movie_dur = float(info["format"]["duration"])
    movie_size_mb = source_path.stat().st_size / (1024 * 1024)

    print("=" * 70)
    print("🎬 MOVIE DUBBING PIPELINE - FULL EXECUTION")
    print("=" * 70)
    print(f"Source Movie:     {source_path.name}")
    print(f"Movie Size:       {movie_size_mb:.2f} MB")
    print(f"Total Duration:   {movie_dur:.2f} seconds ({movie_dur / 60:.2f} minutes)")
    print(f"Target Language:  Bangla (bn)")
    print(f"TTS Engine:       {args.tts_engine.upper()}")
    if args.tts_engine == "chatterbox":
        print(f"Kaggle API URL:   {args.chatterbox_url}")
    print(f"Keep Music Stem:  {'YES (Demucs)' if args.keep_music else 'NO (Fast Dialogue Ducking)'}")
    print(f"Whisper Model:    {args.asr_model}")
    print(f"Output Master:    {out_path}")
    print("=" * 70 + "\n")

    input_media = source_path
    if (args.start > 0) or (args.duration is not None and args.duration > 0 and args.duration < movie_dur):
        dur_tag = f"{int(args.duration)}s" if args.duration else "end"
        slice_path = work_dir / f"movie_slice_{int(args.start)}s_to_{dur_tag}.mp4"
        cmd = ["ffmpeg", "-y", "-ss", str(args.start)]
        if args.duration:
            cmd.extend(["-t", str(args.duration)])
        cmd.extend(["-i", str(source_path), "-c:v", "copy", "-c:a", "aac", str(slice_path)])
        print(f"✂ Extracting movie segment: Start={args.start:.1f}s, Duration={args.duration or 'remaining'}s...")
        from aidub.media.ffmpeg_ops import _run
        _run(cmd)
        input_media = slice_path
        print(f"  ✓ Slice ready: {slice_path.name}\n")

    cfg = PipelineConfig(
        input=input_media,
        output=out_path,
        src_lang="auto",
        tgt_lang="bn",
        work_dir=work_dir,
        asr_model=args.asr_model,
        keep_music=args.keep_music,
        diarize=True,
        tts_engine=args.tts_engine,
        chatterbox_url=args.chatterbox_url,
    )

    def on_progress(stage: str, percent: int, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] [{percent:3d}%] [{stage:12s}] {msg}")

    print("🚀 Starting DubbingEngine...")
    start_time = time.time()
    engine = DubbingEngine(cfg, progress_callback=on_progress)
    outputs = engine.run()
    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print(f"🎉 FULL DUBBING COMPLETED SUCCESSFULLY in {elapsed / 60:.2f} minutes!")
    print("=" * 70)
    print(f"Dubbed Master Video: {outputs.dubbed_video}")
    print(f"Dubbed Audio:        {outputs.dubbed_audio}")
    print(f"Bilingual Subtitles: {outputs.bilingual_srt}")
    print(f"Target Subtitles:    {outputs.target_srt}")
    print(f"Utterance Metadata:  {outputs.transcript_json}")

    if Path(outputs.dubbed_video).is_file():
        final_info = probe(outputs.dubbed_video)
        print(f"✓ Master File Size:  {Path(outputs.dubbed_video).stat().st_size / (1024 * 1024):.2f} MB")
        print(f"✓ Master Duration:   {final_info['format']['duration']} seconds")


if __name__ == "__main__":
    main()
