"""H-212-1: `shared_expectations.md` states the output hygiene rule and points to where verification evidence is recorded."""
from __future__ import annotations

import re
from pathlib import Path

SHARED_EXPECTATIONS = Path(__file__).resolve().parents[3] / "docs" / "prompts" / "shared_expectations.md"


def _section(heading: str) -> str:
    """The text of the `## <heading>` section (``heading`` is a regex) of shared_expectations.md, up to the next `## ` heading."""
    text = SHARED_EXPECTATIONS.read_text(encoding="utf-8")
    heading_match = re.search(rf"^## {heading}\b", text, flags=re.MULTILINE)
    assert heading_match, f"shared_expectations.md has no section '{heading}'"
    start = heading_match.start()
    match = re.search(r"^## ", text[start + 3 :], flags=re.MULTILINE)
    return text[start : start + 3 + match.start()] if match else text[start:]


def test_shared_expectations_has_the_output_hygiene_rule() -> None:
    rules = [line for line in _section(r"\d+\. Output Rules").splitlines() if re.match(r"\d+\. ", line) and "Output hygiene" in line]
    assert len(rules) == 1
    rule = rules[0]
    assert "Output hygiene" in rule
    assert "`enum_provenance`" in rule
    assert "is a limit, not advice" in rule


def test_section_12_points_to_where_evidence_is_recorded() -> None:
    section = _section(r"\d+\. Context Ledger")
    assert "Verification evidence is not artifact text" in section
    assert "`evidence[]`" in section
    assert "`specdev attest`" in section
