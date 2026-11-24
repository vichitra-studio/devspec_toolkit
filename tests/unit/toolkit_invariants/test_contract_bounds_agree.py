"""A prompt and the schema it fills state the same bound; a rule that is not enforced is not claimed as a guarantee (DEVSPEC-225)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def _prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def _schema(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "schema" / name).read_text(encoding="utf-8"))


def test_shared_expectations_does_not_claim_additional_properties_everywhere() -> None:
    text = (ROOT / "docs" / "prompts" / "shared_expectations.md").read_text(encoding="utf-8")
    assert "everywhere" not in text
    assert "Do not include any fields outside the schema." in text


def test_step_14_migration_plan_bound_agrees_between_prompt_and_schema() -> None:
    description = _schema("14_roadmap.schema.json")["allOf"][1]["properties"]["migration_plan"]["description"]
    assert "under 40 words" in description
    assert "under 40 words" in _prompt("prompt_14_roadmap.md")


def test_step_09_migration_plan_bound_agrees_between_prompt_and_schema() -> None:
    description = _schema("09_impl_plan.schema.json")["properties"]["migration_plan"]["description"]
    assert "2–4 sentences" in description
    assert "2 to 4 sentences" in _prompt("prompt_09_impl_plan.md")


def test_16a_and_16c_scope_the_verbose_rule() -> None:
    assert "apply to the `description` of a checklist item" in _prompt("prompt_16a_impl_planner.md")
    assert 'only text the "verbose" rule covers' in _prompt("prompt_16c_impl_reviewer.md")
