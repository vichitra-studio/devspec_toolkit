"""``json patch|insert|delete`` write the indentation the file has (DEVSPEC-150)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.core.json_utils import detect_indent, json_delete, json_insert, json_patch, json_write_atomic

DOC = {"a": 1, "items": [{"id": "x", "v": 1}, {"id": "y", "v": 2}]}


def _write(path: Path, indent: int | str | None) -> str:
    text = json.dumps(DOC, indent=indent) + "\n"
    path.write_text(text, encoding="utf-8")
    return text


def test_patch_keeps_a_two_space_file_two_space(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    old = _write(path, 2)
    json_patch(str(path), ".a", "2", validate=False)
    assert path.read_text(encoding="utf-8") == old.replace('"a": 1', '"a": 2')


def test_insert_and_delete_keep_a_two_space_file(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    _write(path, 2)
    json_insert(str(path), ".items", '{"id": "z", "v": 3}', validate=False)
    json_delete(str(path), ".items[0]", validate=False)
    expected = {"a": 1, "items": [{"id": "y", "v": 2}, {"id": "z", "v": 3}]}
    assert path.read_text(encoding="utf-8") == json.dumps(expected, indent=2) + "\n"


def test_a_tab_file_stays_a_tab_file(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    _write(path, "\t")
    json_patch(str(path), ".a", "2", validate=False)
    assert path.read_text(encoding="utf-8") == json.dumps({**DOC, "a": 2}, indent="\t") + "\n"


def test_a_four_space_file_and_a_new_file_stay_four_space(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    _write(path, 4)
    json_patch(str(path), ".a", "2", validate=False)
    assert path.read_text(encoding="utf-8") == json.dumps({**DOC, "a": 2}, indent=4) + "\n"
    new = tmp_path / "new.json"
    json_write_atomic(str(new), json.dumps(DOC))
    assert new.read_text(encoding="utf-8") == json.dumps(DOC, indent=4) + "\n"


@pytest.mark.parametrize("text", ["{}", ""])
def test_detect_indent_defaults_when_nothing_is_indented(text: str) -> None:
    assert detect_indent(text) == "    "


def test_one_indent_detector_serves_the_migration_writer() -> None:
    """H round 1 D-2: ``migration.writer`` imports ``detect_indent`` instead of keeping a second copy."""
    from specdev_tools.migration import writer

    assert not hasattr(writer, "_detect_indent")
    assert writer.detect_indent is detect_indent
    assert detect_indent('{\r\n\t"a": 1\r\n}\r\n') == "\t"
    assert detect_indent('{\n  "a": 1\n}') == "  "


def test_json_write_atomic_keeps_the_file_mode(tmp_path: Path) -> None:
    """H round 1 D-1: the write goes through ``replace_file_atomically``, which keeps the mode of the file."""
    path = tmp_path / "f.json"
    path.write_text('{"a": 1}\n', encoding="utf-8")
    path.chmod(0o640)
    json_write_atomic(str(path), '{"a": 2}')
    assert path.stat().st_mode & 0o777 == 0o640
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 2}
