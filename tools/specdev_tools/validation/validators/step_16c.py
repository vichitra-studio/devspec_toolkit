"""Step 16c (Review phase) validator.

Validates the review phase of the Trinity Loop: review completeness,
verdict enums, and semantic coverage on top of the base step_16 checks.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from ...core.errors import make_error, SpecError
from .step_16 import _load_roadmap
from .step_16b import validate_step_16b

VALID_VERDICTS = frozenset({"verified", "needs_work", "blocked", "deferred"})


def validate_step_16c(data: dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None) -> list[SpecError]:
    """Deep validation for Step 16c (Review phase).

    A 16c artifact is a 16b execution augmented with a ``review`` section.
    It must satisfy every 16a- and 16b-phase constraint in addition to the
    16c-specific verdict + semantic-review checks below.  Chains up through
    ``validate_step_16b`` → ``validate_step_16a`` → ``validate_step_16``.
    """
    errors = validate_step_16b(data, toolkit_root, spec_path)

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

    # W582 -- FR coverage completeness against the corresponding Step 14 milestone
    # Only runs when verdict is "verified" and spec_path is available
    if verdict == "verified" and spec_path:
        try:
            roadmap_data = _load_roadmap(spec_path)
        except (OSError, json.JSONDecodeError):
            roadmap_data = None
        if roadmap_data is not None:
            try:
                # The vc:16-impl-context schema places milestone_ref only on
                # individual checklist items (root has unevaluatedProperties: false
                # and never declares it).  Scan checklist items to collect the
                # unique planning milestone references this 16c artifact covers.
                checklist = (
                    data.get("plan", {})
                    .get("spec_alignment", {})
                    .get("checklist", [])
                )
                milestone_refs: set[str] = set()
                if isinstance(checklist, list):
                    for item in checklist:
                        if isinstance(item, dict):
                            ref = item.get("milestone_ref", "")
                            if ref:
                                milestone_refs.add(ref)
                # If milestone_refs is empty (checklist absent and no root milestone_ref),
                # W582 runs against ALL milestones in the roadmap — a conservative "all coverage required"
                # fallback. This is intentional: without a scoped milestone, we verify the full roadmap.
                # The W582 message uses "(all)" as the milestone label in this case.
                milestone_fr_refs: list[str] = []
                for milestone in roadmap_data.get("milestones", []):
                    if not isinstance(milestone, dict):
                        continue
                    mid = milestone.get("milestone_id", "")
                    if milestone_refs:
                        if mid not in milestone_refs:
                            continue
                    milestone_fr_refs.extend(
                        fr for fr in milestone.get("fr_refs", []) if isinstance(fr, str)
                    )

                # Collect covered FR IDs from semantic_review.fr_coverage
                covered_fr_ids: set[str] = set()
                if isinstance(semantic_review, dict):
                    for entry in semantic_review.get("fr_coverage", []):
                        if isinstance(entry, dict):
                            fr_id = entry.get("fr_id")
                            if isinstance(fr_id, str):
                                covered_fr_ids.add(fr_id)

                # Fire W582 for each milestone FR not covered in fr_coverage
                for fr_ref in milestone_fr_refs:
                    if fr_ref not in covered_fr_ids:
                        errors.append(
                            make_error(
                                "W582",
                                f"Step 16c: FR '{fr_ref}' from milestone '{', '.join(sorted(milestone_refs)) or '(all)'}' "
                                "in 14_roadmap.json is not covered in semantic_review.fr_coverage"
                            )
                        )
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                pass  # Roadmap parse errors handled by E304 in step_16 base validator

    return errors
