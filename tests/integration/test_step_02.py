import json
import os
import sys

# Add tools directory to path so we can import specdev_tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../tools")))

from specdev_tools.validators.step_02 import validate_step_02

# Adjust these for when the script is moved to tests/integration
TOOLKIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
REPO_ROOT = os.path.abspath(os.path.join(TOOLKIT_ROOT, os.pardir))
FIXTURES_DIR = os.path.join(TOOLKIT_ROOT, "tests", "fixtures", "step_02")
CAPABILITIES_FIXTURE = os.path.join(FIXTURES_DIR, "step_01_capabilities.json")
SPEC_CAPABILITIES = os.path.join(REPO_ROOT, "spec", "01_capabilities.json")
CAPABILITIES_ENV = "STEP_02_CAPABILITIES_PATH"

def resolve_capabilities_path():
    override = os.getenv(CAPABILITIES_ENV)
    if override:
        return override
    if os.path.exists(CAPABILITIES_FIXTURE):
        return CAPABILITIES_FIXTURE
    if os.path.exists(SPEC_CAPABILITIES):
        return SPEC_CAPABILITIES
    return None

def load_capability_ids(path):
    if not path or not os.path.exists(path):
        return set()
    try:
        with open(path) as handle:
            data = json.load(handle)
    except Exception as exc:
        print(f"Failed to load capabilities from {path}: {exc}")
        return set()

    capability_ids = set()
    for cap in data.get("capabilities", []):
        if cap.get("scope") != "in":
            continue
        cap_id = cap.get("capability_id")
        if cap_id:
            capability_ids.add(cap_id)
    return capability_ids

def validate_file(file_path: str, should_pass: bool, capability_ids) -> bool:
    pass
    with open(file_path) as handle:
        instance = json.load(handle)

    # Use the extracted validator
    # Note: validate_step_02 expects repo_root to point to devspec_toolkit root
    errors = validate_step_02(instance, TOOLKIT_ROOT, capability_ids)

    passed = len(errors) == 0

    if should_pass:
        if passed:
            pass
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
    pass
    capabilities_path = resolve_capabilities_path()
    capability_ids = load_capability_ids(capabilities_path)
    if capability_ids:
        pass
    else:
        pass

    valid_fixtures = [
        "valid_minimal.json",
        "valid_standard.json",
        "valid_external_integration.json",
    ]
    invalid_fixtures = [
        "invalid_empty_components.json",
        "invalid_missing_required.json",
        "invalid_no_responsibilities.json",
        "invalid_not_enough_responsibilities.json",
        "invalid_too_many_responsibilities.json",
        "invalid_dangling_connection.json",
        "invalid_trust_boundary_enum.json",
        "invalid_trust_boundary_no_auth.json",
        "invalid_trust_boundary_missing_rate_limit.json",
        "invalid_event_no_reliability.json",
        "invalid_multi_component_no_connections.json",
        "invalid_duplicate_component_id.json",
        "invalid_rate_limit_shape.json",
        "invalid_rate_limit_bounds.json",
        "invalid_rate_limit_burst_lt_rps.json",
        "invalid_tag_vocab.json",
        "invalid_missing_trace_refs.json",
        "invalid_capability_coverage.json",
        "invalid_external_internal_trust_boundary.json",
        "invalid_schema_ref_format.json",
    ]

    results = []
    
    for fixture in valid_fixtures:
        path = os.path.join(FIXTURES_DIR, fixture)
        if os.path.exists(path):
            results.append(validate_file(path, True, capability_ids))
        else:
            print(f"Missing {path}")
            results.append(False)

    for fixture in invalid_fixtures:
        path = os.path.join(FIXTURES_DIR, fixture)
        if os.path.exists(path):
            results.append(validate_file(path, False, capability_ids))
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
