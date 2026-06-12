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
    _extract_slot_kinds,
    _term_kinds_from_cids,
    _SchemaResolverCtx,
    lint_hallucinations,
)
from specdev_tools.core.schema_nav import effective_schema as _nav_effective_schema

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOOLKIT_ROOT = str(Path(__file__).parents[4])  # tests/unit/validation/linters → toolkit root


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

    def test_14_roadmap_milestones_name_suppressed_round4(self):
        """(round-4) milestones[].name in 14_roadmap is suppressed by namespace-aware rule.

        PREMISE CHANGE (round 4): pre-round-4 this test asserted E541 fires
        because 14_roadmap milestones have ``fr_refs``/``capability_refs`` ref
        slots.  Round-4 overturns that premise: the namespace-aware check
        asks whether ANY slot can bind a *term* or *acronym* id — not just
        whether any slot exists at all.

        14_roadmap milestone item: ap:false, ref slots = {fr_refs, capability_refs}.
        Slot kinds = {"fr", "capability"}.  Fired term kind = "term".
        Since "term" ∉ {"fr", "capability"}, binding is structurally impossible
        → E541 MUST be suppressed for kind=term terms.

        The over-suppression guardrail is
        ``TestRound4GuardrailNamespaceMatchingStillFires`` (which uses a
        synthetic schema WITH a ``term_ref`` slot and verifies E541 still fires
        when the slot is absent or bound to the wrong id), plus the real-schema
        unit test
        ``TestRound4GuardrailRealSchemaStillFires::test_glossary_term_ref_slot_unbound_fires``
        (which drives ``vc:03-glossary`` through ``_SchemaResolverCtx`` and
        confirms E541 fires for an unbound mention with ``term_ref`` available
        in the schema).
        Note: ``14_roadmap.schema.json`` has NO ``term_ref`` slot, so a
        "14_roadmap with term_ref" test is structurally incoherent and does not
        exist; ``03_glossary.json`` (the only schema with ``term_ref``) is the
        coherent vehicle.
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
                    # fr_refs/capability_refs slots exist, but kinds are "fr"/"capability"
                    # → no namespace overlap with term kind → E541 suppressed (round 4)
                }
            ],
        }
        eff_schema, resolve_fn = ctx.load_file_schema(data)
        errs = _check_free_text_terms(
            "14_roadmap.json", data, canonical_terms,
            schema_node=eff_schema, resolve_fn=resolve_fn,
        )
        e541 = [e for e in errs if e.code == "E541"]
        assert not e541, (
            "milestones[].name in 14_roadmap must be suppressed by round-4 namespace-aware "
            "rule: fr_refs/capability_refs slots have kinds 'fr'/'capability' which do not "
            "match the term kind 'term'; got: " + str([e.render() for e in e541])
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

    def test_14_roadmap_milestones_name_suppressed_round4_end_to_end(self):
        """Round-4: milestones[].name in 14_roadmap is suppressed end-to-end.

        PREMISE CHANGE (round 4): pre-round-4 this test asserted E541 fires
        because 14_roadmap milestones have fr_refs/capability_refs.  Round-4
        overturns that: slot kinds {"fr", "capability"} don't match term kind
        "term" → namespace-aware suppression → E541 must NOT fire.

        The over-suppression guardrail has moved to
        ``test_03_glossary_terms_definition_without_term_ref_fires`` which
        proves a genuinely-unbound term (object HAS a matching term_ref slot
        but it is NOT bound to the term id) STILL fires E541.
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
                        # fr_refs/capability_refs have kinds "fr"/"capability" —
                        # no namespace overlap with "term" → suppressed (round 4)
                    }
                ],
            }, "14_roadmap.json")
            errs = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                require_manifest_schema_registration=False,
            )
            e541 = [e for e in errs if e.code == "E541"]
            assert not e541, (
                "milestones[].name in 14_roadmap must be suppressed by round-4 "
                "namespace-aware rule (fr_refs/capability_refs are not term-kind); "
                "got: " + str([e.render() for e in e541])
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

    def test_03_glossary_terms_definition_without_term_ref_fires(self):
        """End-to-end guard: E541 FIRES for a genuinely-unbound term with a real schema.

        This is the both-directions side (b) guard for the round-4 namespace-aware
        suppression: an object that HAS a matching ``term_ref`` slot (so the slot
        kind DOES overlap the term kind → no namespace suppression) but does NOT
        bind the mentioned term must still fire E541.

        Vehicle: a spec file with ``$schema: vc:03-glossary`` (the real glossary
        schema, which has a ``term_ref`` slot on ``terms[]`` items → slot_kinds
        includes "term" → namespace check does NOT suppress).  The file is named
        ``glossary.json`` (not ``03_glossary.json``) so the file-scoped
        ``definition`` Category-A skip does not apply — ``definition`` is a live
        free-text field here.  The terms item mentions "Ghost" in ``definition``
        but provides no ``term_ref`` binding → ``bound_ref_ids ∩ cids = ∅`` →
        E541 must fire.

        This confirms that round-4 namespace-aware suppression does NOT
        over-suppress: when slot kind matches the term kind, the check falls
        through to mechanism-2 (term-specific runtime check) and fires correctly.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_minimal_canon(root, "Ghost")
            spec = root / "spec"
            spec.mkdir()
            # File NOT named "03_glossary.json" → file-scoped definition skip inactive
            # $schema vc:03-glossary → real schema nav → term_ref slot present in schema
            # → slot_kinds includes "term" → no namespace suppression
            # definition mentions "ghost" with no term_ref in data → E541 fires
            (spec / "glossary.json").write_text(
                json.dumps({
                    "$schema": "vc:03-glossary",
                    "terms": [
                        {
                            "term_id": "term-theme",
                            "term": "Theme",
                            "definition": "The Ghost theme system for rendering pages.",
                            # term_ref slot exists in schema but is absent here → unbound
                        }
                    ],
                }),
                encoding="utf-8",
            )
            errs = lint_hallucinations(
                str(spec),
                repo_root=str(root),
                require_manifest_schema_registration=False,
            )
            e541 = [e for e in errs if e.code == "E541"]
            assert e541, (
                "E541 must fire end-to-end for a genuinely-unbound term when the real "
                "vc:03-glossary schema provides a term_ref slot (slot_kinds ∋ 'term') "
                "but the data contains no term_ref binding — round-4 namespace suppression "
                "must NOT over-suppress when slot kind matches term kind. "
                "This is the DoD #1(b) both-directions end-to-end guard."
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


# ---------------------------------------------------------------------------
# Term-specific runtime suppression (the bound_refs path)
# ---------------------------------------------------------------------------

class TestBoundRefsTermSpecificSuppression:
    """Runtime ``bound_refs`` suppression must be term-specific, not object-level.

    A sibling ``*_ref`` / ``*_refs`` key suppresses E541 only for the term whose
    canonical id it actually binds (one of the ref's values is in the term's
    ``cids`` set). An unrelated reference — binding a *different* canonical id —
    must NOT suppress a mention of a different, still-unbound term.

    Regression guard for the object-level over-suppression bug, where the mere
    presence of any ``*_ref`` on a dict silenced E541 for every free-text field.

    These tests pass ``schema_node=None`` so the structural rule is inactive and
    the runtime ``bound_refs`` path is the sole suppressor under test.
    """

    _TERMS = {
        "ghost": {"cn:project:term:ghost"},
        "tag": {"cn:project:term:tag"},
    }

    def test_bound_refs_unrelated_ref_does_not_suppress(self):
        """An unrelated ``*_ref`` (binding a different id) must NOT suppress E541."""
        obj = {
            "description": "Ghost admin login behaviour is underspecified",
            "tag_ref": "cn:project:term:tag",  # binds 'tag', NOT 'ghost'
        }
        errs = _check_free_text_terms("x.json", obj, self._TERMS)
        e541 = [e for e in errs if e.code == "E541"]
        assert e541, (
            "An unrelated *_ref (binding a different canonical id) must not "
            "suppress E541 for a different, unbound term ('ghost')"
        )

    def test_bound_refs_matching_ref_suppresses(self):
        """A ``*_ref`` binding the mentioned term's own canonical id suppresses E541."""
        obj = {
            "description": "Ghost admin login behaviour is underspecified",
            "term_ref": "cn:project:term:ghost",  # binds the mentioned term
        }
        errs = _check_free_text_terms("x.json", obj, self._TERMS)
        e541 = [e for e in errs if e.code == "E541"]
        assert not e541, (
            f"A *_ref binding the mentioned term's id must suppress E541; "
            f"got: {[e.render() for e in e541]}"
        )

    def test_bound_refs_matching_ref_in_list_suppresses(self):
        """The ``*_refs`` list form suppresses when the bound id is in the list."""
        obj = {
            "description": "Ghost admin login behaviour is underspecified",
            "term_refs": ["cn:project:term:other", "cn:project:term:ghost"],
        }
        errs = _check_free_text_terms("x.json", obj, self._TERMS)
        e541 = [e for e in errs if e.code == "E541"]
        assert not e541, (
            f"A *_refs list containing the mentioned term's id must suppress E541; "
            f"got: {[e.render() for e in e541]}"
        )

    def test_bound_refs_partial_binding_still_fires_for_unbound_term(self):
        """A ref binding one term must not suppress a second, unbound term in the same field."""
        obj = {
            "description": "Ghost integrates with the tag subsystem",
            "term_ref": "cn:project:term:tag",  # binds 'tag' only; 'ghost' unbound
        }
        errs = _check_free_text_terms("x.json", obj, self._TERMS)
        e541 = [e for e in errs if e.code == "E541"]
        assert e541, (
            "A ref binding only 'tag' must still leave 'ghost' unbound → E541 fires"
        )


# ---------------------------------------------------------------------------
# Round-4 helpers — unit tests for _extract_slot_kinds and _term_kinds_from_cids
# ---------------------------------------------------------------------------

class TestRound4Helpers:
    """Unit tests for the two round-4 helper functions.

    These functions underpin the namespace-aware suppression logic; verifying
    them independently gives a second line of defence against regressions that
    might be masked by an accidentally-passing integration test.
    """

    def test_extract_slot_kinds_returns_none_for_open_schema(self):
        """Open schema (ap not False) → None (don't suppress)."""
        schema_open = {
            "type": "object",
            "properties": {"term_ref": {"type": "string"}},
            # additionalProperties NOT set → open schema
        }
        result = _extract_slot_kinds(schema_open)
        assert result is None, (
            "_extract_slot_kinds must return None for schemas without additionalProperties:false"
        )

    def test_extract_slot_kinds_returns_none_for_none_input(self):
        """None schema_node → None."""
        assert _extract_slot_kinds(None) is None

    def test_extract_slot_kinds_empty_for_closed_no_ref_slots(self):
        """Closed schema (ap:false) with no ref slots → empty set (all kinds suppressed)."""
        schema_closed_no_refs = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"id": {"type": "string"}, "description": {"type": "string"}},
        }
        result = _extract_slot_kinds(schema_closed_no_refs)
        assert result == set(), (
            "_extract_slot_kinds must return an empty set for closed schema with no ref slots"
        )

    def test_extract_slot_kinds_term_and_acronym(self):
        """Closed schema with term_ref and acronym_ref → {'term', 'acronym'}."""
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "term_ref": {"type": "object"},
                "acronym_ref": {"type": "object"},
                "unit_ref": {"type": "object"},
                "definition": {"type": "string"},
            },
        }
        result = _extract_slot_kinds(schema)
        assert result == {"term", "acronym", "unit"}, (
            f"Expected {{'term', 'acronym', 'unit'}}, got {result}"
        )

    def test_extract_slot_kinds_non_term_kinds(self):
        """NFR item: metric_ref, unit_ref, stage_ref, environment_ref → not term/acronym."""
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "metric_ref": {"type": "object"},
                "unit_ref": {"type": "object"},
                "stage_ref": {"type": "object"},
                "environment_ref": {"type": "object"},
                "name": {"type": "string"},
                "description": {"type": "string"},
            },
        }
        result = _extract_slot_kinds(schema)
        assert result == {"metric", "unit", "stage", "environment"}, (
            f"Expected {{'metric', 'unit', 'stage', 'environment'}}, got {result}"
        )
        assert "term" not in result, "NFR item schema must not include 'term' in slot_kinds"
        assert "acronym" not in result, "NFR item schema must not include 'acronym' in slot_kinds"

    def test_extract_slot_kinds_refs_plural(self):
        """Plural _refs slots are stripped correctly: fr_refs → 'fr'."""
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "fr_refs": {"type": "array"},
                "capability_refs": {"type": "array"},
            },
        }
        result = _extract_slot_kinds(schema)
        assert result == {"fr", "capability"}, (
            f"Expected {{'fr', 'capability'}}, got {result}"
        )

    def test_term_kinds_from_cids_project_term(self):
        """cn:project:term:<label> → {'term'}."""
        result = _term_kinds_from_cids({"cn:project:term:ghost"})
        assert result == {"term"}, f"Expected {{'term'}}, got {result}"

    def test_term_kinds_from_cids_core_acronym(self):
        """cn:core:acronym:jwt → {'acronym'}."""
        result = _term_kinds_from_cids({"cn:core:acronym:jwt"})
        assert result == {"acronym"}, f"Expected {{'acronym'}}, got {result}"

    def test_term_kinds_from_cids_mixed(self):
        """Multiple cids with different kinds → union of kinds."""
        result = _term_kinds_from_cids({"cn:core:term:jwt", "cn:core:acronym:jwt"})
        assert result == {"term", "acronym"}, f"Expected {{'term', 'acronym'}}, got {result}"

    def test_term_kinds_from_cids_malformed_ignored(self):
        """IDs not in the four-segment cn:<tier>:<kind>:<label> form are silently ignored.

        This covers:
        - 1-segment ("bad-id"): 1 part, not >= 4 → ignored
        - 3-segment ("cn:project:acronym"): 3 parts, not >= 4 → ignored despite
          appearing canonical; under the old >= 3 guard it would have produced
          "acronym", but the contract requires FOUR segments.

        A well-formed 4-segment ID mixed in must still produce its kind correctly.
        """
        # 1-segment: ignored
        assert _term_kinds_from_cids({"bad-id"}) == set(), (
            "'bad-id' is 1-segment and must be ignored → empty set"
        )
        # 3-segment: looks like cn:<tier>:<kind> but missing <label> → ignored
        assert _term_kinds_from_cids({"cn:project:acronym"}) == set(), (
            "'cn:project:acronym' is 3-segment (no label) and must be ignored; "
            "under >= 3 it would have produced 'acronym', but the contract requires 4 segments"
        )
        # 4-segment: valid
        result = _term_kinds_from_cids({"bad-id", "cn:project:acronym", "cn:project:term:ok"})
        assert result == {"term"}, (
            "Only the 4-segment 'cn:project:term:ok' is well-formed; "
            "bad-id (1-seg) and cn:project:acronym (3-seg) must both be ignored"
        )


