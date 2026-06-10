"""Regression tests for E541 structural-schema suppression (DEVSPEC-38 follow-up).

Background
----------
Removing ``status_ref`` (DEVSPEC-38, v1.0.1 / v1.1.0) un-suppressed E541 on
narrative free-text fields of ``additionalProperties:false`` objects that have
no ``*_ref`` slot — making it structurally impossible to satisfy the E541
demand.  The fix adds a structural rule: if the enclosing object's JSON Schema
declares ``additionalProperties:false`` AND defines no ``*_ref``/``*_refs``
property, E541 is suppressed for all free-text fields of that object.

Four surfaces were affected on the host:
  1. plan.ambiguities[].description  (16_impl_context.schema.json, ap:false, no ref slot)
  2. plan.docs_impact.rationale       (16_impl_context.schema.json, ap:false, no ref slot)
  3. milestones[].name                (09_impl_plan.schema.json,    ap:false, no ref slot)
  4. execution.final_status.test_results[].name  (16_impl_context.schema.json, ap:UNSET)

Surfaces 1–3 are covered by the structural rule (this test file).
Surface 4 is covered by the ``execution`` key-name skip in ``_E541_SKIP_KEYS``
(ap:UNSET = free-form test-runner output, not spec vocabulary).

Both-directions guard (DoD #1)
-------------------------------
- (a) Surfaces 1–3: narrative field mentioning a canonical term on a ref-less
  ``additionalProperties:false`` object → E541 must NOT fire.
- (b) A ref-capable object (``additionalProperties:false`` WITH a ``*_ref``
  slot) → E541 MUST still fire when the term appears with no ref bound.
  This proves the structural rule does NOT over-suppress.

The (b) case uses ``14_roadmap.json`` milestones which are the exact structural
near-twin of (a)'s ``09_impl_plan.json`` milestones: both have ap:false, but
14_roadmap has ``fr_refs``/``capability_refs`` while 09_impl_plan has none.

Direct resolver assertion (trap guard)
---------------------------------------
The advisor flagged: the both-directions end-to-end test can pass with the
structural rule completely broken if schema nav fails silently and falls back to
"fire E541" for the (b) case.  To prevent this, the tests below include a
DIRECT assertion on the schema resolver: it must return the correct
``additionalProperties`` + ref-slot evidence for both schemas.  A green
both-directions test on top of a broken resolver would still fail the
direct-resolver test.
"""
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.validation.hallucination_lint import (
    _check_free_text_terms,
    _is_structurally_unbindable,
    _SchemaResolverCtx,
    lint_hallucinations,
)
from specdev_tools.core.schema_nav import effective_schema as _nav_effective_schema

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOOLKIT_ROOT = str(Path(__file__).parents[5])  # tools/specdev_tools/validation/linters → toolkit root


def _codes(errs):
    return [e.code for e in errs]


