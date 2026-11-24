"""The file forms of ``json patch`` and ``json delete`` count their matches (DEVSPEC-243)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from specdev_tools.core.json_utils import JsonUtilsError, json_delete, json_patch
from unit.trace._lock_support import EXAMPLE_HOST

NONE_MATCH = '.rules[] | select(.scope=="zzz")'
ALL_MATCH = '.rules[] | select(.scope=="in")'


def _copy(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    shutil.copyfile(EXAMPLE_HOST / "spec" / name, path)
    return path


@pytest.fixture
def governance(tmp_path: Path) -> Path:
    return _copy(tmp_path, "10_governance.json")


@pytest.fixture
def glossary(tmp_path: Path) -> Path:
    return _copy(tmp_path, "03_glossary.json")


def _doc(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_patch_with_a_select_that_matches_nothing_fails_and_changes_nothing(governance: Path) -> None:
    before = governance.read_bytes()
    with pytest.raises(JsonUtilsError, match="matches nothing"):
        json_patch(str(governance), NONE_MATCH + " | .scope", '"out"', validate=False)
    assert governance.read_bytes() == before


def test_delete_with_a_select_that_matches_nothing_fails(governance: Path) -> None:
    before = governance.read_bytes()
    with pytest.raises(JsonUtilsError, match="Nothing to delete"):
        json_delete(str(governance), NONE_MATCH)
    assert governance.read_bytes() == before


def test_delete_with_an_out_of_range_index_fails(glossary: Path) -> None:
    before = glossary.read_bytes()
    with pytest.raises(JsonUtilsError, match="Nothing to delete"):
        json_delete(str(glossary), ".terms[500]")
    assert glossary.read_bytes() == before


def test_patch_that_matches_many_warns_on_stderr_and_patches_all(governance: Path, capsys: pytest.CaptureFixture[str]) -> None:
    json_patch(str(governance), ALL_MATCH + " | .scope", '"out"', validate=False)
    assert f"warning: '{ALL_MATCH} | .scope' matches 3 values; all 3 are changed." in capsys.readouterr().err
    assert [rule["scope"] for rule in _doc(governance)["rules"]] == ["out"] * 3


def test_delete_that_matches_many_warns(governance: Path, capsys: pytest.CaptureFixture[str]) -> None:
    json_delete(str(governance), ALL_MATCH)
    assert f"warning: '{ALL_MATCH}' matches 3 values; all 3 are changed." in capsys.readouterr().err
    assert _doc(governance)["rules"] == []


def test_patch_of_a_new_key_of_an_existing_object_still_works(glossary: Path) -> None:
    json_patch(str(glossary), ".terms[0].newkey", '"v"', validate=False)
    assert _doc(glossary)["terms"][0]["newkey"] == "v"


def test_single_match_patch_and_delete_print_as_before(glossary: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert json_patch(str(glossary), ".terms[0].term", '"x"', validate=False) == f"Updated .terms[0].term in {glossary}"
    assert json_delete(str(glossary), ".terms[1]") == f"Deleted .terms[1] in {glossary}"
    assert capsys.readouterr().err == ""
