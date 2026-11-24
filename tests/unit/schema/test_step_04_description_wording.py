"""The step 04 field descriptions ask for behaviour, which the prompt's own constraints also ask for."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

SCHEMA = Path(__file__).resolve().parents[3] / "schema" / "04_fr_list.schema.json"
FORBIDDEN = ("cite the regulation", "session_tokens", "users table", " table ")


def _find_property(node: object, name: str) -> dict | None:
    """Return the first ``properties[name]`` object found anywhere under ``node``."""
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict) and isinstance(props.get(name), dict):
            return props[name]
        children = node.values()
    elif isinstance(node, list):
        children = node
    else:
        return None
    for child in children:
        found = _find_property(child, name)
        if found is not None:
            return found
    return None


@pytest.mark.parametrize("field", ["rationale", "preconditions", "postconditions"])
def test_fr_descriptions_are_behavioural(field: str) -> None:
    fr_items = _find_property(json.loads(SCHEMA.read_text(encoding="utf-8")), "functional_requirements")
    assert fr_items is not None
    prop = _find_property(fr_items, field)
    assert prop is not None
    description = prop["description"]
    for phrase in FORBIDDEN:
        assert phrase not in description, f"{field} description holds {phrase!r}"
