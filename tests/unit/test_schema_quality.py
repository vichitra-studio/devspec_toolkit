"""Schema quality CI lints — regression guards for structural hygiene.

FIX-056: additionalProperties / unevaluatedProperties on every object node
FIX-057: nesting depth ceiling (threshold = 21)
FIX-058: description coverage floor (aggregate >= 80%, per-file >= 70%)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_schema_files() -> list[Path]:
    """Return all *.schema.json files under schema/."""
    return sorted(SCHEMA_DIR.rglob("*.schema.json"))


def _load_json(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


# ---- FIX-056 helpers -------------------------------------------------------

# Nodes that are intentionally open (no additionalProperties constraint).
# step_base is a composable fragment — it deliberately omits additionalProperties
# so consuming schemas can extend it.  environmentConfig uses additionalProperties
# with a value schema (not `false`), which is valid.
_ALLOWED_OPEN_ANCHORS = {
    "stepBase",  # step_base.schema.json — composable fragment
}


def _find_unconstrained_objects(
    node: Any,
    path: str = "$",
    *,
    parent_has_oneof_anyof: bool = False,
    parent_has_unevaluated_props: bool = False,
) -> list[str]:
    """Return JSON-pointer-style paths of ``type: object`` nodes missing both
    ``additionalProperties`` and ``unevaluatedProperties``.

    Exceptions:
    - Nodes inside ``oneOf``/``anyOf`` wrappers (polymorphic branches).
    - Nodes that use ``propertyNames`` (open-map pattern).
    - Nodes with ``$ref`` (delegated constraint).
    - Nodes in ``if``/``then``/``else`` (conditional sub-schemas).
    - Nodes with ``$anchor`` in the allowed-open set.
    - Nodes inside ``allOf`` when the parent schema has ``unevaluatedProperties``
      (allOf composition delegates closedness to the parent).
    """
    issues: list[str] = []

    if not isinstance(node, dict):
        return issues

    # Skip conditional sub-schemas — they augment, not define, objects
    for kw in ("if", "then", "else"):
        if kw in node and isinstance(node[kw], dict):
            pass  # don't recurse into these at the top level

    is_object = node.get("type") == "object"
    has_ap = "additionalProperties" in node
    has_up = "unevaluatedProperties" in node
    has_property_names = "propertyNames" in node
    has_ref = "$ref" in node
    anchor = node.get("$anchor", "")

    # Bare ``{"type": "object"}`` without ``properties`` is an intentional
    # open-map / any-object slot — don't require additionalProperties.
    has_properties = "properties" in node

    if (
        is_object
        and has_properties
        and not has_ap
        and not has_up
        and not has_property_names
        and not has_ref
        and not parent_has_oneof_anyof
        and not parent_has_unevaluated_props
        and anchor not in _ALLOWED_OPEN_ANCHORS
    ):
        issues.append(path)

    # Track whether this node has unevaluatedProperties for allOf children
    this_has_up = "unevaluatedProperties" in node

    # Recurse into sub-schemas
    in_polymorphic = parent_has_oneof_anyof or any(
        k in node for k in ("oneOf", "anyOf")
    )

    for key, child in node.items():
        if key in ("if", "then", "else"):
            # Don't flag objects inside conditional blocks
            continue
        if isinstance(child, dict):
            issues.extend(
                _find_unconstrained_objects(
                    child,
                    f"{path}/{key}",
                    parent_has_oneof_anyof=in_polymorphic,
                    parent_has_unevaluated_props=parent_has_unevaluated_props,
                )
            )
        elif isinstance(child, list):
            for i, item in enumerate(child):
                if isinstance(item, dict):
                    # allOf entries inherit closedness from parent's unevaluatedProperties
                    child_up = (
                        this_has_up if key == "allOf" else parent_has_unevaluated_props
                    )
                    issues.extend(
                        _find_unconstrained_objects(
                            item,
                            f"{path}/{key}/{i}",
                            parent_has_oneof_anyof=in_polymorphic
                            or key in ("oneOf", "anyOf"),
                            parent_has_unevaluated_props=child_up,
                        )
                    )

    return issues


# ---- FIX-057 helpers -------------------------------------------------------


def _measure_nesting_depth(node: Any, depth: int = 0) -> int:
    """Return the maximum nesting depth of a JSON structure."""
    if isinstance(node, dict):
        if not node:
            return depth
        return max(
            _measure_nesting_depth(v, depth + 1) for v in node.values()
        )
    elif isinstance(node, list):
        if not node:
            return depth
        return max(
            _measure_nesting_depth(v, depth + 1) for v in node
        )
    return depth


# ---- FIX-058 helpers -------------------------------------------------------


def _count_description_coverage(node: Any) -> tuple[int, int]:
    """Return (properties_with_description, total_properties).

    Counts every property defined in a ``properties`` block and every
    definition inside ``$defs`` blocks (each $defs entry is a reusable
    type that should carry a description).
    """
    total = 0
    with_desc = 0

    if not isinstance(node, dict):
        return with_desc, total

    props = node.get("properties")
    if isinstance(props, dict):
        for _key, prop_schema in props.items():
            if not isinstance(prop_schema, dict):
                continue
            total += 1
            if "description" in prop_schema:
                with_desc += 1

    # Count $defs entries — each definition is a reusable type that
    # should have a description.  Then recurse into each definition to
    # pick up any nested properties it may contain.
    defs = node.get("$defs")
    if isinstance(defs, dict):
        for _def_name, def_schema in defs.items():
            if not isinstance(def_schema, dict):
                continue
            total += 1
            if "description" in def_schema:
                with_desc += 1
            # Recurse into the definition itself for nested properties
            d, t = _count_description_coverage(def_schema)
            with_desc += d
            total += t

    # Recurse into child structures, skipping keys already handled
    # above to avoid double-counting.
    _handled = {"properties", "$defs"}
    for key, child in node.items():
        if key in _handled:
            continue
        if isinstance(child, dict):
            d, t = _count_description_coverage(child)
            with_desc += d
            total += t
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, dict):
                    d, t = _count_description_coverage(item)
                    with_desc += d
                    total += t

    return with_desc, total


# ---------------------------------------------------------------------------
# Parametrized test IDs — one per schema file
# ---------------------------------------------------------------------------

_SCHEMA_FILES = _collect_schema_files()
_SCHEMA_IDS = [str(p.relative_to(SCHEMA_DIR)) for p in _SCHEMA_FILES]


# ===========================================================================
# FIX-056 — additionalProperties / unevaluatedProperties regression guard
# ===========================================================================


@pytest.mark.parametrize("schema_path", _SCHEMA_FILES, ids=_SCHEMA_IDS)
def test_all_objects_are_closed(schema_path: Path) -> None:
    """Every ``type: object`` node must set ``additionalProperties: false``
    or ``unevaluatedProperties: false`` (with documented exceptions)."""
    schema = _load_json(schema_path)
    issues = _find_unconstrained_objects(schema)
    assert not issues, (
        f"{schema_path.name} has unconstrained object nodes:\n"
        + "\n".join(f"  - {p}" for p in issues)
    )


# ===========================================================================
# FIX-057 — nesting depth regression guard (threshold = 21)
# ===========================================================================

_NESTING_THRESHOLD = 21  # observed max in Step 16 (16_impl_context) — increased by 2 after allOf composition with step_base


@pytest.mark.parametrize("schema_path", _SCHEMA_FILES, ids=_SCHEMA_IDS)
def test_nesting_depth_within_threshold(schema_path: Path) -> None:
    """Schema nesting depth must not exceed the threshold (currently 21,
    increased for allOf composition with step_base)."""
    schema = _load_json(schema_path)
    depth = _measure_nesting_depth(schema)
    assert depth <= _NESTING_THRESHOLD, (
        f"{schema_path.name} nesting depth {depth} exceeds threshold "
        f"{_NESTING_THRESHOLD}"
    )


# ===========================================================================
# FIX-058 — description coverage regression guard (aggregate floor)
# ===========================================================================

# Aggregate coverage after Batch 0b enrichment is ~94.7%.  The floor is set
# to 80% — well below current state — so any significant bulk removal of
# descriptions is caught while leaving room for minor schema refactors.
# Raise the floor if aggregate coverage climbs further and stabilises.
_DESCRIPTION_COVERAGE_FLOOR = 0.80  # 80% — safe buffer below current 94.7%


def test_aggregate_description_coverage() -> None:
    """Aggregate property-description coverage across all schemas must not
    regress below the floor."""
    total_with = 0
    total_all = 0

    for schema_path in _SCHEMA_FILES:
        schema = _load_json(schema_path)
        w, t = _count_description_coverage(schema)
        total_with += w
        total_all += t

    if total_all == 0:
        pytest.skip("No properties found across schemas")

    coverage = total_with / total_all
    assert coverage >= _DESCRIPTION_COVERAGE_FLOOR, (
        f"Aggregate description coverage {coverage:.1%} "
        f"({total_with}/{total_all}) is below floor "
        f"{_DESCRIPTION_COVERAGE_FLOOR:.0%}"
    )


@pytest.mark.parametrize("schema_path", _SCHEMA_FILES, ids=_SCHEMA_IDS)
def test_description_coverage_no_regression(schema_path: Path) -> None:
    """Per-schema description coverage must not fall below the per-file floor.

    After Batch 0b enrichment the lowest-coverage schema sits at ~75%
    (02_system_sketch.schema.json).  The floor is set to 70% — 5 percentage
    points below that minimum — so any significant regression on an individual
    schema is caught without failing on minor fluctuations from small refactors.
    """
    # Per-file floor: 70% — set 5pp below the current minimum of ~75%
    # (02_system_sketch.schema.json: 3/4 = 75.0%).
    # Raise this value as the lowest-coverage schemas are improved.
    _PER_FILE_FLOOR = 0.70

    schema = _load_json(schema_path)
    with_desc, total = _count_description_coverage(schema)

    if total == 0:
        pytest.skip(f"{schema_path.name} has no properties to check")

    coverage_fraction = with_desc / total
    assert coverage_fraction >= _PER_FILE_FLOOR, (
        f"{schema_path.name}: description coverage {coverage_fraction:.1%} "
        f"({with_desc}/{total}) is below per-file floor {_PER_FILE_FLOOR:.0%}"
    )
