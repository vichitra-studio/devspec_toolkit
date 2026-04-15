"""Step 16 Trinity Anchor validator.

Validates the anchor artifact (spec/16_impl_context.json) — the scope declaration
that spans all milestones.  The anchor's unique job is cross-milestone drift detection:

  E308 (ANCHOR_SCOPE_DRIFT): fires when a milestone's scope_in contradicts the
      anchor's scope_out (or vice versa), or when the same FR/API is active in
      two milestones simultaneously.

  E309 (ANCHOR_CHECKLIST_DRIFT): fires when the same checklist ID maps to different
      spec_ref.id values across any two milestone context files.

The anchor validator does NOT call validate_step_16() — the anchor has its own
contract (vc:16-anchor schema), and the checks here are cross-artifact comparisons
that schema validation cannot express.

Schema validation (required fields, forbidden sections) is handled by the
vc:16-anchor JSON Schema.  This module adds only logic that requires reading
multiple files from the filesystem.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from ...core.errors import make_error, SpecError
from .step_16 import _is_anchor


def validate_step_16_anchor(
    data: dict[str, Any],
    _toolkit_root: str,
    spec_path: Optional[str] = None,
) -> list[SpecError]:
    """Deep validation for the Step 16 Trinity Anchor artifact.

    Args:
        data:         Parsed JSON content of the anchor artifact.
        toolkit_root: Toolkit root directory (unused directly, kept for API symmetry).
        spec_path:    Absolute path to the artifact file.  Required for drift checks;
                      without it only the _is_anchor guard can run.

    Returns:
        List of SpecError objects.  Empty list when valid.
    """
    errors: list[SpecError] = []

    # Guard: if this is somehow called on a non-anchor artifact, return early.
    # Schema validation already enforces artifact_role == "anchor", so reaching
    # this path with a non-anchor usually means a routing bug — surface a warning.
    if not _is_anchor(spec_path, data):
        errors.append(
            make_error(
                "W586",
                "ANCHOR_VALIDATOR_WRONG_ARTIFACT: validate_step_16_anchor called on "
                "a non-anchor artifact (artifact_role != 'anchor' and path heuristic "
                "does not match 16_impl_context.json outside impl_context/).  "
                "Check validate.py dispatch routing.",
            )
        )
        return errors

    if spec_path is None:
        # Cannot perform filesystem-dependent drift checks without a path.
        errors.append(
            make_error(
                "W585",
                "ANCHOR_DRIFT_SKIP: spec_path is None — cross-milestone drift checks "
                "skipped.  Pass spec_path to validate_step_16_anchor to enable E308/E309.",
            )
        )
        return errors

    anchor_path = Path(spec_path)

    anchor_plan = data.get("plan", {}) if isinstance(data.get("plan"), dict) else {}
    anchor_summary = anchor_plan.get("summary", {}) if isinstance(anchor_plan.get("summary"), dict) else {}
    anchor_scope_in: list[str] = anchor_summary.get("scope_in", []) or []
    anchor_scope_out: list[str] = anchor_summary.get("scope_out", []) or []

    # ── W587: drift-checks staleness ───────────────────────────────────────────
    # An anchor that registers one or more milestones but records zero drift checks
    # is paying its maintenance cost without doing its job.  Fires regardless of
    # whether impl_context/ exists — the signal is "you have milestones to watch
    # but no evidence you have watched them".
    milestone_index: list[dict[str, Any]] = anchor_plan.get("milestone_index", []) or []
    drift_block = anchor_plan.get("drift", {}) if isinstance(anchor_plan.get("drift"), dict) else {}
    drift_checks = drift_block.get("checks", []) if isinstance(drift_block.get("checks"), list) else []
    if milestone_index and not drift_checks:
        errors.append(
            make_error(
                "W587",
                f"ANCHOR_DRIFT_CHECKS_STALE: milestone_index has "
                f"{len(milestone_index)} entries but plan.drift.checks is empty — "
                f"record at least one drift check per Trinity cycle.",
            )
        )

    # ── E308: FR ownership conflict ────────────────────────────────────────────
    # Uses only anchor data — runs even when impl_context/ is absent or empty.
    # The same FR/API ID must not be active in two milestones simultaneously.
    # Done milestones do not conflict — a FR may be revisited after delivery.
    fr_to_active_milestone: dict[str, str] = {}
    for entry in milestone_index:
        if not isinstance(entry, dict):
            continue
        ms_id = entry.get("milestone_id", "")
        status = entry.get("status", "")
        if status == "done":
            continue  # Done milestones do not block
        fr_refs: list[str] = entry.get("fr_refs", []) or []
        for fr_id in fr_refs:
            if not isinstance(fr_id, str):
                continue
            if fr_id in fr_to_active_milestone:
                prev_ms = fr_to_active_milestone[fr_id]
                errors.append(
                    make_error(
                        "E308",
                        f"ANCHOR_SCOPE_DRIFT: FR ownership conflict — '{fr_id}' is "
                        f"claimed by both active milestone '{prev_ms}' and '{ms_id}'.  "
                        f"Only one active milestone may own a given FR at a time.",
                    )
                )
            else:
                fr_to_active_milestone[fr_id] = ms_id

    # ── Filesystem-dependent checks (E308 scope drift, E309 checklist drift) ──
    # These require loading milestone context files from impl_context/.
    impl_context_dir = anchor_path.parent / "impl_context"
    if not impl_context_dir.exists():
        # No milestone contexts yet — valid state for a fresh anchor.
        return errors

    milestone_contexts: dict[str, dict[str, Any]] = {}
    for ms_file in sorted(impl_context_dir.glob("*.json")):
        try:
            ms_data = json.loads(ms_file.read_text(encoding="utf-8"))
            if isinstance(ms_data, dict):
                milestone_contexts[str(ms_file)] = ms_data
        except (OSError, json.JSONDecodeError):
            continue  # Unreadable milestone files are reported by their own validators.

    if not milestone_contexts:
        return errors

    # ── E308: ANCHOR_SCOPE_DRIFT (bidirectional scope check) ──────────────────
    # milestone scope_in must not overlap anchor scope_out, and vice versa.
    anchor_scope_in_set = {s.strip().lower() for s in anchor_scope_in if isinstance(s, str)}
    anchor_scope_out_set = {s.strip().lower() for s in anchor_scope_out if isinstance(s, str)}

    for ms_file, ms_data in milestone_contexts.items():
        ms_plan = ms_data.get("plan", {}) if isinstance(ms_data.get("plan"), dict) else {}
        ms_summary = ms_plan.get("summary", {}) if isinstance(ms_plan.get("summary"), dict) else {}
        ms_scope_in: list[str] = ms_summary.get("scope_in", []) or []
        ms_scope_out: list[str] = ms_summary.get("scope_out", []) or []
        ms_name = Path(ms_file).name

        for item in ms_scope_in:
            if isinstance(item, str) and item.strip().lower() in anchor_scope_out_set:
                errors.append(
                    make_error(
                        "E308",
                        f"ANCHOR_SCOPE_DRIFT: milestone '{ms_name}' has scope_in item "
                        f"'{item}' that appears in anchor scope_out — scope contradiction",
                    )
                )

        for item in ms_scope_out:
            if isinstance(item, str) and item.strip().lower() in anchor_scope_in_set:
                errors.append(
                    make_error(
                        "E308",
                        f"ANCHOR_SCOPE_DRIFT: milestone '{ms_name}' has scope_out item "
                        f"'{item}' that appears in anchor scope_in — scope contradiction",
                    )
                )

    # ── E309: ANCHOR_CHECKLIST_DRIFT ──────────────────────────────────────────
    # Cross-milestone checklist ID registry: the same checklist item ID must not
    # map to different spec_ref.id values across any two milestone context files.
    id_registry: dict[str, tuple[str, str]] = {}  # id → (spec_ref_id, source_file)
    for ms_file, ms_data in milestone_contexts.items():
        ms_plan = ms_data.get("plan", {}) if isinstance(ms_data.get("plan"), dict) else {}
        checklist: list[dict[str, Any]] = (
            ms_plan.get("spec_alignment", {}).get("checklist", [])
            if isinstance(ms_plan.get("spec_alignment"), dict)
            else []
        )
        ms_name = Path(ms_file).name
        for item in checklist:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            spec_ref = item.get("spec_ref")
            spec_ref_id = spec_ref.get("id") if isinstance(spec_ref, dict) else None
            if not item_id or not spec_ref_id:
                continue
            if item_id in id_registry:
                prev_ref, prev_file = id_registry[item_id]
                if prev_ref != spec_ref_id:
                    errors.append(
                        make_error(
                            "E309",
                            f"ANCHOR_CHECKLIST_DRIFT: checklist id '{item_id}' maps to "
                            f"'{spec_ref_id}' in '{ms_name}' but '{prev_ref}' in "
                            f"'{Path(prev_file).name}' — same ID, different spec_ref",
                        )
                    )
            else:
                id_registry[item_id] = (spec_ref_id, ms_file)

    return errors
