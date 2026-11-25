"""`/specdev-review --review-only`: reviewers run once, nothing is fixed, and upstream reconciliation is not a review output (DEVSPEC-194)."""
from __future__ import annotations

from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[3] / ".claude" / "skills" / "specdev-review" / "SKILL.md"


@pytest.mark.skipif(not SKILL.is_file(), reason=".claude is absent")
@pytest.mark.parametrize(
    "text",
    [
        "--review-only",
        "the verdict is `CLEAN` or `FINDINGS`",
        "Upstream reconciliation (confirming or refuting what earlier steps reported) is not a review output",
    ],
)
def test_review_skill_documents_review_only(text: str) -> None:
    assert text in " ".join(SKILL.read_text(encoding="utf-8").split())
