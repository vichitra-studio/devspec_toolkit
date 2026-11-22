"""``p5_triage``: the rows of the triage list that no content script lists (phase 5).

It writes worklist items and nothing else.  Each row is one kind of item; the id is stable, so a rerun adds none and a resolved item stays resolved:

* ``anchor-open-item``: an open item (not resolved) of the anchor's ``plan.ambiguities``, from the capture.  The anchor is not exempt from
  the open-item rule (only frozen plans are), so each is the operator's to raise again in the artifact it is about, as an open item with
  ``about``, or to drop (blocking).
* ``decisions-seed``: a seed of the manifest whose id or file says "decision": it is folded into the seeds that own its content and removed
  (blocking: a decisions seed is an error in 1.2.0).
* ``seed-trinity-route``: a ``step_requirements`` key at or after step 16 (a node of the trinity steps links no seed, so the route can
  never be used).
* ``pending-task``: a task of a legacy-closed milestone that the roadmap left ``pending`` or ``in_progress`` (informational: progress is computed from
  refined criteria and proof now, nothing stores it).
* ``staging-environment``: a 02a environment declared ``decommissioned-at-production-go-live`` that no step-12 job runs in.
* ``seed-route-cleanup``: a seed no route names (E747) and a route no node of its step uses (E748), as ``check_seed_routes`` finds them on the
  migrated tree; the decisions seed is left out (its own item covers it).

The open items of the frozen plans are listed by ``p4_ambiguities`` (kind ``legacy-open-item``, not blocking); this script counts them in its
report.  The status conflicts are listed by ``p5_legacy_close``.  No item asks for ``signers``, and the legacy binding pass is not a triage item.
"""

from __future__ import annotations

import os
import re
from typing import Any

from specdev_tools.core.ambiguity_items import ANCHOR_STEP
from specdev_tools.migration.context import CAPTURE_REL
from specdev_tools.core.step_paths import PLAN_DIR_NAME
from specdev_tools.graph.build import build_graph
from specdev_tools.migration.registry import PHASE_CLOSE, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import closed_milestones, LEGACY, plan_milestones, ROADMAP_STEP, step_data, step_file
from specdev_tools.migration.worklist import WORKLIST_FILE, WorklistItem, add_items, make_item, missing_items
from specdev_tools.validation.graph_checks.context import SEED_MANIFEST_PATH, GraphCheckContext
from specdev_tools.validation.graph_checks.seed_routes import STEP_REQUIREMENTS, TRINITY_KEYS, check_seed_routes

SCRIPT = ScriptSpec(id="p5_triage", phase=PHASE_CLOSE, touches=("extras",))

KIND_ANCHOR_ITEM = "anchor-open-item"
KIND_DECISIONS_SEED = "decisions-seed"
KIND_TRINITY_ROUTE = "seed-trinity-route"
KIND_PENDING_TASK = "pending-task"
KIND_STAGING = "staging-environment"
KIND_SEED_ROUTE = "seed-route-cleanup"
STEP_SEEDS = "00"
STEP_DELIVERY_BASELINE = "02a"
STEP_CI_GATES = "12"
OPEN_TASK_STATUSES = ("pending", "in_progress")
DECOMMISSIONED = "decommissioned-at-production-go-live"
UNROUTED = "unrouted"
_DECISION = re.compile(r"decision", re.IGNORECASE)
_WORKLIST_REL = WORKLIST_FILE.replace("\\", "/")


def _manifest(ctx) -> dict[str, Any]:
    """The seed manifest as the spec folder holds it (``{}`` when the host has none)."""
    if not os.path.isfile(os.path.join(ctx.spec_root, SEED_MANIFEST_PATH)):
        return {}
    data = ctx.documents.load(SEED_MANIFEST_PATH).data
    return data if isinstance(data, dict) else {}


