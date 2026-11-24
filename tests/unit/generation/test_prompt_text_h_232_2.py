"""H-232-2: prompt 02a and the 02a schema descriptions say that gate and compliance names are not checked against a list."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT = (REPO_ROOT / "prompts" / "prompt_02a_delivery_baseline.md").read_text(encoding="utf-8")
SCHEMA = (REPO_ROOT / "schema" / "02a_delivery_baseline.schema.json").read_text(encoding="utf-8")


def test_prompt_02a_says_gate_names_are_not_checked_against_the_pipeline() -> None:
    assert "no tool checks that a gate exists in the pipeline" in PROMPT
    assert "do not invent gate names that do not correspond to real pipeline steps." not in PROMPT


def test_prompt_02a_compliance_names_are_free_strings() -> None:
    assert "`compliance` is a free list of strings, so no tool checks the spelling" in PROMPT
    assert "use the canonical short names defined in the schema" not in PROMPT


def test_02a_schema_descriptions_name_no_standard_list() -> None:
    assert "Standard names:" not in SCHEMA
    assert "Use canonical short names:" not in SCHEMA
    assert "Example names (not an enum" in SCHEMA
    assert "Use these short names (a free list: the spelling is not checked)" in SCHEMA
