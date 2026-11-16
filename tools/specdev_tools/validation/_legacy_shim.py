"""Guards for readers of 1.1.1 fields that the spec graph retires (M6c deletes this module).

A guarded reader runs only when the artifacts that reader itself reads still carry a field that
reader itself reads (one constant per reader or group of readers; never "any loaded artifact").
There is no old-to-new translation: new-shape data skips the reader and yields no finding.
A guard counts a field anywhere in the whole array it reads: one array that holds entries of both shapes
(some carrying the 1.1.1 field, some not) turns the 1.1.1 reader on for every entry of that array.
Deleting this module means deleting every use of ``reader_on``, ``has_legacy_fields`` and the ``LEGACY_*``
names; the callers of ``is_parked_any_shape`` go back to ``core.scope_helpers.is_parked``. Two functions here are
not guards and go with the retirement of their callers: ``removed_paths`` (``forward_replay_check.py``) and
``out_of_scope_fr_ids`` (``cli.py``, ``matrix.py``, ``traceability_closure.py``).
"""
from __future__ import annotations

import json
import os
from collections.abc import Collection, Iterable, Mapping
from pathlib import Path
from typing import Any

from ..core.scope_helpers import is_parked, scope_in

# 1.1.1 `trace` links, read by three live readers: W564/E535 (05 apis) and W568 (04 frs) in
# `traceability_closure.py`, and FR-to-API coverage (05 apis) in `matrix.py`.
LEGACY_TRACE_FIELDS: frozenset[str] = frozenset({"trace"})

# Charter -> capabilities chain, read by E560 in `traceability_closure.py`. Each half needs both sides, so a pair
# with one side migrated reports nothing for it: the goal half runs only when the charter carries `goal_id` AND the
# capabilities carry `trace`; the metric half runs when the capabilities carry `trace` or `success_metric_refs`
# (a 1.1.1 capability has either; the charter `metric_id` exists in both shapes, so it cannot gate).
LEGACY_CHARTER_GOAL_FIELDS: frozenset[str] = frozenset({"goal_id"})
LEGACY_CAPABILITY_GOAL_FIELDS: frozenset[str] = frozenset({"trace"})
LEGACY_CAPABILITY_METRIC_FIELDS: frozenset[str] = frozenset({"trace", "success_metric_refs"})

# Step-02 capability-coverage reader in `cross_artifact_checks.py` (component `trace` / `trace_refs`).
LEGACY_COMPONENT_TRACE_FIELDS: frozenset[str] = frozenset({"trace", "trace_refs"})

# Fixture `targets`: the fixture-to-API link read by `matrix.py`.
LEGACY_FIXTURE_TARGET_FIELDS: frozenset[str] = frozenset({"targets"})

# FR-to-fixture coverage (W565, E536 in `traceability_closure.py`, the same dimension in
# `completeness-check`): fixture `targets` and the step-08 `out_of_scope` exemption.
LEGACY_FIXTURE_COVERAGE_FIELDS: frozenset[str] = frozenset({"targets", "out_of_scope"})

# NFR `trace`: the NFR-to-API and NFR-to-FR links read by `matrix.py`.
LEGACY_NFR_TRACE_FIELDS: frozenset[str] = frozenset({"trace"})

# Threat `target_ids` and `mitigations`: the threat links read by `matrix.py` (API-to-threat and
# invariant-threat coverage).
LEGACY_THREAT_TARGET_FIELDS: frozenset[str] = frozenset({"target_ids"})
LEGACY_THREAT_MITIGATION_FIELDS: frozenset[str] = frozenset({"mitigations"})

# Step-14 `fr_refs`: milestone coverage in `matrix.py`, W561 / W566 / the task part of W567 in
# `traceability_closure.py`, the `fr-milestone` dimension of `completeness-check`.
LEGACY_ROADMAP_FR_REF_FIELDS: frozenset[str] = frozenset({"fr_refs"})

# Step-14 fields the trace matrix is built from: the W604 staleness warning in `validators/step_14.py`.
LEGACY_ROADMAP_MATRIX_FIELDS: frozenset[str] = frozenset({"fr_refs", "source_milestones"})

# Step-09 milestone `deliverables`: W575 in `traceability_closure.py`.
LEGACY_DELIVERABLE_FIELDS: frozenset[str] = frozenset({"deliverables"})

# Milestone-plan checklist `spec_ref`: W562 and W563 in `traceability_closure.py`.
LEGACY_PLAN_CHECKLIST_FIELDS: frozenset[str] = frozenset({"spec_ref"})

# Milestone-plan `critical_evidence` and checklist `spec_ref`: the executed-task set W576 in
# `traceability_closure.py` is built from.
LEGACY_PLAN_EVIDENCE_FIELDS: frozenset[str] = frozenset({"critical_evidence", "spec_ref"})

