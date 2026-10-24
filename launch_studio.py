"""Canonical launcher for the single AI Movie Dubbing Studio desktop app."""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from aidub.ui.application import run_desktop

if __name__ == "__main__":
    sys.exit(run_desktop())
