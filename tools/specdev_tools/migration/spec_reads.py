"""What the migration scripts share when they read a 1.1.1 spec folder and the capture: the one place for each fact.

Which file is step N, which files are plans, which milestone a plan is for, which milestones are legacy-closed, the
renames phase 2 recorded, and how a row of the shape map (``maps/v1_2_0.yaml``) finds the files it applies to.  A script
imports these from here, never from another script, so the order ``p1`` to ``p7`` is a run order only
(the open-item array helpers and the 09 schedule proposals are here for that reason).
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from typing import Any

from specdev_tools.core.ambiguity_items import ANCHOR_STEP
from specdev_tools.core.plan_files import MILESTONE_KEY, plan_files
from specdev_tools.core.step_paths import PLAN_DIR_NAME, STEP_JSON_RE
from specdev_tools.graph.ids import mint_slug
from specdev_tools.graph.model import Graph
from specdev_tools.graph.names import ABOUT, ROADMAP_STEP, ROW_DONE
from specdev_tools.graph.resolve import link_target_allowed
from specdev_tools.lifecycle.anchor_store import is_legacy_close
from specdev_tools.migration.context import CAPTURE_REL, MigrationContext

LEGACY = "legacy_"
"""The prefix of every value the capture copied from a 1.1.1 file."""
RENAMES_KEY = "renames"
"""The capture section that lists the ids phase 2 renamed."""
AMBIGUITY = "ambiguity-item"
PLAN_HOLDER_STEP = "16a"
"""The step the graph gives every open item of a plan file."""
OPEN_ITEM_ID_PREFIX = "amb-"
VERDICT_VERIFIED = "verified"
CAPTURE_STATUS = "milestone_status"
SOURCE_ROADMAP = "14.status"
SOURCE_ANCHOR = "anchor.status"
SOURCE_VERDICT = "16c.verdict"
_SOURCE_ORDER = (SOURCE_ROADMAP, SOURCE_ANCHOR, SOURCE_VERDICT)

# What a shape-map row id says about the file it applies to (``SC-16_impl_context-13``); the anchor file is the step ``16``
# file of the spec folder, so its row-id fragment is not the step id ``ANCHOR_STEP``.
ANCHOR_ROW_STEP = "16_anchor"
PLAN_ROW_STEP = "16_impl_context"
STRIP = "strip"
_ROW_STEP = re.compile(r"^SC-(.+)-\d+$")
_TOKEN = re.compile(r"^([^\[\]{}]+)(\[\]|\{\})?$")


# --- the files of the spec folder ---------------------------------------------------------------------------------------


def step_json_names(spec_root: str) -> list[tuple[str, str]]:
    """``(step id, file name)`` of every root step file ``NN_*.json`` of the spec folder, in name order."""
    return [(match.group(1), name) for name in sorted(os.listdir(spec_root)) if (match := STEP_JSON_RE.match(name))]


def step_file(ctx: MigrationContext, step: str) -> str | None:
    """The file name of *step* in the spec folder (``None`` when the host has none; the first in name order when it has two)."""
    return next((name for found, name in step_json_names(ctx.spec_root) if found == step), None)


def step_data(ctx: MigrationContext, step: str) -> dict[str, Any]:
    """The data of the file of *step* (``{}`` when the host has none)."""
    name = step_file(ctx, step)
    data = ctx.documents.load(name).data if name else None
    return data if isinstance(data, dict) else {}


def anchor_rows(ctx: MigrationContext) -> Iterator[dict[str, Any]]:
    """The objects of the anchor's ``plan.milestone_index`` (legacy or converted)."""
    plan = step_data(ctx, ANCHOR_STEP).get("plan")
    rows = plan.get("milestone_index") if isinstance(plan, dict) else None
    return (row for row in rows if isinstance(row, dict)) if isinstance(rows, list) else iter(())


def plan_rels(ctx: MigrationContext) -> list[str]:
    """Every plan file, relative to the spec folder, in name order."""
    return [f"{PLAN_DIR_NAME}/{path.name}" for path in plan_files(ctx.spec_root)]


def insert_key(data: dict[str, Any], name: str, value: Any, *, after: str | None = None) -> None:
    """Add *name* to *data* in place, right after the key *after* (first when *after* is absent), keeping the other keys in order."""
    rest = list(data.items())
    data.clear()
    placed = False
    if after is None or after not in dict(rest):
        data[name], placed = value, True
    for key, held in rest:
        data[key] = held
        if key == after and not placed:
            data[name], placed = value, True


# --- plans and the milestones they are for ------------------------------------------------------------------------------


def row_milestone(row: dict[str, Any]) -> str | None:
    """The 14 milestone id of an anchor row: the legacy ``milestone_id``, or the one id of ``about``."""
    legacy = row.get("milestone_id")
    if isinstance(legacy, str):
        return legacy
    about = row.get("about")
    return about[0] if isinstance(about, list) and len(about) == 1 and isinstance(about[0], str) else None


