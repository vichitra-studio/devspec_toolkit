#!/usr/bin/env python3
"""
Verification script for Step 15 (Scaffold Generation).
Validates schema compliance, logic rules (uniqueness), and formatting.
"""

import json
import sys
import re
from pathlib import Path


# Enum definitions matching schema
VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
VALID_BUILD_STATUS = {"pending", "green", "red"}

def validate_structure(data):
    """
    Validate basic structure and required fields.
    """
    if not isinstance(data, dict):
        return False, "Root must be an object"
    
    required_fields = ["id", "owner", "created_at", "service_skeleton", "route_map", "validators", "build_status"]
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
            
    # basic types check
    if not isinstance(data['service_skeleton'], dict):
        return False, "service_skeleton must be an object"
    if 'language' not in data['service_skeleton']:
        return False, "service_skeleton.language is required"
        
    if not isinstance(data['route_map'], list):
        return False, "route_map must be an array"
        
    if not isinstance(data['validators'], list):
        return False, "validators must be an array"
        
    if data['build_status'] not in VALID_BUILD_STATUS:
        return False, f"Invalid build_status: {data['build_status']}"
        
    return True, "Structure valid"

def validate_route_map(data):
    """
    Validate route_map items using extracted validator.
    """
    from specdev_tools.validation.validators.step_15 import validate_step_15
    
    errors = validate_step_15(data, ".")
    if errors:
        return False, "; ".join(errors)

    return True, "Logic valid"

def validate_fixture(fixture_path):
    try:
        with open(fixture_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return False, f"Failed to load JSON: {e}"
        
    # Structure
    ok, msg = validate_structure(data)
    if not ok:
        return False, msg
        
    # Route Map Logic (passed the whole data object now)
    ok, msg = validate_route_map(data)
    if not ok:
        return False, msg
        
    return True, "Valid"

def main():
    if len(sys.argv) < 2:
        print("Usage: python verifica_step_15.py <fixture_path_or_dir>")
        sys.exit(1)
        
    target = Path(sys.argv[1])
    
    if target.is_file():
        ok, msg = validate_fixture(target)
        if ok:
            pass
            sys.exit(0)
        else:
            print(f"✗ {target.name}: FAIL - {msg}")
            sys.exit(1)
            
    elif target.is_dir():
        results = []
        pass
        for f in sorted(target.glob("*.json")):
            ok, msg = validate_fixture(f)
            status = "PASS" if ok else "FAIL"
            pass
            if not ok:
                pass
            
            # Smart assertion: 
            # If filename contains 'invalid', we EXPECT failure.
            # If filename contains 'valid', we EXPECT pass.
            is_invalid_file = "invalid" in f.name
            
            if is_invalid_file and not ok:
                # Expected failure
                results.append(True)
            elif is_invalid_file and ok:
                # Unexpected pass
                print(f"  ERROR: Expected failure for {f.name} but it passed!")
                results.append(False)
            elif not is_invalid_file and not ok:
                # Unexpected failure
                results.append(False)
            else:
                # Expected pass
                results.append(True)
                
        if all(results):
            pass
            sys.exit(0)
        else:
            print("\nSome expectations failed.")
            sys.exit(1)
    else:
        print(f"Error: {target} not found")
        sys.exit(1)

if __name__ == "__main__":
    main()
