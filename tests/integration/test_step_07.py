#!/usr/bin/env python3
"""Thin CLI wrapper for Step 07 validation.

Invokes the real ``specdev validate`` command against the given fixture.
Exit code mirrors the validator's exit code (0 = pass, 1 = fail).
"""

import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: test_step_07.py <fixture>")
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
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "step_07"

# The worked example of the spec-graph design (NFR "New" form): `trace` becomes three typed links.
_DOC_EXAMPLE_NFR: dict[str, Any] = {
    "nfr_id": "nfr-latency-reset-email",
    "category": "latency",
    "metric": "reset email delivery time p95",
    "target": "<= 60 s",
    "unit": "s",
    "stage": "staging",
    "owner": "ops",
    "measurement_method": "Synthetic reset request every 15 minutes in staging; time to receipt in a test inbox.",
    "constrains": ["fr-password-reset"],
    "derives_from": ["metric-recovery-time"],
    "relies_on": ["tp-mailrelay"],
    "metric_ref": {"id": "cn:project:metric:email-delivery-time", "kind": "metric"},
    "unit_ref": {"id": "cn:core:unit:s", "kind": "unit"},
    "environment_ref": {"id": "cn:core:environment:staging", "kind": "environment"},
}


class Step07IntegrationTests(unittest.TestCase):
    def _nfr_errors(self, mutate: Callable[[dict], None]) -> list[str]:
        """Rendered E520 errors for the design-doc NFR after ``mutate`` edits a copy of it."""
        spec = json.loads((_FIXTURES / "valid_minimal.json").read_text())
        nfr = json.loads(json.dumps(_DOC_EXAMPLE_NFR))
        mutate(nfr)
        spec["nfrs"] = [nfr]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "07_nfrs.json"
            path.write_text(json.dumps(spec))
            errors = specdev_validate_file(str(_REPO_ROOT), str(path))
        return [e.render() for e in errors if e.code == "E520"]

    def _assert_nfr_fails_naming(self, mutate: Callable[[dict], None], needle: str) -> None:
        rendered = self._nfr_errors(mutate)
        self.assertTrue(any(needle in msg for msg in rendered), rendered)

    def test_doc_example_validates(self):
        self.assertEqual(self._nfr_errors(lambda nfr: None), [])

    def test_nfr_without_constrains_validates(self):
        self.assertEqual(self._nfr_errors(lambda nfr: nfr.pop("constrains")), [])

    def test_nfr_with_old_trace_fails(self):
        self._assert_nfr_fails_naming(
            lambda nfr: nfr.update(trace=[{"type": "fr", "id": "fr-password-reset"}]), "trace"
        )

    def test_nfr_with_only_constrains_validates(self):
        def only_constrains(nfr: dict) -> None:
            nfr.pop("derives_from")
            nfr.pop("relies_on")

        self.assertEqual(self._nfr_errors(only_constrains), [])

    def test_scope_later_without_scope_reason_fails(self):
        self._assert_nfr_fails_naming(lambda nfr: nfr.update(scope="later"), "scope_reason")

    def test_nfr_id_without_a_condition_segment_fails_the_schema(self):
        errors = specdev_validate_file(str(_REPO_ROOT), str(_FIXTURES / "invalid_nfr_id_one_segment.json"))
        rendered = [e.render() for e in errors if e.code == "E520"]
        self.assertTrue(any("nfr_id" in msg for msg in rendered), rendered)
