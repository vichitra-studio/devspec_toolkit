"""H-212-1: `shared_expectations.md` states the output hygiene rule and points to where verification evidence is recorded."""
from __future__ import annotations

import re
from pathlib import Path

SHARED_EXPECTATIONS = Path(__file__).resolve().parents[3] / "docs" / "prompts" / "shared_expectations.md"


def _section(heading: str) -> str:
    """The text of the `## <heading>` section of shared_expectations.md, up to the next `## ` heading."""
    text = SHARED_EXPECTATIONS.read_text(encoding="utf-8")
    start = text.index(f"## {heading}")
    match = re.search(r"^## ", text[start + 3 :], flags=re.MULTILINE)
    return text[start : start + 3 + match.start()] if match else text[start:]


def test_shared_expectations_has_the_output_hygiene_rule() -> None:
    rules = [line for line in _section("6. Output Rules").splitlines() if line.startswith("11. ")]
    assert len(rules) == 1
    rule = rules[0]
    assert "Output hygiene" in rule
    assert "`enum_provenance`" in rule
    assert "is a limit, not advice" in rule


def test_section_12_points_to_where_evidence_is_recorded() -> None:
    section = _section("12. Context Ledger")
    assert "Verification evidence is not artifact text" in section
    assert "`evidence[]`" in section
    assert "`specdev attest`" in section
