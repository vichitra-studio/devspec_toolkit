"""H-275-1: the artifact ``id`` description teaches no convention that no tool reads."""
from __future__ import annotations

import json
from pathlib import Path

STEP_BASE = Path(__file__).resolve().parents[3] / "schema" / "core" / "step_base.schema.json"


def test_step_base_id_names_no_unread_convention() -> None:
    description = json.loads(STEP_BASE.read_text(encoding="utf-8"))["properties"]["id"]["description"]
    assert "{step-noun}" not in description
    assert "{N}" not in description


def test_migration_templates_name_no_unread_id_convention() -> None:
    templates = sorted((STEP_BASE.parents[2] / "prompts" / "migration").glob("template_*.md"))
    assert templates
    assert [t.name for t in templates if "{step-noun}" in t.read_text(encoding="utf-8")] == []
