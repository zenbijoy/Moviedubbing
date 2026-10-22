"""Atomic Utterance Persistence & Hash-based Incremental Re-dubbing (from open-dubbing utterance.py)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class UtteranceStore:
    """
    Manages atomic JSON persistence of dialogue utterances with SHA-256 hashing.

    Enables incremental re-dubbing: on project reload, re-calculates hashes to identify
    ONLY modified segments, avoiding expensive re-ASR or re-translation.
    """

    def __init__(self, target_language: str, output_directory: Path | str) -> None:
        self.target_language = target_language.replace("-", "_").lower()
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)

    def _get_filename(self) -> Path:
        return self.output_directory / f"utterance_metadata_{self.target_language}.json"

    def save_utterances(
        self,
        utterance_metadata: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """
        Atomically save utterance list with computed SHA-256 hashes to disk.
        """
        target_path = self._get_filename()
        hashed_utterances = self._hash_utterances(utterance_metadata)

        payload = {
            "target_language": self.target_language,
            "utterances": hashed_utterances,
            "metadata": metadata or {},
        }

        json_data = json.dumps(payload, ensure_ascii=False, indent=2)

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, encoding="utf-8", dir=self.output_directory
        ) as tmp:
            tmp.write(json_data)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name

        shutil.copyfile(tmp_name, str(target_path))
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except Exception:
            pass

        logger.debug("Saved %d utterances to %s", len(hashed_utterances), target_path)
        return target_path

    def load_utterances(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Load utterances and metadata from JSON file."""
        target_path = self._get_filename()
        if not target_path.exists():
            return [], {}

        with target_path.open(encoding="utf-8") as f:
            data = json.load(f)
            return data.get("utterances", []), data.get("metadata", {})

    def get_modified_utterances(
        self, current_utterances: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Compare current utterance states against stored hashes.

        Returns only utterances that have been edited by user or pipeline modifications.
        """
        modified: list[dict[str, Any]] = []

        for u in current_utterances:
            stored_hash = u.get("_hash")
            if not stored_hash:
                modified.append(u)
                continue

            filtered = {k: v for k, v in u.items() if not k.startswith("_")}
            dict_str = json.dumps(filtered, sort_keys=True)
            curr_hash = hashlib.sha256(dict_str.encode()).hexdigest()

            if curr_hash != stored_hash:
                modified.append(u)

        logger.info(
            "UtteranceStore: %d of %d utterances modified", len(modified), len(current_utterances)
        )
        return modified

    def _hash_utterances(self, utterances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        hashed_list: list[dict[str, Any]] = []

        for idx, u in enumerate(utterances, start=1):
            item = u.copy()
            item["id"] = item.get("id", idx)

            filtered = {k: v for k, v in item.items() if not k.startswith("_")}
            dict_str = json.dumps(filtered, sort_keys=True)
            item["_hash"] = hashlib.sha256(dict_str.encode()).hexdigest()

            for field_name in ["assigned_voice", "speaker_id", "text", "tgt"]:
                val = item.get(field_name)
                if val:
                    item[f"_{field_name}_hash"] = hashlib.sha256(str(val).encode()).hexdigest()

            hashed_list.append(item)

        return hashed_list


__all__ = ["UtteranceStore"]
