"""P1: copy what a later script removes and a person or a proposer still needs into ``spec/extras/migration/capture.json``.

The mechanical scripts of the migration may delete content because this one runs first: it records the values that the
migrated tree can no longer give (statuses that the close step compares, ``tech_stack`` entries, the rules of step 10,
``exit_conditions``, the ``linked_test_expectation`` of plan items, open ambiguity items, ...) grouped by the work that
reads them, plus the source commit so that everything else is one ``git show`` away.  It also creates an empty
``worklist.json`` for the scripts that follow (``migration/worklist.py``).

Layout of ``capture.json`` (schema ``schema/infra/migration_capture.schema.json``): ``source`` (commit, spec folder, the
``git show`` form, the sha256 of every spec file before the run) and one list or object per reader.  Every value copied
from a 1.1.1 file sits under a key that starts with ``legacy_``; the other keys are the capture's own.  Order and values
come from the spec files and git only (no clock, no absolute path), so a copy of the host gives the same bytes.

``detect`` is 0 as soon as ``capture.json`` exists, whatever the tree holds then: the mechanical commit moves HEAD and
the tree no longer has the old values, so a later run must never capture again.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable, Iterator
from typing import Any

from specdev_tools.core.ambiguity_items import ANCHOR_STEP, is_open, iter_ambiguity_items
from specdev_tools.migration.context import CAPTURE_FILE, CAPTURE_REL, MigrationContext, Snapshot
from specdev_tools.migration.registry import PHASE_CAPTURE, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import LEGACY, anchor_rows, plan_rels, step_data
from specdev_tools.migration.worklist import WORKLIST_FILE, new_worklist_data

SCRIPT = ScriptSpec("p1_capture", PHASE_CAPTURE, touches=("extras",))

CAPTURE_SCHEMA = "vc:infra:migration-capture"
_OWN_FILES = frozenset({CAPTURE_REL, WORKLIST_FILE.replace(os.sep, "/")})
_MIGRATION_DIR = os.path.dirname(CAPTURE_FILE).replace(os.sep, "/") + "/"
_OPEN_ITEM_STEPS = frozenset({ANCHOR_STEP, "16a", "16b"})
_ITEM_FIELDS = ("linked_test_expectation", "fixture_ref", "checklist_status", "deferred_reason", "wont_do_reason")
_GOVERNANCE_KEYS = ("pr_rules", "review_policy", "reviewers", "spec_first_policy", "policy_ref", "command_ref")
_LINK_KEYS = ("source_milestones", "deliverables", "fr_refs", "capability_refs")
_COMPONENT_DROPPED = "trace"


def _legacy(source: dict[str, Any], names: Iterable[str]) -> dict[str, Any]:
    """The values of *source* under *names*, each under ``legacy_<name>``; a name *source* does not have is left out."""
    return {LEGACY + name: source[name] for name in names if name in source}


def _objects(value: Any) -> Iterator[dict[str, Any]]:
    """The objects of *value* when it is a list (anything else, and any entry that is not an object, gives nothing)."""
    if isinstance(value, list):
        yield from (entry for entry in value if isinstance(entry, dict))


def _entries(value: Any) -> list[Any]:
    """*value* when it is a list, else an empty list."""
    return value if isinstance(value, list) else []


def _get(source: Any, *path: str) -> Any:
    """The value at the key path in nested objects, ``None`` when a step is missing or not an object."""
    for key in path:
        if not isinstance(source, dict):
            return None
        source = source.get(key)
    return source


class _Reader:
    """The step files and plans of the spec folder, read once through the context's ``DocumentSet``."""

    def __init__(self, ctx: MigrationContext) -> None:
        self.ctx = ctx

    def step(self, step: str) -> dict[str, Any]:
        """The data of the file of *step* (``{}`` when the host has none)."""
        return step_data(self.ctx, step)

    def milestones(self, step: str) -> Iterator[dict[str, Any]]:
        """The ``milestones[]`` objects of *step* that have a ``milestone_id``."""
        return (m for m in _objects(self.step(step).get("milestones")) if isinstance(m.get("milestone_id"), str))

    def anchor_rows(self) -> Iterator[dict[str, Any]]:
        """The ``plan.milestone_index[]`` objects of the anchor that have a ``milestone_id``."""
        return (row for row in anchor_rows(self.ctx) if isinstance(row.get("milestone_id"), str))

    def plans(self) -> Iterator[tuple[str, dict[str, Any]]]:
        """Each plan file as ``(path relative to the spec folder, its data)``, in name order."""
        for rel in plan_rels(self.ctx):
            data = self.ctx.documents.load(rel).data
            yield rel, data if isinstance(data, dict) else {}


