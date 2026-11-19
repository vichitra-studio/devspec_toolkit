"""Upstream-backlog rollup: every open ambiguity item of a spec folder, grouped by the step it is about.

The items come from ``core.ambiguity_items`` (step files 00-15, the anchor, and the ``plan.ambiguities`` and
``execution.emergent_ambiguities`` arrays of the milestone plans).  An item is placed by what it is ``about``: each
target is resolved on the spec graph and the item goes to the group of that node's step (``seed`` for a seed, the step
of the missing kind for a silent-spec item).  An item whose ``about`` nodes span several steps appears in each group
and counts once.  A legacy-shape item (no ``about``) goes to the earliest step named in its ``impact[]``.  An item
that cannot be placed goes to ``unplaced``.

Read-only reporter.  Four layers with one-way deps:
  Loader     -> ``iter_ambiguity_items`` (FS) + per-item E520 checks
  Classifier -> ``place``: item + graph -> ``Placement`` (groups, about steps)
  Filter     -> ``filter_records``: records + severity/status thresholds -> records (legacy items only)
  Render     -> ``render_plain`` / ``render_json``: records -> str

``run()`` returns a ``BacklogReport`` (``stdout``, ``stderr_lines``, ``exit_code``) with no side effects, so CLI dispatch
owns all I/O.  The exit code is 2 when ``load_items`` returned a problem (or a file, array or folder could not be read),
else 0; it is never read back from the text of a line.
W613 stderr lines are formatted manually (not via ``SpecError.render()``) because the spec requires the format
``W613 UPSTREAM_BACKLOG_UNCLASSIFIED <target>`` while ``render()`` places the path between code and message.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any, Literal, NamedTuple

from ..core.ambiguity_items import (
    AmbiguityItem,
    AmbiguityReadError,
    SilentTarget,
    about_targets,
    is_open,
    iter_ambiguity_items,
)
from ..core.errors import ERROR_CODES, FindingError
from ..graph.build import build_graph
from ..graph.model import Graph
from ..graph.kinds import SEED_STEP

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# plan.ambiguities[] (16a) uses a binary blocking/non_blocking severity scale; it is mapped onto the shared rank so
# --severity filtering treats both origins alike.  The raw authored value is kept verbatim on the record.
PLAN_SEVERITY_RANK = {
    "blocking": SEVERITY_ORDER["critical"],
    "non_blocking": SEVERITY_ORDER["low"],
}

PLAN_STEP = "16a"
UNPLACED = "unplaced"
MATCHED_RULE_PLACED = 1
MATCHED_RULE_UNPLACED = 4
SEVERITY_FIELD = "severity"
STATUS_FIELD = "status"
IMPACT_FIELD = "impact"
StatusFilter = Literal["open", "resolved", "all"]
JSON_SCHEMA_VERSION = "2"
SPEC_PREFIX = "spec/"
ANSWER_KNOWN = "answer known"
NEEDS_ANSWER = "needs operator answer"

_IMPACT_STEP_RE = re.compile(r"^spec/([0-9]{2}[a-z]?)_[a-z0-9_]+\.json(?::.+)?$")


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

class Placement(NamedTuple):
    """Where one item goes: its groups in group order, the steps of its ``about`` nodes and the derived pointers."""

    groups: tuple[str, ...]
    about_steps: tuple[str, ...]
    impact: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class Record:
    """One item with its placement; ``group`` and ``also_in`` are set per occurrence by ``expand``."""

    item: AmbiguityItem
    rel_artifact: str
    placement: Placement
    group: str = ""
    also_in: tuple[str, ...] = ()

    @property
    def legacy(self) -> bool:
        return self.item.shape == "legacy"

    @property
    def item_id(self) -> str:
        return self.item.id

    @property
    def description(self) -> str:
        return self.item.description

    @property
    def decision(self) -> str:
        return self.item.decision or ""

    @property
    def about(self) -> list[str]:
        return list(self.item.about_ids)

    @property
    def severity(self) -> str | None:
        return legacy_fields(self.item).severity

    @property
    def status(self) -> str | None:
        return legacy_fields(self.item).status if self.legacy else None

    @property
    def impact_raw(self) -> list[Any]:
        return legacy_fields(self.item).impact


class LegacyFields(NamedTuple):
    """The fields only a 1.1.1 item carries (``severity``, ``status``, ``impact``); each is ``None`` / empty when absent or mistyped."""

    severity: str | None
    status: str | None
    impact: list[Any]


def legacy_fields(item: AmbiguityItem) -> LegacyFields:
    """The one place the legacy-only fields of an item are read from its raw object."""
    severity = item.raw.get(SEVERITY_FIELD)
    status = item.raw.get(STATUS_FIELD)
    impact = item.raw.get(IMPACT_FIELD)
    return LegacyFields(
        severity if isinstance(severity, str) else None,
        status if isinstance(status, str) else None,
        impact if isinstance(impact, list) else [],
    )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _valid_severities(step: str) -> frozenset[str]:
    return frozenset(PLAN_SEVERITY_RANK) if step == PLAN_STEP else frozenset(SEVERITY_ORDER)


class ItemProblem(NamedTuple):
    """An item that cannot be reported: where it is and why (``reason`` is the text after ``E520 UNRESOLVED_INPUT``)."""

    path: str
    step: str
    item_id: str
    reason: str

    def line(self) -> str:
        """The stderr line of this problem."""
        return _e520_line(f"{self.reason} in {self.path} (step={self.step}, item={self.item_id or '?'})")


def item_problem(item: AmbiguityItem) -> str | None:
    """The E520 reason for an item that cannot be reported (no id; a legacy severity outside its scale), else ``None``."""
    if not item.id:
        return "missing_id"
    if item.shape == "legacy":
        severity = legacy_fields(item).severity
        if severity is None and SEVERITY_FIELD not in item.raw:
            return "item has neither about nor a valid severity"
        if severity not in _valid_severities(item.step):
            return f"invalid_severity={item.raw.get(SEVERITY_FIELD)!r}"
    return None


def _e520_line(detail: str) -> str:
    return f"E520 {ERROR_CODES['E520']} {detail}"


def load_items(spec_dir: str) -> tuple[list[AmbiguityItem], list[ItemProblem]]:
    """Every readable item of *spec_dir* and one problem per item that cannot be reported.

    Raises:
        AmbiguityReadError: a file is not readable JSON or an array is malformed (the caller reports it, exit 2).
    """
    items: list[AmbiguityItem] = []
    problems: list[ItemProblem] = []
    for item in iter_ambiguity_items(spec_dir):
        reason = item_problem(item)
        if reason is None:
            items.append(item)
        else:
            problems.append(ItemProblem(item.artifact_path, item.step, item.id, reason))
    return items, problems


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def _target_steps(target: str | SilentTarget, graph: Graph) -> list[str]:
    """Steps a target resolves to: the step of the node or seed, or every step that declares the missing kind."""
    if isinstance(target, SilentTarget):
        return list(graph.shape.kind_steps.get(target.missing_kind, ()))
    node = graph.find(target)
    return [node.step] if node is not None and node.step is not None else []


def _pointers(graph: Graph, ids: list[str]) -> tuple[dict[str, str], ...]:
    """``{file, id}`` pointers for the nodes *ids* name, in order, without repeats; seeds are not JSON and are skipped."""
    out: dict[str, dict[str, str]] = {}
    for node_id in ids:
        node = graph.find(node_id)
        if node is not None and node.step != SEED_STEP:
            out.setdefault(node.id, {"file": f"{SPEC_PREFIX}{node.file}", "id": node.id})
    return tuple(out.values())


def _ordered(steps: set[str], graph: Graph) -> tuple[str, ...]:
    return tuple(sorted(steps, key=graph.shape.step_key))


def _earliest_impact_step(impact: list[Any], graph: Graph) -> str | None:
    """The earliest step (in graph order) named by a ``spec/NN_*.json`` entry of *impact*, ``None`` when none is."""
    steps = {m.group(1) for e in impact if isinstance(e, str) and (m := _IMPACT_STEP_RE.match(e))}
    return min(steps, key=graph.shape.step_key) if steps else None


def place(item: AmbiguityItem, graph: Graph) -> Placement:
    """Where *item* goes.

    Each ``about`` target (``about_targets``) that resolves gives its step; targets that do not resolve are ignored
    and an item with none resolved goes to ``unplaced``.  A legacy item without ``about`` goes to the earliest step
    its ``impact[]`` names, else ``unplaced``.
    """
    targets = about_targets(item)
    steps = {step for target in targets for step in _target_steps(target, graph)}
    if steps:
        return Placement(_ordered(steps, graph), _ordered(steps, graph), _pointers(graph, list(item.about_ids)))
    if item.shape == "legacy" and not targets:
        step = _earliest_impact_step(legacy_fields(item).impact, graph)
        if step is not None:
            return Placement((step,), (), ())
    return Placement((UNPLACED,), (), ())


def group_key(group: str, graph: Graph) -> tuple[bool, tuple[int, str]]:
    """Sort key of a group: ``seed``, then steps in graph (DAG) order, then ``unplaced``."""
    return group == UNPLACED, graph.shape.step_key(group)


def expand(record: Record) -> list[Record]:
    """One occurrence of *record* per group; the second and later ones carry the other groups in ``also_in``."""
    groups = record.placement.groups
    return [
        Record(record.item, record.rel_artifact, record.placement, group,
               tuple(g for g in groups if g != group) if index else ())
        for index, group in enumerate(groups)
    ]


# ---------------------------------------------------------------------------
# Filter (pure)
# ---------------------------------------------------------------------------

def severity_rank(record: Record) -> int:
    """Shared 0-3 rank of a legacy record's severity; a unified item has none and ranks as ``critical``."""
    severity = record.severity
    if severity is None:
        return SEVERITY_ORDER["critical"]
    if record.item.step == PLAN_STEP:
        return PLAN_SEVERITY_RANK[severity]
    return SEVERITY_ORDER[severity]


