"""``json insert`` refuses a path that names one item of an array (DEVSPEC-144)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from specdev_tools.core.json_utils import JsonUtilsError, json_insert
from unit.trace._lock_support import EXAMPLE_HOST

RULE = '{"id": "rule-new", "text": "t"}'


@pytest.fixture
def governance(tmp_path: Path) -> Path:
    path = tmp_path / "10_governance.json"
    shutil.copyfile(EXAMPLE_HOST / "spec" / "10_governance.json", path)
    return path


def test_insert_at_an_indexed_object_is_refused_and_the_file_is_unchanged(governance: Path) -> None:
    before = governance.read_bytes()
    with pytest.raises(JsonUtilsError, match=r"'\.rules\[1\]' names an item of an array"):
        json_insert(str(governance), ".rules[1]", RULE, validate=False)
    assert governance.read_bytes() == before


def test_insert_at_a_selector_that_yields_array_items_is_refused(governance: Path) -> None:
    before = governance.read_bytes()
    with pytest.raises(JsonUtilsError, match="names an item of an array"):
        json_insert(str(governance), '.rules[] | select(.scope=="in")', RULE, validate=False)
    assert governance.read_bytes() == before


def test_insert_into_the_array_still_appends(governance: Path) -> None:
    count = len(json.loads(governance.read_text(encoding="utf-8"))["rules"])
    json_insert(str(governance), ".rules", RULE, validate=False)
    assert len(json.loads(governance.read_text(encoding="utf-8"))["rules"]) == count + 1


def test_insert_at_an_indexed_array_still_appends(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    path.write_text('{"m": [[1], [2]]}', encoding="utf-8")
    json_insert(str(path), ".m[0]", "9", validate=False)
    assert json.loads(path.read_text(encoding="utf-8")) == {"m": [[1, 9], [2]]}
