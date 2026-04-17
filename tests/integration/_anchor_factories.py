"""Factories for Step 16 Trinity Anchor and milestone-context test artifacts.

Centralised here so anchor + milestone helpers don't fork across multiple test
classes (and across schema rev cycles).  Used by ``test_step_16_anchor.py``
and any future suite that needs a real on-disk anchor + milestone tree.

These are *not* pytest fixtures — they're plain functions because the existing
anchor tests are ``unittest.TestCase``-based and cannot inject pytest fixtures.
The functions take an explicit ``Path`` for the temp directory so callers stay
in control of cleanup (typically via ``tempfile.TemporaryDirectory()``).

Schema invariants enforced by the factories:
  - Anchor uses ``$schema: vc:16-anchor`` and ``artifact_role: "anchor"``.
  - Milestone-plan files use ``$schema: vc:16-impl-context``.
  - ``milestone_index[].status`` uses the shared ``atoms#milestoneStatus`` enum
    (``pending`` | ``in_progress`` | ``done`` | ``deferred``) — never the old
    ``active`` / ``planned`` strings.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def make_anchor(
    tmp_dir: Path,
    *,
    scope_in: Optional[list[str]] = None,
    scope_out: Optional[list[str]] = None,
    milestone_index: Optional[list[dict[str, Any]]] = None,
    drift_checks: Optional[list[str]] = None,
    ambiguities: Optional[list[dict[str, Any]]] = None,
    functional_summary: str = "Test anchor for the Trinity Anchor validator.",
) -> Path:
    """Write a ``vc:16-anchor`` artifact to ``tmp_dir/16_impl_context.json`` and return its path.

    All anchor sub-fields default to schema-valid empty values so a single
    keyword override is enough to drive a single behaviour under test.
    """
    anchor: dict[str, Any] = {
        "$schema": "vc:16-anchor",
        "id": "anchor-test",
        "owner": "api",
        "created_at": "2024-01-01T00:00:00Z",
        "artifact_role": "anchor",
        "canonical_refs_used": [],
        "plan": {
            "summary": {
                "functional_summary": functional_summary,
                "scope_in": scope_in if scope_in is not None else ["test-scope-default"],
                "scope_out": scope_out or [],
            },
            "ambiguities": ambiguities or [],
            "drift": {"checks": drift_checks or []},
            "milestone_index": milestone_index or [],
        },
    }
    path = tmp_dir / "16_impl_context.json"
    path.write_text(json.dumps(anchor), encoding="utf-8")
    return path


def make_milestone_entry(
    milestone_id: str,
    *,
    status: str = "in_progress",
    fr_refs: Optional[list[str]] = None,
    checklist_id_prefix: Optional[str] = None,
    summary: Optional[str] = None,
    context_path: Optional[str] = None,
) -> dict[str, Any]:
    """Build one ``plan.milestone_index[]`` entry that satisfies the anchor schema.

    ``checklist_id_prefix`` defaults to a derivative of ``milestone_id`` capped
    at 20 chars and SCREAMING_SNAKE-cased so collision tests can override it
    explicitly while no-collision tests get a unique value automatically.
    """
    derived_prefix = (
        milestone_id.upper().replace("-", "_")[:20]
        if checklist_id_prefix is None
        else checklist_id_prefix
    )
    return {
        "milestone_id": milestone_id,
        "context_path": context_path
        or f"spec/impl_context/{milestone_id.replace('-', '_')}_plan.json",
        "status": status,
        "fr_refs": fr_refs or ["fr-login"],
        "checklist_id_prefix": derived_prefix,
        "summary": summary or f"{milestone_id} summary line for tests.",
    }


def make_milestone_plan(
    impl_context_dir: Path,
    filename: str,
    *,
    scope_in: Optional[list[str]] = None,
    scope_out: Optional[list[str]] = None,
    checklist: Optional[list[dict[str, Any]]] = None,
) -> Path:
    """Write a milestone-plan artifact for anchor drift-check tests.

    Produces the minimal shape the anchor validator reads during E308 scope
    drift and E309 checklist drift checks: ``$schema``, ``plan.summary``
    (scope_in/scope_out), and ``plan.spec_alignment.checklist``.  This is
    **not** a fully schema-valid ``vc:16-impl-context`` artifact — optional
    fields like ``milestone_ref`` and ``implementation`` are omitted because
    the anchor validator never schema-validates the milestone files it loads.
    """
    ms: dict[str, Any] = {
        "$schema": "vc:16-impl-context",
        "id": "ms-test",
        "owner": "api",
        "created_at": "2024-01-01T00:00:00Z",
        "plan": {
            "status": "active",
            "summary": {
                "functional_summary": f"Test milestone authored by {filename}.",
                "scope_in": scope_in or ["auth"],
                "scope_out": scope_out or [],
                "target_file_patterns": ["src/**/*.py"],
            },
            "spec_alignment": {
                "requirements_summary": [{"theme": "Core", "summary": "Test."}],
                "checklist": checklist or [],
            },
            "docs_impact": {
                "status": "not_required",
                "rationale": "No doc changes needed.",
                "docs_touched": [],
            },
            "review_requirements": {"test_commands": ["pytest tests/"]},
        },
        "canonical_refs_used": [],
        "canonical_proposals": [],
        "canonical_conflicts": [],
    }
    path = impl_context_dir / filename
    path.write_text(json.dumps(ms), encoding="utf-8")
    return path


def make_checklist_item(
    item_id: str,
    spec_ref_id: str,
    *,
    item_type: str = "behavior",
) -> dict[str, Any]:
    """Build one ``plan.spec_alignment.checklist[]`` item for a milestone plan.

    Produces a structurally sufficient item for the anchor validator's
    cross-file drift checks (E309, W610).  The anchor validator reads
    ``id`` and ``spec_ref.id`` — it does not schema-validate the milestone
    plan itself.  Optional fields (``nfr_refs``, ``implementation``) are
    omitted rather than populated with schema-invalid defaults.
    """
    return {
        "id": item_id,
        "spec_ref": {
            "type": "fr",
            "id": spec_ref_id,
            "line_range": "L1-L10",
            "commit_hash": "a1b2c3d4e5f61234567890123456789012345678",
        },
        "description": f"Checklist item {item_id}.",
        "type": item_type,
        "layer": "api",
        "linked_test_expectation": "pytest test_auth",
        "fixture_ref": "fixture-auth",
    }