# ---------------------------------------------------------------------------
# Round-4 guardrail: unbound term WITH matching term_ref slot STILL fires E541
# ---------------------------------------------------------------------------

class TestRound4GuardrailNamespaceMatchingStillFires:
    """Guardrail: namespace-aware suppression must NOT silence genuinely-unbound terms.

    An object that HAS a ``term_ref``/``acronym_ref`` slot (so the namespace
    DOES match a ``term``/``acronym`` canonical id) must still fire E541 when:
      (a) the slot is absent (unbound), or
      (b) the slot is bound to a *different* canonical id than the mentioned term.

    This mirrors the round-2 ``TestBoundRefsTermSpecificSuppression`` intent but
    adds the round-4 dimension: the fix must not suppress these cases under the
    namespace-aware check because the slot KIND matches → the namespace check
    passes through to the runtime ``bound_ref_ids`` check → E541 fires correctly.

    These tests use a synthetic schema with ``additionalProperties:false`` AND
    ``term_ref`` so that ``slot_kinds = {"term"}`` → no namespace suppression →
    mechanism-2 (term-specific ref-value check) is the sole decider.
    """

    _SCHEMA_WITH_TERM_REF = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "description": {"type": "string"},
            "term_ref": {"type": "string"},
        },
    }

    _TERMS = {
        "ghost": {"cn:project:term:ghost"},
    }

    def test_term_ref_slot_present_but_empty_fires_e541(self):
        """Object has term_ref slot (matching namespace) but no binding → E541 fires.

        This is the §4 guardrail: a term-capable object whose term_ref is absent
        (or not bound to the mentioned term's id) must still be flagged, regardless
        of round-4's namespace suppression logic.
        """
        obj = {
            "description": "Ghost admin login behaviour is underspecified",
            # term_ref is absent — the slot exists in schema but is not bound
        }
        # Pass the schema with term_ref → slot_kinds = {"term"} → no suppression
        errs = _check_free_text_terms(
            "x.json", obj, self._TERMS,
            schema_node=self._SCHEMA_WITH_TERM_REF,
            resolve_fn=lambda ref: None,  # trivial resolver — no $ref in this schema
        )
        e541 = [e for e in errs if e.code == "E541"]
        assert e541, (
            "An object with a term_ref slot (namespace matches 'term') but NO binding "
            "must still fire E541 — round-4 namespace suppression must not over-suppress. "
            f"(round-2 win preserved; slot_kinds should be {{'term'}} → passes through to E541)"
        )

    def test_term_ref_slot_bound_to_wrong_id_fires_e541(self):
        """Object has term_ref bound to a different id → E541 still fires for the mentioned term.

        Confirms that round-4 namespace-aware suppression (which only checks KIND
        membership, not id value) correctly defers to mechanism-2 (term-specific
        runtime check) when the slot kind matches but the bound id does not.
        """
        obj = {
            "description": "Ghost admin login behaviour is underspecified",
            "term_ref": "cn:project:term:other-term",  # wrong id, not ghost
        }
        errs = _check_free_text_terms(
            "x.json", obj, self._TERMS,
            schema_node=self._SCHEMA_WITH_TERM_REF,
            resolve_fn=lambda ref: None,
        )
        e541 = [e for e in errs if e.code == "E541"]
        assert e541, (
            "A term_ref bound to a DIFFERENT canonical id must not suppress E541 for "
            "the mentioned term — mechanism-2 (term-specific runtime check) must still fire."
        )

    def test_term_ref_slot_bound_correctly_suppresses(self):
        """Positive control: term_ref bound to the correct id must suppress E541.

        Confirms that when both namespace AND id match, suppression works as expected
        and mechanism-2 (round-2) correctly identifies the binding.
        """
        obj = {
            "description": "Ghost admin login behaviour is underspecified",
            "term_ref": "cn:project:term:ghost",  # correct binding
        }
        errs = _check_free_text_terms(
            "x.json", obj, self._TERMS,
            schema_node=self._SCHEMA_WITH_TERM_REF,
            resolve_fn=lambda ref: None,
        )
        e541 = [e for e in errs if e.code == "E541"]
        assert not e541, (
            f"A correctly-bound term_ref must suppress E541; got: {[e.render() for e in e541]}"
        )