def plan_rel_of_row(row: dict[str, Any]) -> str | None:
    """The plan file a legacy row names, as a path relative to the spec folder (``impl_context/<file>``)."""
    path = row.get("context_path")
    if not isinstance(path, str) or not path:
        return None
    return f"{PLAN_DIR_NAME}/{path.replace(chr(92), '/').rsplit('/', 1)[-1]}"


def plan_milestones(ctx: MigrationContext) -> dict[str, str]:
    """``{plan file: milestone id}``: the plan's own key when it has one, else the anchor row that names the file."""
    named = {rel: row_milestone(row) for row in anchor_rows(ctx) if (rel := plan_rel_of_row(row))}
    found: dict[str, str] = {}
    for rel in plan_rels(ctx):
        key = ctx.documents.load(rel).data.get(MILESTONE_KEY)
        milestone = key if isinstance(key, str) else named.get(rel)
        if milestone:
            found[rel] = milestone
    return found


def closed_sources(ctx: MigrationContext) -> dict[str, list[str]]:
    """``{milestone id: the evidence names that say it is closed}`` for the 14 milestones that are legacy-closed, read from ``capture.json``.

    The three ways a milestone was closed in 1.1.1, each from the capture's ``milestone_status`` (the values as they were
    before phase 3 removed them): the roadmap says ``done`` (``14.status``), the anchor row says ``done``
    (``anchor.status``; a live legacy close record of the row counts too), or the plan's review verdict is ``verified``
    (``16c.verdict``).  The names are listed in that order.
    """
    held = ctx.documents.load(CAPTURE_REL).data.get(CAPTURE_STATUS) or {}
    found: dict[str, list[str]] = {}
    for name, section in ((SOURCE_ROADMAP, "roadmap"), (SOURCE_ANCHOR, "anchor")):
        for entry in held.get(section) or []:
            if entry.get(LEGACY + "status") == ROW_DONE:
                found.setdefault(entry["milestone"], []).append(name)
    for row in anchor_rows(ctx):
        milestone = row_milestone(row)
        if milestone and is_legacy_close(row.get("close")) and SOURCE_ANCHOR not in found.get(milestone, []):
            found.setdefault(milestone, []).append(SOURCE_ANCHOR)
    by_plan = plan_milestones(ctx)
    for entry in held.get("plans") or []:
        milestone = by_plan.get(entry["file"])
        if milestone and entry.get("review_verdict") == VERDICT_VERIFIED:
            found.setdefault(milestone, []).append(SOURCE_VERDICT)
    return {milestone: sorted(names, key=_SOURCE_ORDER.index) for milestone, names in found.items()}


def closed_milestones(ctx: MigrationContext) -> set[str]:
    """The 14 milestones that are legacy-closed: the keys of ``closed_sources`` (they read the capture, so the answer does not change when a later phase removes the 14 ``status``)."""
    return set(closed_sources(ctx))


def closed_plan_files(ctx: MigrationContext) -> set[str]:
    """The plan files of legacy-closed milestones."""
    closed = closed_milestones(ctx)
    return {rel for rel, milestone in plan_milestones(ctx).items() if milestone in closed}


def capture_renames(ctx: MigrationContext) -> dict[str, dict[str, str]]:
    """The ids phase 2 renamed, as ``{kind: {old id: new id}}`` (empty when the capture holds no ``renames`` section).

    The capture keys 09 records by the id they had when it was made; a reader that matches one of them by id maps the
    old id through this (``p2_id_collisions`` writes the section in the run that renames).
    """
    renames = ctx.documents.load(CAPTURE_REL).data.get(RENAMES_KEY)
    found: dict[str, dict[str, str]] = {}
    for entry in renames if isinstance(renames, list) else ():
        if isinstance(entry, dict):
            found.setdefault(entry["kind"], {})[entry["old"]] = entry["new"]
    return found


# --- open items of a plan and the 09 milestone schedule ------------------------------------------------------------------


def array_at(data: dict[str, Any], location: str) -> list[Any] | None:
    """The list at a dotted ``.a.b`` location of *data*, ``None`` when a key or the list is missing."""
    node: Any = data
    for key in location.lstrip(".").split("."):
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, list) else None


def ensure_array(data: dict[str, Any], location: str) -> list[Any]:
    """The list at a dotted ``.a.b`` location of *data*; the missing keys and the list are made (a key after the last one holds the list)."""
    *walk, last = location.lstrip(".").split(".")
    node = data
    for key in walk:
        node = node.setdefault(key, {})
    return node.setdefault(last, [])


