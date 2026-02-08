import json
import os
import sys
from referencing import Registry, Resource
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

# Paths
TOOLKIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
SCHEMA_DIR = os.path.join(TOOLKIT_ROOT, "schema")
FIXTURES_DIR = os.path.join(TOOLKIT_ROOT, "tests", "fixtures", "seed_manifest")

def load_schema_store(schema_dir):
    store = {}
    for root, _, files in os.walk(schema_dir):
        for file in files:
            if file.endswith(".json"):
                path = os.path.join(root, file)
                with open(path) as f:
                    try:
                        schema = json.load(f)
                        if "$id" in schema:
                            store[schema["$id"]] = Resource.from_contents(schema)
                    except Exception as e:
                        print(f"Skipping {path}: {e}")
    return store

def validate_file(validator, file_path, should_pass=True):
    print(f"\nValidating {file_path} (Expect {'PASS' if should_pass else 'FAIL'})...")
    with open(file_path) as f:
        instance = json.load(f)

    try:
        validator.validate(instance)
        if should_pass:
            print("✅ PASS")
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
            print(f"Context: {e.path}")
            return False

def main():
    print("Loading schemas...")
    store = load_schema_store(SCHEMA_DIR)
    registry = Registry().with_resources(store.items())

    with open(os.path.join(SCHEMA_DIR, "seed_manifest.schema.json")) as f:
        schema = json.load(f)

    validator = Draft202012Validator(
        schema,
        registry=registry,
    )

    valid_fixture = os.path.join(FIXTURES_DIR, "valid_minimal.json")
    invalid_fixture = os.path.join(FIXTURES_DIR, "invalid_missing_required.json")

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
