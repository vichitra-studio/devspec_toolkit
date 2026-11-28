#!/usr/bin/env python3
"""Thin CLI wrapper for Step 06 validation.

Invokes the real ``specdev validate`` command against the given fixture.
Exit code mirrors the validator's exit code (0 = pass, 1 = fail).
"""

import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: test_step_06.py <fixture>")
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
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "step_06"

# The worked example of the spec-graph design (invariant "New" form): one relation, one field.
_DOC_EXAMPLE_INVARIANT: dict[str, Any] = {
    "inv_id": "inv-reset-token-single-use",
    "language": "text",
    "severity": "error",
    "enforcement_point": "service",
    "description": "The system ensures that a reset token changes a password at most once.",
    "expression": "redeem(token) succeeds only if token.used_at == null; a successful redeem sets token.used_at",
    "constrains": ["fr-password-reset", "api-password-reset-confirm", "identity-service"],
    "policy_ref": {"id": "cn:project:policy:auth-required", "kind": "policy"},
}


class Step06IntegrationTests(unittest.TestCase):
    def _schema_errors(self, fixture: str, mutate: Callable[[dict], None]) -> list[str]:
        """Rendered E520 errors for a step_06 fixture after ``mutate`` edits a copy."""
        spec = json.loads((_FIXTURES / fixture).read_text())
        mutate(spec)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "06_invariants.json"
            path.write_text(json.dumps(spec))
            errors = specdev_validate_file(str(_REPO_ROOT), str(path))
        return [e.render() for e in errors if e.code == "E520"]

    def _rule_errors(self, mutate: Callable[[dict], None]) -> list[str]:
        """Schema errors for the design-doc invariant after ``mutate`` edits a copy of the rule."""

        def edit(spec: dict) -> None:
            rule = json.loads(json.dumps(_DOC_EXAMPLE_INVARIANT))
            mutate(rule)
            spec["rules"] = [rule]

        return self._schema_errors("valid_full.json", edit)

    def _assert_rule_fails_naming(self, mutate: Callable[[dict], None], needle: str) -> None:
        rendered = self._rule_errors(mutate)
        self.assertTrue(any(needle in msg for msg in rendered), rendered)

    def test_valid_fixture_has_no_schema_errors(self):
        self.assertEqual(self._schema_errors("valid_full.json", lambda spec: None), [])

    def test_doc_example_validates(self):
        self.assertEqual(self._rule_errors(lambda rule: None), [])

    def test_invariant_without_constrains_validates(self):
        self.assertEqual(self._rule_errors(lambda rule: rule.pop("constrains")), [])

    def test_invariant_without_policy_ref_fails(self):
        self._assert_rule_fails_naming(lambda rule: rule.pop("policy_ref"), "policy_ref")

    def test_old_scope_object_fails(self):
        self._assert_rule_fails_naming(
            lambda rule: rule.update(scope={"components": ["identity-service"], "apis": ["api-password-reset-confirm"]}),
            "scope",
        )

    def test_old_trace_fails(self):
        self._assert_rule_fails_naming(
            lambda rule: rule.update(trace=[{"type": "fr", "id": "fr-password-reset"}]), "trace"
        )

    def test_scope_later_without_scope_reason_fails(self):
        self._assert_rule_fails_naming(lambda rule: rule.update(scope="later"), "scope_reason")

    def test_scope_later_with_scope_reason_validates(self):
        self.assertEqual(
            self._rule_errors(lambda rule: rule.update(scope="later", scope_reason="Deferred until the mobile client ships")),
            [],
        )

    def test_invalid_owner_fixture_fails_naming_owner(self):
        rendered = self._schema_errors("invalid_owner.json", lambda spec: None)
        self.assertTrue(any("owner" in msg for msg in rendered), rendered)

    def test_rule_without_severity_fails(self):
        rendered = self._schema_errors("valid_full.json", lambda spec: spec["rules"][0].pop("severity"))
        self.assertTrue(any("severity" in msg for msg in rendered), rendered)
