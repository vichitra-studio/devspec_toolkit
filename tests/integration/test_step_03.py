#!/usr/bin/env python3
"""
Step 03 Glossary Verification Tool

Validates Step 03 glossary fixtures against schema and additional quality constraints
that JSON Schema cannot enforce, such as unique term_id and term values (case-insensitive),
and metric coverage/unit consistency checks.
"""

import json
import os
import sys
from pathlib import Path

# Add the tools directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))

# Import the validate function directly from validate module
from specdev_tools.validate import validate_file


def load_json(path):
    """Load JSON file with error handling."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to load {path}: {e}")


def validate_glossary_terms(glossary_data, fixture_path):
    """
    Validate glossary terms against additional constraints not covered by JSON Schema.
    
    Args:
        glossary_data: Loaded glossary JSON data
        fixture_path: Path to the fixture file for error reporting
        
    Returns:
        list[str]: List of validation errors
    """
    errors = []
    
    # Get terms array
    terms = glossary_data.get('terms', [])
    
    # Check for empty terms array (already covered by schema, but let's be explicit)
    if len(terms) == 0:
        errors.append(f"Fixture {fixture_path} has empty terms array")
    
    # Track unique term_id and term values (case-insensitive)
    seen_term_ids = set()
    seen_terms = set()
    
    for i, term in enumerate(terms):
        # Validate term_id uniqueness (case-insensitive)
        term_id = term.get('term_id')
        if term_id:
            term_id_lower = term_id.lower()
            if term_id_lower in seen_term_ids:
                errors.append(f"Fixture {fixture_path}: Duplicate term_id '{term_id}' at index {i}")
            seen_term_ids.add(term_id_lower)
        
        # Validate term uniqueness (case-insensitive)  
        term_text = term.get('term')
        if term_text:
            term_text_lower = term_text.lower()
            if term_text_lower in seen_terms:
                errors.append(f"Fixture {fixture_path}: Duplicate term '{term_text}' at index {i}")
            seen_terms.add(term_text_lower)
        
        # Validate optional fields are not empty strings
        domain = term.get('domain')
        if isinstance(domain, str) and domain == "":
            errors.append(f"Fixture {fixture_path}: Empty domain string at term index {i}")
            
        units = term.get('units')
        if isinstance(units, str) and units == "":
            errors.append(f"Fixture {fixture_path}: Empty units string at term index {i}")
    
    return errors


def validate_glossary_coverage(glossary_data, nfrs_data=None, monitoring_data=None):
    """
    Validate glossary coverage and unit consistency against NFRs/monitoring data.
    
    Args:
        glossary_data: Loaded glossary JSON data
        nfrs_data: Optional NFRs data for coverage checking
        monitoring_data: Optional monitoring data for unit consistency
        
    Returns:
        list[str]: List of coverage/validation errors
    """
    errors = []
    
    # Get terms from glossary
    terms = glossary_data.get('terms', [])
    term_lookup = {term['term'].lower(): term for term in terms if 'term' in term}
    
    # Check coverage against NFRs if provided
    if nfrs_data and 'nfrs' in nfrs_data:
        for nfr in nfrs_data['nfrs']:
            metric_name = nfr.get('metric')
            if metric_name:
                # Check if the metric is defined in glossary
                if metric_name.lower() not in term_lookup:
                    errors.append(f"NFR metric '{metric_name}' not found in glossary")
                else:
                    # Check that it has units if required
                    term = term_lookup[metric_name.lower()]
                    units = term.get('units')
                    if not units:
                        errors.append(f"NFR metric '{metric_name}' missing units in glossary")
    
    # Check unit consistency with monitoring data if provided
    if monitoring_data and 'metrics' in monitoring_data:
        for metric in monitoring_data['metrics']:
            metric_name = metric.get('name')
            expected_units = metric.get('units')
            
            if metric_name and expected_units:
                if metric_name.lower() in term_lookup:
                    term = term_lookup[metric_name.lower()]
                    actual_units = term.get('units')
                    if actual_units and actual_units != expected_units:
                        errors.append(f"Unit mismatch for '{metric_name}': expected '{expected_units}', got '{actual_units}'")
    
    return errors


def main():
    """Main verification function."""
    # Get fixture directory from command line or use default
    if len(sys.argv) < 2:
        print("Usage: python verify_step_03.py <fixture_path> [nfrs_path] [monitoring_path]")
        sys.exit(1)
    
    fixture_path = Path(sys.argv[1])
    nfrs_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    monitoring_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    
    # Load fixture data
    try:
        glossary_data = load_json(fixture_path)
    except ValueError as e:
        print(f"Error loading fixture: {e}")
        sys.exit(1)
    
    # Load NFRs and monitoring data if provided
    nfrs_data = None
    monitoring_data = None
    
    if nfrs_path and nfrs_path.exists():
        try:
            nfrs_data = load_json(nfrs_path)
        except ValueError as e:
            print(f"Warning: Failed to load NFRs data: {e}")
    
    if monitoring_path and monitoring_path.exists():
        try:
            monitoring_data = load_json(monitoring_path)
        except ValueError as e:
            print(f"Warning: Failed to load monitoring data: {e}")
    
    # Validate against schema first using existing tool
    print(f"Validating {fixture_path} against schema...")
    try:
        # Use the existing validation mechanism by calling the validate function directly
        import subprocess
        import os
        
        # Run the CLI validation command instead of importing the function directly
        # to avoid circular import issues
        env = os.environ.copy()
        tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../tools"))
        env["PYTHONPATH"] = tools_path + os.pathsep + env.get("PYTHONPATH", "")
        toolkit_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

        result = subprocess.run([
            sys.executable, "-m", "specdev_tools.cli", "validate", 
            str(fixture_path), "--repo-root", toolkit_root
        ], capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            print("Schema validation failed:")
            print(result.stderr)
            sys.exit(1)
        else:
            print("✓ Schema validation passed")
    except Exception as e:
        print(f"Schema validation error: {e}")
        sys.exit(1)
    
    # Validate additional constraints
    print("Validating additional constraints...")
    errors = []
    
    # Check term uniqueness and optional field validation
    term_errors = validate_glossary_terms(glossary_data, fixture_path)
    errors.extend(term_errors)
    
    # Check coverage/unit consistency
    coverage_errors = validate_glossary_coverage(glossary_data, nfrs_data, monitoring_data)
    errors.extend(coverage_errors)
    
    # Report results
    if errors:
        print("✗ Validation failed with the following errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("✓ All validations passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
