"""Tests for step_11 deep validation: threat_id uniqueness, API coverage (W583), invariant coverage (W615)."""
import json
import os

import pytest

from specdev_tools.validation.validators.step_11 import (
    _fr_ids_from_constrains,
    _fr_ids_from_derives_from,
    validate_step_11,
)

from ...graph._synth import unique_id_errors

_SECURITY_REF = {"id": "cn:core:risk_category:security", "kind": "risk_category", "label": "security"}


def _render(errors):
    """Render SpecError list to strings for assertion convenience."""
    return [e.render() for e in errors]


def _threat(threat_id="threat-01", threatens=("api-x",), mitigated_by=("fr-x",), **extra):
    """A graph-shape threat object."""
    return {"threat_id": threat_id, "threatens": list(threatens), "mitigated_by": list(mitigated_by), **extra}


@pytest.fixture
def toolkit_root(tmp_path):
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    return str(tmp_path)


def _write_spec(toolkit_root, filename, data):
    with open(os.path.join(toolkit_root, "spec", filename), "w") as f:
        json.dump(data, f)


def _codes(toolkit_root, instance, code, artifact_path=None):
    """Rendered errors of *instance* that carry *code*."""
    return [e for e in _render(validate_step_11(instance, toolkit_root, artifact_path)) if code in e]


class TestValidMinimal:
    def test_empty_threats(self, toolkit_root):
        assert validate_step_11({"threats": []}, toolkit_root) == []

    def test_valid_threat(self, toolkit_root):
        assert validate_step_11({"threats": [_threat()]}, toolkit_root) == []


class TestDuplicateThreatId:
    def test_duplicate(self, toolkit_root):
        instance = {"threats": [_threat(threatens=("a",)), _threat(threatens=("b",))]}
        assert not any("threat-01" in e for e in _render(validate_step_11(instance, toolkit_root)))
        errors = unique_id_errors({"11_redteam.json": instance})
        assert [(e.code, e.owner, e.node_id) for e in errors] == [("E704", "step:11", "threat-01")]


class TestRemovedFieldsAreNotRead:
    def test_target_ids_and_mitigations_are_ignored(self, toolkit_root):
        instance = {"threats": [{
            "threat_id": "threat-01",
            "target_ids": [{"type": "weird", "id": "nowhere"}],
            "mitigations": [{"type": "weird"}, "not-an-object"],
        }]}
        assert validate_step_11(instance, toolkit_root) == []

    def test_no_existence_check_of_named_ids(self, toolkit_root):
        _write_spec(toolkit_root, "05_interface_contracts.json", {"apis": [{"api_id": "api-real"}]})
        instance = {"threats": [_threat(threatens=("api-real", "api-unknown"), mitigated_by=("inv-unknown",))]}
        assert validate_step_11(instance, toolkit_root) == []


class TestNonObjectThreat:
    """Defensive guard: non-dict entries in threats[] must emit E520, not AttributeError."""

    @pytest.mark.parametrize("entry", ["not-a-dict", 42])
    def test_non_object_threat_emits_e520(self, toolkit_root, entry):
        rendered = _render(validate_step_11({"threats": [entry]}, toolkit_root))
        assert any("E520" in e and "threats[0]" in e and "not an object" in e for e in rendered), rendered

    def test_mixed_threats_only_bad_entry_flagged(self, toolkit_root):
        rendered = _render(validate_step_11({"threats": [_threat(), "bad-entry"]}, toolkit_root))
        assert any("E520" in e and "threats[1]" in e and "not an object" in e for e in rendered), rendered
        assert not any("threats[0]" in e and "not an object" in e for e in rendered), rendered


class TestWrongTypedLinks:
    @pytest.mark.parametrize("bad", [7, None, "api-x", {"x": 1}, [7, None, ["api-x"]]])
    def test_wrong_typed_threatens_and_mitigated_by_do_not_raise(self, toolkit_root, bad):
        _write_spec(toolkit_root, "05_interface_contracts.json", {"apis": [{"api_id": "api-x"}]})
        _write_spec(toolkit_root, "06_invariants.json", {"rules": [{"inv_id": "inv-x", "risk_category_ref": _SECURITY_REF}]})
        rendered = _render(validate_step_11({"threats": [{"threat_id": "t", "threatens": bad, "mitigated_by": bad}]}, toolkit_root))
        assert any("W583" in e and "api-x" in e for e in rendered)
        assert any("W615" in e and "inv-x" in e for e in rendered)


