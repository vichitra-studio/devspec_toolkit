from typing import List, Dict, Any, Optional
import json
import os
from pathlib import Path

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


def validate_step_16(data: Dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None) -> List[str]:
    """
    Deep validation for Step 16 (Implementation Context).
    
    Args:
        data: The parsed JSON content of the step file.
        toolkit_root: The root directory of the toolkit (for resolving references).
        
    Returns:
        List of error messages. Empty list if valid.
    """
    errors = []
    
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
        
        if item_type not in ["behavior", "constraint", "validation", "metadata", "perf", "logging", "docs", "security"]:
            errors.append(f"Checklist item '{item_id}' has invalid type '{item_type}'. Must be one of: behavior, constraint, validation, metadata, perf, logging, docs, security")
        
        if item_layer not in ["db", "model", "service", "api", "integration", "tests", "docs", "config", "security"]:
            errors.append(f"Checklist item '{item_id}' has invalid layer '{item_layer}'. Must be one of: db, model, service, api, integration, tests, docs, config, security")
        
        # Logic Check: New checklist fields (nfr_refs, fixture_ref) required for non-deferred items
        if checklist_status != "deferred":
            nfr_refs = item.get("nfr_refs", [])
            if not nfr_refs:
                errors.append(f"Checklist item '{item_id}' is not deferred but has no nfr_refs")
            
            fixture_ref = item.get("fixture_ref")
            if not fixture_ref:
                errors.append(f"Checklist item '{item_id}' is not deferred but has no fixture_ref")
        
        # Logic Check: Verified/In-Progress items must have actions
        if status in ["verified", "in_progress"]:
            actions = impl.get("actions", [])
            if not actions and status == "verified":
                 # Strict check: Verified items must have actions documenting what was done
                 errors.append(f"Checklist item '{item_id}' is 'verified' but has no actions.")
             
            # Logic Check: Verified items must have evidence for at least one action if actions exist
            if status == "verified" and actions:
                has_evidence = False
                for action in actions:
                    if "evidence" in action:
                        has_evidence = True
                        break
                if not has_evidence:
                    errors.append(f"Checklist item '{item_id}' is 'verified' but contains no evidence in any action.")

    # Logic Check: Ensure target_file_patterns cover touched files
    summary_patterns = set(plan.get("summary", {}).get("target_file_patterns", []))
    
    # Collect all files touched in actions
    actually_touched = set()
    for item in checklist:
        impl = item.get("implementation", {})
        if impl.get("status") in ["in_progress", "verified"]:
            for f in impl.get("files_touched", []):
                actually_touched.add(f)
                
    # Logic: Warn if files are touched but not in target_file_patterns
    # For now, we won't implement complex glob matching in this audit step because we don't want to add fnmatch overhead
    # But we can check for direct matches if patterns are simple paths
    # Or just skip this check if we want to be lenient.
    # Let's implement a simple check: if the file is NOT in the patterns list EXACTLY, we flag it.
    # This encourages specific file listing or explicit patterns.
    # Note: This is a strict interpretation. If users rely on patterns like "*.py", this strict check will fail.
    # So we probably should skip this strict check unless we import fnmatch.
    
    import fnmatch
    
    for f in actually_touched:
        matched = False
        for pattern in summary_patterns:
            if fnmatch.fnmatch(f, pattern):
                matched = True
                break
        
        if not matched:
            errors.append(f"File '{f}' is touched by implementation but not covered by target_file_patterns.")

    manifest_path = _find_seed_manifest(spec_path, toolkit_root)
    doc_patterns: List[str] = []
    doc_patterns_valid = False
    if manifest_path:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            doc_patterns = manifest.get("docs_policy", {}).get("doc_paths", []) or []
            doc_patterns_valid = isinstance(doc_patterns, list) and len(doc_patterns) > 0
            if not doc_patterns_valid:
                errors.append("seed_manifest.json missing docs_policy.doc_paths; cannot validate docs_impact doc paths.")
        except Exception:
            errors.append("Failed to read seed_manifest.json; cannot validate docs_impact doc paths.")
    else:
        errors.append("seed_manifest.json not found; cannot validate docs_impact doc paths.")

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
            errors.append("plan.docs_impact is required when code changes are present.")
        else:
            status = docs_impact.get("status")
            if status != "required":
                errors.append("plan.docs_impact.status must be 'required' when code changes are present.")
            docs_touched = docs_impact.get("docs_touched", [])
            if not docs_touched:
                errors.append("plan.docs_impact.docs_touched must be provided when code changes are present.")
            elif doc_patterns_valid:
                for doc_path in docs_touched:
                    if not is_doc_path(doc_path):
                        errors.append(f"plan.docs_impact.docs_touched contains non-doc path: {doc_path}")

    # D22: Command-to-proof linkage — active plans must prove test commands passed
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
                    f"E301 MISSING_PROOF_CLOSURE test command '{cmd}' required "
                    f"by review_requirements but not found in execution_results with status=passed"
                )

    # D23: Verified review without proof closure
    review = data.get("review", {})
    verdict = review.get("verdict") if isinstance(review, dict) else None
    if verdict == "verified":
        if not execution or not isinstance(execution, dict):
            errors.append(
                "E302 UNPROVEN_VERIFIED_REVIEW review.verdict is 'verified' "
                "but no execution section exists"
            )
        elif not execution_results:
            errors.append(
                "E302 UNPROVEN_VERIFIED_REVIEW review.verdict is 'verified' "
                "but execution_results is empty"
            )

        # All test commands must be proven
        if test_commands:
            unproven = [
                cmd for cmd in test_commands
                if isinstance(cmd, str) and cmd.strip() not in passed_commands
            ]
            if unproven:
                errors.append(
                    f"E302 UNPROVEN_VERIFIED_REVIEW review.verdict is 'verified' "
                    f"but {len(unproven)} test command(s) lack proof: {unproven}"
                )

        # Check critical_evidence consistency
        critical_evidence = execution.get("critical_evidence", {}) if isinstance(execution, dict) else {}
        declared_passed = critical_evidence.get("passed_test_commands", []) if isinstance(critical_evidence, dict) else []
        if isinstance(declared_passed, list) and test_commands:
            declared_set = {c.strip() for c in declared_passed if isinstance(c, str)}
            for cmd in test_commands:
                if isinstance(cmd, str) and cmd.strip() not in declared_set:
                    errors.append(
                        f"E302 UNPROVEN_VERIFIED_REVIEW test command '{cmd}' "
                        f"not listed in critical_evidence.passed_test_commands"
                    )

    # E303 — ci_status gate
    fixture_status = review.get("fixture_status") if isinstance(review, dict) else None
    ci_status_val = fixture_status.get("ci_status") if isinstance(fixture_status, dict) else None
    if verdict == "verified" and (ci_status_val is None or ci_status_val == "red"):
        if ci_status_val is None:
            errors.append(
                "E303 CI_GATE_VIOLATION: verdict is 'verified' but review.fixture_status is absent or "
                "review.fixture_status.ci_status is missing — set ci_status to 'green' or change verdict"
            )
        else:
            errors.append(
                "E303 CI_GATE_VIOLATION: verdict is 'verified' but review.fixture_status.ci_status is 'red' — "
                "set fixture_status.ci_status to 'green' or change verdict"
            )

    # E304 — roadmap-to-checklist coverage
    if spec_path:
        artifact_path = Path(spec_path)
        roadmap_path = artifact_path.parent / "14_roadmap.json"
        if not roadmap_path.exists():
            pass  # Roadmap is optional in pre-roadmap phases — skip E304 silently
        else:
            try:
                roadmap_data = json.loads(roadmap_path.read_text())
                roadmap_task_ids = {
                    task["task_id"]
                    for milestone in roadmap_data.get("milestones", [])
                    for task in milestone.get("tasks", [])
                    if isinstance(task, dict) and "task_id" in task
                }
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
                        f"E304 ROADMAP_TASK_UNCOVERED: roadmap task '{task_id}' has no checklist item with matching spec_ref.id"
                    )
            except Exception:
                pass  # malformed roadmap — skip silently

    # E305 — planned-vs-executed diff
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
                f"E305 PLANNED_UNEXECUTED: checklist item '{item_id}' is active but not in satisfied_checklist_ids{suffix}"
            )

    return errors