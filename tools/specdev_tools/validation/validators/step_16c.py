"""Step 16c (Review phase) validator.

Validates the review phase of the Trinity Loop: review completeness,
verdict enums, and semantic coverage on top of the base step_16 checks.
"""
from __future__ import annotations

from typing import Any, Optional

from ...core.scope_helpers import as_dict, dict_items, str_in
from ...core.errors import make_error, SpecError
from .step_16b import validate_step_16b

VALID_VERDICTS = frozenset({"verified", "needs_work", "blocked", "deferred"})


def validate_step_16c(data: dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None, spec_root: Optional[str] = None) -> list[SpecError]:
    """Deep validation for Step 16c (Review phase).

    A 16c artifact is a 16b execution augmented with a ``review`` section.
    It must satisfy every 16a- and 16b-phase constraint in addition to the
    16c-specific verdict + semantic-review checks below.  Chains up through
    ``validate_step_16b`` → ``validate_step_16a`` → ``validate_step_16``.
    """
    errors = validate_step_16b(data, toolkit_root, spec_path, spec_root)

    review = data.get("review", {})
    if not isinstance(review, dict):
        errors.append(make_error("E520", "Step 16c expects a 'review' object"))
        return errors

    # Verdict must be a valid enum
    verdict = review.get("verdict")
    semantic_review = review.get("semantic_review")
    if verdict is not None and not str_in(verdict, VALID_VERDICTS):
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

    errors.extend(_duplicate_fr_id_errors(as_dict(semantic_review).get("fr_coverage")))
    return errors


def _duplicate_fr_id_errors(fr_coverage: Any) -> list[SpecError]:
    """E520 for every ``fr_id`` that a later ``fr_coverage`` entry repeats."""
    seen: set[str] = set()
    errors: list[SpecError] = []
    for fr_id in (entry.get("fr_id") for entry in dict_items(fr_coverage)):
        if not isinstance(fr_id, str):
            continue
        if fr_id in seen:
            errors.append(make_error("E520", f"Step 16c: duplicate fr_id '{fr_id}' in semantic_review.fr_coverage"))
        seen.add(fr_id)
    return errors
