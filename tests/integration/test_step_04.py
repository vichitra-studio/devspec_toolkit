#!/usr/bin/env python3
"""Thin CLI wrapper for Step 04 validation.

Invokes the real ``specdev validate`` command against the given fixture.
Exit code mirrors the validator's exit code (0 = pass, 1 = fail).
"""

import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: test_step_04.py <fixture>")
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
_VALID_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "step_04" / "valid_comprehensive.json"


class Step04IntegrationTests(unittest.TestCase):
    def _schema_errors(self, mutate: Callable[[dict], None]) -> list[str]:
        """Rendered E520 errors for the valid fixture after ``mutate`` edits a copy."""
        spec = json.loads(_VALID_FIXTURE.read_text())
        mutate(spec)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "04_fr_list.json"
            path.write_text(json.dumps(spec))
            errors = specdev_validate_file(str(_REPO_ROOT), str(path))
        return [e.render() for e in errors if e.code == "E520"]

    def test_valid_fixture_has_no_schema_errors(self):
        self.assertEqual(self._schema_errors(lambda spec: None), [])

    def test_fr_without_derives_from_fails(self):
        rendered = self._schema_errors(
            lambda spec: spec["functional_requirements"][0].pop("derives_from")
        )
        self.assertTrue(any("derives_from" in msg for msg in rendered), rendered)

    def test_fr_scope_out_without_reason_fails(self):
        rendered = self._schema_errors(
            lambda spec: spec["functional_requirements"][0].update(scope="out")
        )
        self.assertTrue(any("scope_reason" in msg for msg in rendered), rendered)

    def test_fr_depends_on_self_reference_parses(self):
        def self_reference(spec: dict) -> None:
            fr = spec["functional_requirements"][0]
            fr["depends_on"] = [fr["fr_id"]]

        self.assertEqual(self._schema_errors(self_reference), [])

    def test_invalid_bad_derives_from_fixture_fails(self):
        """invalid_bad_derives_from.json must fail on the id pattern of derives_from[0]."""
        errors = specdev_validate_file(
            str(_REPO_ROOT), str(_REPO_ROOT / "tests" / "fixtures" / "step_04" / "invalid_bad_derives_from.json")
        )
        rendered = [e.render() for e in errors if e.code == "E520" and "Unevaluated properties" not in e.render()]
        self.assertTrue(
            any("functional_requirements/0/derives_from/0" in msg and "does not match" in msg for msg in rendered),
            rendered,
        )
