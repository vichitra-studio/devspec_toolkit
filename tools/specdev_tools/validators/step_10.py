from typing import List, Dict, Any
import re

def validate_step_10(instance: Dict[str, Any], toolkit_root: str) -> List[str]:
    """
    Validate Step 10 (Governance) logic.
    Checks owners, enums, regex patterns, and trace/link structure.
    """
    errors = []
    
    # Validate owner
    allowed_owners = {"api", "ui", "system", "ops", "data", "product", "business", "engineering"}
    owner = instance.get("owner")
    if owner and owner not in allowed_owners:
        errors.append(f"Invalid owner '{owner}'. Must be one of {sorted(allowed_owners)}")
        
    # Validate commit_message_rules
    if "commit_message_rules" in instance:
        rules = instance["commit_message_rules"]
        if "pattern" in rules:
            try:
                re.compile(rules["pattern"])
            except re.error as e:
                errors.append(f"Invalid regex pattern in commit_message_rules: {e}")

    # Validate pr_rules
    if "pr_rules" in instance:
        allowed_rules = {
            "validate", "validate-all", "matrix", "fixtures-lint", 
            "invariants-check", "governance-check", "test", "build", 
            "lint", "format", "audit", "security"
        }
        for i, rule in enumerate(instance["pr_rules"]):
            if rule not in allowed_rules:
                errors.append(f"Invalid pr_rule '{rule}' at index {i}. Must be one of {sorted(allowed_rules)}")

    # Validate trace types
    if "trace" in instance:
        allowed_types = {"fr", "api", "nfr", "inv", "fixture", "doc", "capability"}
        for i, item in enumerate(instance["trace"]):
            t_type = item.get("type")
            if t_type and t_type not in allowed_types:
                errors.append(f"Invalid trace type '{t_type}' at index {i}. Must be one of {sorted(allowed_types)}")

    return errors
