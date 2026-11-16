#!/usr/bin/env python3
"""Thin CLI wrapper for Step 10 validation.

Invokes the real ``specdev validate`` command against the given fixture.
Exit code mirrors the validator's exit code (0 = pass, 1 = fail).
"""

import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: test_step_10.py <fixture>")
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
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "step_10"

# The worked example of the spec-graph design (governance "New" form), with the one-word rename of the
# command field (`command_ref` becomes `cli_command`, ruled 2026-11-15, CD-16).
_DOC_EXAMPLE_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "rule-contract-tests-on-every-pr",
        "scope": "in",
        "text": "Every pull request runs the contract test suite before merge.",
        "derives_from": ["contract-tests"],
    },
    {
        "rule_id": "rule-spec-check-on-every-pr",
        "scope": "in",
        "text": "Every pull request passes the spec merge check.",
        "derives_from": ["risk-reset-link-takeover"],
        "cli_command": "spec-check",
    },
    {
        "rule_id": "rule-security-review-of-token-handling",
        "scope": "in",
        "enforcer": "review",
        "text": "A person reviews every change to reset-token handling before release.",
        "derives_from": ["risk-reset-link-takeover"],
    },
]


class Step10IntegrationTests(unittest.TestCase):
    def _errors(self, mutate: Callable[[dict], None]) -> list[str]:
        """Rendered E520 errors for the valid fixture with the design-doc rules, after ``mutate`` edits the copy."""
        spec = json.loads((_FIXTURES / "valid_full.json").read_text())
        spec["rules"] = json.loads(json.dumps(_DOC_EXAMPLE_RULES))
        mutate(spec)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "10_governance.json"
            path.write_text(json.dumps(spec))
            errors = specdev_validate_file(str(_REPO_ROOT), str(path))
        return [e.render() for e in errors if e.code == "E520"]

    def _assert_fails_naming(self, mutate: Callable[[dict], None], needle: str) -> None:
        rendered = self._errors(mutate)
        self.assertTrue(any(needle in msg for msg in rendered), rendered)

    def test_doc_example_validates_with_cli_command(self):
        self.assertEqual(self._errors(lambda spec: None), [])

    def test_rule_with_enforcer_and_cli_command_fails(self):
        self._assert_fails_naming(
            lambda spec: spec["rules"][1].update(enforcer="review"), "should not be valid under"
        )

    def test_enforcer_job_fails(self):
        self._assert_fails_naming(lambda spec: spec["rules"][2].update(enforcer="job"), "enforcer")

    def test_enforcer_command_fails(self):
        self._assert_fails_naming(lambda spec: spec["rules"][2].update(enforcer="command"), "enforcer")

    def test_rule_without_derives_from_fails(self):
        self._assert_fails_naming(lambda spec: spec["rules"][0].pop("derives_from"), "derives_from")

    def test_old_pr_rules_and_spec_first_policy_fail(self):
        self._assert_fails_naming(lambda spec: spec.update(pr_rules=["validate"]), "pr_rules")
        self._assert_fails_naming(lambda spec: spec.update(spec_first_policy=True), "spec_first_policy")

    def test_rule_text_shorter_than_ten_characters_fails(self):
        self._assert_fails_naming(lambda spec: spec["rules"][0].update(text="Too short"), "is too short")

    def test_artifact_without_rules_fails(self):
        self._assert_fails_naming(lambda spec: spec.pop("rules"), "rules")

    def test_scope_later_without_scope_reason_fails(self):
        self._assert_fails_naming(lambda spec: spec["rules"][0].update(scope="later"), "scope_reason")
