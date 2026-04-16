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
                "an artifact that is neither field-marked (artifact_role == 'anchor') "
                "nor path-marked (spec/16_impl_context.json outside impl_context/). "
                "Both signals failed — this indicates a routing bug in validate.py "
                "dispatch or a mis-authored artifact that should not have reached here.",
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

    # ── E308: FR/API ownership conflict ───────────────────────────────────────
    # Uses only anchor data — runs even when impl_context/ is absent or empty.
    # The same FR/API ID must not be in-flight in two milestones simultaneously.
    # Done milestones do not conflict — an ID may be revisited after delivery.
    id_to_milestone: dict[str, str] = {}
    for entry in milestone_index:
        if not isinstance(entry, dict):
            continue
        ms_id = entry.get("milestone_id", "")
        status = entry.get("status", "")
        if status == "done":
            continue  # Done milestones do not block (delivered, may be revisited)
        fr_refs: list[str] = entry.get("fr_refs", []) or []
        for ref_id in fr_refs:
            if not isinstance(ref_id, str):
                continue
            if ref_id in id_to_milestone:
                prev_ms = id_to_milestone[ref_id]
                kind = "API" if ref_id.startswith("api-") else "FR"
                errors.append(
                    make_error(
                        "E308",
                        f"ANCHOR_SCOPE_DRIFT: {kind} ownership conflict — '{ref_id}' is "
                        f"claimed by both in-flight milestone '{prev_ms}' and '{ms_id}'.  "
                        f"Only one non-done milestone may own a given {kind} at a time.",
                    )
                )
            else:
                id_to_milestone[ref_id] = ms_id

    # ── E309: checklist_id_prefix collision (anchor milestone_index) ──────────
    # Two milestone_index entries sharing the same checklist_id_prefix will
    # allocate checklist IDs from the same namespace in their 16a plans; this
    # is the authoring-time equivalent of the cross-milestone ID collision
    # E309 below catches at plan time.  Detecting it here stops the drift at
    # its root and is what prompt_16 promises.
    prefix_to_milestone: dict[str, str] = {}
    for entry in milestone_index:
        if not isinstance(entry, dict):
            continue
        prefix = entry.get("checklist_id_prefix")
        ms_id = entry.get("milestone_id", "")
        if not isinstance(prefix, str) or not prefix:
            continue
        if prefix in prefix_to_milestone:
            prev_ms = prefix_to_milestone[prefix]
            errors.append(
                make_error(
                    "E309",
                    f"ANCHOR_CHECKLIST_DRIFT: checklist_id_prefix '{prefix}' is shared by "
                    f"milestone_index entries '{prev_ms}' and '{ms_id}' — two milestones "
                    f"cannot allocate checklist IDs from the same namespace.",
                )
            )
        else:
            prefix_to_milestone[prefix] = ms_id

    # ── Filesystem-dependent checks (E308 scope drift, E309 checklist drift) ──
    # These require loading milestone context files from impl_context/.
    impl_context_dir = anchor_path.parent / "impl_context"
    if not impl_context_dir.exists():
        # No milestone contexts yet — valid state for a fresh anchor.
        return errors

    # Only milestone-plan artifacts declaring $schema == "vc:16-impl-context" count
    # for drift detection.  Stray files in impl_context/ (temp drafts, backups,
    # non-JSON-object roots) are silently skipped — they have their own validators
    # or should not be there.  Filtering by $schema prevents a misfiled document
    # from polluting the E308/E309 registries.
    #
    # A file that *should* be a milestone plan but cannot be read or parsed is a
    # different case: silently dropping it would hide the file from E308/E309
    # entirely, so emit W588 and continue.  In ``validate_dir`` that same file
    # will also be picked up by its own dispatcher (with a richer error); in
    # ``validate_file`` on the anchor alone, W588 is the only diagnostic the
    # author sees.
    milestone_contexts: dict[str, dict[str, Any]] = {}
    for ms_file in sorted(impl_context_dir.glob("*.json")):
        try:
            ms_data = json.loads(ms_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(
                make_error(
                    "W588",
                    f"ANCHOR_MILESTONE_UNREADABLE: '{ms_file.name}' in impl_context/ "
                    f"could not be read or parsed ({type(exc).__name__}: {exc}); "
                    f"drift detection skipped this file.",
                )
            )
            continue
        if not isinstance(ms_data, dict):
            continue
        if ms_data.get("$schema") != "vc:16-impl-context":
            continue
        milestone_contexts[str(ms_file)] = ms_data

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
