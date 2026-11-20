"""The host declarations file: its loader, its schema and the host template."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.host_declarations import (
    HOST_DECLARATIONS_FILE,
    HostDeclarations,
    HostDeclarationsError,
    PinSource,
    load_host_declarations,
)
from specdev_tools.core.json_utils import resolve_effective_toolkit_root
from specdev_tools.core.schema_validate import schema_violations

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_SPEC = ROOT / "tests" / "fixtures" / "host_declarations" / "spec"
TEMPLATE = ROOT / "templates" / "host_declarations.host.json"
TOOLKIT_PATH = "devspec_toolkit"


def _violations(document: dict[str, Any]) -> list[Any]:
    return schema_violations(resolve_effective_toolkit_root(None), document)


def _spec_with(tmp_path: Path, text: str) -> Path:
    (tmp_path / "common").mkdir()
    (tmp_path / HOST_DECLARATIONS_FILE).write_text(text, encoding="utf-8")
    return tmp_path


def test_load_reads_the_four_items() -> None:
    declarations = load_host_declarations(FIXTURE_SPEC)
    assert declarations.release_tag_pattern == r"^v[0-9]+\.[0-9]+\.[0-9]+$"
    assert declarations.setup_command == "npm ci"
    assert declarations.code_tree_exclusions == (TOOLKIT_PATH, "test-results/")
    assert declarations.pin_sources["tp-argon2"] == (
        PinSource(type="json-pointer", file="package-lock.json", pointer="/packages/node_modules~1argon2/version"),
    )
    assert [source.pattern for source in declarations.pin_sources["tp-mailrelay"]] == [
        'MAILRELAY_API_VERSION = "(api-v[0-9]+)"',
        "X-Api-Version: (api-v[0-9]+)",
    ]
    assert set(declarations.pin_sources) == {"tp-argon2", "tp-mailrelay"}


def test_missing_file_gives_empty_declarations(tmp_path: Path) -> None:
    declarations = load_host_declarations(tmp_path)
    assert declarations == HostDeclarations()
    assert (declarations.release_tag_pattern, declarations.setup_command) == (None, None)
    assert (declarations.code_tree_exclusions, declarations.pin_sources) == ((), {})


def test_every_key_is_optional(tmp_path: Path) -> None:
    spec = _spec_with(tmp_path, json.dumps({"$schema": "vc:host-declarations", "setup_command": "make setup"}))
    assert load_host_declarations(spec) == HostDeclarations(setup_command="make setup")


def test_file_is_valid_against_the_schema() -> None:
    document = json.loads((FIXTURE_SPEC / HOST_DECLARATIONS_FILE).read_text(encoding="utf-8"))
    assert _violations(document) == []


@pytest.mark.parametrize(
    "document",
    [
        {"release_tag_pattern": ""},
        {"unknown_key": 1},
        {"code_tree_exclusions": ["a", "a"]},
        {"pin_sources": {"Not_Kebab": [{"type": "regex", "file": "f", "pattern": "(x)"}]}},
        {"pin_sources": {"tp-x": []}},
        {"pin_sources": {"tp-x": [{"type": "toml", "file": "f"}]}},
        {"pin_sources": {"tp-x": [{"type": "json-pointer", "file": "f", "pattern": "(x)"}]}},
        {"pin_sources": {"tp-x": [{"type": "json-pointer", "file": "f", "pointer": "no-slash"}]}},
    ],
)
def test_schema_refuses_a_wrong_shape(document: dict[str, Any]) -> None:
    assert _violations({"$schema": "vc:host-declarations", **document})


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("{not json", "cannot be read as JSON"),
        ("[]", "must hold a JSON object"),
        (json.dumps({"setup_command": 3}), ".setup_command"),
    ],
)
def test_bad_file_raises_a_host_declarations_error(tmp_path: Path, text: str, reason: str) -> None:
    spec = _spec_with(tmp_path, text)
    with pytest.raises(HostDeclarationsError, match=reason) as caught:
        load_host_declarations(spec)
    assert caught.value.path == str(spec / HOST_DECLARATIONS_FILE)


def test_template_validates_and_lists_the_toolkit_path(tmp_path: Path) -> None:
    document = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert _violations(document) == []
    assert TOOLKIT_PATH in document["code_tree_exclusions"]
    assert set(document) == {"$schema", "release_tag_pattern", "setup_command", "code_tree_exclusions", "pin_sources"}
    declarations = load_host_declarations(_spec_with(tmp_path, TEMPLATE.read_text(encoding="utf-8")))
    assert TOOLKIT_PATH in declarations.code_tree_exclusions
