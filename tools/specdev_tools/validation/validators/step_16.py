from __future__ import annotations

from typing import Any, Optional
import fnmatch
import os
from pathlib import Path

from ...core.constants import SEED_MANIFEST_FILE
from ...core.errors import FindingError, make_error, SpecError
from ...core.loaders import read_json_object
from ...core.scope_helpers import as_dict, dict_items, str_in, str_items
from ...core.step_paths import PLAN_DIR_NAME
from ...lifecycle.anchor_store import is_legacy_close, read_row
from ...core.plan_files import milestone_key
from ...graph.names import PAUSED_DISPOSITIONS

# Checklist type and layer enums — currently hardcoded.  These values mirror the
# enum constraints in schema/16_impl_context.schema.json (``checklist[].type``
# and ``checklist[].layer``).  Loading them dynamically from canon/kinds/ is not
# practical: the values are schema-level enums, not canonical vocabulary entries,
# and the schema is the single source of truth.  See AUDIT-023.
VALID_CHECKLIST_TYPES = frozenset({"behavior", "constraint", "validation", "metadata", "perf", "logging", "docs", "security"})
VALID_CHECKLIST_LAYERS = frozenset({"db", "model", "service", "api", "integration", "tests", "docs", "config", "security"})

PLAN_BYTES_WARN = 750_000
"""W837 reports a plan file larger than this many bytes."""

# Built-in doc basenames — any file whose basename matches is treated as a doc
# regardless of directory depth.  Covers the common case of per-component
# README/CHANGELOG files that seed_manifest glob patterns (e.g. ``**/README.md``)
# do not reliably match via Python's ``fnmatch`` (which does not match ``**``
# against bare root basenames).
_BUILTIN_DOC_BASENAMES: frozenset[str] = frozenset({
    "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "AUTHORS.md", "LICENSE.md",
})

def _find_seed_manifest(spec_path: Optional[str], spec_root: Optional[str] = None) -> Optional[str]:
    """Locate the host's spec/common/seed_manifest.json without upward-walk ancestor escape.

    Resolution strategy (authoritative order):

    1. **spec_root declared**: return ``<spec_root>/common/seed_manifest.json`` if it
       exists, else ``None``.  When the caller supplies an explicit spec root, that is
       the authoritative location — no fallback to a spec_path walk if the declared
       root has no manifest.  Returning ``None`` causes the caller to emit W570, which
       is the correct signal: the declared root is missing its manifest.

    2. **spec_root absent, spec_path provided**: deterministic spec_path-relative
       resolution mirroring ``_load_roadmap``.  Compute the spec dir from spec_path:
       - If ``basename(dirname(spec_path)) == "impl_context"`` (milestone plan inside
         ``spec/impl_context/``): spec_dir = ``dirname(dirname(spec_path))``.
       - Otherwise (anchor at ``spec/16_impl_context.json``): spec_dir =
         ``dirname(spec_path)``.
       Return ``<spec_dir>/common/seed_manifest.json`` if it exists, else ``None``.

    3. **Both absent**: return ``None``.

    The unbounded upward walk used previously has been removed.  That walk violated
    the DEVSPEC-43 north star by escaping the host boundary: in a monorepo where the
    host has no local manifest but an ancestor directory does, the walk returned the
    ancestor's manifest instead of ``None``.  With the deterministic fallback, a host
    that lacks a local manifest correctly gets ``None`` → W570 rather than silently
    inheriting an ancestor's manifest.

    Behavior for standard submodule layouts (spec_root = host spec dir):
        - spec_root supplied → resolves ``<host>/spec/common/seed_manifest.json``
          directly.  Same manifest the walk found; behaviour unchanged for
          correctly structured hosts. ✓
        - Anchor (``spec/16_impl_context.json``, no spec_root): spec_dir =
          ``dirname(spec_path)`` = ``<host>/spec/`` →
          ``<host>/spec/common/seed_manifest.json``. ✓
        - Milestone plan (``spec/impl_context/ms_foo_plan.json``, no spec_root):
          spec_dir = ``dirname(dirname(spec_path))`` = ``<host>/spec/`` →
          ``<host>/spec/common/seed_manifest.json``. ✓
    """
    if spec_root is not None:
        cand = os.path.join(os.path.abspath(spec_root), SEED_MANIFEST_FILE)
        return cand if os.path.exists(cand) else None

    if spec_path:
        dirname = os.path.dirname(os.path.abspath(spec_path))
        if os.path.basename(dirname) == "impl_context":
            spec_dir = os.path.dirname(dirname)
        else:
            spec_dir = dirname
        cand = os.path.join(spec_dir, SEED_MANIFEST_FILE)
        return cand if os.path.exists(cand) else None

    return None


