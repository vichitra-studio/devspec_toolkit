import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.fixtures_lint import lint_fixtures
from specdev_tools.core.errors import render_errors


class FixturesLintTests(unittest.TestCase):
    def test_status_required_only_for_contract_mode(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "08_fixtures.json").write_text(
                json.dumps(
                    {
                        "$schema": "vc:08-fixtures",
                        "fixtures": [
                            {
                                "fixture_id": "fx-1",
                                "targets": [{"type": "fr", "id": "fr-1"}],
                                "mode": "unit",
                                "input": {},
                                "expected": {}
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (root / "04_fr_list.json").write_text(
                json.dumps(
                    {
                        "$schema": "vc:04-fr-list",
                        "functional_requirements": [{"fr_id": "fr-1"}],
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_fixtures(str(root))
            self.assertFalse(any("expected.status" in e for e in render_errors(errs)))

    def test_inv_alias_normalization(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "08_fixtures.json").write_text(
                json.dumps(
                    {
                        "$schema": "vc:08-fixtures",
                        "fixtures": [
                            {
                                "fixture_id": "fx-1",
                                "targets": [{"type": "inv", "id": "inv-1"}],
                                "mode": "unit",
                                "input": {},
                                "expected": {}
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (root / "06_invariants.json").write_text(
                json.dumps(
                    {
                        "$schema": "vc:06-invariants",
                        "rules": [{"inv_id": "inv-1"}],
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_fixtures(str(root))
            self.assertEqual([], errs)


if __name__ == "__main__":
    unittest.main()
