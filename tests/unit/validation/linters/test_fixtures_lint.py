import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from specdev_tools.validation.fixtures_lint import lint_fixtures
from specdev_tools.core.errors import render_errors

# The lint recognises a step 08 artifact by the registry id or by the suffix of its ``$schema``.
_FIXTURES_SCHEMA = "https://example.invalid/schema/08_fixtures.schema.json"
_REGISTRY_ID = "vc:08-fixtures"
_WORKED_EXAMPLE_SPEC = Path(__file__).resolve().parents[3] / "fixtures" / "graph_example" / "spec"


def _lint(fixtures: list[Any], schema: str = _FIXTURES_SCHEMA, apis: list[Any] | None = None) -> list[str]:
    """Render the findings of ``lint_fixtures`` over a spec dir that holds one step 08 artifact (and a step 05 one with *apis*)."""
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "08_fixtures.json").write_text(
            json.dumps({"$schema": schema, "fixtures": fixtures}), encoding="utf-8"
        )
        if apis is not None:
            (Path(td) / "05_interface_contracts.json").write_text(
                json.dumps({"$schema": "vc:05-interface-contracts", "apis": apis}), encoding="utf-8"
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

    def test_contract_status_follows_the_protocol_of_the_apis_the_fixture_verifies(self):
        """An HTTP status unless the fixture names APIs and none is an HTTP API: then the number of that protocol, 0 or more."""
        apis = [{"api_id": "api-web", "protocol": "http"}, {"api_id": "api-rpc", "protocol": "grpc"}, {"api_id": "api-bare"}, 7]
        def found(verifies: Any, status: Any) -> list[str]:
            return _lint([{"fixture_id": "fx-1", "mode": "contract", "input": {}, "expected": {"status": status}, "verifies": verifies}], apis=apis)
        self.assertEqual(found(["api-rpc"], 5), [])
        self.assertEqual(found(["api-rpc"], 0), [])
        self.assertEqual(found(["api-rpc", "ac-some-criterion"], 5), [])
        for status in (-1, True, "5", 5.0, None):
            with self.subTest(status=status):
                self.assertTrue(any("status number of the API's protocol (an integer of 0 or more)" in e for e in found(["api-rpc"], status)))
        for verifies in (["api-web"], ["api-web", "api-rpc"], ["api-rpc", "api-web"], ["api-bare"], ["ac-some-criterion"], [], None, "api-rpc"):
            with self.subTest(verifies=verifies):
                self.assertTrue(any("must be an HTTP status (100-599)" in e for e in found(verifies, 5)), verifies)
                self.assertEqual(found(verifies, 404), [])
        self.assertEqual(found([["api-rpc"], {"a": 1}, 7, "api-rpc"], 5), [])  # wrong-typed entries are passed over, never raised on

    def test_contract_status_follows_the_protocol_of_the_error_the_fixture_expects(self):
        """A negative-case fixture that verifies an invariant names its API through the error it expects."""
        apis = [
            {"api_id": "api-rpc", "protocol": "grpc", "errors": [{"error_id": "err-rpc-gone"}, 7, {"error_id": ["x"]}]},
            {"api_id": "api-web", "protocol": "http", "errors": [{"error_id": "err-web-gone"}]},
            {"api_id": ["unhashable"], "protocol": "grpc", "errors": "not a list"},
        ]
        def found(expects: Any, status: Any, verifies: Any = ("inv-some-rule",)) -> list[str]:
            fixture = {"fixture_id": "fx-1", "mode": "contract", "input": {}, "expected": {"status": status}, "verifies": list(verifies), "expects": expects}
            return _lint([fixture], apis=apis)
        self.assertEqual(found(["err-rpc-gone"], 5), [])
        self.assertEqual(found(["err-web-gone"], 404), [])
        for expects in (["err-web-gone"], ["err-rpc-gone", "err-web-gone"], ["err-nobody"], [], None):
            with self.subTest(expects=expects):
                rendered = found(expects, 5)
                self.assertTrue(any("must be an HTTP status (100-599)" in e and "names that API in verifies, or its error in expects" in e for e in rendered))
        self.assertTrue(found(["err-rpc-gone"], 5, verifies=["api-web"]))  # an HTTP API named in verifies keeps the HTTP rule

    def test_the_way_out_is_said_only_in_a_spec_with_an_api_of_another_protocol(self):
        fixture = {"fixture_id": "fx-1", "mode": "contract", "input": {}, "expected": {"status": 42}}
        for apis in (None, [], [{"api_id": "api-web", "protocol": "http"}, {"api_id": "api-bare"}]):
            with self.subTest(apis=apis):
                rendered = _lint([fixture], apis=apis)
                self.assertTrue(len(rendered) == 1 and rendered[0].endswith("for mode 'contract'"), rendered)

    def test_an_unreadable_step_05_file_keeps_the_http_rule(self):
        fixture = {"fixture_id": "fx-1", "mode": "contract", "input": {}, "expected": {"status": 5}, "verifies": ["api-rpc"]}
        for text in ("{ not json", json.dumps({"$schema": "vc:05-interface-contracts", "apis": None}), json.dumps(["a list"])):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as td:
                (Path(td) / "08_fixtures.json").write_text(json.dumps({"$schema": _REGISTRY_ID, "fixtures": [fixture]}), encoding="utf-8")
                (Path(td) / "05_interface_contracts.json").write_text(text, encoding="utf-8")
                self.assertTrue(any("must be an HTTP status (100-599)" in e for e in render_errors(lint_fixtures(td))))

    def test_contract_status_without_a_step_05_file_is_an_http_status(self):
        fixture = {"fixture_id": "fx-1", "mode": "contract", "input": {}, "expected": {"status": 5}, "verifies": ["api-rpc"]}
        self.assertTrue(any("must be an HTTP status (100-599)" in e for e in _lint([fixture])))

    def test_wrong_typed_entries_do_not_raise(self):
        self.assertEqual(_lint([7, "fix-a", None, ["x"]]), [])

    def test_file_with_registry_id_is_read(self):
        rendered = _lint([{"fixture_id": "fx-bad-status", "mode": "contract", "input": {}, "expected": {"status": 42}}], _REGISTRY_ID)
        self.assertTrue(any("fx-bad-status" in e and "expected.status" in e for e in rendered), rendered)

    def test_file_with_legacy_suffix_is_still_read(self):
        rendered = _lint([{"fixture_id": "fx-bad-status", "mode": "contract", "input": {}, "expected": {"status": 42}}], _FIXTURES_SCHEMA)
        self.assertTrue(any("fx-bad-status" in e and "expected.status" in e for e in rendered), rendered)

    def test_worked_example_fixtures_pass(self):
        self.assertEqual(render_errors(lint_fixtures(str(_WORKED_EXAMPLE_SPEC))), [])

    def test_fixture_without_expected_in_registry_id_file_is_e520(self):
        rendered = _lint([{"fixture_id": "fx-no-expected", "mode": "unit", "input": {}}], _REGISTRY_ID)
        self.assertTrue(any("E520" in e and "fx-no-expected" in e and "missing input/expected" in e for e in rendered), rendered)


if __name__ == "__main__":
    unittest.main()
