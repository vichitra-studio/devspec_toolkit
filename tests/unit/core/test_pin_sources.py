"""The pin-source readers: the RFC 6901 pointer (with its two escapes) and the one-capture-group regex."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.core.host_declarations import PinSource
from specdev_tools.core.pin_sources import SourceError, read_source
from unit.thirdparty._support import CLIENT, LOCK, pointer_source, regex_source

FIXTURE_REPO = Path(__file__).resolve().parents[2] / "fixtures" / "host_declarations" / "repo"


def test_json_pointer_unescapes_tilde_one_to_slash() -> None:
    """``~1`` in a pointer token is ``/`` in the key: ``node_modules~1argon2`` selects the key ``node_modules/argon2``."""
    assert read_source(pointer_source("/packages/node_modules~1argon2/version"), FIXTURE_REPO) == "0.41.1"


def test_json_pointer_unescapes_tilde_zero_to_tilde(tmp_path: Path) -> None:
    """``~0`` is ``~``, and ``~01`` is the two characters ``~1`` (``~1`` is undone first, so it cannot eat the ``1``)."""
    (tmp_path / "doc.json").write_text(json.dumps({"a~b": "tilde", "a/b": "slash", "~1": "literal"}), encoding="utf-8")
    assert read_source(pointer_source("/a~0b", "doc.json"), tmp_path) == "tilde"
    assert read_source(pointer_source("/a~1b", "doc.json"), tmp_path) == "slash"
    assert read_source(pointer_source("/~01", "doc.json"), tmp_path) == "literal"


def test_json_pointer_indexes_an_array(tmp_path: Path) -> None:
    (tmp_path / "doc.json").write_text(json.dumps({"tags": ["first", "second"]}), encoding="utf-8")
    assert read_source(pointer_source("/tags/1", "doc.json"), tmp_path) == "second"


def test_regex_takes_the_first_match() -> None:
    """Two lines match the pattern; the value is the capture group of the first."""
    assert read_source(regex_source(r'_API_VERSION = "(api-v[0-9]+)"'), FIXTURE_REPO) == "api-v3"


def test_regex_is_multi_line_so_a_line_anchor_matches_inside_the_file(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.2.3"\n', encoding="utf-8")
    assert read_source(regex_source(r'^version = "(.*)"$', "pyproject.toml"), tmp_path) == "1.2.3"


@pytest.mark.parametrize("pattern", [r"API_VERSION", r'(MAILRELAY)_API_(VERSION)', r"(?:API)_VERSION"])
def test_regex_needs_exactly_one_capture_group(pattern: str) -> None:
    """No group, two groups and a non-capturing group are all refused, even though the pattern matches the file."""
    with pytest.raises(SourceError, match="exactly one capture group"):
        read_source(regex_source(pattern), FIXTURE_REPO)


def test_regex_that_does_not_compile_is_a_source_error() -> None:
    with pytest.raises(SourceError, match="does not compile"):
        read_source(regex_source("(unclosed"), FIXTURE_REPO)


def test_regex_without_a_match_is_a_source_error() -> None:
    with pytest.raises(SourceError, match="does not match"):
        read_source(regex_source(r"NO_SUCH_CONSTANT = (\w+)"), FIXTURE_REPO)


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        (pointer_source("/packages/node_modules~1argon2/version", "no-such-file.json"), "cannot be read"),
        (regex_source("(x)", "no/such/file.ts"), "cannot be read"),
        (pointer_source("/packages/node_modules~1missing/version"), "does not resolve"),
        (pointer_source("/packages/node_modules~1lists/tags/2"), "does not resolve"),
        (pointer_source("/packages/node_modules~1lists/tags/01"), "does not resolve"),
        (pointer_source("/packages/node_modules~1lists/version"), "does not select a string"),
        (pointer_source("/packages/node_modules~1argon2"), "does not select a string"),
        (pointer_source("packages"), "must start with '/'"),
        (pointer_source("/name", CLIENT), "is not JSON"),
    ],
)
def test_missing_file_and_unresolved_pointer_are_source_errors(source: PinSource, reason: str) -> None:
    """A missing file, a pointer that selects nothing or a non-string, a bad pointer and a file that is not JSON each raise ``SourceError``."""
    with pytest.raises(SourceError, match=reason):
        read_source(source, FIXTURE_REPO)


def test_unknown_source_type_is_a_source_error() -> None:
    with pytest.raises(SourceError, match="unknown source type"):
        read_source(PinSource(type="toml", file=LOCK), FIXTURE_REPO)
