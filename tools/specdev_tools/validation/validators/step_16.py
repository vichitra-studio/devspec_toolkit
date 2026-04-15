from __future__ import annotations

from typing import List, Dict, Any, Optional
import hashlib
import json
import os
import re
from pathlib import Path

from ...core.errors import make_error, SpecError

# Checklist type and layer enums — currently hardcoded.  These values mirror the
# enum constraints in schema/16_scaffold.schema.json (``checklist[].type`` and
# ``checklist[].layer``).  Loading them dynamically from canon/kinds/ is not
# practical: the values are schema-level enums, not canonical vocabulary entries,
# and the schema is the single source of truth.  See AUDIT-023.
VALID_CHECKLIST_TYPES = frozenset({"behavior", "constraint", "validation", "metadata", "perf", "logging", "docs", "security", "config"})
VALID_CHECKLIST_LAYERS = frozenset({"db", "model", "service", "api", "integration", "tests", "docs", "config", "security"})
TYPES_REQUIRING_PROOF = frozenset({"behavior", "constraint", "validation", "perf", "security"})

# Success marker keywords for evidence content validation (Task 7-03 AUDIT-070)
_SUCCESS_MARKERS: tuple[str, ...] = ("PASS", "OK", "passed", "success", "0 failures")

# Spec artifact ID pattern for evidence binding validation (AUDIT-032)
_ARTIFACT_ID_RE = re.compile(r'\b(?:fr|api|nfr|inv)-[a-z0-9-]+\b')

# Cache for step_16 validation results by content hash.  When step_16a, 16b,
# and 16c each call validate_step_16(), the first call computes the result and
# subsequent calls for the same artifact return cached results.  This prevents
# the triple execution overhead without changing the public API (AUDIT-029).
_step16_cache: Dict[str, list[SpecError]] = {}

def _find_seed_manifest(spec_path: Optional[str], toolkit_root: str) -> Optional[str]:
    if spec_path:
        cur = os.path.abspath(os.path.dirname(spec_path))
        while True:
            cand = os.path.join(cur, "spec", "common", "seed_manifest.json")
            if os.path.exists(cand):
                return cand
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent

    fallback = os.path.join(toolkit_root, "spec", "common", "seed_manifest.json")
    if os.path.exists(fallback):
        return fallback
    return None


def _is_anchor(spec_path: Optional[str], data: Optional[Dict[str, Any]] = None) -> bool:
    """Detect whether this artifact is the Step 16 Trinity Anchor (vs. a 16a/16b/16c plan).

    Prefers field-based detection (artifact_role) when available;
    falls back to path heuristic: anchor lives at spec/16_impl_context.json,
    plans live inside spec/impl_context/.
    # TODO: upgrade to artifact_role field check exclusively after Task 2.7 (vc:16-anchor schema).
    """
    if data and data.get("artifact_role") == "anchor":
        return True
    if not spec_path:
        return False
    p = Path(spec_path)
    return p.name == "16_impl_context.json" and p.parent.name != "impl_context"


def _load_roadmap(spec_path: str) -> Optional[Dict[str, Any]]:
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


def _check_behavior_validation_pairing(checklist: List[Dict[str, Any]], errors: list[SpecError]) -> None:
    """E307: For every behavioral spec ref (fr, api, inv, nfr), ensure at least one behavior and one validation item.

    Groups non-deferred checklist items by their spec_ref.id and checks that each
    group has both a 'behavior' and a 'validation' type item.
    Non-behavioral spec_ref types ('doc', 'code') are excluded — these are work items,
    not testable behaviors, and do not require behavior+validation pairing.
    """
    from collections import defaultdict

    groups: Dict[str, set] = defaultdict(set)
    for item in checklist:
        if not isinstance(item, dict):
            continue
        if item.get("checklist_status") == "deferred":
            continue
        spec_ref = item.get("spec_ref")
        if not isinstance(spec_ref, dict):
            continue
        ref_id = spec_ref.get("id")
        if not ref_id:
            continue
        # Skip non-behavioral spec_ref types (doc, code) — work items, not testable behaviors
        if spec_ref.get("type") in {"doc", "code"}:
            continue
        item_type = item.get("type", "")
        if item_type:
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


