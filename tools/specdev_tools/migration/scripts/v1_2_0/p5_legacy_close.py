"""``p5_legacy_close``: a milestone that was done before 1.2.0 gets a legacy close record, and the 14 ``status`` leaves the roadmap (phase 5).

Which milestones are legacy-closed is ``spec_reads.closed_sources`` (the capture's three ways a milestone was closed in 1.1.1: the roadmap
says ``done``, the anchor row says ``done``, the plan's review verdict is ``verified``; any one suffices).  The close is M8's own: the
anchor store writes ``{signed_off_by: legacy-migration, source, signoff: null, plan_hash}`` and sets the row ``done``, and the plan is
frozen from then on.  ``source`` names the evidence in that order (``14.status``, ``anchor.status``, ``16c.verdict``).  The hash is taken
from the plan as it stands, so every plan reshaping of phases 2 to 4 is in it; this script and the ones after it never write a plan file.

A milestone the sources disagree about (one says done, another says it is not: the roadmap, the anchor, the 09 milestone the roadmap
names in ``source_milestones``, the verdict) gets an operator item ``status-conflict``; the closed ones are closed all the same, the item
asks the operator to confirm.  A closed milestone that cannot be closed (no plan file names it, or no anchor row is about it) gets an
operator item ``legacy-close-skipped`` and is left as it is.  An open milestone is not touched.

The 14 ``milestones[].status`` (map row SC-14-09) is removed here and nowhere earlier: until this script ran, the closed rule had to be able
to read it.  It reads the capture now (ruling P23), so the field can go and a rerun computes the same closed set.
"""

from __future__ import annotations

from typing import Any

from specdev_tools.migration.context import CAPTURE_REL
from specdev_tools.graph.names import ROW_DONE
from specdev_tools.lifecycle import anchor_store
from specdev_tools.migration.maps import shape_rows
from specdev_tools.migration.registry import PHASE_CLOSE, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import anchor_rows, CAPTURE_STATUS, closed_sources, files_of_row, last_key, LEGACY, parents_at, plan_milestones, ROADMAP_STEP, row_milestone, VERDICT_VERIFIED
from specdev_tools.migration.worklist import WorklistItem, add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p5_legacy_close", phase=PHASE_CLOSE, touches=("14", "16", "extras"))

KIND_CONFLICT = "status-conflict"
KIND_SKIPPED = "legacy-close-skipped"


def _status_of(entries: list[Any], milestone: str) -> str | None:
    """The captured ``legacy_status`` of *milestone* in one ``milestone_status`` section (``None`` when it holds no entry or no status)."""
    entry = next((e for e in entries if e.get("milestone") == milestone), None)
    status = entry.get(LEGACY + "status") if entry else None
    return status if isinstance(status, str) else None


def _source_milestones(capture: dict[str, Any]) -> dict[str, list[str]]:
    """``{14 milestone id: the 09 milestone ids it names in source_milestones}``, as the capture holds them (both sides as 1.1.1 wrote them)."""
    return {
        row["milestone"]: [s for s in row.get(LEGACY + "source_milestones") or [] if isinstance(s, str)]
        for row in capture.get("milestone_links") or []
        if row.get("step") == ROADMAP_STEP
    }


def _readings(ctx, capture: dict[str, Any], milestone: str) -> list[tuple[str, str]]:
    """What each source says of *milestone* as ``(source, reading)``: a status, or ``verified`` / the verdict of its plan; a source with no value is left out."""
    held = capture.get(CAPTURE_STATUS) or {}
    readings: list[tuple[str, str]] = []
    for name, section in (("14", "roadmap"), ("anchor", "anchor")):
        status = _status_of(held.get(section) or [], milestone)
        if status:
            readings.append((name, status))
    for source in _source_milestones(capture).get(milestone, []):
        status = _status_of(held.get("impl_plan") or [], source)
        if status:
            readings.append((f"09 {source}", status))
    by_plan = plan_milestones(ctx)
    for entry in held.get("plans") or []:
        verdict = entry.get("review_verdict")
        if by_plan.get(entry["file"]) == milestone and isinstance(verdict, str) and verdict:
            readings.append(("16c verdict", verdict))
    return readings


def _says_done(reading: str) -> bool:
    return reading in (ROW_DONE, VERDICT_VERIFIED)


def _conflicts(ctx) -> list[WorklistItem]:
    capture = ctx.documents.load(CAPTURE_REL).data
    closed = closed_sources(ctx)
    milestones = [entry["milestone"] for entry in (capture.get(CAPTURE_STATUS) or {}).get("roadmap") or []]
    items: list[WorklistItem] = []
    for milestone in milestones:
        readings = _readings(ctx, capture, milestone)
        if not (any(_says_done(r) for _s, r in readings) and any(not _says_done(r) for _s, r in readings)):
            continue
        said = "; ".join(f"{source} says {reading}" for source, reading in readings)
        outcome = f"closed by {', '.join(closed[milestone])}" if milestone in closed else "no closing source, so it stays open"
        items.append(make_item(
            ROADMAP_STEP, KIND_CONFLICT, milestone, audience="operator", blocking=True,
            evidence=f"the sources of {milestone} disagree: {said} ({outcome})",
            proposal=(
                f"decide this item first, before any other work of the pass. If {milestone} is done, resolve the item. If it is not: undo the migration "
                "(`git checkout -- spec && git clean -fd spec` before the migration commit; `git revert <the migration commit>` after it), correct in the 1.1.1 spec each source "
                "that says done (the evidence names them), commit, and run `specdev align apply spec --auto` again: the milestone is then open and its plan is migrated as an open plan "
                "(see the host guide, 'A milestone closed by mistake')"
                if milestone in closed else f"decide whether {milestone} is done and close it with `specdev milestone close`"
            ),
        ))
    return items


