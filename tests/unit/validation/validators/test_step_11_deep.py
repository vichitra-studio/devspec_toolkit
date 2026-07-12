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


class TestNonObjectThreat:
    """Defensive guard: non-dict entries in threats[] must emit E520, not AttributeError."""

    def test_string_threat_emits_e520_not_attributeerror(self, toolkit_root):
        """A string entry in threats[] must produce a structured E520, not raise AttributeError."""
        instance = {
            "threats": ["not-a-dict"],
        }
        # Must not raise — previously would blow up with AttributeError on .get()
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("E520" in e and "threats[0]" in e and "not an object" in e for e in rendered), (
            f"expected E520 for non-dict threat entry, got: {rendered}"
        )

    def test_int_threat_emits_e520(self, toolkit_root):
        """An int entry in threats[] must produce a structured E520."""
        instance = {
            "threats": [42],
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("E520" in e and "threats[0]" in e and "not an object" in e for e in rendered), (
            f"expected E520 for non-dict threat entry, got: {rendered}"
        )

    def test_mixed_threats_only_bad_entry_flagged(self, toolkit_root):
        """A valid threat followed by a non-dict entry: only the non-dict emits E520 for this guard."""
        instance = {
            "threats": [
                {
                    "threat_id": "threat-01",
                    "target_ids": [{"type": "api", "id": "api-x"}],
                    "mitigations": [{"type": "fr", "id": "fr-x"}],
                },
                "bad-entry",
            ]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("E520" in e and "threats[1]" in e and "not an object" in e for e in rendered), (
            f"expected E520 for threats[1]: {rendered}"
        )
        assert not any("threats[0]" in e and "not an object" in e for e in rendered), (
            f"threats[0] is valid and must not be flagged as non-object: {rendered}"
        )


class TestNonObjectTarget:
    """Defensive guard: non-dict entries in target_ids[] must emit E520, not AttributeError."""

    def test_string_target_emits_e520_not_attributeerror(self, toolkit_root):
        """A string entry in target_ids[] must produce a structured E520, not raise AttributeError."""
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": ["not-a-dict"],
                "mitigations": [{"type": "fr", "id": "fr-x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("E520" in e and "target_ids[0]" in e and "not an object" in e for e in rendered), (
            f"expected E520 for non-dict target_ids entry, got: {rendered}"
        )

    def test_int_target_emits_e520(self, toolkit_root):
        """An int entry in target_ids[] must produce a structured E520."""
        instance = {
            "threats": [{
                "threat_id": "threat-42",
                "target_ids": [99],
                "mitigations": [{"type": "fr", "id": "fr-x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("E520" in e and "target_ids[0]" in e and "not an object" in e for e in rendered), (
            f"expected E520 for non-dict target_ids entry, got: {rendered}"
        )

    def test_mixed_targets_only_bad_entry_flagged(self, toolkit_root):
        """A valid target followed by a non-dict entry: only the non-dict emits the guard E520."""
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [
                    {"type": "api", "id": "api-x"},
                    "bad-target",
                ],
                "mitigations": [{"type": "fr", "id": "fr-x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        rendered = _render(errors)
        assert any("E520" in e and "target_ids[1]" in e and "not an object" in e for e in rendered), (
            f"expected E520 for target_ids[1]: {rendered}"
        )
        assert not any("target_ids[0]" in e and "not an object" in e for e in rendered), (
            f"target_ids[0] is valid and must not be flagged as non-object: {rendered}"
        )


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


class TestApiCoverageWontHaveFrExclusion:
    """W583 must not demand threat coverage for an API whose only tracing FR
    is priority:"wont-have" -- it will never be built (DEVSPEC-122 follow-up)."""

    def _write_step04(self, toolkit_root, frs):
        spec_dir = os.path.join(toolkit_root, "spec")
        with open(os.path.join(spec_dir, "04_fr_list.json"), "w") as f:
            json.dump({"functional_requirements": frs}, f)

    def _write_step05(self, toolkit_root, apis):
        spec_dir = os.path.join(toolkit_root, "spec")
        with open(os.path.join(spec_dir, "05_interface_contracts.json"), "w") as f:
            json.dump({"apis": apis}, f)

    def test_api_tracing_only_to_wont_have_fr_does_not_fire_w583(self, toolkit_root):
        self._write_step04(toolkit_root, [{"fr_id": "fr-legacy-export", "priority": "wont-have"}])
        self._write_step05(toolkit_root, [
            {"api_id": "api-legacy-export", "trace": [{"type": "fr", "id": "fr-legacy-export"}]}
        ])
        errors = validate_step_11({"threats": []}, toolkit_root)
        rendered = _render(errors)
        assert not any("W583" in e and "api-legacy-export" in e for e in rendered), rendered

    def test_control_api_tracing_to_must_have_fr_still_fires_w583(self, toolkit_root):
        """Control: an API tracing only to a must-have FR must still fire W583."""
        self._write_step04(toolkit_root, [{"fr_id": "fr-login", "priority": "must-have"}])
        self._write_step05(toolkit_root, [
            {"api_id": "api-login", "trace": [{"type": "fr", "id": "fr-login"}]}
        ])
        errors = validate_step_11({"threats": []}, toolkit_root)
        rendered = _render(errors)
        assert any("W583" in e and "api-login" in e for e in rendered), rendered

    def test_api_tracing_to_mixed_fr_priorities_still_fires_w583(self, toolkit_root):
        """Control: an API tracing to BOTH a wont-have and a must-have FR must
        still fire W583 -- not every tracing FR is wont-have."""
        self._write_step04(toolkit_root, [
            {"fr_id": "fr-legacy-export", "priority": "wont-have"},
            {"fr_id": "fr-login", "priority": "must-have"},
        ])
        self._write_step05(toolkit_root, [
            {
                "api_id": "api-mixed",
                "trace": [
                    {"type": "fr", "id": "fr-legacy-export"},
                    {"type": "fr", "id": "fr-login"},
                ],
            }
        ])
        errors = validate_step_11({"threats": []}, toolkit_root)
        rendered = _render(errors)
        assert any("W583" in e and "api-mixed" in e for e in rendered), rendered


class TestMitigationCrossRef:
    """DEVSPEC-89: mitigation IDs are cross-referenced against upstream specs."""

    # ------------------------------------------------------------------
    # inv (step 06) cross-ref
    # ------------------------------------------------------------------

    def test_unknown_inv_id_emits_e590(self, tmp_path):
        """When step 06 exists, a mitigation with an unknown inv id fires E590."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "06_invariants.json").write_text(json.dumps({
            "rules": [{"inv_id": "inv-known"}]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "inv", "id": "inv-unknown"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("E590" in e and "inv-unknown" in e for e in rendered), rendered

    def test_valid_inv_id_no_e590(self, tmp_path):
        """A mitigation referencing an inv_id that exists in step 06 should not fire E590."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "06_invariants.json").write_text(json.dumps({
            "rules": [{"inv_id": "inv-known"}]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "inv", "id": "inv-known"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("inv-known" in e and "E590" in e for e in rendered), rendered

    def test_absent_step06_no_e590(self, tmp_path):
        """When step 06 is absent, inv mitigations are not cross-referenced (guard)."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "inv", "id": "inv-anything"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("inv-anything" in e and "E590" in e for e in rendered), rendered

    # ------------------------------------------------------------------
    # fr (step 04) cross-ref
    # ------------------------------------------------------------------

    def test_unknown_fr_id_emits_e590(self, tmp_path):
        """When step 04 exists, a mitigation with an unknown fr id fires E590."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "04_fr_list.json").write_text(json.dumps({
            "functional_requirements": [{"fr_id": "fr-known"}]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "fr", "id": "fr-ghost"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("E590" in e and "fr-ghost" in e for e in rendered), rendered

    def test_valid_fr_id_no_e590(self, tmp_path):
        """A mitigation referencing an fr_id that exists in step 04 should not fire E590."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "04_fr_list.json").write_text(json.dumps({
            "functional_requirements": [{"fr_id": "fr-known"}]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "fr", "id": "fr-known"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("fr-known" in e and "E590" in e for e in rendered), rendered

    # ------------------------------------------------------------------
    # capability (step 01) cross-ref
    # ------------------------------------------------------------------

    def test_unknown_capability_id_emits_e590(self, tmp_path):
        """When step 01 exists, a mitigation with an unknown capability id fires E590."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "01_capabilities.json").write_text(json.dumps({
            "capabilities": [{"capability_id": "cap-auth"}]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "capability", "id": "cap-phantom"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("E590" in e and "cap-phantom" in e for e in rendered), rendered

    def test_absent_step01_no_e590(self, tmp_path):
        """When step 01 is absent, capability mitigations are not cross-referenced."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "capability", "id": "cap-anything"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("cap-anything" in e and "E590" in e for e in rendered), rendered

    # ------------------------------------------------------------------
    # capability (step 01) — valid id (negative control)
    # ------------------------------------------------------------------

    def test_valid_capability_id_no_e590(self, tmp_path):
        """A mitigation referencing a cap-* ID that exists in step 01 must NOT fire E590."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "01_capabilities.json").write_text(json.dumps({
            "capabilities": [{"capability_id": "cap-x"}]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "capability", "id": "cap-x"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("cap-x" in e and "E590" in e for e in rendered), rendered

    # ------------------------------------------------------------------
    # nfr (step 07) cross-ref
    # ------------------------------------------------------------------

    def test_valid_nfr_id_no_e590(self, tmp_path):
        """A mitigation referencing an nfr_id that exists in step 07 must NOT fire E590."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "07_nfrs.json").write_text(json.dumps({
            "nfrs": [{"nfr_id": "nfr-x"}]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "nfr", "id": "nfr-x"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("nfr-x" in e and "E590" in e for e in rendered), rendered

    def test_unknown_nfr_id_emits_e590(self, tmp_path):
        """When step 07 exists, a mitigation with an unknown nfr id fires E590."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "07_nfrs.json").write_text(json.dumps({
            "nfrs": [{"nfr_id": "nfr-x"}]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "nfr", "id": "nfr-ghost"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("E590" in e and "nfr-ghost" in e for e in rendered), rendered

    # ------------------------------------------------------------------
    # fixture (step 08) cross-ref
    # ------------------------------------------------------------------

    def test_valid_fixture_id_no_e590(self, tmp_path):
        """A mitigation referencing a fixture_id that exists in step 08 must NOT fire E590."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "08_fixtures.json").write_text(json.dumps({
            "fixtures": [{"fixture_id": "fix-x"}]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "fixture", "id": "fix-x"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("fix-x" in e and "E590" in e for e in rendered), rendered

    def test_unknown_fixture_id_emits_e590(self, tmp_path):
        """When step 08 exists, a mitigation with an unknown fixture id fires E590."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "08_fixtures.json").write_text(json.dumps({
            "fixtures": [{"fixture_id": "fix-x"}]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "fixture", "id": "fix-ghost"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("E590" in e and "fix-ghost" in e for e in rendered), rendered

    # ------------------------------------------------------------------
    # api mitigation (step 05) cross-ref
    # ------------------------------------------------------------------

    def test_valid_api_mitigation_no_e590(self, tmp_path):
        """A mitigation referencing an api_id that exists in step 05 must NOT fire E590."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "05_interface_contracts.json").write_text(json.dumps({
            "apis": [{"api_id": "api-x"}]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "api", "id": "api-x"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("api-x" in e and "E590" in e for e in rendered), rendered

    def test_unknown_api_mitigation_emits_e590(self, tmp_path):
        """When step 05 exists, a mitigation with an unknown api id fires E590."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "05_interface_contracts.json").write_text(json.dumps({
            "apis": [{"api_id": "api-x"}]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "api", "id": "api-ghost"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("E590" in e and "api-ghost" in e for e in rendered), rendered

    # ------------------------------------------------------------------
    # empty upstream — present-but-empty file must still fire E590
    # ------------------------------------------------------------------

    def test_empty_upstream_mitigation_still_fires_e590(self, tmp_path):
        """An upstream step file that exists but has an empty rules array must still
        fire E590 for an unresolved inv mitigation (empty-set != None)."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "06_invariants.json").write_text(json.dumps({"rules": []}))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "inv", "id": "inv-ghost"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("E590" in e and "inv-ghost" in e for e in rendered), (
            f"empty upstream rules must still flag inv-ghost: {rendered}"
        )

    def test_empty_upstream_fr_mitigation_still_fires_e590(self, tmp_path):
        """An upstream step 04 file that exists but has an empty functional_requirements
        array must still fire E590 for an unresolved fr mitigation (empty-set != None)."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "04_fr_list.json").write_text(json.dumps({"functional_requirements": []}))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "fr", "id": "fr-ghost"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("E590" in e and "fr-ghost" in e for e in rendered), (
            f"empty upstream functional_requirements must still flag fr-ghost: {rendered}"
        )

    def test_empty_upstream_nfr_mitigation_still_fires_e590(self, tmp_path):
        """An upstream step 07 file that exists but has an empty nfrs array must still
        fire E590 for an unresolved nfr mitigation (empty-set != None)."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "07_nfrs.json").write_text(json.dumps({"nfrs": []}))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "nfr", "id": "nfr-ghost"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("E590" in e and "nfr-ghost" in e for e in rendered), (
            f"empty upstream nfrs must still flag nfr-ghost: {rendered}"
        )

    def test_empty_upstream_fixture_mitigation_still_fires_e590(self, tmp_path):
        """An upstream step 08 file that exists but has an empty fixtures array must still
        fire E590 for an unresolved fixture mitigation (empty-set != None)."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "08_fixtures.json").write_text(json.dumps({"fixtures": []}))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "fixture", "id": "fix-ghost"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("E590" in e and "fix-ghost" in e for e in rendered), (
            f"empty upstream fixtures must still flag fix-ghost: {rendered}"
        )

    def test_empty_upstream_capability_mitigation_still_fires_e590(self, tmp_path):
        """An upstream step 01 file that exists but has an empty capabilities array must still
        fire E590 for an unresolved capability mitigation (empty-set != None)."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "01_capabilities.json").write_text(json.dumps({"capabilities": []}))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "capability", "id": "cap-ghost"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("E590" in e and "cap-ghost" in e for e in rendered), (
            f"empty upstream capabilities must still flag cap-ghost: {rendered}"
        )

    # ------------------------------------------------------------------
    # inv alias — type 'inv' must not produce E530 (alias → 'invariant')
    # ------------------------------------------------------------------

    def test_inv_alias_no_e530(self, tmp_path):
        """Mitigation type 'inv' normalizes to 'invariant' and must NOT produce E530."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "inv", "id": "inv-x"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("E530" in e for e in rendered), (
            f"type 'inv' alias must not produce E530: {rendered}"
        )

    # ------------------------------------------------------------------
    # doc mitigation — always exempt from cross-ref
    # ------------------------------------------------------------------

    def test_doc_mitigation_never_e590(self, tmp_path):
        """doc mitigations with any id must never fire E590 regardless of upstreams present."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        # Create multiple upstream files — doc should still be exempt
        (spec_dir / "04_fr_list.json").write_text(json.dumps({"functional_requirements": [{"fr_id": "fr-x"}]}))
        (spec_dir / "06_invariants.json").write_text(json.dumps({"rules": [{"inv_id": "inv-x"}]}))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "doc", "id": "doc-arbitrary-runbook-id"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("doc-arbitrary-runbook-id" in e and "E590" in e for e in rendered), rendered


class TestInvariantCoverageW615:
    """DEVSPEC-89: W615 fires for security-relevant invariants with no referencing threat."""

    def test_invariant_with_risk_category_ref_and_no_threat_emits_w615(self, tmp_path):
        """An invariant WITH risk_category_ref and no referencing threat fires W615."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "06_invariants.json").write_text(json.dumps({
            "rules": [{
                "inv_id": "inv-auth-required",
                "risk_category_ref": {"id": "cn:core:risk_category:security", "kind": "risk_category", "label": "security"},
            }]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        # No mitigation references inv-auth-required
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "fr", "id": "fr-x"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("W615" in e and "inv-auth-required" in e for e in rendered), rendered

    def test_invariant_without_risk_category_ref_no_w615(self, tmp_path):
        """An invariant WITHOUT risk_category_ref and no referencing threat must NOT fire W615."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "06_invariants.json").write_text(json.dumps({
            "rules": [{
                "inv_id": "inv-no-risk-cat",
                # No risk_category_ref field
            }]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "fr", "id": "fr-x"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("W615" in e and "inv-no-risk-cat" in e for e in rendered), rendered

    def test_invariant_with_risk_category_ref_and_referencing_threat_no_w615(self, tmp_path):
        """An invariant WITH risk_category_ref that IS referenced by a threat mitigation must NOT fire W615."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "06_invariants.json").write_text(json.dumps({
            "rules": [{
                "inv_id": "inv-auth-required",
                "risk_category_ref": {"id": "cn:core:risk_category:security", "kind": "risk_category", "label": "security"},
            }]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "inv", "id": "inv-auth-required"}],
            }]
        }
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("W615" in e and "inv-auth-required" in e for e in rendered), rendered

    def test_absent_step06_no_w615(self, tmp_path):
        """When step 06 is absent, W615 must not fire (guard)."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {"threats": []}
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("W615" in e for e in rendered), rendered


class TestInvariantCoverageWontHaveFrExclusion:
    """W615 must not demand threat coverage for an invariant whose only
    tracing FR is priority:"wont-have" (DEVSPEC-122 follow-up)."""

    def test_invariant_tracing_only_to_wont_have_fr_does_not_fire_w615(self, tmp_path):
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "04_fr_list.json").write_text(json.dumps({
            "functional_requirements": [{"fr_id": "fr-legacy-export", "priority": "wont-have"}]
        }))
        (spec_dir / "06_invariants.json").write_text(json.dumps({
            "rules": [{
                "inv_id": "inv-legacy-export-integrity",
                "risk_category_ref": {"id": "cn:core:risk_category:security", "kind": "risk_category", "label": "security"},
                "trace": [{"type": "fr", "id": "fr-legacy-export"}],
            }]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {"threats": []}
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert not any("W615" in e and "inv-legacy-export-integrity" in e for e in rendered), rendered

    def test_control_invariant_tracing_to_must_have_fr_still_fires_w615(self, tmp_path):
        """Control: an invariant tracing only to a must-have FR must still fire W615."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "04_fr_list.json").write_text(json.dumps({
            "functional_requirements": [{"fr_id": "fr-login", "priority": "must-have"}]
        }))
        (spec_dir / "06_invariants.json").write_text(json.dumps({
            "rules": [{
                "inv_id": "inv-auth-required",
                "risk_category_ref": {"id": "cn:core:risk_category:security", "kind": "risk_category", "label": "security"},
                "trace": [{"type": "fr", "id": "fr-login"}],
            }]
        }))
        artifact_path = str(spec_dir / "11_redteam.json")
        instance = {"threats": []}
        errors = validate_step_11(instance, str(tmp_path), artifact_path)
        rendered = _render(errors)
        assert any("W615" in e and "inv-auth-required" in e for e in rendered), rendered


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
