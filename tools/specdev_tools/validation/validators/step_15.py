from __future__ import annotations

from typing import List, Dict, Any

from ...core.errors import make_error, SpecError
from ...core.loaders import load_upstream_ids, KEBAB_ID_RE

def validate_step_15(instance: Dict[str, Any], toolkit_root: str) -> list[SpecError]:
    """
    Validate Step 15 (Scaffold) logic.
    Checks build_status enum, interface_map uniqueness, and method enums.
    """
    errors: list[SpecError] = []

    # Structure Checks
    required_fields = ["id", "owner", "created_at", "project_skeleton", "validators", "build_status"]
    for field in required_fields:
        if field not in instance:
            errors.append(make_error("E520", f"Missing required field: {field}"))

    if "project_skeleton" in instance and not isinstance(instance["project_skeleton"], dict):
        errors.append(make_error("E520", "project_skeleton must be an object"))

    if "interface_map" in instance and not isinstance(instance["interface_map"], list):
        errors.append(make_error("E520", "interface_map must be an array"))

    if "validators" in instance and not isinstance(instance["validators"], list):
        errors.append(make_error("E520", "validators must be an array"))

    # Validate build_status
    valid_status = {"pending", "green", "red"}
    status = instance.get("build_status")
    if status and status not in valid_status:
        errors.append(make_error("E530", f"Invalid build_status '{status}'. Must be one of {sorted(valid_status)}"))

    # Logic: Green requires validators
    if status == "green":
        validators = instance.get("validators")
        if not validators or len(validators) == 0:
            errors.append(make_error("E520", "Build status is 'green' but 'validators' list is empty. Green status requires at least one validator."))

    # Validate interface_map
    if "interface_map" in instance:
        interface_map = instance["interface_map"]
        seen_interface_refs = set()
        kebab_pattern = KEBAB_ID_RE
        valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}

        for i, route in enumerate(interface_map):
            if not isinstance(route, dict):
                continue

            interface_ref = route.get("interface_ref")
            method = route.get("method")

            if interface_ref:
                if not kebab_pattern.match(interface_ref):
                    errors.append(make_error("E530", f"interface_map[{i}].interface_ref '{interface_ref}' must be kebab-case"))

                if interface_ref in seen_interface_refs:
                    errors.append(make_error("E520", f"Duplicate interface_ref found: '{interface_ref}'"))
                seen_interface_refs.add(interface_ref)

            if method and method not in valid_methods:
                errors.append(make_error("E530", f"interface_map[{i}].method '{method}' is invalid. Must be one of {sorted(valid_methods)}"))

    # Cross-step validation: verify interface_ref values exist in 05_interface_contracts.json
    api_ids = load_upstream_ids(toolkit_root, "05", "apis", "api_id", fallback_keys=("contracts",))
    if api_ids is None:
        errors.append(make_error("W590", "CROSS_STEP_UPSTREAM_MISSING 05_interface_contracts.json not found; skipping API reference validation"))
    elif "interface_map" in instance:
        interface_map = instance["interface_map"]
        for entry in interface_map:
            if not isinstance(entry, dict):
                continue
            interface_ref = entry.get("interface_ref")
            if interface_ref and interface_ref not in api_ids:
                errors.append(make_error("E590", f"CROSS_STEP_ID_NOT_FOUND interface_map interface_ref '{interface_ref}' not found in 05_interface_contracts.json"))

    return errors
