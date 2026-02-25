#!/usr/bin/env python3
"""
Verification script for Step 13 and Step 13a hardening.
Validates extension naming conventions, manifest schema, and verifies linked extensions exist.
"""

import os
import sys
import json
import re
from pathlib import Path

def validate_manifest_schema(manifest_path):
    """Validate that the manifest follows the correct schema."""
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Check basic structure
        required_fields = ['id', 'owner', 'created_at', 'extensions']
        for field in required_fields:
            if field not in manifest:
                return False, f"Missing required field: {field}"
        
        # Validate extensions array
        if not isinstance(manifest.get('extensions'), list):
            return False, "Extensions must be an array"
        
        # Validate each extension
        for i, ext in enumerate(manifest.get('extensions', [])):
            required_ext_fields = ['extension_id', 'title', 'file_name', 'area_of_concern', 'required_schema_sections']
            for field in required_ext_fields:
                if field not in ext:
                    return False, f"Extension {i} missing required field: {field}"
            
            # Validate extension_id format (should be ext-[0-9]{2}-[a-z0-9-]+)
            ext_id = ext.get('extension_id', '')
            if not re.match(r'^ext-[0-9]{2}-[a-z0-9-]+$', ext_id):
                return False, f"Extension {i} has invalid extension_id format: {ext_id}"
            
            # Validate file_name format (should be ext_[0-9]{2}_[a-z0-9_]+\.json)
            file_name = ext.get('file_name', '')
            if not re.match(r'^ext_[0-9]{2}_[a-z0-9_]+\.json$', file_name):
                return False, f"Extension {i} has invalid file_name format: {file_name}"
        
        return True, "Manifest schema is valid"
    
    except Exception as e:
        return False, f"Error validating manifest: {str(e)}"

def validate_extension_naming(manifest_path, spec_dir):
    """Validate that all extensions in manifest have corresponding files."""
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Get list of extension file names from manifest
        extension_files = [ext['file_name'] for ext in manifest.get('extensions', [])]
        
        # Check if all files exist
        missing_files = []
        for file_name in extension_files:
            file_path = os.path.join(spec_dir, file_name)
            if not os.path.exists(file_path):
                missing_files.append(file_name)
        
        if missing_files:
            return False, f"Missing extension files: {', '.join(missing_files)}"
        
        return True, "All extension files exist"
    
    except Exception as e:
        return False, f"Error validating extension naming: {str(e)}"

def validate_extension_manifest(manifest_path, spec_dir):
    """Main validation function."""
    
    # Validate schema
    is_valid, message = validate_manifest_schema(manifest_path)
    
    if not is_valid:
        return False
    
    # Validate naming and file existence
    is_valid, message = validate_extension_naming(manifest_path, spec_dir)
    
    if not is_valid:
        return False
    
    return True

def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python3 verify_step_13.py <path_to_manifest>")
        sys.exit(1)
    
    manifest_path = sys.argv[1]
    manifest_path = sys.argv[1]
    spec_dir = os.path.dirname(manifest_path)
    if not spec_dir:
        spec_dir = "."

    
    if not os.path.exists(manifest_path):
        print(f"Error: Manifest file does not exist: {manifest_path}")
        sys.exit(1)
    
    success = validate_extension_manifest(manifest_path, spec_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
