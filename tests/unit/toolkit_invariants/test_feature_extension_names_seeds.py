"""The feature-extension workflow names the seed stage (DEVSPEC-226)."""
from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[3] / "docs" / "developers" / "workflows" / "workflow_feature_extension.md"


def test_feature_extension_workflow_has_a_seed_stage() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    # The stage lists the manual moves; no skill by that name exists.
    assert "seed_templates/seed_extension.md" in text
    assert "spec/common/seed_manifest.json" in text
    assert "step_requirements" in text
    assert "seed-lint" in text
    assert "/specdev-seed" not in text
