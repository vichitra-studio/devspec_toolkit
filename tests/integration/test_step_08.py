#!/usr/bin/env python3
"""
Verification script for Step 8 hardening changes.
This script runs schema validation and linter checks on the new fixtures.
"""

import subprocess
import sys
import os
import json

def run_command(command, description):
    """Run a command and return success status."""
    print(f"\n{description}")
    print(f"Command: {' '.join(command)}")
    
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    tools_path = os.path.abspath("devspec_toolkit/tools")
    if tools_path not in pythonpath:
        env["PYTHONPATH"] = f"{tools_path}:{pythonpath}" if pythonpath else tools_path

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, env=env)
        print("✓ SUCCESS")
        if result.stdout:
            print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print("✗ FAILED")
        print(f"Error: {e.stderr}")
        return False

def check_unique_ids(directory):
    """Check that all fixture_ids are unique across checks."""
    print(f"\nChecking for unique fixture_ids in {directory}...")
    seen_ids = {}
    duplicates = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith('.json'):
                continue
            
            path = os.path.join(root, file)
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    
                if 'fixtures' not in data:
                    continue
                    
                for fixture in data['fixtures']:
                    fid = fixture.get('fixture_id')
                    if not fid:
                        continue
                        
                    if fid in seen_ids:
                        duplicates.append(f"{fid} (in {file} and {seen_ids[fid]})")
                    else:
                        seen_ids[fid] = file
            except Exception as e:
                print(f"Warning: Could not check {file}: {e}")
                
    if duplicates:
        print("✗ FAILED: Duplicate IDs found:")
        for d in duplicates:
            print(f"  - {d}")
        return False
    
    print("✓ SUCCESS: All fixture_ids are unique")
    return True

def main():
    """Run all verification checks."""
    print("=== Step 8 Verification Script ===")
    
    success = True
    
    # Test 1: Schema validation for valid fixtures
    success &= run_command([
        sys.executable, "-m", "specdev_tools.cli", "validate", 
        "devspec_toolkit/tests/fixtures/step_08/valid/valid_http.json"
    ], "Validating valid_http.json fixture...")
    
    success &= run_command([
        sys.executable, "-m", "specdev_tools.cli", "validate", 
        "devspec_toolkit/tests/fixtures/step_08/valid/valid_generic.json"
    ], "Validating valid_generic.json fixture...")
    
    # Test 2: Schema validation for invalid fixtures (should FAIL)
    print("\nValidating invalid_targets_format.json (should FAIL)...")
    try:
        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        tools_path = os.path.abspath("devspec_toolkit/tools")
        if tools_path not in pythonpath:
            env["PYTHONPATH"] = f"{tools_path}:{pythonpath}" if pythonpath else tools_path

        subprocess.run([
            sys.executable, "-m", "specdev_tools.cli", "validate", 
            "devspec_toolkit/tests/fixtures/step_08/invalid/invalid_targets_format.json"
        ], capture_output=True, text=True, check=True, env=env)
        print("✗ FAILED: Should have failed validation but PASSED")
        success = False
    except subprocess.CalledProcessError:
        print("✓ SUCCESS: Correctly failed validation")

    print("\nValidating invalid_missing_targets.json (should FAIL)...")
    try:
        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        tools_path = os.path.abspath("devspec_toolkit/tools")
        if tools_path not in pythonpath:
            env["PYTHONPATH"] = f"{tools_path}:{pythonpath}" if pythonpath else tools_path
            
        subprocess.run([
            sys.executable, "-m", "specdev_tools.cli", "validate", 
            "devspec_toolkit/tests/fixtures/step_08/invalid/invalid_missing_targets.json"
        ], capture_output=True, text=True, check=True, env=env)
        print("✗ FAILED: Should have failed validation but PASSED")
        success = False
    except subprocess.CalledProcessError:
        print("✓ SUCCESS: Correctly failed validation")

    # Test 3: Linter check on VALID directory
    success &= run_command([
        sys.executable, "-m", "specdev_tools.cli", "fixtures-lint", 
        "devspec_toolkit/tests/fixtures/step_08/valid"
    ], "Linting VALID fixtures directory (should PASS)")

    # Test 4: Linter check on INVALID directory (should FAIL)
    print("\nLinting INVALID fixtures directory (should FAIL)...")
    try:
        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        tools_path = os.path.abspath("devspec_toolkit/tools")
        if tools_path not in pythonpath:
            env["PYTHONPATH"] = f"{tools_path}:{pythonpath}" if pythonpath else tools_path
            
        subprocess.run([
            sys.executable, "-m", "specdev_tools.cli", "fixtures-lint", 
            "devspec_toolkit/tests/fixtures/step_08/invalid"
        ], capture_output=True, text=True, check=True, env=env)
        print("✗ FAILED: Linter check passed but should have failed")
        success = False
    except subprocess.CalledProcessError:
        print("✓ SUCCESS: Linter check correctly failed on invalid fixtures")
    
    # Test 5: Unique IDs check
    success &= check_unique_ids("devspec_toolkit/tests/fixtures/step_08")

    if success:
        print("\n=== ALL VERIFICATION TESTS PASSED ===")
        return 0
    else:
        print("\n=== SOME VERIFICATION TESTS FAILED ===")
        return 1

if __name__ == "__main__":
    sys.exit(main())
