"""Generate an English test movie clip for end-to-end dubbing verification."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

from aidub.media.ffmpeg_ops import _ffmpeg_exe


async def _synthesize_line(text: str, voice: str, output_path: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def make_test_clip(output_path: Path | str = "clip.mp4", duration_seconds: float = 120.0) -> Path:
    out = Path(output_path).resolve()
    ffmpeg = _ffmpeg_exe()

    if duration_seconds >= 120.0:
        line_defs = [
            (
                "Welcome to the AI Movie Dubbing Studio. This is our automated translation test.",
                "en-US-JennyNeural",
                1000,
            ),
            (
                "We are testing neural speech recognition, translation, and high quality speech synthesis.",
                "en-US-GuyNeural",
                16000,
            ),
            (
                "Precise timing alignment ensures that every character speaks naturally on screen.",
                "en-US-JennyNeural",
                32000,
            ),
            (
                "The master video combines synchronized dialogue with background music seamlessly.",
                "en-US-GuyNeural",
                48000,
            ),
            (
                "Spoken dialogue in movies must preserve the emotional weight of every dramatic scene.",
                "en-US-JennyNeural",
                64000,
            ),
            (
                "Our translation engine adapts cultural nuances and idioms for the target audience.",
                "en-US-GuyNeural",
                80000,
            ),
            (
                "Every spoken phrase matches the natural rhythm and visual timing of the actors.",
                "en-US-JennyNeural",
                96000,
            ),
            (
                "The final dubbed master is rendered with high fidelity audio and accurate subtitles.",
                "en-US-GuyNeural",
                110000,
            ),
        ]
    elif duration_seconds >= 60.0:
        line_defs = [
            (
                "Welcome to the AI Movie Dubbing Studio. This is our automated translation test.",
                "en-US-JennyNeural",
                1000,
            ),
            (
                "We are testing neural speech recognition, translation, and high quality speech synthesis.",
                "en-US-GuyNeural",
                16000,
            ),
            (
                "Precise timing alignment ensures that every character speaks naturally on screen.",
                "en-US-JennyNeural",
                32000,
            ),
            (
                "The master video combines synchronized dialogue with background music seamlessly.",
                "en-US-GuyNeural",
                48000,
            ),
        ]
    else:
        line_defs = [
            (
                "Welcome to the AI Movie Dubbing Studio. This is our automated translation test.",
                "en-US-JennyNeural",
                1000,
            ),
            (
                "We are testing neural speech recognition, translation, and high quality speech synthesis.",
                "en-US-GuyNeural",
                7500,
            ),
            (
                "Precise timing alignment ensures that every character speaks naturally on screen.",
                "en-US-JennyNeural",
                14500,
            ),
            (
                "The master video combines synchronized dialogue with background music seamlessly.",
                "en-US-GuyNeural",
                21500,
            ),
        ]

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        lines_to_synth: list[tuple[str, str, Path]] = []
        dialogue_inputs: list[str] = []
        delay_filters: list[str] = []
        amix_inputs = ["[bg]"]

        for idx, (text, voice, delay_ms) in enumerate(line_defs):
            wav_path = tmp_dir / f"line_{idx}.mp3"
            lines_to_synth.append((text, voice, wav_path))
            dialogue_inputs.extend(["-i", str(wav_path)])
            stream_idx = 4 + idx
            delay_filters.append(f"[{stream_idx}:a]adelay={delay_ms}|{delay_ms}[d{idx}];")
            amix_inputs.append(f"[d{idx}]")

        async def _synth_all() -> None:
            await asyncio.gather(
                *[_synthesize_line(text, voice, path) for text, voice, path in lines_to_synth]
            )

        print(f"Synthesizing {len(lines_to_synth)} dialogue lines with Edge TTS...")
        asyncio.run(_synth_all())

        print(
            f"Muxing {duration_seconds:.0f}s video with timed dialogue and background music bed..."
        )
        audio_filter_complex = (
            "[1:a][2:a][3:a]amix=inputs=3:duration=first:dropout_transition=2,volume=0.04[bg];"
            + "".join(delay_filters)
            + "".join(amix_inputs)
            + f"amix=inputs={len(amix_inputs)}:duration=first:dropout_transition=0,volume=2.0[aout]"
        )

        filter_with_text = (
            f"{audio_filter_complex};"
            f"[0:v]drawtext=text='AI DUBBING TEST CLIP ({duration_seconds:.0f}s)':x=(w-text_w)/2:y=60:fontsize=32:fontcolor=white:box=1:boxcolor=black@0.6,"
            "drawtext=text='TIME %{pts\\:hms}':x=(w-text_w)/2:y=120:fontsize=28:fontcolor=yellow:box=1:boxcolor=black@0.6[vout]"
        )

        base_cmd = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=1280x720:rate=24:duration={duration_seconds}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=220:duration={duration_seconds}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=277.18:duration={duration_seconds}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=329.63:duration={duration_seconds}",
            *dialogue_inputs,
        ]

        cmd = [
            *base_cmd,
            "-filter_complex",
            filter_with_text,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            str(duration_seconds),
            str(out),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(
                "drawtext filter not supported or font missing, building with clean video source..."
            )
            cmd_fallback = [
                *base_cmd,
                "-filter_complex",
                audio_filter_complex,
                "-map",
                "0:v",
                "-map",
                "[aout]",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-t",
                str(duration_seconds),
                str(out),
            ]
            subprocess.run(cmd_fallback, check=True)

    print(f"Generated test clip: {out} ({out.stat().st_size} bytes)")
    return out


if __name__ == "__main__":
    out_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("clip.mp4")
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
    make_test_clip(out_file, duration_seconds=dur)
