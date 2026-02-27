import re
from typing import List, Dict, Any

FR_ID_PATTERN = re.compile(r"^fr-[a-z0-9]+(?:-[a-z0-9]+)*$")

def validate_step_04(instance: Dict[str, Any], toolkit_root: str) -> List[str]:
    """
    Validate Step 04 (Functional Requirements) logic.
    Checks for duplicate fr_ids and fr_id format convention.
    """
    errors = []

    # Check for unique fr_id values
    seen = set()

    for i, req in enumerate(instance.get("functional_requirements", [])):
        fr_id = req.get("fr_id")
        if fr_id:
            if not FR_ID_PATTERN.match(fr_id):
                errors.append(f"FR at index {i} has fr_id '{fr_id}' that does not follow 'fr-<kebab>' convention")
            if fr_id in seen:
                errors.append(f"Duplicate fr_id found: '{fr_id}' at index {i}")
            seen.add(fr_id)

    return errors
