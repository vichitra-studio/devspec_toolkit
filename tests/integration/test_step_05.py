#!/usr/bin/env python3
"""
Verification script for Step 5 (Interface Contracts) 
Validates test fixtures using the specdev_tools CLI validation.
"""

import subprocess
import sys
import os
from pathlib import Path

def validate_fixture(fixture_path):
    """
    Validate a fixture using the specdev_tools CLI.
    
    Args:
        fixture_path: Path to the JSON fixture
        
    Returns:
        bool: True if validation passes, False otherwise
    """
    
    # Use the specdev_tools CLI to validate
    try:
        env = os.environ.copy()
        # Add devspec_toolkit/tools to Python path so we can import specdev_tools
        tools_path = os.path.join(os.getcwd(), "devspec_toolkit", "tools")
        env["PYTHONPATH"] = f"{tools_path}:{env.get('PYTHONPATH', '')}"
        
        result = subprocess.run([
            sys.executable, "-m", "specdev_tools.cli", "validate", 
            fixture_path, "--repo-root", "."
        ], capture_output=True, text=True, env=env)
        
        if result.returncode == 0:
            return True
        else:
            print(f"✗ {fixture_path.name} - INVALID")
            print(f"  Error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ {fixture_path.name} - ERROR: {e}")
        return False

def main():
    """Main verification function."""
    
    # Define test fixture paths
    test_fixtures_dir = Path('devspec_toolkit/tests/fixtures/step_05')
    
    if not test_fixtures_dir.exists():
        return 1
    
    # Get all JSON files in the directory
    fixture_files = list(test_fixtures_dir.glob('*.json'))
    
    if not fixture_files:
        return 1
    
    # Validate each fixture
    results = []
    for fixture_file in fixture_files:
        is_negative_test = "invalid" in fixture_file.name
        is_valid = validate_fixture(fixture_file)
        
        if is_negative_test:
            # For negative tests, we expect validation to FAIL
            passed = not is_valid
            if passed:
                print(f"  -> SUCCESS (Expected Failure)")
            else:
                print(f"  -> FAILURE (Expected Failure but Passed)")
        else:
            # For normal tests, we expect validation to PASS
            passed = is_valid
            
        results.append((fixture_file.name, passed))
    
    # Summary
    
    valid_count = sum(1 for _, valid in results if valid)
    total_count = len(results)
    
    for fixture_name, is_valid in results:
        status = "PASS" if is_valid else "FAIL"
    
    
    # Exit with error if any fixture failed
    if valid_count != total_count:
        print("Some fixtures failed validation!")
        return 1
    else:
        return 0

if __name__ == "__main__":
    sys.exit(main())
