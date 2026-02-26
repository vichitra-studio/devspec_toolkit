#!/usr/bin/env python3
"""
Verification script for Step 09 (Implementation Plan) hardening.
This script validates the test fixtures against the new schema.
"""

import json
import sys
import os
from pathlib import Path

from specdev_tools.validation.validate import validate_file

def main():
    """Validate all test fixtures for Step 09"""
    
    # Define fixture paths
    fixtures_dir = Path("tests/fixtures/step_09")
    
    # Valid fixtures that should pass validation
    valid_fixtures = [
        "valid_complete.json",
        "valid_minimal.json",
        "valid_optional_trace.json"
    ]
    
    # Invalid fixtures that should fail validation
    invalid_fixtures = [
        "invalid_date_format.json"
    ]
    
    pass
    
    # Test valid fixtures
    pass
    all_passed = True
    
    for fixture_name in valid_fixtures:
        fixture_path = fixtures_dir / fixture_name
        if not fixture_path.exists():
            print(f"  ❌ {fixture_name}: File not found")
            all_passed = False
            continue
            
        try:
            # Validate the fixture
            result = validate_file(".", str(fixture_path))
            if not result:
                pass
            else:
                print(f"  ❌ {fixture_name}: FAILED")
                for error in result:
                    print(f"    Error: {error}")
                all_passed = False
        except Exception as e:
            print(f"  ❌ {fixture_name}: EXCEPTION - {e}")
            all_passed = False
    
    # Test invalid fixtures
    print("\nTesting invalid fixtures:")
    
    for fixture_name in invalid_fixtures:
        fixture_path = fixtures_dir / fixture_name
        if not fixture_path.exists():
            print(f"  ❌ {fixture_name}: File not found")
            all_passed = False
            continue
            
        try:
            # Validate the fixture - should fail
            result = validate_file(".", str(fixture_path))
            if result:
                print(f"  ✅ {fixture_name}: CORRECTLY FAILED")
                # Optional: print errors to debug if needed
                # for error in result:
                #    print(f"    (Expected Error: {error})")
            else:
                print(f"  ❌ {fixture_name}: SHOULD HAVE FAILED BUT PASSED")
                all_passed = False
        except Exception as e:
            print(f"  ✅ {fixture_name}: CORRECTLY FAILED WITH EXCEPTION - {e}")
    
    if all_passed:
        pass
        return 0
    else:
        print("\n💥 Some verification tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
