from __future__ import annotations

from typing import Any, Optional
import fnmatch
from collections import defaultdict
import json
import os
import re
from pathlib import Path

from ...core.errors import make_error, SpecError
from ...core.scope_helpers import as_dict, dict_items, str_in, str_items
from ..linter_utils import extract_command_string

# Checklist type and layer enums — currently hardcoded.  These values mirror the
# enum constraints in schema/16_impl_context.schema.json (``checklist[].type``
# and ``checklist[].layer``).  Loading them dynamically from canon/kinds/ is not
# practical: the values are schema-level enums, not canonical vocabulary entries,
# and the schema is the single source of truth.  See AUDIT-023.
VALID_CHECKLIST_TYPES = frozenset({"behavior", "constraint", "validation", "metadata", "perf", "logging", "docs", "security"})
VALID_CHECKLIST_LAYERS = frozenset({"db", "model", "service", "api", "integration", "tests", "docs", "config", "security"})
TYPES_REQUIRING_PROOF = frozenset({"behavior", "constraint", "validation", "perf", "security"})

# `disposition.value` of a roadmap task meaning "paused or permanently cancelled, not absent": E304 skips such a task.
PAUSED_OR_CANCELLED_DISPOSITIONS = frozenset({"deferred", "wont_do"})

# checklist_status values of a 1.1.1-shaped plan with the same meaning (DEVSPEC-122 follow-up); read only by the
# legacy-guarded E305. M8 deletes this name; the set above stays.
# M8 rewrites
PAUSED_OR_CANCELLED_CHECKLIST_STATUSES = PAUSED_OR_CANCELLED_DISPOSITIONS

# Success marker keywords for evidence content validation (Task 7-03 AUDIT-070)
_SUCCESS_MARKERS: tuple[str, ...] = ("PASS", "OK", "passed", "success", "0 failures")

# Spec artifact ID pattern for evidence binding validation (AUDIT-032)
_ARTIFACT_ID_RE = re.compile(r'\b(?:fr|api|nfr|inv)-[a-z0-9-]+\b')

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
        cand = os.path.join(os.path.abspath(spec_root), "common", "seed_manifest.json")
        return cand if os.path.exists(cand) else None

    if spec_path:
        dirname = os.path.dirname(os.path.abspath(spec_path))
        if os.path.basename(dirname) == "impl_context":
            spec_dir = os.path.dirname(dirname)
        else:
            spec_dir = dirname
        cand = os.path.join(spec_dir, "common", "seed_manifest.json")
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
        Parsed roadmap dict, or None if 14_roadmap.json does not exist.

    Raises:
        OSError: If the file exists but cannot be read.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    artifact_path = Path(spec_path)
    if artifact_path.parent.name == "impl_context":
        roadmap_path = artifact_path.parent.parent / "14_roadmap.json"
    else:
        roadmap_path = artifact_path.parent / "14_roadmap.json"

    if not roadmap_path.exists():
        return None
    return json.loads(roadmap_path.read_text())


# M8 rewrites
def _check_behavior_validation_pairing(checklist: list[dict[str, Any]], errors: list[SpecError]) -> None:
    """E307: For every behavioral spec ref (fr, api, inv, nfr), ensure at least one behavior and one validation item.

    Keyed on the 1.1.1 ``spec_ref``; a 1.2.0 plan item has none, so on that shape this finds nothing.

    Groups checklist items by their spec_ref.id and checks that each group has
    both a 'behavior' and a 'validation' type item. Deferred items are included
    in this grouping -- a deferred 'validation' item still satisfies the pairing
    requirement (it's paused, not absent).
    Non-behavioral spec_ref types ('doc', 'code', 'task') are excluded — these are work items,
    not testable behaviors, and do not require behavior+validation pairing.
    """
    groups: dict[str, set] = defaultdict(set)
    for item in checklist:
        spec_ref = item.get("spec_ref")
        if not isinstance(spec_ref, dict):
            continue
        ref_id = spec_ref.get("id")
        if not isinstance(ref_id, str) or not ref_id:
            continue
        # Skip non-behavioral spec_ref types (doc, code, task) — work items, not testable behaviors
        if spec_ref.get("type") in ("doc", "code", "task"):
            continue
        item_type = item.get("type")
        if isinstance(item_type, str) and item_type:
            groups[ref_id].add(item_type)

    for ref_id, types in groups.items():
        missing = []
        if "behavior" not in types:
            missing.append("behavior")
        if "validation" not in types:
            missing.append("validation")
        if missing:
            errors.append(
                make_error("E307", f"BEHAVIOR_VALIDATION_PAIRING: spec ref '{ref_id}' "
                f"is missing checklist item(s) of type: {', '.join(missing)}")
            )


