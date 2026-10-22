"""Canonical launcher for the single AI Movie Dubbing Studio desktop app."""

from __future__ import annotations

import sys

from aidub.ui.application import run_desktop

if __name__ == "__main__":
    sys.exit(run_desktop())
