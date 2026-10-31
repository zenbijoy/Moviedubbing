"""QC report generator."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QCCheck:
    name: str
    passed: bool
    value: float
    threshold: float
    message: str = ""


class QCReportGenerator:
    @staticmethod
    def generate(checks: list[QCCheck]) -> dict:
        passed = sum(1 for c in checks if c.passed)
        total = len(checks)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": (passed / total * 100.0) if total else 100.0,
            "overall": "PASS" if all(c.passed for c in checks) else "FAIL",
            "checks": [c.__dict__ for c in checks],
        }


__all__ = ["QCCheck", "QCReportGenerator"]
