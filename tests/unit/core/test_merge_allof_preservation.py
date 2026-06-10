"""Behavior-preservation gate for merge_allof / effective_schema (F2, §5 WS3).

WS3 rerouted ``merge_allof`` (context/_utils.py) and ``_get_all_properties``
(registry/generate.py) through ``core/schema_nav.py::effective_schema``.  The
critical invariant to preserve is the **own-first UNION merge**: a step's OWN
properties must survive alongside the step-base properties contributed by the
``allOf: [$ref vc:core:step-base]`` branch.

This module is the automated guard for that invariant (the P2 regression was an
overwrite that silently dropped own properties).  Each parametrised test case
calls ``merge_allof`` directly — the same internal path that
``structure.py:_output_schema_keys`` uses — so the assertion spans the full
merge chain including ``$ref`` resolution.

Two sets of keys are asserted per step:
- **step-base keys**: ``id``, ``owner``, ``created_at``, ``canonical_refs_used``
  — these are the *required* properties defined on ``vc:core:step-base`` and are
  contributed exclusively by the ``$ref(vc:core:step-base)`` allOf branch.
  Their presence proves the allOf branch was NOT dropped.
- **step-own keys**: the representative domain-specific properties declared by
  the step schema itself.  Their presence proves own properties were NOT
  overwritten by the allOf merge (the P2 regression).

Assertions use subset containment (``expected <= actual``) — NOT exact-set
equality — so that additive schema changes (new optional fields, etc.) do not
break the guard.
"""
from __future__ import annotations

import pathlib
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Repository root: tests/unit/core → ../../.. → toolkit root
# (Matches the idiom used in test_json_utils_dry_run.py:30.)
_TOOLKIT_ROOT = pathlib.Path(__file__).resolve().parents[3]

# Keys defined on vc:core:step-base (all are required); contributed to every
# step's merged property set exclusively via the allOf $ref branch.
_STEP_BASE_KEYS: frozenset[str] = frozenset(
    {"id", "owner", "created_at", "canonical_refs_used"}
)

# ---------------------------------------------------------------------------
# Parametrize: (step_id, expected_own_keys)
#
# Chosen steps:
#   "00"  — two-branch allOf schema: allOf[0] = step-base $ref, allOf[1] =
#            own properties (title, problem_statement, in_scope, …); NO root
#            `properties` block at schema top level
#   "02"  — has both own properties (components, connections, tech_stack) AND
#            allOf step-base; named explicitly in the F2 finding
#   "03"  — minimal step-own (terms); exercises the same allOf merge path
#   "04"  — single step-own key (functional_requirements); clean signal
#   "09"  — step-own key asserted: milestones only; own props declared at schema
#            ROOT alongside allOf step-base $ref
#   "12"  — two asserted step-own keys (jobs, coverage_thresholds); trace is
#            also present in allOf[1] but is not asserted in this frozenset
#   "16"  — complex impl-context schema; named in F2 finding; own props at
#            schema ROOT alongside allOf step-base $ref
# ---------------------------------------------------------------------------

_STEP_CASES: list[tuple[str, frozenset[str]]] = [
    ("00", frozenset({"title", "problem_statement", "in_scope", "out_of_scope"})),
    ("02", frozenset({"components", "connections", "tech_stack"})),
    ("03", frozenset({"terms"})),
    ("04", frozenset({"functional_requirements"})),
    ("09", frozenset({"milestones"})),
    ("12", frozenset({"jobs", "coverage_thresholds"})),
    ("16", frozenset({"plan", "execution"})),
]


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _load_registry():
    """Return a SchemaRegistry pointed at the toolkit root.

    Import is deferred so collection works without specdev_env active
    (pytest collection itself never exercises this path, but the guard
    is belt-and-suspenders for IDEs that import test modules eagerly).
    """
    from specdev_tools.core.registry import SchemaRegistry  # noqa: PLC0415
    return SchemaRegistry(str(_TOOLKIT_ROOT))


