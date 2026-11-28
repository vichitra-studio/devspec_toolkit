"""Prompt 05 says which of its rules a tool checks and which it does not (DEVSPEC-232)."""
from __future__ import annotations

from pathlib import Path

PROMPT_05 = Path(__file__).resolve().parents[3] / "prompts" / "prompt_05_interface_contracts.md"


def _text() -> str:
    return PROMPT_05.read_text(encoding="utf-8")


def test_prompt_05_names_enum_provenance() -> None:
    text = _text()
    assert "`enum_provenance`" in text
    assert "E311" in text


def test_prompt_05_says_status_classes_are_unchecked() -> None:
    text = _text()
    assert "No tool checks the status classes" in text
    assert "(review rule; not checked by a tool)" in text


def test_prompt_05_says_an_http_api_has_path_and_method() -> None:
    text = _text()
    assert "an `http` API also has `path` and `method`" in text
    assert "route/path (or equivalent)" not in text
