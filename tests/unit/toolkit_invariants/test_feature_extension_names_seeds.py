"""The feature-extension workflow names the seed stage (DEVSPEC-226)."""
from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[3] / "docs" / "developers" / "workflows" / "workflow_feature_extension.md"


def test_feature_extension_workflow_has_a_seed_stage() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "/specdev-seed" in text
    assert "step_requirements" in text
