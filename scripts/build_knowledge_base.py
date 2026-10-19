"""Build comprehensive Knowledge Base and BRAIN.md for Bangla AI Movie Dubbing."""

import os

BASE_DIR = "dubbing-research/knowledge"
CHEATSHEETS_DIR = os.path.join(BASE_DIR, "cheatsheets")
os.makedirs(CHEATSHEETS_DIR, exist_ok=True)

print("Building Knowledge Base...")
