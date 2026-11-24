"""The label rename of a glossary term is written down where an author meets E590 (DEVSPEC-186)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RENAME = "node rename --label"


def test_glossary_prompt_names_the_label_rename() -> None:
    assert RENAME in (ROOT / "prompts" / "prompt_03_glossary.md").read_text(encoding="utf-8")


def test_e590_resolution_names_the_label_rename() -> None:
    catalogue = (ROOT / "docs" / "developers" / "error-codes.md").read_text(encoding="utf-8")
    section = catalogue.split("### E590 ", 1)[1].split("\n### ", 1)[0]
    assert RENAME in section
