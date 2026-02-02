#!/usr/bin/env python3
"""
Verification script for Step 7 (NFRs)
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
    print(f"Validating: {fixture_path}")
    
    # Use the specdev_tools CLI to validate
    # Note: We use tools.specdev_tools.cli because of how the python path is set up in the mono-repo
    try:
        env = os.environ.copy()
        
        # Construct command
        cmd = [
            sys.executable, "-m", "tools.specdev_tools.cli", "validate", 
            str(fixture_path), "--repo-root", "."
        ]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            env=env,
            cwd=os.getcwd() # Run from repo root
        )
        
        if result.returncode == 0:
            print(f"✓ {fixture_path.name} - VALID")
            return True
        else:
            print(f"✗ {fixture_path.name} - INVALID")
            # Only print stderr if it's not a negative test where we expect failure, 
            # but usually the caller handles logic. Here we just return validity.
            # We print output for debugging.
            print(f"  Output: {result.stderr or result.stdout}")
            return False
            
    except Exception as e:
        print(f"✗ {fixture_path.name} - ERROR: {e}")
        return False

def main():
    """Main verification function."""
    
    # Define test fixture paths
    test_fixtures_dir = Path('tests/fixtures/step_07')
    
    if not test_fixtures_dir.exists():
        print(f"Test fixtures directory does not exist: {test_fixtures_dir}")
        return 1
    
    # Get all JSON files in the directory
    fixture_files = list(test_fixtures_dir.glob('*.json'))
    
    if not fixture_files:
        print("No test fixtures found")
        return 1
    
    # Validate each fixture
    results = []
    print(f"Found {len(fixture_files)} fixtures in {test_fixtures_dir}")
    
    for fixture_file in fixture_files:
        is_negative_test = "invalid" in fixture_file.name
        is_valid = validate_fixture(fixture_file)
        
        if is_negative_test:
            # For negative tests, we expect validation to FAIL (is_valid=False)
            passed = not is_valid
            if passed:
                print(f"  -> SUCCESS (Expected Failure)")
            else:
                print(f"  -> FAILURE (Expected Failure but Validated Successfully)")
        else:
            # For normal tests, we expect validation to PASS (is_valid=True)
            passed = is_valid
            if passed:
                print(f"  -> SUCCESS (Expected Success)")
            else:
                 print(f"  -> FAILURE (Expected Success but Failed)")
            
        results.append((fixture_file.name, passed))
    
    # Summary
    print("\n" + "="*50)
    print("VERIFICATION SUMMARY")
    print("="*50)
    
    valid_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for fixture_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {fixture_name}")
    
    print(f"\nTotal: {valid_count}/{total_count} fixtures passed behavior check")
    
    # Exit with error if any fixture failed
    if valid_count != total_count:
        print("Some fixtures failed verification!")
        return 1
    else:
        print("All fixtures verified!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