def _write_minimal_canon(root: Path, *labels: str) -> None:
    """Write a canon/manifest.json with one term entry per label."""
    canon = root / "canon"
    canon.mkdir(exist_ok=True)
    entries = []
    for label in labels:
        entries.append({
            "id": f"cn:project:term:{label.lower()}",
            "kind": "term",
            "preferred_label": label,
            "version": "1.0.0",
            "status": "active",
            "aliases": [],
            "lifecycle": {"introduced_at": "2026-01-01T00:00:00Z"},
        })
    (canon / "manifest.json").write_text(
        json.dumps({"registry_version": "1.0.0", "entries": entries, "aliases": []}),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Direct resolver assertions (trap guard — must pass independently of E541)
# ---------------------------------------------------------------------------

class TestSchemaResolverCtx:
    """Directly assert that the schema resolver navigates 09_impl_plan and
    14_roadmap milestones items correctly.

    These tests are the trap guard.  If the allOf-merge or ref-resolution is
    broken, these fail even when the both-directions E541 tests accidentally
    pass (e.g. because schema-nav failure silently fires E541 on (b) via the
    fallback path rather than via correct ref-slot detection).
    """

    def test_09_impl_plan_milestones_item_is_structurally_unbindable(self):
        """09_impl_plan.schema.json milestones items: ap:false, no ref slot → unbindable."""
        ctx = _SchemaResolverCtx(_TOOLKIT_ROOT)
        # Synthesise a minimal data dict with the correct $schema URI
        data: dict[str, Any] = {"$schema": "vc:09-impl-plan", "milestones": []}
        eff_root, resolve_fn = ctx.load_file_schema(data)
        assert eff_root is not None, (
            "Schema resolver must return a non-None effective root for vc:09-impl-plan"
        )
        # Navigate: root → milestones (array) → items (object)
        milestones_schema = eff_root.get("properties", {}).get("milestones")
        assert milestones_schema is not None, "milestones property must be present in 09_impl_plan schema"
        eff_milestones = _nav_effective_schema(milestones_schema, resolve_fn, include_conditionals=True)
        items_raw = eff_milestones.get("items")
        assert isinstance(items_raw, dict), "milestones.items must be a dict schema node"
        eff_items = _nav_effective_schema(items_raw, resolve_fn, include_conditionals=True)

        # Key assertions: ap:false, no *_ref/*_refs property
        assert eff_items.get("additionalProperties") is False, (
            "09_impl_plan milestones item must have additionalProperties:false"
        )
        ref_keys = [k for k in eff_items.get("properties", {}) if k.endswith("_ref") or k.endswith("_refs")]
        assert ref_keys == [], (
            f"09_impl_plan milestones item must have no *_ref/*_refs properties; found: {ref_keys}"
        )
        assert _is_structurally_unbindable(eff_items) is True, (
            "_is_structurally_unbindable must return True for 09_impl_plan milestones item"
        )

    def test_14_roadmap_milestones_item_is_ref_capable(self):
        """14_roadmap.schema.json milestones items: ap:false but HAS fr_refs/capability_refs → ref-capable.

        This is the critical near-twin: same ap:false but WITH ref slots.
        _is_structurally_unbindable must return False here.
        """
        ctx = _SchemaResolverCtx(_TOOLKIT_ROOT)
        data: dict[str, Any] = {"$schema": "vc:14-roadmap", "milestones": []}
        eff_root, resolve_fn = ctx.load_file_schema(data)
        assert eff_root is not None, (
            "Schema resolver must return a non-None effective root for vc:14-roadmap"
        )
        # Navigate to milestones items
        milestones_schema = eff_root.get("properties", {}).get("milestones")
        assert milestones_schema is not None, "milestones property must be present in 14_roadmap schema"
        eff_milestones = _nav_effective_schema(milestones_schema, resolve_fn, include_conditionals=True)
        items_raw = eff_milestones.get("items")
        assert isinstance(items_raw, dict), "milestones.items must be a dict schema node"
        eff_items = _nav_effective_schema(items_raw, resolve_fn, include_conditionals=True)

        # Key assertions: ap:false BUT has fr_refs and capability_refs
        assert eff_items.get("additionalProperties") is False, (
            "14_roadmap milestones item must have additionalProperties:false"
        )
        ref_keys = {k for k in eff_items.get("properties", {}) if k.endswith("_ref") or k.endswith("_refs")}
        assert "fr_refs" in ref_keys, (
            f"14_roadmap milestones item must have fr_refs in properties; got: {sorted(ref_keys)}"
        )
        assert "capability_refs" in ref_keys, (
            f"14_roadmap milestones item must have capability_refs in properties; got: {sorted(ref_keys)}"
        )
        assert _is_structurally_unbindable(eff_items) is False, (
            "_is_structurally_unbindable must return False for 14_roadmap milestones item "
            "(it has fr_refs/capability_refs ref slots)"
        )


# ---------------------------------------------------------------------------
# Surface 3: milestones[].name — both-directions unit tests
# ---------------------------------------------------------------------------

class TestMilestonesNameStructuralRule:
    """Both-directions guard for surface 3 (milestones[].name in 09_impl_plan)."""

    def _ctx_and_terms(self):
        ctx = _SchemaResolverCtx(_TOOLKIT_ROOT)
        canonical_terms = {"ghost": {"cn:project:term:ghost"}}
        return ctx, canonical_terms

    def test_09_impl_plan_milestones_name_suppressed(self):
        """(a) milestones[].name in 09_impl_plan must NOT fire E541.

        09_impl_plan milestones item: ap:false, no *_ref slot → structurally
        unbindable → E541 suppressed by structural rule.
        """
        ctx, canonical_terms = self._ctx_and_terms()
        data = {
            "$schema": "vc:09-impl-plan",
            "milestones": [
                {
                    "milestone_id": "ms-ghost-setup",
                    "name": "Ghost platform setup milestone",
                    "status": "active",
                    "deliverables": [{"type": "fr", "id": "fr-ghost-setup"}],
                    # No *_ref/*_refs on this item — structural rule must handle it
                }
            ],
        }
        eff_schema, resolve_fn = ctx.load_file_schema(data)
        errs = _check_free_text_terms(
            "09_impl_plan.json", data, canonical_terms,
            schema_node=eff_schema, resolve_fn=resolve_fn,
        )
        e541 = [e for e in errs if e.code == "E541"]
        assert not e541, (
            f"milestones[].name in 09_impl_plan must be suppressed by structural rule; "
            f"got: {[e.render() for e in e541]}"
        )

    def test_14_roadmap_milestones_name_still_fires(self):
        """(b) milestones[].name in 14_roadmap MUST still fire E541.

        14_roadmap milestones item: ap:false WITH fr_refs/capability_refs →
        structurally ref-capable → E541 must not be suppressed.

        This is the over-suppression guard: if the structural rule incorrectly
        skips 14_roadmap, this test fails.
        """
        ctx, canonical_terms = self._ctx_and_terms()
        data = {
            "$schema": "vc:14-roadmap",
            "milestones": [
                {
                    "milestone_id": "ms-ghost-setup",
                    "name": "Ghost platform setup milestone",
                    "status": "planned",
                    "deliverables": [{"type": "fr", "id": "fr-ghost-setup"}],
                    # No fr_refs/capability_refs bound → E541 MUST fire
                }
            ],
        }
        eff_schema, resolve_fn = ctx.load_file_schema(data)
        errs = _check_free_text_terms(
            "14_roadmap.json", data, canonical_terms,
            schema_node=eff_schema, resolve_fn=resolve_fn,
        )
        e541 = [e for e in errs if e.code == "E541"]
        assert e541, (
            "milestones[].name in 14_roadmap must still fire E541 — it has fr_refs/capability_refs "
            "ref slots (over-suppression guard failed)"
        )


# ---------------------------------------------------------------------------
# Surfaces 1 & 2: plan.ambiguities[] and plan.docs_impact — structural rule
# ---------------------------------------------------------------------------

class TestPlanSubtreesStructuralRule:
    """Surfaces 1 and 2 (plan.ambiguities[].description, plan.docs_impact.rationale)."""

    def test_ambiguities_description_suppressed(self):
        """(a) plan.ambiguities[].description must NOT fire E541 (structural rule)."""
        ctx = _SchemaResolverCtx(_TOOLKIT_ROOT)
        canonical_terms = {"ghost": {"cn:project:term:ghost"}}
        data = {
            "$schema": "vc:16-impl-context",
            "plan": {
                "ambiguities": [
                    {
                        "id": "amb-01",
                        "description": "Ghost admin login behaviour is underspecified",
                        "impact": "medium",
                        "resolution": "deferred",
                    }
                ]
            },
        }
        eff_schema, resolve_fn = ctx.load_file_schema(data)
        errs = _check_free_text_terms(
            "ms_plan.json", data, canonical_terms,
            schema_node=eff_schema, resolve_fn=resolve_fn,
        )
        e541 = [e for e in errs if e.code == "E541"]
        assert not e541, (
            f"plan.ambiguities[].description must be suppressed; got: {[e.render() for e in e541]}"
        )

    def test_docs_impact_rationale_suppressed(self):
        """(a) plan.docs_impact.rationale must NOT fire E541 (structural rule)."""
        ctx = _SchemaResolverCtx(_TOOLKIT_ROOT)
        canonical_terms = {"ghost": {"cn:project:term:ghost"}}
        data = {
            "$schema": "vc:16-impl-context",
            "plan": {
                "docs_impact": {
                    "rationale": "Ghost theme documentation needs updating after this change",
                    "affected_docs": [],
                }
            },
        }
        eff_schema, resolve_fn = ctx.load_file_schema(data)
        errs = _check_free_text_terms(
            "ms_plan.json", data, canonical_terms,
            schema_node=eff_schema, resolve_fn=resolve_fn,
        )
        e541 = [e for e in errs if e.code == "E541"]
        assert not e541, (
            f"plan.docs_impact.rationale must be suppressed; got: {[e.render() for e in e541]}"
        )


# ---------------------------------------------------------------------------
# Surface 4: execution.final_status.test_results[].name — key-name skip
# ---------------------------------------------------------------------------

class TestExecutionTestResultsSkip:
    """Surface 4: execution.final_status.test_results[].name.

    test_results items have additionalProperties UNSET (free-form).  The
    structural rule requires ap:false and will NOT suppress these; they are
    covered by the 'execution' key-name skip in _E541_SKIP_KEYS.
    """

    def test_test_results_name_suppressed(self):
        """execution.final_status.test_results[].name must NOT fire E541."""
        canonical_terms = {"ghost": {"cn:project:term:ghost"}}
        obj = {
            "execution": {
                "final_status": {
                    "test_results": [
                        {"name": "Ghost admin login test", "status": "pass"},
                    ]
                }
            }
        }
        errs = _check_free_text_terms("ms_plan.json", obj, canonical_terms)
        e541 = [e for e in errs if e.code == "E541"]
        assert not e541, (
            f"execution.final_status.test_results[].name must be suppressed; "
            f"got: {[e.render() for e in e541]}"
        )


# ---------------------------------------------------------------------------
# End-to-end via lint_hallucinations — all four surfaces + over-suppression guard
# ---------------------------------------------------------------------------

class TestE541StructuralRuleEndToEnd:
    """End-to-end tests driving lint_hallucinations with a real spec directory."""

    def _setup_spec(self, root: Path, spec_data: dict, filename: str) -> None:
        _write_minimal_canon(root, "Ghost", "tag", "theme", "email")
        spec = root / "spec"
        spec.mkdir()
        (spec / filename).write_text(json.dumps(spec_data), encoding="utf-8")

    def test_09_impl_plan_milestones_name_suppressed_end_to_end(self):
        """Surface 3: milestones[].name in 09_impl_plan must not fire E541 end-to-end."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._setup_spec(root, {
                "$schema": "vc:09-impl-plan",
                "milestones": [
                    {
                        "milestone_id": "ms-ghost-setup",
                        "name": "Ghost theme and tag setup",
                        "status": "active",
                        "deliverables": [{"type": "fr", "id": "fr-ghost-setup"}],
                    }
                ],
            }, "09_impl_plan.json")
            errs = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                require_manifest_schema_registration=False,
            )
            e541 = [e for e in errs if e.code == "E541"]
            assert not e541, (
                f"milestones[].name in 09_impl_plan must be suppressed end-to-end; "
                f"got: {[e.render() for e in e541]}"
            )

    def test_14_roadmap_milestones_name_still_fires_end_to_end(self):
        """Over-suppression guard: milestones[].name in 14_roadmap must still fire E541 end-to-end.

        14_roadmap milestone items have fr_refs/capability_refs → ref-capable →
        E541 must fire when no binding is provided.  This is the DoD #1(b) guard.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._setup_spec(root, {
                "$schema": "vc:14-roadmap",
                "milestones": [
                    {
                        "milestone_id": "ms-ghost-setup",
                        "name": "Ghost theme and tag setup",
                        "status": "planned",
                        "deliverables": [{"type": "fr", "id": "fr-ghost-setup"}],
                        # No fr_refs/capability_refs → E541 must fire
                    }
                ],
            }, "14_roadmap.json")
            errs = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                require_manifest_schema_registration=False,
            )
            e541 = [e for e in errs if e.code == "E541"]
            assert e541, (
                "milestones[].name in 14_roadmap must still fire E541 end-to-end "
                "(over-suppression guard failed)"
            )

    def test_16_impl_context_surfaces_suppressed_end_to_end(self):
        """Surfaces 1, 2, 4: plan.ambiguities, plan.docs_impact, execution.test_results
        must all be suppressed end-to-end."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._setup_spec(root, {
                "$schema": "vc:16-impl-context",
                "plan": {
                    "ambiguities": [
                        {
                            "id": "amb-01",
                            "description": "Ghost tag filtering behaviour is underspecified",
                            "impact": "medium",
                            "resolution": "deferred",
                        }
                    ],
                    "docs_impact": {
                        "rationale": "Ghost theme docs need updating after tag email changes",
                        "affected_docs": [],
                    },
                },
                "execution": {
                    "files_touched": [],
                    "execution_results": [],
                    "critical_evidence": {
                        "satisfied_checklist_ids": [],
                        "passed_test_commands": [],
                    },
                    "emergent_ambiguities": [],
                    "final_status": {
                        "test_results": [
                            {"name": "Ghost admin login with tag filter", "status": "pass"},
                        ]
                    },
                },
            }, "ms_bootstrap_plan.json")
            errs = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                require_manifest_schema_registration=False,
            )
            e541 = [e for e in errs if e.code == "E541"]
            assert not e541, (
                f"Surfaces 1/2/4 must all be suppressed end-to-end; "
                f"got {len(e541)} E541(s): {[e.render() for e in e541]}"
            )

    def test_no_schema_falls_back_to_key_name_skips(self):
        """Files without $schema fall back to key-name skips only.

        When $schema is absent, load_file_schema returns (None, None) and the
        structural rule is inactive.  The key-name skips in _E541_SKIP_KEYS
        must still suppress the affected subtrees.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Write canon without going through _setup_spec
            _write_minimal_canon(root, "Ghost")
            spec = root / "spec"
            spec.mkdir()
            # Hand-authored file with no $schema — mimics old/migrated artifacts
            (spec / "hand_authored.json").write_text(
                json.dumps({
                    # No $schema — structural rule inactive
                    "ambiguities": [
                        {"id": "amb-01", "description": "Ghost admin behaviour is unclear"}
                    ],
                    "execution": {
                        "final_status": {
                            "test_results": [{"name": "Ghost login test", "status": "pass"}]
                        }
                    },
                }),
                encoding="utf-8",
            )
            errs = lint_hallucinations(
                str(spec),
                repo_root=str(root),
                require_manifest_schema_registration=False,
            )
            e541 = [e for e in errs if e.code == "E541"]
            assert not e541, (
                f"Key-name skips must cover affected subtrees when $schema is absent; "
                f"got: {[e.render() for e in e541]}"
            )
