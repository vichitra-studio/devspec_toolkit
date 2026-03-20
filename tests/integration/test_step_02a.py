import json
import jsonschema
import sys
import os

from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

HAS_REFERENCING = True

# Define schema path relative to the repo root (assumed execution dir)
SCHEMA_PATH = "schema/02a_delivery_baseline.schema.json"
REPO_ROOT = os.getcwd()

# Map vc: URIs to local file paths for offline resolution
_URI_TO_PATH = {
    "vc:core:atoms": "schema/core/atoms.schema.json",
    "vc:core:collections": "schema/core/collections.schema.json",
    "vc:core:step-base": "schema/core/step_base.schema.json",
    "vc:core:errors": "schema/core/errors.schema.json",
}

def load_schema(schema_subpath):
    abs_path = os.path.join(REPO_ROOT, schema_subpath)
    if not os.path.exists(abs_path):
        print(f"Error: Schema not found at {abs_path}")
        sys.exit(1)
    with open(abs_path, 'r') as f:
        return json.load(f)

def load_json(json_path):
    with open(json_path, 'r') as f:
        return json.load(f)

def load_schema_from_path(rel_path):
    abs_path = os.path.join(REPO_ROOT, rel_path)
    if not os.path.exists(abs_path):
        print(f"Warning: Referenced schema not found at {abs_path}")
        return {}
    with open(abs_path, 'r') as f:
        return json.load(f)

def _build_registry(schema):
    """Build a referencing.Registry with all core schemas for offline resolution."""
    if HAS_REFERENCING:
        resources = [(schema.get("$id", ""), Resource.from_contents(schema, default_specification=DRAFT202012))]
        for uri, path in _URI_TO_PATH.items():
            core = load_schema_from_path(path)
            if core:
                resources.append((uri, Resource.from_contents(core, default_specification=DRAFT202012)))
        return Registry().with_resources(resources)
    return None

def _build_resolver(schema):
    """Build a legacy RefResolver with a store and a handler that resolves vc: URIs locally."""
    store = {schema['$id']: schema}
    for uri, path in _URI_TO_PATH.items():
        core = load_schema_from_path(path)
        if core:
            store[uri] = core

    def _local_handler(uri):
        if uri in store:
            return store[uri]
        raise jsonschema.RefResolutionError(f"Cannot resolve {uri} (no network access)")

    return jsonschema.RefResolver(
        base_uri=schema['$id'],
        referrer=schema,
        store=store,
        handlers={"https": _local_handler},
    )

def validate_artifact(json_path, schema):
    try:
        data = load_json(json_path)

        if HAS_REFERENCING:
            registry = _build_registry(schema)
            validator_cls = jsonschema.validators.validator_for(schema)  # type: ignore[attr-defined]
            validator = validator_cls(schema, registry=registry)
            validator.validate(data)
        else:
            resolver = _build_resolver(schema)
            jsonschema.validate(instance=data, schema=schema, resolver=resolver)

        return True
    except jsonschema.ValidationError as e:
        print(f"❌ FAIL: {json_path}")
        return False
    except Exception as e:
        print(f"⚠️ ERROR: {e}")
        return False

def run_self_test(schema):
    pass
    fixtures_dir = os.path.join(REPO_ROOT, "tests/fixtures/step_02a")
    if not os.path.exists(fixtures_dir):
        print(f"Error: Fixtures directory not found at {fixtures_dir}")
        return False
    
    # Expected results: filename -> should_pass
    expectations = {
        "valid_minimal.json": True,
        "invalid_empty_env.json": False,
        "invalid_gates.json": False,
        "invalid_gate_format.json": False
    }
    
    all_passed = True
    for filename in os.listdir(fixtures_dir):
        if not filename.endswith(".json"):
            continue
            
        full_path = os.path.join(fixtures_dir, filename)
        should_pass = expectations.get(filename, True) # Default to True unless known invalid
        
        pass
        actual_result = validate_artifact(full_path, schema)
        
        if actual_result != should_pass:
            print(f"🚨 MISMATCH: Expected {should_pass}, got {actual_result}")
            all_passed = False
        else:
            pass
            
    return all_passed

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/verify_step_02a.py <path_to_artifact.json> | --self-test")
        sys.exit(1)

    schema = load_schema(SCHEMA_PATH)

    if sys.argv[1] == "--self-test":
        success = run_self_test(schema)
    else:
        target_file = sys.argv[1]
        success = validate_artifact(target_file, schema)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
