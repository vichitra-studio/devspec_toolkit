import json
import os
import sys

from specdev_tools.validation.validators.step_01 import validate_step_01

# Adjust these for when the script is moved to tests/integration
TOOLKIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
REPO_ROOT = os.path.abspath(os.path.join(TOOLKIT_ROOT, os.pardir))
FIXTURES_DIR = os.path.join(TOOLKIT_ROOT, "tests", "fixtures", "step_01")
SYSTEM_SKETCH_PATH = os.path.join(REPO_ROOT, "spec", "02_system_sketch.json")

def load_system_sketch_components(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
            components = data.get("components", [])
            return {
                c.get("component_id") 
                for c in components 
                if c.get("component_id")
            }
    except Exception as e:
        print(f"Warning: Failed to load system sketch components: {e}")
        return None

def validate_file(file_path: str, should_pass: bool, component_ids) -> bool:
    with open(file_path) as handle:
        instance = json.load(handle)

    errors = validate_step_01(instance, TOOLKIT_ROOT, component_ids)

    passed = len(errors) == 0

    if should_pass:
        if passed:
            return True
        for err in errors:
            print(f"❌ FAIL: {err}")
        return False

    if passed:
        print("❌ FAIL (Unexpected Pass)")
        return False

    if errors:
        print(f"✅ Expected Failure: {errors[0]}")
    return True

def main() -> None:
    component_ids = load_system_sketch_components(SYSTEM_SKETCH_PATH)
    
    valid_fixtures = ["valid_minimal.json"]
    invalid_fixtures = ["invalid_missing_required.json"]

    results = []
    
    for fixture in valid_fixtures:
        path = os.path.join(FIXTURES_DIR, fixture)
        if os.path.exists(path):
            results.append(validate_file(path, True, component_ids))
        else:
            print(f"Missing {path}")
            results.append(False)

    for fixture in invalid_fixtures:
        path = os.path.join(FIXTURES_DIR, fixture)
        if os.path.exists(path):
            results.append(validate_file(path, False, component_ids))
        else:
            print(f"Missing {path}")
            results.append(False)

    if all(results):
        print("\n🎉 All tests passed!")
        sys.exit(0)

    print("\n💀 Some tests failed.")
    sys.exit(1)

if __name__ == "__main__":
    main()
