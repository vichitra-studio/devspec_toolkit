"""H-202-1: an accepted canonical proposal stays; the texts say so and name the read route."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.core.json_utils import json_read

_ROOT = Path(__file__).resolve().parents[3]
_REVIEWER = _ROOT / ".claude" / "agents" / "specdev-reviewer.md"


def _text(*parts: str) -> str:
    return _ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_shared_expectations_states_the_proposal_lifecycle():
    text = _text("docs", "prompts", "shared_expectations.md")
    assert "An accepted proposal stays in `canonical_proposals`" in text
    assert "do not report an accepted proposal as stale" in text


def test_glossary_prompt_says_the_proposal_stays():
    assert "The proposal stays in the file afterwards; it is not removed or marked." in _text(
        "prompts", "prompt_03_glossary.md"
    )


@pytest.mark.skipif(not _REVIEWER.is_file(), reason=".claude is absent")
def test_reviewer_does_not_call_an_accepted_proposal_stale():
    text = _REVIEWER.read_text(encoding="utf-8")
    assert "accepted proposal" in text
    assert "do not report it as stale or unused" in text


def test_the_documented_canon_read_route_returns_the_entry():
    kind_file = _ROOT / "canon" / "kinds" / "environment.json"
    first_id = json.loads(kind_file.read_text(encoding="utf-8"))["entries"][0]["id"]
    entry = json.loads(json_read(str(kind_file), f'.entries[] | select(.id=="{first_id}")', as_json=True))
    assert entry["id"] == first_id and entry["definition"]
