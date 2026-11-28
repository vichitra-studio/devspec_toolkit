"""Tests for the format-preserving writer and the folder diff (WI-M10-02)."""

import json
import os

import pytest

from specdev_tools.migration.writer import DocumentSet, WriterError, detect_style, diff_trees

DATA = {"id": "x", "name": "café", "items": [{"a": 1, "b": [1, 2]}, {"a": 2, "b": []}], "empty": {}}


def _dump(**kwargs) -> str:
    final_newline = kwargs.pop("final_newline", True)
    return json.dumps(DATA, **kwargs) + ("\n" if final_newline else "")


@pytest.fixture
def spec(tmp_path):
    root = tmp_path / "spec"
    root.mkdir()
    return root


def _put(spec, name: str, text: str) -> None:
    (spec / name).write_text(text, encoding="utf-8", newline="")


def _read(spec, name: str) -> str:
    return (spec / name).read_text(encoding="utf-8")


def _round_trip(spec, text: str) -> str:
    _put(spec, "f.json", text)
    documents = DocumentSet(str(spec))
    document = documents.load("f.json")
    assert not document.style.irregular
    assert document.text() == text
    document.data["id"] = "x"
    return text


def test_round_trip_identity_indent_2(spec):
    _round_trip(spec, _dump(indent=2, ensure_ascii=False))


def test_round_trip_identity_indent_4(spec):
    _round_trip(spec, _dump(indent=4, ensure_ascii=False))


def test_round_trip_identity_tabs(spec):
    _round_trip(spec, _dump(indent="\t", ensure_ascii=False))


def test_round_trip_identity_ascii_escaped(spec):
    text = _round_trip(spec, _dump(indent=2, ensure_ascii=True))
    assert "\\u00e9" in text


def test_round_trip_identity_trailing_newline_present(spec):
    _round_trip(spec, _dump(indent=4, ensure_ascii=False, final_newline=True))


def test_round_trip_identity_trailing_newline_absent(spec):
    _round_trip(spec, _dump(indent=4, ensure_ascii=False, final_newline=False))


def test_round_trip_identity_crlf(spec):
    _round_trip(spec, _dump(indent=2, ensure_ascii=False).replace("\n", "\r\n"))


def test_irregular_file_is_rewritten_only_when_changed(spec):
    hand = '{"id": "x",\n  "items": [1, 2,\n    3]}\n'
    _put(spec, "f.json", hand)
    documents = DocumentSet(str(spec))
    document = documents.load("f.json")
    assert document.style.irregular
    assert documents.write() == []
    assert _read(spec, "f.json") == hand
    document.data["id"] = "y"
    assert documents.write() == ["f.json"]
    rewritten = _read(spec, "f.json")
    assert json.loads(rewritten) == {"id": "y", "items": [1, 2, 3]}
    assert rewritten.endswith("\n") and '\n  "id": "y"' in rewritten


def test_noop_script_leaves_every_byte_unchanged(spec):
    texts = {
        "a.json": _dump(indent=2, ensure_ascii=True, final_newline=False),
        "b.json": _dump(indent=4, ensure_ascii=False),
        "c.json": _dump(indent="\t", ensure_ascii=False),
        "d.json": '{"x":1,\n "y":[1,\n2]}',
    }
    for name, text in texts.items():
        _put(spec, name, text)
    documents = DocumentSet(str(spec))
    for name in texts:
        document = documents.load(name)
        document.data = json.loads(json.dumps(document.data))
    assert documents.write() == []
    assert {name: _read(spec, name) for name in texts} == texts


def test_one_key_edit_changes_only_that_keys_lines(spec, tmp_path):
    before = _dump(indent=4, ensure_ascii=False)
    _put(spec, "f.json", before)
    documents = DocumentSet(str(spec))
    documents.load("f.json").data["name"] = "new"
    copy_root = tmp_path / "before"
    copy_root.mkdir()
    (copy_root / "f.json").write_text(before, encoding="utf-8", newline="")
    assert documents.write() == ["f.json"]
    diff_lines = [line for line in diff_trees(str(copy_root), str(spec)).splitlines() if line[:1] in "+-" and line[:3] not in ("+++", "---")]
    assert diff_lines == ['-    "name": "café",', '+    "name": "new",']


def test_edit_keeps_key_order_and_appends_new_keys(spec):
    _put(spec, "f.json", _dump(indent=4, ensure_ascii=False))
    documents = DocumentSet(str(spec))
    documents.load("f.json").data["added"] = True
    documents.write()
    assert list(json.loads(_read(spec, "f.json"))) == ["id", "name", "items", "empty", "added"]


def test_key_order_change_counts_as_a_change(spec):
    _put(spec, "f.json", _dump(indent=4, ensure_ascii=False))
    documents = DocumentSet(str(spec))
    document = documents.load("f.json")
    document.data = dict(reversed(list(document.data.items())))
    assert documents.write() == ["f.json"]


def test_diff_is_unified_and_lists_only_changed_files(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    for root in (before, after):
        (root / "sub").mkdir(parents=True)
        (root / "same.json").write_text("{}\n", encoding="utf-8")
    (before / "sub" / "one.json").write_text('{\n    "a": 1\n}\n', encoding="utf-8")
    (after / "sub" / "one.json").write_text('{\n    "a": 2\n}\n', encoding="utf-8")
    (after / "new.json").write_text("{}", encoding="utf-8")
    diff = diff_trees(str(before), str(after))
    assert "same.json" not in diff
    assert diff.index("--- /dev/null") < diff.index("--- a/sub/one.json")
    assert "+++ b/new.json" in diff and "+++ b/sub/one.json" in diff
    assert "@@" in diff and '-    "a": 1' in diff and '+    "a": 2' in diff
    assert "\\ No newline at end of file" in diff
    assert str(tmp_path) not in diff
    assert diff_trees(str(before), str(before)) == ""
    assert diff == diff_trees(str(before), str(after))


def test_path_leaving_the_spec_folder_is_refused(spec):
    with pytest.raises(WriterError, match="leaves the spec folder"):
        DocumentSet(str(spec)).load(os.path.join("..", "other.json"))


def test_invalid_json_is_reported_with_its_path(spec):
    _put(spec, "bad.json", "{")
    with pytest.raises(WriterError, match="bad.json"):
        DocumentSet(str(spec)).load("bad.json")


def test_ascii_text_with_a_literal_escape_sequence_is_regular():
    text = json.dumps({"k": "\\u0041"}, indent=4) + "\n"
    assert not detect_style(text, json.loads(text)).irregular


def test_create_writes_a_new_file_in_the_default_style_and_refuses_one_that_exists(tmp_path):
    documents = DocumentSet(str(tmp_path))
    document = documents.create("extras/migration/new.json", {"name": "é", "items": []})
    path = tmp_path / "extras" / "migration" / "new.json"
    assert path.read_text(encoding="utf-8") == '{\n    "name": "é",\n    "items": []\n}\n'
    document.data["items"].append(1)
    assert documents.write() == ["extras/migration/new.json"]
    assert json.loads(path.read_text(encoding="utf-8"))["items"] == [1]
    with pytest.raises(WriterError, match="the file exists"):
        documents.create("extras/migration/new.json", {})
    with pytest.raises(WriterError, match="leaves the spec folder"):
        documents.create("../outside.json", {})
    assert not (tmp_path.parent / "outside.json").exists()
