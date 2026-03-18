from __future__ import annotations

from typing import List, Dict, Any

from ...core.errors import make_error, SpecError
from ...core.loaders import load_upstream_ids, KEBAB_ID_RE

def validate_step_15(instance: Dict[str, Any], toolkit_root: str) -> list[SpecError]:
    """
    Validate Step 15 (Scaffold) logic.
    Checks build_status enum, route_map uniqueness, and method enums.
    """
    errors: list[SpecError] = []

    # Structure Checks
    required_fields = ["id", "owner", "created_at", "service_skeleton", "route_map", "validators", "build_status"]
    for field in required_fields:
        if field not in instance:
            errors.append(make_error("E520", f"Missing required field: {field}"))

    if "service_skeleton" in instance and not isinstance(instance["service_skeleton"], dict):
        errors.append(make_error("E520", "service_skeleton must be an object"))

    if "route_map" in instance and not isinstance(instance["route_map"], list):
        errors.append(make_error("E520", "route_map must be an array"))

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

    # Validate route_map
    if "route_map" in instance:
        route_map = instance["route_map"]
        seen_api_refs = set()
        kebab_pattern = KEBAB_ID_RE
        valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}

        for i, route in enumerate(route_map):
            if not isinstance(route, dict):
                continue

            api_ref = route.get("api_ref")
            method = route.get("method")

            if api_ref:
                if not kebab_pattern.match(api_ref):
                    errors.append(make_error("E530", f"route_map[{i}].api_ref '{api_ref}' must be kebab-case"))

                if api_ref in seen_api_refs:
                    errors.append(make_error("E520", f"Duplicate api_ref found: '{api_ref}'"))
                seen_api_refs.add(api_ref)

            if method and method not in valid_methods:
                errors.append(make_error("E530", f"route_map[{i}].method '{method}' is invalid. Must be one of {sorted(valid_methods)}"))

    # Cross-step validation: verify api_ref values exist in 05_interface_contracts.json
    api_ids = load_upstream_ids(toolkit_root, "05", "apis", "api_id", fallback_keys=("contracts",))
    if api_ids is None:
        errors.append(make_error("W590", "CROSS_STEP_UPSTREAM_MISSING 05_interface_contracts.json not found; skipping API reference validation"))
    elif "route_map" in instance:
        route_map = instance["route_map"]
        for entry in route_map:
            if not isinstance(entry, dict):
                continue
            api_ref = entry.get("api_ref")
            if api_ref and api_ref not in api_ids:
                errors.append(make_error("E590", f"CROSS_STEP_ID_NOT_FOUND route_map api_ref '{api_ref}' not found in 05_interface_contracts.json"))

    return errors