class TestApiCoverageCheck:
    """W583: every public API in Step 05 should be named by the ``threatens`` of at least one threat."""

    def _write_step05(self, toolkit_root, apis):
        _write_spec(toolkit_root, "05_interface_contracts.json", {"apis": apis})

    def test_no_step05_no_warning(self, toolkit_root):
        assert _codes(toolkit_root, {"threats": []}, "W583") == []

    def test_uncovered_api_emits_w583(self, toolkit_root):
        self._write_step05(toolkit_root, [{"api_id": "api-login"}, {"api_id": "api-logout"}])
        rendered = _codes(toolkit_root, {"threats": [_threat(threatens=("api-login",))]}, "W583")
        assert any("api-logout" in e for e in rendered)
        assert not any("api-login" in e for e in rendered)

    def test_w583_api_named_by_threatens_is_covered(self, toolkit_root):
        self._write_step05(toolkit_root, [{"api_id": "api-login"}])
        assert _codes(toolkit_root, {"threats": [_threat(threatens=("api-login",))]}, "W583") == []

    def test_empty_apis_list_no_w583(self, toolkit_root):
        self._write_step05(toolkit_root, [])
        assert _codes(toolkit_root, {"threats": []}, "W583") == []

    def test_multiple_threats_cover_same_api(self, toolkit_root):
        self._write_step05(toolkit_root, [{"api_id": "api-login"}])
        instance = {"threats": [_threat("threat-01", ("api-login",)), _threat("threat-02", ("api-login",))]}
        assert _codes(toolkit_root, instance, "W583") == []

    def test_edge_case_threatens_does_not_cover_an_api(self, toolkit_root):
        self._write_step05(toolkit_root, [{"api_id": "api-login"}])
        instance = {"threats": [], "edge_cases": [{"id": "ec-x", "threatens": ["api-login"], "mitigated_by": ["fr-x"]}]}
        assert any("api-login" in e for e in _codes(toolkit_root, instance, "W583"))


class TestApiCoverageWontHaveFrExclusion:
    """W583 must not demand threat coverage for an API whose every FR is parked: it will never be built."""

    def _setup(self, toolkit_root, frs, apis):
        _write_spec(toolkit_root, "04_fr_list.json", {"functional_requirements": frs})
        _write_spec(toolkit_root, "05_interface_contracts.json", {"apis": apis})

    def test_w583_api_deriving_only_from_parked_frs_stays_exempt(self, toolkit_root):
        self._setup(
            toolkit_root,
            [{"fr_id": "fr-legacy-export", "priority": "wont-have"},
             {"fr_id": "fr-out", "scope": "out", "scope_reason": "dropped"}],
            [{"api_id": "api-legacy-export", "derives_from": ["fr-legacy-export"]},
             {"api_id": "api-out", "derives_from": ["fr-out"]}],
        )
        assert _codes(toolkit_root, {"threats": []}, "W583") == []

    def test_control_api_deriving_from_live_fr_still_fires_w583(self, toolkit_root):
        self._setup(
            toolkit_root,
            [{"fr_id": "fr-login", "priority": "must-have", "scope": "in"}],
            [{"api_id": "api-login", "derives_from": ["fr-login"]}],
        )
        assert any("api-login" in e for e in _codes(toolkit_root, {"threats": []}, "W583"))

    def test_api_deriving_from_parked_fr_and_other_id_not_exempt(self, toolkit_root):
        self._setup(
            toolkit_root,
            [{"fr_id": "fr-parked", "priority": "wont-have"}, {"fr_id": "fr-login", "priority": "must-have"}],
            [{"api_id": "api-mixed", "derives_from": ["fr-parked", "fr-login"]},
             {"api_id": "api-mixed-ids", "derives_from": ["fr-parked", "cap-x"]},
             {"api_id": "api-only-parked", "derives_from": ["fr-parked"]}],
        )
        fired = _codes(toolkit_root, {"threats": []}, "W583")
        assert any("api-mixed " in e for e in fired), fired
        assert any("api-mixed-ids" in e for e in fired), fired
        assert not any("api-only-parked" in e for e in fired), fired


