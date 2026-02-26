import json
import os
from typing import Optional, Set
from jsonschema import Draft202012Validator
from ...core.registry import SchemaRegistry
from ...core.trace_types import normalize_trace_type

def validate_trace_integrity(instance: dict, component_ids: Optional[Set[str]]) -> list:
    """
    Validates that capabilities trace to known components in the System Sketch.
    """
    errors = []
    if component_ids is None:
        return errors

    for cap in instance.get("capabilities", []):
        for trace in cap.get("trace", []):
            if normalize_trace_type(trace.get("type", "")) == "component":
                target_id = trace.get("id")
                if target_id not in component_ids:
                    errors.append(f"Capability '{cap.get('capability_id')}' traces to unknown component '{target_id}'")
    return errors

def validate_step_01(
    instance: dict, 
    repo_root: str,
    component_ids: Optional[Set[str]] = None
) -> list[str]:
    """
    Validation logic for Step 01 (Capabilities).
    Includes Schema Validation + Trace Integrity.
    """
    errors = []
    
    # 1. Schema Validation
    registry = SchemaRegistry(repo_root)
    schema = registry.load("https://specdev.local/schema/01_capabilities.schema.json")

    
    # Strip $schema if present
    data_for_validation = dict(instance)
    data_for_validation.pop("$schema", None)
    
    # Construct referencing Registry from the store
    from referencing import Registry, Resource
    registry_obj = Registry().with_resources([
        (uri, Resource.from_contents(content)) 
        for uri, content in registry.store.items()
    ])

    validator = Draft202012Validator(schema, registry=registry_obj)
    for err in validator.iter_errors(data_for_validation):

        errors.append(f"Schema Error: {err.message}")

    # 2. Trace Integrity (if component_ids provided)
    if component_ids:
        custom_errors = validate_trace_integrity(instance, component_ids)
        errors.extend(custom_errors)
        
    return errors