def _merged_props(step_id: str) -> dict[str, Any]:
    """Return the merged property map for *step_id* via merge_allof.

    Replicates the exact call chain in
    ``structure.py::_output_schema_keys`` — including the same
    SchemaRegistry instance — so the test exercises the live path WS3
    modified.
    """
    from specdev_tools.context._utils import (  # noqa: PLC0415
        find_step_schema_uri,
        merge_allof,
    )

    reg = _load_registry()
    uri = find_step_schema_uri(step_id, reg)
    assert uri, f"Could not find schema URI for step {step_id!r} in registry"

    schema = reg.load(uri)
    result = merge_allof(schema, reg)
    return result["properties"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMergeAllofUnionInvariant:
    """Parametrised behavior-preservation tests for merge_allof (WS3 gate).

    Each test asserts the UNION property: own step keys AND step-base keys
    are both present in the merged output, proving neither half was dropped.
    """

    @pytest.mark.parametrize("step_id", [c[0] for c in _STEP_CASES])
    def test_step_base_keys_survive_allof_merge(
        self, step_id: str
    ) -> None:
        """Step-base keys (id, owner, created_at, canonical_refs_used) must be
        present in the merged property set for every step.

        These keys come exclusively from the ``$ref(vc:core:step-base)``
        allOf branch; their absence would mean the branch was dropped.
        This is the half-invariant that the CLI ``output_schema_keys``
        cannot verify (it strips boilerplate keys before returning).
        """
        props = _merged_props(step_id)
        missing = _STEP_BASE_KEYS - set(props)
        assert not missing, (
            f"Step {step_id!r}: step-base keys dropped from merged output — "
            f"missing: {sorted(missing)}. "
            f"Actual props: {sorted(props)}"
        )

    @pytest.mark.parametrize("step_id,expected_own_keys", _STEP_CASES)
    def test_own_step_keys_not_overwritten(
        self, step_id: str, expected_own_keys: frozenset[str]
    ) -> None:
        """Step-specific own keys must be present in the merged output.

        These keys are declared on the step schema itself (either at root
        ``properties`` or in an ``allOf`` branch other than step-base).
        Their absence would mean the P2 overwrite regression recurred —
        own properties silently discarded because the allOf merge did a
        ``base['properties'] = merged_props`` overwrite instead of a
        union.
        """
        props = _merged_props(step_id)
        missing = expected_own_keys - set(props)
        assert not missing, (
            f"Step {step_id!r}: own step keys dropped from merged output — "
            f"missing: {sorted(missing)}. "
            f"Actual props: {sorted(props)}"
        )

    @pytest.mark.parametrize("step_id,expected_own_keys", _STEP_CASES)
    def test_union_invariant_both_halves_present(
        self, step_id: str, expected_own_keys: frozenset[str]
    ) -> None:
        """Composite: BOTH step-base keys AND step-own keys present.

        This is the definitive union assertion that captures the full WS3
        guarantee in a single parametrised check: the merge is a UNION, so
        no source is discarded.
        """
        props = _merged_props(step_id)
        all_expected = _STEP_BASE_KEYS | expected_own_keys
        missing = all_expected - set(props)
        assert not missing, (
            f"Step {step_id!r}: union invariant violated — "
            f"missing keys: {sorted(missing)}. "
            f"Actual props: {sorted(props)}"
        )


# ---------------------------------------------------------------------------
# _get_all_properties (registry/generate.py) — WS3 second reroute guard
# ---------------------------------------------------------------------------

# Own root-level properties for the two steps whose own keys are declared at
# the schema ROOT (alongside allOf step-base $ref).  The no-op resolver in
# _get_all_properties intentionally does NOT resolve vc:core:step-base, so
# step-base keys will be ABSENT from the result — that is the expected behavior.
#
# Steps selected:
#   "09"  — root properties: tech_stack, tech_stack_ref, milestones, …
#   "16"  — root properties: extensions, plan, execution, review, …
_GET_ALL_PROPS_CASES: list[tuple[str, frozenset[str]]] = [
    ("09", frozenset({"milestones", "tech_stack"})),
    ("16", frozenset({"plan", "execution"})),
]


def _get_all_props_for_step(step_id: str) -> dict:
    """Return the _get_all_properties result for *step_id*.

    Mirrors how generate.py itself invokes _get_all_properties inside
    _scan_schema_for_arrays: load the schema file, call the function directly.
    """
    from specdev_tools.registry import generate  # noqa: PLC0415

    schema_dir = str(_TOOLKIT_ROOT / "schema")
    schema_path = generate._schema_file_for_step(step_id, schema_dir)
    assert schema_path, f"No schema file found for step {step_id!r}"
    schema = generate._load_json(schema_path)
    return generate._get_all_properties(schema)


class TestGetAllPropertiesNoopResolver:
    """Behavior-preservation gate for _get_all_properties (WS3 second reroute).

    _get_all_properties uses a no-op resolver — it intentionally does NOT
    resolve the vc:core:step-base $ref branch.  The critical invariant is:

    1. Own root-level properties SURVIVE the merge (regression guard: an
       overwrite bug would clobber root props to empty).
    2. Step-base keys are ABSENT (proves the no-op resolver is genuinely
       exercised and the allOf $ref branch is correctly skipped).

    This contrasts with TestMergeAllofUnionInvariant where step-base keys ARE
    expected to be present (merge_allof resolves the $ref fully).
    """

    @pytest.mark.parametrize("step_id,expected_own_keys", _GET_ALL_PROPS_CASES)
    def test_own_root_keys_survive(
        self, step_id: str, expected_own_keys: frozenset[str]
    ) -> None:
        """Own root-level keys must be present in _get_all_properties output.

        These keys are declared directly in ``properties`` at the schema root.
        Under the original overwrite regression, the allOf merge would clobber
        root properties to empty, dropping all own keys.
        """
        props = _get_all_props_for_step(step_id)
        missing = expected_own_keys - set(props)
        assert not missing, (
            f"Step {step_id!r}: own root keys dropped from _get_all_properties "
            f"output — missing: {sorted(missing)}. "
            f"Actual props: {sorted(props)}"
        )

    @pytest.mark.parametrize("step_id", [c[0] for c in _GET_ALL_PROPS_CASES])
    def test_step_base_keys_absent_with_noop_resolver(
        self, step_id: str
    ) -> None:
        """Step-base keys must be ABSENT from _get_all_properties output.

        The no-op resolver in _get_all_properties returns None for any $ref
        node, causing effective_schema to treat the vc:core:step-base allOf
        branch as empty.  Step-base keys (id, owner, created_at,
        canonical_refs_used) must therefore NOT appear — their presence would
        indicate the no-op resolver is not being applied correctly.
        """
        props = _get_all_props_for_step(step_id)
        unexpectedly_present = _STEP_BASE_KEYS & set(props)
        assert not unexpectedly_present, (
            f"Step {step_id!r}: step-base keys unexpectedly present in "
            f"_get_all_properties output (no-op resolver should have skipped "
            f"the $ref branch) — found: {sorted(unexpectedly_present)}. "
            f"Actual props: {sorted(props)}"
        )
