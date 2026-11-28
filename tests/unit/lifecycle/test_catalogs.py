"""WI-M8-16: the text of the M8 catalogues (error codes, command reference, changelog).

Each test pins a fact, such as "this code has an entry with its registered name" or "the two changelog files agree".
Four pin a phrase: ``M8_CHANGELOG_MARKERS`` (the words that find a changelog entry), ``OLD_WORDINGS`` (sentences the catalogues must not hold),
the ``Shown by`` ending of an M8 changelog entry, and the milestone state block of the reference.
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

M8_CODE_NAMES = {
    "E800": "MILESTONE_NOT_STARTABLE",
    "E801": "MILESTONE_TRANSITION_INVALID",
    "E802": "DEFER_REASON_MISSING",
    "E803": "PLAN_MILESTONE_UNKNOWN",
    "E810": "CLOSE_CRITERION_UNREALISED",
    "E811": "CLOSE_CRITERION_UNPROVEN",
    "E812": "CLOSE_ITEM_NOT_EXECUTED",
    "E813": "CLOSE_REVIEW_NOT_VERIFIED",
    "E814": "CLOSE_NO_SIGNOFF",
    "E820": "PLAN_FROZEN",
    "E821": "RECORD_TARGET_UNKNOWN",
    "E822": "RECORD_ACTION_NAMES_VERIFIER",
    "E823": "REVIEW_RECORD_INVALID",
    "E824": "ATTEST_TARGET_NOT_ATTESTABLE",
    "W825": "EXECUTION_STALE",
    "W826": "PLAN_ITEM_REALISES_EXCLUDED_TASK",
    "E827": "PLAN_CHANGED_AFTER_CLOSE",
    "E830": "REVIEW_RULE_UNATTESTED",
    "W837": "PLAN_FILE_LARGE",
}
# Retired by M8 (BR-a): each has a "(removed)" stub, and none is registered or emitted any more.
M8_RETIRED = {
    "E301": "MISSING_PROOF_CLOSURE",
    "E302": "UNPROVEN_VERIFIED_REVIEW",
    "E305": "PLANNED_UNEXECUTED",
    "E306": "SEMANTIC_REVIEW_FR_MISMATCH",
    "E307": "BEHAVIOR_VALIDATION_PAIRING",
    "W599": "EVIDENCE_TOO_SHORT",
    "W600": "VERIFIED_ACTION_NO_EVIDENCE",
    "W601": "EVIDENCE_NO_ARTIFACT_REF",
}
# Codes that stay and whose entry M8 rewrote (E303 re-meant, the anchor family re-keyed).
M8_REWRITTEN = {
    "E303": "COMMIT_MESSAGE_MISMATCH",
    "E308": "ANCHOR_SCOPE_DRIFT",
    "E309": "ANCHOR_CHECKLIST_DRIFT",
    "W588": "ANCHOR_MILESTONE_UNREADABLE",
    "W589": "ANCHOR_MILESTONE_MISSCHEMAED",
    "W611": "ANCHOR_DRIFT_SUPPRESSED",
}
M8_COMMANDS = (
    "milestone start", "milestone defer", "milestone sign-off", "milestone close",
    "status", "plan record", "review record", "verify attest", "step create",
)
# One distinctive phrase per changelog entry that M8 wrote; the md bullet and the yaml change carrying it must agree.
M8_CHANGELOG_MARKERS = (
    "Step 16 plan (`16_impl_context`), breaking for a host's plans",
    "`specdev milestone start|defer|sign-off|close <milestone-id>` write",
    "`specdev status [--milestone <milestone-id>] [--json]`",
    "`specdev plan record <ITEM>/<action-id> --outcome done|failed|blocked [--note TEXT]` appends",
    "`specdev verify attest <node-id>...` records an attestation",
    "`specdev step create 16 --from DRAFT` creates the anchor file",
    "New error codes E800 MILESTONE_NOT_STARTABLE",
    "Step 16 schemas, additions",
    "`specdev milestone-state --batch-id <batch>` prints a new key `milestone`",
    "Error codes retired into the removed set",
    "The step 16 prompts (`prompt_16_impl_context.md`",
    "While a host migrates it meets these states",
    "`docs/developers/reference.md` documents the commands above",
)
# Wordings that M8 made untrue; none may be left in the catalogue, the reference, the workflow pages or the changelog.
OLD_WORDINGS = ("refuses a step from 16 to 16c", "No command runs the close gate", "evd-install-", "SPECDEV_PLAN_BYTES", "for steps 16 to 16c")
_TEXT_FILES = (
    _ERROR_CODES_MD, _REFERENCE_MD, _CHANGELOG_MD, _CHANGELOG_YAML,
    _ROOT / "docs" / "developers" / "workflows" / "spec_to_impl.md",
    _ROOT / "docs" / "developers" / "workflows" / "workflow_bootstrap_legacy.md",
    _ROOT / "docs" / "agents" / "agents.md",
)


def _changelog_texts() -> tuple[list[str], list[str]]:
    bullets = [b for section in ("Breaking Changes", "Added", "Changed", "Fixed") for b in _md_bullets(section)]
    descriptions = [c["description"] for c in yaml.safe_load(_CHANGELOG_YAML.read_text(encoding="utf-8"))["changes"]]
    return bullets, descriptions


def _heading(text: str, code: str) -> re.Match[str] | None:
    return re.search(rf"^#{{3,4}} {code} (\S+)", text, re.M)


@pytest.mark.parametrize("code", sorted(M8_CODE_NAMES))
def test_every_m8_code_has_an_entry_with_trigger_resolution_and_promotable(code):
    text = _ERROR_CODES_MD.read_text(encoding="utf-8")
    entry = _entry(text, code)
    assert entry, f"{code} has no entry in docs/developers/error-codes.md"
    assert "**Trigger**" in entry and "**Resolution**" in entry and "**Promotable**" in entry
    assert "not built yet" not in entry
    heading = _heading(text, code)
    assert heading and heading.group(1) == M8_CODE_NAMES[code], f"the heading of {code} does not carry its registered name"


@pytest.mark.parametrize("code", sorted(M8_REWRITTEN))
def test_the_rewritten_entries_keep_their_registered_names(code):
    text = _ERROR_CODES_MD.read_text(encoding="utf-8")
    heading = _heading(text, code)
    assert heading and heading.group(1) == M8_REWRITTEN[code]
    assert ERROR_CODES.get(code) == M8_REWRITTEN[code]
    assert "(removed)" not in text[heading.start():text.index("\n", heading.start())]


@pytest.mark.parametrize("code", sorted(M8_RETIRED))
def test_every_retired_code_has_a_removed_stub_and_is_not_registered(code):
    text = _ERROR_CODES_MD.read_text(encoding="utf-8")
    heading = re.search(rf"^### {code} {M8_RETIRED[code]} \(removed\)$", text, re.M)
    assert heading, f"{code} has no '(removed)' stub"
    assert text.index("## Removed Codes") < heading.start() < text.index("## Exception Classes"), f"the stub of {code} is not in the Removed Codes section"
    stub = _entry(text, code)
    assert stub.strip().startswith("Removed in 1.2.0")
    assert code in REMOVED_CODES and code not in ERROR_CODES


def test_a_retired_code_has_no_live_entry_in_the_catalogue():
    text = _ERROR_CODES_MD.read_text(encoding="utf-8")
    live = [code for code in M8_RETIRED if re.search(rf"^### {code} [A-Z_]+$", text, re.M)]
    assert live == []


def test_m8_codes_are_registered_with_their_names_and_none_is_a_removed_code():
    for code, name in M8_CODE_NAMES.items():
        assert ERROR_CODES.get(code) == name
    assert not set(M8_CODE_NAMES) & set(REMOVED_CODES)


def test_every_m8_code_is_emitted_or_listed_as_without_an_emitter():
    emitted: set[str] = set()
    for py_file in TOOLS_DIR.rglob("*.py"):
        if py_file != ERRORS_MODULE:
            emitted.update(CODE_LITERAL_RE.findall(py_file.read_text(encoding="utf-8")))
    unaccounted = set(M8_CODE_NAMES) - emitted - REGISTERED_WITHOUT_EMITTER
    assert not unaccounted, f"M8 codes with no emitter that are not listed: {sorted(unaccounted)}"
    assert not set(M8_CODE_NAMES) & REGISTERED_WITHOUT_EMITTER, "an M8 code is still listed as having no emitter; the catalogue says it is emitted"


def test_the_close_gate_entries_say_who_runs_the_gate():
    """E632 and E347 name the command that runs the gate now; the old sentence that no command runs it is gone."""
    text = _ERROR_CODES_MD.read_text(encoding="utf-8")
    assert "specdev milestone close" in _entry(text, "E632")
    assert "specdev milestone close" in _entry(text, "E347")
    assert "specdev verify attest" in _entry(text, "E347")


@pytest.mark.parametrize("path", [p for p in M8_COMMANDS])
def test_m8_commands_are_in_the_generated_list_and_the_reference(path):
    paths = [c["path"] for c in json.loads(_CLI_COMMANDS.read_text(encoding="utf-8"))["commands"]]
    assert path in paths
    reference = _REFERENCE_MD.read_text(encoding="utf-8")
    assert f"`specdev {path}" in reference, f"docs/developers/reference.md has no entry for `specdev {path}`"


def test_the_reference_milestone_state_block_shows_the_keys_the_command_prints():
    reference = _REFERENCE_MD.read_text(encoding="utf-8")
    block = reference[reference.index("#### `milestone-state`"):reference.index("### Version Update & Migration")]
    contract = re.search(r"\*\*Output contract\*\*[^`]*```json\n(.*?)```", block, re.S).group(1)
    for key in ('"milestone_id"', '"milestone"', '"groups"', '"group_id"', '"state"', '"blocking_amb_ids"', '"derived_phase_position"', '"blockers"'):
        assert key in contract, f"the output contract does not show {key}"
    for gone in ("blocking_amb_health", "fixtures_exercised", "|verified|"):
        assert gone not in contract, f"the output contract still shows {gone}"
    assert "not the `milestone` command group" in block


@pytest.mark.parametrize("marker", M8_CHANGELOG_MARKERS)
def test_changelog_md_and_yaml_carry_the_same_m8_entry(marker):
    plain = _normalised(marker)
    bullets, descriptions = _changelog_texts()
    md = next((b for b in bullets if plain in _normalised(b)), "")
    entry = next((d for d in descriptions if plain in _normalised(d)), "")
    assert md, f"changelog/v1.2.0.md has no bullet with {marker!r}"
    assert entry, f"changelog/v1.2.0.yaml has no change with {marker!r}"
    assert _normalised(md) == _normalised(entry)


def test_changelog_names_every_m8_code_retired_code_and_command():
    bullets, _ = _changelog_texts()
    text = " ".join(bullets)
    assert [code for code in (*M8_CODE_NAMES, *M8_RETIRED) if code not in text] == []
    assert [path for path in M8_COMMANDS if f"specdev {path}" not in text and f"specdev {path.split()[0]}" not in text] == []


def test_every_m8_changelog_entry_ends_with_a_command_a_reader_can_run():
    bullets, _ = _changelog_texts()
    for marker in M8_CHANGELOG_MARKERS:
        bullet = next(b for b in bullets if _normalised(marker) in _normalised(b))
        assert re.search(r"Shown by `[^`]+`\.$", bullet), f"the entry {marker!r} does not end with a command"


@pytest.mark.parametrize("wording", OLD_WORDINGS)
def test_no_text_file_keeps_a_wording_the_milestone_made_untrue(wording):
    hits = [path.name for path in _TEXT_FILES if wording in path.read_text(encoding="utf-8")]
    assert hits == [], f"{wording!r} is still in {hits}"
