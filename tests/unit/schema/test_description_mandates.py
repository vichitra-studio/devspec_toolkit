"""Three content rules left the schema descriptions for the step prompts: nothing checks them, so a description does not state them as contract (DEVSPEC-147)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
GUIDANCE_MARKER = "Guidance, not checked:"
FORBIDDEN = ("must", "Decision rule")


def _load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "schema" / name).read_text(encoding="utf-8"))


def _rationale() -> str:
    return _load("13_extension_manifest.schema.json")["properties"]["extension_decision"]["properties"]["rationale"]["description"]


def _spikes() -> str:
    milestones = _load("14_roadmap.schema.json")["allOf"][1]["properties"]["milestones"]
    return milestones["items"]["properties"]["spikes"]["description"]


def _finding_description() -> str:
    review = _load("16_impl_context.schema.json")["properties"]["review"]
    return review["properties"]["findings"]["items"]["properties"]["description"]["description"]


@pytest.mark.parametrize("description", [_rationale, _spikes, _finding_description], ids=["13-rationale", "14-spikes", "16-finding"])
def test_the_description_states_no_content_mandate(description) -> None:
    text = description()
    assert not [word for word in FORBIDDEN if word in text]


@pytest.mark.parametrize(
    "prompt",
    ["prompt_13_extension_manifest.md", "prompt_14_roadmap.md", "prompt_16c_impl_reviewer.md"],
)
def test_the_prompt_holds_the_guidance_line(prompt: str) -> None:
    assert GUIDANCE_MARKER in (ROOT / "prompts" / prompt).read_text(encoding="utf-8")
