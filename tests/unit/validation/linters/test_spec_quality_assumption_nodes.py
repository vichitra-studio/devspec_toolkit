"""Assumption nodes (objects with ``text``) are scanned like the 1.1.1 assumption strings."""
import json

from specdev_tools.core.errors import render_errors
from specdev_tools.validation.spec_quality_lint import lint_spec_quality_file


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


def test_assumption_object_unbound_id_w573(tmp_path):
    assert any("W573" in line and "fr-x" in line for line in _codes(tmp_path, [_node("Existing fr-x keeps its contract")]))


def test_clean_assumption_object_gives_no_finding(tmp_path):
    lines = _codes(tmp_path, [_node("The legacy database schema stays unchanged during the migration")])
    assert not any(code in line for line in lines for code in ("W571", "W572", "W573", "E512"))
