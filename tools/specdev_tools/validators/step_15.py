from typing import List, Dict, Any
import re

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

    return errors
