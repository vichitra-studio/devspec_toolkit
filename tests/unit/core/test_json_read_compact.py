"""``specdev json read --compact``: a section view for reading, one line per leaf, repeated blocks printed once (DEVSPEC-228)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.core import json_utils
from specdev_tools.core.json_utils import JsonUtilsError, json_read_compact, render_compact

LINKS = {"derives_from": ["cap-a", "cap-b"], "owner": {"team": "api", "contact": "x y"}}
DOC = {
    "items": [
        {"id": "fr-a", "statement": "The system shall do A.", "links": LINKS, "tags": []},
        {"id": "fr-b", "statement": " padded ", "links": LINKS, "odd key": 1, "none": None},
    ]
}


@pytest.fixture
def file(tmp_path: Path) -> str:
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(DOC), encoding="utf-8")
    return str(path)


def test_one_line_per_leaf_and_a_repeated_block_is_printed_once(file: str) -> None:
    assert json_read_compact(file, ".items").splitlines() == [
        "[0].id: fr-a",
        "[0].statement: The system shall do A.",
        "[0].links.derives_from: [cap-a, cap-b]",
        "[0].links.owner.team: api",
        "[0].links.owner.contact: x y",
        "[0].tags: []",
        "[1].id: fr-b",
        '[1].statement: " padded "',
        "[1].links: = [0].links",
        '[1]["odd key"]: 1',
        "[1].none: null",
    ]


def test_several_results_are_numbered_and_one_scalar_is_one_line(file: str) -> None:
    assert json_read_compact(file, ".items[].id").splitlines() == ["[0]: fr-a", "[1]: fr-b"]
    assert json_read_compact(file, ".items[0].id") == ".: fr-a"
    assert json_read_compact(file, ".items[0].links.owner").splitlines() == [".team: api", ".contact: x y"]


def test_the_view_is_shorter_than_the_json_and_loses_no_leaf(file: str) -> None:
    view = json_read_compact(file, ".items")
    assert len(view) < len(json.dumps(DOC["items"], indent=2))
    for leaf in ("fr-a", "fr-b", "cap-a", "cap-b", "api", "The system shall do A."):
        assert leaf in view


def test_the_whole_file_is_refused_as_for_a_plain_read(file: str) -> None:
    with pytest.raises(JsonUtilsError):
        json_read_compact(file, ".")
    assert render_compact([]) == ""


def test_the_flag_is_on_the_command_and_refuses_json_with_it(file: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["specdev json", "read", file, ".items[1].links", "--compact"])
    try:
        json_utils.main()
    except SystemExit as exc:
        assert exc.code in (0, None)
    assert capsys.readouterr().out.splitlines() == [".derives_from: [cap-a, cap-b]", ".owner.team: api", ".owner.contact: x y"]
    monkeypatch.setattr("sys.argv", ["specdev json", "read", file, ".items", "--compact", "--json"])
    with pytest.raises(SystemExit) as stop:
        json_utils.main()
    assert stop.value.code not in (0, None)


def test_a_string_that_would_read_as_another_value_keeps_its_quotes() -> None:
    view = render_compact([{"n": 1, "s": "1", "t": True, "u": "true", "v": None, "w": "null", "l": [1, "1", "a, b", "[x]", "plain"], "e": "= .b", "neg": "-2"}])
    assert view.splitlines() == [
        ".n: 1", '.s: "1"', ".t: true", '.u: "true"', ".v: null", '.w: "null"',
        '.l: [1, "1", "a, b", "[x]", plain]', '.e: "= .b"', '.neg: "-2"',
    ]


def test_a_filter_with_no_results_says_so(file: str) -> None:
    assert json_read_compact(file, ".items[] | select(.id == \"none\")") == "(no results)"