def validate_step_16(data: Dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None) -> list[SpecError]:
    """
    Deep validation for Step 16 (Implementation Context).

    Args:
        data: The parsed JSON content of the step file.
        toolkit_root: The root directory of the toolkit (for resolving references).

    Returns:
        List of SpecError objects. Empty list if valid.
    """
    # Cache lookup: hash data + spec_path to detect identical invocations from 16a/16b/16c
    cache_input = json.dumps(data, sort_keys=True) + "\0" + (spec_path or "")
    cache_key = hashlib.md5(cache_input.encode()).hexdigest()
    if cache_key in _step16_cache:
        return list(_step16_cache[cache_key])  # Return a copy

    errors: list[SpecError] = []

    plan = data.get("plan", {})
    checklist = plan.get("spec_alignment", {}).get("checklist", [])
    docs_impact = plan.get("docs_impact")

    for item in checklist:
        impl = item.get("implementation", {})
        status = impl.get("status")
        item_id = item.get("id", "unknown")
        checklist_status = item.get("checklist_status", "active")

        # Logic Check: New checklist types and layers
        item_type = item.get("type", "")
        item_layer = item.get("layer", "")

        if item_type not in VALID_CHECKLIST_TYPES:
            errors.append(make_error("E530", f"Checklist item '{item_id}' has invalid type '{item_type}'. Must be one of: {', '.join(sorted(VALID_CHECKLIST_TYPES))}"))

        if item_layer not in VALID_CHECKLIST_LAYERS:
            errors.append(make_error("E530", f"Checklist item '{item_id}' has invalid layer '{item_layer}'. Must be one of: {', '.join(sorted(VALID_CHECKLIST_LAYERS))}"))

        # Logic Check: New checklist fields (nfr_refs, fixture_ref) required for non-deferred items
        # Only types that have measurable NFR/fixture associations require proof; types like
        # docs, metadata, logging, and config legitimately have no NFR or fixture link.
        if checklist_status != "deferred" and item_type in TYPES_REQUIRING_PROOF:
            nfr_refs = item.get("nfr_refs", [])
            if not nfr_refs:
                errors.append(make_error("E520", f"Checklist item '{item_id}' is not deferred but has no nfr_refs"))

            fixture_ref = item.get("fixture_ref")
            if not fixture_ref:
                errors.append(make_error("E520", f"Checklist item '{item_id}' is not deferred but has no fixture_ref"))

        # Logic Check: Verified/In-Progress items must have actions
        if status in ["verified", "in_progress"]:
            actions = impl.get("actions", [])
            if not actions and status == "verified":
                 # Strict check: Verified items must have actions documenting what was done
                 errors.append(make_error("E301", f"Checklist item '{item_id}' is 'verified' but has no actions."))

            # Logic Check: Verified items must have evidence for at least one action if actions exist
            # Task 7-03 (AUDIT-070) + Task 7-04 (AUDIT-032): evidence content quality + binding
            if status == "verified" and actions:
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
                    # AUDIT-032: check that evidence content references at least one spec artifact ID
                    if isinstance(evidence, dict):
                        combined = " ".join(filter(None, [
                            evidence.get("content") if isinstance(evidence.get("content"), str) else "",
                            evidence.get("stdout") if isinstance(evidence.get("stdout"), str) else "",
                            evidence.get("stderr") if isinstance(evidence.get("stderr"), str) else "",
                        ]))
                        if combined and not _ARTIFACT_ID_RE.search(combined):
                            errors.append(make_error("W601", f"EVIDENCE_NO_ARTIFACT_REF: evidence in checklist item '{item_id}' action '{action.get('type', 'unknown')}' does not reference any spec artifact ID (fr-*, api-*, nfr-*, inv-*)"))
                if not has_evidence:
                    errors.append(make_error("E301", f"Checklist item '{item_id}' is 'verified' but contains no evidence in any action."))

    # Logic Check: Ensure target_file_patterns cover touched files
    summary_patterns = set(plan.get("summary", {}).get("target_file_patterns", []))

    # Collect all files touched in actions (implementation.files_touched per checklist item)
    actually_touched = set()
    for item in checklist:
        impl = item.get("implementation", {})
        if impl.get("status") in ["in_progress", "verified"]:
            for f in impl.get("files_touched", []):
                actually_touched.add(f)

    # Task 7-09 (AUDIT-087): also collect files from execution.files_touched
    execution_block = data.get("execution", {})
    execution_files: set[str] = set()
    if isinstance(execution_block, dict):
        for f in execution_block.get("files_touched", []):
            if isinstance(f, str):
                actually_touched.add(f)
                execution_files.add(f)

    # AUDIT-087: Scope-binding check — warn if execution.files_touched contains files
    # not declared in any checklist item's implementation.files_touched.
    # Such files are outside any specific task's tracked scope.
    checklist_declared_files: set[str] = set()
    for item in checklist:
        impl = item.get("implementation", {})
        for f in impl.get("files_touched", []):
            if isinstance(f, str):
                checklist_declared_files.add(f)
    for f in execution_files:
        if f not in checklist_declared_files:
            errors.append(make_error("W603", f"FILES_OUTSIDE_TASK_SCOPE: execution file '{f}' is not declared in any checklist item's files_touched — may be outside task scope"))

    # Logic: Warn if files are touched but not in target_file_patterns
    import fnmatch

    for f in actually_touched:
        matched = False
        for pattern in summary_patterns:
            if fnmatch.fnmatch(f, pattern):
                matched = True
                break

        if not matched:
            errors.append(make_error("E520", f"File '{f}' is touched by implementation but not covered by target_file_patterns."))

    manifest_path = _find_seed_manifest(spec_path, toolkit_root)
    doc_patterns: List[str] = []
    doc_patterns_valid = False
    if manifest_path:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            doc_patterns = manifest.get("doc_paths", []) or []
            doc_patterns_valid = isinstance(doc_patterns, list) and len(doc_patterns) > 0
            if not doc_patterns_valid:
                errors.append(make_error("W570", "seed_manifest.json missing doc_paths; cannot validate docs_impact doc paths."))
        except Exception:
            errors.append(make_error("W570", "Failed to read seed_manifest.json; cannot validate docs_impact doc paths."))
    else:
        errors.append(make_error("W570", "seed_manifest.json not found; cannot validate docs_impact doc paths."))

    def is_doc_path(path: str) -> bool:
        if not path:
            return False
        if not doc_patterns_valid:
            return False
        norm = path.replace("\\", "/").lstrip("./")
        for pattern in doc_patterns:
            if fnmatch.fnmatch(norm, pattern):
                return True
        return False

    code_change_targets = []
    for item in checklist:
        impl = item.get("implementation", {})
        for action in impl.get("actions", []):
            if action.get("type") in ["file_create", "file_edit"]:
                target = action.get("target", "")
                if target and not is_doc_path(target):
                    code_change_targets.append(target)

    if code_change_targets:
        if not isinstance(docs_impact, dict):
            errors.append(make_error("E520", "plan.docs_impact is required when code changes are present."))
        else:
            status = docs_impact.get("status")
            if status != "required":
                errors.append(make_error("E520", "plan.docs_impact.status must be 'required' when code changes are present."))
            docs_touched = docs_impact.get("docs_touched", [])
            if not docs_touched:
                errors.append(make_error("E520", "plan.docs_impact.docs_touched must be provided when code changes are present."))
            elif doc_patterns_valid:
                for doc_path in docs_touched:
                    if not is_doc_path(doc_path):
                        errors.append(make_error("E520", f"plan.docs_impact.docs_touched contains non-doc path: {doc_path}"))

    # E307: Behavior->validation pairing -- every roadmap task must have at least one
    # checklist item of type "behavior" and one of type "validation"
    _check_behavior_validation_pairing(checklist, errors)

    # D22: Command-to-proof linkage -- active plans must prove test commands passed
    plan_status = plan.get("status")
    review_reqs = plan.get("review_requirements", {})
    test_commands = review_reqs.get("test_commands", []) if isinstance(review_reqs, dict) else []
    execution = data.get("execution", {})
    execution_results = execution.get("execution_results", []) if isinstance(execution, dict) else []

    passed_commands: set[str] = set()
    for result in execution_results:
        if isinstance(result, dict) and result.get("status") == "passed":
            cmd = result.get("command")
            if isinstance(cmd, str):
                passed_commands.add(cmd.strip())

    if plan_status == "active" and test_commands and execution_results:
        for cmd in test_commands:
            if isinstance(cmd, str) and cmd.strip() not in passed_commands:
                errors.append(
                    make_error("E301", f"MISSING_PROOF_CLOSURE test command '{cmd}' required "
                    f"by review_requirements but not found in execution_results with status=passed")
                )

    # D23: Verified review without proof closure
    review = data.get("review", {})
    verdict = review.get("verdict") if isinstance(review, dict) else None
    if verdict == "verified":
        if not execution or not isinstance(execution, dict):
            errors.append(
                make_error("E302", "UNPROVEN_VERIFIED_REVIEW review.verdict is 'verified' "
                "but no execution section exists")
            )
        elif not execution_results:
            errors.append(
                make_error("E302", "UNPROVEN_VERIFIED_REVIEW review.verdict is 'verified' "
                "but execution_results is empty")
            )

        # All test commands must be proven
        if test_commands:
            unproven = [
                cmd for cmd in test_commands
                if isinstance(cmd, str) and cmd.strip() not in passed_commands
            ]
            if unproven:
                errors.append(
                    make_error("E302", f"UNPROVEN_VERIFIED_REVIEW review.verdict is 'verified' "
                    f"but {len(unproven)} test command(s) lack proof: {unproven}")
                )

        # Check critical_evidence consistency
        critical_evidence = execution.get("critical_evidence", {}) if isinstance(execution, dict) else {}
        declared_passed = critical_evidence.get("passed_test_commands", []) if isinstance(critical_evidence, dict) else []
        if isinstance(declared_passed, list) and test_commands:
            declared_set = {c.strip() for c in declared_passed if isinstance(c, str)}
            for cmd in test_commands:
                if isinstance(cmd, str) and cmd.strip() not in declared_set:
                    errors.append(
                        make_error("E302", f"UNPROVEN_VERIFIED_REVIEW test command '{cmd}' "
                        f"not listed in critical_evidence.passed_test_commands")
                    )

    # E303 -- ci_status gate (Task 7-04 AUDIT-032: strengthened to reject anything not explicitly 'green')
    fixture_status = review.get("fixture_status") if isinstance(review, dict) else None
    ci_status_val = fixture_status.get("ci_status") if isinstance(fixture_status, dict) else None
    if verdict == "verified" and ci_status_val != "green":
        if ci_status_val is None:
            errors.append(
                make_error("E303", "CI_GATE_VIOLATION: verdict is 'verified' but review.fixture_status is absent or "
                "review.fixture_status.ci_status is missing -- set ci_status to 'green' or change verdict")
            )
        else:
            errors.append(
                make_error("E303", f"CI_GATE_VIOLATION: verdict is 'verified' but review.fixture_status.ci_status is '{ci_status_val}' -- "
                "set fixture_status.ci_status to 'green' or change verdict")
            )

    # E304 -- roadmap-to-checklist coverage (fires on 16a plans, NOT on the anchor)
    if spec_path and not _is_anchor(spec_path, data):
        try:
            roadmap_data = _load_roadmap(spec_path)
            if roadmap_data is not None:
                # Get milestone_ref from the artifact
                milestone_ref = data.get("milestone_ref", "")
                roadmap_task_ids = set()
                milestone_found = False
                for milestone in roadmap_data.get("milestones", []):
                    mid = milestone.get("milestone_id", "")
                    mstatus = milestone.get("status", "")
                    if milestone_ref:
                        # If milestone_ref is set, only include tasks from that milestone
                        if mid != milestone_ref:
                            continue
                        milestone_found = True
                    else:
                        # If milestone_ref is absent (first Trinity cycle), include only
                        # milestones that are not yet done (active/in-progress)
                        if mstatus in ("done", "completed"):
                            continue
                    for task in milestone.get("tasks", []):
                        tid = task.get("task_id")
                        if tid:
                            roadmap_task_ids.add(tid)
                # E582 -- milestone_ref points to a non-existent roadmap milestone
                roadmap_milestones = roadmap_data.get("milestones", [])
                if milestone_ref and not milestone_found and len(roadmap_milestones) > 0:
                    errors.append(
                        make_error("E582", f"UNCOVERED_FR_REVIEW_COVERAGE: milestone_ref '{milestone_ref}' not found in roadmap milestones")
                    )
                checklist_refs = {
                    item["spec_ref"]["id"]
                    for item in checklist
                    if isinstance(item, dict)
                    and isinstance(item.get("spec_ref"), dict)
                    and item.get("checklist_status") != "deferred"
                }
                unmapped = roadmap_task_ids - checklist_refs
                for task_id in sorted(unmapped):
                    errors.append(
                        make_error("E304", f"ROADMAP_TASK_UNCOVERED: roadmap task '{task_id}' has no checklist item with matching spec_ref.id")
                    )
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(
                make_error("E304", f"ROADMAP_PARSE_ERROR: could not load 14_roadmap.json: {exc}")
            )
        except (KeyError, TypeError) as exc:
            errors.append(
                make_error("E304", f"ROADMAP_STRUCTURE_ERROR: unexpected roadmap structure: {exc}")
            )

    # W581 -- milestone_ref binding validation (skips anchor artifacts)
    if spec_path and not _is_anchor(spec_path, data):
        try:
            roadmap_data_ms = _load_roadmap(spec_path)
            if roadmap_data_ms is not None:
                task_to_milestone: dict[str, str] = {}
                for ms in roadmap_data_ms.get("milestones", []):
                    ms_id = ms.get("milestone_id", "")
                    for task in ms.get("tasks", []):
                        if isinstance(task, dict) and "task_id" in task:
                            task_to_milestone[task["task_id"]] = ms_id

                for item in checklist:
                    if not isinstance(item, dict):
                        continue
                    if item.get("checklist_status") == "deferred":
                        continue
                    item_id = item.get("id", "unknown")
                    milestone_ref = item.get("milestone_ref")
                    spec_ref_id = None
                    if isinstance(item.get("spec_ref"), dict):
                        spec_ref_id = item["spec_ref"].get("id")

                    if milestone_ref is None:
                        errors.append(make_error("W581", f"MILESTONE_REF_MISSING item={item_id}"))
                    elif spec_ref_id and spec_ref_id in task_to_milestone:
                        expected_ms = task_to_milestone[spec_ref_id]
                        if milestone_ref != expected_ms:
                            errors.append(
                                make_error("E582", f"UNCOVERED_FR_REVIEW_COVERAGE milestone_ref mismatch item={item_id} "
                                f"expected={expected_ms} got={milestone_ref}")
                            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            pass  # Roadmap parse errors already handled by E304

    # E305 -- planned-vs-executed diff
    final_status = data.get("execution", {}).get("final_status", {}) if isinstance(data.get("execution"), dict) else {}
    if final_status and final_status.get("ci_status") == "green":
        planned_ids = {
            item["id"] for item in checklist
            if isinstance(item, dict) and item.get("checklist_status") != "deferred" and "id" in item
        }
        critical_evidence_2 = data.get("execution", {}).get("critical_evidence", {}) if isinstance(data.get("execution"), dict) else {}
        satisfied_ids = set(
            critical_evidence_2.get("satisfied_checklist_ids", [])
            if isinstance(critical_evidence_2, dict) else []
        )
        checklist_by_id = {
            item["id"]: item for item in checklist
            if isinstance(item, dict) and "id" in item
        }
        unexecuted = planned_ids - satisfied_ids
        for item_id in sorted(unexecuted):
            item = checklist_by_id.get(item_id, {})
            test_hint = item.get("linked_test_expectation")
            suffix = f" (expected test: {test_hint})" if test_hint else ""
            errors.append(
                make_error("E305", f"PLANNED_UNEXECUTED: checklist item '{item_id}' is active but not in satisfied_checklist_ids{suffix}")
            )

    # E306 -- semantic_review.fr_coverage cross-ref against Step 04
    if spec_path and isinstance(review, dict):
        semantic_review = review.get("semantic_review")
        if isinstance(semantic_review, dict):
            fr_coverage = semantic_review.get("fr_coverage", [])
            if isinstance(fr_coverage, list) and fr_coverage:
                artifact_path = Path(spec_path)
                # When artifact lives inside impl_context/, step 04 is one level up
                _fr_base = (
                    artifact_path.parent.parent
                    if artifact_path.parent.name == "impl_context"
                    else artifact_path.parent
                )
                fr_list_path = _fr_base / "04_fr_list.json"
                if fr_list_path.exists():
                    try:
                        fr_data = json.loads(fr_list_path.read_text())
                        known_fr_ids = {
                            fr.get("fr_id")
                            for fr in fr_data.get("functional_requirements", [])
                            if isinstance(fr, dict) and fr.get("fr_id")
                        }
                        for entry in fr_coverage:
                            if isinstance(entry, dict):
                                fr_id = entry.get("fr_id")
                                if isinstance(fr_id, str) and fr_id not in known_fr_ids:
                                    errors.append(
                                        make_error("E306", f"SEMANTIC_REVIEW_FR_MISMATCH: "
                                        f"fr_coverage references '{fr_id}' "
                                        f"not found in 04_fr_list.json")
                                    )
                    except (OSError, json.JSONDecodeError):
                        pass  # Step 04 unreadable -- skip E306

    _step16_cache[cache_key] = list(errors)  # Cache a copy
    return errors