class TestInvariantCoverageW615:
    """W615 fires for security-relevant invariants (with a risk_category_ref) that no threat is ``mitigated_by``."""

    def _write_step06(self, toolkit_root, rules):
        _write_spec(toolkit_root, "06_invariants.json", {"rules": rules})

    def test_invariant_with_risk_category_ref_and_no_threat_emits_w615(self, toolkit_root):
        self._write_step06(toolkit_root, [{"inv_id": "inv-auth-required", "risk_category_ref": _SECURITY_REF}])
        rendered = _codes(toolkit_root, {"threats": [_threat()]}, "W615")
        assert any("inv-auth-required" in e for e in rendered), rendered

    def test_invariant_without_risk_category_ref_no_w615(self, toolkit_root):
        self._write_step06(toolkit_root, [{"inv_id": "inv-no-risk-cat"}])
        assert _codes(toolkit_root, {"threats": [_threat()]}, "W615") == []

    def test_w615_invariant_named_by_mitigated_by_is_covered(self, toolkit_root):
        self._write_step06(toolkit_root, [{"inv_id": "inv-auth-required", "risk_category_ref": _SECURITY_REF}])
        instance = {"threats": [_threat(mitigated_by=("inv-auth-required",))]}
        assert _codes(toolkit_root, instance, "W615") == []

    def test_absent_step06_no_w615(self, toolkit_root):
        assert _codes(toolkit_root, {"threats": []}, "W615") == []

    def test_old_mitigations_do_not_cover_an_invariant(self, toolkit_root):
        self._write_step06(toolkit_root, [{"inv_id": "inv-auth-required", "risk_category_ref": _SECURITY_REF}])
        instance = {"threats": [{"threat_id": "t", "mitigations": [{"type": "inv", "id": "inv-auth-required"}]}]}
        assert any("inv-auth-required" in e for e in _codes(toolkit_root, instance, "W615"))


class TestInvariantCoverageWontHaveFrExclusion:
    """W615 must not demand threat coverage for an invariant that only ``constrains`` parked FRs."""

    def _setup(self, toolkit_root, frs, constrains):
        _write_spec(toolkit_root, "04_fr_list.json", {"functional_requirements": frs})
        _write_spec(toolkit_root, "06_invariants.json", {"rules": [
            {"inv_id": "inv-guarded", "risk_category_ref": _SECURITY_REF, "constrains": constrains}]})

    def test_w615_invariant_constraining_only_parked_frs_stays_exempt(self, toolkit_root):
        self._setup(toolkit_root, [{"fr_id": "fr-legacy-export", "priority": "wont-have"}], ["fr-legacy-export"])
        assert _codes(toolkit_root, {"threats": []}, "W615") == []

    def test_invariant_constraining_a_scope_out_fr_stays_exempt(self, toolkit_root):
        self._setup(toolkit_root, [{"fr_id": "fr-out", "scope": "out", "scope_reason": "dropped"}], ["fr-out"])
        assert _codes(toolkit_root, {"threats": []}, "W615") == []

    def test_control_invariant_constraining_a_live_fr_still_fires_w615(self, toolkit_root):
        self._setup(toolkit_root, [{"fr_id": "fr-login", "priority": "must-have"}], ["fr-login"])
        assert any("inv-guarded" in e for e in _codes(toolkit_root, {"threats": []}, "W615"))

    def test_invariant_constraining_a_parked_fr_and_an_api_is_not_exempt(self, toolkit_root):
        self._setup(toolkit_root, [{"fr_id": "fr-parked", "priority": "wont-have"}], ["fr-parked", "api-x"])
        assert any("inv-guarded" in e for e in _codes(toolkit_root, {"threats": []}, "W615"))

    def test_old_trace_is_not_a_fallback(self, toolkit_root):
        _write_spec(toolkit_root, "04_fr_list.json", {"functional_requirements": [
            {"fr_id": "fr-legacy-export", "priority": "wont-have"}]})
        _write_spec(toolkit_root, "06_invariants.json", {"rules": [{
            "inv_id": "inv-guarded", "risk_category_ref": _SECURITY_REF,
            "trace": [{"type": "fr", "id": "fr-legacy-export"}]}]})
        assert any("inv-guarded" in e for e in _codes(toolkit_root, {"threats": []}, "W615"))


