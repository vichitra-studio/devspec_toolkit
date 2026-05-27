from __future__ import annotations

from typing import Any

from ...core.errors import make_error, SpecError
from ...core.loaders import load_upstream_ids

# Coverage threshold: any dimension ratio below this fires W592
COVERAGE_THRESHOLD = 0.8

# Required dimension keys
REQUIRED_DIMENSIONS = (
    "fr_api_coverage",
    "fr_fixture_coverage",
    "fr_milestone_coverage",
    "capability_fr_coverage",
)

_OPT_DIMENSION = "milestone_decomp_completeness"


def _validate_dimension_consistency(
    dim_key: str,
    dim: dict[str, Any],
    errors: list[SpecError],
) -> None:
    """Run consistency and threshold checks for a single coverage dimension."""
    covered_count = dim.get("covered_count")
    total_count = dim.get("total_count")
    ratio = dim.get("ratio")
    uncovered_ids = dim.get("uncovered_ids")

    # Internal consistency: covered_count + len(uncovered_ids) == total_count
    if (
        isinstance(covered_count, int)
        and isinstance(total_count, int)
        and isinstance(uncovered_ids, list)
    ):
        expected_uncovered = total_count - covered_count
        if expected_uncovered < 0:
            errors.append(make_error(
                "E520",
                f"DIMENSION_INCONSISTENCY {dim_key}: covered_count ({covered_count}) "
                f"exceeds total_count ({total_count})"
            ))
        elif len(uncovered_ids) != expected_uncovered:
            errors.append(make_error(
                "E520",
                f"DIMENSION_INCONSISTENCY {dim_key}: uncovered_ids has {len(uncovered_ids)} "
                f"entries but total_count - covered_count = {expected_uncovered}"
            ))

    # Ratio consistency: ratio == covered_count / total_count when total_count > 0
    if (
        isinstance(covered_count, int)
        and isinstance(total_count, int)
        and isinstance(ratio, (int, float))
    ):
        if total_count > 0:
            expected_ratio = covered_count / total_count
            if abs(ratio - expected_ratio) > 1e-6:
                errors.append(make_error(
                    "E520",
                    f"RATIO_INCONSISTENCY {dim_key}: ratio {ratio} does not match "
                    f"covered_count/total_count = {expected_ratio:.6f}"
                ))
        elif total_count == 0 and ratio != 1.0:
            errors.append(make_error(
                "E520",
                f"RATIO_INCONSISTENCY {dim_key}: ratio must be 1.0 when total_count is 0 "
                f"(vacuous coverage), got {ratio}"
            ))

    # Threshold warning: ratio < COVERAGE_THRESHOLD fires W592
    if isinstance(ratio, (int, float)) and 0 <= ratio < COVERAGE_THRESHOLD:
        errors.append(make_error(
            "W592",
            f"COVERAGE_THRESHOLD_WARN {dim_key}: ratio {ratio:.4f} is below "
            f"threshold {COVERAGE_THRESHOLD} — consider closing coverage gaps before Step 14"
        ))


def validate_step_13a(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    errors: list[SpecError] = []

    dimensions = instance.get("dimensions")
    if not isinstance(dimensions, dict):
        errors.append(make_error("E520", "MISSING_DIMENSIONS 'dimensions' object is required for step 13a"))
        return errors

    # Check all four required dimension keys are present
    for dim_key in REQUIRED_DIMENSIONS:
        if dim_key not in dimensions:
            errors.append(make_error(
                "E520",
                f"MISSING_DIMENSION '{dim_key}' is required in dimensions"
            ))

    # Validate each required dimension that is present
    for dim_key in REQUIRED_DIMENSIONS:
        dim = dimensions.get(dim_key)
        if not isinstance(dim, dict):
            continue
        _validate_dimension_consistency(dim_key, dim, errors)

    # Validate optional milestone_decomp_completeness dimension if present
    opt_dim = dimensions.get(_OPT_DIMENSION)
    if isinstance(opt_dim, dict):
        _validate_dimension_consistency(_OPT_DIMENSION, opt_dim, errors)

    # -------------------------------------------------------------------
    # Cross-step ID validation
    # Load upstream ID sets; returns None if upstream file is absent.
    # -------------------------------------------------------------------
    fr_ids = load_upstream_ids(toolkit_root, "04", "functional_requirements", "fr_id", spec_root=spec_root)
    api_ids = load_upstream_ids(toolkit_root, "05", "apis", "api_id", spec_root=spec_root)
    cap_ids = load_upstream_ids(toolkit_root, "01", "capabilities", "capability_id", spec_root=spec_root)

    # upstream_map: prefix -> (id_set_or_None, source_filename, type_label)
    #
    # "cap-" and "capability-" both map to cap_ids: projects use "cap-" by
    # convention (e.g., cap-auth) while the schema description says "capability-*".
    # Mapping both ensures E590 fires for hallucinated IDs regardless of which
    # prefix is used; W590 fires at most once per source file (deduped by filename).
    #
    # "api-" is retained for forward compatibility: no current dimension produces
    # api-* uncovered IDs, but future dimensions may reference API IDs.
    upstream_map: dict[str, tuple[set[str] | None, str, str]] = {
        "fr-": (fr_ids, "04_fr_list.json", "FR"),
        "api-": (api_ids, "05_interface_contracts.json", "API"),
        "cap-": (cap_ids, "01_capabilities.json", "capability"),
        "capability-": (cap_ids, "01_capabilities.json", "capability"),
    }

    # "ms-" validates milestone IDs in the optional milestone_decomp_completeness
    # dimension against the Step 14 roadmap. Only loaded when the optional dimension
    # is present to avoid spurious W590 in documents that don't use it.
    if isinstance(opt_dim, dict):
        milestone_ids = load_upstream_ids(toolkit_root, "14", "milestones", "milestone_id", spec_root=spec_root)
        upstream_map["ms-"] = (milestone_ids, "14_roadmap.json", "milestone")

    # Emit W590 once per missing upstream file (deduplicated by filename)
    warned_missing: set[str] = set()
    for prefix, (id_set, filename, type_label) in upstream_map.items():
        if id_set is None and filename not in warned_missing:
            errors.append(
                make_error("W590", f"CROSS_STEP_UPSTREAM_MISSING {filename} not found; "
                f"skipping {type_label} reference validation")
            )
            warned_missing.add(filename)

    # Validate uncovered_ids across all dimensions: required + optional
    dims_to_validate = list(REQUIRED_DIMENSIONS) + [_OPT_DIMENSION]
    for dim_key in dims_to_validate:
        dim = dimensions.get(dim_key)
        if not isinstance(dim, dict):
            continue
        uncovered_ids = dim.get("uncovered_ids", [])
        if not isinstance(uncovered_ids, list):
            continue
        for ref in uncovered_ids:
            if not isinstance(ref, str):
                continue
            for prefix, (id_set, filename, type_label) in upstream_map.items():
                if ref.startswith(prefix):
                    if id_set is not None and ref not in id_set:
                        errors.append(
                            make_error("E590", f"CROSS_STEP_ID_NOT_FOUND dimension "
                            f"'{dim_key}' references unknown {type_label} "
                            f"'{ref}' (not in {filename})")
                        )
                    break

    return errors
