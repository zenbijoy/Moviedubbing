"""AI Dubbing Studio application package."""

from __future__ import annotations

import os

# Prevent OpenBLAS / OpenMP thread exhaustion on Windows
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

__all__ = ["__version__"]

__version__ = "0.1.0.dev0"
