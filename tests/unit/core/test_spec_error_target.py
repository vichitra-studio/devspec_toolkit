"""``SpecError.target``: the link a finding is about, part of its identity, never printed."""
from __future__ import annotations

from specdev_tools.core.errors import SpecError, link_target, make_error
from specdev_tools.core.json_output import error_to_dict


def test_target_defaults_to_none_and_make_error_sets_it() -> None:
    assert SpecError(code="E700", message="m").target is None
    assert make_error("E700", "m").target is None
    assert make_error("E700", "m", target="derives_from->fr-x").target == "derives_from->fr-x"
    assert link_target("derives_from", "fr-x") == "derives_from->fr-x"


def test_target_is_not_rendered_and_not_in_json_output() -> None:
    error = make_error("E700", "m", "p", target="derives_from->fr-x", node_id="api-y", owner="step:05")
    assert error.render() == "E700 p m"
    document = error_to_dict(error)
    assert "target" not in document
    assert "derives_from->fr-x" not in str(document)
    assert document["node_id"] == "api-y"
