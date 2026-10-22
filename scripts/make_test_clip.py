"""Generate a 30-second English test movie clip for end-to-end dubbing verification."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from aidub.media.ffmpeg_ops import _ffmpeg_exe


async def _synthesize_line(text: str, voice: str, output_path: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def make_test_clip(output_path: Path | str = "clip.mp4", duration_seconds: float = 30.0) -> Path:
    out = Path(output_path).resolve()
    ffmpeg = _ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        line1_wav = tmp_dir / "line1.mp3"
        line2_wav = tmp_dir / "line2.mp3"
        line3_wav = tmp_dir / "line3.mp3"
        line4_wav = tmp_dir / "line4.mp3"

        lines = [
            ("Welcome to the AI Movie Dubbing Studio. This is our automated translation test.", "en-US-JennyNeural", line1_wav),
            ("We are testing neural speech recognition, translation, and high quality speech synthesis.", "en-US-GuyNeural", line2_wav),
            ("Precise timing alignment ensures that every character speaks naturally on screen.", "en-US-JennyNeural", line3_wav),
            ("The master video combines synchronized dialogue with background music seamlessly.", "en-US-GuyNeural", line4_wav),
        ]

        async def _synth_all() -> None:
            await asyncio.gather(*[_synthesize_line(text, voice, path) for text, voice, path in lines])

        print("Synthesizing dialogue lines with Edge TTS...")
        asyncio.run(_synth_all())

        # Construct composite audio using FFmpeg filter_complex:
        # line 1 at 1.0s, line 2 at 7.5s, line 3 at 14.5s, line 4 at 21.5s
        # Plus a subtle synth chord background music bed so stem separation (Demucs) has real music to separate!
        print("Muxing 30s video with timed dialogue and background music bed...")
        cmd = [
            ffmpeg,
            "-y",
            # Video source: 30-second 1280x720 24fps test pattern
            "-f", "lavfi",
            "-i", f"testsrc=size=1280x720:rate=24:duration={duration_seconds}",
            # Background ambient music source (sine waves chord at -24dB)
            "-f", "lavfi",
            "-i", f"sine=frequency=220:duration={duration_seconds}",
            "-f", "lavfi",
            "-i", f"sine=frequency=277.18:duration={duration_seconds}",
            "-f", "lavfi",
            "-i", f"sine=frequency=329.63:duration={duration_seconds}",
            # Dialogue inputs
            "-i", str(line1_wav),
            "-i", str(line2_wav),
            "-i", str(line3_wav),
            "-i", str(line4_wav),
            "-filter_complex",
            (
                # Mix background chord and soften volume
                "[1:a][2:a][3:a]amix=inputs=3:duration=first:dropout_transition=2,volume=0.04[bg];"
                # Delay dialogue lines to respective timestamps
                "[4:a]adelay=1000|1000[d1];"
                "[5:a]adelay=7500|7500[d2];"
                "[6:a]adelay=14500|14500[d3];"
                "[7:a]adelay=21500|21500[d4];"
                # Combine dialogue and background
                "[bg][d1][d2][d3][d4]amix=inputs=5:duration=first:dropout_transition=0,volume=2.0[aout];"
                # Visual timecode text overlay on video
                "[0:v]drawtext=text='AI DUBBING TEST CLIP (30s)':x=(w-text_w)/2:y=60:fontsize=32:fontcolor=white:box=1:boxcolor=black@0.6,"
                "drawtext=text='TIME %{pts\\:hms}':x=(w-text_w)/2:y=120:fontsize=28:fontcolor=yellow:box=1:boxcolor=black@0.6[vout]"
            ),
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", str(duration_seconds),
            str(out),
        ]

        # In case drawtext font is missing or fails, fallback to simple video without drawtext filter
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("drawtext filter not supported or font missing, building with clean video source...")
            cmd_fallback = [
                ffmpeg,
                "-y",
                "-f", "lavfi",
                "-i", f"testsrc=size=1280x720:rate=24:duration={duration_seconds}",
                "-f", "lavfi",
                "-i", f"sine=frequency=220:duration={duration_seconds}",
                "-f", "lavfi",
                "-i", f"sine=frequency=277.18:duration={duration_seconds}",
                "-f", "lavfi",
                "-i", f"sine=frequency=329.63:duration={duration_seconds}",
                "-i", str(line1_wav),
                "-i", str(line2_wav),
                "-i", str(line3_wav),
                "-i", str(line4_wav),
                "-filter_complex",
                (
                    "[1:a][2:a][3:a]amix=inputs=3:duration=first:dropout_transition=2,volume=0.04[bg];"
                    "[4:a]adelay=1000|1000[d1];"
                    "[5:a]adelay=7500|7500[d2];"
                    "[6:a]adelay=14500|14500[d3];"
                    "[7:a]adelay=21500|21500[d4];"
                    "[bg][d1][d2][d3][d4]amix=inputs=5:duration=first:dropout_transition=0,volume=2.0[aout]"
                ),
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", str(duration_seconds),
                str(out),
            ]
            subprocess.run(cmd_fallback, check=True)

    print(f"Generated test clip: {out} ({out.stat().st_size} bytes)")
    return out


if __name__ == "__main__":
    out_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("clip.mp4")
    make_test_clip(out_file)

