"""Static contract of the four Trinity prompts on the 1.2.0 model (WI-M8-13, DEVSPEC-151, 230, 235, 242, 264).

The prompts are text an agent obeys: this file pins what they must not say any more (retired fields, codes and commands, a
direct write of a spec file), what they must say (the command that writes each artifact, the pack of each role, the action id
rule, the mark on every 16c rule that no tool enforces) and that every command form they give is one the parser has.  The
examples themselves are checked in ``tests/integration/test_prompt_output_examples.py``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.generation import prompt_schema_sync as sync
from unit.generation._contracts_support import _flags
from unit.graph._synth import run_cli

ROOT = Path(__file__).parents[3]
PROMPTS = ROOT / "prompts"
NAMES = {
    "anchor": "prompt_16_impl_context.md",
    "16a": "prompt_16a_impl_planner.md",
    "16b": "prompt_16b_impl_coder.md",
    "16c": "prompt_16c_impl_reviewer.md",
}
ALL = list(NAMES)


def _text(key: str) -> str:
    return (PROMPTS / NAMES[key]).read_text(encoding="utf-8")


@pytest.mark.parametrize("key", ALL)
@pytest.mark.parametrize(
    "phrase",
    ["update the relevant spec", "spec_mutations", "new_fixtures", "checklist_status", "commit_hash", "MUST also update", "Crucial Side Effect"],
)
def test_ticket_phrases_are_gone(key: str, phrase: str) -> None:
    assert phrase not in _text(key)


RETIRED_FIELDS = (
    "execution_results", "final_status", "evidence_binding", "critical_evidence", "fixture_status", "fr_coverage",
    "linked_test_expectation", "milestone_ref", "deferred_reason", "wont_do_reason", "fr_refs", "context_path",
    "implementation.status", "ci_status",
)
RETIRED_COMMANDS = ("specdev matrix", "trace_matrix", "forward-replay-check", "--with-replay", "step 13a")
RETIRED_CODES = ("E301", "E302", "E305", "E306", "E307", "W599", "W600", "W601")


@pytest.mark.parametrize("key", ALL)
def test_retired_fields_commands_and_codes_are_gone(key: str) -> None:
    text = _text(key)
    for name in (*RETIRED_FIELDS, *RETIRED_COMMANDS):
        assert name not in text, name
    for code in RETIRED_CODES:
        assert not re.search(rf"\b{code}\b", text), code


@pytest.mark.parametrize("key", ["anchor", "16a", "16b"])
def test_spec_ref_is_a_live_field_only_in_a_review_finding(key: str) -> None:
    assert "spec_ref" not in _text(key)


def test_spec_ref_in_16c_is_only_the_field_of_a_review_finding() -> None:
    lines = [line for line in _text("16c").splitlines() if "spec_ref" in line]
    assert lines and all('"note"' in line and '"type": "code"' in line for line in lines)


@pytest.mark.parametrize("key", ALL)
def test_no_prompt_writes_a_spec_file_directly_or_runs_step_ready_for_16b_or_16c(key: str) -> None:
    text = _text(key)
    for sentence in ("directly to disk", "Write/update the artifact file", "Write the JSON artifact to `spec/", "Write the final JSON artifact"):
        assert sentence not in text, sentence
    assert not re.search(r"step ready 16[bc]", text)


def test_each_artifact_is_written_by_its_command() -> None:
    assert "specdev step create 16 --from" in _text("anchor")
    assert "specdev json insert --step 16 .plan.milestone_index" in _text("anchor")
    assert "specdev step create 16a <batch> --from" in _text("16a")
    assert "specdev plan record" in _text("16b") and "specdev verify run" in _text("16b")
    assert "specdev review record" in _text("16c")
    for form in ("json patch <plan> '.execution.emergent_ambiguities' '[<item>]'", "json insert <plan> '.execution.emergent_ambiguities' '<item>'"):
        assert form in _text("16b")
    assert "json patch <plan> '.execution' " not in _text("16b")


@pytest.mark.parametrize(("key", "role"), [("16a", "16a"), ("16b", "16b"), ("16c", "16c")])
def test_each_prompt_names_the_pack_of_its_role(key: str, role: str) -> None:
    assert f"specdev trace --recipe {role} " in _text(key)


def test_the_anchor_row_is_pending_and_status_is_the_milestone_commands() -> None:
    text = _text("anchor")
    assert "specdev milestone start|defer|close" in text
    block = json.loads(re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)[-1])
    assert {row["status"] for row in block["plan"]["milestone_index"]} == {"pending"}
    assert all("close" not in row and "deferral_reason" not in row for row in block["plan"]["milestone_index"])
    assert "milestone_ref" not in text


def test_16c_never_writes_a_milestone_status() -> None:
    text = _text("16c")
    assert "never written by this step" in text
    assert not re.search(r"milestone_index\[.*\]\.status", text)


# --- the 16c rules that no tool enforces -------------------------------------------------------------------------


REVIEWER_JUDGEMENT = (
    "Blocking finding forbids `verified`",
    "Security RED forbids `verified`",
    "Rating evidence (ENF-140)",
    "Remediation for every finding (ENF-144)",
    "Rating bounds",
    "Vague findings",
    "Per-item verdicts",
)


def _judgement_rules() -> list[str]:
    section = _text("16c").split("### Reviewer judgement", 1)[1].split("\n## ", 1)[0]
    return [line for line in section.splitlines() if re.match(r"^\d+\.\s", line)]


def test_every_16c_rule_without_an_enforcer_carries_the_reviewer_judgement_mark() -> None:
    rules = _judgement_rules()
    assert len(rules) == len(REVIEWER_JUDGEMENT)
    for rule, name in zip(rules, REVIEWER_JUDGEMENT, strict=True):
        assert f"**{name}**" in rule and "reviewer judgement" in rule, rule
    assert "`review record` checks input only" in _text("16c")


def test_16c_scale_is_marked_reviewer_judgement() -> None:
    assert "(reviewer judgement — rating bounds)" in _text("16c")


# --- the examples carry the new shape ------------------------------------------------------------------------------


def _examples() -> list[tuple[str, dict[str, Any]]]:
    found: list[tuple[str, dict[str, Any]]] = []
    for key in ("16a", "16b", "16c"):
        text = _text(key)
        section = text[sync.OUTPUT_CONTRACT_HEADING_RE.search(text).end():]
        found.extend((key, json.loads(m.group(1))) for m in sync.FENCED_JSON_RE.finditer(section))
    return found


def test_every_example_action_has_an_id_unique_within_its_item() -> None:
    seen = 0
    for key, example in _examples():
        for item in example["plan"]["spec_alignment"]["checklist"]:
            ids = [action.get("id") for action in item["implementation"]["actions"]]
            assert all(isinstance(i, str) and re.fullmatch(r"a[0-9]{2,}", i) for i in ids), (key, ids)
            assert len(set(ids)) == len(ids), (key, ids)
            seen += len(ids)
    assert seen >= 6


def test_examples_hold_no_field_the_1_2_0_plan_dropped() -> None:
    for key, example in _examples():
        flat = json.dumps(example)
        for name in ('"evidence"', "execution_results", "fixture_status", "semantic_review", "delivery_status", "final_status"):
            assert name not in flat, (key, name)
        for item in example.get("execution", {}).get("emergent_ambiguities", []):
            assert set(item) <= {"id", "description", "about", "decision", "proposed_assumption", "missing_kind"}, item


# --- every command form a prompt names is one the parser has ----------------------------------------------------


@pytest.mark.parametrize(
    ("key", "command"),
    [("16a", "step create"), ("anchor", "step create"), ("16b", "plan record"), ("16b", "verify run"), ("16b", "verify bind"), ("16a", "verify bind"),
     ("16a", "plan record"), ("16c", "review record"), ("16c", "verify run"), ("16c", "trace")],
)
def test_every_flag_a_prompt_gives_a_command_is_one_its_parser_has(key: str, command: str) -> None:
    flags = _flags(_text(key), command)
    code, help_text = run_cli(*command.split(), "--help")
    assert code == 0
    for flag in flags:
        assert flag in help_text, (key, command, flag)


def test_the_16c_verdicts_and_the_ratings_are_the_ones_the_command_takes() -> None:
    text = _text("16c")
    assert "--verdict verified|needs_work|blocked|deferred" in text
    code, help_text = run_cli("review", "record", "--help")
    assert code == 0 and "verified, needs_work, blocked or" in " ".join(help_text.split())
    for rating in ("spec_completeness", "code_quality", "tests_completeness", "docs_completeness", "metadata_usage"):
        assert rating in text


# --- the gates the prompts rest on ---------------------------------------------------------------------------------


def test_prompt_sync_and_extraction_intent_check_still_pass() -> None:
    for command in ("prompt-sync", "extraction-intent-check"):
        code, out = run_cli(command, "--repo-root", str(ROOT))
        assert code == 0 and "OK" in out, (command, out)


def test_the_substep_domains_name_no_field_the_plan_dropped() -> None:
    domains = sync._SUBSTEP_EXPECTED_KEYS
    assert "evidence" not in domains["16b"]
    assert domains["16b"] == {"execution", "implementation"}