# ---------------------------------------------------------------------------
# Round-4: Category-A semantic skip for 03_glossary.json terms[].definition
# ---------------------------------------------------------------------------

class TestGlossaryDefinitionSemanticSkip:
    """The glossary ``terms[].definition`` field must not fire E541.

    Rationale: the glossary IS the vocabulary source.  A definition mentioning
    other project terms (e.g., "The theme template system used by Ghost for
    rendering...") cannot be expected to bind every mentioned term via a
    ``term_ref`` — that would require each definition to be a cross-reference
    graph rather than prose.  The file-scoped Category-A skip for
    ``03_glossary.json`` → ``definition`` handles this.

    Note: the glossary ``terms[]`` DOES have ``term_ref``/``acronym_ref`` slots
    (used to bind the entry's OWN canonical id), so the namespace-aware structural
    rule does NOT suppress it.  This explicit skip is the only mechanism that
    covers it.  The test below verifies the skip fires for the glossary file and
    does NOT fire for a non-glossary file (ensuring the skip is scoped correctly).
    """

    _TERMS = {"ghost": {"cn:project:term:ghost"}}

    def test_glossary_definition_suppressed(self):
        """definition in 03_glossary.json must NOT fire E541."""
        obj = {
            "terms": [
                {
                    "term_id": "term-theme",
                    "term": "Theme",
                    "definition": "The Ghost theme system used for rendering pages.",
                    "term_ref": {"id": "cn:project:term:theme", "kind": "term"},
                    # 'ghost' is mentioned in definition but NOT bound via term_ref
                }
            ]
        }
        errs = _check_free_text_terms("03_glossary.json", obj, self._TERMS)
        e541 = [e for e in errs if e.code == "E541"]
        assert not e541, (
            f"03_glossary.json terms[].definition must be suppressed by Category-A skip; "
            f"got: {[e.render() for e in e541]}"
        )

    def test_non_glossary_definition_still_fires(self):
        """definition in a non-glossary file is NOT covered by the glossary skip.

        If a future step defines a ``definition`` field in an object with a
        ``term_ref`` slot, E541 must still fire when the term is unbound.
        This test uses schema_node=None (no structural suppression) to isolate
        the file-scoped skip behaviour.
        """
        obj = {
            "definition": "The Ghost admin login behaviour is underspecified",
            # No *_ref binding ghost → E541 should fire for non-glossary files
        }
        # Pass schema_node=None so structural/namespace suppression is inactive
        errs = _check_free_text_terms("04_fr_list.json", obj, self._TERMS)
        e541 = [e for e in errs if e.code == "E541"]
        assert e541, (
            "definition in a non-glossary file must still fire E541 — "
            "the Category-A skip is scoped to 03_glossary.json only"
        )


