from __future__ import annotations
import json, os, sys
import time
from jsonschema import Draft202012Validator, RefResolver
from .registry import SchemaRegistry
from .validators import step_01, step_02, step_03, step_04, step_10, step_15, step_16

def _resolver_for(registry: SchemaRegistry):
    return RefResolver.from_schema({}, store=registry.store)

def _get_step_from_path(path: str) -> str:
    """Extract step number from file path"""
    filename = os.path.basename(path)
    if filename.startswith('00_') or filename.startswith('01_') or filename.startswith('02_') or filename.startswith('03_') or filename.startswith('04_') or filename.startswith('05_') or filename.startswith('06_') or filename.startswith('07_') or filename.startswith('08_') or filename.startswith('09_') or filename.startswith('10_') or filename.startswith('11_') or filename.startswith('12_') or filename.startswith('13_') or filename.startswith('14_') or filename.startswith('15_') or filename.startswith('16_'):
        # Extract first two characters for step number
        step = filename.split('_')[0]
        return step
    return "unknown"

def _get_prompt_path(path: str) -> str:
    """Get corresponding prompt file path"""
    step = _get_step_from_path(path)
    if step != "unknown":
        return f"prompts/prompt_{step}*.md"
    return "prompts/*.md"

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
        v = Draft202012Validator(
            schema, 
            resolver=resolver,
            format_checker=Draft202012Validator.FORMAT_CHECKER
        )
        errors = sorted(v.iter_errors(data_for_validation), key=lambda e: e.path)
        
        # Enhance error messages with context
        enhanced_errors = []
        for e in errors:
            error_msg = f"{path}:{'/'.join(map(str, e.path))}: {e.message}"
            
            # Add context about what to do next
            step = _get_step_from_path(path)
            if step != "unknown":
                prompt_path = _get_prompt_path(path)
                error_msg += f"\n  See: {prompt_path} for guidance on requirements"
            
            enhanced_errors.append(error_msg)
            
        # If schema validation passed (or failed but we want to report everything), run deep logic checks
        # Only run deep checks if schema validation passed to avoid noise
        if not enhanced_errors:
            step = _get_step_from_path(path)
            
            deep_errors = []
            try:
                if step == "01":
                     # For Step 01, we need component IDs from step 02 if available
                     # For now, we pass None and let the validator handle it or just rely on schema
                     # In a real CLI run, we might want to load dependencies.
                     # However, the validator signature is (instance, toolkit_root, component_ids)
                     # We can try to load 02 if it exists relative to repo_root
                     # Try to find sketch relative to the file being validated (User Project)
                     sketch_path = os.path.join(os.path.dirname(path), "02_system_sketch.json")
                     if not os.path.exists(sketch_path):
                         # Fallback to toolkit root (Internal Testing)
                         sketch_path = os.path.join(repo_root, "spec", "02_system_sketch.json")
                     component_ids = None
                     if os.path.exists(sketch_path):
                         try:
                             with open(sketch_path) as f:
                                 cid_data = json.load(f)
                                 component_ids = {c.get("component_id") for c in cid_data.get("components", []) if c.get("component_id")}
                         except:
                             pass
                     deep_errors = step_01.validate_step_01(data, repo_root, component_ids)
                
                elif step == "02":
                    deep_errors = step_02.validate_step_02(data, repo_root)
                
                elif step == "03":
                    # Step 03 might need NFRs or Monitoring
                    deep_errors = step_03.validate_step_03(data, repo_root)

                elif step == "04":
                    deep_errors = step_04.validate_step_04(data, repo_root)
                
                elif step == "10":
                    deep_errors = step_10.validate_step_10(data, repo_root)
                
                elif step == "15":
                    deep_errors = step_15.validate_step_15(data, repo_root)

                elif step == "16":
                    deep_errors = step_16.validate_step_16(data, repo_root)
            
            except Exception as e:
                deep_errors = [f"Deep Validation Critical Error: {str(e)}"]

            if deep_errors:
                enhanced_errors.extend([f"{path}: {e}" for e in deep_errors])

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