def filter_records(records: list[Record], severity_min: str, status_filter: StatusFilter) -> list[Record]:
    """Apply ``--severity`` and ``--status`` to the legacy records; a unified record has neither and always passes."""
    min_rank = SEVERITY_ORDER[severity_min]
    out: list[Record] = []
    for r in records:
        if not r.legacy:
            out.append(r)
            continue
        resolved = not is_open(r.item)
        if severity_rank(r) < min_rank:
            continue
        if (status_filter == "open" and resolved) or (status_filter == "resolved" and not resolved):
            continue
        out.append(r)
    return out


def _sort_key(record: Record, graph: Graph) -> tuple[Any, ...]:
    return (group_key(record.group, graph), -severity_rank(record), record.rel_artifact, record.item_id)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Summary:
    """Counts over the items shown, each item once however many groups it appears in."""

    items: int
    with_answer: int
    needing_answer: int
    unplaced: int = 0
    hidden_by_status: int = 0
    warnings: tuple[dict[str, str], ...] = ()


def summarise(records: list[Record], *, hidden_by_status: int = 0, warnings: Sequence[dict[str, str]] = ()) -> Summary:
    """Count the distinct items of *records* (an item is its artifact plus its id) by answer state."""
    distinct = {(r.item.artifact_path, r.item.location, r.item_id): r for r in records}
    with_answer = sum(1 for r in distinct.values() if r.decision)
    unplaced = sum(1 for r in distinct.values() if UNPLACED in r.placement.groups)
    return Summary(len(distinct), with_answer, len(distinct) - with_answer, unplaced, hidden_by_status, tuple(warnings))


