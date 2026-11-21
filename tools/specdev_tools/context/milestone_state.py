"""Deterministic milestone-state engine for the DevSpec Toolkit.

A pure, unit-testable derivation of per-group convergence and the milestone's phase position from the plan file, the
review findings under ``.specdev/findings/`` and what the spec graph says about the plan's items.

## Design notes

**What is derived and what is read.**  A plan item stores no status.  The engine derives a group's state from three
inputs: the findings files of the group (convergence), the roadmap tasks the item ``realises`` (a ``deferred`` or
``wont_do`` ``disposition`` set aside the group) and the open items of the plan that are about a node on the item's
chain (``blocked``).  Whether the milestone is ``closed`` is read from its anchor row (``status == done``), never from
group states.  The spec-side inputs are one ``SpecView``, built by ``load_spec_view``; without one every group is
judged from its findings files alone.

**Per-group states:** ``pending``, ``code_converged``, ``blocked``, ``deferred``, ``wont_do``.  First match wins:
``deferred``/``wont_do`` > ``blocked`` > ``code_converged`` > ``pending``.  ``blocked`` needs converged findings (the
work is done and waits on an open question) and an open item whose ``about`` names a node on the item's chain:
the plan item, the task criteria it ``realises``, the obligations they ``refine`` and the verifiers they list in
``verified_by``.  An open item carries no status, severity or resolved flag: all are alike.
``wont_do`` has the same precedence and roll-up exclusion as ``deferred``: both mean "not part of the active work
being tracked" (paused versus permanently cancelled) and are kept distinct so callers can tell them apart.  A group
whose criteria are all set aside is ``wont_do`` when every one is ``wont_do``, else ``deferred``.

**``executing`` is omitted.**  It is a transient in-flight state that is never persisted; the engine never emits it.

**``impl_complete`` vs ``review_pending`` disambiguation.**
- ``impl_complete``: every active (non-deferred, non-wont_do) group in {code_converged, blocked} AND *no
  milestone-review file exists at all*.
- ``review_pending``: same group condition AND milestone-review file(s) exist but *none* has empty findings.
- ``review_complete``: same group condition AND >=1 milestone-review file has ``findings == []``.

**All-deferred/wont_do milestone.**  If every group is deferred or wont_do, ``derived_phase_position`` defaults to
``"pending"`` (nothing to track), unless the anchor row is ``done``.

**No graph.**  When the spec graph cannot be built (a host that is not migrated), the view is empty: no group is
``deferred``, ``wont_do`` or ``blocked`` and nothing raises.

**Filesystem robustness.**  Findings files whose top-level JSON value is not a ``dict`` (e.g. a bare list) are
silently skipped for convergence detection.  Cross-platform mtime: ``os.stat().st_mtime`` + ``datetime.fromtimestamp``
with ``timezone.utc``.
"""
from __future__ import annotations

import glob as _glob
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..core.errors import FindingError
from ..core.scope_helpers import as_dict, as_list, dict_items, str_items
from ..graph.build import build_graph
from ..graph.contract import item_of
from ..graph.kinds import KindRegistryError
from ..graph.model import Graph
from ..graph.names import PAUSED_DISPOSITIONS, REALISES, REFINES, VERIFIED_BY
from ..graph.queries import task_of
from ..graph.trace import TraceOptions, trace_node
from ..lifecycle.anchor_store import read_row
from ..lifecycle.plans import MILESTONE_KEY
from ..trace.history import DONE_STATUS

_CHAIN_VERBS = frozenset({REALISES, REFINES, VERIFIED_BY})
_WONT_DO = "wont_do"
_DEFERRED = "deferred"


