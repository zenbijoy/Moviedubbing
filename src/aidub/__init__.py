"""AI Dubbing Studio application package."""

from __future__ import annotations

import os
import sys

# Prevent OpenBLAS / OpenMP thread exhaustion on Windows
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

# Ensure stdout and stderr use UTF-8 on Windows to safely handle multilingual / Bengali text
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

__all__ = ["__version__"]

__version__ = "0.1.0.dev0"
