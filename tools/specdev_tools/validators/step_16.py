from typing import List, Dict, Any, Optional
import os

def validate_step_16(data: Dict[str, Any], toolkit_root: str) -> List[str]:
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

    return errors
