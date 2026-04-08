"""Tests for step_11 deep validation: threat_id uniqueness, target cross-ref, mitigations."""
import json
import os
import pytest
from specdev_tools.validation.validators.step_11 import validate_step_11


def _render(errors):
    """Render SpecError list to strings for assertion convenience."""
    return [e.render() for e in errors]


@pytest.fixture
def toolkit_root(tmp_path):
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    return str(tmp_path)


class TestValidMinimal:
    def test_empty_threats(self, toolkit_root):
        errors = validate_step_11({"threats": []}, toolkit_root)
        assert errors == []

    def test_valid_threat(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-login"}],
                "mitigations": [{"type": "fr", "description": "Rate limiting"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        # May have cross-ref errors if step files don't exist, but no structural errors
        structural = [e for e in rendered if "Duplicate" in e or "invalid target type" in e or "invalid mitigation type" in e]
        assert structural == []


class TestDuplicateThreatId:
    def test_duplicate(self, toolkit_root):
        instance = {
            "threats": [
                {"threat_id": "threat-01", "target_ids": [{"type": "api", "id": "a"}], "mitigations": [{"type": "fr", "description": "x"}]},
                {"threat_id": "threat-01", "target_ids": [{"type": "api", "id": "b"}], "mitigations": [{"type": "fr", "description": "y"}]},
            ]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("Duplicate" in e and "threat-01" in e for e in rendered)


class TestInvalidTargetType:
    def test_bad_target_type(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "database", "id": "db-main"}],
                "mitigations": [{"type": "fr", "description": "x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("invalid target type" in e for e in rendered)


class TestNoTargets:
    def test_missing_target_ids(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [],
                "mitigations": [{"type": "fr", "description": "x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("no target_ids" in e for e in rendered)


class TestInvalidMitigationType:
    def test_bad_mitigation_type(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "unknown-type", "description": "x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("invalid mitigation type" in e for e in rendered)


class TestNoMitigations:
    def test_empty_mitigations(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("no mitigations" in e for e in rendered)


class TestMitigationMissingFields:
    def test_missing_id(self, toolkit_root):
        """Mitigation with no `id` should be flagged (schema also enforces this;
        linter keeps it as a safety net for fixture-based tests)."""
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "fr"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("missing required 'id'" in e for e in rendered)

    def test_current_shape_passes(self, toolkit_root):
        """The current {type, id, note} mitigation shape must not trip E520."""
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{
                    "type": "inv",
                    "id": "inv-auth-required",
                    "note": "Enforced by auth middleware",
                }],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert not any("without description or ref" in e for e in rendered)
        assert not any("missing required 'id'" in e for e in rendered)


class TestComponentCrossRef:
    def test_unknown_component(self, toolkit_root):
        """When step 02 exists, unknown component IDs should be flagged."""
        spec_dir = os.path.join(toolkit_root, "spec")
        sketch = {"components": [{"component_id": "comp-auth"}]}
        with open(os.path.join(spec_dir, "02_system_sketch.json"), "w") as f:
            json.dump(sketch, f)

        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "component", "id": "comp-nonexistent"}],
                "mitigations": [{"type": "fr", "description": "x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("comp-nonexistent" in e and "unknown component" in e for e in rendered)

    def test_known_component(self, toolkit_root):
        spec_dir = os.path.join(toolkit_root, "spec")
        sketch = {"components": [{"component_id": "comp-auth"}]}
        with open(os.path.join(spec_dir, "02_system_sketch.json"), "w") as f:
            json.dump(sketch, f)

        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "component", "id": "comp-auth"}],
                "mitigations": [{"type": "fr", "description": "x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert not any("unknown component" in e for e in rendered)


class TestEmptyUpstreamFlagsStrayRefs:
    """Regression: when an upstream step file exists but contains an empty
    ``apis``/``components`` list, any threat targeting an ID from that step
    must still fire E590. Previously the loaders converted empty-set → None,
    which silently skipped cross-ref validation against an empty upstream."""

    def test_empty_apis_flags_unknown_api_target(self, tmp_path):
        host_spec = tmp_path / "host" / "spec"
        host_spec.mkdir(parents=True)
        (host_spec / "05_interface_contracts.json").write_text(json.dumps({"apis": []}))
        artifact_path = str(host_spec / "11_redteam.json")
        toolkit_root = tmp_path / "toolkit"
        (toolkit_root / "spec").mkdir(parents=True)

        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-ghost"}],
                "mitigations": [{"type": "fr", "id": "fr-x"}],
            }]
        }
        errors = validate_step_11(instance, str(toolkit_root), artifact_path)
        rendered = _render(errors)
        assert any("api-ghost" in e and "unknown API" in e for e in rendered), (
            f"empty upstream apis must still flag stray targets: {rendered}"
        )

    def test_empty_components_flags_unknown_component_target(self, tmp_path):
        host_spec = tmp_path / "host" / "spec"
        host_spec.mkdir(parents=True)
        (host_spec / "02_system_sketch.json").write_text(json.dumps({"components": []}))
        artifact_path = str(host_spec / "11_redteam.json")
        toolkit_root = tmp_path / "toolkit"
        (toolkit_root / "spec").mkdir(parents=True)

        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "component", "id": "comp-ghost"}],
                "mitigations": [{"type": "fr", "id": "fr-x"}],
            }]
        }
        errors = validate_step_11(instance, str(toolkit_root), artifact_path)
        rendered = _render(errors)
        assert any("comp-ghost" in e and "unknown component" in e for e in rendered), (
            f"empty upstream components must still flag stray targets: {rendered}"
        )


class TestNonObjectMitigation:
    def test_string_mitigation(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": ["just a string"],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("non-object mitigation" in e for e in rendered)


class TestApiCoverageCheck:
    """W583: every public API in Step 05 should be targeted by at least one threat."""

    def _write_step05(self, toolkit_root, apis):
        spec_dir = os.path.join(toolkit_root, "spec")
        data = {"apis": apis}
        with open(os.path.join(spec_dir, "05_interface_contracts.json"), "w") as f:
            json.dump(data, f)

    def test_no_step05_no_warning(self, toolkit_root):
        """When step 05 is absent, no W583 warnings should fire."""
        instance = {"threats": []}
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert not any("W583" in e for e in rendered)

    def test_uncovered_api_emits_w583(self, toolkit_root):
        """When step 05 exists and an API has no threat, W583 should fire."""
        self._write_step05(toolkit_root, [{"api_id": "api-login"}, {"api_id": "api-logout"}])
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-login"}],
                "mitigations": [{"type": "fr", "description": "Rate limiting"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("W583" in e and "api-logout" in e for e in rendered)
        assert not any("W583" in e and "api-login" in e for e in rendered)

    def test_all_apis_covered_no_w583(self, toolkit_root):
        """When all APIs have at least one threat, no W583 should fire."""
        self._write_step05(toolkit_root, [{"api_id": "api-login"}])
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-login"}],
                "mitigations": [{"type": "fr", "description": "Rate limiting"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert not any("W583" in e for e in rendered)

    def test_empty_apis_list_no_w583(self, toolkit_root):
        """When step 05 exists but has no APIs, no W583 should fire."""
        self._write_step05(toolkit_root, [])
        instance = {"threats": []}
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert not any("W583" in e for e in rendered)

    def test_multiple_threats_cover_same_api(self, toolkit_root):
        """Multiple threats targeting the same API should not cause W583."""
        self._write_step05(toolkit_root, [{"api_id": "api-login"}])
        instance = {
            "threats": [
                {
                    "threat_id": "threat-01",
                    "target_ids": [{"type": "api", "id": "api-login"}],
                    "mitigations": [{"type": "fr", "description": "Rate limiting"}],
                },
                {
                    "threat_id": "threat-02",
                    "target_ids": [{"type": "api", "id": "api-login"}],
                    "mitigations": [{"type": "fr", "description": "Auth check"}],
                },
            ]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert not any("W583" in e for e in rendered)


class TestHostSpecSiblingResolution:
    """Bug 1 regression: when the Step 11 artifact lives in a host spec dir
    (e.g. ``host_repo/spec/11_redteam.json``) the linter must resolve sibling
    upstream files from that same directory, not from ``<toolkit_root>/spec``.
    """

    def test_sibling_dir_wins_over_toolkit_spec(self, tmp_path):
        # Toolkit-side spec: has fictional APIs that should NOT be consulted
        toolkit_root = tmp_path / "toolkit"
        toolkit_spec = toolkit_root / "spec"
        toolkit_spec.mkdir(parents=True)
        (toolkit_spec / "05_interface_contracts.json").write_text(json.dumps({
            "apis": [{"api_id": "api-toolkit-only"}]
        }))

        # Host-side spec: the real APIs the artifact is cross-referenced against
        host_spec = tmp_path / "host" / "spec"
        host_spec.mkdir(parents=True)
        (host_spec / "05_interface_contracts.json").write_text(json.dumps({
            "apis": [{"api_id": "api-host-login"}]
        }))
        artifact_path = str(host_spec / "11_redteam.json")

        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-host-login"}],
                "mitigations": [{"type": "fr", "id": "fr-login"}],
            }]
        }

        errors = validate_step_11(instance, str(toolkit_root), artifact_path)
        rendered = _render(errors)
        # Must not flag api-host-login as unknown: sibling dir resolves it.
        assert not any("api-host-login" in e and "unknown API" in e for e in rendered)
        # Must not flag api-toolkit-only as uncovered: the toolkit spec must
        # not shadow the host spec when sibling resolution succeeds.
        assert not any("api-toolkit-only" in e for e in rendered)

    def test_component_sibling_dir_wins_over_toolkit_spec(self, tmp_path):
        """Symmetric to the API test: component cross-ref must also resolve
        from the artifact's sibling dir before falling back to toolkit/spec."""
        toolkit_root = tmp_path / "toolkit"
        toolkit_spec = toolkit_root / "spec"
        toolkit_spec.mkdir(parents=True)
        (toolkit_spec / "02_system_sketch.json").write_text(json.dumps({
            "components": [{"component_id": "comp-toolkit-only"}]
        }))

        host_spec = tmp_path / "host" / "spec"
        host_spec.mkdir(parents=True)
        (host_spec / "02_system_sketch.json").write_text(json.dumps({
            "components": [{"component_id": "comp-host-auth"}]
        }))
        artifact_path = str(host_spec / "11_redteam.json")

        # Target BOTH the host component (must resolve) AND the toolkit-only
        # component (must be flagged unknown — proves the toolkit spec was
        # NOT consulted as a fallback once the sibling dir resolved).
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [
                    {"type": "component", "id": "comp-host-auth"},
                    {"type": "component", "id": "comp-toolkit-only"},
                ],
                "mitigations": [{"type": "fr", "id": "fr-auth"}],
            }]
        }

        errors = validate_step_11(instance, str(toolkit_root), artifact_path)
        rendered = _render(errors)
        # Host-side component must resolve (not flagged unknown).
        assert not any("comp-host-auth" in e and "unknown component" in e for e in rendered)
        # Toolkit-side component MUST be flagged unknown: the sibling dir
        # resolved successfully, so the toolkit spec must not shadow it.
        assert any("comp-toolkit-only" in e and "unknown component" in e for e in rendered)
