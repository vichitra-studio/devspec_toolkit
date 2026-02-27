import json
import os
import re
from typing import List, Dict, Any, Optional, Set

FR_ID_PATTERN = re.compile(r"^fr-[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_04(instance: Dict[str, Any], toolkit_root: str) -> List[str]:
    """
    Validate Step 04 (Functional Requirements) logic.
    Checks for duplicate fr_ids, fr_id format convention, trace presence, and capability_ref cross-validation.
    """
    errors = []
    seen = set()

    for i, req in enumerate(instance.get("functional_requirements", [])):
        fr_id = req.get("fr_id")

        # Check FR ID format convention
        if fr_id:
            if not FR_ID_PATTERN.match(fr_id):
                errors.append(f"FR at index {i} has fr_id '{fr_id}' that does not follow 'fr-<kebab>' convention")
            if fr_id in seen:
                errors.append(f"Duplicate fr_id found: '{fr_id}' at index {i}")
            seen.add(fr_id)

        # Check trace presence and non-empty requirement
        _validate_trace_presence(req, i, fr_id, errors)

    # Cross-step capability_ref validation
    capability_ids = _load_capability_ids(toolkit_root)
    if capability_ids is not None:
        for i, req in enumerate(instance.get("functional_requirements", [])):
            _validate_capability_ref(req, i, capability_ids, errors)

    return errors


def _validate_trace_presence(req: Dict[str, Any], index: int, fr_id: str, errors: List[str]) -> None:
    """
    Validate that each FR item has a non-empty trace array.
    Ensures traceability chain is maintained across downstream consumers.
    """
    trace = req.get("trace")
    if trace is None:
        errors.append(f"FR at index {index} ('{fr_id}') is missing required 'trace' field")
    elif isinstance(trace, list) and len(trace) == 0:
        errors.append(f"FR '{fr_id}' at index {index} has empty 'trace' array; must contain at least one trace reference")


def _validate_capability_ref(req: Dict[str, Any], index: int, capability_ids: set, errors: List[str]) -> None:
    """
    Validate that capability_ref in FR item matches an existing capability ID.
    Ensures FR-to-capability traceability is correct when capability spec exists.
    """
    fr_id = req.get("fr_id", f"<index {index}>")
    capability_ref = req.get("capability_ref")
    if capability_ref and isinstance(capability_ref, str) and capability_ref not in capability_ids:
        errors.append(f"FR '{fr_id}' references unknown capability '{capability_ref}' (not in 01_capabilities.json)")


def _load_capability_ids(toolkit_root: str) -> Optional[Set[str]]:
    """Load capability IDs from step 01 if available."""
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None

    for fn in os.listdir(spec_dir):
        if fn.startswith("01_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    cap.get("capability_id")
                    for cap in data.get("capabilities", [])
                    if isinstance(cap, dict) and cap.get("capability_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None
