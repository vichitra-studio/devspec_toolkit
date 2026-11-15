#!/usr/bin/env python3
"""Thin CLI wrapper for Step 05 validation.

Invokes the real ``specdev validate`` command against the given fixture.
Exit code mirrors the validator's exit code (0 = pass, 1 = fail).
"""

import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: test_step_05.py <fixture>")
    fixture = Path(sys.argv[1])
    toolkit_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "validate", str(fixture),
         "--repo-root", str(toolkit_root)],
        cwd=str(toolkit_root),
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Pytest-style tests
# ---------------------------------------------------------------------------

import json
import tempfile
import unittest
from typing import Callable

from specdev_tools.validation.validate import validate_file as specdev_validate_file

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "step_05"


class Step05IntegrationTests(unittest.TestCase):
    def _schema_errors(self, fixture: str, mutate: Callable[[dict], None]) -> list[str]:
        """Rendered E520 errors for a step_05 fixture after ``mutate`` edits a copy."""
        spec = json.loads((_FIXTURES / fixture).read_text())
        mutate(spec)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "05_interface_contracts.json"
            path.write_text(json.dumps(spec))
            errors = specdev_validate_file(str(_REPO_ROOT), str(path))
        return [e.render() for e in errors if e.code == "E520"]

    def _assert_valid_fixture_fails_naming(self, mutate: Callable[[dict], None], needle: str) -> None:
        rendered = self._schema_errors("valid_rest_api.json", mutate)
        self.assertTrue(any(needle in msg for msg in rendered), rendered)

    def test_valid_fixture_has_no_schema_errors(self):
        self.assertEqual(self._schema_errors("valid_rest_api.json", lambda spec: None), [])

    def test_api_without_derives_from_fails(self):
        rendered = self._schema_errors("invalid_missing_derives_from.json", lambda spec: None)
        self.assertTrue(any("derives_from" in msg for msg in rendered), rendered)

    def test_api_error_without_error_id_fails(self):
        self._assert_valid_fixture_fails_naming(
            lambda spec: spec["apis"][0]["errors"][0].pop("error_id"), "error_id"
        )

    def test_api_with_example_refs_fails(self):
        self._assert_valid_fixture_fails_naming(
            lambda spec: spec["apis"][0].update(example_refs=["fixture-login"]), "example_refs"
        )

    def test_api_error_empty_derives_from_fails(self):
        self._assert_valid_fixture_fails_naming(
            lambda spec: spec["apis"][0]["errors"][0].update(derives_from=[]), "derives_from"
        )

    def test_invalid_bad_protocol_fixture_fails(self):
        """invalid_bad_protocol.json must fail because protocol is not in the protocol enum."""
        rendered = [
            m
            for m in self._schema_errors("invalid_bad_protocol.json", lambda spec: None)
            if "Unevaluated properties" not in m
        ]
        self.assertTrue(
            any("apis/0/protocol" in msg and "'invalid-protocol' is not one of" in msg for msg in rendered), rendered
        )
