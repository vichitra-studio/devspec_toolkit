#!/usr/bin/env python3
"""Thin CLI wrapper for Step 08 validation.

Invokes the real ``specdev validate`` command against the given fixture.
Exit code mirrors the validator's exit code (0 = pass, 1 = fail).
"""

import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: test_step_08.py <fixture>")
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
from typing import Any, Callable

from specdev_tools.validation.validate import validate_file as specdev_validate_file

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "step_08"

# The worked example of the spec-graph design (fixture "New" form): `targets` becomes `verifies`.
_DOC_EXAMPLE_FIXTURE: dict[str, Any] = {
    "fixture_id": "fix-password-reset-expired-token",
    "mode": "contract",
    "description": "The confirm endpoint rejects a token issued 31 minutes earlier and leaves the password unchanged.",
    "verifies": ["ac-password-reset-3", "api-password-reset-confirm"],
    "input": {
        "method": "POST",
        "path": "/v1/password-resets/tok-fixture-expired",
        "body": {"new_password": "N3w-Passw0rd!"},
    },
    "expected": {"status": 410, "body": {"error": "token-expired"}},
    "tag_ref": {"id": "cn:core:tag:critical-path", "kind": "tag"},
}


class Step08IntegrationTests(unittest.TestCase):
    def _errors(self, spec: dict[str, Any]) -> list[str]:
        """Rendered E520 errors for a step 08 document."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "08_fixtures.json"
            path.write_text(json.dumps(spec))
            errors = specdev_validate_file(str(_REPO_ROOT), str(path))
        return [e.render() for e in errors if e.code == "E520"]

    def _fixture_errors(self, mutate: Callable[[dict], None]) -> list[str]:
        """Schema errors for the design-doc fixture after ``mutate`` edits a copy of it."""
        spec = json.loads((_FIXTURES / "valid" / "valid_generic.json").read_text())
        fixture = json.loads(json.dumps(_DOC_EXAMPLE_FIXTURE))
        mutate(fixture)
        spec["fixtures"] = [fixture]
        return self._errors(spec)

    def _assert_fixture_fails_naming(self, mutate: Callable[[dict], None], needle: str) -> None:
        rendered = self._fixture_errors(mutate)
        self.assertTrue(any(needle in msg for msg in rendered), rendered)

    def test_valid_fixture_files_have_no_schema_errors(self):
        for name in ("valid_generic.json", "valid_http.json"):
            with self.subTest(fixture=name):
                spec = json.loads((_FIXTURES / "valid" / name).read_text())
                self.assertEqual(self._errors(spec), [])

    def test_doc_example_validates(self):
        self.assertEqual(self._fixture_errors(lambda fixture: None), [])

    def test_fixture_with_neither_verifies_nor_removes_fails(self):
        spec = json.loads((_FIXTURES / "invalid" / "invalid_missing_verifies.json").read_text())
        for rendered in (self._errors(spec), self._fixture_errors(lambda fixture: fixture.pop("verifies"))):
            self.assertTrue(any("is not valid under any of the given schemas" in msg for msg in rendered), rendered)

    def test_removal_fixture_validates_without_verifies(self):
        def removal(fixture: dict) -> None:
            fixture.pop("verifies")
            fixture["removes"] = ["api-password-reset-legacy"]

        self.assertEqual(self._fixture_errors(removal), [])

    def test_manual_fixture_without_manual_reason_fails(self):
        self._assert_fixture_fails_naming(lambda fixture: fixture.update(mode="manual"), "manual_reason")

    def test_manual_fixture_with_manual_reason_validates(self):
        self.assertEqual(
            self._fixture_errors(
                lambda fixture: fixture.update(mode="manual", manual_reason="A person judges the printed receipt layout")
            ),
            [],
        )

    def test_old_targets_and_out_of_scope_fail(self):
        spec = json.loads((_FIXTURES / "valid" / "valid_generic.json").read_text())
        spec["fixtures"][0]["targets"] = [{"type": "fr", "id": "fr-data-processing"}]
        spec["out_of_scope"] = [{"fr_id": "fr-legacy-report-export", "rationale": "Deferred to a later phase."}]
        rendered = self._errors(spec)
        self.assertTrue(any("targets" in msg for msg in rendered), rendered)
        self.assertTrue(any("out_of_scope" in msg for msg in rendered), rendered)

    def test_fixture_with_scope_fails(self):
        self._assert_fixture_fails_naming(lambda fixture: fixture.update(scope="in"), "scope")
