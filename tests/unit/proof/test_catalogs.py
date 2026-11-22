"""WI-M7-14: the text of the M7 catalogues (error codes, command reference, host declarations page, changelog).

Each test pins a fact, such as "this code has an entry" or "the two changelog files agree", and never the wording of a sentence.
"""
from __future__ import annotations

import json
import re

import pytest
import yaml

from specdev_tools.core.errors import ERROR_CODES

from ..core._error_code_support import CODE_LITERAL_RE, ERRORS_MODULE, REGISTERED_WITHOUT_EMITTER, REMOVED_CODES, TOOLS_DIR
from .._catalog_support import (
    _CHANGELOG_MD, _CHANGELOG_YAML, _CLI_COMMANDS, _ERROR_CODES_MD, _REFERENCE_MD, _ROOT, _entry, _md_bullets, _normalised,
)

_HOST_DECLARATIONS_MD = _ROOT / "docs" / "developers" / "host_declarations.md"
_HOST_DECLARATIONS_SCHEMA = _ROOT / "schema" / "host_declarations.schema.json"

M7_CODE_NAMES = {
    "E330": "BINDING_STAGE_MISMATCH",
    "E331": "BINDING_TARGET_NOT_VERIFIED",
    "E332": "BINDING_GUARD_INVALID",
    "E333": "BINDING_DUPLICATE_TARGET",
    "E334": "UNKNOWN_STAGE_FOR_ENVIRONMENT",
    "E336": "THIRD_PARTY_PIN_NOT_EXACT",
    "E337": "THIRD_PARTY_PIN_MISMATCH",
    "E338": "THIRD_PARTY_SOURCE_UNRESOLVED",
    "E339": "THIRD_PARTY_INSTALLED_MISMATCH",
    "E341": "REMOVAL_FIXTURE_MISMATCH",
    "E342": "REMOVES_TARGET_PRESENT",
    "E343": "REALISATION_OUTDATED",
    "E344": "REALISATION_REMOVED",
    "E347": "VERIFIER_NO_VALID_EVIDENCE",
    "E348": "OBLIGATION_NOT_PROVEN",
    "W350": "SUBMODULE_DIRTY_NOT_COVERED",
    "W351": "RUN_CHANGED_CODE_TREE",
}
# E345 and E346 were never used: their numbers stay free, and are not registered.
M7_UNUSED_NUMBERS = ("E345", "E346")
M7_COMMANDS = ("verify bind", "verify run", "third-party pin", "third-party check")
M7_HOST_DECLARATION_ITEMS = ("release_tag_pattern", "setup_command", "code_tree_exclusions", "pin_sources")

# One distinctive phrase per changelog entry that M7 wrote; the md bullet and the yaml change carrying it must agree.
M7_CHANGELOG_MARKERS = (
    "`specdev verify bind <verifier-id>",
    "`specdev third-party pin <tp-id> <version>`",
    "The optional host file `spec/common/host_declarations.json`",
    "New fields of the records",
    "a new check, `removal-rules`",
    "New error codes E330 BINDING_STAGE_MISMATCH",
    "`specdev attest --prune` also removes the verification and evidence records",
    "The `records` check of `spec-check` also runs the record lint",
    "E752 (`prose-ids`) no longer reads a field whose schema is a choice between forms",
    "The graph check does not resolve the `verified_by` and `refines` links of the task criteria of a closed milestone",
    "A verifier named by a verification record",
    "`specdev trace <milestone-id> --recipe 16c` lists the verification records",
)


def _changelog_texts() -> tuple[list[str], list[str]]:
    bullets = [b for section in ("Added", "Changed", "Fixed") for b in _md_bullets(section)]
    descriptions = [c["description"] for c in yaml.safe_load(_CHANGELOG_YAML.read_text(encoding="utf-8"))["changes"]]
    return bullets, descriptions


@pytest.mark.parametrize("code", sorted(M7_CODE_NAMES))
def test_every_m7_code_has_an_error_codes_md_entry(code):
    entry = _entry(_ERROR_CODES_MD.read_text(encoding="utf-8"), code)
    assert entry, f"{code} has no entry in docs/developers/error-codes.md"
    assert "**Trigger**" in entry and "**Resolution**" in entry
    assert "not built yet" not in entry and "not emitted" not in entry
    heading = re.search(rf"^### {code} (\S+)", _ERROR_CODES_MD.read_text(encoding="utf-8"), re.M)
    assert heading and heading.group(1) == M7_CODE_NAMES[code], f"the heading of {code} does not carry its registered name"


def _m7_command_paths() -> list[str]:
    return [c["path"] for c in json.loads(_CLI_COMMANDS.read_text(encoding="utf-8"))["commands"]]


def test_m7_commands_are_in_the_generated_list():
    """The guard below is not vacuous: the four leaf commands and their two groups are in tools/cli_commands.json."""
    paths = _m7_command_paths()
    for name in ("verify", "third-party", *M7_COMMANDS):
        assert name in paths


def test_every_m7_command_has_a_reference_md_entry():
    reference = _REFERENCE_MD.read_text(encoding="utf-8")
    missing = [path for path in M7_COMMANDS if f"`specdev {path}" not in reference]
    assert not missing, f"commands without an entry in docs/developers/reference.md: {missing}"


def test_m7_codes_are_registered_with_their_names_and_none_is_a_removed_code():
    for code, name in M7_CODE_NAMES.items():
        assert ERROR_CODES.get(code) == name
    assert not set(M7_CODE_NAMES) & set(REMOVED_CODES)
    assert not set(M7_UNUSED_NUMBERS) & set(ERROR_CODES)
    assert not set(M7_UNUSED_NUMBERS) & set(REMOVED_CODES)


def test_every_m7_code_is_emitted_or_listed():
    """A registered M7 code is written as a literal in the tools, or it is listed as one that has no emitter."""
    emitted: set[str] = set()
    for py_file in TOOLS_DIR.rglob("*.py"):
        if py_file != ERRORS_MODULE:
            emitted.update(CODE_LITERAL_RE.findall(py_file.read_text(encoding="utf-8")))
    unaccounted = set(M7_CODE_NAMES) - emitted - REGISTERED_WITHOUT_EMITTER
    assert not unaccounted, f"M7 codes with no emitter that are not listed: {sorted(unaccounted)}"


@pytest.mark.parametrize("marker", M7_CHANGELOG_MARKERS)
def test_changelog_md_and_yaml_carry_the_same_m7_entry(marker):
    plain = _normalised(marker)
    bullets, descriptions = _changelog_texts()
    md = next((b for b in bullets if plain in _normalised(b)), "")
    entry = next((d for d in descriptions if plain in _normalised(d)), "")
    assert md, f"changelog/v1.2.0.md has no bullet with {marker!r}"
    assert entry, f"changelog/v1.2.0.yaml has no change with {marker!r}"
    assert _normalised(md) == _normalised(entry)


def test_changelog_names_every_m7_code_and_command():
    bullets, _ = _changelog_texts()
    text = " ".join(bullets)
    assert [code for code in M7_CODE_NAMES if code not in text] == []
    assert [path for path in M7_COMMANDS if f"specdev {path}" not in text] == []


def test_host_declarations_doc_names_the_four_items():
    text = _HOST_DECLARATIONS_MD.read_text(encoding="utf-8")
    schema_items = set(json.loads(_HOST_DECLARATIONS_SCHEMA.read_text(encoding="utf-8"))["properties"]) - {"$schema"}
    assert schema_items == set(M7_HOST_DECLARATION_ITEMS)
    assert [item for item in M7_HOST_DECLARATION_ITEMS if f"`{item}`" not in text] == []