def _answer_state(record: Record) -> str:
    return ANSWER_KNOWN if record.decision else NEEDS_ANSWER


def _first_line(text: str) -> str:
    return text.split("\n", 1)[0].strip()


def _record_lines(record: Record) -> list[str]:
    marks = []
    if record.also_in:
        marks.append(f"also in {', '.join(record.also_in)}")
    if record.legacy:
        marks.append("legacy")
    mark = f" ({'; '.join(marks)})" if marks else ""
    lines = [f"  {record.rel_artifact} / {record.item_id} - {_answer_state(record)}{mark}"]
    if description := _first_line(record.description):
        lines.append(f"    {description}")
    if record.about:
        lines.append(f"    about: {' | '.join(record.about)}")
    return lines


def render_plain(records: list[Record], summary: Summary, graph: Graph) -> str:
    """Plain-text report: one section per group in group order, then the totals line."""
    groups: dict[str, list[Record]] = {}
    for r in records:
        groups.setdefault(r.group, []).append(r)
    sections = []
    for group in sorted(groups, key=lambda g: group_key(g, graph)):
        header = f"{group} - {len(groups[group])} item(s)"
        if group == UNPLACED and summary.warnings:
            header += f"  [{len(summary.warnings)} x W613 - see stderr]"
        sections.append("\n".join([header, *(line for r in groups[group] for line in _record_lines(r))]))
    noun = "item" if summary.items == 1 else "items"
    totals = f"Totals: {summary.items} {noun} / {summary.with_answer} with answer / {summary.needing_answer} needing answer."
    return "\n\n".join([*sections, totals])


def _json_record(record: Record) -> dict[str, Any]:
    """JSON form of one occurrence.  ``impact`` is the raw list for a legacy item and derived pointers for a unified one."""
    out: dict[str, Any] = {
        "group": record.group,
        "also_in": list(record.also_in),
        "artifact": record.rel_artifact,
        "step": record.item.step,
        "item_id": record.item_id,
        "about": record.about,
        "about_steps": list(record.placement.about_steps),
        "decision": record.decision,
        "shape": record.item.shape,
        "description": record.description,
        "impact": record.impact_raw if record.legacy else list(record.placement.impact),
    }
    if record.legacy:
        out.update(severity=record.severity, status=record.status, bucket=_legacy_bucket(record),
                   matched_rule=MATCHED_RULE_UNPLACED if record.group == UNPLACED else MATCHED_RULE_PLACED)
    return out


