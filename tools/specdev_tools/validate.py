from __future__ import annotations
import json, os, sys
import time
from jsonschema import Draft202012Validator, RefResolver
from .registry import SchemaRegistry

def _resolver_for(registry: SchemaRegistry):
    return RefResolver.from_schema({}, store=registry.store)

def _get_step_from_path(path: str) -> str:
    """Extract step number from file path"""
    filename = os.path.basename(path)
    if filename.startswith('00_') or filename.startswith('01_') or filename.startswith('02_') or filename.startswith('03_') or filename.startswith('04_') or filename.startswith('05_') or filename.startswith('06_') or filename.startswith('07_') or filename.startswith('08_') or filename.startswith('09_') or filename.startswith('10_') or filename.startswith('11_') or filename.startswith('12_') or filename.startswith('13_') or filename.startswith('14_') or filename.startswith('15_') or filename.startswith('16_') or filename.startswith('17_'):
        # Extract first two characters for step number
        step = filename.split('_')[0]
        return step
    return "unknown"

def _get_guide_path(path: str) -> str:
    """Get corresponding guide file path"""
    step = _get_step_from_path(path)
    if step != "unknown":
        return f"spec/{step}_*.guide.md"
    return "spec/*.guide.md"

def validate_file(repo_root: str, path: str) -> list[str]:
    registry = SchemaRegistry(repo_root)
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        schema_uri = data.get("$schema")
        if not schema_uri:
            return [f"{path}: missing $schema. Please add schema reference to the top of the file"]
        
        schema = registry.load(schema_uri)

        # Exclude $schema from validation payload because many step schemas disallow unknown keys
        data_for_validation = dict(data)
        data_for_validation.pop("$schema", None)

        # Build a resolver store
        resolver = _resolver_for(registry)
        v = Draft202012Validator(schema, resolver=resolver)
        errors = sorted(v.iter_errors(data_for_validation), key=lambda e: e.path)
        
        # Enhance error messages with context
        enhanced_errors = []
        for e in errors:
            error_msg = f"{path}:{'/'.join(map(str, e.path))}: {e.message}"
            
            # Add context about what to do next
            step = _get_step_from_path(path)
            if step != "unknown":
                guide_path = _get_guide_path(path)
                error_msg += f"\n  See: {guide_path} for guidance on requirements"
            
            enhanced_errors.append(error_msg)
            
        return enhanced_errors
    except (OSError, json.JSONDecodeError, ValueError, KeyError, AttributeError, TypeError) as e:
        return [f"{path}: error during validation - {str(e)}"]

def validate_dir(repo_root: str, spec_dir: str) -> list[str]:
    failures = []
    
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                file_path = os.path.join(root, fn)
                failures.extend(validate_file(repo_root, file_path))
                
    return failures
