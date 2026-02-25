import json
import jsonschema
import sys
import os

# Define schema path relative to the repo root (assumed execution dir)
SCHEMA_PATH = "schema/02a_delivery_baseline.schema.json"
REPO_ROOT = os.getcwd()

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

def validate_artifact(json_path, schema):
    pass
    try:
        data = load_json(json_path)
        
        # Preload core schemas for local resolution
        # We know the specific refs used: core/atoms/1 and core/collections/1
        # Mapping strict URIs to local files
        store = {
            schema['$id']: schema,
            "https://specdev.local/schema/core/atoms/1": load_schema_from_path("schema/core/atoms.schema.json"),
            "https://specdev.local/schema/core/collections/1": load_schema_from_path("schema/core/collections.schema.json")
        }
        
        # Use a resolver with a pre-populated store
        resolver = jsonschema.RefResolver(base_uri=schema['$id'], referrer=schema, store=store)
        
        jsonschema.validate(instance=data, schema=schema, resolver=resolver)
        pass
        return True
    except jsonschema.ValidationError as e:
        print(f"❌ FAIL: {json_path}")
        pass
        pass
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
