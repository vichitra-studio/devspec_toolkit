"""Deep-validation tests for step_01 capability trace integrity."""
from specdev_tools.validation.validators.step_01 import validate_step_01


def _render(errors):
    return [e.render() for e in errors]


class TestComponentIdsContract:
    """Regression: an empty ``component_ids`` set (upstream present but empty)
    must still flag stray capability->component trace refs. ``None`` means
    "upstream absent, skip cross-ref"; ``set()`` means "upstream known-empty,
    any ref is stray".
    """

    def test_none_skips_cross_ref(self, tmp_path):
        instance = {
            "capabilities": [{
                "capability_id": "cap-x",
                "trace": [{"type": "component", "id": "comp-ghost"}],
            }]
        }
        errors = validate_step_01(instance, str(tmp_path), component_ids=None)
        assert not any("unknown component" in e.render() for e in errors)

    def test_empty_set_flags_stray_ref(self, tmp_path):
        instance = {
            "capabilities": [{
                "capability_id": "cap-x",
                "trace": [{"type": "component", "id": "comp-ghost"}],
            }]
        }
        errors = validate_step_01(instance, str(tmp_path), component_ids=set())
        rendered = _render(errors)
        assert any("comp-ghost" in e and "unknown component" in e for e in rendered), rendered

    def test_populated_set_resolves_known(self, tmp_path):
        instance = {
            "capabilities": [{
                "capability_id": "cap-x",
                "trace": [{"type": "component", "id": "comp-real"}],
            }]
        }
        errors = validate_step_01(instance, str(tmp_path), component_ids={"comp-real"})
        assert not any("unknown component" in e.render() for e in errors)
