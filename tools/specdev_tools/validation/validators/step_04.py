from typing import List, Dict, Any

def validate_step_04(instance: Dict[str, Any], toolkit_root: str) -> List[str]:
    """
    Validate Step 04 (Functional Requirements) logic.
    Checks for duplicate fr_ids.
    """
    errors = []
    
    # Check for unique fr_id values
    fr_ids = []
    seen = set()
    
    for i, req in enumerate(instance.get("functional_requirements", [])):
        fr_id = req.get("fr_id")
        if fr_id:
            if fr_id in seen:
                errors.append(f"Duplicate fr_id found: '{fr_id}' at index {i}")
            seen.add(fr_id)
            
    return errors
