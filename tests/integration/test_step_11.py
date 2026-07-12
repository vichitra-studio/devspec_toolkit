"""
Integration tests for Step 11 (Red-Team / Failure Modes) validation.

Validates that step 11 fixtures conform to schema and that reference
validation logic works correctly using self-contained mock data.
"""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "step_11"


# ---------------------------------------------------------------------------
# Mock ID index (replaces live spec/ reads)
# ---------------------------------------------------------------------------

MOCK_ID_INDEX = {
    "api": {"api-ask", "api-search", "api-trace-retrieval"},
    "component": {"comp-retrieval-engine", "comp-auth-service"},
    "fr": {"fr-read-document", "fr-search-docs"},
    "nfr": {"nfr-availability-api", "nfr-latency-p99"},
    "inv": {"invariant-payload-validation", "inv-input-validation"},
    "fixture": {"fix-happy-path-search"},
    "doc": set(),
    "capability": {"cap-search"},
}


# ---------------------------------------------------------------------------
# Helper: reference validation (extracted from old script)
# ---------------------------------------------------------------------------


def _validate_references(fixture_data, id_index):
    """Return list of error strings for invalid references."""
    errors = []
    for threat in fixture_data.get("threats", []):
        threat_id = threat.get("threat_id", "<unknown>")

        # Target IDs
        for target in threat.get("target_ids", []):
            t_type = target.get("type")
            t_id = target.get("id")
            if t_type not in ("api", "component"):
                errors.append(
                    f"Threat {threat_id}: invalid target type '{t_type}'"
                )
                continue
            known = id_index.get(t_type, set())
            if known and t_id not in known:
                errors.append(
                    f"Threat {threat_id}: target '{t_id}' ({t_type}) not found"
                )

        # Mitigation IDs
        for mit in threat.get("mitigations", []):
            m_type = mit.get("type")
            m_id = mit.get("id")
            if m_type in ("inv", "nfr", "fr", "api", "capability", "fixture"):
                known = id_index.get(m_type, set())
                if known and m_id not in known:
                    errors.append(
                        f"Threat {threat_id}: mitigation '{m_id}' ({m_type}) not found"
                    )

    return errors


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


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

    def test_valid_full_references_resolve(self):
        """All target and mitigation IDs in valid_full.json resolve against mock index."""
        data = json.loads((FIXTURES_DIR / "valid_full.json").read_text())
        errors = _validate_references(data, MOCK_ID_INDEX)
        assert errors == [], f"Reference errors: {errors}"

    def test_invalid_missing_target_lacks_target_ids(self):
        """invalid_missing_target.json has a threat without target_ids."""
        data = json.loads(
            (FIXTURES_DIR / "invalid_missing_target.json").read_text()
        )
        threat = data["threats"][0]
        assert "target_ids" not in threat, (
            "Expected missing target_ids in invalid fixture"
        )

    def test_invalid_category_has_bad_category(self):
        """invalid_category.json uses a non-enum category value."""
        data = json.loads(
            (FIXTURES_DIR / "invalid_category.json").read_text()
        )
        threat = data["threats"][0]
        assert threat["category"] == "invalid-category"

    def test_unresolvable_mitigation_detected(self):
        """Reference validator catches a mitigation ID that does not exist."""
        fake_fixture = {
            "threats": [
                {
                    "threat_id": "threat-test",
                    "target_ids": [{"type": "api", "id": "api-ask"}],
                    "mitigations": [
                        {"type": "fr", "id": "fr-does-not-exist"}
                    ],
                }
            ]
        }
        errors = _validate_references(fake_fixture, MOCK_ID_INDEX)
        assert len(errors) == 1
        assert "fr-does-not-exist" in errors[0]

    def test_invalid_target_type_detected(self):
        """Reference validator rejects a target type outside api/component."""
        fake_fixture = {
            "threats": [
                {
                    "threat_id": "threat-test",
                    "target_ids": [{"type": "widget", "id": "w-1"}],
                    "mitigations": [],
                }
            ]
        }
        errors = _validate_references(fake_fixture, MOCK_ID_INDEX)
        assert len(errors) == 1
        assert "invalid target type" in errors[0]


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