class TestHostSpecSiblingResolution:
    """The Step 11 artifact in a host spec dir resolves sibling upstream files from that dir, not ``<toolkit>/spec``."""

    def test_sibling_dir_wins_over_toolkit_spec(self, tmp_path):
        toolkit_spec = tmp_path / "toolkit" / "spec"
        toolkit_spec.mkdir(parents=True)
        (toolkit_spec / "05_interface_contracts.json").write_text(json.dumps({"apis": [{"api_id": "api-toolkit-only"}]}))
        host_spec = tmp_path / "host" / "spec"
        host_spec.mkdir(parents=True)
        (host_spec / "05_interface_contracts.json").write_text(json.dumps({"apis": [{"api_id": "api-host-login"}]}))
        instance = {"threats": [_threat(threatens=("api-host-login",))]}

        rendered = _render(validate_step_11(instance, str(tmp_path / "toolkit"), str(host_spec / "11_redteam.json")))
        assert not any("api-toolkit-only" in e for e in rendered)
        assert not any("api-host-login" in e for e in rendered)

    def test_malformed_first_candidate_falls_through_to_valid_sibling(self, tmp_path):
        spec = tmp_path / "spec"
        spec.mkdir()
        (spec / "04_aaa_broken.json").write_text("{not json")
        (spec / "04_fr_list.json").write_text(json.dumps({"functional_requirements": [
            {"fr_id": "fr-legacy-export", "priority": "wont-have"}]}))
        (spec / "05_aaa_broken.json").write_text("[1, 2]")
        (spec / "05_interface_contracts.json").write_text(json.dumps({"apis": [
            {"api_id": "api-legacy-export", "derives_from": ["fr-legacy-export"]}, {"api_id": "api-live"}]}))
        (spec / "06_aaa_broken.json").write_text("{not json")
        (spec / "06_invariants.json").write_text(json.dumps({"rules": [
            {"inv_id": "inv-legacy", "risk_category_ref": _SECURITY_REF, "constrains": ["fr-legacy-export"]},
            {"inv_id": "inv-live", "risk_category_ref": _SECURITY_REF}]}))

        errors = validate_step_11({"threats": []}, str(tmp_path), str(spec / "11_redteam.json"))
        rendered = _render(errors)
        assert any("W583" in e and "api-live" in e for e in rendered), rendered
        assert not any("api-legacy-export" in e for e in rendered), rendered
        assert any("W615" in e and "inv-live" in e for e in rendered), rendered
        assert not any("inv-legacy" in e for e in rendered), rendered


def test_fr_ids_from_derives_from_ignores_wrong_typed_value():
    for bad in (7, None, "fr-a", {"x": 1}):
        assert _fr_ids_from_derives_from({"derives_from": bad}) == set()
    assert _fr_ids_from_derives_from({"derives_from": ["fr-a", 7, "", None]}) == {"fr-a"}


def test_fr_ids_from_constrains_ignores_wrong_typed_value_and_does_not_filter_ids():
    for bad in (7, None, "fr-a", {"x": 1}):
        assert _fr_ids_from_constrains({"constrains": bad}) == set()
    assert _fr_ids_from_constrains({"constrains": ["fr-a", 7, "", None, "api-b"]}) == {"fr-a", "api-b"}
    assert _fr_ids_from_constrains({"trace": [{"type": "fr", "id": "fr-a"}]}) == set()
