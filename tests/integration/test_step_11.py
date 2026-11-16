"""
Integration tests for Step 11 (Red-Team / Failure Modes) validation.

Validates that step 11 fixtures conform to the schema in the graph shape: a threat names what it
``threatens`` and what it is ``mitigated_by``; an edge case does the same, and both links are required there.
"""

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.validation.validate import validate_file as specdev_validate_file

_REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = _REPO_ROOT / "tests" / "fixtures" / "step_11"

# The worked examples of the spec-graph design (threat and edge case "New" forms).
_DOC_EXAMPLE_THREAT: dict[str, Any] = {
    "threat_id": "threat-reset-token-replay",
    "category": "authn",
    "severity": "high",
    "description": "An attacker who obtains a used or expired reset link replays it to set the account password.",
    "derives_from": ["risk-reset-link-takeover"],
    "threatens": ["api-password-reset-confirm"],
    "mitigated_by": ["inv-reset-token-single-use", "fix-password-reset-expired-token"],
    "risk_category_ref": {"id": "cn:project:risk_category:authn", "kind": "risk_category"},
}
_DOC_EXAMPLE_EDGE_CASE: dict[str, Any] = {
    "id": "ec-token-at-expiry-second",
    "scope": "in",
    "description": "A token redeemed in the second it expires.",
    "trigger": "Clock reaches issued_at + 30 min.",
    "threatens": ["api-password-reset-confirm"],
    "mitigated_by": ["ac-password-reset-3", "fix-password-reset-expired-token"],
}


def _schema_errors(spec: dict[str, Any]) -> list[str]:
    """Rendered E520 errors for a step 11 document."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "11_redteam.json"
        path.write_text(json.dumps(spec))
        errors = specdev_validate_file(str(_REPO_ROOT), str(path))
    return [e.render() for e in errors if e.code == "E520"]


def _doc_example_errors(mutate: Callable[[dict, dict], None]) -> list[str]:
    """Schema errors for the design-doc threat and edge case after ``mutate(threat, edge_case)`` edits copies."""
    spec = json.loads((FIXTURES_DIR / "valid_full.json").read_text())
    threat = json.loads(json.dumps(_DOC_EXAMPLE_THREAT))
    edge_case = json.loads(json.dumps(_DOC_EXAMPLE_EDGE_CASE))
    mutate(threat, edge_case)
    spec["threats"] = [threat]
    spec["edge_cases"] = [edge_case]
    return _schema_errors(spec)


def _assert_fails_naming(mutate: Callable[[dict, dict], None], needle: str) -> None:
    rendered = _doc_example_errors(mutate)
    assert any(needle in msg for msg in rendered), rendered


class TestStep11Fixtures:
    """Validate step 11 test fixtures."""

    def test_valid_full_loads(self):
        """valid_full.json is well-formed JSON."""
        path = FIXTURES_DIR / "valid_full.json"
        data = json.loads(path.read_text())
        assert data["id"] == "redteam-catalog"
        assert len(data["threats"]) >= 1

    def test_valid_full_has_required_fields(self):
        """valid_full.json contains all required top-level fields."""
        data = json.loads((FIXTURES_DIR / "valid_full.json").read_text())
        for field in ("$schema", "id", "owner", "threats", "edge_cases"):
            assert field in data, f"Missing required field: {field}"

    def test_valid_full_has_no_schema_errors(self):
        assert _schema_errors(json.loads((FIXTURES_DIR / "valid_full.json").read_text())) == []

    def test_invalid_missing_target_lacks_threatens(self):
        """invalid_missing_target.json has a threat without threatens, and the schema says so."""
        data = json.loads((FIXTURES_DIR / "invalid_missing_target.json").read_text())
        assert "threatens" not in data["threats"][0]
        assert any("threatens" in msg for msg in _schema_errors(data))

    def test_invalid_category_has_bad_category(self):
        """invalid_category.json uses a non-enum category value."""
        data = json.loads(
            (FIXTURES_DIR / "invalid_category.json").read_text()
        )
        threat = data["threats"][0]
        assert threat["category"] == "invalid-category"

    def test_doc_example_validates(self):
        assert _doc_example_errors(lambda threat, edge_case: None) == []

    def test_edge_case_with_empty_mitigated_by_fails(self):
        _assert_fails_naming(lambda threat, edge_case: edge_case.update(mitigated_by=[]), "mitigated_by")

    def test_edge_case_without_mitigated_by_or_threatens_fails(self):
        _assert_fails_naming(lambda threat, edge_case: edge_case.pop("mitigated_by"), "mitigated_by")
        _assert_fails_naming(lambda threat, edge_case: edge_case.pop("threatens"), "threatens")

    def test_threat_without_mitigated_by_validates(self):
        assert _doc_example_errors(lambda threat, edge_case: threat.pop("mitigated_by")) == []

    def test_threat_without_threatens_fails(self):
        _assert_fails_naming(lambda threat, edge_case: threat.pop("threatens"), "threatens")

    def test_old_target_ids_and_mitigations_fail(self):
        _assert_fails_naming(
            lambda threat, edge_case: threat.update(target_ids=[{"type": "api", "id": "api-ask"}]), "target_ids"
        )
        _assert_fails_naming(
            lambda threat, edge_case: threat.update(mitigations=[{"type": "inv", "id": "inv-x"}]), "mitigations"
        )

    def test_old_artifact_level_trace_fails(self):
        spec = json.loads((FIXTURES_DIR / "valid_full.json").read_text())
        spec["trace"] = [{"type": "doc", "id": "spec-11-redteam"}]
        assert any("trace" in msg for msg in _schema_errors(spec))

    def test_scope_later_without_scope_reason_fails(self):
        _assert_fails_naming(lambda threat, edge_case: threat.update(scope="later"), "scope_reason")
        _assert_fails_naming(lambda threat, edge_case: edge_case.update(scope="out"), "scope_reason")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
