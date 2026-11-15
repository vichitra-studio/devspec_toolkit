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


def test_trust_boundary_internal_to_third_party():
    instance = {
        "components": [_component("comp-api", ["cap-a"])],
        "third_parties": [{"third_party_id": "tp-stripe", "name": "Stripe", "pin": "2024-06"}],
        "connections": [
            {"connection_id": "conn-pay", "connects_to": ["tp-stripe"], "trust_boundary": "internal"},
            {"connection_id": "conn-db", "connects_to": ["comp-api"], "trust_boundary": "internal"},
        ],
    }
    errors = _codes(validate_step_02(instance, "."))
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
    assert validate_step_02(instance, str(tmp_path / "elsewhere")) == []
    covered = {"components": [_component("comp-api", ["cap-a"])]}
    assert validate_step_02(covered, str(tmp_path), str(spec_root)) == []


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
