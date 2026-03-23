"""Step 16c (Review phase) validator.

Validates the review phase of the Trinity Loop: review completeness,
verdict enums, and semantic coverage on top of the base step_16 checks.
"""
from __future__ import annotations

from typing import Any, Optional

from ...core.errors import make_error, SpecError
from .step_16 import validate_step_16

VALID_VERDICTS = frozenset({"verified", "needs_work", "blocked", "deferred"})


def validate_step_16c(data: dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None) -> list[SpecError]:
    """Deep validation for Step 16c (Review phase)."""
    errors = validate_step_16(data, toolkit_root, spec_path)

    review = data.get("review", {})
    if not isinstance(review, dict):
        errors.append(make_error("E520", "Step 16c expects a 'review' object"))
        return errors

    # Verdict must be a valid enum
    verdict = review.get("verdict")
    semantic_review = review.get("semantic_review")
    if verdict is not None and verdict not in VALID_VERDICTS:
        errors.append(
            make_error("E520", f"Step 16c: invalid verdict '{verdict}'. "
            f"Must be one of: {', '.join(sorted(VALID_VERDICTS))}")
        )

    # When verdict is "verified", semantic_review with fr_coverage is REQUIRED
    if verdict == "verified":
        if not isinstance(semantic_review, dict):
            errors.append(make_error("E520", "Step 16c: verdict is 'verified' but 'review.semantic_review' is missing"))
        elif not semantic_review.get("fr_coverage"):
            errors.append(make_error("E520", "Step 16c: verdict is 'verified' but 'review.semantic_review.fr_coverage' is empty"))

    # Semantic review coverage check
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
                        errors.append(make_error("E520", f"Step 16c: duplicate fr_id '{fr_id}' in semantic_review.fr_coverage"))
                    seen_fr_ids.add(fr_id)

    return errors