@dataclass(frozen=True)
class ItemView:
    """What the spec graph says about one plan item: the set-aside disposition of its criteria and the ids on its chain.

    ``set_aside`` is ``"deferred"`` or ``"wont_do"`` when every criterion the item ``realises`` belongs to a task with
    such a ``disposition`` (``None`` otherwise); ``chain`` holds the ids of the nodes the item reaches.
    """

    set_aside: str | None = None
    chain: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SpecView:
    """The spec-side inputs of one milestone: whether its anchor row is ``done`` and an ``ItemView`` per plan-item id."""

    closed: bool = False
    items: Mapping[str, ItemView] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> Any:
    """Load JSON from *path*, returning the parsed value."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _mtime_to_iso(path: str) -> str:
    """Return the UTC mtime of *path* as an ISO 8601 string (``YYYY-MM-DDTHH:MM:SSZ``)."""
    mtime = os.stat(path).st_mtime
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_empty_findings(path: str) -> bool:
    """Return True iff *path* is a valid findings file with ``findings == []``."""
    try:
        data = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    return data.get("findings") == []


def _latest_empty_findings(files: list[str]) -> str | None:
    """Return the path of the most-recent empty-findings file from *files*, or None."""
    empty = [f for f in files if _is_empty_findings(f)]
    if not empty:
        return None
    return max(empty, key=lambda f: os.stat(f).st_mtime)


# ---------------------------------------------------------------------------
# Per-group derivation
# ---------------------------------------------------------------------------

def derive_group_state(
    group: dict,
    findings_dir: str,
    ambiguities: list[dict],
    item_view: ItemView = ItemView(),
) -> dict:
    """Derive the state object for a single plan-item group.

    Parameters
    ----------
    group:
        One entry from ``plan.spec_alignment.checklist``.
    findings_dir:
        Absolute path to the ``.specdev/findings/`` directory.
    ambiguities:
        The open items of the plan file: ``plan.ambiguities`` and ``execution.emergent_ambiguities``.
    item_view:
        What the spec graph says about the item (``SpecView.items``); the default says nothing, so the group is
        judged from its findings files alone.

    Returns
    -------
    dict
        A group object conforming to the milestone-state output contract::

            {
              "group_id": str,
              "state": "pending|code_converged|blocked|deferred|wont_do",
              "implementation_converged_at": str | None,
              "reviewer_rounds": int,
              "findings_resolved_path": str | None,
              "blocking_amb_ids": list[str],
            }
    """
    group_id: str = group["id"]
    findings = _probe_findings(findings_dir, group_id)
    blocking_amb_ids = _blocking_ids(ambiguities, item_view.chain)
    converged = findings.resolved_path is not None

    # --- State derivation (precedence: deferred/wont_do > blocked > code_converged > pending) --
    if item_view.set_aside is not None:
        state = item_view.set_aside
    elif converged and blocking_amb_ids:
        state = "blocked"
    elif converged:
        state = "code_converged"
    else:
        state = "pending"

    return {
        "group_id": group_id,
        "state": state,
        "implementation_converged_at": findings.converged_at,
        "reviewer_rounds": findings.reviewer_rounds,
        "findings_resolved_path": findings.resolved_path,
        "blocking_amb_ids": blocking_amb_ids,
    }


@dataclass(frozen=True)
class _Findings:
    """What the findings files of one group say: the latest empty (converging) file, its mtime and the per-reviewer file count."""

    resolved_path: str | None
    converged_at: str | None
    reviewer_rounds: int


def _probe_findings(findings_dir: str, group_id: str) -> _Findings:
    """Probe ``findings_<group_id>_*`` under *findings_dir*.

    Three findings-file shapes exist for a group:
      per-reviewer:   findings_<group_id>_<N>_r<M>.json   (and _rr<M> double-r variant)
      round-output:   findings_<group_id>_<N>.json         (convergence signal when findings==[])
      halt-archive:   findings_<group_id>_<N>_<unix_ts>.json
    Halt-archive files are intentionally excluded — per SKILL.md they are NOT promoted to a canonical convergence
    name and must not be treated as convergence signals.
    """
    all_group_files: list[str] = _glob.glob(os.path.join(findings_dir, f"findings_{group_id}_*"))
    per_reviewer_files = [f for f in all_group_files if _is_per_reviewer_file(os.path.basename(f), group_id)]
    round_output_files = [f for f in all_group_files if _is_round_output_file(os.path.basename(f), group_id)]
    resolved_path = _latest_empty_findings(round_output_files + per_reviewer_files)
    converged_at = _mtime_to_iso(resolved_path) if resolved_path else None
    return _Findings(resolved_path, converged_at, len(per_reviewer_files))


def _blocking_ids(ambiguities: list[dict], chain: frozenset[str]) -> list[str]:
    """The ids of the open items whose ``about`` names a node of *chain*, in listing order.

    An open item has no status or resolved flag, so every item counts; one that is not an object, or has no string
    ``id``, is skipped.
    """
    return [
        amb["id"]
        for amb in dict_items(ambiguities)
        if isinstance(amb.get("id"), str) and chain.intersection(str_items(amb.get("about")))
    ]


def _is_per_reviewer_file(basename: str, group_id: str) -> bool:
    """Return True iff *basename* is a per-reviewer findings file.

    Matches ``findings_<group_id>_<N>_r<reviewer_id>.json`` and
    ``findings_<group_id>_<N>_rr<reviewer_id>.json`` (double-r variant).
    The last underscore-separated token must be ``r<digits>`` or ``rr<digits>``.
    Fixer files (``_fixer-discovered``) are explicitly excluded.
    """
    prefix = f"findings_{group_id}_"
    if not basename.startswith(prefix):
        return False
    if not basename.endswith(".json"):
        return False
    if "fixer" in basename:
        return False
    middle = basename[len(prefix):-len(".json")]
    # last segment after final underscore
    last = middle.rsplit("_", 1)[-1] if "_" in middle else ""
    if last.startswith("rr") and last[2:].isdigit():
        return True
    if last.startswith("r") and last[1:].isdigit():
        return True
    return False


def _is_round_output_file(basename: str, group_id: str) -> bool:
    """Return True iff *basename* is a round-output (non-reviewer) findings file.

    Round-output files follow ``findings_<group_id>_<N>.json`` where the only
    part after the prefix is a plain decimal integer.  Files with ``_rN``,
    ``_rrN``, or ``fixer`` suffixes are per-reviewer or fixer outputs and are
    excluded.
    """
    prefix = f"findings_{group_id}_"
    if not basename.startswith(prefix):
        return False
    if not basename.endswith(".json"):
        return False
    middle = basename[len(prefix):-len(".json")]
    return middle.isdigit()


# ---------------------------------------------------------------------------
# Roll-up
# ---------------------------------------------------------------------------

# States that represent meaningful forward progress (used in impl_in_progress)
_PROGRESS_STATES = frozenset({"executing", "code_converged"})
# States considered "implementation-advanced" (beyond pending)
_ADVANCED_STATES = frozenset({"code_converged", "blocked"})


def derive_phase_position(
    groups: list[dict],
    findings_dir: str,
    batch_id: str,
    closed: bool = False,
) -> str:
    """Compute ``derived_phase_position`` from per-group state objects.

    Parameters
    ----------
    groups:
        List of group state objects (output of :func:`derive_group_state`).
    findings_dir:
        Absolute path to the ``.specdev/findings/`` directory.
    batch_id:
        The milestone batch identifier (used to glob milestone-review files).
    closed:
        Whether the anchor row of the milestone is ``done`` (``SpecView.closed``); it decides ``closed`` alone.

    Returns
    -------
    str
        One of ``pending``, ``impl_in_progress``, ``impl_complete``,
        ``review_pending``, ``review_complete``, ``operator_pending``, ``closed``.
    """
    if closed:
        return "closed"

    # "active" excludes both deferred (paused) and wont_do (permanently
    # cancelled) groups from every progress computation below -- neither is
    # part of the work currently being tracked (DEVSPEC-122 follow-up).
    active_groups = [g for g in groups if g["state"] not in ("deferred", "wont_do")]

    # All-deferred/wont_do → treat as pending (nothing to track)
    if not active_groups:
        return "pending"

    # --- Milestone-review files
    review_glob = os.path.join(
        findings_dir,
        f"findings_{batch_id}_review_*",
    )
    review_files = _glob.glob(review_glob)
    has_any_review_file = bool(review_files)
    has_review_empty = any(_is_empty_findings(f) for f in review_files)

    # --- operator_pending requires review_complete first
    all_advanced = all(g["state"] in _ADVANCED_STATES for g in active_groups)

    if all_advanced and has_review_empty:
        # review_complete condition met — check operator_pending
        has_blocked = any(g["state"] == "blocked" for g in active_groups)
        has_open_blocking_item = any(g["blocking_amb_ids"] for g in active_groups)
        if has_blocked or has_open_blocking_item:
            return "operator_pending"
        return "review_complete"

    if all_advanced and has_any_review_file and not has_review_empty:
        # All advanced, review files exist but none empty → review_pending
        return "review_pending"

    if all_advanced and not has_any_review_file:
        # All advanced, no review file at all → impl_complete
        return "impl_complete"

    # --- impl_in_progress: ≥1 progress, ≥1 pending
    has_progress = any(g["state"] in _PROGRESS_STATES for g in active_groups)
    has_pending = any(g["state"] == "pending" for g in active_groups)
    if has_progress and has_pending:
        return "impl_in_progress"

    # --- pending: every active group is pending
    if all(g["state"] == "pending" for g in active_groups):
        return "pending"

    # Fallback: covers transient executing-bearing cases not captured by the named predicates
    # (e.g. executing alone, executing+blocked without pending).  executing is never persisted
    # in plan files, so this path is not expected to appear in steady-state.
    return "impl_in_progress"


# ---------------------------------------------------------------------------
# The spec-side view
# ---------------------------------------------------------------------------

def load_spec_view(plan: dict, spec_root: str, repo_root: str) -> SpecView:
    """The ``SpecView`` of the milestone *plan* names: its anchor row's closedness and the graph facts of each plan item.

    Reads the anchor row through ``anchor_store.read_row`` (an unreadable status reads as not closed) and builds the
    spec graph once, as ``spec-check`` does.  When the graph cannot be built (a host that is not migrated) the items
    are empty, so no group is deferred, wont_do or blocked.  Never raises.

    Parameters
    ----------
    plan:
        The parsed ``ms_<batch_id>_plan.json`` document.
    spec_root:
        The spec folder (the anchor file and the graph are read from it).
    repo_root:
        The toolkit root (the graph's registry).
    """
    milestone = plan.get(MILESTONE_KEY)
    closed = False
    if isinstance(milestone, str):
        try:
            row = read_row(spec_root, milestone)
        except FindingError:
            row = None
        closed = row is not None and row.status == DONE_STATUS
    try:
        graph = build_graph(spec_root, repo_root)
    except KindRegistryError:
        return SpecView(closed=closed)
    items = {item["id"]: _item_view(graph, item) for item in _checklist(plan)}
    return SpecView(closed=closed, items=items)


def _item_view(graph: Graph, item: dict) -> ItemView:
    """The ``ItemView`` of one plan item: ``set_aside`` from the dispositions of its criteria's tasks, ``chain`` from the graph."""
    criteria = str_items(item.get("realises"))
    dispositions = [_disposition(graph, criterion) for criterion in criteria]
    set_aside = None
    if criteria and all(value is not None for value in dispositions):
        set_aside = _WONT_DO if all(value == _WONT_DO for value in dispositions) else _DEFERRED
    return ItemView(set_aside=set_aside, chain=_chain(graph, item["id"]))


def _disposition(graph: Graph, criterion_id: str) -> str | None:
    """The set-aside ``disposition.value`` (``deferred`` or ``wont_do``) of the task that holds *criterion_id*; ``None`` for any other case."""
    task = task_of(graph, criterion_id)
    content = item_of(graph, task) if task is not None else None
    value = as_dict(content.get("disposition")).get("value") if content is not None else None
    return value if value in PAUSED_DISPOSITIONS else None


def _chain(graph: Graph, item_id: str) -> frozenset[str]:
    """The item's own id and the ids (and older ids) of the nodes it reaches through ``realises``, ``refines`` and ``verified_by``; containment is not followed."""
    if graph.find(item_id) is None:
        return frozenset({item_id})
    options = TraceOptions(verbs=_CHAIN_VERBS, containment=False)
    side = trace_node(graph, item_id, ("up",), options).up
    reached = (*side.nodes, *side.records) if side is not None else ()
    return frozenset({item_id, *(name for node in reached for name in (node.id, *node.aliases))})


# ---------------------------------------------------------------------------
# Top-level compute
# ---------------------------------------------------------------------------

def _checklist(plan: dict) -> list[dict]:
    """The plan items of *plan* that carry a string ``id``; a wrong-typed level reads as absent."""
    return [
        item for item in dict_items(as_dict(as_dict(plan.get("plan")).get("spec_alignment")).get("checklist"))
        if isinstance(item.get("id"), str)
    ]


def _blockers(groups: list[dict]) -> list[dict]:
    """One advisory blocker per open item that blocks a group, in group order; an item that blocks two groups is listed once."""
    blockers: dict[str, dict] = {}
    for group in groups:
        for amb_id in group["blocking_amb_ids"]:
            blockers.setdefault(amb_id, {
                "kind": "ambiguity",
                "id": amb_id,
                "issue": f"open ambiguity about a node of group {group['group_id']}",
            })
    return list(blockers.values())


def compute_milestone_state(
    plan: dict,
    findings_dir: str,
    batch_id: str,
    view: SpecView = SpecView(),
) -> dict:
    """Compute the full milestone-state output contract object.

    Parameters
    ----------
    plan:
        The parsed ``ms_<batch_id>_plan.json`` document.
    findings_dir:
        Absolute path to the ``.specdev/findings/`` directory.
    batch_id:
        The milestone batch identifier (e.g. ``"phase2_newsletter_send"``).
    view:
        The spec-side inputs (``load_spec_view``); the default says nothing.

    Returns
    -------
    dict
        Full output contract object::

            {
              "milestone_id": str,
              "milestone": str | None,
              "groups": list[dict],
              "derived_phase_position": str,
              "blockers": list[dict],
            }

        ``milestone_id`` echoes *batch_id*; ``milestone`` is the plan's file-level ``milestone`` key (the id that
        ``milestone start|close`` and ``status --milestone`` take), ``None`` when the plan has none.

    Notes
    -----
    **``blockers[]`` is advisory — do NOT gate on its emptiness.**  Downstream consumers MUST gate on
    ``derived_phase_position``: an open item about a node of a group is listed in ``blockers[]`` also when the
    milestone is ``closed``, for visibility, not as a gate.
    """
    milestone = plan.get(MILESTONE_KEY)
    ambiguities: list[dict] = [
        *as_list(as_dict(plan.get("plan")).get("ambiguities")),
        *as_list(as_dict(plan.get("execution")).get("emergent_ambiguities")),
    ]
    group_states: list[dict] = [
        derive_group_state(item, findings_dir, ambiguities, view.items.get(item["id"], ItemView()))
        for item in _checklist(plan)
    ]
    phase_position = derive_phase_position(group_states, findings_dir, batch_id, view.closed)

    blockers = _blockers(group_states)

    return {
        "milestone_id": batch_id,
        "milestone": milestone if isinstance(milestone, str) else None,
        "groups": group_states,
        "derived_phase_position": phase_position,
        "blockers": blockers,
    }
