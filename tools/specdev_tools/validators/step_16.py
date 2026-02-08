from typing import List, Dict, Any, Optional
import json
import os

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

    return errors
