"""The E607 section of the error catalogue names the way out that exists."""
from __future__ import annotations

import re
from pathlib import Path

ERROR_CODES_MD = Path(__file__).resolve().parents[3] / "docs" / "developers" / "error-codes.md"


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^### {heading}\b.*?(?=^### |^## )", text, re.S | re.M)
    assert match, f"no section {heading}"
    return match.group(0)


def test_e607_resolution_does_not_send_to_canon_accept() -> None:
    section = _section(ERROR_CODES_MD.read_text(encoding="utf-8"), "E607")
    assert "re-run" not in section
    assert "specdev guide E607" in section
