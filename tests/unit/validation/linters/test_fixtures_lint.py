import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from specdev_tools.validation.fixtures_lint import lint_fixtures
from specdev_tools.core.errors import render_errors

# The lint recognises a step 08 artifact by the suffix of its ``$schema``.
_FIXTURES_SCHEMA = "https://example.invalid/schema/08_fixtures.schema.json"


def _lint(fixtures: list[Any]) -> list[str]:
    """Render the findings of ``lint_fixtures`` over a spec dir that holds one step 08 artifact."""
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "08_fixtures.json").write_text(
            json.dumps({"$schema": _FIXTURES_SCHEMA, "fixtures": fixtures}), encoding="utf-8"
        )
        return render_errors(lint_fixtures(td))


class FixturesLintTests(unittest.TestCase):
    def test_status_required_only_for_contract_mode(self):
        unit = {"fixture_id": "fx-1", "mode": "unit", "input": {}, "expected": {}}
        contract = {**unit, "fixture_id": "fx-2", "mode": "contract"}
        rendered = _lint([unit, contract])
        self.assertFalse(any("fx-1" in e for e in rendered), rendered)
        self.assertTrue(any("fx-2" in e and "expected.status" in e for e in rendered), rendered)

    def test_missing_targets_no_longer_e520(self):
        rendered = _lint([{"fixture_id": "fx-1", "mode": "unit", "input": {}, "expected": {}}])
        self.assertEqual(rendered, [])

    def test_fixture_targets_are_not_read(self):
        targets = [{"type": "fr", "id": "fr-nowhere"}, "not-a-target"]
        rendered = _lint([{"fixture_id": "fx-1", "targets": targets, "mode": "unit", "input": {}, "expected": {}}])
        self.assertEqual(rendered, [])

    def test_input_expected_status_header_checks_unchanged(self):
        base = {"mode": "contract", "input": {}}
        cases = {
            "fx-no-input": ({"fixture_id": "fx-no-input", "mode": "unit", "expected": {}}, "missing input/expected"),
            "fx-bad-status": ({**base, "fixture_id": "fx-bad-status", "expected": {"status": 42}}, "expected.status"),
            "fx-bad-headers": ({**base, "fixture_id": "fx-bad-headers", "expected": {"status": 200, "headers": []}}, "expected.headers"),
            "fx-not-dict": ({**base, "fixture_id": "fx-not-dict", "expected": "ok"}, "expected should be a dictionary"),
        }
        for fixture_id, (fixture, needle) in cases.items():
            with self.subTest(fixture=fixture_id):
                rendered = _lint([fixture])
                self.assertTrue(any(fixture_id in e and needle in e for e in rendered), rendered)

    def test_wrong_typed_entries_do_not_raise(self):
        self.assertEqual(_lint([7, "fix-a", None, ["x"]]), [])


if __name__ == "__main__":
    unittest.main()
