"""
Bangla Subtitle Quality Control (QC) & Grammar/Formatting Validator.
Ensures broadcast compliance: character length, reading speed (CPS), and Bengali punctuation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class SubtitleIssue:
    cue_index: int
    issue_type: str
    severity: str  # "error", "warning", "info"
    description: str
    suggested_fix: str | None = None

    @property
    def message(self) -> str:
        return self.description


class BanglaSubtitleQC:
    """Validates Bengali subtitle deliverables for broadcast and theatrical standards."""

    MAX_CHARS_PER_LINE = 40
    MAX_LINES_PER_CUE = 2
    MAX_CPS = 18.0  # Max Characters Per Second for human reading comprehension
    MIN_DURATION_S = 0.8

    @classmethod
    def audit_cue(
        cls,
        index: int,
        start_s: float,
        end_s: float,
        text: str,
    ) -> list[SubtitleIssue]:
        issues: list[SubtitleIssue] = []
        dur = max(0.01, end_s - start_s)

        # 1. Duration check
        if dur < cls.MIN_DURATION_S:
            issues.append(
                SubtitleIssue(
                    cue_index=index,
                    issue_type="DURATION_TOO_SHORT",
                    severity="warning",
                    description=f"Subtitle duration ({dur:.2f}s) is shorter than minimum {cls.MIN_DURATION_S}s.",
                )
            )

        # 2. Reading speed check (CPS)
        char_count = len(text.replace(" ", ""))
        cps = char_count / dur
        if cps > cls.MAX_CPS:
            issues.append(
                SubtitleIssue(
                    cue_index=index,
                    issue_type="READING_SPEED_EXCEEDED",
                    severity="warning",
                    description=f"Reading speed {cps:.1f} CPS exceeds comfortable limit ({cls.MAX_CPS} CPS).",
                    suggested_fix="Condense dialogue phrasing or extend display duration.",
                )
            )

        # 3. Line length & count check
        lines = text.split("\n")
        if len(lines) > cls.MAX_LINES_PER_CUE:
            issues.append(
                SubtitleIssue(
                    cue_index=index,
                    issue_type="TOO_MANY_LINES",
                    severity="error",
                    description=f"Subtitle has {len(lines)} lines; maximum allowed is {cls.MAX_LINES_PER_CUE}.",
                )
            )

        for line_no, line in enumerate(lines, 1):
            if len(line.strip()) > cls.MAX_CHARS_PER_LINE:
                issues.append(
                    SubtitleIssue(
                        cue_index=index,
                        issue_type="LINE_TOO_LONG",
                        severity="warning",
                        description=f"Line {line_no} has {len(line)} characters (max {cls.MAX_CHARS_PER_LINE}).",
                    )
                )

        # 4. Bengali Punctuation Check
        if "." in text and not re.search(r"\d+\.\d+", text):
            # English period instead of Bengali Dari '।'
            issues.append(
                SubtitleIssue(
                    cue_index=index,
                    issue_type="PUNCTUATION_DARI_EXPECTED",
                    severity="info",
                    description="English period '.' found in Bengali text; Dari '।' is recommended.",
                    suggested_fix=text.replace(".", "।"),
                )
            )

        # 5. Broken Hasanta check (orphaned virama)
        if re.search(r"\s্", text):
            issues.append(
                SubtitleIssue(
                    cue_index=index,
                    issue_type="ORPHANED_HASANTA",
                    severity="error",
                    description="Orphaned Bengali Hasanta '্' detected without preceding consonant.",
                    suggested_fix=text.replace(" ্", ""),
                )
            )

        return issues

    @classmethod
    def audit_all(cls, cues: list[dict[str, Any]]) -> list[SubtitleIssue]:
        """Audits a complete list of subtitle cues."""
        all_issues: list[SubtitleIssue] = []
        for idx, c in enumerate(cues, 1):
            st = float(c.get("start_s", 0.0))
            et = float(c.get("end_s", 0.0))
            txt = str(c.get("text", ""))
            all_issues.extend(cls.audit_cue(idx, st, et, txt))
        return all_issues

    @classmethod
    def check_line(cls, text: str, duration_sec: float = 2.0) -> list[SubtitleIssue]:
        """Convenience method to check a single dialogue subtitle line."""
        return cls.audit_cue(1, 0.0, max(0.1, duration_sec), text)

    @classmethod
    def auto_fix(cls, text: str) -> str:
        """Auto-fixes common Bengali punctuation and formatting issues."""
        fixed = text
        # Replace Western period with Bengali Dari (unless inside decimals)
        fixed = re.sub(r"(?<!\d)\.(?!\d)", "।", fixed)
        if fixed.endswith("."):
            fixed = fixed[:-1] + "।"
        # Fix orphaned Hasanta
        fixed = fixed.replace(" ্", "")
        return fixed


__all__ = ["BanglaSubtitleQC", "SubtitleIssue"]
