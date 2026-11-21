"""Static contract of the trinity skill on the 1.2.0 model (WI-M8-14, rulings L1, L8, L11, L12, L15 as corrected).

The skill is the orchestration an operator's session follows through a milestone, so this file pins what must not drift: the
retired names that are gone, the command forms it names and their order in a milestone's life, the sentences that leave the
four person decisions to a person, the dispatch keys it shares with the agent files, the file names it shares with
``milestone-state`` and the prompts, and the codes of its refusal table.  The last tests do what the skill text tells a session
to do, on a git copy of the worked example.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from specdev_tools.core.errors import ERROR_CODES
from unit.generation.test_trinity_contracts_agents import _flags, _item_with_findings
from unit.graph._synth import run_cli
from unit.trace._lock_support import git_copy_of_example, run_on_example

ROOT = Path(__file__).parents[3]
SKILL_FILE = ROOT / ".claude" / "skills" / "specdev-trinity" / "SKILL.md"
STEP_SKILL_FILE = ROOT / ".claude" / "skills" / "specdev-step" / "SKILL.md"
AGENTS = ROOT / ".claude" / "agents"
PROMPTS = ROOT / "prompts"
ITEM = "PWRESET_CONFIRM_EXPIRED_01"
MILESTONE = "ms-account-recovery"
BATCH = "account_recovery"
MAX_LINES = 600  # the skill is loaded whole into an operator's session each time it runs


def _skill() -> str:
    return SKILL_FILE.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return " ".join(text.split())


def _agent(name: str) -> str:
    return (AGENTS / name).read_text(encoding="utf-8")


def _prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """The text from the line that starts with *heading* up to the next heading of the same or a higher level."""
    level = len(heading) - len(heading.lstrip("#"))
    lines = text.splitlines()
    start = next(number for number, line in enumerate(lines) if line.startswith(heading))
    end = len(lines)
    for number in range(start + 1, len(lines)):
        match = re.match(r"(#+) ", lines[number])
        if match and len(match.group(1)) <= level:
            end = number
            break
    return "\n".join(lines[start:end])


def _in_order(text: str, fragments: list[str]) -> None:
    position = -1
    for fragment in fragments:
        found = text.find(fragment, position + 1)
        assert found > position, f"{fragment!r} is missing or out of order"
        position = found


# --- what the skill must not say any more ---------------------------------------------------------------------------------

RETIRED_FIELDS = (
    "execution_results", "final_status", "evidence_binding", "critical_evidence", "fixture_status", "fr_coverage",
    "checklist_status", "blocking_amb_health", "fixtures_exercised", "spec_ref", "milestone_ref", "implementation.status",
    "trinity_", "verified_at", "linked_test_expectation",
)
RETIRED_CODES = ("E301", "E302", "E305", "E306", "E307", "W599", "W600", "W601")


def test_retired_fields_commands_codes_and_citations_are_gone() -> None:
    text = _skill()
    for name in RETIRED_FIELDS:
        assert name not in text, name
    for code in RETIRED_CODES:
        assert not re.search(rf"\b{code}\b", text), code
    for phrase in ("write directly", "with_replay", "--with-replay", "specdev matrix", "forward-replay", "step 13a", "canon-accept"):
        assert phrase not in text, phrase
    assert not re.search(r"K_agentification|\bK1\b|\bK2\b", text)


def test_the_skill_writes_no_spec_file_and_no_status() -> None:
    text = _skill()
    assert not re.search(r"specdev json patch\s+spec/", text), "no json patch of a spec file"
    assert not re.search(r"status\s*=\s*\"done\"", text), "no status patch"
    assert "Update anchor and roadmap" not in text, "the Y/N anchor prompt is gone"
    assert not re.search(r"step ready 16[bc]", text), "L8: the skill never runs step ready 16b or 16c"
    assert "specdev step ready 16a" in text
    assert "Does not write a file under `spec/` by hand" in _flat(text)


def test_no_ask_question_is_asked_in_the_close_sequence() -> None:
    close = _section(_skill(), "### After convergence")
    assert "AskUserQuestion" not in close
    assert "the person" in close and "explicit yes" in close


def test_the_skill_stays_small_enough_to_load_whole() -> None:
    assert len(_skill().splitlines()) <= MAX_LINES


# --- the forms it names, and their order ----------------------------------------------------------------------------------


def test_it_names_every_form_of_the_loop() -> None:
    text = _skill()
    for form in (
        "specdev trace --recipe 16a <task-id>", "specdev trace --recipe 16b <plan-item-id>", "specdev trace --recipe 16c <milestone-id>",
        "specdev milestone-state --batch-id <batch_id>", "specdev step ready 16a", "specdev step create 16a <batch_id> --from",
        "specdev milestone start <ms-id>", "specdev plan record", "specdev verify run --milestone <ms-id> --stage ci",
        "specdev verify attest <node-id>...", "specdev verify bind <verifier-id> --command CMD --guard REGEX",
        "specdev review record <ms-id> --verdict verified --findings-file", "specdev status --milestone <ms-id>",
        "specdev milestone sign-off <ms-id>", "specdev milestone close <ms-id> --check", "specdev milestone close <ms-id>`",
        "specdev milestone defer <ms-id> --reason", "specdev plan record --prune <ms-id>", "release",
    ):
        assert form in text, form


def test_a_milestone_life_names_its_commands_in_order() -> None:
    life = _section(_skill(), "## The life of a milestone, in order")
    _in_order(life, [
        "specdev milestone-state --batch-id <batch_id>", "specdev step ready 16a", "specdev step create 16a <batch_id> --from <draft>",
        "specdev milestone start <ms-id>", "specdev plan record", "specdev verify run",
        "specdev verify run --milestone <ms-id> --stage ci", "specdev verify attest", "specdev review record <ms-id> --verdict verified",
        "specdev status --milestone <ms-id>", "specdev milestone sign-off <ms-id>", "specdev milestone close <ms-id> --check",
        "specdev milestone close <ms-id>`",
    ])


def test_the_close_sequence_runs_the_proof_before_the_review_and_the_sign_off_before_the_close() -> None:
    close = _section(_skill(), "### After convergence")
    _in_order(close, [
        "must be committed", "specdev verify run --milestone <ms-id> --stage ci", "specdev verify attest <node-id>...",
        "specdev review record <ms-id> --verdict verified", "specdev status --milestone <ms-id>` again",
        "specdev milestone sign-off <ms-id>", "specdev milestone close <ms-id> --check", "specdev milestone close <ms-id>`",
    ])
    assert "The skill never commits" in _flat(close)
    assert "A `FAIL` line (exit 1) is not a findings file: send it back to the milestone-wide review loop" in _flat(close)
    assert "specdev verify run --milestone <ms-id> --stage ci --no-record" in _flat(close)
    assert "specdev verify run --milestone <milestone-id> --stage ci --no-record" in _agent("specdev-trinity-reviewer.md")


def test_the_plan_gate_starts_the_milestone_and_the_plan_phase_creates_a_missing_plan_by_the_command() -> None:
    plan = _section(_skill(), "## --phase plan (default)")
    assert "specdev step create 16a <batch_id> --from .specdev/drafts/plan_<batch_id>.json" in plan
    assert "Never write a file under `spec/` yourself" in _flat(plan)
    assert "E767" in plan and "specdev step create 16" in plan and "specdev json insert --step 16" in plan
    _in_order(plan, ["specdev step ready 16a", "specdev step create 16a", "### Step 2", "### Step 3", "specdev milestone start <ms-id>"])
    assert "E800" in plan


def test_the_re_plan_rule_names_the_two_attests_by_what_they_do() -> None:
    plan = _flat(_section(_skill(), "## --phase plan (default)"))
    assert "`specdev attest <item-id> --yes`" in plan
    assert "`specdev plan record --prune <ms-id>` only when `specdev spec-check` reports" in plan
    assert "E700" in plan


# --- who decides ----------------------------------------------------------------------------------------------------------


def test_the_four_person_decisions_are_left_to_a_person() -> None:
    text = _flat(_section(_skill(), "## Who decides what"))
    for sentence in (
        "A **person** decides:",
        "**sign-off** (`specdev milestone sign-off <ms-id>`) and **defer**",
        "`specdev verify attest <node-id>...`; not `specdev attest`, which re-accepts links",
        "**release**, the cut (`specdev release --tag <name>`): not a step of a milestone's loop; the person runs it and the skill never does.",
        "Before each of them: show `specdev status --milestone <ms-id>` first, ask the person in the conversation, and run the command only on an explicit yes.",
        "that prompt is the person's and the skill never answers it",
        "The skill never runs one of these commands on its own judgement.",
    ):
        assert sentence in text, sentence
    code, out = run_cli("release", "--help")
    assert code == 0 and "--tag" in out, "`release --tag` is the command the skill names"


def test_the_skill_asks_before_a_manual_record_and_before_a_manual_attestation() -> None:
    text = _flat(_skill())
    assert "`specdev plan record <group_id>/<action-id> --outcome done --note \"operator confirmed\"`" in text
    assert "Ask the person whether each was carried out" in text
    assert "ask the person whether it was carried out and, for each yes, run `specdev verify attest <node-id>...`" in text
    assert "Ask the person for the sign-off" in text


def test_the_skill_stops_on_a_plan_without_a_milestone_key() -> None:
    text = _flat(_section(_skill(), "## The milestone id"))
    assert "read the `milestone` key ONCE" in text
    assert "`milestone_id` echoes the batch id and is not a milestone id" in text
    assert 'If `milestone` is `null`, the plan has no `milestone` key' in text
    assert 'E803 no plan names milestone <ms-id>: add it with `specdev json patch <plan file> \'.milestone\' \'"<milestone-id>"\'` (the plan has no `milestone` key)' in text
    assert "the migration which writes the key may not be in this toolkit version yet" in text


# --- the skill and the agent files -----------------------------------------------------------------------------------------


def _keys(block_pattern: str) -> set[str]:
    match = re.search(block_pattern, _skill(), re.S)
    assert match, block_pattern
    return set(re.findall(r'"(\w+)":', match.group(0)))


def _agent_example_keys(agent: str, anchor: str) -> set[str]:
    text = _agent(agent)
    start = text.index(anchor)
    block = re.search(r"\{.*?\n\}", text[start:], re.S)
    assert block
    return set(re.findall(r'^  "(\w+)":', block.group(0), re.M))


def test_the_impl_dispatches_carry_the_keys_the_impl_agent_reads() -> None:
    execute = _keys(r'\{\s*"mode": "execute".*?\}')
    fix = _keys(r'\{\s*"mode": "fix".*?\}')
    milestone_fix = _keys(r'\{\s*"mode": "milestone_fix".*?\}')
    agent = _agent("specdev-trinity-impl.md")
    assert execute == {"mode", "plan_path", "group_id", "batch_id"}
    assert fix == {"mode", "findings_path", "group_id", "batch_id"}
    assert milestone_fix == {"mode", "findings_path", "milestone_id", "batch_id", "plan_path"}
    assert 'Dispatcher includes `mode: "execute"` | `"fix"` | `"milestone_fix"` as the first line' in agent
    assert re.search(r'"milestone_id": "ms-account-recovery"', agent), "the milestone_fix return carries the milestone id"


def test_the_impl_return_keys_are_the_ones_the_agent_returns() -> None:
    skill, agent = _skill(), _agent("specdev-trinity-impl.md")
    for key in ("recorded", "awaiting_confirmation", "skipped_at_deploy", "ambiguities_raised", "errors_remaining", "gate_status"):
        assert f'"{key}"' in agent, key
        assert f"`{key}`" in skill, key
    assert "an action that names a verifier is proven by `specdev verify run`, not recorded" in _flat(skill)
    assert "`manual_verification`: do not record it; list it in `awaiting_confirmation`" in _flat(agent)


def test_the_reviewer_dispatches_carry_the_keys_the_reviewer_agent_reads() -> None:
    group = _keys(r'\{\s*"milestone_id": "<ms-id>",\s*"batch_id": "<batch_id>",\s*"group_id".*?\}')
    milestone = _keys(r'\{\s*"milestone_id": "<ms-id>",\s*"batch_id": "<batch_id>",\s*"scope_kind": "code_phase_milestone".*?\}')
    agent_keys = _agent_example_keys("specdev-trinity-reviewer.md", "## Dispatch input")
    assert group == agent_keys
    assert milestone == agent_keys - {"group_id"}
    agent = _flat(_agent("specdev-trinity-reviewer.md"))
    assert "`milestone_id` is the roadmap milestone id (the `milestone` key of `specdev milestone-state`)" in agent
    assert "a plan-item id for `code_phase_group`, the milestone id for `code_phase_milestone`" in agent
    skill = _skill()
    assert '"scope": "<ms-id>"' in skill and '"scope": "<group_id>"' in skill


def test_the_plan_review_dispatch_has_no_retired_flag_and_the_scope_dispatch_matches_the_scope_agent() -> None:
    skill = _skill()
    assert '"flags": { "with_backlog": false }' in skill
    reviewer = _agent("specdev-reviewer.md")
    assert '"with_backlog": false' in reviewer and "with_replay" not in reviewer
    scope = _agent("specdev-scope.md")
    assert '"mode": "milestone_state"' in scope and '"batch_id": "<batch-id>"' in scope
    assert '"milestone": "<the plan\'s file-level milestone key, or null>"' in scope
    assert '{ "mode": "milestone_state", "batch_id": "<batch_id>" }' in skill


def test_the_findings_file_names_agree_with_the_reviewer_and_with_milestone_state() -> None:
    skill = _skill()
    assert ".specdev/findings/findings_<ms-id>_<round>_r1.json" in skill
    assert ".specdev/findings/findings_<batch_id>_review_<round>.json" in skill
    assert ".specdev/findings/findings_<scope>_<round>_r<reviewer_id>.json" in _agent("specdev-trinity-reviewer.md")
    impl = _agent("specdev-trinity-impl.md")  # milestone_fix reads the milestone-wide file under the one name the skill passes
    assert ".specdev/findings/findings_<batch_id>_review_<round>.json" in impl and "findings_<milestone_id>_review" not in impl
    state = (ROOT / "tools" / "specdev_tools" / "context" / "milestone_state.py").read_text(encoding="utf-8")
    assert 'f"findings_{batch_id}_review_*"' in state
    assert 'f"findings_{group_id}_*"' in state
    assert ".specdev/findings/findings_<group_id>_<round>_r1.json" in skill


# --- the skill and the prompts ------------------------------------------------------------------------------------------


def test_the_skill_and_the_prompts_give_the_forms_the_same_way() -> None:
    skill = _skill().replace("<ms-id>", "<milestone-id>").replace("<batch_id>", "<batch>")
    p16a, p16b, p16c, p16 = (_prompt(f"prompt_{n}.md") for n in ("16a_impl_planner", "16b_impl_coder", "16c_impl_reviewer", "16_impl_context"))
    assert "specdev step create 16a <batch> --from .specdev/drafts/plan_<batch>.json" in p16a and "specdev step create 16a <batch> --from .specdev/drafts/plan_<batch>.json" in skill
    assert "specdev step create 16 --from .specdev/drafts/step_16.json" in p16 and "specdev json insert --step 16 .plan.milestone_index '<row>'" in p16
    assert "specdev json insert --step 16 .plan.milestone_index '<row>'" in skill
    assert '--note "operator confirmed"' in p16b and '--note "operator confirmed"' in skill
    assert "specdev plan record --prune <milestone-id>" in p16b and "specdev plan record --prune <milestone-id>" in skill
    assert "specdev review record <milestone-id> --verdict" in p16c and "specdev review record <milestone-id> --verdict verified" in skill
    assert "specdev verify run --milestone <milestone-id> --stage ci" in p16c and "specdev verify run --milestone <milestone-id> --stage ci" in skill
    assert '"$schema": "vc:infra:findings"' in p16c and '"$schema": "vc:infra:findings"' in skill
    assert "`specdev milestone start|defer|close`" in p16 or "specdev milestone start|defer|close" in p16


def test_the_step_skill_names_the_route_to_a_plan_in_one_sentence() -> None:
    text = _flat(STEP_SKILL_FILE.read_text(encoding="utf-8"))
    assert "a milestone's plan is created by `/specdev-trinity --phase plan` with `specdev step create 16a <batch> --from <draft>`" in text
    assert "`step create` writes steps 00 to 15 and refuses the rest" not in text
    assert "NOT for step 16 trinity phases" in text


# --- every command form the skill names is one the parser has ----------------------------------------------------------


COMMANDS = (
    "milestone start", "milestone defer", "milestone sign-off", "milestone close", "plan record", "review record",
    "verify run", "verify bind", "verify attest", "status", "step ready", "step create", "trace", "attest", "stale",
    "spec-check", "validate", "milestone-state",
)


@pytest.mark.parametrize("command", COMMANDS)
def test_every_flag_the_skill_gives_a_command_is_one_its_parser_has(command: str) -> None:
    flags = _flags(_skill(), command)
    code, help_text = run_cli(*command.split(), "--help")
    assert code == 0, command
    for flag in flags:
        assert flag in help_text, (command, flag)


def test_the_skill_gives_the_milestone_commands_their_flags() -> None:
    skill = _skill()
    assert _flags(skill, "milestone close") == {"--check"}
    assert _flags(skill, "milestone defer") == {"--reason"}
    assert {"--outcome", "--note", "--prune"} <= _flags(skill, "plan record")
    assert {"--verdict", "--findings-file"} <= _flags(skill, "review record")
    assert {"--milestone", "--stage"} <= _flags(skill, "verify run")
    code, help_text = run_cli("milestone", "close", "--help")
    assert code == 0 and "--dry-run" not in help_text and not re.search(r"milestone close[^\n]*--dry-run", skill)


# --- the refusal table ------------------------------------------------------------------------------------------------------


def _table_codes() -> set[str]:
    table = _section(_skill(), "## When a command refuses")
    return set(re.findall(r"^\| (E\d{3})", table, re.M))


def test_every_code_in_the_refusal_table_is_registered() -> None:
    codes = _table_codes()
    assert {"E800", "E803", "E810", "E811", "E812", "E813", "E814", "E746", "E632", "E763", "E820", "E821", "E822", "E823", "E767"} <= codes
    for code in codes:
        assert code in ERROR_CODES, code
        assert code not in RETIRED_CODES


# --- what the skill text tells a session to do, done on a git copy of the worked example ---------------------------------


def test_the_close_gate_findings_of_the_example_are_all_in_the_refusal_table(tmp_path: Path) -> None:
    host = git_copy_of_example(tmp_path / "host")
    code, out = run_on_example(host, "milestone", "close", MILESTONE, "--check")
    assert code == 1 and f"milestone {MILESTONE} cannot be closed" in out, out
    printed = set(re.findall(r"^\s+(E\d{3}) ", out, re.M))
    assert {"E810", "E811", "E812", "E813", "E814"} <= printed, printed
    assert printed <= _table_codes(), printed - _table_codes()
    code, status = run_on_example(host, "status", "--milestone", MILESTONE)
    assert code == 0 and status.splitlines()[0] == f"milestone {MILESTONE}: in_progress", status


def test_the_milestone_id_is_read_from_milestone_state_and_a_batch_id_is_not_one(tmp_path: Path) -> None:
    host = git_copy_of_example(tmp_path / "host")
    code, out = run_on_example(host, "milestone-state", "--batch-id", BATCH)
    state = json.loads(out)
    assert code == 0 and state["milestone"] == MILESTONE and state["milestone_id"] == BATCH, out
    code, out = run_on_example(host, "milestone", "start", BATCH)
    assert code == 1 and out.startswith(f"E803 {BATCH} is a batch id"), out
    plan = host / "spec" / "impl_context" / f"ms_{BATCH}_plan.json"
    document = json.loads(plan.read_text(encoding="utf-8"))
    del document["milestone"]
    plan.write_text(json.dumps(document), encoding="utf-8")
    code, out = run_on_example(host, "milestone-state", "--batch-id", BATCH)
    assert code == 0 and json.loads(out)["milestone"] is None, out
    code, out = run_on_example(host, "status", "--milestone", MILESTONE)
    assert code == 1 and out.startswith("E803 ") and "add it with `specdev json patch <plan file>" in out, out


def _write(host: Path, name: str, document: dict) -> Path:
    return Path(_item_with_findings(host, name, document))


def _converged(scope: str, round_number: int = 1) -> dict:
    return {"$schema": "vc:infra:findings", "round": round_number, "scope": scope, "generated_at": 1795305600, "findings": []}


def test_the_loop_files_move_milestone_state_as_the_skill_says_and_review_record_takes_the_converged_one(tmp_path: Path) -> None:
    host = git_copy_of_example(tmp_path / "host")
    # impl phase: the reviewer's per-item file, copied to the canonical name
    _write(host, f"findings_{ITEM}_1_r1.json", _converged(ITEM))
    _write(host, f"findings_{ITEM}_1.json", _converged(ITEM))
    code, out = run_on_example(host, "milestone-state", "--batch-id", BATCH)
    state = json.loads(out)
    assert code == 0 and state["groups"][0]["state"] == "code_converged" and state["derived_phase_position"] == "impl_complete", out
    # review phase: the reviewer writes findings_<ms-id>_<round>_r1.json; the skill copies it to the name milestone-state reads
    reviewer_file = _write(host, f"findings_{MILESTONE}_1_r1.json", _converged(MILESTONE))
    converged = host / ".specdev" / "findings" / f"findings_{BATCH}_review_1.json"
    shutil.copyfile(reviewer_file, converged)
    code, out = run_on_example(host, "milestone-state", "--batch-id", BATCH)
    assert code == 0 and json.loads(out)["derived_phase_position"] == "review_complete", out
    code, out = run_cli("validate", str(converged), "--repo-root", str(ROOT))
    assert code == 0 and "OK" in out, out
    code, out = run_on_example(host, "review", "record", MILESTONE, "--verdict", "verified", "--findings-file", str(converged))
    assert code == 0 and "verdict verified, 0 finding(s)" in out, out
    code, out = run_on_example(host, "status", "--milestone", MILESTONE)
    assert code == 0 and "E813" not in out, "the review is recorded: E813 no longer owed"


def test_the_jq_merge_the_skill_gives_produces_a_file_that_validates(tmp_path: Path) -> None:
    if shutil.which("jq") is None:
        pytest.skip("jq is not installed")
    match = re.search(r"jq -s '(.*?)' \\\n", _skill())
    assert match, "the merge one-liner is in the skill"
    expression = match.group(1)
    assert '"$schema": "vc:infra:findings"' in expression
    host = git_copy_of_example(tmp_path / "host")
    finding = {"kind": "gap", "location": "spec/impl_context/ms_account_recovery_plan.json", "message": "example finding", "severity": "P2"}
    for reviewer in ("r1", "r2"):
        document = _converged("ms-account_recovery-plan") | {"findings": [finding | {"signature": f"sig-{reviewer}"}]}
        _write(host, f"findings_ms-account_recovery-plan_1_{reviewer}.json", document)
    folder = host / ".specdev" / "findings"
    merged = folder / "findings_ms-account_recovery-plan_1.json"
    inputs = sorted(str(path) for path in folder.glob("findings_ms-account_recovery-plan_1_r*.json"))
    done = subprocess.run(["jq", "-s", expression, *inputs], capture_output=True, text=True, check=True)
    merged.write_text(done.stdout, encoding="utf-8")
    assert len(json.loads(done.stdout)["findings"]) == 2
    code, out = run_cli("validate", str(merged), "--repo-root", str(ROOT))
    assert code == 0 and "OK" in out, out


def test_a_manual_action_is_recorded_after_the_person_confirms_and_a_verifier_action_is_not(tmp_path: Path) -> None:
    host = git_copy_of_example(tmp_path / "host")
    action = {"id": "a02", "type": "manual_verification", "target": "confirm endpoint", "description": "A person tries an expired link in staging."}
    code, out = run_on_example(host, "json", "insert", "--id", ITEM, ".implementation.actions", json.dumps(action))
    assert code == 0, out
    code, out = run_on_example(host, "plan", "record", f"{ITEM}/a02", "--outcome", "done", "--note", "operator confirmed")
    assert code == 0 and "recorded rec-0001" in out, out
    verifier = {"id": "a03", "type": "run_command", "command": "npx vitest run tests/contract/password-reset-confirm.test.ts -t \"expired token\"", "description": "Run the expired token test."}
    code, out = run_on_example(host, "json", "insert", "--id", ITEM, ".implementation.actions", json.dumps(verifier))
    assert code == 0, out
    code, out = run_on_example(host, "plan", "record", f"{ITEM}/a03", "--outcome", "done")
    assert code == 1 and out.startswith("E822 "), out


def test_the_milestone_lifecycle_commands_refuse_as_the_skill_table_says(tmp_path: Path) -> None:
    host = git_copy_of_example(tmp_path / "host")
    code, out = run_on_example(host, "milestone", "start", "ms-nope")
    assert code == 1 and out.startswith("E800 "), out
    code, out = run_on_example(host, "milestone", "defer", MILESTONE)
    assert code == 1 and out.startswith("E802 "), out
    code, out = run_on_example(host, "plan", "record", f"{ITEM}/a09", "--outcome", "done")
    assert code == 1 and out.startswith("E821 "), out
    code, out = run_on_example(host, "milestone", "start", MILESTONE)
    assert code == 0 and "already in progress" in out, out