# ---------------------------------------------------------------------------
# Round-4 guardrail: real-schema term_ref slot unit test (Finding #2 / T1)
# ---------------------------------------------------------------------------

class TestRound4GuardrailRealSchemaStillFires:
    """Guardrail: real vc:03-glossary schema via _SchemaResolverCtx confirms E541 still fires.

    ``TestRound4GuardrailNamespaceMatchingStillFires`` uses a synthetic schema to
    isolate the mechanism-2 ref-value check.  This companion class exercises the
    REAL ``vc:03-glossary`` schema through ``_SchemaResolverCtx`` to ensure the
    schema-nav path itself does not introduce a regression.

    ``03_glossary.json`` is the only production schema with a ``term_ref`` slot on
    its data objects (``terms[]`` items).  Its ``terms[]`` item schema has
    ``additionalProperties:false`` and ``term_ref``/``acronym_ref``/``unit_ref``
    slots → ``slot_kinds = {"term", "acronym", "unit"}`` → the namespace-aware
    check does NOT suppress for term-kind terms → mechanism-2 (runtime bound-ref
    check) decides whether E541 fires.

    Note: the file-scoped ``definition`` skip applies when the filename is
    ``03_glossary.json``.  These tests use a different filename so the
    ``definition`` field is live and the real suppression path is exercised.
    """

    _TERMS = {"ghost": {"cn:project:term:ghost"}}

    def test_glossary_term_ref_slot_unbound_fires(self):
        """Real vc:03-glossary schema: term_ref slot present in schema but absent in data → E541 fires.

        This is the unit-level over-suppression boundary guard using the real
        schema (complement to ``TestRound4GuardrailNamespaceMatchingStillFires``
        which uses a synthetic schema).  It ensures that schema-nav failures
        cannot silently suppress E541 through this path.
        """
        ctx = _SchemaResolverCtx(_TOOLKIT_ROOT)
        data = {
            "$schema": "vc:03-glossary",
            "terms": [
                {
                    "term_id": "term-theme",
                    "term": "Theme",
                    "definition": "The Ghost theme system for rendering pages.",
                    # term_ref slot exists in schema but is absent here → unbound
                }
            ],
        }
        eff_schema, resolve_fn = ctx.load_file_schema(data)
        errs = _check_free_text_terms(
            # NOT "03_glossary.json" → file-scoped definition skip inactive
            "glossary.json", data, self._TERMS,
            schema_node=eff_schema, resolve_fn=resolve_fn,
        )
        e541 = [e for e in errs if e.code == "E541"]
        assert e541, (
            "vc:03-glossary terms[] item has term_ref slot (slot_kinds ∋ 'term') but "
            "no term_ref binding in data → mechanism-2 runtime check must fire E541. "
            "Round-4 namespace-aware suppression must NOT over-suppress when the slot "
            "kind matches the term kind."
        )

    def test_glossary_term_ref_slot_correctly_bound_suppresses(self):
        """Positive control: term_ref bound to the mentioned term's id suppresses E541.

        Confirms that when the real vc:03-glossary schema is used and the data
        contains a term_ref binding matching the mentioned term's canonical ID,
        E541 is correctly suppressed by mechanism-2.
        """
        ctx = _SchemaResolverCtx(_TOOLKIT_ROOT)
        data = {
            "$schema": "vc:03-glossary",
            "terms": [
                {
                    "term_id": "term-ghost",
                    "term": "Ghost",
                    "definition": "The Ghost CMS platform.",
                    "term_ref": "cn:project:term:ghost",  # correct binding
                }
            ],
        }
        eff_schema, resolve_fn = ctx.load_file_schema(data)
        errs = _check_free_text_terms(
            "glossary.json", data, self._TERMS,
            schema_node=eff_schema, resolve_fn=resolve_fn,
        )
        e541 = [e for e in errs if e.code == "E541"]
        assert not e541, (
            f"term_ref correctly bound to the mentioned term's id must suppress E541 "
            f"via mechanism-2; got: {[e.render() for e in e541]}"
        )


