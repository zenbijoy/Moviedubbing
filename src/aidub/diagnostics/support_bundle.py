"""
Redacted Diagnostics Support Bundle Generator.

Creates sanitized ZIP support bundles for technical support (`aidub doctor --bundle`),
automatically redacting all API keys, bearer tokens, passwords, and sensitive environment variables.
"""

from __future__ import annotations

import json
import logging
import os
import re
import zipfile
from collections.abc import Sequence
from pathlib import Path

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)

SECRET_PATTERNS = [
    re.compile(
        r"(?i)(api[_-]?key|secret|token|password|auth|bearer)\s*[:=]\s*['\"]?([^\s'\"]+)['\"]?"
    ),
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),
    re.compile(r"bearer\s+[a-zA-Z0-9\._\-]{20,}", re.IGNORECASE),
]


class SupportBundleResult(ContractModel):
    """Result summary of diagnostic support bundle creation."""

    bundle_id: Identifier
    zip_path: str = Field(min_length=1)
    file_count: int = Field(ge=0)
    redacted_tokens_count: int = Field(ge=0)


class SupportBundleGenerator:
    """
    Assembles sanitized diagnostic support bundles with automatic secret redaction.
    """

    def redact_sensitive_text(self, text: str) -> tuple[str, int]:
        """
        Scan and redact sensitive tokens from diagnostic log strings.
        """
        redacted_text = text
        count = 0

        for pattern in SECRET_PATTERNS:
            matches = list(pattern.finditer(redacted_text))
            count += len(matches)
            for m in matches:
                full_match = m.group(0)
                if ":" in full_match or "=" in full_match:
                    prefix = (
                        full_match.split("=")[0] if "=" in full_match else full_match.split(":")[0]
                    )
                    redacted_text = redacted_text.replace(full_match, f"{prefix}=REDACTED_SECRET")
                else:
                    redacted_text = redacted_text.replace(full_match, "REDACTED_SECRET")

        return redacted_text, count

    def generate_support_bundle(
        self,
        output_directory: str = "dist/diagnostics",
        extra_log_files: Sequence[str] = (),
    ) -> SupportBundleResult:
        """
        Generate diagnostic support ZIP archive.
        """
        out_dir = Path(output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)

        bundle_id = Identifier(f"bundle_{int(os.times().system * 100)}")
        zip_path = out_dir / f"aidub_support_{bundle_id}.zip"

        total_redactions = 0
        file_count = 0

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. System Info
            sys_info = {
                "os": os.name,
                "platform": os.getenv("OS", "windows"),
                "python_version": "3.12.10",
                "app": "Movie Dubbing Studio AI Enterprise",
            }
            sys_info_str, r_count = self.redact_sensitive_text(json.dumps(sys_info, indent=2))
            total_redactions += r_count
            zf.writestr("sys_info.json", sys_info_str)
            file_count += 1

            # 2. Environment Variables (Sanitized)
            env_dict = dict(os.environ)
            sanitized_env = {
                k: "REDACTED_SECRET"
                if any(s in k.lower() for s in ["key", "secret", "pass", "token"])
                else v
                for k, v in env_dict.items()
            }
            env_str, r_count = self.redact_sensitive_text(json.dumps(sanitized_env, indent=2))
            total_redactions += r_count
            zf.writestr("environment.json", env_str)
            file_count += 1

            # 3. Include extra log files if provided
            for log_file in extra_log_files:
                p = Path(log_file)
                if p.exists() and p.is_file():
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    clean_content, r_count = self.redact_sensitive_text(content)
                    total_redactions += r_count
                    zf.writestr(f"logs/{p.name}", clean_content)
                    file_count += 1

        logger.info(
            "support_bundle: created diagnostic bundle %s with %d redactions",
            zip_path,
            total_redactions,
        )

        return SupportBundleResult(
            bundle_id=bundle_id,
            zip_path=str(zip_path),
            file_count=file_count,
            redacted_tokens_count=total_redactions,
        )


__all__ = [
    "SupportBundleGenerator",
    "SupportBundleResult",
]
