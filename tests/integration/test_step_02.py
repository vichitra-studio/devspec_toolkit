import json
import os
import shutil
import sys
import tempfile
import unittest
from functools import lru_cache

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.ids import check_unique_ids
from specdev_tools.validation.validators.step_02 import validate_step_02

TOOLKIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
SCHEMA_DIR = os.path.join(TOOLKIT_ROOT, "schema")
FIXTURES_DIR = os.path.join(TOOLKIT_ROOT, "tests", "fixtures", "step_02")
CAPABILITIES_FIXTURE = os.path.join(FIXTURES_DIR, "step_01_capabilities.json")
CAPABILITIES_ENV = "STEP_02_CAPABILITIES_PATH"
STEP_01_FILE_NAME = "01_capabilities.json"
STEP_02_FILE_NAME = "02_system_sketch.json"

VALID_FIXTURES = [
    "valid_minimal.json",
    "valid_standard.json",
    "valid_external_integration.json",
    "valid_no_tech_stack.json",
]
INVALID_FIXTURES = [
    "invalid_empty_components.json",
    "invalid_missing_required.json",
    "invalid_no_responsibilities.json",
    "invalid_not_enough_responsibilities.json",
    "invalid_too_many_responsibilities.json",
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
    "invalid_missing_derives_from.json",
    "invalid_component_empty_derives_from.json",
    "invalid_component_type_external.json",
    "invalid_connection_with_from.json",
    "invalid_third_party_without_pin.json",
    "invalid_capability_coverage.json",
    "invalid_external_internal_trust_boundary.json",
]


def resolve_capabilities_path() -> str:
    """Path of the Step 01 capabilities file used for the coverage check (env override, else the fixture)."""
    return os.getenv(CAPABILITIES_ENV) or CAPABILITIES_FIXTURE


@lru_cache(maxsize=1)
def _schema_validator() -> Draft202012Validator:
    resources = []
    for root, _dirs, files in os.walk(SCHEMA_DIR):
        for name in files:
            if not name.endswith(".json"):
                continue
            with open(os.path.join(root, name)) as handle:
                schema = json.load(handle)
            if "$id" in schema:
                resources.append((schema["$id"], Resource.from_contents(schema)))
    with open(os.path.join(SCHEMA_DIR, "02_system_sketch.schema.json")) as handle:
        sketch_schema = json.load(handle)
    return Draft202012Validator(sketch_schema, registry=Registry().with_resources(resources))


def collect_errors(file_path: str, spec_root: str) -> list[str]:
    """Return schema errors first, then (only when the schema passes) deep-validator and duplicate-id errors, as strings."""
    with open(file_path) as handle:
        instance = json.load(handle)
    schema_errors = [err.message for err in _schema_validator().iter_errors(instance)]
    if schema_errors:
        return schema_errors
    deep_errors = validate_step_02(instance, TOOLKIT_ROOT, spec_root)
    id_errors = check_unique_ids(build_graph(spec_root, TOOLKIT_ROOT, overrides={STEP_02_FILE_NAME: instance}))
    return [err.render() for err in (*deep_errors, *id_errors)]


def validate_file(file_path: str, should_pass: bool, spec_root: str) -> bool:
    errors = collect_errors(file_path, spec_root)
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

    print(f"✅ Expected Failure: {errors[0]}")
    return True


def make_spec_root(parent: str) -> str:
    """Create a spec folder under *parent* holding the Step 01 fixture where the validator looks for it."""
    spec_root = os.path.join(parent, "spec")
    os.makedirs(spec_root)
    shutil.copyfile(resolve_capabilities_path(), os.path.join(spec_root, STEP_01_FILE_NAME))
    return spec_root


def main() -> None:
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        spec_root = make_spec_root(tmp)
        for fixtures, should_pass in ((VALID_FIXTURES, True), (INVALID_FIXTURES, False)):
            for fixture in fixtures:
                path = os.path.join(FIXTURES_DIR, fixture)
                if os.path.exists(path):
                    results.append(validate_file(path, should_pass, spec_root))
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


# ---------------------------------------------------------------------------
# Pytest-style tests
# ---------------------------------------------------------------------------


class Step02IntegrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.spec_root = make_spec_root(tmp.name)

    def errors(self, fixture: str) -> list[str]:
        return collect_errors(os.path.join(FIXTURES_DIR, fixture), self.spec_root)

    def assert_fails_mentioning(self, fixture: str, *needles: str) -> None:
        errors = self.errors(fixture)
        self.assertTrue(errors, f"{fixture}: expected validation errors")
        rendered = " | ".join(errors)
        for needle in needles:
            self.assertIn(needle, rendered)

    def test_sketch_with_third_party_and_connects_to_passes(self):
        self.assertEqual(self.errors("valid_external_integration.json"), [])

    def test_component_type_external_fails(self):
        self.assert_fails_mentioning("invalid_component_type_external.json", "'external' is not one of")

    def test_connection_with_from_fails(self):
        self.assert_fails_mentioning("invalid_connection_with_from.json", "'from'")

    def test_third_party_without_pin_fails(self):
        self.assert_fails_mentioning("invalid_third_party_without_pin.json", "'pin' is a required property")

    def test_component_empty_derives_from_fails(self):
        self.assert_fails_mentioning("invalid_component_empty_derives_from.json", "[] should be non-empty")

    def test_sketch_without_tech_stack_passes(self):
        self.assertEqual(self.errors("valid_no_tech_stack.json"), [])