def _row_of(ctx, milestone: str) -> dict[str, Any] | None:
    return next((row for row in anchor_rows(ctx) if row_milestone(row) == milestone), None)


def _plan_of(ctx, milestone: str) -> str | None:
    return next((rel for rel, held in plan_milestones(ctx).items() if held == milestone), None)


def _plan_closes(ctx) -> tuple[list[tuple[str, str]], list[WorklistItem]]:
    """The closes to write as ``(milestone, source)`` and the items for the closed milestones that cannot be closed."""
    closes: list[tuple[str, str]] = []
    skipped: list[WorklistItem] = []
    for milestone, names in sorted(closed_sources(ctx).items()):
        row = _row_of(ctx, milestone)
        if row is not None and row.get("close") is not None:
            continue
        reason = (
            f"no anchor row is about {milestone}" if row is None
            else f"no plan file names {milestone} in its `milestone` key" if _plan_of(ctx, milestone) is None else None
        )
        if reason:
            skipped.append(make_item(
                "16", KIND_SKIPPED, milestone, audience="operator", blocking=True,
                evidence=f"{milestone} is done by {', '.join(names)}, but {reason}, so the legacy close cannot be written (E767 / E803)",
                proposal="add the anchor row or the plan's `milestone` key, then run the migration again: the close is written the next time",
            ))
        else:
            closes.append((milestone, ", ".join(names)))
    return closes, skipped


def _status_removals(ctx) -> list[tuple[str, dict[str, Any], str]]:
    """The ``(file, holder, key)`` of each field the script's map rows remove (the 14 milestone ``status``)."""
    found = []
    for row in shape_rows(SCRIPT.id):
        key = last_key(row["path"])
        for rel in files_of_row(ctx, row, set()):
            found.extend((rel, holder, key) for holder in parents_at(ctx.documents.load(rel).data, row["path"]) if key in holder)
    return found


def _items(ctx, skipped: list[WorklistItem]) -> list[WorklistItem]:
    return [*_conflicts(ctx), *skipped]


def detect(ctx) -> int:
    """Closes still to write, 14 ``status`` keys still to remove, and items not yet listed."""
    closes, skipped = _plan_closes(ctx)
    return len(closes) + len(_status_removals(ctx)) + len(missing_items(ctx, _items(ctx, skipped)))


def apply(ctx) -> ScriptResult:
    """Write the legacy closes through the anchor store, remove the 14 ``status``, list the conflicts and the closes that could not be written."""
    closes, skipped = _plan_closes(ctx)
    items = _items(ctx, skipped)
    removals = _status_removals(ctx)
    for _rel, holder, key in removals:
        del holder[key]
    listed = add_items(ctx, items)
    # The anchor is written by the store, on disk, after the documents were read: the set holds no edit of that file.
    for milestone, source in closes:
        anchor_store.write_legacy_close(ctx.spec_root, milestone, source, repo_root=ctx.toolkit_root)
    residue = tuple(f"{milestone}: legacy close ({source})" for milestone, source in closes)
    if removals:
        residue += (f"SC-14-09: {len(removals)} removed",)
    return ScriptResult(edits=len(closes) + len(removals) + listed, worklist_items=listed, residue=residue)


def _bad_close(row: Any) -> bool:
    """A row whose ``close`` is a legacy close but which is not ``done`` with a plan hash and no sign-off."""
    close = row.get("close") if isinstance(row, dict) else None
    if not close or not anchor_store.is_legacy_close(close):
        return False
    return not (row.get("status") == ROW_DONE and close.get("plan_hash") and close.get("signoff") is None)


def verify(before, after) -> list[Problem]:
    """Every anchor row that is a legacy close is ``done`` with a plan hash and no sign-off, and no 14 milestone keeps a ``status``."""
    problems: list[Problem] = []
    for rel, document in sorted(after.documents.items()):
        if not isinstance(document, dict):
            continue
        milestones = document.get("milestones") if rel.startswith(f"{ROADMAP_STEP}_") else None
        problems += [Problem(f"{rel}: milestone {m.get('milestone_id')} still has a status", rel) for m in milestones or [] if isinstance(m, dict) and "status" in m]
        rows = (document.get("plan") or {}).get("milestone_index") if rel.startswith("16_") else None
        problems += [Problem(f"{rel}: the legacy close of {row_milestone(row)} is not a done row with a plan hash and no sign-off", rel) for row in rows or [] if _bad_close(row)]
    return problems
