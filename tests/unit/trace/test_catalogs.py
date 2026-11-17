"""WI-M5-16: the text of the M5 catalogues (error codes, command reference, changelog, policy docs).

Each test reads a text file and fails when the text it guards is removed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from specdev_tools.core.errors import ERROR_CODES

from ..core.test_error_code_registry import REGISTERED_WITHOUT_EMITTER

_ROOT = Path(__file__).resolve().parents[3]
_ERROR_CODES_MD = _ROOT / "docs" / "developers" / "error-codes.md"
_REFERENCE_MD = _ROOT / "docs" / "developers" / "reference.md"
_SHARED_MD = _ROOT / "docs" / "prompts" / "shared_expectations.md"
_GOVERNANCE_MD = _ROOT / "docs" / "architecture" / "governance_architecture.md"
_CHANGELOG_MD = _ROOT / "changelog" / "unreleased.md"
_CHANGELOG_YAML = _ROOT / "changelog" / "unreleased.yaml"
_CLI_COMMANDS = _ROOT / "tools" / "cli_commands.json"

# E766 was withdrawn: no entry and no registration.
M5_CODES = (
    "E760", "E761", "E762", "E763", "E764", "E765",
    "E767", "E768", "E769", "E770", "E771", "E772", "E773", "E774",
    "E778", "E882",
)
M5_COMMAND_GROUPS = ("stale", "attest", "coverage", "lock", "step")
M5_EXTRA_COMMANDS = ("node rename",)

# One distinctive phrase per changelog entry that M5 wrote; the md bullet and the yaml change carrying it must agree.
M5_CHANGELOG_MARKERS = (
    "The trace lock `spec/extras/trace.lock.json`",
    "`specdev stale [--step NN] [--diff]`",
    "`specdev lock merge BASE OURS THEIRS PATH`",
    "`specdev json patch|insert|delete --id <node-id>`",
    "`specdev step create NN --from DRAFT",
    "`specdev node rename OLD NEW",
    "Verification and evidence records",
    "New error codes E760 to E765",
    "File-level forward replay is retired",
    "(DEVSPEC-317)",
    "(DEVSPEC-318)",
)


def _entry(text: str, code: str) -> str:
    """The body of the catalogue entry of *code* (from its heading to the next heading), or an empty string."""
    match = re.search(rf"^### {code}\b[^\n]*\n(.*?)(?=^#{{2,3}} )", text, re.S | re.M)
    return match.group(1) if match else ""


def _normalised(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "").replace("**", "")).strip()


def _md_bullets(section: str) -> list[str]:
    md = _CHANGELOG_MD.read_text(encoding="utf-8")
    body = md.split(f"### {section}\n", 1)[1].split("\n### ", 1)[0]
    return [line[2:] for line in body.splitlines() if line.startswith("- ")]


def _changelog_pairs() -> list[tuple[str, str, str]]:
    """(marker, md bullet, yaml description) for each M5 marker; an empty string where one is missing."""
    bullets = [b for section in ("Added", "Changed", "Fixed") for b in _md_bullets(section)]
    descriptions = [c["description"] for c in yaml.safe_load(_CHANGELOG_YAML.read_text(encoding="utf-8"))["changes"]]
    pairs = []
    for marker in M5_CHANGELOG_MARKERS:
        plain = _normalised(marker)
        md = next((b for b in bullets if plain in _normalised(b)), "")
        entry = next((d for d in descriptions if plain in _normalised(d)), "")
        pairs.append((marker, md, entry))
    return pairs


@pytest.mark.parametrize("code", M5_CODES)
def test_every_m5_code_has_an_error_codes_md_entry(code):
    entry = _entry(_ERROR_CODES_MD.read_text(encoding="utf-8"), code)
    assert entry, f"{code} has no entry in docs/developers/error-codes.md"
    assert "**Trigger**" in entry and "**Resolution**" in entry
    assert "not built yet" not in entry and "not emitted" not in entry
    assert code in ERROR_CODES


def test_e766_has_no_entry_and_is_not_registered():
    assert "E766" not in ERROR_CODES
    assert not _entry(_ERROR_CODES_MD.read_text(encoding="utf-8"), "E766")


def _m5_command_paths() -> list[str]:
    paths = [c["path"] for c in json.loads(_CLI_COMMANDS.read_text(encoding="utf-8"))["commands"]]
    return [p for p in paths if p.split()[0] in M5_COMMAND_GROUPS or p in M5_EXTRA_COMMANDS]


def test_m5_commands_are_in_the_generated_list():
    """The guard below is not vacuous: every group and extra command of M5 is in tools/cli_commands.json."""
    paths = _m5_command_paths()
    for name in ("stale", "attest", "coverage", "lock merge", "lock install-driver", "step create", "step ready", "node rename"):
        assert name in paths


def test_every_m5_command_has_a_reference_md_entry():
    reference = _REFERENCE_MD.read_text(encoding="utf-8")
    leaves = [p for p in _m5_command_paths() if p not in ("lock", "step")]
    missing = [p for p in leaves if f"`specdev {p}" not in reference]
    assert not missing, f"commands without an entry in docs/developers/reference.md: {missing}"


@pytest.mark.parametrize(
    "phrase",
    [
        "json patch --id",
        "json insert --id",
        "json delete --id",
        "json insert --step",
        "Without `--yes` it prints what it would write",
        "specdev attest --prune",
        "### Trace lock, replay and attest",
    ],
)
def test_reference_md_documents_the_id_forms_and_attest(phrase):
    assert phrase in _REFERENCE_MD.read_text(encoding="utf-8")


def test_registered_without_emitter_holds_no_m5_code():
    assert not set(M5_CODES) & REGISTERED_WITHOUT_EMITTER
    assert "W720" not in REGISTERED_WITHOUT_EMITTER


def test_error_codes_md_no_longer_says_forward_replay_emits_the_retired_codes():
    text = _ERROR_CODES_MD.read_text(encoding="utf-8")
    e550 = _entry(text, "E550 / W550") or text.split("### E550 / W550", 1)[1].split("\n### ", 1)[0]
    assert "`unknown_step_in_diff`" not in e550 and "four shapes" not in e550
    w595 = text.split("### E595 / W595", 1)[1].split("\n### ", 1)[0]
    assert "no longer report W595" in w595
    assert "no check emits" not in text.split("### W720", 1)[1].split("\n### ", 1)[0]


@pytest.mark.parametrize("marker", M5_CHANGELOG_MARKERS)
def test_changelog_md_and_yaml_carry_the_same_m5_entry(marker):
    (_, md, entry), = [p for p in _changelog_pairs() if p[0] == marker]
    assert md, f"changelog/unreleased.md has no bullet with {marker!r}"
    assert entry, f"changelog/unreleased.yaml has no change with {marker!r}"
    assert _normalised(md) == _normalised(entry)


def test_changelog_no_longer_says_w720_is_not_emitted():
    for path in (_CHANGELOG_MD, _CHANGELOG_YAML):
        assert "no check emits it" not in _normalised(path.read_text(encoding="utf-8"))


def test_shared_expectations_describes_the_forward_pass_and_the_id_form_flags():
    text = _SHARED_MD.read_text(encoding="utf-8")
    assert "specdev stale --step NN" in text and "specdev attest --step NN --yes" in text
    assert "accept all three flags" in text


def test_governance_architecture_marks_forward_replay_superseded():
    text = _GOVERNANCE_MD.read_text(encoding="utf-8")
    assert "no longer decides whether replay is required" in text
    assert "to verify all downstream steps are replayed" not in text
