"""WI-M9-12: the text of the M9 catalogues (error codes, command reference, host pages, changelog).

Each test pins a fact, such as "this code has an entry with its registered name", "this message is what the command prints" or "the two changelog files agree", and never the wording of a sentence.
A message is pinned by running the command on a copy and looking for what it printed in the entry of the catalogue, not by writing the string twice.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from specdev_tools import cli, host_install
from specdev_tools.lifecycle import anchor_store
from specdev_tools.core.errors import ERROR_CODES, PROMOTABLE_PAIRS

from ..core.test_error_code_registry import CODE_LITERAL_RE, ERRORS_MODULE, REGISTERED_WITHOUT_EMITTER, REMOVED_CODES, TOOLS_DIR
from ..graph._synth import ROOT
from ..lifecycle._milestone_support import cli_run
from ..lifecycle._support import closed_record
from ..trace.test_catalogs import (
    _CHANGELOG_MD, _CHANGELOG_YAML, _CLI_COMMANDS, _ERROR_CODES_MD, _REFERENCE_MD, _ROOT, _entry, _md_bullets, _normalised,
)
from ..verify._support import commit_all, edit_doc
from ._support import release_host, tag

_DOCS = _ROOT / "docs" / "developers"
_HOST_SETUP_MD = _DOCS / "host_setup.md"
_UPDATE_MD = _DOCS / "tools" / "update.md"
_INDEX_MD = _DOCS / "index.md"
_GETTING_STARTED_MD = _DOCS / "getting_started.md"
_HOST_DECLARATIONS_MD = _DOCS / "host_declarations.md"
_TEMPLATES = _ROOT / "templates" / "workflows"

M9_CODE_NAMES = {
    "E900": "MERGE_BASE_UNRESOLVED",
    "E901": "MERGE_BINDING_FAILED",
    "E910": "RELEASE_REPO_DIRTY",
    "E911": "RELEASE_TAG_PATTERN_UNDECLARED",
    "E912": "RELEASE_TAG_INVALID",
    "E913": "RELEASE_MILESTONE_UNSIGNED",
    "E914": "RELEASE_OBLIGATION_NOT_BUILT",
    "E920": "RELEASE_PREVIOUS_UNVERIFIED",
    "E921": "PROD_TAG_UNRESOLVED",
    "E923": "PROD_DELIVERY_NOT_BUILT",
    "E924": "PROD_RELIEVED_NODE_FAILS",
    "E925": "ROLLBACK_TAG_UNKNOWN",
    "E926": "ROLLBACK_REASON_EMPTY",
    "E927": "ROLLBACK_ALREADY_RECORDED",
    "E928": "RELEASE_UNREALISED_DESIGN_MILESTONE",
    "W930": "HOST_TEMPLATE_DRIFT",
    "W931": "HOST_INSTALL_REFUSED",
    "W932": "HOST_RETIRED_COMMAND",
    "W933": "RELEASE_SCOPE_LISTED",
    "W934": "PROD_STAGING_SKIPPED",
    "W935": "HOST_SETUP_UNDECLARED",
    "W936": "RELEASE_STAGE_SKIPPED",
    "W937": "RELEASE_NO_PREVIOUS",
    "W938": "RELEASE_PREVIOUS_PREDATES_1_2_0",
}
# Numbers of the band that no code uses (rulings N1 and N2, and numbers nobody named): none may be registered or catalogued.
M9_UNUSED = ("E915", "E916", "E917", "E918", "E919", "E922", "E929", "W939")
M9_COMMANDS = ("release", "release check", "release prep", "release rollback")
M9_UPDATE_FLAGS = ("--git-root", "--install-only", "--no-install", "--adopt", "--force-claude")
# One distinctive phrase per changelog entry that M9 wrote; the md bullet and the yaml change carrying it must agree.
M9_CHANGELOG_MARKERS = (
    "`specdev spec-check SPEC --merge [--base-ref REF]` runs the merge gate",
    "`specdev release --tag NAME [--message TEXT]` cuts a release",
    "`specdev release check --stage prod --tag NAME` is the production-deploy gate",
    "`specdev release prep` runs the dev and CI bindings",
    "`specdev release rollback TAG --reason TEXT` writes",
    "New error codes E900 MERGE_BASE_UNRESOLVED",
    "`specdev update SPEC_DIR` installs the toolkit's files into the host",
    "`templates/workflows/` holds four workflow templates",
    "`docs/developers/host_setup.md` (new, linked from the developer index)",
    "`specdev status` prints the release gate run on the checkout",
    "The wrapper `tools/run_specdev.sh` that `init` wrote named `devspec_env`",
    "`specdev update` (and `init`, which runs it) installs the driver in the clone it runs in",
    "`specdev spec-check --merge` runs the merge gate and reports E631 and W633",
    "`specdev update` installs the Claude Code ask rules into a host's clone",
)
# Wordings that M9 made untrue; none may be left in the catalogue, the reference, the host pages or the changelog.
OLD_WORDINGS = (
    "release gate not installed",
    "No command runs the merge gate",
    "not by any command in this release",
    "is not run by any setup script",
    "no setup script installs the driver",
    "which no command runs yet",
    "no command installs the template",
    "functions that no command runs in this release",
    "is a library function in this release",
    "is not a command of this toolkit version",
    "re-stamped instantly",
    "the release check is not in this release",
    "is milestone M9's",
)
_TEXT_FILES = (
    _ERROR_CODES_MD, _REFERENCE_MD, _CHANGELOG_MD, _CHANGELOG_YAML, _HOST_SETUP_MD, _UPDATE_MD, _INDEX_MD, _GETTING_STARTED_MD, _HOST_DECLARATIONS_MD,
    _DOCS / "workflows" / "spec_to_impl.md",
    _DOCS / "workflows" / "discovery.md",
)


def _changelog_texts() -> tuple[list[str], list[str]]:
    bullets = [b for section in ("Breaking", "Added", "Changed", "Fixed") for b in _md_bullets(section)]
    descriptions = [c["description"] for c in yaml.safe_load(_CHANGELOG_YAML.read_text(encoding="utf-8"))["changes"]]
    return bullets, descriptions


def _heading(text: str, code: str) -> re.Match[str] | None:
    return re.search(rf"^#{{3,4}} {code} (\S+)", text, re.M)


# --- the codes -------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("code", sorted(M9_CODE_NAMES))
def test_every_m9_code_has_an_entry_with_trigger_and_resolution(code):
    text = _ERROR_CODES_MD.read_text(encoding="utf-8")
    entry = _entry(text, code)
    assert entry, f"{code} has no entry in docs/developers/error-codes.md"
    assert "**Trigger**" in entry and "**Resolution**" in entry and "**Promotable**: No" in entry
    heading = _heading(text, code)
    assert heading and heading.group(1) == M9_CODE_NAMES[code], f"the heading of {code} does not carry its registered name"
    section = text[text.index("## Merge and Release Gates"):text.index("## Removed Codes")]
    assert heading.start() > text.index("## Merge and Release Gates") and f"### {code} " in section


def test_m9_codes_are_registered_with_their_names_and_none_is_promotable():
    for code, name in M9_CODE_NAMES.items():
        assert ERROR_CODES.get(code) == name
    assert not set(M9_CODE_NAMES) & set(REMOVED_CODES)
    promotable = set(PROMOTABLE_PAIRS) | set(PROMOTABLE_PAIRS.values())
    assert not set(M9_CODE_NAMES) & promotable, "a code of the merge and release band is promotable; its entry says it is not"


def test_w9xx_not_promotable():
    warnings = [code for code in M9_CODE_NAMES if code.startswith("W")]
    assert warnings and not [code for code in warnings if code in PROMOTABLE_PAIRS]


def test_expected_codes_present():
    registered = {code for code in ERROR_CODES if re.fullmatch(r"[EW]9\d\d", code)}
    assert registered == set(M9_CODE_NAMES), f"registered {sorted(registered - set(M9_CODE_NAMES))} unlisted, listed {sorted(set(M9_CODE_NAMES) - registered)} missing"
    text = _ERROR_CODES_MD.read_text(encoding="utf-8")
    assert [code for code in M9_UNUSED if code in ERROR_CODES or re.search(rf"^### {code}\b", text, re.M)] == []


def test_every_m9_code_is_emitted_or_listed_as_without_an_emitter():
    emitted: set[str] = set()
    for py_file in TOOLS_DIR.rglob("*.py"):
        if py_file != ERRORS_MODULE:
            emitted.update(CODE_LITERAL_RE.findall(py_file.read_text(encoding="utf-8")))
    unaccounted = set(M9_CODE_NAMES) - emitted - REGISTERED_WITHOUT_EMITTER
    assert not unaccounted, f"M9 codes with no emitter that are not listed: {sorted(unaccounted)}"
    assert not set(M9_CODE_NAMES) & REGISTERED_WITHOUT_EMITTER, "an M9 code is still listed as having no emitter; the catalogue says it is emitted"


def test_the_ownership_the_catalogue_describes_is_the_one_of_the_table():
    table = json.loads((_ROOT / "tools" / "error_ownership.json").read_text(encoding="utf-8"))["rows"]
    owner_of = {code: row["owner"] for row in table for code in row["codes"]}
    assert owner_of["E900"] == owner_of["E901"] == "merge-check"
    assert owner_of["E913"] == "close-gate"
    assert all(owner_of[code] == "release-gate" for code in ("E920", "E921", "E923", "E924", "E928", "W933", "W934", "W936", "W937", "W938"))
    assert not [code for code in ("E910", "E911", "E912", "E925", "E926", "E927", "W930", "W931", "W932", "W935") if code in owner_of], "the catalogue says these have no owner row"


def test_the_gate_entries_name_the_command_that_runs_them():
    text = _ERROR_CODES_MD.read_text(encoding="utf-8")
    for code in ("E343", "E344", "E830"):
        assert "specdev release" in _entry(text, code), code
    for code in ("E347", "E348"):
        assert "release check --stage prod" in _entry(text, code), code
    assert "spec-check --merge" in _entry(text, "E631") and "spec-check --merge" in _entry(text, "W633")


# --- messages, pinned by running the command ---------------------------------------------------------------------------------------


def _message(code: str, *streams: str) -> str:
    line = next((line for stream in streams for line in stream.splitlines() if line.strip().startswith(code)), "")
    return line.strip()


def _in_entry(code: str, printed: str) -> None:
    assert printed, f"the command printed no {code}"
    assert _normalised(printed) in _normalised(_entry(_ERROR_CODES_MD.read_text(encoding="utf-8"), code)), f"the entry of {code} does not quote what the command printed: {printed}"


def test_the_quoted_messages_are_what_the_commands_print(tmp_path):
    host = release_host(tmp_path)
    code, out, err = cli_run(host, "release", "--tag", "banana")
    assert code == 1
    _in_entry("E912", _message("E912", out, err))
    code, out, err = cli_run(host, "release", "check", "--stage", "prod", "--tag", "v9.9.9")
    assert code == 1
    _in_entry("E921", _message("E921", out, err))
    code, out, err = cli_run(host, "release", "rollback", "v7.7.7", "--reason", "x")
    assert code == 1
    _in_entry("E925", _message("E925", out, err))
    tag(host, "v1.0.0")
    code, out, err = cli_run(host, "release", "rollback", "v1.0.0", "--reason", " ")
    assert code == 1
    _in_entry("E926", _message("E926", out, err))
    code, out, err = cli_run(host, "spec-check", str(host / "spec"), "--merge", "--base-ref", "origin/nowhere")
    assert code == 1
    _in_entry("E900", _message("E900", out, err))


def test_the_quoted_message_of_a_close_record_with_no_sign_off_is_what_the_command_prints(tmp_path):
    """E913 has two messages: the row of a milestone with no close record (first) and a close record that names no sign-off record (second)."""
    host = release_host(tmp_path)
    anchor_store.write_row_state(host / "spec", "ms-account-recovery", "done", close=closed_record(signoff=None), repo_root=str(ROOT))
    commit_all(host, "a close record that names no sign-off")
    code, out, err = cli_run(host, "release", "--tag", "v1.0.0")
    assert code == 1
    printed = _message("E913", out, err)
    assert "names no sign-off record" in printed and "set its status back to `in_progress`" in printed
    _in_entry("E913", printed)


def test_the_quoted_message_of_a_done_row_with_no_close_record_is_what_the_command_prints(tmp_path):
    """The first E913 text (a row that is done and has no ``close`` key: only a hand edit leaves it) is quoted as the command prints it, and the way out it names is the one the Resolution ran."""
    host = release_host(tmp_path)
    edit_doc(host, "16_impl_context.json", lambda doc: doc["plan"]["milestone_index"][0].update(status="done"))
    commit_all(host, "a done row with no close record")
    code, out, err = cli_run(host, "release", "--tag", "v1.0.0")
    assert code == 1
    printed = _message("E913", out, err)
    assert "no `close` key" in printed and "set its status back to `in_progress`" in printed
    _in_entry("E913", printed)


def test_the_quoted_dirty_tree_message_names_the_file_of_a_rollback_record(tmp_path):
    """E910 names the file git lists (``rollback-v1.0.0.json``), not its folder; the entry and the host guide quote it."""
    host = release_host(tmp_path)
    tag(host, "v1.0.0")
    code, out, err = cli_run(host, "release", "rollback", "v1.0.0", "--reason", "x")
    assert code == 0, out + err
    code, out, err = cli_run(host, "release", "--tag", "v1.0.1")
    assert code == 1
    printed = _message("E910", out, err)
    assert "(1 path(s): spec/extras/releases/rollback-v1.0.0.json)" in printed
    _in_entry("E910", printed)
    assert "(1 path(s): spec/extras/releases/rollback-v1.0.0.json)" in (ROOT / "docs" / "developers" / "host_setup.md").read_text(encoding="utf-8")


def test_the_quoted_message_of_an_undeclared_pattern_is_what_the_command_prints(tmp_path):
    host = release_host(tmp_path)
    (host / "spec" / "common" / "host_declarations.json").unlink()
    commit_all(host, "no declarations")
    code, out, err = cli_run(host, "release", "--tag", "v1.0.0")
    assert code == 1
    _in_entry("E911", _message("E911", out, err))


def test_the_first_release_prints_the_quoted_warning(tmp_path):
    host = release_host(tmp_path)
    code, out, err = cli_run(host, "release", "--tag", "v1.0.0")
    assert code == 0, out + err
    line = next(line.strip() for line in out.splitlines() if "W937" in line)
    assert _normalised(line) in _normalised(_entry(_ERROR_CODES_MD.read_text(encoding="utf-8"), "W937"))


# --- the commands ------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", M9_COMMANDS)
def test_every_m9_command_is_in_the_generated_list_and_the_reference(path):
    paths = [c["path"] for c in json.loads(_CLI_COMMANDS.read_text(encoding="utf-8"))["commands"]]
    assert path in paths
    reference = _REFERENCE_MD.read_text(encoding="utf-8")
    assert f"`specdev {path}" in reference, f"docs/developers/reference.md has no entry for `specdev {path}`"


def test_the_merge_gate_flag_is_in_the_reference_and_the_parser():
    reference = _REFERENCE_MD.read_text(encoding="utf-8")
    assert "spec-check --merge" in reference and "### Merge gate" in reference
    args = cli.build_parser().parse_args(["spec-check", "spec", "--merge", "--base-ref", "main"])
    assert args.merge is True and args.base_ref == "main"


@pytest.mark.parametrize("flag", M9_UPDATE_FLAGS)
def test_every_update_flag_is_in_the_reference_the_update_page_and_the_parser(flag):
    assert f"`{flag}" in _REFERENCE_MD.read_text(encoding="utf-8")
    assert f"`{flag}`" in _UPDATE_MD.read_text(encoding="utf-8")
    argv = ["update", "spec", flag] + (["."] if flag == "--git-root" else [])
    assert cli.build_parser().parse_args(argv).cmd == "update"


def test_the_update_pages_name_every_piece_of_the_installer_in_order():
    names = [piece.name for piece in host_install.PIECES]
    for page in (_HOST_SETUP_MD, _UPDATE_MD):
        text = page.read_text(encoding="utf-8")
        positions = [text.find(f"`{name}`") for name in names]
        assert -1 not in positions, f"{page.name} does not name every piece: {names}"
    reference = _REFERENCE_MD.read_text(encoding="utf-8")
    assert all(f"`{name}`" in reference for name in names)


def test_the_host_page_names_each_workflow_template_and_the_installed_one_is_marked():
    text = _HOST_SETUP_MD.read_text(encoding="utf-8")
    templates = sorted(path.name for path in _TEMPLATES.iterdir())
    assert templates and all(name in text for name in templates)
    assert (_TEMPLATES / "specdev-merge-check.yml").read_text(encoding="utf-8").startswith("# specdev-managed: merge-check")


def test_host_setup_guide_is_linked_from_the_index():
    assert "host_setup.md" in _INDEX_MD.read_text(encoding="utf-8")
    assert "host_setup.md" in _GETTING_STARTED_MD.read_text(encoding="utf-8")
    assert "host_setup.md" in _REFERENCE_MD.read_text(encoding="utf-8")
    assert _HOST_SETUP_MD.is_file()


def test_the_declarations_page_says_which_command_reads_each_of_the_three_items():
    text = _HOST_DECLARATIONS_MD.read_text(encoding="utf-8")
    rows = {name: next(line for line in text.splitlines() if line.startswith(f"| `{name}`")) for name in ("release_tag_pattern", "setup_command", "pin_sources")}
    assert "specdev release" in rows["release_tag_pattern"] and "specdev update" in rows["setup_command"] and "spec-check --merge" in rows["pin_sources"]


def test_discovery_page_says_enforcement_is_the_merge_check_not_pull_request_blocking():
    text = (_DOCS / "workflows" / "discovery.md").read_text(encoding="utf-8")
    assert "spec-check --merge" in text and "specdev-merge-check.yml" in text


# --- the open item that the merge gate reports is printed in merge mode ----------------------------------------------------------------------


def test_the_merge_gate_prints_the_open_item_the_catalogue_describes(tmp_path):
    host = release_host(tmp_path)
    edit_doc(host, "05_interface_contracts.json", lambda doc: doc.update(ambiguities=[{"id": "amb-reset-seed", "description": "which seed account", "about": ["seed-accounts"], "decision": "apply in the batch pass"}]))
    commit_all(host, "an open item")
    code, out, err = cli_run(host, "spec-check", str(host / "spec"), "--merge", "--base-ref", "HEAD")
    assert code == 1 and "E631" in out + err
    _, plain_out, plain_err = cli_run(host, "spec-check", str(host / "spec"))
    assert "E631" not in plain_out + plain_err and "merge-open-items" not in plain_out


# --- the changelog -------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("marker", M9_CHANGELOG_MARKERS)
def test_changelog_md_and_yaml_carry_the_same_m9_entry(marker):
    plain = _normalised(marker)
    bullets, descriptions = _changelog_texts()
    md = next((b for b in bullets if plain in _normalised(b)), "")
    entry = next((d for d in descriptions if plain in _normalised(d)), "")
    assert md, f"changelog/unreleased.md has no bullet with {marker!r}"
    assert entry, f"changelog/unreleased.yaml has no change with {marker!r}"
    assert _normalised(md) == _normalised(entry)


def test_changelog_names_every_m9_code_and_command():
    bullets, _ = _changelog_texts()
    text = " ".join(bullets)
    assert [code for code in M9_CODE_NAMES if code not in text] == []
    assert [path for path in M9_COMMANDS if f"specdev {path}" not in text] == []
    assert "--merge" in text and all(flag in text for flag in M9_UPDATE_FLAGS)


def test_every_m9_command_entry_ends_with_a_command_a_reader_can_run():
    bullets, _ = _changelog_texts()
    for marker in M9_CHANGELOG_MARKERS[:11]:
        bullet = next(b for b in bullets if _normalised(marker) in _normalised(b))
        assert re.search(r"Shown by `[^`]+`( in a host)?\.$", bullet), f"the entry {marker!r} does not end with a command"


@pytest.mark.parametrize("wording", OLD_WORDINGS)
def test_no_text_file_keeps_a_wording_the_milestone_made_untrue(wording):
    hits = [path.name for path in _TEXT_FILES if wording in path.read_text(encoding="utf-8")]
    assert hits == [], f"{wording!r} is still in {hits}"
