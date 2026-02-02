#!/usr/bin/env python3
"""
Verification script for Step 14 (Roadmap) hardening.
This script validates the test fixtures against the new schema and implements
custom validation logic for business rules like date sequencing.
"""

import json
import sys
import os
import re
from pathlib import Path

# Add the devspec_toolkit to path so we can import specdev_tools
sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))

from specdev_tools.validate import validate_file

def load_step_09_spec(spec_path):
    """Load Step 09 specification from the given path"""
    path = Path(spec_path)
    if not path.exists():
        print(f"Warning: Step 09 spec not found at {path}. Skipping referential integrity checks.")
        return None
    
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load Step 09 spec: {e}")
        return None

def validate_source_milestones(milestones, step09_data):
    """Validate that source_milestones exist in Step 09"""
    if not step09_data or not milestones:
        return []
        
    step09_milestones = {m.get('id') for m in step09_data.get('milestones', []) if m.get('id')}
    errors = []
    
    for m in milestones:
        sources = m.get('source_milestones', [])
        for src_id in sources:
            if src_id not in step09_milestones:
                errors.append(
                    f"Milestone '{m.get('name')}' references unknown source milestone '{src_id}'. "
                    f"Available IDs in Step 09: {sorted(list(step09_milestones))}"
                )
    return errors

def validate_tech_stack_integrity(tech_stack, step09_data):
    """Validate that tech stack includes all items from Step 09"""
    if not step09_data or not tech_stack:
        return []

    errors = []
    step09_stack = step09_data.get('tech_stack', {})
    
    for category in ['languages', 'frameworks', 'infrastructure', 'tools']:
        s9_items = {item['name']: item for item in step09_stack.get(category, [])}
        s14_items = {item['name']: item for item in tech_stack.get(category, [])}
        
        for name, s9_item in s9_items.items():
            if name not in s14_items:
                errors.append(f"Missing required {category} item from Step 09: '{name}'")
            elif s14_items[name]['version'] != s9_item['version']:
                errors.append(
                    f"Version mismatch for {category} item '{name}': "
                    f"Step 09 requires '{s9_item['version']}', Roadmap has '{s14_items[name]['version']}'"
                )
    
    return errors

def validate_date_sequencing(milestones):
    """Validate that milestone dates are in chronological order"""
    if not milestones:
        return []

    errors = []
    prev_date = None
    prev_name = None
    for milestone in milestones:
        curr_date = milestone.get('target_date')
        curr_name = milestone.get('name', 'unknown')

        if prev_date and curr_date:
            # Compare dates lexicographically (works for ISO format)
            if prev_date > curr_date:
                errors.append(
                    f"Milestone '{prev_name}' ({prev_date}) should come before milestone "
                    f"'{curr_name}' ({curr_date})"
                )

        if curr_date:
            prev_date = curr_date
            prev_name = curr_name
    
    return errors

def validate_dependencies_format(dependencies):
    """Validate dependency objects for required fields and external ownership"""
    if not dependencies:
        return []

    errors = []
    kebab_id_pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    for dep in dependencies:
        if not isinstance(dep, dict):
            errors.append(f"Dependency entry must be an object: {dep}")
            continue
        dep_type = dep.get("type")
        dep_id = dep.get("id")
        owner = dep.get("owner")
        note = dep.get("note")

        if dep_type not in ("milestone", "external"):
            errors.append(f"Dependency entry has invalid type: {dep_type}")
            continue
        if not isinstance(dep_id, str) or not kebab_id_pattern.match(dep_id):
            errors.append(f"Dependency entry has invalid id: {dep_id}")
            continue
        if dep_type == "external":
            if not isinstance(owner, str) or not owner.strip():
                errors.append(f"External dependency '{dep_id}' missing owner")
            if not isinstance(note, str) or len(note.strip().split()) < 2:
                errors.append(f"External dependency '{dep_id}' missing rationale note")

    return errors

def validate_milestone_fields(milestones):
    """Validate that all required milestone fields are present and valid"""
    errors = []
    
    for milestone in milestones:
        # Check required fields
        required_fields = ['milestone_id', 'name', 'target_date', 'user_story', 'source_milestones', 'tasks', 'deliverables']
        for field in required_fields:
            if field not in milestone or milestone[field] is None:
                errors.append(f"Milestone '{milestone.get('name', 'unknown')}' missing required field: {field}")

        if 'source_milestones' in milestone:
            sources = milestone.get('source_milestones')
            if not isinstance(sources, list) or len(sources) == 0:
                errors.append(f"Milestone '{milestone.get('name', 'unknown')}' has empty source_milestones list")
        
        # Check tasks is not empty
        if 'tasks' in milestone and isinstance(milestone['tasks'], list) and len(milestone['tasks']) == 0:
            errors.append(f"Milestone '{milestone.get('name', 'unknown')}' has empty tasks list")
        
        # Check deliverables is not empty
        if 'deliverables' in milestone and isinstance(milestone['deliverables'], list) and len(milestone['deliverables']) == 0:
            errors.append(f"Milestone '{milestone.get('name', 'unknown')}' has empty deliverables list")
    
    return errors