def _seeds(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [seed for seed in manifest.get("seeds") or [] if isinstance(seed, dict) and isinstance(seed.get("seed_id"), str)]


def _decision_seeds(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [seed for seed in _seeds(manifest) if _DECISION.search(seed["seed_id"]) or _DECISION.search(str(seed.get("path", "")))]


def _routes_of(manifest: dict[str, Any], seed: str) -> list[str]:
    routes = manifest.get(STEP_REQUIREMENTS)
    return [step for step, seeds in routes.items() if isinstance(seeds, list) and seed in seeds] if isinstance(routes, dict) else []


def _anchor_items(ctx) -> list[WorklistItem]:
    anchor = step_file(ctx, ANCHOR_STEP)
    items = []
    for entry in ctx.documents.load(CAPTURE_REL).data.get("ambiguities") or []:
        held = entry.get(LEGACY + "item") or {}
        if entry.get("file") != anchor or not isinstance(held.get("id"), str):
            continue
        impact = held.get("impact") or held.get("about") or []
        items.append(make_item(
            ANCHOR_STEP, KIND_ANCHOR_ITEM, held["id"], audience="operator", blocking=True,
            evidence=f"{held.get('description', '')} (status {held.get('status', 'none')}, about {', '.join(map(str, impact)) or 'nothing named'}); an open item in the anchor is not exempt from the open-item rule",
            proposal="raise it again in the artifact it is about as an open item with `about`, or drop it",
        ))
    return items


def _decision_items(manifest: dict[str, Any]) -> list[WorklistItem]:
    return [
        make_item(
            STEP_SEEDS, KIND_DECISIONS_SEED, seed["seed_id"], audience="operator", blocking=True,
            evidence=f"the seed manifest lists {seed['seed_id']} ({seed.get('path', 'no path')}), which holds decisions; routed to steps {', '.join(_routes_of(manifest, seed['seed_id'])) or 'none'}",
            proposal="fold what it decides into the seeds that own each subject, then remove its entry (`seeds`, `global_seed_order`, `step_requirements`) and its document",
        )
        for seed in _decision_seeds(manifest)
    ]


def _trinity_items(manifest: dict[str, Any]) -> list[WorklistItem]:
    routes = manifest.get(STEP_REQUIREMENTS)
    return [
        make_item(
            STEP_SEEDS, KIND_TRINITY_ROUTE, key, audience="operator", blocking=False,
            evidence=f"step_requirements[{key!r}] routes {', '.join(map(str, seeds))} to a trinity step, whose nodes link no seed",
            proposal="move each seed to the step that distils it, or remove the route",
        )
        for key, seeds in (routes.items() if isinstance(routes, dict) else [])
        if key in TRINITY_KEYS and isinstance(seeds, list)
    ]


def _pending_task_items(ctx) -> list[WorklistItem]:
    closed = closed_milestones(ctx)
    return [
        make_item(
            ROADMAP_STEP, KIND_PENDING_TASK, row["task"], audience="operator", blocking=False,
            evidence=f"task {row['task']} of the closed milestone {row['milestone']} was {row[LEGACY + 'status']}" + (f" ({row[LEGACY + 'status_reason']})" if row.get(LEGACY + "status_reason") else ""),
            proposal="record the disposition `deferred` or `wont_do` with a reason, or confirm the task is done: progress is computed from the refined criteria and proof, nothing stores it now",
        )
        for row in ctx.documents.load(CAPTURE_REL).data.get("task_status") or []
        if row["milestone"] in closed and row.get(LEGACY + "status") in OPEN_TASK_STATUSES
    ]


def _environment_of(job: dict[str, Any]) -> str | None:
    ref = job.get("environment_ref")
    ref_id = ref.get("id") if isinstance(ref, dict) else ref
    return ref_id.rsplit(":", 1)[-1] if isinstance(ref_id, str) else None


def _staging_items(ctx) -> list[WorklistItem]:
    jobs = [job for job in step_data(ctx, STEP_CI_GATES).get("jobs") or [] if isinstance(job, dict)]
    used = {name for job in jobs if (name := _environment_of(job))}
    return [
        make_item(
            STEP_DELIVERY_BASELINE, KIND_STAGING, row["environment"], audience="operator", blocking=False,
            evidence=f"environment {row['environment']} is declared {DECOMMISSIONED} and no step-12 job runs in it",
            proposal="keep it with `scope: later` or `in` and add a staging job, or set `scope: out` (the stage bindings and the staging gate then skip it)",
        )
        for row in ctx.documents.load(CAPTURE_REL).data.get("environment_host_keys") or []
        if (row.get(LEGACY + "environment") or {}).get("lifecycle") == DECOMMISSIONED and row["environment"] not in used
    ]


def _seed_route_items(ctx, skip: set[str]) -> list[WorklistItem]:
    manifest = _manifest(ctx)
    if not _seeds(manifest):
        return []
    graph = build_graph(ctx.spec_root, ctx.toolkit_root)
    # The ownership table is the running toolkit's (a temp toolkit root has none); nothing in it depends on the host.
    checks = GraphCheckContext.from_graph(graph, None, None, git_root=ctx.host_root, spec_root=ctx.spec_root)
    items = []
    for finding in check_seed_routes(checks, "merge"):
        seed = finding.node_id
        if finding.code not in ("E747", "E748") or not seed or seed in skip:
            continue
        step, key = (finding.route[1], finding.route[1]) if finding.route else (STEP_SEEDS, UNROUTED)
        items.append(make_item(step, KIND_SEED_ROUTE, seed, audience="operator", blocking=False, evidence=f"{finding.code}: {finding.message}", key=key))
    return items


def _wanted(ctx) -> list[WorklistItem]:
    manifest = _manifest(ctx)
    decisions = {seed["seed_id"] for seed in _decision_seeds(manifest)}
    return [
        *_anchor_items(ctx),
        *_decision_items(manifest),
        *_trinity_items(manifest),
        *_pending_task_items(ctx),
        *_staging_items(ctx),
        *_seed_route_items(ctx, decisions),
    ]


def frozen_plan_open_items(ctx) -> int:
    """How many not-resolved items the capture holds for the plans of legacy-closed milestones (``p4_ambiguities`` lists each as ``legacy-open-item``)."""
    closed, by_plan = closed_milestones(ctx), plan_milestones(ctx)
    return sum(
        1
        for entry in ctx.documents.load(CAPTURE_REL).data.get("ambiguities") or []
        if str(entry.get("file", "")).startswith(f"{PLAN_DIR_NAME}/") and by_plan.get(entry["file"]) in closed
    )


def detect(ctx) -> int:
    """Items of the rows above that are not listed yet."""
    return len(missing_items(ctx, _wanted(ctx)))


def apply(ctx) -> ScriptResult:
    """List the items; report how many open items the frozen plans held."""
    items = _wanted(ctx)
    listed = add_items(ctx, items)
    counts = {kind: sum(1 for item in items if item.kind == kind) for kind in sorted({item.kind for item in items})}
    residue = tuple(f"{kind}: {count} item(s)" for kind, count in counts.items())
    residue += (f"open items in frozen plans: {frozen_plan_open_items(ctx)} (listed by p4_ambiguities as legacy-open-item)",)
    return ScriptResult(edits=listed, worklist_items=listed, residue=residue)


def verify(before, after) -> list[Problem]:
    """No file changed but the worklist."""
    return [
        Problem(f"{rel}: changed, and this script writes only the worklist", rel)
        for rel in sorted(set(before.files) | set(after.files))
        if before.files.get(rel) != after.files.get(rel) and rel != _WORKLIST_REL
    ]
