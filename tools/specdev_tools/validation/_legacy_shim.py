"""Guards for readers of 1.1.1 fields that the spec graph retires (M6c deletes this module).

A guarded reader runs only when the records that reader itself reads still carry a field that reader itself
reads (one constant per reader or group of readers; never "any loaded artifact"). There is no old-to-new
translation: new-shape data skips the reader and yields no finding.

A guard decides from record KEYS, never from nested values. ``has_legacy_fields(records, names)`` is true when some
record (a mapping) of *records* has a key in *names*; it does not descend, so a free-form payload (a fixture
``input``, an API body) that happens to hold a key named like a 1.1.1 field leaves the reader off. In 1.1.1 every
guarded field is a key of a record of a top-level array of its file (FR, API, NFR, capability, component ``trace``,
fixture ``targets``, threat ``target_ids`` and ``mitigations``, roadmap milestone ``fr_refs`` and
``source_milestones``, step-09 milestone ``deliverables``, charter goal ``goal_id``, capability
``success_metric_refs``) or of the file itself (``out_of_scope``, a file-level ``trace``). A caller passes the records its
reader reads; ``records_of(artifact)`` gives the file and the object members of its top-level arrays. The three
exceptions name their records at the call site: the plan's ``execution`` object (``critical_evidence``), the plan
checklist items (``spec_ref``) and the anchor rows of ``plan.milestone_index`` (``fr_refs``).
One array holding records of both shapes turns the 1.1.1 reader on for the whole array. The reader of an empty or
absent array runs, as it did in 1.1.1 (``reader_on(..., when_empty=True)``); the FR-to-API, FR-to-fixture and FR-to-milestone
decisions below are written once and used by ``matrix.py`` and ``traceability_closure.py`` alike.
Deleting this module means deleting every use of ``reader_on``, ``has_legacy_fields``, ``records_of``,
``fr_api_reader_on``, ``fr_fixture_reader_on``, ``fr_milestone_reader_on`` and the ``LEGACY_*`` names, and with them
``traceability_closure.uncomputed_dimensions`` and the ``not_computed`` output of ``completeness-check`` and
``matrix``, which report which guarded readers were off; the callers of ``is_parked_any_shape`` go back to
``core.scope_helpers.is_parked``. Two functions here are not guards and go with the retirement of their callers: ``removed_paths`` (``forward_replay_check.py``) and
``out_of_scope_fr_ids`` (``cli.py``, ``matrix.py``, ``traceability_closure.py``).
"""
from __future__ import annotations

import os
from collections.abc import Collection, Iterable, Mapping
from pathlib import Path
from typing import Any

from ..core.scope_helpers import is_parked, scope_in
from ..registry.schema_checklist import load_rows, selects

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


def records_of(artifact: Any) -> list[Mapping[str, Any]]:
    """Return *artifact* itself when it is a mapping, followed by the object members of its top-level arrays.

    These are the records a whole-file guard reads. Anything else gives an empty list; never raises.
    """
    if not isinstance(artifact, Mapping):
        return []
    records: list[Mapping[str, Any]] = [artifact]
    for value in artifact.values():
        if isinstance(value, list):
            records.extend(item for item in value if isinstance(item, Mapping))
    return records


def has_legacy_fields(records: Iterable[Any], names: Collection[str]) -> bool:
    """Return True when some mapping of *records* has a key in *names* (it does not look inside the values).

    Anything in *records* that is not a mapping is ignored. Never raises on malformed data.
    """
    return any(isinstance(record, Mapping) and any(key in names for key in record) for record in records)


def reader_on(records: Iterable[Any], names: Collection[str], *, when_empty: bool = True) -> bool:
    """Return True when a 1.1.1 reader of *names* runs on *records*.

    With no record the reader runs, as it did in 1.1.1 (*when_empty*; False for a reader that then has nothing to read);
    otherwise it runs only when a record carries a key of *names*, so records that carry none are a graph-shape
    file and are skipped. Never raises on malformed data.
    """
    records = list(records)
    return has_legacy_fields(records, names) if records else when_empty


def fr_api_reader_on(apis: Iterable[Any]) -> bool:
    """The FR-to-API decision (W564, E535, the matrix FR-to-API links): *apis* are the api records."""
    return reader_on(apis, LEGACY_TRACE_FIELDS)


def fr_fixture_reader_on(fixtures: Iterable[Any]) -> bool:
    """The FR-to-fixture decision (W565, E536): *fixtures* are the fixture records.

    A caller that also reads the file-level ``out_of_scope`` of the 08 file writes that clause itself.
    """
    return reader_on(fixtures, LEGACY_FIXTURE_TARGET_FIELDS)


def fr_milestone_reader_on(milestones: Iterable[Any]) -> bool:
    """The FR-to-milestone decision (W561, W566, the matrix milestone coverage): *milestones* are the roadmap records."""
    return reader_on(milestones, LEGACY_ROADMAP_FR_REF_FIELDS)


_SCHEMA_CHANGES_FILE = Path(__file__).resolve().parents[2] / "schema_changes.json"


def removed_paths(step: str, repo_root: str | os.PathLike[str] | None = None) -> list[str]:
    """Return the removed paths of *step* that forward replay prunes from the old file before comparing ids.

    These are the ``path`` values of the ``tools/schema_changes.json`` rows with ``change: remove``
    and ``shim: true`` whose ``step`` is *step* or a schema of it (``16`` selects ``16_anchor`` and
    ``16_impl_context``). Paths use the rows' notation (``a[].b``, ``m{}``). *repo_root* is the
    toolkit root (default: the toolkit this module belongs to). Returns ``[]`` when the rows file is
    absent or unreadable; a row that is not well formed is left out
    (``registry-generate`` and the closure test report it).
    """
    path = _SCHEMA_CHANGES_FILE if repo_root is None else Path(repo_root) / "tools" / "schema_changes.json"
    try:
        rows, _problems = load_rows(Path(path))
    except (OSError, ValueError):
        return []
    return [row.path for row in rows if row.shim and row.change == "remove" and selects(step, row.step)]


def out_of_scope_fr_ids(artifact: Mapping[str, Any]) -> set[str]:
    """Return the FR ids that the 1.1.1 ``out_of_scope[]`` of *artifact* (a 05 or 08 file) exempts.

    An entry counts when it is an object with a string ``fr_id`` and a non-empty ``rationale``. A
    new-shape file has no ``out_of_scope`` and yields the empty set. Never raises on a wrong-typed value.
    """
    if not isinstance(artifact, Mapping):
        return set()
    entries = artifact.get("out_of_scope")
    if not isinstance(entries, list):
        return set()
    return {
        entry["fr_id"]
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("fr_id"), str) and entry["fr_id"] and entry.get("rationale")
    }
