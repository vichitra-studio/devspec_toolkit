#!/usr/bin/env python3
"""
Verification script for Step 10 (Governance & Change Control)
This script validates the governance schema and logical constraints.
"""

import json
import sys
import os
import re
from pathlib import Path

# Add the devspec_toolkit to path so we can import specdev_tools
sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))

def validate_schema(fixture_path):
    """Validate that the fixture conforms to the governance schema"""
    try:
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        
        # Check if it has the required schema reference
        if "$schema" not in data:
            print(f"❌ {fixture_path}: Missing $schema field")
            return False
            
        if data["$schema"] != "https://specdev.local/schema/10_governance.schema.json":
            print(f"❌ {fixture_path}: Incorrect schema reference")
            return False
            
        # Basic structure validation
        required_fields = ["id", "owner", "created_at", "spec_first_policy"]
        for field in required_fields:
            if field not in data:
                print(f"❌ {fixture_path}: Missing required field '{field}'")
                return False
                
        # Validate owner is one of the allowed values
        allowed_owners = ["api", "ui", "system", "ops", "data", "product", "business", "engineering"]
        if data["owner"] not in allowed_owners:
            print(f"❌ {fixture_path}: Invalid owner '{data['owner']}'. Must be one of {allowed_owners}")
            return False
            
        # Validate spec_first_policy is boolean
        if not isinstance(data["spec_first_policy"], bool):
            print(f"❌ {fixture_path}: spec_first_policy must be boolean")
            return False
            
        # Validate commit_message_rules if present
        if "commit_message_rules" in data:
            rules = data["commit_message_rules"]
            if "require_spec_ids" not in rules:
                print(f"❌ {fixture_path}: commit_message_rules missing required_spec_ids")
                return False
                
            if "pattern" in rules:
                pattern = rules["pattern"]
                try:
                    re.compile(pattern)
                except re.error as e:
                    print(f"❌ {fixture_path}: Invalid regex pattern '{pattern}': {e}")
                    return False
        
        # Validate pr_rules if present
        if "pr_rules" in data:
            rules = data["pr_rules"]
            allowed_rules = [
                "validate", "validate-all", "matrix", "fixtures-lint", 
                "invariants-check", "governance-check", "test", "build", 
                "lint", "format", "audit", "security"
            ]
            
            if not isinstance(rules, list):
                print(f"❌ {fixture_path}: pr_rules must be an array")
                return False
                
            for rule in rules:
                if rule not in allowed_rules:
                    print(f"❌ {fixture_path}: Invalid pr_rule '{rule}'. Must be one of {allowed_rules}")
                    return False
        
        print(f"✅ {fixture_path}: Schema validation passed")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ {fixture_path}: Invalid JSON - {e}")
        return False
    except Exception as e:
        print(f"❌ {fixture_path}: Error during validation - {e}")
        return False

def validate_trace_links(fixture_path):
    """Validate trace and links fields using the extracted validator."""
    try:
        from specdev_tools.validators.step_10 import validate_step_10
        with open(fixture_path, 'r') as f:
            data = json.load(f)
            
        errors = validate_step_10(data, ".")
        
        if errors:
            for e in errors:
                print(f"❌ {fixture_path}: {e}")
            return False
                    
        print(f"✅ {fixture_path}: Trace/links/logic validation passed")
        return True
        
    except Exception as e:
        print(f"❌ {fixture_path}: Error during validation - {e}")
        return False

def main():
    """Main verification function"""
    if len(sys.argv) < 2:
        print("Usage: python verify_step_10.py <fixture_path> or python verify_step_10.py <fixtures_directory>")
        sys.exit(1)
        
    target = sys.argv[1]
    fixtures_dir = Path(target)
    
    print("=== Step 10 Verification Script ===\n")
    
    # Determine if target is a file or directory
    if fixtures_dir.is_file():
        fixture_paths = [fixtures_dir]
    elif fixtures_dir.is_dir():
        fixture_paths = list(fixtures_dir.glob("*.json"))
    else:
        print(f"Error: {target} is neither a file nor directory")
        sys.exit(1)
    
    all_passed = True
    
    for fixture_path in fixture_paths:
        if fixture_path.is_file():
            print(f"Validating {fixture_path.name}...")
            
            # Run schema validation
            schema_valid = validate_schema(fixture_path)
            
            # Run trace/links validation  
            trace_valid = validate_trace_links(fixture_path)
            
            if schema_valid and trace_valid:
                print(f"✓ SUCCESS: {fixture_path.name}\n")
            else:
                print(f"✗ FAILED: {fixture_path.name}\n")
                all_passed = False
    
    if all_passed:
        print("=== ALL VERIFICATION TESTS PASSED ===")
        return 0
    else:
        print("=== SOME VERIFICATION TESTS FAILED ===")
        return 1

if __name__ == "__main__":
    sys.exit(main())
