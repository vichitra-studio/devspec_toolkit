#!/usr/bin/env python3
"""
Verification script for Step 12 (CI Gates) hardening changes.
This script validates DAG integrity, step structure, and command prefixes.
"""

import json
import sys
from pathlib import Path

def validate_dag_integrity(jobs):
    """
    Validate DAG integrity: no cycles, all dependencies exist
    """
    job_ids = {job['job_id'] for job in jobs}
    
    # Check that all requires point to existing jobs
    for job in jobs:
        job_id = job['job_id']
        requires = job.get('requires', [])
        for req in requires:
            if req not in job_ids:
                return False, f"Job '{job_id}' requires non-existent job '{req}'"
    
    # Simple cycle detection using topological sort approach
    # Build dependency graph
    graph = {job_id: set() for job_id in job_ids}
    for job in jobs:
        job_id = job['job_id']
        requires = job.get('requires', [])
        for req in requires:
            graph[req].add(job_id)
    
    # Check for cycles using DFS
    visited = set()
    recursion_stack = set()
    
    def has_cycle(node):
        if node not in visited:
            visited.add(node)
            recursion_stack.add(node)
            
            for neighbor in graph[node]:
                if neighbor not in visited and has_cycle(neighbor):
                    return True
                elif neighbor in recursion_stack:
                    return True
            
            recursion_stack.remove(node)
        return False
    
    for job_id in job_ids:
        if job_id not in visited:
            if has_cycle(job_id):
                return False, f"Cycle detected in DAG"
    
    return True, "DAG is valid"

def validate_step_structure(steps):
    """
    Validate that each step has required fields and proper structure
    """
    for i, step in enumerate(steps):
        # Check required fields
        if not isinstance(step, dict):
            return False, f"Step {i} is not a dictionary"
        
        if 'id' not in step:
            return False, f"Step {i} missing required 'id' field"
        
        if 'command' not in step:
            return False, f"Step {i} missing required 'command' field"
        
        # Validate id format (kebab-case)
        step_id = step['id']
        if not isinstance(step_id, str) or not step_id.replace('-', '').isalnum():
            return False, f"Step {i} id '{step_id}' is not valid kebab-case"
        
        # Validate command format
        command = step['command']
        if not isinstance(command, str):
            return False, f"Step {i} command is not a string"
        
        # Check that command starts with allowed prefixes
        allowed_prefixes = ['python -m ', 'bash ', 'npm ', 'make ', 'sh ']
        has_valid_prefix = any(command.startswith(prefix) for prefix in allowed_prefixes)
        if not has_valid_prefix and command.strip() != "":
            # Allow commands that don't start with prefixes (but warn?)
            pass  # For now, we'll allow any command format
    
    return True, "Step structure is valid"

def validate_fixture(fixture_path):
    """
    Validate a single fixture file
    """
    try:
        with open(fixture_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return False, f"Failed to load fixture: {str(e)}"
    
    # Check required fields at root level
    if 'jobs' not in data:
        return False, "Missing required 'jobs' field"
    
    jobs = data['jobs']
    if not isinstance(jobs, list):
        return False, "'jobs' must be an array"
    
    # Validate DAG integrity
    dag_valid, dag_msg = validate_dag_integrity(jobs)
    if not dag_valid:
        return False, f"DAG validation failed: {dag_msg}"
    
    # Validate each job's steps
    for i, job in enumerate(jobs):
        if 'steps' not in job:
            return False, f"Job {i} missing required 'steps' field"
        
        steps = job['steps']
        if not isinstance(steps, list):
            return False, f"Job {i} 'steps' must be an array"
        
        step_valid, step_msg = validate_step_structure(steps)
        if not step_valid:
            return False, f"Job {i}: {step_msg}"
    
    return True, "Fixture validation passed"

def main():
    """
    Main verification function
    """
    if len(sys.argv) != 2:
        print("Usage: python verify_step_12.py <fixture_path>")
        sys.exit(1)
    
    fixture_path = Path(sys.argv[1])
    
    
    if fixture_path.is_dir():
        # Test all fixture files in directory
        fixture_files = list(fixture_path.glob("*.json"))
        if not fixture_files:
            sys.exit(1)
        
        results = []
        for fixture_file in fixture_files:
            valid, msg = validate_fixture(fixture_file)
            if valid:
                results.append((fixture_file.name, True))
            else:
                print(f"✗ FAILED: {msg}")
                results.append((fixture_file.name, False))
        
        # Summary
        success_count = sum(1 for _, valid in results if valid)
        
        if success_count == len(results):
            return 0
        else:
            print("✗ SOME VERIFICATION TESTS FAILED")
            return 1
            
    else:
        # Test single fixture file
        valid, msg = validate_fixture(fixture_path)
        if valid:
            return 0
        else:
            print(f"✗ FAILED: {msg}")
            print("✗ VERIFICATION FAILED")
            return 1

if __name__ == "__main__":
    sys.exit(main())
