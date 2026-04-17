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

    # ── W608: legacy schema at the anchor path ────────────────────────────────
    # The Trinity Anchor split (0.6.0) moved per-milestone checklist content
    # out of ``spec/16_impl_context.json`` and into ``spec/impl_context/*.json``.
    # The anchor artifact itself now validates against ``vc:16-anchor``.
    #
    # Host repos that pre-date the split still declare ``$schema:
    # vc:16-impl-context`` on their anchor file. That schema is still registered
    # (for milestone-plan artifacts inside ``impl_context/``), so schema
    # validation passes. The routing layer dispatches to this validator based on
    # the anchor *path* regardless of the declared schema — which means the
    # legacy anchor silently bypasses E308/E309/W587 (all of which key off
    # ``milestone_index``, a field the legacy shape does not carry).
    #
    # Without an explicit signal, host repos have no forcing function to
    # migrate. W608 surfaces the mismatch at ``spec-check`` time, pointing at
    # the migration steps documented in ``prompt_16_impl_context.md`` and the
    # breaking-change changelog entry. The check is intentionally *after* the
    # W586 routing guard (a non-anchor artifact should surface the routing bug
    # first, not a schema-migration hint) and *before* the drift checks (which
    # are no-ops on legacy shapes anyway — emitting W608 first makes the
    # dominant cause of an otherwise-clean legacy anchor obvious).
    declared_schema = data.get("$schema") if isinstance(data, dict) else None
    if declared_schema == "vc:16-impl-context":
        errors.append(
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
                "See prompts/prompt_16_impl_context.md and "
                "changelog/unreleased.md (breaking_schema_swap entry).",
            )
        )

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

    # ── W609: misfiled anchor ──────────────────────────────────────────────────
    # An artifact_role="anchor" file living inside spec/impl_context/ is routed
    # back to "16" by validate.py:_refine_impl_context_substep so this validator
    # runs.  But every downstream drift check resolves
    # ``impl_context_dir = anchor_path.parent / "impl_context"`` to
    # spec/impl_context/impl_context/ — which does not exist — so E308/E309/W588/
    # W589/W607 all silently no-op.  Without this warning the file looks fine
    # (passes schema, zero errors) while contributing nothing to drift detection.
    # Fire W609 so the author sees the routing mismatch and the canonical
    # location, regardless of whether the rest of the drift logic finds
    # anything to compare against.
    if anchor_path.parent.name == "impl_context":
        errors.append(
            make_error(
                "W609",
                f"ANCHOR_MISFILED: '{anchor_path.name}' has artifact_role='anchor' "
                f"but lives inside '{anchor_path.parent}'.  The Trinity Anchor must "
                f"sit at spec/16_impl_context.json (one level up); files inside "
                f"spec/impl_context/ are per-milestone plans (vc:16-impl-context).  "
                f"Move this file to '{anchor_path.parent.parent}/16_impl_context.json' "
                f"so cross-milestone drift checks (E308/E309/W588/W589/W607) can "
                f"resolve the impl_context/ sibling directory correctly.",
            )
        )

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

    # ── Single-pass milestone_index sweep (E308 ownership / E309 prefix / W607 path) ──
    # All three checks iterate the same list with the same dict-validity guard.
    # Combining them keeps the semantics identical (each check still owns its
    # registry) while avoiding 3× iteration and 3× repetition of the
    # ``isinstance(entry, dict)`` skip.  The schema enforces presence + pattern
    # of every field touched here; the guards below are defence-in-depth in case
    # routing ever reaches this validator with schema-bypassing data.
    #
    # Done milestones are exempt from FR/API ownership conflict (delivered IDs
    # may be referenced again in follow-on work) but still participate in the
    # prefix-collision and context-path checks (a done milestone's namespace
    # is still allocated, and its plan file must still exist on disk).
    impl_context_dir = anchor_path.parent / "impl_context"
    id_to_milestone: dict[str, str] = {}        # FR/API ID → first-seen milestone_id (E308)
    prefix_to_milestone: dict[str, str] = {}    # checklist_id_prefix → first-seen milestone_id (E309)
    for entry in milestone_index:
        if not isinstance(entry, dict):
            continue
        ms_id = entry.get("milestone_id", "")
        status = entry.get("status", "")

        # ── E308: FR/API ownership conflict (skip done milestones) ───────────
        if status != "done":
            for ref_id in entry.get("fr_refs", []) or []:
                if not isinstance(ref_id, str):
                    continue
                if ref_id in id_to_milestone:
                    prev_ms = id_to_milestone[ref_id]
                    kind = "API" if ref_id.startswith("api-") else "FR"
                    errors.append(
                        make_error(
                            "E308",
                            f"ANCHOR_SCOPE_DRIFT: {kind} ownership conflict — '{ref_id}' is "
                            f"claimed by both non-done milestone '{prev_ms}' and '{ms_id}'.  "
                            f"Only one non-done milestone may own a given {kind} at a time.",
                        )
                    )
                else:
                    id_to_milestone[ref_id] = ms_id

        # ── E309: checklist_id_prefix collision (applies to all milestones) ──
        # Two milestone_index entries sharing a prefix would allocate checklist
        # IDs from the same namespace in their 16a plans — the authoring-time
        # equivalent of the cross-milestone ID collision E309 catches below at
        # plan-comparison time.
        prefix = entry.get("checklist_id_prefix")
        if isinstance(prefix, str) and prefix:
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

        # ── W607: declared context_path must exist on disk ───────────────────
        # Schema pins context_path to ``^(spec/)?impl_context/<filename>.json$``.
        # Resolve using the same logic as ``traceability_closure._resolve_context_path``:
        # strip an optional leading directory segment that matches the anchor's
        # parent dir name (the ``spec/`` convention), then join relative to
        # the anchor's parent dir (= spec_dir).  This keeps resolution
        # consistent between the anchor validator and traceability_closure,
        # and correctly handles both ``spec/impl_context/foo.json`` and
        # ``impl_context/foo.json`` forms.
        ctx_path = entry.get("context_path")
        if isinstance(ctx_path, str) and ctx_path:
            resolved_ctx = ctx_path
            # Strip optional leading segment matching the anchor's parent
            # directory name (typically ``spec/``).  Uses the actual dirname
            # so the logic works in test fixtures whose spec dir is named
            # differently.
            anchor_parent_name = anchor_path.parent.name
            if resolved_ctx.startswith(anchor_parent_name + "/"):
                resolved_ctx = resolved_ctx[len(anchor_parent_name) + 1:]
            # Also strip a literal ``spec/`` prefix when the anchor's parent
            # has a different name (e.g. test fixtures).  The schema allows
            # ``spec/impl_context/...`` as a repo-root-relative convention.
            elif resolved_ctx.startswith("spec/"):
                resolved_ctx = resolved_ctx[len("spec/"):]
            declared_path = anchor_path.parent / resolved_ctx
            if not declared_path.exists():
                errors.append(
                    make_error(
                        "W607",
                        f"ANCHOR_CONTEXT_PATH_MISSING: milestone_index entry "
                        f"'{ms_id}' declares context_path '{ctx_path}' but the "
                        f"file does not exist at '{declared_path}'. Drift detection "
                        f"will silently skip this milestone until the plan is authored.",
                    )
                )

    # ── Filesystem-dependent checks (E308 scope drift, E309 checklist drift) ──
    # These require loading milestone context files from impl_context/.
    # NOTE: W607 above intentionally already ran inside the milestone_index
    # sweep, so a missing ``impl_context/`` directory still surfaces W607 for
    # every declared milestone — the sweep does not depend on the directory
    # existing, only on the declarations existing.  This early return only
    # short-circuits the cross-file E308/E309/W588/W589 checks that genuinely
    # need a populated directory.
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
    files_seen = 0
    for ms_file in sorted(impl_context_dir.glob("*.json")):
        files_seen += 1
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
        # Rename to ms_declared_schema to avoid shadowing the outer-scope
        # ``declared_schema`` variable used by the W608 check earlier in this
        # function (line ~86).  The two variables have unrelated semantics —
        # the outer is the ANCHOR's $schema (legacy detection); this one is
        # each MILESTONE PLAN's $schema (mis-schemaed detection).
        ms_declared_schema = ms_data.get("$schema")
        if ms_declared_schema != "vc:16-impl-context":
            # File parses as JSON but isn't declared as a milestone plan.
            # Silent-skipping it would hide authoring mistakes (missing or
            # wrong `$schema`) and drop the file from every drift check.
            # Surface the mismatch so the author can either fix the $schema
            # or move the file out of impl_context/.
            errors.append(
                make_error(
                    "W589",
                    f"ANCHOR_MILESTONE_MISSCHEMAED: '{ms_file.name}' in "
                    f"impl_context/ has $schema={ms_declared_schema!r} — expected "
                    f"'vc:16-impl-context'. Drift checks skipped this file.",
                )
            )
            continue
        milestone_contexts[str(ms_file)] = ms_data

    if not milestone_contexts:
        # ── W611: drift detection suppressed ────────────────────────────��────
        # If impl_context/ contained JSON files but none survived filtering
        # (all hit W588/W589), cross-milestone E308/E309 checks are completely
        # suppressed.  Without this warning the anchor looks clean while
        # contributing nothing to drift detection.  When files_seen==0 the
        # directory is genuinely empty — a valid state for a fresh anchor.
        if files_seen > 0:
            errors.append(
                make_error(
                    "W611",
                    f"ANCHOR_DRIFT_SUPPRESSED: impl_context/ contains "
                    f"{files_seen} JSON file(s) but none declare "
                    f"$schema='vc:16-impl-context' — E308/E309 cross-milestone "
                    f"drift detection is completely suppressed.  Fix the W588/W589 "
                    f"warnings above to restore drift checks.",
                )
            )
        return errors

    # ── E308: ANCHOR_SCOPE_DRIFT (bidirectional scope check) ──────────────────
    # milestone scope_in must not overlap anchor scope_out, and vice versa.
    # Normalisation: lowercase + strip for case-insensitive comparison.  The
    # schema's ``uniqueItems: true`` is case-sensitive (``"Auth"`` and ``"auth"``
    # are distinct items), but for drift detection purposes they describe the
    # same scope category.  This means an anchor with both ``"Auth"`` and
    # ``"auth"`` in scope_in passes schema validation but collapses to one
    # entry here — intentional, since the drift check cares about semantic
    # overlap, not string identity.
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

    # ── W610: ANCHOR_PREFIX_VIOLATION ───────────────────────────────────────
    # The anchor declares a checklist_id_prefix per milestone (e.g. "AUTH").
    # 16a planners are told to name checklist IDs starting with that prefix.
    # Schema cannot enforce this cross-artifact contract — verify it here by
    # matching each loaded milestone plan to its anchor index entry via
    # context_path and checking every checklist ID against the prefix.
    # Build reverse map: ms filename → declared prefix (from the milestone_index sweep).
    ms_path_to_prefix: dict[str, str] = {}
    for entry in milestone_index:
        if not isinstance(entry, dict):
            continue
        ctx_path = entry.get("context_path")
        prefix = entry.get("checklist_id_prefix")
        if isinstance(ctx_path, str) and isinstance(prefix, str) and prefix:
            resolved_ctx = ctx_path
            anchor_parent_name = anchor_path.parent.name
            if resolved_ctx.startswith(anchor_parent_name + "/"):
                resolved_ctx = resolved_ctx[len(anchor_parent_name) + 1:]
            elif resolved_ctx.startswith("spec/"):
                resolved_ctx = resolved_ctx[len("spec/"):]
            abs_path = str(anchor_path.parent / resolved_ctx)
            ms_path_to_prefix[abs_path] = prefix

    for ms_file, ms_data in milestone_contexts.items():
        expected_prefix = ms_path_to_prefix.get(ms_file)
        if not expected_prefix:
            continue
        ms_plan = ms_data.get("plan", {}) if isinstance(ms_data.get("plan"), dict) else {}
        checklist = (
            ms_plan.get("spec_alignment", {}).get("checklist", [])
            if isinstance(ms_plan.get("spec_alignment"), dict)
            else []
        )
        ms_name = Path(ms_file).name
        prefix_with_sep = expected_prefix + "_"
        for item in checklist:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            if isinstance(item_id, str) and not item_id.startswith(prefix_with_sep):
                errors.append(
                    make_error(
                        "W610",
                        f"ANCHOR_PREFIX_VIOLATION: checklist id '{item_id}' in "
                        f"'{ms_name}' does not start with the declared "
                        f"checklist_id_prefix '{expected_prefix}_' from "
                        f"milestone_index.  Namespace violations undermine "
                        f"E309 collision prevention.",
                    )
                )

    return errors
