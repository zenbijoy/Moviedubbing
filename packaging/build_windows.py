"""
Standalone Windows Application Packaging Script.

Automates the assembly of a standalone Windows distribution directory, bundling:
  - Python application source & libraries (lib/aidub)
  - Launcher scripts (MovieDubbingStudio.bat, MovieDubbingStudio.ps1, aidub.bat)
  - Application resources (resources/i18n, resources/themes, SQL migrations)
  - External dependency diagnostics & documentation (FFmpeg/FFprobe in bin/, AI models in models/)
  - Package manifest and licensing information
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to sys.path so script can be run standalone
repo_root = Path(__file__).resolve().parent.parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from aidub.infrastructure.packaging import PackagingSpec, WindowsPackager  # noqa: E402

__all__ = ["PackagingSpec", "WindowsPackager"]

if __name__ == "__main__":
    packager = WindowsPackager()
    dist_path = packager.assemble_distribution()
    valid = WindowsPackager.verify_distribution(dist_path)
    print(f"Distribution built at: {dist_path} (Valid: {valid})")
