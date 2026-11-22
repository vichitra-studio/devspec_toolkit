"""WI-M6a-11: the text of the M6a catalogues (error codes, command reference, changelog).

Each test reads a text file and fails when the text it guards is removed or stops matching the code.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest
import yaml

from specdev_tools import cli
from specdev_tools.core.errors import ERROR_CODES

from ..core._error_code_support import REGISTERED_WITHOUT_EMITTER

_ROOT = Path(__file__).resolve().parents[3]
_ERROR_CODES_MD = _ROOT / "docs" / "developers" / "error-codes.md"
_REFERENCE_MD = _ROOT / "docs" / "developers" / "reference.md"
_CHANGELOG_MD = _ROOT / "changelog" / "v1.2.0.md"
_CHANGELOG_YAML = _ROOT / "changelog" / "v1.2.0.yaml"
_SOURCE = _ROOT / "tools" / "specdev_tools"
_OPEN_ITEMS_SOURCE = _SOURCE / "validation" / "open_items.py"

M6A_CODES = ("W630", "E631", "E632", "W633")
_GATES_RUN_BY_A_COMMAND = ("merge", "close")
_GATE_HELP_PREFIX = "With --step or --paths"

# One distinctive phrase per changelog entry that M6a wrote; the md bullet and the yaml change carrying it must agree.
M6A_CHANGELOG_MARKERS = (
    "`specdev spec-check` gates one step: `--step N`",
    "New error codes W630 (`OPEN_ITEM`)",
    "Every finding in `spec-check --json` has an `owner`",
    "`specdev upstream-backlog` lists every open item of the spec grouped by the step",
    "The host pre-commit template `templates/pre-commit-config.host.yaml` runs `spec-check ... --paths`",
    "`specdev upstream-backlog` and `milestone-state` read both ambiguity shapes: an open item (`about`, no `severity`) is listed by `upstream-backlog`",
)


def _entry(text: str, code: str) -> str:
    """The body of the catalogue entry of *code* (from its heading to the next heading), or an empty string."""
    match = re.search(rf"^### {code}\b[^\n]*\n(.*?)(?=^#{{2,3}} )", text, re.S | re.M)
    return match.group(1) if match else ""


def _heading(text: str, code: str) -> str:
    match = re.search(rf"^### {code} (\S+)\s*$", text, re.M)
    return match.group(1) if match else ""


def _normalised(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "").replace("**", "")).strip()


def _md_bullets() -> list[str]:
    text = _CHANGELOG_MD.read_text(encoding="utf-8")
    bullets: list[str] = []
    for section in ("Added", "Changed", "Fixed"):
        body = text.split(f"### {section}\n", 1)[1].split("\n### ", 1)[0]
        bullets.extend(line[2:] for line in body.splitlines() if line.startswith("- "))
    return bullets


def _yaml_descriptions() -> list[str]:
    return [change["description"] for change in yaml.safe_load(_CHANGELOG_YAML.read_text(encoding="utf-8"))["changes"]]


def _spec_check_parser() -> argparse.ArgumentParser:
    subparsers = next(a for a in cli.build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    return subparsers.choices["spec-check"]


def _gate_flags() -> list[str]:
    """The long options of ``spec-check`` that belong to the step gate, read from the parser.

    A gate option is one in the mutually exclusive group of ``--step`` and ``--paths``, or one whose help starts
    "With --step or --paths".
    """
    parser = _spec_check_parser()
    grouped = {a for group in parser._mutually_exclusive_groups for a in group._group_actions}
    gated = {a for a in parser._actions if (a.help or "").startswith(_GATE_HELP_PREFIX)}
    return sorted(flag for action in grouped | gated for flag in action.option_strings if flag.startswith("--"))


def test_the_gate_flags_are_read_from_the_parser():
    """The guard below is not vacuous: the parser has the four flags the milestone shipped."""
    assert _gate_flags() == ["--base-ref", "--detail", "--paths", "--step"]


@pytest.mark.parametrize("code", M6A_CODES)
def test_every_m6a_code_has_a_catalogue_entry(code):
    text = _ERROR_CODES_MD.read_text(encoding="utf-8")
    entry = _entry(text, code)
    assert entry, f"{code} has no entry in docs/developers/error-codes.md"
    assert "**Trigger**" in entry and "**Resolution**" in entry and "**Promotable**" in entry
    assert code in ERROR_CODES
    assert _heading(text, code) == ERROR_CODES[code]
    assert code not in REGISTERED_WITHOUT_EMITTER


def test_the_catalogue_names_the_command_that_runs_the_merge_gate():
    """E631 and W633 name `spec-check --merge`, E632 names `milestone close`, and none of the three says that no command runs its gate.

    Until M9 the entries said "No command runs the merge gate yet" and this test passed only while that stayed true; since `spec-check --merge` exists the
    sentence is gone, and the test guards what replaced it.  The merge gate is run by the command and the close gate by `milestone close`: both are
    callers of ``check_open_items`` outside its own module.
    """
    text = _ERROR_CODES_MD.read_text(encoding="utf-8")
    assert "spec-check --merge" in _entry(text, "E631") and "spec-check --merge" in _entry(text, "W633")
    assert "specdev milestone close" in _entry(text, "E632")
    assert not [code for code in ("E631", "E632", "W633") if "No command runs" in _entry(text, code)]
    callers = {
        gate: [path.name for path in _SOURCE.rglob("*.py") if path != _OPEN_ITEMS_SOURCE and f'gate="{gate}"' in path.read_text(encoding="utf-8")]
        for gate in _GATES_RUN_BY_A_COMMAND
    }
    assert all(callers.values()), f"a gate the catalogue says a command runs has no caller outside open_items.py: {callers}"


@pytest.mark.parametrize("marker", M6A_CHANGELOG_MARKERS)
def test_changelog_md_and_yaml_carry_the_m6a_entries(marker):
    plain = _normalised(marker)
    md = next((b for b in _md_bullets() if plain in _normalised(b)), "")
    entry = next((d for d in _yaml_descriptions() if plain in _normalised(d)), "")
    assert md, f"changelog/v1.2.0.md has no bullet with {marker!r}"
    assert entry, f"changelog/v1.2.0.yaml has no change with {marker!r}"
    assert _normalised(md) == _normalised(entry)


def test_reference_names_the_step_gate_flags_and_the_open_items_check():
    text = _REFERENCE_MD.read_text(encoding="utf-8")
    section = text.split("### Step gate:", 1)[1].split("\n### ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("| `")]
    missing = [flag for flag in _gate_flags() if not any(row.startswith(f"| `{flag}") for row in rows)]
    assert not missing, f"gate flags with no row in the Step gate table of docs/developers/reference.md: {missing}"
    examples = [line for line in text.splitlines() if line.startswith("./tools/run_specdev.sh spec-check ")]
    for flag in _gate_flags():
        assert any(f" {flag}" in line for line in examples), f"no spec-check example of {flag} in docs/developers/reference.md"
    assert "The `open-items` check" in text
    row = next(line for line in text.splitlines() if line.startswith("| `specdev upstream-backlog"))
    assert "`schema_version` `\"2\"`" in row and "`unplaced`" in row and "W613" in row
