"""Step 16c (Review phase) validator.

Validates the review phase of the Trinity Loop: review completeness,
verdict enums, and semantic coverage on top of the base step_16 checks.
"""
from __future__ import annotations

from typing import Any, Optional

from .step_16 import validate_step_16

VALID_VERDICTS = frozenset({"verified", "needs_work", "blocked", "deferred"})


def validate_step_16c(data: dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None) -> list[str]:
    """Deep validation for Step 16c (Review phase)."""
    errors = validate_step_16(data, toolkit_root, spec_path)

    review = data.get("review", {})
    if not isinstance(review, dict):
        errors.append("Step 16c expects a 'review' object")
        return errors

    # Verdict must be a valid enum
    verdict = review.get("verdict")
    if verdict and verdict not in VALID_VERDICTS:
        errors.append(
            f"Step 16c: invalid verdict '{verdict}'. "
            f"Must be one of: {', '.join(sorted(VALID_VERDICTS))}"
        )

    # Semantic review coverage check
    semantic_review = review.get("semantic_review")
    if isinstance(semantic_review, dict):
        fr_coverage = semantic_review.get("fr_coverage", [])
        if isinstance(fr_coverage, list):
            seen_fr_ids: set[str] = set()
            for entry in fr_coverage:
                if not isinstance(entry, dict):
                    continue
                fr_id = entry.get("fr_id")
                if isinstance(fr_id, str):
                    if fr_id in seen_fr_ids:
                        errors.append(f"Step 16c: duplicate fr_id '{fr_id}' in semantic_review.fr_coverage")
                    seen_fr_ids.add(fr_id)

    return errors
