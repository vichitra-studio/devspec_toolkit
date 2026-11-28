"""Assumption nodes (objects with ``text``) are scanned like the 1.1.1 assumption strings."""
import json

from specdev_tools.core.errors import render_errors
from specdev_tools.validation.graph_checks.prose_ids import check_prose_ids
from specdev_tools.validation.spec_quality_lint import lint_spec_quality_file
from unit.validation.graph_checks._example_support import context_of_spec, edited_example


def _codes(tmp_path, assumptions):
    path = tmp_path / "00_charter.json"
    path.write_text(json.dumps({"id": "charter", "assumptions": assumptions}), encoding="utf-8")
    return render_errors(lint_spec_quality_file(str(path), str(tmp_path)))


def _node(text):
    return {"assumption_id": "asm-one", "text": text, "derives_from": ["seed-brief"]}


def test_assumption_object_vague_quantifier_w571(tmp_path):
    assert any("W571" in line and ".text" in line for line in _codes(tmp_path, [_node("Several users share one login")]))


def test_assumption_object_placeholder_e512(tmp_path):
    assert any("E512" in line for line in _codes(tmp_path, [_node("The vendor API is TBD")]))


def test_assumption_naming_an_id_is_e752(tmp_path):
    def name_an_id(doc):
        doc["assumptions"][0]["text"] = "The flow of cap-account-recovery is unchanged."

    spec = edited_example(tmp_path / "spec", **{"00_charter.json": name_an_id})
    (error,) = check_prose_ids(context_of_spec(spec), "merge")
    assert (error.code, error.node_id) == ("E752", "asm-member-controls-email")


def test_clean_assumption_object_gives_no_finding(tmp_path):
    lines = _codes(tmp_path, [_node("The legacy database schema stays unchanged during the migration")])
    assert not any(code in line for line in lines for code in ("W571", "W572", "E512"))