# `trace`, `targets`, `fr_refs`, `source_milestones`: the edges `context/scope_resolver.py` builds its
# trace graph from.
LEGACY_SCOPE_LINK_FIELDS: frozenset[str] = frozenset({"trace", "targets", "fr_refs", "source_milestones"})

# `trace` arrays: the structural review in `context/reviewer.py` (coverage and reverse trace) counts them.
LEGACY_REVIEWER_TRACE_FIELDS: frozenset[str] = frozenset({"trace"})

# The 1.1.1 spellings of a parked node: a capability with `scope: future` and an FR with
# `priority: wont-have`. Readers that can meet a legacy file (`matrix.py`, `traceability_closure.py`,
# `validators/step_11.py`, `cli.py`) call `is_parked_any_shape`.
LEGACY_PARKED_SCOPES: frozenset[str] = frozenset({"future"})
LEGACY_PARKED_PRIORITY = "wont-have"


def is_parked_any_shape(node: Mapping[str, Any]) -> bool:
    """Return True when *node* is parked in the current shape (``is_parked``) or the 1.1.1 one.

    The 1.1.1 forms are ``scope: future`` and ``priority: wont-have``. For readers that can meet
    a legacy file and a new-shape file in the same run. When this module is deleted its callers
    go back to ``is_parked``. Never raises on a wrong-typed value.
    """
    return (
        is_parked(node)
        or scope_in(node, LEGACY_PARKED_SCOPES)
        or node.get("priority") == LEGACY_PARKED_PRIORITY
    )


def _carries(value: Any, names: Collection[str]) -> bool:
    if isinstance(value, Mapping):
        return any(key in names or _carries(item, names) for key, item in value.items())
    if isinstance(value, list):
        return any(_carries(item, names) for item in value)
    return False


def has_legacy_fields(artifacts: Iterable[Any], names: Collection[str]) -> bool:
    """Return True when any key in *names* appears at any depth of any artifact in *artifacts*.

    *artifacts* is an iterable of loaded artifact values (dicts); anything that is not a mapping
    or list is ignored. Never raises on malformed data.
    """
    return any(_carries(artifact, names) for artifact in artifacts)


_SAME: Any = object()


def reader_on(
    artifacts: Iterable[Any],
    names: Collection[str],
    *,
    entries: Any = _SAME,
    when_empty: bool = True,
) -> bool:
    """Return True when a 1.1.1 reader of *names* runs on *artifacts*.

    The one rule of every guard: when *entries* (default *artifacts*; ``None`` is an absent array) is empty or absent the reader runs as
    before (*when_empty*; pass False for a reader that has nothing to read then); otherwise it runs only when
    *artifacts* still carry a key of *names*, so an array whose entries carry none of them is a graph-shape file
    and is skipped. *entries* is the array whose emptiness decides, when the fields are searched in a larger
    artifact (a step-05 file for its ``apis``). Never raises on malformed data.
    """
    artifacts = list(artifacts)
    watched = artifacts if entries is _SAME else entries
    if not watched:
        return when_empty
    return has_legacy_fields(artifacts, names)


_SCHEMA_CHANGES_FILE = Path(__file__).resolve().parents[2] / "schema_changes.json"


def removed_paths(step: str, repo_root: str | os.PathLike[str] | None = None) -> list[str]:
    """Return the paths of fields removed from *step* that a legacy reader still reads.

    These are the ``path`` values of the ``tools/schema_changes.json`` rows with ``change: remove``
    and ``shim: true`` whose ``step`` is *step* or a schema of it (``16`` selects ``16_anchor`` and
    ``16_impl_context``). Paths use the rows' notation (``a[].b``, ``m{}``). *repo_root* is the
    toolkit root (default: the toolkit this module belongs to). Returns ``[]`` when the rows file is
    absent or unreadable.
    """
    path = _SCHEMA_CHANGES_FILE if repo_root is None else Path(repo_root) / "tools" / "schema_changes.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("rows", [])
    except (OSError, ValueError, AttributeError):
        return []
    return [
        row["path"]
        for row in rows
        if isinstance(row, dict)
        and row.get("shim") is True
        and row.get("change") == "remove"
        and isinstance(row.get("path"), str)
        and isinstance(row.get("step"), str)
        and (row["step"] == step or row["step"].startswith(f"{step}_"))
    ]


def out_of_scope_fr_ids(artifact: Mapping[str, Any]) -> set[str]:
    """Return the FR ids that the 1.1.1 ``out_of_scope[]`` of *artifact* (a 05 or 08 file) exempts.

    An entry counts when it is an object with a string ``fr_id`` and a non-empty ``rationale``. A
    new-shape file has no ``out_of_scope`` and yields the empty set. Never raises on a wrong-typed value.
    """
    entries = artifact.get("out_of_scope")
    if not isinstance(entries, list):
        return set()
    return {
        entry["fr_id"]
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("fr_id"), str) and entry["fr_id"] and entry.get("rationale")
    }
