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
  - Milestone-plan files use ``$schema: vc:16-impl-context`` and name their milestone in the file-level
    ``milestone`` key.
  - ``milestone_index[]`` rows are anchor rows (``anchor_id``, ``about``, ``status``, ``checklist_id_prefix``,
    ``summary``); ``status`` uses the shared ``atoms#milestoneStatus`` enum
    (``pending`` | ``in_progress`` | ``done`` | ``deferred``) — never the old
    ``active`` / ``planned`` strings.  A ``deferred`` row carries ``deferral_reason`` and a ``done`` row ``close``.
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
    checklist_id_prefix: Optional[str] = None,
    summary: Optional[str] = None,
) -> dict[str, Any]:
    """Build one ``plan.milestone_index[]`` anchor row that satisfies the anchor schema.

    ``checklist_id_prefix`` defaults to a derivative of ``milestone_id`` capped
    at 20 chars and SCREAMING_SNAKE-cased so collision tests can override it
    explicitly while no-collision tests get a unique value automatically.  A
    ``deferred`` row gets a ``deferral_reason`` and a ``done`` row a ``close``,
    which the schema requires for those statuses.
    """
    derived_prefix = (
        milestone_id.upper().replace("-", "_")[:20]
        if checklist_id_prefix is None
        else checklist_id_prefix
    )
    row: dict[str, Any] = {
        "anchor_id": f"anchor-{milestone_id}",
        "about": [milestone_id],
        "status": status,
        "checklist_id_prefix": derived_prefix,
        "summary": summary or f"{milestone_id} summary line for tests.",
    }
    if status == "deferred":
        row["deferral_reason"] = "Waits for an upstream decision."
    if status == "done":
        row["close"] = {"signed_off_by": "test-reviewer"}
    return row


def make_legacy_milestone_entry(
    milestone_id: str,
    *,
    status: str = "in_progress",
    fr_refs: Optional[list[str]] = None,
    checklist_id_prefix: str = "LEGACY",
) -> dict[str, Any]:
    """Build one pre-1.2.0 ``milestone_index[]`` entry (``milestone_id``, ``context_path``, ``fr_refs``).

    It no longer satisfies the anchor schema; it exists to drive the E308 ownership arm, which still reads
    ``fr_refs`` until the milestone commands rewrite it.
    """
    return {
        "milestone_id": milestone_id,
        "context_path": f"spec/impl_context/{milestone_id.replace('-', '_')}_plan.json",
        "status": status,
        "fr_refs": fr_refs or ["fr-login"],
        "checklist_id_prefix": checklist_id_prefix,
        "summary": f"{milestone_id} summary line for tests.",
    }


def make_milestone_plan(
    impl_context_dir: Path,
    filename: str,
    *,
    scope_in: Optional[list[str]] = None,
    scope_out: Optional[list[str]] = None,
    checklist: Optional[list[dict[str, Any]]] = None,
    milestone: Optional[str] = None,
) -> Path:
    """Write a milestone-plan artifact for anchor drift-check tests.

    ``milestone`` sets the file-level ``milestone`` key; without it the file is a pre-1.2.0 plan.

    Produces the minimal shape the anchor validator reads during E308 scope
    drift and E309 checklist drift checks: ``$schema``, ``plan.summary``
    (scope_in/scope_out), and ``plan.spec_alignment.checklist``.  This is
    **not** a fully schema-valid ``vc:16-impl-context`` artifact — the plan
    items a caller passes in (see ``make_checklist_item``) may omit
    ``realises`` and ``implementation`` because the anchor validator never
    schema-validates the milestone files it loads.
    """
    ms: dict[str, Any] = {
        "$schema": "vc:16-impl-context",
        "id": "ms-test",
        "owner": "api",
        "created_at": "2024-01-01T00:00:00Z",
        "plan": {
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
    if milestone is not None:
        ms["milestone"] = milestone
    path = impl_context_dir / filename
    path.write_text(json.dumps(ms), encoding="utf-8")
    return path


def make_object_test_command(
    command: str,
    *,
    command_ref: Optional[dict[str, Any]] = None,
    description: Optional[str] = None,
) -> dict[str, Any]:
    """Build an object-form ``review_requirements.test_commands[]`` entry.

    Schema (``schema/16_impl_context.schema.json``) permits each entry to be
    either a plain string or an object with ``command`` (string) plus optional
    ``command_ref`` (canonicalRef object, e.g. ``{"id": "cn:project:command:jq"}``)
    and ``description`` fields. The validator only consumes ``command``;
    ``command_ref`` resolution is out of scope for step_16.
    """
    entry: dict[str, Any] = {"command": command}
    if command_ref is not None:
        entry["command_ref"] = command_ref
    if description is not None:
        entry["description"] = description
    return entry


def make_checklist_item(
    item_id: str,
    spec_ref_id: str,
    *,
    item_type: str = "behavior",
) -> dict[str, Any]:
    """Build one 1.1.1-shaped ``plan.spec_alignment.checklist[]`` item for a milestone plan.

    Produces a structurally sufficient item for the anchor validator's
    cross-file drift checks (E309, W610).  The anchor validator reads
    ``id`` and ``spec_ref.id`` (its ``spec_ref`` arm is the legacy one, # M8 rewrites)
    — it does not schema-validate the milestone plan itself, so the item
    stays in the old shape on purpose.
    """
    return {
        "id": item_id,
        "spec_ref": {"type": "fr", "id": spec_ref_id},
        "description": f"Checklist item {item_id}.",
        "type": item_type,
        "layer": "api",
    }
