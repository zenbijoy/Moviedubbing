"""[LEGACY DEMO SCRIPT]

This script was originally authored as a demonstration runner targeting an external movie file
(Inception_1080P_480P.mp4) not stored in the repository.

For standard end-to-end production dubbing on verified repo media, run:
    aidub dub -i clip.mp4 -o out_bn.mp4 -t bn --work-dir work
Or generate a fresh 30-second English test clip via:
    python scripts/make_test_clip.py
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from aidub.cli import main

DEFAULT_MOVIE = Path(r"C:\Users\24030\Downloads\Inception_1080P_480P.mp4")
DEFAULT_OUTPUT = Path("exports/inception_bangla_dubbed.mp4")


def dub_inception_to_bangla(argv: Sequence[str] | None = None) -> int:
    """Execute dubbing on Inception; falls back cleanly to clip.mp4 if external file missing."""
    forwarded = list(sys.argv[1:] if argv is None else argv)
    if not any(arg in {"-i", "--input"} or arg.startswith("--input=") for arg in forwarded):
        source = DEFAULT_MOVIE if DEFAULT_MOVIE.is_file() else Path("clip.mp4")
        if not source.is_file():
            print(
                f"[DEMO NOTICE] External movie '{DEFAULT_MOVIE}' not found and 'clip.mp4' not generated."
            )
            print("Run 'python scripts/make_test_clip.py' first or pass '--input <path>'.")
        forwarded.extend(("--input", str(source)))
    if not any(arg in {"-o", "--output"} or arg.startswith("--output=") for arg in forwarded):
        forwarded.extend(("--output", str(DEFAULT_OUTPUT)))
    if not any(arg in {"--overwrite", "-f"} for arg in forwarded):
        forwarded.append("--overwrite")
    return main(["dub", *forwarded])


if __name__ == "__main__":
    raise SystemExit(dub_inception_to_bangla())