def _source(ctx: MigrationContext) -> dict[str, Any]:
    """The header: the commit the migration starts from, how to read an old file, and the digest of every file now."""
    commit = ctx.git("rev-parse", "HEAD").strip()
    spec_dir = os.path.relpath(ctx.spec_root, ctx.host_root).replace(os.sep, "/")
    hashes: dict[str, str] = {}
    for folder, _dirs, names in os.walk(ctx.spec_root):
        for name in names:
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, ctx.spec_root).replace(os.sep, "/")
            if not rel.startswith(_MIGRATION_DIR):
                with open(path, "rb") as handle:
                    hashes[rel] = hashlib.sha256(handle.read()).hexdigest()
    return {
        "commit": commit,
        "spec_dir": spec_dir,
        "show_form": f"git show {commit}:{spec_dir}/<file>",
        "file_hashes": dict(sorted(hashes.items())),
    }


def _milestone_status(reader: _Reader) -> dict[str, Any]:
    """Status per source: step 14, step 09, the anchor rows, and for each plan its review verdict and ``plan.status``."""
    plans = [
        {
            "file": rel,
            "review_verdict": _get(data, "review", "verdict"),
            "legacy_plan_status": _get(data, "plan", "status"),
            **({"legacy_plan_deferred_reason": reason} if isinstance(reason := _get(data, "plan", "deferred_reason"), str) else {}),
        }
        for rel, data in reader.plans()
    ]
    return {
        "roadmap": [
            {"milestone": m["milestone_id"], **_legacy(m, ("status", "milestone_status_reason"))} for m in reader.milestones("14")
        ],
        "impl_plan": [{"milestone": m["milestone_id"], **_legacy(m, ("status",))} for m in reader.milestones("09")],
        "anchor": [{"milestone": row["milestone_id"], **_legacy(row, ("status",))} for row in reader.anchor_rows()],
        "plans": plans,
    }


def _tasks(reader: _Reader) -> Iterator[tuple[str, dict[str, Any]]]:
    """Each task of the roadmap as ``(its milestone id, the task object)``."""
    for milestone in reader.milestones("14"):
        for task in _objects(milestone.get("tasks")):
            if isinstance(task.get("task_id"), str):
                yield milestone["milestone_id"], task


def _task_status(reader: _Reader) -> list[dict[str, Any]]:
    return [
        {
            "milestone": milestone,
            "task": task["task_id"],
            **_legacy(task, ("status", "status_reason", "fr_refs", "invariant_refs")),
        }
        for milestone, task in _tasks(reader)
    ]


def _task_lists(reader: _Reader, name: str) -> list[dict[str, Any]]:
    """The tasks that hold a non-empty list under *name* (``exit_conditions``, ``assumptions``)."""
    return [
        {"milestone": milestone, "task": task["task_id"], LEGACY + name: task[name]}
        for milestone, task in _tasks(reader)
        if isinstance(task.get(name), list) and task[name]
    ]


def _third_party(reader: _Reader) -> dict[str, Any]:
    """The ``tech_stack`` of steps 02, 09 and 14 and the external components of step 02 (without their ``trace``)."""
    stacks = [
        {"step": step, **_legacy(reader.step(step), ("tech_stack",))}
        for step in ("02", "09", "14")
        if "tech_stack" in reader.step(step)
    ]
    components = [
        {
            "component": component.get("component_id"),
            "legacy_component": {k: v for k, v in component.items() if k != _COMPONENT_DROPPED},
        }
        for component in _objects(reader.step("02").get("components"))
        if component.get("type") == "external"
    ]
    return {"tech_stacks": stacks, "external_components": components}


def _governance(reader: _Reader) -> dict[str, Any]:
    return _legacy(reader.step("10"), _GOVERNANCE_KEYS)


def _plan_security(reader: _Reader) -> list[dict[str, Any]]:
    rows = []
    for rel, data in reader.plans():
        security = _legacy(_get(data, "plan", "security") or {}, ("spec_mutations", "new_fixtures"))
        if any(security.values()):
            rows.append({"file": rel, **security})
    return rows