# ---------------------------------------------------------------------------
# patternProperties child-schema lookup coverage (Finding #4 / T3)
# ---------------------------------------------------------------------------

class TestPatternPropertiesChildSchemaLookup:
    """Coverage for the patternProperties fallback in _check_free_text_terms.

    When a dict key is not found in a schema's ``properties``, the child-schema
    lookup falls back to ``patternProperties``: the first pattern whose regex
    matches the key is used.  This branch IS reachable in production: the
    ``vc:seed-manifest`` schema's ``step_requirements`` property uses
    ``patternProperties`` (pattern ``^(\\d{2}[a-c]?)$``) so when
    ``_check_free_text_terms`` processes a ``step_requirements`` dict like
    ``{"00": [...], "01": [...]}`` it reaches this fallback for each key.

    These tests use synthetic schemas (honest: the production patternProperties
    sites contain array-typed values with no free-text opportunity, so we must
    synthesise to get discriminating E541 outcomes).  The synthetic schema tests
    the MECHANISM; the docstring above documents the real-world reachability.

    The discrimination test confirms the branch works correctly: a broken lookup
    (``child_schema=None``) would fall back to schema-less mode (no suppression,
    E541 fires).  A working lookup (``child_schema`` set to ap:false no-ref-slot
    schema) applies structural suppression (E541 suppressed).  So
    ``assert not e541`` passes ONLY when the patternProperties path computes and
    passes the correct ``child_schema``.
    """

    _TERMS = {"ghost": {"cn:project:term:ghost"}}

    def test_pattern_matched_key_gets_child_schema_suppression(self):
        """patternProperties lookup sets correct child_schema → suppression applied.

        Schema: outer dict has a ``patternProperties`` entry for ``^[a-z]+$``.
        Value schema: ``{ap:false, no *_ref slots, description field}`` →
        ``slot_kinds = set()`` → structurally unbindable → E541 suppressed.

        If the patternProperties lookup were broken (child_schema stays None):
        no structural suppression → E541 would fire → ``assert not e541`` fails.
        Therefore this assertion is a discriminating guard for the branch.

        Note: cited real-world reachability — ``vc:seed-manifest`` schema's
        ``step_requirements`` uses patternProperties (pattern ``^(\\d{2}[a-c]?)$``),
        and keys like ``"00"`` are not in ``properties``, so the fallback runs
        for every step-requirements key in a seed-manifest file.
        """
        pattern_value_schema: dict = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "description": {"type": "string"},
                # No *_ref/*_refs → slot_kinds = set() → structurally unbindable
            },
        }
        outer_schema: dict = {
            "type": "object",
            "additionalProperties": False,
            "properties": {},  # empty → key "abc" not found here
            "patternProperties": {
                "^[a-z]+$": pattern_value_schema,
            },
        }
        data = {
            "abc": {
                "description": "Ghost admin login behaviour is underspecified",
            }
        }
        errs = _check_free_text_terms(
            "x.json", data, self._TERMS,
            schema_node=outer_schema,
            resolve_fn=lambda ref: None,  # no $ref in synthetic schema
        )
        e541 = [e for e in errs if e.code == "E541"]
        assert not e541, (
            "patternProperties child_schema must be found and applied — the ap:false "
            "no-ref-slot value schema makes the object structurally unbindable → "
            "E541 must be suppressed. If this fails, the patternProperties lookup "
            "is broken (child_schema=None → no suppression → E541 fires). "
            f"Got: {[e.render() for e in e541]}"
        )

    def test_re_error_in_pattern_does_not_crash(self):
        """A malformed regex in patternProperties is silently skipped (no crash, no suppression).

        The ``re.error`` guard in the patternProperties loop must swallow the
        exception and continue to the next pattern.  If a bad pattern is the only
        one, no child_schema is found → schema-less mode → E541 fires normally.
        """
        bad_pattern_schema: dict = {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
            "patternProperties": {
                "[":  # invalid regex → re.error must be caught
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {"description": {"type": "string"}},
                    }
            },
        }
        data = {
            "abc": {
                "description": "Ghost admin login behaviour is underspecified",
            }
        }
        # Must not raise; and since bad pattern is skipped → child_schema=None →
        # no suppression → the inner object (no *_ref) fires E541 from the
        # schema-less runtime path.
        errs = _check_free_text_terms(
            "x.json", data, self._TERMS,
            schema_node=bad_pattern_schema,
            resolve_fn=lambda ref: None,
        )
        # Should not crash — that's the primary assertion.
        assert isinstance(errs, list), "re.error guard must not propagate exceptions"
        # Discriminating assertion: bad regex → pattern skipped → child_schema=None
        # → schema-less mode for the inner dict → structurally_unbindable=False →
        # slot_kinds=None → bound_ref_ids={} → E541 fires for the unbound "ghost" term.
        # This would be green even if the re.error guard were removed (crash would
        # surface), but it proves the schema-less fallback path fires E541 as documented.
        e541 = [e for e in errs if e.code == "E541"]
        assert len(e541) >= 1, (
            "bad-regex patternProperties: child_schema=None → schema-less mode → "
            "E541 must fire for the unbound 'ghost' mention; "
            f"got {len(e541)} E541(s) from {[e.render() for e in errs]}"
        )