def validate_task_format(milestones):
    """Validate task objects for shape, description length, and unique ids"""
    errors = []
    kebab_id_pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    for milestone in milestones:
        tasks = milestone.get('tasks', [])
        if not isinstance(tasks, list):
            errors.append(f"Milestone '{milestone.get('name', 'unknown')}' tasks must be a list")
            continue
        seen_ids = set()
        for task in tasks:
            if not isinstance(task, dict):
                errors.append(f"Milestone '{milestone.get('name', 'unknown')}' task must be an object: {task}")
                continue
            task_id = task.get("task_id")
            description = task.get("description")
            acceptance = task.get("acceptance_criteria")
            if not isinstance(task_id, str) or not kebab_id_pattern.match(task_id):
                errors.append(f"Milestone '{milestone.get('name', 'unknown')}' task has invalid task_id: {task_id}")
                continue
            if task_id in seen_ids:
                errors.append(f"Milestone '{milestone.get('name', 'unknown')}' task_id is duplicated: {task_id}")
            seen_ids.add(task_id)
            if not isinstance(description, str) or len(description.strip().split()) < 2:
                errors.append(f"Milestone '{milestone.get('name', 'unknown')}' task description is too short: {description}")
            if acceptance is not None:
                if not isinstance(acceptance, list) or len(acceptance) == 0:
                    errors.append(f"Milestone '{milestone.get('name', 'unknown')}' task has empty acceptance_criteria")
                    continue
                for criterion in acceptance:
                    if not isinstance(criterion, dict):
                        errors.append(f"Milestone '{milestone.get('name', 'unknown')}' acceptance_criteria must be objects: {criterion}")
                        continue
                    criterion_id = criterion.get("criterion_id")
                    text = criterion.get("text")
                    fixture_ref = criterion.get("fixture_ref")
                    if not isinstance(criterion_id, str) or not kebab_id_pattern.match(criterion_id):
                        errors.append(f"Milestone '{milestone.get('name', 'unknown')}' acceptance_criteria has invalid criterion_id: {criterion_id}")
                    if not isinstance(text, str) or len(text.strip()) < 15:
                        errors.append(f"Milestone '{milestone.get('name', 'unknown')}' acceptance_criteria text too short: {text}")
                    if fixture_ref is not None and (not isinstance(fixture_ref, str) or not kebab_id_pattern.match(fixture_ref)):
                        errors.append(f"Milestone '{milestone.get('name', 'unknown')}' acceptance_criteria has invalid fixture_ref: {fixture_ref}")

    return errors

def validate_migration_plan(plan):
    """Validate that migration_plan is 'none' or a short, descriptive sentence"""
    if plan is None:
        return []
    if not isinstance(plan, str):
        return [f"migration_plan must be a string: {plan}"]

    normalized = plan.strip()
    if not normalized:
        return ["migration_plan must not be empty"]
    if normalized.lower() == "none":
        return []

    word_count = len(normalized.split())
    if word_count < 3:
        return [f"migration_plan is too short: {plan}"]
    if word_count > 40:
        return [f"migration_plan is too long ({word_count} words)"]

    return []

