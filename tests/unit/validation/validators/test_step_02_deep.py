"""Deep-validation tests for the step 02 (system sketch) validator."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from specdev_tools.validation.validators.step_02 import validate_step_02

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _codes(errors):
    return [e.render() for e in errors]


def _component(component_id, derives_from):
    return {"component_id": component_id, "type": "service", "derives_from": derives_from}


def _write_capabilities(spec_dir, capabilities):
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "01_capabilities.json").write_text(json.dumps({"capabilities": capabilities}))


def test_trust_boundary_internal_to_third_party(tmp_path):
    instance = {
        "components": [_component("comp-api", ["cap-a"])],
        "third_parties": [{"third_party_id": "tp-stripe", "name": "Stripe", "pin": "2024-06"}],
        "connections": [
            {"connection_id": "conn-pay", "connects_to": ["tp-stripe"], "trust_boundary": "internal"},
            {"connection_id": "conn-db", "connects_to": ["comp-api"], "trust_boundary": "internal"},
        ],
    }
    errors = _codes(validate_step_02(instance, str(tmp_path)))
    assert len(errors) == 1
    assert "E520" in errors[0] and "Connection[0]" in errors[0]


def test_capability_scope_later_exempt_from_component_coverage(tmp_path):
    _write_capabilities(
        tmp_path / "spec",
        [
            {"capability_id": "cap-now", "scope": "in"},
            {"capability_id": "cap-later", "scope": "later"},
            {"capability_id": "cap-out", "scope": "out"},
            {"capability_id": "cap-missed", "scope": "in"},
        ],
    )
    instance = {"components": [_component("comp-api", ["cap-now"])]}
    errors = _codes(validate_step_02(instance, str(tmp_path)))
    assert len(errors) == 1
    assert "E590" in errors[0] and "cap-missed" in errors[0]
    assert "cap-later" not in errors[0] and "cap-out" not in errors[0]


def test_validate_step_02_reads_capabilities_from_01(tmp_path):
    spec_root = tmp_path / "host_spec"
    _write_capabilities(spec_root, [{"capability_id": "cap-a", "scope": "in"}])
    instance = {"components": [_component("comp-api", ["cap-other"])]}

    assert "cap-a" in _codes(validate_step_02(instance, str(tmp_path / "elsewhere"), str(spec_root)))[0]
    assert validate_step_02(instance, str(tmp_path / "elsewhere")) == []  # no 01 file reachable: no data
    covered = {"components": [_component("comp-api", ["cap-a"])]}
    assert validate_step_02(covered, str(tmp_path), str(spec_root)) == []


def test_validate_step_02_reads_01_beside_the_artifact(tmp_path):
    spec_dir = tmp_path / "spec"
    _write_capabilities(spec_dir, [{"capability_id": "cap-a", "scope": "in"}])
    instance = {"components": [_component("comp-api", ["cap-other"])]}
    artifact = str(spec_dir / "02_system_sketch.json")

    errors = validate_step_02(instance, str(tmp_path / "elsewhere"), None, artifact)
    assert "E590" in _codes(errors)[0]


def test_validate_file_without_spec_root_finds_sibling_01(tmp_path):
    import shutil

    from specdev_tools.validation.validate import validate_file

    spec_dir = tmp_path / "spec"
    shutil.copytree(_REPO_ROOT / "tests" / "fixtures" / "graph_example" / "spec", spec_dir)
    cap_file = spec_dir / "01_capabilities.json"
    caps = json.loads(cap_file.read_text())
    extra = dict(caps["capabilities"][0], capability_id="cap-uncovered-extra")
    caps["capabilities"].append(extra)
    cap_file.write_text(json.dumps(caps))

    errors = validate_file(str(_REPO_ROOT), str(spec_dir / "02_system_sketch.json"))
    assert any(e.code == "E590" and "cap-uncovered-extra" in e.message for e in errors), [e.render() for e in errors]


def test_first_unparseable_01_candidate_does_not_hide_a_valid_one(tmp_path):
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    (spec_dir / "01_a_capabilities.json").write_text("{bad")
    (spec_dir / "01_b_capabilities.json").write_text(
        json.dumps({"capabilities": [{"capability_id": "cap-a", "scope": "in"}]})
    )
    instance = {"components": [_component("comp-api", ["cap-other"])]}
    errors = validate_step_02(instance, str(tmp_path), None, str(spec_dir / "02_x.json"))
    assert "E590" in _codes(errors)[0]


def test_unreadable_01_file_raises_no_error(tmp_path):
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    (spec_dir / "01_capabilities.json").write_text("{not json")
    instance = {"components": [_component("comp-api", ["cap-a"])]}
    assert validate_step_02(instance, str(tmp_path)) == []


def test_third_party_empty_pin_fails_schema():
    schema = json.loads((_REPO_ROOT / "schema" / "02_system_sketch.schema.json").read_text())
    pin = schema["allOf"][1]["properties"]["third_parties"]["items"]["properties"]["pin"]
    assert pin["minLength"] >= 1
    assert not Draft202012Validator(pin).is_valid("")
    assert Draft202012Validator(pin).is_valid("2024-06")


def test_non_string_connects_to_entry_does_not_raise(tmp_path):
    instance = {
        "components": [_component("comp-api", ["cap-a"])],
        "third_parties": [{"third_party_id": "tp-stripe", "name": "Stripe", "pin": "2024-06"}],
        "connections": [
            {"connection_id": "conn-a", "connects_to": [{"x": 1}, "tp-stripe"], "trust_boundary": "internal"},
            {"connection_id": "conn-b", "connects_to": 7, "trust_boundary": "internal"},
        ],
    }
    errors = _codes(validate_step_02(instance, str(tmp_path)))
    assert len(errors) == 1 and "Connection[0]" in errors[0]


def test_wrong_typed_derives_from_does_not_raise(tmp_path):
    _write_capabilities(tmp_path / "spec", [{"capability_id": "cap-a", "scope": "in"}])
    for bad in (7, [{"x": 1}], {"x": 1}):
        instance = {"components": [_component("comp-api", bad), _component("comp-b", ["cap-a"])]}
        assert _codes(validate_step_02(instance, str(tmp_path))) == []


def test_wrong_typed_third_parties_do_not_raise(tmp_path):
    connection = {"connection_id": "conn-a", "connects_to": ["tp-x"], "trust_boundary": "external"}
    for bad in (None, 7, ["x"], [7], [{"third_party_id": {"a": 1}}], [{"third_party_id": ["a"]}]):
        instance = {"components": [_component("comp-a", [])], "third_parties": bad, "connections": [connection]}
        validate_step_02(instance, str(tmp_path))


def test_partner_and_public_connection_without_rate_limit_is_an_error():
    from specdev_tools.validation.validators.step_02 import check_partner_public_rate_limit

    connections = [
        {"connection_id": "conn-partner", "trust_boundary": "partner"},
        {"connection_id": "conn-public", "trust_boundary": "public"},
        {"connection_id": "conn-internal", "trust_boundary": "internal"},
        {"connection_id": "conn-limited", "trust_boundary": "public", "rate_limit": {"requests": 10}},
    ]
    errors = check_partner_public_rate_limit(connections)
    assert [e.code for e in errors] == ["E520", "E520"]
    assert "Connection[0]" in errors[0].message and "'partner'" in errors[0].message
    assert "Connection[1]" in errors[1].message and "'public'" in errors[1].message