def _is_anchor(spec_path: Optional[str], data: Optional[dict[str, Any]] = None) -> bool:
    """Detect whether this artifact is the Step 16 Trinity Anchor (vs. a 16a/16b/16c plan).

    Two-tier detection (defence-in-depth): prefers the `artifact_role` field
    declared on the vc:16-anchor schema when the artifact is structurally
    parseable, and falls back to a path heuristic for cases where the field
    is absent (malformed artifact, pre-schema fixture, routing probe before
    full parse). The path heuristic keeps validators safe even when an author
    omits `artifact_role` — the schema will reject it, but routing still
    needs a correct yes/no answer before schema errors surface.
    """
    role = data.get("artifact_role") if isinstance(data, dict) else None
    if isinstance(role, str) and role.strip() == "anchor":
        return True
    if not spec_path:
        return False
    p = Path(spec_path)
    return p.name == "16_impl_context.json" and p.parent.name != "impl_context"


def _load_roadmap(spec_path: str) -> Optional[dict[str, Any]]:
    """Load 14_roadmap.json relative to spec_path with correct path resolution.

    Resolves correctly for both anchor and milestone plan artifacts:
    - Anchor (spec/16_impl_context.json) → spec/14_roadmap.json
    - 16a plan (spec/impl_context/ms_auth_plan.json) → spec/14_roadmap.json

    Returns:
        The roadmap object; ``None`` when 14_roadmap.json is missing, unreadable, not UTF-8, not JSON or not an
        object.  Never raises.  A caller that reports a present file it cannot use tests ``roadmap_path`` itself.
    """
    return read_json_object(_roadmap_path(spec_path))


def _roadmap_path(spec_path: str) -> Path:
    """Where ``14_roadmap.json`` lies for the artifact at *spec_path*."""
    artifact_path = Path(spec_path)
    base = artifact_path.parent.parent if artifact_path.parent.name == "impl_context" else artifact_path.parent
    return base / "14_roadmap.json"


