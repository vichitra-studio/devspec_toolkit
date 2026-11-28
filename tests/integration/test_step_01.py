import os
import sys
import unittest
from pathlib import Path

from specdev_tools.validation.validate import validate_file as specdev_validate_file

TOOLKIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
FIXTURES_DIR = os.path.join(TOOLKIT_ROOT, "tests", "fixtures", "step_01")


def schema_errors(file_path: str) -> list[str]:
    """Rendered schema (E520) and deep-validator errors for one fixture.

    Canonical-integrity and quality-lint results are excluded: the fixtures use
    project-tier canonical ids that core canon does not know (E110), and this
    test only checks the step-01 schema and deep validator.
    """
    errors = specdev_validate_file(
        TOOLKIT_ROOT,
        file_path,
        include_quality_lint=False,
        include_canonical_integrity=False,
    )
    return [e.render() for e in errors if e.code.startswith("E")]


def validate_fixture(file_path: str, should_pass: bool) -> bool:
    errors = schema_errors(file_path)
    passed = not errors

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


def main() -> None:
    # Schema validation runs first (as validate.py does); the step-01 deep
    # validator then has no content check left to add.
    cases = [("valid_minimal.json", True), ("invalid_missing_required.json", False)]

    results = []
    for fixture, should_pass in cases:
        path = os.path.join(FIXTURES_DIR, fixture)
        if os.path.exists(path):
            results.append(validate_fixture(path, should_pass))
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


class Step01IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixtures_dir = Path(FIXTURES_DIR)

    def _assert_fails_naming(self, fixture: str, needle: str) -> None:
        rendered = schema_errors(str(self.fixtures_dir / fixture))
        self.assertTrue(rendered, f"Expected schema errors for {fixture}")
        self.assertTrue(
            any(needle in msg for msg in rendered),
            f"Expected an error mentioning {needle!r}, got: {rendered}",
        )

    def test_capability_scope_future_fails(self):
        self._assert_fails_naming("invalid_scope_future.json", "'future' is not one of")

    def test_capability_scope_later_without_scope_reason_fails(self):
        self._assert_fails_naming("invalid_later_without_scope_reason.json", "scope_reason")

    def test_capability_empty_derives_from_fails(self):
        self._assert_fails_naming("invalid_empty_derives_from.json", "derives_from")

    def test_capability_derives_from_metric_id_passes_schema(self):
        self.assertEqual(schema_errors(str(self.fixtures_dir / "valid_derives_from_metric.json")), [])