def _checklist_of(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """The plan items (``plan.spec_alignment.checklist``) that are objects."""
    return dict_items(as_dict(plan.get("spec_alignment")).get("checklist"))


# M8 rewrites
def _legacy_status(item: dict[str, Any]) -> Optional[str]:
    """``implementation.status`` of a 1.1.1-shaped plan item; ``None`` on the 1.2.0 shape, which stores none.

    The status-keyed rules below run only when this returns a value.
    """
    status = as_dict(item.get("implementation")).get("status")
    return status if isinstance(status, str) else None


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


def _check_action_evidence(item_id: str, item_type: str, actions: list[dict[str, Any]], errors: list[SpecError]) -> None:
    """E301, W599, W600, W601 on the actions of one legacy ``verified`` item (evidence presence and quality).

    Task 7-03 (AUDIT-070) + Task 7-04 (AUDIT-032): evidence content quality and binding.
    """
    has_evidence = False
    for action in actions:
        evidence = action.get("evidence")
        if evidence is None:
            # W600: each individual verified action should have evidence
            errors.append(make_error("W600", f"VERIFIED_ACTION_NO_EVIDENCE: verified action '{action.get('type', 'unknown')}' in checklist item '{item_id}' has no evidence field"))
            continue
        # evidence is present — mark presence and validate quality
        has_evidence = True
        if not isinstance(evidence, dict):
            # Non-dict evidence (e.g., plain string) satisfies presence check but
            # cannot be quality-validated — skip content/structure checks
            continue
        content = evidence.get("content")
        has_structured = "stdout" in evidence or "stderr" in evidence
        if isinstance(content, str):
            if len(content) < 50:
                errors.append(make_error("W599", f"EVIDENCE_TOO_SHORT: action evidence in checklist item '{item_id}' has content shorter than 50 characters ({len(content)} chars)"))
            has_success_marker = any(marker in content for marker in _SUCCESS_MARKERS)
            if not has_success_marker and not has_structured:
                errors.append(make_error("E301", f"EVIDENCE_CONTENT_INVALID: action evidence in checklist item '{item_id}' lacks a success marker keyword (e.g. PASS, OK, passed, success, '0 failures') and has no stdout/stderr fields"))
        elif not has_structured:
            # Evidence dict present but missing both content and stdout/stderr
            errors.append(make_error("W600", f"EVIDENCE_NO_CONTENT: verified action in checklist item '{item_id}' has evidence dict but no 'content', 'stdout', or 'stderr' field"))
        # AUDIT-032: check that evidence content references at least one spec artifact ID.
        # Only proof-types (TYPES_REQUIRING_PROOF) have an honest fr-/nfr-/inv- tie to
        # cite; non-proof types (metadata, docs, logging, config) legitimately have none.
        if str_in(item_type, TYPES_REQUIRING_PROOF):
            combined = " ".join(filter(None, [
                content if isinstance(content, str) else "",
                evidence.get("stdout") if isinstance(evidence.get("stdout"), str) else "",
                evidence.get("stderr") if isinstance(evidence.get("stderr"), str) else "",
            ]))
            if combined and not _ARTIFACT_ID_RE.search(combined):
                errors.append(make_error("W601", f"EVIDENCE_NO_ARTIFACT_REF: evidence in checklist item '{item_id}' action '{action.get('type', 'unknown')}' does not reference any spec artifact ID (fr-*, api-*, nfr-*, inv-*)"))
    if not has_evidence:
        errors.append(make_error("E301", f"Checklist item '{item_id}' is 'verified' but contains no evidence in any action."))


# M8 rewrites
def _check_legacy_verified_items(checklist: list[dict[str, Any]], errors: list[SpecError]) -> None:
    """E301 and the evidence-quality checks (W599, W600, W601) of 1.1.1-shaped plans.

    Runs only for an item that carries ``implementation.status``; a 1.2.0 plan item stores none.
    """
    for item in checklist:
        status = _legacy_status(item)
        if status not in ("verified", "in_progress"):
            continue
        item_id = item.get("id", "unknown")
        actions = dict_items(as_dict(item.get("implementation")).get("actions"))
        if status == "verified" and not actions:
            errors.append(make_error("E301", f"Checklist item '{item_id}' is 'verified' but has no actions."))
        elif status == "verified":
            _check_action_evidence(item_id, item.get("type", ""), actions, errors)


# M8 rewrites
def _legacy_touched_files(checklist: list[dict[str, Any]]) -> set[str]:
    """The ``implementation.files_touched`` of the started items (``in_progress`` or ``verified``) of a 1.1.1-shaped plan."""
    touched: set[str] = set()
    for item in checklist:
        if _legacy_status(item) in ("in_progress", "verified"):
            touched.update(str_items(as_dict(item.get("implementation")).get("files_touched")))
    return touched


def _touched_files(checklist: list[dict[str, Any]], execution_files: set[str]) -> set[str]:
    """Files the plan says it touches: ``execution.files_touched`` plus, on legacy plans, the files of started items."""
    return set(execution_files) | _legacy_touched_files(checklist)


def _check_target_patterns_and_scope(data: dict[str, Any], plan: dict[str, Any], checklist: list[dict[str, Any]], errors: list[SpecError]) -> None:
    """E520 for touched files outside ``target_file_patterns``; W603 for execution files outside any declared scope."""
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

    for f in _touched_files(checklist, execution_files):
        if not any(fnmatch.fnmatch(f, pattern) for pattern in summary_patterns):
            errors.append(make_error("E520", f"File '{f}' is touched by implementation but not covered by target_file_patterns."))


def _load_doc_patterns(spec_path: Optional[str], spec_root: Optional[str], errors: list[SpecError]) -> Optional[list[str]]:
    """The ``doc_paths`` of the host seed manifest; ``None`` (with a W570) when it is absent, unreadable or empty."""
    manifest_path = _find_seed_manifest(spec_path, spec_root)
    if not manifest_path:
        errors.append(make_error("W570", "seed_manifest.json not found; cannot validate docs_impact doc paths."))
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        errors.append(make_error("W570", "Failed to read seed_manifest.json; cannot validate docs_impact doc paths."))
        return None
    doc_patterns = as_dict(manifest).get("doc_paths") or []
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


def _executed_commands(data: dict[str, Any]) -> tuple[set[str], set[str]]:
    """``(passed, acknowledged)`` command strings of ``execution.execution_results``.

    Acknowledged = passed or blocked: a blocked entry is an explicit acknowledgment, not a missing proof, so it
    satisfies E301 but not E302 (verified verdict).
    """
    passed: set[str] = set()
    acknowledged: set[str] = set()
    for result in dict_items(as_dict(data.get("execution")).get("execution_results")):
        status, cmd = result.get("status"), result.get("command")
        if not isinstance(cmd, str):
            continue
        if status == "passed":
            passed.add(cmd.strip())
        if status in ("passed", "blocked"):
            acknowledged.add(cmd.strip())
    return passed, acknowledged


def _check_proof_closure(data: dict[str, Any], plan: dict[str, Any], errors: list[SpecError]) -> None:
    """E301 MISSING_PROOF_CLOSURE (D22), E302 UNPROVEN_VERIFIED_REVIEW (D23) and E303 CI_GATE_VIOLATION."""
    review_reqs = as_dict(plan.get("review_requirements"))
    test_commands = review_reqs.get("test_commands", [])
    test_commands = test_commands if isinstance(test_commands, list) else []
    execution = data.get("execution", {})
    execution_results = as_dict(execution).get("execution_results")
    passed_commands, acknowledged_commands = _executed_commands(data)

    # A plan stores no status since 1.2.0 (the anchor holds a milestone's deferral): an absent status is an active plan.
    if plan.get("status", "active") == "active" and test_commands and execution_results:
        for cmd in test_commands:
            cmd_str = extract_command_string(cmd)
            if cmd_str and cmd_str.strip() not in acknowledged_commands:
                errors.append(
                    make_error("E301", f"MISSING_PROOF_CLOSURE test command '{cmd_str}' required "
                    f"by review_requirements but not found in execution_results with status=passed")
                )

    review = as_dict(data.get("review"))
    verdict = review.get("verdict")
    if verdict != "verified":
        return
    if not execution or not isinstance(execution, dict):
        errors.append(make_error("E302", "UNPROVEN_VERIFIED_REVIEW review.verdict is 'verified' but no execution section exists"))
    elif not execution_results:
        errors.append(make_error("E302", "UNPROVEN_VERIFIED_REVIEW review.verdict is 'verified' but execution_results is empty"))

    unproven = [
        cmd_str for cmd in test_commands
        for cmd_str in [extract_command_string(cmd)]
        if cmd_str and cmd_str.strip() not in passed_commands
    ]
    if unproven:
        errors.append(
            make_error("E302", f"UNPROVEN_VERIFIED_REVIEW review.verdict is 'verified' "
            f"but {len(unproven)} test command(s) lack proof: {unproven}")
        )

    # E303 -- ci_status gate (Task 7-04 AUDIT-032: strengthened to reject anything not explicitly 'green')
    ci_status_val = as_dict(review.get("fixture_status")).get("ci_status")
    if ci_status_val is None:
        errors.append(
            make_error("E303", "CI_GATE_VIOLATION: verdict is 'verified' but review.fixture_status is absent or "
            "review.fixture_status.ci_status is missing -- set ci_status to 'green' or change verdict")
        )
    elif ci_status_val != "green":
        errors.append(
            make_error("E303", f"CI_GATE_VIOLATION: verdict is 'verified' but review.fixture_status.ci_status is '{ci_status_val}' -- "
            "set fixture_status.ci_status to 'green' or change verdict")
        )


def _realised_criteria(checklist: list[dict[str, Any]]) -> set[str]:
    """Every criterion id some plan item ``realises``."""
    return {cid for item in checklist for cid in str_items(item.get("realises"))}


def _is_set_aside(task: dict[str, Any]) -> bool:
    """True when the roadmap task carries a ``disposition`` of ``deferred`` or ``wont_do`` (paused or cancelled, not absent)."""
    return str_in(as_dict(task.get("disposition")).get("value"), PAUSED_OR_CANCELLED_DISPOSITIONS)


def _check_roadmap_coverage(data: dict[str, Any], checklist: list[dict[str, Any]], roadmap: dict[str, Any], errors: list[SpecError]) -> None:
    """E304: the plan's ``milestone`` names a roadmap milestone, and each of its tasks has a criterion some item realises.

    A task set aside by its ``disposition`` (deferred or wont_do) needs no item. A plan without a ``milestone`` has no
    scope to check: the schema reports the missing key.
    """
    milestone_id = data.get("milestone")
    if not isinstance(milestone_id, str):
        return
    milestone = next((m for m in dict_items(roadmap.get("milestones")) if m.get("milestone_id") == milestone_id), None)
    if milestone is None:
        errors.append(make_error("E304", f"ROADMAP_MILESTONE_UNKNOWN: plan milestone '{milestone_id}' is not a milestone of 14_roadmap.json"))
        return
    realised = _realised_criteria(checklist)
    for task in dict_items(milestone.get("tasks")):
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or _is_set_aside(task):
            continue
        criteria = {c["criterion_id"] for c in dict_items(task.get("acceptance_criteria")) if isinstance(c.get("criterion_id"), str)}
        if not criteria & realised:
            errors.append(
                make_error("E304", f"ROADMAP_TASK_UNCOVERED: roadmap task '{task_id}' of milestone '{milestone_id}' has no plan item that realises one of its acceptance criteria")
            )


# M8 rewrites
def _check_planned_vs_executed(data: dict[str, Any], checklist: list[dict[str, Any]], errors: list[SpecError]) -> None:
    """E305 PLANNED_UNEXECUTED: a green legacy plan lists an active item that ``critical_evidence`` does not satisfy.

    Runs only when a plan item carries ``implementation.status``; the 1.2.0 shape stores neither.
    """
    if not any(_legacy_status(item) for item in checklist):
        return
    execution = as_dict(data.get("execution"))
    if as_dict(execution.get("final_status")).get("ci_status") != "green":
        return
    satisfied_ids = set(str_items(as_dict(execution.get("critical_evidence")).get("satisfied_checklist_ids")))
    for item in sorted(checklist, key=lambda i: str(i.get("id"))):
        item_id = item.get("id")
        if not isinstance(item_id, str) or str_in(item.get("checklist_status"), PAUSED_OR_CANCELLED_CHECKLIST_STATUSES):
            continue
        if item_id in satisfied_ids:
            continue
        test_hint = item.get("linked_test_expectation")
        suffix = f" (expected test: {test_hint})" if test_hint else ""
        errors.append(
            make_error("E305", f"PLANNED_UNEXECUTED: checklist item '{item_id}' is active but not in satisfied_checklist_ids{suffix}")
        )


def _check_fr_coverage_against_step_04(data: dict[str, Any], spec_path: str, errors: list[SpecError]) -> None:
    """E306: every ``review.semantic_review.fr_coverage[].fr_id`` is a functional requirement of Step 04."""
    fr_coverage = as_dict(as_dict(data.get("review")).get("semantic_review")).get("fr_coverage")
    if not isinstance(fr_coverage, list) or not fr_coverage:
        return
    artifact_path = Path(spec_path)
    # When artifact lives inside impl_context/, step 04 is one level up
    fr_base = artifact_path.parent.parent if artifact_path.parent.name == "impl_context" else artifact_path.parent
    fr_list_path = fr_base / "04_fr_list.json"
    if not fr_list_path.exists():
        return
    try:
        fr_data = json.loads(fr_list_path.read_text())
    except (OSError, json.JSONDecodeError):
        return  # Step 04 unreadable -- skip E306
    known_fr_ids = {fr["fr_id"] for fr in dict_items(as_dict(fr_data).get("functional_requirements")) if isinstance(fr.get("fr_id"), str) and fr["fr_id"]}
    for entry in dict_items(fr_coverage):
        fr_id = entry.get("fr_id")
        if isinstance(fr_id, str) and fr_id not in known_fr_ids:
            errors.append(
                make_error("E306", f"SEMANTIC_REVIEW_FR_MISMATCH: "
                f"fr_coverage references '{fr_id}' "
                f"not found in 04_fr_list.json")
            )


def _check_roadmap(data: dict[str, Any], checklist: list[dict[str, Any]], spec_path: str, errors: list[SpecError]) -> None:
    """Load ``14_roadmap.json`` beside *spec_path* and run E304 on it (a 16a plan, never the anchor)."""
    try:
        roadmap = _load_roadmap(spec_path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(make_error("E304", f"ROADMAP_PARSE_ERROR: could not load 14_roadmap.json: {exc}"))
        return
    if isinstance(roadmap, dict):
        _check_roadmap_coverage(data, checklist, roadmap, errors)
    elif roadmap is not None:
        errors.append(make_error("E304", "ROADMAP_STRUCTURE_ERROR: 14_roadmap.json is not an object"))


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
    _check_legacy_verified_items(checklist, errors)
    _check_target_patterns_and_scope(data, plan, checklist, errors)
    _check_docs_impact(plan, checklist, spec_path, spec_root, errors)
    # E307 keys on `spec_ref`, which the 1.2.0 plan item no longer has: it finds nothing there. # M8 rewrites
    _check_behavior_validation_pairing(checklist, errors)
    _check_proof_closure(data, plan, errors)
    if spec_path and not _is_anchor(spec_path, data):
        _check_roadmap(data, checklist, spec_path, errors)
    _check_planned_vs_executed(data, checklist, errors)
    if spec_path:
        _check_fr_coverage_against_step_04(data, spec_path, errors)

    return errors
