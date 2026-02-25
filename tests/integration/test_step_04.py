#!/usr/bin/env python3
"""
Verification script for Step 4 Functional Requirements fixtures.
This script validates the schema compliance of Step 4 fixtures and ensure
unique fr_id values across the list.
"""

import json
import sys
import os
import subprocess
from pathlib import Path

# Add tools to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../tools")))

def validate_fixture(fixture_path, should_pass=True):
    """
    Validate a fixture against the Step 4 schema and check for unique fr_ids.
    
    Args:
        fixture_path: Path to the JSON fixture
        should_pass: If True, expects validation to succeed. If False, expects it to fail.
    
    Returns:
        bool: True if the outcome matches expectation, False otherwise.
    """
    
    
    # 1. Schema Validation via CLI
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "tools") + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run([
        sys.executable, "-m", "specdev_tools.cli", "validate", 
        fixture_path, "--repo-root", "."
    ], capture_output=True, text=True, env=env)
    
    schema_valid = (result.returncode == 0)
    
    if should_pass and not schema_valid:
        print(f"❌ FAIL: Expected PASS but got Schema Validation Error:")
        return False
        
    if not should_pass and schema_valid:
        print(f"❌ FAIL: Expected FAIL but Schema Validation passed unexpectedly.")
        return False
        
    if not should_pass and not schema_valid:
        print(f"✅ PASS: Schema validation failed as expected.")
        return True

    # 2. logical Validation (only if schema passed and we expected it to)
    if should_pass:
        try:
            from specdev_tools.validators.step_04 import validate_step_04
            with open(fixture_path, 'r') as f:
                fixture_data = json.load(f)
            
            # Use the extracted validator
            logic_errors = validate_step_04(fixture_data, ".")

            if logic_errors:
                for err in logic_errors:
                    print(f"❌ FAIL: {err}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ FAIL: logical check error: {str(e)}")
            return False

    return True

def main():
    """Main verification function."""
    
    # Define test cases: (path, should_pass)
    # Use repo-root relative paths assuming running from repo root
    test_cases = [
        ("devspec_toolkit/tests/fixtures/step_04/valid_comprehensive.json", True),
        ("devspec_toolkit/tests/fixtures/step_04/invalid_bad_trace.json", False)
    ]
    
    # Allow overriding via args (assumes all args are expected to PASS)
    if len(sys.argv) > 1:
        test_cases = [(path, True) for path in sys.argv[1:]]
    
    
    all_success = True
    
    for path, should_pass in test_cases:
        if os.path.exists(path):
            if not validate_fixture(path, should_pass):
                all_success = False
        else:
            print(f"⚠️  WARNING: Fixture not found: {path}")
            # Don't fail the build for a missing file unless it's strict, 
            # but here we'll count it as a failure to ensure we fix paths
            all_success = False
    
    if all_success:
        return 0
    else:
        print("💀 VERIFICATION FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
