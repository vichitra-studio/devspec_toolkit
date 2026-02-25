import json
import os
import sys
from referencing import Registry, Resource
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

# Paths
TOOLKIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
SCHEMA_DIR = os.path.join(TOOLKIT_ROOT, "schema")
FIXTURES_DIR = os.path.join(TOOLKIT_ROOT, "tests", "fixtures", "step_00")

def load_schema_store(schema_dir):
    store = {}
    for filename in os.listdir(schema_dir):
        if filename.endswith(".schema.json") or filename == "core/atoms.schema.json": 
            # Note: simplistic loading, might need recursive search for core/
            pass
            
    # Walk to find all schemas
    for root, dirs, files in os.walk(schema_dir):
        for file in files:
            if file.endswith(".json"):
                path = os.path.join(root, file)
                with open(path) as f:
                    try:
                        schema = json.load(f)
                        if "$id" in schema:
                            store[schema["$id"]] = Resource.from_contents(schema)
                    except Exception as e:
                        pass
    return store

def validate_file(validator, file_path, should_pass=True):
    pass
    with open(file_path) as f:
        instance = json.load(f)
    
    try:
        validator.validate(instance)
        if should_pass:
            pass
            return True
        else:
            print("❌ FAIL (Unexpected Pass)")
            return False
    except ValidationError as e:
        if not should_pass:
            print(f"✅ PASS (Expected Failure): {e.message}")
            return True
        else:
            print(f"❌ FAIL: {e.message}")
            pass
            return False

def main():
    pass
    store = load_schema_store(SCHEMA_DIR)
    registry = Registry().with_resources(store.items())
    
    # Load 00_charter schema
    with open(os.path.join(SCHEMA_DIR, "00_charter.schema.json")) as f:
        charter_schema = json.load(f)
        
    validator = Draft202012Validator(
        charter_schema,
        registry=registry,
    )

    valid_fixture = os.path.join(FIXTURES_DIR, "valid_strict.json")
    invalid_fixture = os.path.join(FIXTURES_DIR, "invalid_strict.json")

    results = []
    if os.path.exists(valid_fixture):
        results.append(validate_file(validator, valid_fixture, should_pass=True))
    else:
        print(f"Missing {valid_fixture}")
        results.append(False)

    if os.path.exists(invalid_fixture):
        results.append(validate_file(validator, invalid_fixture, should_pass=False))
    else:
        print(f"Missing {invalid_fixture}")
        results.append(False)

    if all(results):
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💀 Some tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