def main():
    """Validate all test fixtures for Step 14"""
    import argparse
    parser = argparse.ArgumentParser(description="Verify Step 14 Roadmap Artifacts")
    parser.add_argument("files", nargs="*", help="Specific files to verify (optional)")
    parser.add_argument("--step-09-spec", default=None, help="Path to Step 09 Implementation Plan for referential integrity checks")
    args = parser.parse_args()

    # Load Step 09 spec if provided, or fall back to mock for testing
    spec_path = args.step_09_spec
    if not spec_path and Path("tests/fixtures/step_14/mock_09_impl_plan.json").exists():
        print("Using mock Step 09 spec for verification testing...")
        spec_path = "tests/fixtures/step_14/mock_09_impl_plan.json"

    step09_data = None
    if spec_path:
        step09_data = load_step_09_spec(spec_path)
    
    # Define fixture paths
    fixtures_dir = Path("tests/fixtures/step_14")
    
    # Valid fixtures that should pass validation
    valid_fixtures = [
        "valid_roadmap.json",
        "valid_roadmap_migration.json"
    ]
    
    # Invalid fixtures that should fail validation
    invalid_fixtures = [
        "invalid_tech_mismatch.json",
        "invalid_date_order.json",
        "invalid_missing_source_milestones.json",
        "invalid_integrity_bad_source.json"
    ]
    
    print("Starting verification of Step 14 fixtures...")
    
    # Test valid fixtures
    print("\nTesting valid fixtures:")
    all_passed = True
    
    for fixture_name in valid_fixtures:
        fixture_path = fixtures_dir / fixture_name
        if not fixture_path.exists():
            print(f"  ❌ {fixture_name}: File not found")
            all_passed = False
            continue
            
        try:
            # Validate the fixture with schema
            schema_errors = validate_file(".", str(fixture_path))
            if schema_errors:
                print(f"  ❌ {fixture_name}: SCHEMA VALIDATION FAILED")
                for error in schema_errors:
                    print(f"    Error: {error}")
                all_passed = False
                continue
            
            # Load the file to perform custom business logic validation
            with open(fixture_path, 'r') as f:
                data = json.load(f)
            
            # Perform custom validation
            milestones = data.get('milestones', [])
            
            # Validate date sequencing
            date_errors = validate_date_sequencing(milestones)
            if date_errors:
                print(f"  ❌ {fixture_name}: DATE SEQUENCING FAILED")
                for error in date_errors:
                    print(f"    Error: {error}")
                all_passed = False
                continue
            
            # Validate milestone fields
            field_errors = validate_milestone_fields(milestones)
            if field_errors:
                print(f"  ❌ {fixture_name}: MILESTONE FIELD VALIDATION FAILED")
                for error in field_errors:
                    print(f"    Error: {error}")
                all_passed = False
                continue

            # Validate task format
            task_errors = validate_task_format(milestones)
            if task_errors:
                print(f"  ❌ {fixture_name}: TASK FORMAT FAILED")
                for error in task_errors:
                    print(f"    Error: {error}")
                all_passed = False
                continue

            # Validate migration plan
            plan_errors = validate_migration_plan(data.get('migration_plan'))
            if plan_errors:
                print(f"  ❌ {fixture_name}: MIGRATION PLAN FAILED")
                for error in plan_errors:
                    print(f"    Error: {error}")
                all_passed = False
                continue

            # Validate dependency format
            dep_errors = validate_dependencies_format(data.get('dependencies', []))
            if dep_errors:
                print(f"  ❌ {fixture_name}: DEPENDENCY FORMAT FAILED")
                for error in dep_errors:
                    print(f"    Error: {error}")
                all_passed = False
                continue

            # Validate referential integrity against Step 09
            if step09_data:
                integrity_errors = validate_source_milestones(milestones, step09_data)
                integrity_errors.extend(validate_tech_stack_integrity(data.get('tech_stack'), step09_data))
                
                if integrity_errors:
                    print(f"  ❌ {fixture_name}: REFERENTIAL INTEGRITY FAILED")
                    for error in integrity_errors:
                        print(f"    Error: {error}")
                    all_passed = False
                    continue
            
            print(f"  ✅ {fixture_name}: PASSED")
            
        except Exception as e:
            print(f"  ❌ {fixture_name}: EXCEPTION - {e}")
            all_passed = False
    
    # If specific files were provided, skip the automated fixture discovery suite
    if args.files:
        return 0 if all_passed else 1
    
    # Test invalid fixtures
    print("\nTesting invalid fixtures:")
    
    for fixture_name in invalid_fixtures:
        fixture_path = fixtures_dir / fixture_name
        if not fixture_path.exists():
            print(f"  ❌ {fixture_name}: File not found")
            all_passed = False
            continue
            
        try:
            # Validate the fixture - should fail schema validation or custom logic
            schema_errors = validate_file(".", str(fixture_path))

            if schema_errors:
                print(f"  ✅ {fixture_name}: CORRECTLY FAILED SCHEMA VALIDATION")
                continue

            with open(fixture_path, 'r') as f:
                data = json.load(f)

            milestones = data.get('milestones', [])

            date_errors = validate_date_sequencing(milestones)
            field_errors = validate_milestone_fields(milestones)
            task_errors = validate_task_format(milestones)
            plan_errors = validate_migration_plan(data.get('migration_plan'))
            dep_errors = validate_dependencies_format(data.get('dependencies', []))
            
            integrity_errors = []
            if step09_data:
                integrity_errors = validate_source_milestones(milestones, step09_data)
                integrity_errors.extend(validate_tech_stack_integrity(data.get('tech_stack'), step09_data))

            if date_errors or field_errors or task_errors or plan_errors or dep_errors or integrity_errors:
                print(f"  ✅ {fixture_name}: CORRECTLY FAILED CUSTOM VALIDATION")
                continue

            print(f"  ❌ {fixture_name}: UNEXPECTEDLY PASSED ALL VALIDATION")
            all_passed = False

        except Exception as e:
            print(f"  ✅ {fixture_name}: CORRECTLY FAILED WITH EXCEPTION - {e}")
    
    if all_passed:
        print("\n🎉 All verification tests passed!")
        return 0
    else:
        print("\n💥 Some verification tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