def _checklist_of(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """The plan items (``plan.spec_alignment.checklist``) that are objects."""
    return dict_items(as_dict(plan.get("spec_alignment")).get("checklist"))


def _check_type_and_layer(checklist: list[dict[str, Any]], errors: list[SpecError]) -> None:
    """E530: every plan item's ``type`` and ``layer`` is one of the declared enum values."""
    for item in checklist:
        item_id = item.get("id", "unknown")
        item_type = item.get("type", "")
        item_layer = item.get("layer", "")
        if not str_in(item_type, VALID_CHECKLIST_TYPES):
            errors.append(make_error("E530", f"Checklist item '{item_id}' has invalid type '{item_type}'. Must be one of: {', '.join(sorted(VALID_CHECKLIST_TYPES))}"))
        if not str_in(item_layer, VALID_CHECKLIST_LAYERS):
            errors.append(make_error("E530", f"Checklist item '{item_id}' has invalid layer '{item_layer}'. Must be one of: {', '.join(sorted(VALID_CHECKLIST_LAYERS))}"))


def _check_target_patterns_and_scope(data: dict[str, Any], plan: dict[str, Any], checklist: list[dict[str, Any]], errors: list[SpecError]) -> None:
    """E520 for execution files outside ``target_file_patterns``; W603 for execution files outside any declared scope."""
    summary = as_dict(plan.get("summary"))
    summary_patterns = set(str_items(summary.get("target_file_patterns")))
    execution_files = set(str_items(as_dict(data.get("execution")).get("files_touched")))

    # AUDIT-087: scope-binding check -- execution.files_touched not declared in any item's files_touched.
    declared = {f for item in checklist for f in str_items(as_dict(item.get("implementation")).get("files_touched"))}
    milestone_files = set(str_items(summary.get("milestone_supporting_files")))
    for f in execution_files:
        if f not in declared and f not in milestone_files:
            errors.append(make_error(
                "W603",
                f"FILES_OUTSIDE_TASK_SCOPE: execution file '{f}' is not declared in "
                f"any checklist item's files_touched or plan.summary.milestone_supporting_files "
                f"— may be outside task scope",
            ))

    for f in execution_files:
        if not any(fnmatch.fnmatch(f, pattern) for pattern in summary_patterns):
            errors.append(make_error("E520", f"File '{f}' is touched by implementation but not covered by target_file_patterns."))


def _load_doc_patterns(spec_path: Optional[str], spec_root: Optional[str], errors: list[SpecError]) -> Optional[list[str]]:
    """The ``doc_paths`` of the host seed manifest; ``None`` (with a W570) when it is absent, unreadable or empty.

    With neither *spec_path* nor *spec_root* there is nowhere to look: ``None`` and no finding.
    """
    if not spec_path and spec_root is None:
        return None
    manifest_path = _find_seed_manifest(spec_path, spec_root)
    if not manifest_path:
        errors.append(make_error("W570", "seed_manifest.json not found; cannot validate docs_impact doc paths."))
        return None
    manifest = read_json_object(manifest_path)
    if manifest is None:
        errors.append(make_error("W570", "Failed to read seed_manifest.json; cannot validate docs_impact doc paths."))
        return None
    doc_patterns = manifest.get("doc_paths") or []
    if not isinstance(doc_patterns, list) or not doc_patterns:
        errors.append(make_error("W570", "seed_manifest.json missing doc_paths; cannot validate docs_impact doc paths."))
        return None
    return [p for p in doc_patterns if isinstance(p, str)]


def _is_doc_path(path: str, doc_patterns: Optional[list[str]]) -> bool:
    """True when *path* is a built-in doc basename or matches one of the manifest's doc patterns."""
    if not path:
        return False
    norm = path.replace("\\", "/").lstrip("./")
    if os.path.basename(norm) in _BUILTIN_DOC_BASENAMES:
        return True
    return any(fnmatch.fnmatch(norm, pattern) for pattern in doc_patterns or [])


def _check_docs_impact(plan: dict[str, Any], checklist: list[dict[str, Any]], spec_path: Optional[str], spec_root: Optional[str], errors: list[SpecError]) -> None:
    """W570 and E520: ``plan.docs_impact`` is present, required and doc-pathed when the plan changes code."""
    doc_patterns = _load_doc_patterns(spec_path, spec_root, errors)
    code_change_targets = [
        target
        for item in checklist
        for action in dict_items(as_dict(item.get("implementation")).get("actions"))
        if action.get("type") in ("file_create", "file_edit")
        for target in [action.get("target", "")]
        if isinstance(target, str) and target and not _is_doc_path(target, doc_patterns)
    ]
    if not code_change_targets:
        return
    docs_impact = plan.get("docs_impact")
    if not isinstance(docs_impact, dict):
        errors.append(make_error("E520", "plan.docs_impact is required when code changes are present."))
        return
    if docs_impact.get("status") != "required":
        errors.append(make_error("E520", "plan.docs_impact.status must be 'required' when code changes are present."))
    docs_touched = docs_impact.get("docs_touched", [])
    if not docs_touched:
        errors.append(make_error("E520", "plan.docs_impact.docs_touched must be provided when code changes are present."))
    elif doc_patterns:
        for doc_path in str_items(docs_touched):
            if not _is_doc_path(doc_path, doc_patterns):
                errors.append(make_error("E520", f"plan.docs_impact.docs_touched contains non-doc path: {doc_path}"))


def _realised_criteria(checklist: list[dict[str, Any]]) -> set[str]:
    """Every criterion id some plan item ``realises``."""
    return {cid for item in checklist for cid in str_items(item.get("realises"))}


def _is_set_aside(task: dict[str, Any]) -> bool:
    """True when the roadmap task carries a ``disposition`` of ``deferred`` or ``wont_do`` (paused or cancelled, not absent)."""
    # A raw task dict of a plan being validated: there is no graph here, so this cannot call ``graph.queries.task_disposition``.
    return str_in(as_dict(task.get("disposition")).get("value"), PAUSED_DISPOSITIONS)


def _check_roadmap_coverage(data: dict[str, Any], checklist: list[dict[str, Any]], roadmap: dict[str, Any], errors: list[SpecError]) -> None:
    """E304: the plan's ``milestone`` names a roadmap milestone (by its id or an alias, so a renamed milestone is found), and each of its tasks has a criterion some item realises.

    A task set aside by its ``disposition`` (deferred or wont_do) needs no item. A plan without a ``milestone`` has no
    scope to check: the schema reports the missing key.
    """
    milestone_id = data.get("milestone")
    if not isinstance(milestone_id, str):
        return
    milestone = next(
        (m for m in dict_items(roadmap.get("milestones")) if milestone_id in (m.get("milestone_id"), *str_items(m.get("aliases")))), None
    )
    if milestone is None:
        errors.append(make_error("E304", f"ROADMAP_MILESTONE_UNKNOWN: plan milestone '{milestone_id}' is not a milestone of 14_roadmap.json"))
        return
    realised = _realised_criteria(checklist)
    for task in dict_items(milestone.get("tasks")):
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or _is_set_aside(task):
            continue
        criteria = {c["criterion_id"] for c in dict_items(task.get("acceptance_criteria")) if isinstance(c.get("criterion_id"), str)}
        if not criteria:
            errors.append(
                make_error("E304", f"ROADMAP_TASK_UNCOVERED: roadmap task '{task_id}' of milestone '{milestone_id}' has no acceptance criterion, so no plan item can realise it; add a criterion to the task or give it a disposition")
            )
        elif not criteria & realised:
            errors.append(
                make_error("E304", f"ROADMAP_TASK_UNCOVERED: roadmap task '{task_id}' of milestone '{milestone_id}' has no plan item that realises one of its acceptance criteria")
            )


def _check_roadmap(data: dict[str, Any], checklist: list[dict[str, Any]], spec_path: str, errors: list[SpecError]) -> None:
    """Load ``14_roadmap.json`` beside *spec_path* and run E304 on it (a 16a plan, never the anchor)."""
    roadmap = _load_roadmap(spec_path)
    if roadmap is not None:
        _check_roadmap_coverage(data, checklist, roadmap, errors)
    elif _roadmap_path(spec_path).exists():  # present but not a UTF-8 JSON object
        errors.append(make_error("E304", "ROADMAP_PARSE_ERROR: could not load 14_roadmap.json: not a UTF-8 JSON object"))


def is_legacy_closed_plan(spec_path: str, spec_root: Optional[str] = None) -> bool:
    """Whether the plan file at *spec_path* belongs to a milestone whose anchor row is legacy-closed (ruling L2).

    A legacy-closed plan keeps the 1.1.1 shape as history until ``specdev align`` migrates it, so its schema findings
    are not reported and it is not asked for ``realises``.  The plan's milestone is its file-level ``milestone`` key;
    *spec_root* defaults to the folder above ``impl_context/``.  A file outside ``impl_context/``, a plan without the
    key, a milestone with no anchor row and an anchor file that cannot be read all answer ``False``.
    """
    path = Path(spec_path)
    if path.parent.name != PLAN_DIR_NAME:
        return False
    milestone = milestone_key(path)
    if milestone is None:
        return False
    try:
        row = read_row(spec_root or path.parent.parent, milestone)
    except FindingError:
        return False
    return row is not None and is_legacy_close(row.close)


def _check_plan_file_size(spec_path: str, errors: list[SpecError]) -> None:
    """W837: the plan file at *spec_path* is larger than ``PLAN_BYTES_WARN`` bytes (a file that cannot be read has no size to report)."""
    try:
        size = os.path.getsize(spec_path)
    except OSError:
        return
    if size > PLAN_BYTES_WARN:
        errors.append(make_error("W837", f"PLAN_FILE_LARGE: the plan file is {size} bytes, above {PLAN_BYTES_WARN}; split the milestone so each plan stays small"))


def validate_step_16(data: dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None, spec_root: Optional[str] = None) -> list[SpecError]:
    """Deep validation for Step 16 (Implementation Context).

    Args:
        data: The parsed JSON content of the step file.
        toolkit_root: The root directory of the toolkit (for resolving references).
        spec_path: Absolute path to the artifact file being validated, used for
            sibling-file lookups (roadmap, seed manifest). None disables those checks.
        spec_root: Path to the host spec root directory, used for cross-step
            artifact discovery. None falls back to artifact-directory scans.

    Returns:
        List of SpecError objects. Empty list if valid. Never raises on a wrong-typed value: a value of the wrong
        type reads as absent (the schema reports it).
    """
    errors: list[SpecError] = []
    plan = as_dict(data.get("plan"))
    checklist = _checklist_of(plan)

    _check_type_and_layer(checklist, errors)
    _check_target_patterns_and_scope(data, plan, checklist, errors)
    _check_docs_impact(plan, checklist, spec_path, spec_root, errors)
    if spec_path:
        _check_plan_file_size(spec_path, errors)
        if not _is_anchor(spec_path, data) and not is_legacy_closed_plan(spec_path, spec_root):
            _check_roadmap(data, checklist, spec_path, errors)

    return errors
