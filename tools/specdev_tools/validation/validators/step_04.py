from __future__ import annotations

from typing import Dict, Any

from ...core.errors import make_error, SpecError
from ...core.loaders import load_upstream_ids, kebab_id_re
from ...core.scope_helpers import dict_items

FR_ID_PATTERN = kebab_id_re("fr")


def validate_step_04(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    """
    Validate Step 04 (Functional Requirements) logic.
    Checks the fr_id format convention, and capability_ref cross-validation.
    """
    errors: list[SpecError] = []

    requirements = dict_items(instance.get("functional_requirements"))

    for i, req in enumerate(requirements):
        fr_id = req.get("fr_id")

        # Check FR ID format convention
        if isinstance(fr_id, str) and fr_id:
            if not FR_ID_PATTERN.match(fr_id):
                errors.append(make_error("E530", f"FR at index {i} has fr_id '{fr_id}' that does not follow 'fr-<kebab>' convention"))

    # Cross-step capability_ref validation
    capability_ids = load_upstream_ids(toolkit_root, "01", "capabilities", "capability_id", spec_root=spec_root)
    if capability_ids is not None:
        for i, req in enumerate(requirements):
            _validate_capability_ref(req, i, capability_ids, errors)

    return errors


def _validate_capability_ref(req: Dict[str, Any], index: int, capability_ids: set, errors: list[SpecError]) -> None:
    """
    Validate that capability_ref in FR item matches an existing capability ID.
    Ensures FR-to-capability traceability is correct when capability spec exists.
    """
    fr_id = req.get("fr_id", f"<index {index}>")
    capability_ref = req.get("capability_ref")
    if capability_ref and isinstance(capability_ref, str) and capability_ref not in capability_ids:
        errors.append(make_error("E590", f"FR '{fr_id}' references unknown capability '{capability_ref}' (not in 01_capabilities.json)"))