def _legacy_bucket(record: Record) -> str:
    """The v1 ``bucket`` label of a legacy record: ``step_NN``, or ``unclassified`` when it is unplaced."""
    return "unclassified" if record.group == UNPLACED else f"step_{record.group}"


def render_json(records: list[Record], summary: Summary) -> str:
    """JSON report (``schema_version`` 2): ``summary``, one ``records`` entry per group occurrence, ``warnings``."""
    payload = {
        "schema_version": JSON_SCHEMA_VERSION,
        "summary": {
            "items": summary.items,
            "with_answer": summary.with_answer,
            "needing_answer": summary.needing_answer,
            "unplaced_count": summary.unplaced,
            "hidden_by_status_count": summary.hidden_by_status,
        },
        "records": [_json_record(r) for r in records],
        "warnings": list(summary.warnings),
    }
    return json.dumps(payload, indent=2, sort_keys=False)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _records_of(items: list[AmbiguityItem], graph: Graph, spec_dir: str) -> list[Record]:
    """Every occurrence of every item, one per group."""
    out: list[Record] = []
    for item in items:
        rel = os.path.relpath(item.artifact_path, spec_dir)
        out.extend(expand(Record(item, rel, place(item, graph))))
    return out


def _hidden_by_status(records: list[Record], shown: list[Record], severity: str) -> int:
    """Items the status filter hid: legacy items that pass ``--severity`` but are not shown."""
    min_rank = SEVERITY_ORDER[severity]
    shown_keys = {(r.item.artifact_path, r.item.location, r.item_id) for r in shown}
    hidden = {
        (r.item.artifact_path, r.item.location, r.item_id)
        for r in records
        if r.legacy and severity_rank(r) >= min_rank
    }
    return len(hidden - shown_keys)


class BacklogReport(NamedTuple):
    """What ``run`` gives the CLI: the text for stdout, the lines for stderr in order, the exit code."""

    stdout: str
    stderr_lines: list[str]
    exit_code: int


EXIT_PROBLEM = 2


def run(
    spec_dir: str,
    *,
    repo_root: str = ".",
    severity: str = "low",
    status: StatusFilter = "open",
    json_output: bool = False,
) -> BacklogReport:
    """The backlog of *spec_dir* as a ``BacklogReport``.

    ``repo_root`` is the toolkit root (kind registry and step order for the graph).  Exit 2 when a file or array
    cannot be read (a file that is not readable JSON, a permission error, a folder named like a step file), an item
    has no id or a legacy item has an invalid severity (E520, one line per item; the run goes on), the spec folder
    does not exist (E520), or the toolkit has no registry.
    """
    if not os.path.isdir(spec_dir):
        return BacklogReport("", [_e520_line(f"missing_spec_dir {spec_dir}")], EXIT_PROBLEM)
    try:
        items, problems = load_items(spec_dir)
    except AmbiguityReadError as exc:
        return BacklogReport("", [_e520_line(f"{exc.path}: {exc.reason}")], EXIT_PROBLEM)
    stderr_lines = [problem.line() for problem in problems]
    try:
        graph = build_graph(spec_dir, repo_root)
    except FindingError as exc:
        return BacklogReport("", [exc.error.render()], EXIT_PROBLEM)

    records = _records_of(items, graph, spec_dir)
    shown = filter_records(records, severity, status)
    shown.sort(key=lambda r: _sort_key(r, graph))

    hidden = _hidden_by_status(records, shown, severity)
    if hidden > 0:
        stderr_lines.append(
            f"W617 {ERROR_CODES['W617']} {hidden} record(s) hidden by --status {status} (pass --status all to include)"
        )
    warnings = []
    for r in shown:
        if r.group == UNPLACED:
            target = f"{r.rel_artifact}:{r.item_id}"
            warnings.append({"code": "W613", "target": target})
            stderr_lines.append(f"W613 {ERROR_CODES['W613']} {target}")

    summary = summarise(shown, hidden_by_status=hidden, warnings=warnings)
    stdout = render_json(shown, summary) if json_output else render_plain(shown, summary, graph)
    return BacklogReport(stdout, stderr_lines, EXIT_PROBLEM if problems else 0)
