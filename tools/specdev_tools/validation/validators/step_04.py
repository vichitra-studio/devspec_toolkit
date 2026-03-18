from __future__ import annotations

from typing import List, Dict, Any

from ...core.errors import make_error, SpecError
from ...core.loaders import load_upstream_ids, kebab_id_re
from ...validation.linter_utils import check_no_duplicates

FR_ID_PATTERN = kebab_id_re("fr")


def validate_step_04(instance: Dict[str, Any], toolkit_root: str) -> list[SpecError]:
    """
    Validate Step 04 (Functional Requirements) logic.
    Checks for duplicate fr_ids, fr_id format convention, trace presence, and capability_ref cross-validation.
    """
    errors: list[SpecError] = []

    check_no_duplicates(instance.get("functional_requirements", []), "fr_id", "fr_id", errors)

    for i, req in enumerate(instance.get("functional_requirements", [])):
        fr_id = req.get("fr_id")

        # Check FR ID format convention
        if fr_id:
            if not FR_ID_PATTERN.match(fr_id):
                errors.append(make_error("E530", f"FR at index {i} has fr_id '{fr_id}' that does not follow 'fr-<kebab>' convention"))

        # Check trace presence and non-empty requirement
        _validate_trace_presence(req, i, fr_id, errors)

    # Cross-step capability_ref validation
    capability_ids = load_upstream_ids(toolkit_root, "01", "capabilities", "capability_id")
    if capability_ids is not None:
        for i, req in enumerate(instance.get("functional_requirements", [])):
            _validate_capability_ref(req, i, capability_ids, errors)

    return errors


def _validate_trace_presence(req: Dict[str, Any], index: int, fr_id: str, errors: list[SpecError]) -> None:
    """
    Validate that each FR item has a non-empty trace array.
    Ensures traceability chain is maintained across downstream consumers.
    """
    trace = req.get("trace")
    if trace is None:
        errors.append(make_error("E520", f"FR at index {index} ('{fr_id}') is missing required 'trace' field"))
    elif isinstance(trace, list) and len(trace) == 0:
        errors.append(make_error("E520", f"FR '{fr_id}' at index {index} has empty 'trace' array; must contain at least one trace reference"))


def _validate_capability_ref(req: Dict[str, Any], index: int, capability_ids: set, errors: list[SpecError]) -> None:
    """
    Validate that capability_ref in FR item matches an existing capability ID.
    Ensures FR-to-capability traceability is correct when capability spec exists.
    """
    fr_id = req.get("fr_id", f"<index {index}>")
    capability_ref = req.get("capability_ref")
    if capability_ref and isinstance(capability_ref, str) and capability_ref not in capability_ids:
        errors.append(make_error("E590", f"FR '{fr_id}' references unknown capability '{capability_ref}' (not in 01_capabilities.json)"))