def _plan_items(reader: _Reader) -> list[dict[str, Any]]:
    """The checklist items of every plan that carry one of the fields a later step removes, by item id."""
    rows = []
    for rel, data in reader.plans():
        for item in _objects(_get(data, "plan", "spec_alignment", "checklist")):
            copied = _legacy(item, _ITEM_FIELDS)
            if copied and isinstance(item.get("id"), str):
                rows.append({"file": rel, "item": item["id"], **copied})
    return rows


def _milestone_ordering(reader: _Reader) -> dict[str, Any]:
    pairs = [{"milestone": m["milestone_id"], **_legacy(m, ("depends_on",))} for m in reader.milestones("09") if "depends_on" in m]
    typed = [
        {"step": step, "legacy_dependency": entry}
        for step in ("09", "14")
        for entry in _entries(reader.step(step).get("dependencies"))
    ]
    refs = [{"step": step, **_legacy(reader.step(step), ("dependency_ref",))} for step in ("09", "14") if "dependency_ref" in reader.step(step)]
    return {"pairs": pairs, "typed_dependencies": typed, "dependency_refs": refs}


def _milestone_links(reader: _Reader) -> list[dict[str, Any]]:
    rows = [
        {"step": step, "milestone": m["milestone_id"], **_legacy(m, _LINK_KEYS)}
        for step in ("09", "14")
        for m in reader.milestones(step)
    ]
    rows.extend(
        {"step": ANCHOR_STEP, "milestone": row["milestone_id"], **_legacy(row, ("fr_refs", "context_path"))}
        for row in reader.anchor_rows()
    )
    return rows


def _ambiguities(ctx: MigrationContext) -> list[dict[str, Any]]:
    """The ambiguity items of the anchor and the plans that are not resolved, whole (their ``impact[]`` included)."""
    return [
        {
            "file": os.path.relpath(item.artifact_path, ctx.spec_root).replace(os.sep, "/"),
            "step": item.step,
            "legacy_item": item.raw,
        }
        for item in iter_ambiguity_items(ctx.spec_root)
        if item.step in _OPEN_ITEM_STEPS and is_open(item)
    ]


def _environments(reader: _Reader) -> list[dict[str, Any]]:
    """The environments of step 02a whole: the host keys with no node field are among them, the filter is WI-M10-05's."""
    environments = reader.step("02a").get("environments")
    if not isinstance(environments, dict):
        return []
    return [{"environment": name, "legacy_environment": value} for name, value in environments.items() if isinstance(value, dict)]


def build_capture(ctx: MigrationContext) -> dict[str, Any]:
    """The whole content of ``capture.json`` for the spec folder of *ctx* as it stands."""
    reader = _Reader(ctx)
    return {
        "$schema": CAPTURE_SCHEMA,
        "source": _source(ctx),
        "milestone_status": _milestone_status(reader),
        "task_status": _task_status(reader),
        "task_exit_conditions": _task_lists(reader, "exit_conditions"),
        "task_assumptions": _task_lists(reader, "assumptions"),
        "third_party": _third_party(reader),
        "governance": _governance(reader),
        "plan_security": _plan_security(reader),
        "plan_items": _plan_items(reader),
        "milestone_ordering": _milestone_ordering(reader),
        "milestone_links": _milestone_links(reader),
        "ambiguities": _ambiguities(ctx),
        "environment_host_keys": _environments(reader),
    }


def detect(ctx: MigrationContext) -> int:
    """1 while ``capture.json`` does not exist, 0 once it does (whatever the tree holds then)."""
    return 0 if os.path.isfile(os.path.join(ctx.spec_root, CAPTURE_FILE)) else 1


def apply(ctx: MigrationContext) -> ScriptResult:
    """Write ``capture.json`` (first) and, when the host has none, an empty ``worklist.json``; nothing else changes."""
    ctx.documents.create(CAPTURE_FILE, build_capture(ctx))
    edits = 1
    if not os.path.isfile(os.path.join(ctx.spec_root, WORKLIST_FILE)):
        ctx.documents.create(WORKLIST_FILE, new_worklist_data())
        edits += 1
    return ScriptResult(edits=edits)


def verify(before: Snapshot, after: Snapshot) -> list[Problem]:
    """The script touched no file but its two."""
    return [
        Problem(f"changed {rel}, which is not one of the two files of the capture", rel)
        for rel in sorted(set(before.files) | set(after.files))
        if before.files.get(rel) != after.files.get(rel) and rel not in _OWN_FILES
    ]
