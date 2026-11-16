"""Step 16 Trinity Anchor validator.

Validates the anchor artifact (spec/16_impl_context.json) — the scope declaration
that spans all milestones.  The anchor's unique job is cross-milestone drift detection:

  E308 (ANCHOR_SCOPE_DRIFT): fires when a milestone's scope_in contradicts the
      anchor's scope_out (or vice versa).  The FR/API ownership arm reads the
      removed ``fr_refs`` and does nothing on the 1.2.0 row shape.

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
from ...core.scope_helpers import as_dict, as_list
from ...lifecycle.plans import MILESTONE_KEY, PLAN_DIR_NAME, find_plan
from .step_16 import _is_anchor

_PLAN_SCHEMA = "vc:16-impl-context"


def _row_milestone(row: dict[str, Any]) -> str:
    """The milestone a ``milestone_index`` row is about: its ``about`` item, else the row id, else the old ``milestone_id``."""
    about = as_list(row.get("about"))
    for candidate in (about[0] if about else None, row.get("anchor_id"), row.get("milestone_id")):
        if isinstance(candidate, str) and candidate:
            return candidate
    return ""


def validate_step_16_anchor(
    data: dict[str, Any],
    toolkit_root: str,  # noqa: ARG001 — kept for DEEP_VALIDATORS API symmetry
    spec_path: Optional[str] = None,
) -> list[SpecError]:
    """Deep validation for the Step 16 Trinity Anchor artifact.

    Args:
        data:         Parsed JSON content of the anchor artifact.
        toolkit_root: Toolkit root directory (unused directly, kept for API symmetry).
        spec_path:    Absolute path to the artifact file.  Required for drift checks;
                      without it only in-memory checks run (E308 ownership, E309 prefix).

    Returns:
        List of SpecError objects.  Empty list when valid.  Never raises on a wrong-typed value.
    """
    # Guard: if this is somehow called on a non-anchor artifact, return early.
    # Schema validation already enforces artifact_role == "anchor", so reaching
    # this path with a non-anchor usually means a routing bug — surface a warning.
    if not _is_anchor(spec_path, data):
        return [
            make_error(
                "W586",
                "ANCHOR_VALIDATOR_WRONG_ARTIFACT: validate_step_16_anchor called on "
                "an artifact that is neither field-marked (artifact_role == 'anchor') "
                "nor path-marked (spec/16_impl_context.json outside impl_context/). "
                "Both signals failed — this indicates a routing bug in validate.py "
                "dispatch or a mis-authored artifact that should not have reached here.",
            )
        ]

    errors = _legacy_schema_errors(data)
    plan = as_dict(data.get("plan"))
    rows = [row for row in as_list(plan.get("milestone_index")) if isinstance(row, dict)]
    errors.extend(_drift_staleness_errors(plan, rows))
    errors.extend(_row_errors(rows))

    # Everything below requires spec_path for path resolution and file I/O.
    if spec_path is None:
        errors.append(
            make_error(
                "W585",
                "ANCHOR_DRIFT_SKIP: spec_path is None — filesystem drift checks "
                "skipped (E308-scope/E309-mapping/W610).  "
                "Pass spec_path to validate_step_16_anchor to enable them.",
            )
        )
        return errors

    anchor_path = Path(spec_path)
    if anchor_path.parent.name == PLAN_DIR_NAME:
        errors.append(_misfiled_error(anchor_path))
        return errors
    errors.extend(_cross_file_errors(anchor_path, plan, rows))
    return errors


def _legacy_schema_errors(data: dict[str, Any]) -> list[SpecError]:
    """W608 when the anchor file still declares the pre-split milestone-plan schema.

    The Trinity Anchor split (0.6.0) moved per-milestone checklist content out of ``spec/16_impl_context.json``
    into ``spec/impl_context/*.json``.  Host repos that pre-date the split declare ``$schema: vc:16-impl-context``
    on their anchor file; that schema is still registered (for plan files), so schema validation passes while
    the anchor-only checks have nothing to read.  The warning is the forcing function to migrate.
    """
    if data.get("$schema") != _PLAN_SCHEMA:
        return []
    return [
        make_error(
            "W608",
            "ANCHOR_LEGACY_SCHEMA: artifact at the anchor path declares "
            "$schema='vc:16-impl-context' (the pre-split milestone-plan "
            "schema). The Trinity Anchor is now a distinct contract "
            "(vc:16-anchor). Migrate: (1) move per-milestone checklist "
            "content to spec/impl_context/<milestone>_plan.json; "
            "(2) rewrite this file against vc:16-anchor with plan.summary, "
            "plan.ambiguities, plan.drift, plan.milestone_index; "
            "(3) set artifact_role='anchor'. "
            "See prompts/prompt_16_impl_context.md for the target schema.",
        )
    ]


def _drift_staleness_errors(plan: dict[str, Any], rows: list[dict[str, Any]]) -> list[SpecError]:
    """W587 when milestones are registered but ``plan.drift.checks`` records no drift check."""
    checks = as_list(as_dict(plan.get("drift")).get("checks"))
    if not rows or checks:
        return []
    return [
        make_error(
            "W587",
            f"ANCHOR_DRIFT_CHECKS_STALE: milestone_index has "
            f"{len(rows)} entries but plan.drift.checks is empty — "
            f"record at least one drift check per Trinity cycle.",
        )
    ]


def _row_errors(rows: list[dict[str, Any]]) -> list[SpecError]:
    """In-memory checks over ``milestone_index``: E308 ownership (old shape only) and E309 prefix collision.

    Done milestones are exempt from FR/API ownership conflict (delivered IDs may be referenced again in follow-on
    work) but still take part in the prefix-collision check (a done milestone's namespace is still allocated).
    """
    errors: list[SpecError] = []
    owner_of: dict[str, str] = {}  # FR/API ID -> first non-done milestone that claims it
    prefix_owner: dict[str, str] = {}  # checklist_id_prefix -> first milestone that uses it
    for row in rows:
        milestone = _row_milestone(row)
        if row.get("status") != "done":
            errors.extend(_ownership_errors(row, milestone, owner_of))
        prefix = row.get("checklist_id_prefix")
        if not isinstance(prefix, str) or not prefix:
            continue
        if prefix in prefix_owner:
            errors.append(
                make_error(
                    "E309",
                    f"ANCHOR_CHECKLIST_DRIFT [prefix]: checklist_id_prefix '{prefix}' is shared by "
                    f"milestone_index entries '{prefix_owner[prefix]}' and '{milestone}' — two milestones "
                    f"cannot allocate checklist IDs from the same namespace.",
                )
            )
        else:
            prefix_owner[prefix] = milestone
    return errors


def _ownership_errors(row: dict[str, Any], milestone: str, owner_of: dict[str, str]) -> list[SpecError]:
    """E308 [ownership] for FR/API ids claimed by two non-done rows.

    Reads the removed ``fr_refs``: a no-op on the 1.2.0 row shape, which has none.
    """
    errors: list[SpecError] = []
    for ref_id in as_list(row.get("fr_refs")):  # M8 rewrites: re-keyed onto the computed 14 fr_refs
        if not isinstance(ref_id, str):
            continue
        if ref_id not in owner_of:
            owner_of[ref_id] = milestone
            continue
        kind = "API" if ref_id.startswith("api-") else "FR"
        errors.append(
            make_error(
                "E308",
                f"ANCHOR_SCOPE_DRIFT [ownership]: {kind} ownership conflict — '{ref_id}' is "
                f"claimed by both non-done milestone '{owner_of[ref_id]}' and '{milestone}'.  "
                f"Only one non-done milestone may own a given {kind} at a time.",
            )
        )
    return errors


def _misfiled_error(anchor_path: Path) -> SpecError:
    """W609: the anchor sits inside ``impl_context/``, where per-milestone plans live."""
    return make_error(
        "W609",
        f"ANCHOR_MISFILED: '{anchor_path.name}' has artifact_role='anchor' "
        f"but lives inside '{anchor_path.parent}'.  The Trinity Anchor must "
        f"sit at spec/16_impl_context.json (one level up); files inside "
        f"spec/impl_context/ are per-milestone plans (vc:16-impl-context).  "
        f"Move this file to '{anchor_path.parent.parent}/16_impl_context.json' "
        f"so cross-milestone drift checks can resolve the impl_context/ "
        f"sibling directory correctly.",
    )


def _cross_file_errors(anchor_path: Path, plan: dict[str, Any], rows: list[dict[str, Any]]) -> list[SpecError]:
    """Checks that read the plan files: W588/W589/W608/W611 (scan), E308 scope, E309 mapping and W610 prefix."""
    spec_root = anchor_path.parent
    impl_context_dir = spec_root / PLAN_DIR_NAME
    if not impl_context_dir.exists():
        return []  # No milestone plans yet — a valid state for a fresh anchor.
    row_milestones = {_row_milestone(row) for row in rows}
    contexts, errors = _scan_plan_files(impl_context_dir, row_milestones)
    summary = as_dict(plan.get("summary"))
    errors.extend(_scope_drift_errors(as_list(summary.get("scope_in")), as_list(summary.get("scope_out")), contexts))
    errors.extend(_mapping_drift_errors(contexts))
    errors.extend(_prefix_errors(spec_root, rows, contexts))
    return errors


def _scan_plan_files(
    impl_context_dir: Path, row_milestones: set[str]
) -> tuple[dict[str, dict[str, Any]], list[SpecError]]:
    """Classify every ``impl_context/*.json`` file; return the plans that take part in drift checks and the notices.

    A file takes part when it parses to an object declaring ``vc:16-impl-context`` and its file-level ``milestone``
    names a milestone some anchor row is about.  Anything else is skipped with a notice and never raises:
    W588 unreadable, W589 wrong ``$schema``, W608 no ``milestone`` key (a pre-1.2.0 plan), W611 a ``milestone`` that
    no anchor row is about, or no usable plan at all.
    """
    contexts: dict[str, dict[str, Any]] = {}
    errors: list[SpecError] = []
    orphans: list[str] = []
    files = sorted(impl_context_dir.glob("*.json"))
    for ms_file in files:
        try:
            ms_data = json.loads(ms_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
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
        notice = _plan_notice(ms_file, ms_data)
        if notice is not None:
            errors.append(notice)
        elif ms_data[MILESTONE_KEY] not in row_milestones:
            orphans.append(ms_file.name)
        else:
            contexts[str(ms_file)] = ms_data
    if orphans or (files and not contexts):
        errors.append(_suppressed_error(len(files), len(contexts), orphans))
    return contexts, errors


def _plan_notice(ms_file: Path, ms_data: dict[str, Any]) -> Optional[SpecError]:
    """W589 for a file that is not a milestone plan, W608 for a plan with no ``milestone`` key; else ``None``."""
    declared = ms_data.get("$schema")
    if declared != _PLAN_SCHEMA:
        # A file that parses but is not declared as a milestone plan: silently skipping it would hide a missing
        # or wrong `$schema` and drop the file from every drift check.
        return make_error(
            "W589",
            f"ANCHOR_MILESTONE_MISSCHEMAED: '{ms_file.name}' in "
            f"impl_context/ has $schema={declared!r} — expected "
            f"'{_PLAN_SCHEMA}'. Drift checks skipped this file.",
        )
    if not isinstance(ms_data.get(MILESTONE_KEY), str):
        return make_error(
            "W608",
            f"ANCHOR_LEGACY_SCHEMA: plan file '{ms_file.name}' in impl_context/ has no file-level "
            f"'{MILESTONE_KEY}' key (the pre-1.2.0 plan shape). Drift detection skipped this file until "
            f"it names its milestone.",
        )
    return None


def _suppressed_error(files_seen: int, usable: int, orphans: list[str]) -> SpecError:
    """W611: some plan files, or all of them, take no part in E308/E309 drift detection."""
    reason = ""
    if orphans:
        reason = f" Plan file(s) {', '.join(repr(n) for n in orphans)} name a milestone that no anchor row is about."
    return make_error(
        "W611",
        f"ANCHOR_DRIFT_SUPPRESSED: impl_context/ contains {files_seen} JSON file(s); "
        f"{usable} take part in E308/E309 drift detection.{reason}  Fix the W588/W589/W608 warnings "
        f"above, or add the anchor row, to restore drift checks.",
    )


def _scope_drift_errors(
    anchor_scope_in: list[Any], anchor_scope_out: list[Any], contexts: dict[str, dict[str, Any]]
) -> list[SpecError]:
    """E308 [scope]: a plan's ``scope_in`` must not overlap the anchor's ``scope_out``, and the reverse.

    Items compare lowercased and stripped: the schema's ``uniqueItems`` is case-sensitive, but ``"Auth"`` and
    ``"auth"`` name the same scope category for drift detection.
    """
    errors: list[SpecError] = []
    in_set = {s.strip().lower() for s in anchor_scope_in if isinstance(s, str)}
    out_set = {s.strip().lower() for s in anchor_scope_out if isinstance(s, str)}
    for ms_file, ms_data in contexts.items():
        ms_summary = as_dict(as_dict(ms_data.get("plan")).get("summary"))
        ms_name = Path(ms_file).name
        for field, anchor_set, anchor_field in (("scope_in", out_set, "scope_out"), ("scope_out", in_set, "scope_in")):
            for item in as_list(ms_summary.get(field)):
                if isinstance(item, str) and item.strip().lower() in anchor_set:
                    errors.append(
                        make_error(
                            "E308",
                            f"ANCHOR_SCOPE_DRIFT [scope]: milestone '{ms_name}' has {field} item "
                            f"'{item}' that appears in anchor {anchor_field} — scope contradiction",
                        )
                    )
    return errors


def _checklist(ms_data: dict[str, Any]) -> list[Any]:
    """The ``plan.spec_alignment.checklist`` list of a plan file."""
    return as_list(as_dict(as_dict(ms_data.get("plan")).get("spec_alignment")).get("checklist"))


def _mapping_drift_errors(contexts: dict[str, dict[str, Any]]) -> list[SpecError]:
    """E309 [mapping]: one checklist id must not map to different ``spec_ref.id`` values across plan files.

    Reads the old object-shaped ``spec_ref``: a no-op on a 1.2.0 plan, whose ``spec_ref`` is a bare task id.
    """
    errors: list[SpecError] = []
    registry: dict[str, tuple[str, str]] = {}  # checklist id -> (spec_ref id, plan file)
    for ms_file, ms_data in contexts.items():
        ms_name = Path(ms_file).name
        for item in _checklist(ms_data):
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            spec_ref = item.get("spec_ref")  # M8 rewrites: re-keyed onto differing `realises` sets
            spec_ref_id = spec_ref.get("id") if isinstance(spec_ref, dict) else None
            if not item_id or not spec_ref_id:
                continue
            if item_id not in registry:
                registry[item_id] = (spec_ref_id, ms_file)
            elif registry[item_id][0] != spec_ref_id:
                prev_ref, prev_file = registry[item_id]
                errors.append(
                    make_error(
                        "E309",
                        f"ANCHOR_CHECKLIST_DRIFT [mapping]: checklist id '{item_id}' maps to "
                        f"'{spec_ref_id}' in '{ms_name}' but '{prev_ref}' in "
                        f"'{Path(prev_file).name}' — same ID, different spec_ref",
                    )
                )
    return errors


def _prefix_errors(
    spec_root: Path, rows: list[dict[str, Any]], contexts: dict[str, dict[str, Any]]
) -> list[SpecError]:
    """W610: every checklist id of a plan must start with the ``checklist_id_prefix`` of its anchor row.

    The plan of a row is found through ``plans.find_plan``.  16a planners are told to name checklist ids with the
    prefix; the schema cannot enforce this cross-artifact contract, so it is verified here.
    """
    errors: list[SpecError] = []
    for row in rows:
        prefix = row.get("checklist_id_prefix")
        plan_path = find_plan(spec_root, _row_milestone(row))
        if plan_path is None or not isinstance(prefix, str) or not prefix:
            continue
        ms_data = contexts.get(str(plan_path))
        if ms_data is None:
            continue
        for item in _checklist(ms_data):
            item_id = item.get("id") if isinstance(item, dict) else None
            if isinstance(item_id, str) and not item_id.startswith(prefix + "_"):
                errors.append(
                    make_error(
                        "W610",
                        f"ANCHOR_PREFIX_VIOLATION: checklist id '{item_id}' in "
                        f"'{plan_path.name}' does not start with the declared "
                        f"checklist_id_prefix '{prefix}_' from "
                        f"milestone_index.  Namespace violations undermine "
                        f"E309 collision prevention.",
                    )
                )
    return errors
