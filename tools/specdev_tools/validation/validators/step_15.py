import json
import os
import re
from typing import List, Dict, Any, Optional, Set

def validate_step_15(instance: Dict[str, Any], toolkit_root: str) -> List[str]:
    """
    Validate Step 15 (Scaffold) logic.
    Checks build_status enum, route_map uniqueness, and method enums.
    """
    errors = []
    
    # Structure Checks
    required_fields = ["id", "owner", "created_at", "service_skeleton", "route_map", "validators", "build_status"]
    for field in required_fields:
        if field not in instance:
            errors.append(f"Missing required field: {field}")
            
    if "service_skeleton" in instance and not isinstance(instance["service_skeleton"], dict):
        errors.append("service_skeleton must be an object")
    
    if "route_map" in instance and not isinstance(instance["route_map"], list):
        errors.append("route_map must be an array")
        
    if "validators" in instance and not isinstance(instance["validators"], list):
        errors.append("validators must be an array")

    # Validate build_status
    valid_status = {"pending", "green", "red"}
    status = instance.get("build_status")
    if status and status not in valid_status:
        errors.append(f"Invalid build_status '{status}'. Must be one of {sorted(valid_status)}")
        
    # Logic: Green requires validators
    if status == "green":
        validators = instance.get("validators")
        if not validators or len(validators) == 0:
            errors.append("Build status is 'green' but 'validators' list is empty. Green status requires at least one validator.")
        
    # Validate route_map
    if "route_map" in instance:
        route_map = instance["route_map"]
        seen_api_refs = set()
        kebab_pattern = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
        valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
        
        for i, route in enumerate(route_map):
            if not isinstance(route, dict):
                continue
                
            api_ref = route.get("api_ref")
            method = route.get("method")
            
            if api_ref:
                if not kebab_pattern.match(api_ref):
                    errors.append(f"route_map[{i}].api_ref '{api_ref}' must be kebab-case")
                
                if api_ref in seen_api_refs:
                    errors.append(f"Duplicate api_ref found: '{api_ref}'")
                seen_api_refs.add(api_ref)
            
            if method and method not in valid_methods:
                errors.append(f"route_map[{i}].method '{method}' is invalid. Must be one of {sorted(valid_methods)}")

    # Cross-step validation: verify api_ref values exist in 05_interface_contracts.json
    api_ids = _load_api_ids(toolkit_root)
    if api_ids is None:
        errors.append("W590 CROSS_STEP_UPSTREAM_MISSING 05_interface_contracts.json not found; skipping API reference validation")
    elif "route_map" in instance:
        route_map = instance["route_map"]
        for entry in route_map:
            if not isinstance(entry, dict):
                continue
            api_ref = entry.get("api_ref")
            if api_ref and api_ref not in api_ids:
                errors.append(f"E590 CROSS_STEP_ID_NOT_FOUND route_map api_ref '{api_ref}' not found in 05_interface_contracts.json")

    return errors


def _load_api_ids(toolkit_root: str) -> Optional[Set[str]]:
    """Load API IDs from step 05 (interface contracts) if available."""
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None

    for fn in os.listdir(spec_dir):
        if fn.startswith("05_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Support both "apis" (primary) and "contracts" (alternative) array keys
                items = data.get("apis", data.get("contracts", []))
                return {
                    item.get("api_id")
                    for item in items
                    if isinstance(item, dict) and item.get("api_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None
