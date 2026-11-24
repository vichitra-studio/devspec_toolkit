"""The docs agree with the code: the reference lists every command, the catalogue every new code, the host guide parses.

Each test pins a fact, never the wording of a sentence.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path

import pytest
import yaml

from specdev_tools import cli
from specdev_tools.core.errors import ERROR_CODES
from specdev_tools.core.guide import lookup_guide

from ..core._error_code_support import REMOVED_CODES

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs"
DEVELOPER_DOCS = DOCS / "developers"
REFERENCE_MD = DEVELOPER_DOCS / "reference.md"
ERROR_CODES_MD = DEVELOPER_DOCS / "error-codes.md"
HOST_GUIDE = DEVELOPER_DOCS / "workflows" / "workflow_migrate_1_2_0.md"
CLI_COMMANDS = ROOT / "tools" / "cli_commands.json"
CHANGELOG_DIR = ROOT / "changelog"

CODE_RE = re.compile(r"\b([EW]\d{3})\b")
# Codes the 1.2.0 changelog names only to say that they do not exist.
SAID_NOT_TO_EXIST = {"E750", "E751", "E766"}


def _code_heading_codes(text: str) -> set[str]:
    """Every code that a heading of the catalogue names (`### E880 NAME`, `#### W611 NAME`, `### Step-16 ... (W587 / W588)`)."""
    return {code for line in text.splitlines() if re.match(r"#{2,4} ", line) for code in CODE_RE.findall(line)}


def _changelog_of_this_release() -> str:
    """The text of the 1.2.0 changelog: `v1.2.0.yaml` once it exists, else `unreleased.yaml`."""
    released = CHANGELOG_DIR / "v1.2.0.yaml"
    return (released if released.exists() else CHANGELOG_DIR / "unreleased.yaml").read_text(encoding="utf-8")


def _codes_named_before_this_release() -> set[str]:
    text = ""
    for path in CHANGELOG_DIR.glob("v*.yaml"):
        if path.name != "v1.2.0.yaml":
            text += path.read_text(encoding="utf-8")
    return set(CODE_RE.findall(text))


def _phrase(path: str) -> str:
    """A regex for the words of a command path in running text (`align diff`), not inside a longer name (`validate` in `validate-all`)."""
    return r"(?<![\w-])" + r"\s+".join(re.escape(word) for word in path.split()) + r"(?![\w-])"


def _align_parser() -> argparse.ArgumentParser:
    parser = cli.build_parser()
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    return subparsers.choices["align"]


# ---------------------------------------------------------------------------


def test_every_registered_command_path_is_in_reference_md() -> None:
    reference = REFERENCE_MD.read_text(encoding="utf-8")
    paths = [entry["path"] for entry in json.loads(CLI_COMMANDS.read_text(encoding="utf-8"))["commands"]]
    missing = [path for path in paths if not re.search(_phrase(path), reference)]
    assert not missing, f"commands registered in tools/cli_commands.json that reference.md never names: {missing}"


def test_every_align_action_and_flag_is_in_reference_md() -> None:
    reference = REFERENCE_MD.read_text(encoding="utf-8")
    align = _align_parser()
    actions = next(action.choices for action in align._actions if action.dest == "action")
    flags = {flag for action in align._actions for flag in action.option_strings if flag.startswith("--") and flag != "--help"}
    assert not [a for a in actions if f"align {a}" not in reference], "an `align` action reference.md does not show"
    assert not [f for f in sorted(flags) if f not in reference], "an `align` flag reference.md does not name"


def test_every_code_of_the_1_2_0_changelog_has_an_error_codes_entry_and_a_registration() -> None:
    named = set(CODE_RE.findall(_changelog_of_this_release())) - _codes_named_before_this_release()
    unknown = {code for code in named if code not in ERROR_CODES and code not in REMOVED_CODES} - SAID_NOT_TO_EXIST
    assert not unknown, f"the changelog names codes that are neither registered, removed nor said not to exist: {sorted(unknown)}"
    registered = {code for code in named if code in ERROR_CODES}
    assert registered, "the check found no new code: its reading of the changelog is broken"
    catalogued = _code_heading_codes(ERROR_CODES_MD.read_text(encoding="utf-8"))
    assert not sorted(registered - catalogued), "codes the 1.2.0 changelog names and error-codes.md has no heading for"


def test_every_e88x_code_has_a_guide_yaml() -> None:
    codes = sorted(code for code in ERROR_CODES if code.startswith("E88"))
    assert {"E880", "E881", "E882", "E884"} <= set(codes)
    assert "E883" not in ERROR_CODES, "E883 is unused: the migration section of the catalogue says so"
    assert [code for code in codes if lookup_guide(code) is None] == []


def test_e700_to_e704_have_a_guide_yaml() -> None:
    for code in ("E700", "E701", "E702", "E703", "E704"):
        entry = lookup_guide(code)
        assert entry is not None, f"no guide for {code}"
        assert entry["code"] == code and entry["resolution"].strip() and entry["trigger"].strip()


def test_the_host_guide_exists_and_its_links_resolve() -> None:
    assert HOST_GUIDE.is_file()
    text = HOST_GUIDE.read_text(encoding="utf-8")
    headings = {re.sub(r"[^a-z0-9 -]", "", line.lstrip("# ").strip().lower()).replace(" ", "-") for line in text.splitlines() if line.startswith("#")}
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        if re.match(r"[a-z]+://", target):
            continue
        path, _, anchor = target.partition("#")
        if path:
            assert (HOST_GUIDE.parent / path).resolve().exists(), f"link to a missing file: {target}"
        else:
            assert anchor in headings, f"link to a missing heading of the guide: {target}"
    for index in ("docs/developers/index.md", "docs/README.md"):
        assert "workflow_migrate_1_2_0.md" in (ROOT / index).read_text(encoding="utf-8"), f"{index} does not link the host guide"


_NEGATION = re.compile(r"\b(no|not|never|nothing|without|none|neither|nor|instead of)\b", re.I)
_CLAIM = re.compile(r"backup branch|apply\b[^.\n]{0,60}\b(commits|creates a (git )?commit|makes a (git )?commit|creates a backup|makes a backup)", re.I)


def _docs_that_describe_the_current_behaviour() -> list[Path]:
    """The developer docs and the docs index; `design/` is history and `architecture/` is the design itself."""
    history = DEVELOPER_DOCS / "design"
    return [DOCS / "README.md", *(path for path in sorted(DEVELOPER_DOCS.rglob("*.md")) if history not in path.parents)]


@pytest.mark.parametrize("path", _docs_that_describe_the_current_behaviour(), ids=lambda p: str(p.relative_to(DOCS)))
def test_no_doc_says_align_apply_makes_a_commit_or_a_backup_branch(path: Path) -> None:
    offending = [
        line.strip()[:160]
        for line in path.read_text(encoding="utf-8").splitlines()
        if _CLAIM.search(line) and not _NEGATION.search(line)
    ]
    assert not offending, f"{path.relative_to(ROOT)} says `align apply` commits or makes a backup, which it does not: {offending}"


def _bash_blocks(text: str) -> list[str]:
    return re.findall(r"^```bash\n(.*?)^```", text, re.S | re.M)


def _specdev_lines(block: str) -> list[list[str]]:
    lines = []
    for raw in block.splitlines():
        raw = raw.strip()
        raw = re.sub(r'^env PATH="[^"]*" ', "", raw)
        if raw.startswith("specdev "):
            lines.append(shlex.split(raw, comments=True)[1:])
    return lines


def test_every_command_line_in_the_host_guide_parses_with_the_real_parser() -> None:
    parser = cli.build_parser()
    commands = [line for block in _bash_blocks(HOST_GUIDE.read_text(encoding="utf-8")) for line in _specdev_lines(block)]
    assert len(commands) >= 8, "the guide shows fewer commands than expected: the reading of its code blocks is broken"
    for argv in commands:
        argv = [arg.replace("$TK", "./devspec_toolkit") for arg in argv]
        try:
            parser.parse_args(argv)
        except SystemExit as exit_:  # argparse prints its usage to stderr and exits 2
            raise AssertionError(f"the real parser refuses a command of the host guide: specdev {' '.join(argv)}") from exit_


def test_the_guides_of_the_migration_codes_are_valid_yaml_with_the_fields_the_loader_reads() -> None:
    folder = ROOT / "tools" / "specdev_tools" / "guides"
    for code in ("E700", "E701", "E702", "E703", "E704", "E880", "E881", "E882", "E884"):
        data = yaml.safe_load((folder / f"{code}.yaml").read_text(encoding="utf-8"))
        assert data["code"] == code and data["title"] and data["trigger"] and data["resolution"]


def test_step_10_is_not_described_as_change_control() -> None:
    discovery = (ROOT / "docs" / "developers" / "workflows" / "discovery.md").read_text(encoding="utf-8")
    prompt = (ROOT / "prompts" / "prompt_10_governance.md").read_text(encoding="utf-8")
    assert "change control policies" not in discovery.lower()
    assert "change control" not in prompt.lower()
    assert "| 10 — Governance | Set the commit-message convention" in discovery
    assert prompt.startswith("# Step 10 · Governance\n")


@pytest.mark.parametrize(
    ("relative", "sentence"),
    [
        ("docs/prompts/shared_expectations.md", "A decision that another step or a seed owns"),
        ("docs/agents/agents.md", "An answer that another step or a seed owns is not applied in this step"),
    ],
)
def test_shared_expectations_and_agents_name_the_open_item_route(relative: str, sentence: str) -> None:
    text = (ROOT / relative).read_text(encoding="utf-8")
    assert sentence in text and ".ambiguities" in text and "open item" in text