def has_open_item(array: list[Any], description: str, about: list[str]) -> bool:
    """Whether *array* holds an item with this description and ``about``."""
    return any(isinstance(entry, dict) and entry.get("description") == description and entry.get("about") == about for entry in array)


def add_open_item(array: list[Any], description: str, about: list[str], taken: set[str], label: str) -> bool:
    """Append a unified open item to *array* unless ``has_open_item``; its id is minted from *label*, free of *taken* (and added to it).  Returns whether it added one."""
    if has_open_item(array, description, about):
        return False
    new_id = mint_slug(label, taken, prefix=OPEN_ITEM_ID_PREFIX)
    taken.add(new_id)
    array.append({"id": new_id, "description": description, "about": about})
    return True


def about_allowed(graph: Graph, holder_step: str, target_id: str) -> bool:
    """Whether an open item of step *holder_step* may name *target_id* in ``about``: the node exists and is in an earlier step (E700, E701, E702 stay quiet)."""
    decl = next(link for link in graph.decls[AMBIGUITY].links if link.field == ABOUT)
    target = graph.by_id.get(target_id)
    return target is not None and link_target_allowed(decl, holder_step, target, graph.shape)


def schedule_proposals(ctx, graph, kind_of: dict[str, str]) -> dict[str, list[str]]:
    """``{09 milestone id (now): obligation ids it could schedule}``: the typed ``deliverables`` of the milestone and the FRs of the paired 14 milestones.

    Read from ``capture.json`` (``milestone_links``): the 09 rows are keyed by the id the milestone had when the capture
    was made, the 14 rows name their 09 milestones in ``legacy_source_milestones`` by the same old ids; ``capture_renames``
    maps an old 09 id to its id now.  Only ids of a kind the registry lets a 09 milestone schedule are proposed.
    """
    renames = capture_renames(ctx).get("design-milestone", {})
    decl = graph.decls.get("design-milestone")
    allowed = {k for link in (decl.links if decl else ()) if link.field == "schedules" for k in link.kinds}
    rows = ctx.documents.load(CAPTURE_REL).data.get("milestone_links") or []
    paired: dict[str, list[str]] = {}
    for row in rows:
        if row.get("step") == "14":
            for old in row.get("legacy_source_milestones") or []:
                paired.setdefault(old, []).extend(row.get("legacy_fr_refs") or [])
    found: dict[str, list[str]] = {}
    for row in rows:
        if row.get("step") != "09":
            continue
        old = str(row["milestone"])
        ids = [e.get("id") for e in row.get("legacy_deliverables") or [] if isinstance(e, dict)] + paired.get(old, [])
        unique = list(dict.fromkeys(i for i in ids if isinstance(i, str) and kind_of.get(i) in allowed))
        found[renames.get(old, old)] = unique
    return found


# --- the rows of the shape map ------------------------------------------------------------------------------------------


def row_step(row: dict[str, Any]) -> str:
    """The step part of a row id: ``SC-14-09`` gives ``14``, ``SC-16_impl_context-13`` gives ``16_impl_context``."""
    match = _ROW_STEP.match(row["id"])
    return match.group(1) if match else ""


def _step_into(nodes: list[Any], token: str) -> list[Any]:
    """The objects one path token leads to from each of *nodes*."""
    match = _TOKEN.match(token)
    if not match:
        return []
    name, suffix = match.groups()
    reached: list[Any] = []
    for node in nodes:
        held = node.get(name) if isinstance(node, dict) else None
        if suffix == "[]" and isinstance(held, list):
            reached.extend(held)
        elif suffix == "{}" and isinstance(held, dict):
            reached.extend(held.values())
        elif suffix is None and isinstance(held, dict):
            reached.append(held)
    return reached


def parents_at(data: Any, path: str) -> Iterator[dict[str, Any]]:
    """The objects of *data* that would hold the last key of *path*; ``[]`` steps into each object of a list, ``{}`` into each map value."""
    current: list[Any] = [data]
    *walk, _last = path.split(".")
    for token in walk:
        current = _step_into(current, token)
    yield from (node for node in current if isinstance(node, dict))


def last_key(path: str) -> str:
    """The key a row path ends in (its last segment)."""
    return path.rsplit(".", 1)[-1]


def files_of_row(ctx: MigrationContext, row: dict[str, Any], closed_rels: set[str]) -> list[str]:
    """The spec files a row applies to (relative paths): the step's file, the anchor, or the plan files its ``closed_plans`` admits."""
    step = row_step(row)
    if step == PLAN_ROW_STEP:
        keep_closed = row.get("closed_plans", "keep") != STRIP
        return [rel for rel in plan_rels(ctx) if not (keep_closed and rel in closed_rels)]
    name = step_file(ctx, ANCHOR_STEP if step == ANCHOR_ROW_STEP else step)
    return [name] if name else []