# ---------------------------------------------------------------------------
# review_requirements key-name skip coverage (round-4 addition, DEVSPEC-38)
# ---------------------------------------------------------------------------

class TestReviewRequirementsKeyNameSkip:
    """The ``review_requirements`` subtree must not fire E541.

    ``review_requirements`` is in ``_E541_SKIP_KEYS`` (Category B) because its
    sub-fields (``test_commands``, ``nfr_measurement_methods``) contain
    operational verification instructions — not canonical term-binding sites.
    The structural rule cannot reliably suppress them (schema-nav loses
    ``additionalProperties`` through oneOf merges, and patternProperties values
    receive no child_schema), so an explicit key-name skip is required.

    The discriminating design: both tests use the same data and the same
    canonical term (``ghost``).  The ONLY variable is the parent key name.
    Under ``review_requirements`` the key-name skip fires and E541 is
    suppressed.  Under ``description`` (a non-skipped free-text key) E541
    fires — proving the fixture is not vacuous and that removing the
    ``review_requirements`` skip would break the suppression test.
    """

    _TERMS = {"ghost": {"cn:project:term:ghost"}}

    def test_review_requirements_key_name_suppressed(self):
        """Free-text value nested under ``review_requirements`` must NOT fire E541.

        _is_e541_skipped returns True for ``review_requirements`` → the entire
        subtree is skipped before any free-text checks run → E541 must be absent.
        """
        obj = {
            "review_requirements": {
                "description": "Ghost admin login flow passes end-to-end",
                "test_commands": [
                    "Ghost admin login flow passes end-to-end"
                ],
                "nfr_measurement_methods": {
                    "perf": "Measure Ghost page load under 500 ms"
                },
            }
        }
        errs = _check_free_text_terms("ms_plan.json", obj, self._TERMS)
        e541 = [e for e in errs if e.code == "E541"]
        assert not e541, (
            "review_requirements subtree must be suppressed by key-name skip in "
            "_E541_SKIP_KEYS; E541 must not fire for canonical terms mentioned in "
            "review_requirements.description (a _FREE_TEXT_FIELDS key) because the "
            "key-name skip fires before any free-text scan of the subtree; "
            f"got: {[e.render() for e in e541]}"
        )

    def test_review_requirements_non_skipped_sibling_still_fires(self):
        """Positive control: the same canonical term under a non-skipped key fires E541.

        This confirms the fixture is discriminating: if ``review_requirements``
        were removed from ``_E541_SKIP_KEYS``, the suppression test above would
        also fire E541 and fail.  This sibling test uses an identical value under
        ``description`` (not in _E541_SKIP_KEYS) to prove the term IS detectable
        and no other suppression mechanism silences it.
        """
        obj = {
            "description": "Ghost admin login flow passes end-to-end",
            # Same text as above but under a non-skipped key → must fire E541
        }
        errs = _check_free_text_terms("ms_plan.json", obj, self._TERMS)
        e541 = [e for e in errs if e.code == "E541"]
        assert e541, (
            "The same 'ghost' mention under a non-skipped key ('description') must fire "
            "E541 — this proves the review_requirements suppression test is not vacuous "
            "and that the term is genuinely detectable."
        )
