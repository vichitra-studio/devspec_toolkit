"""Static contract of the two trinity agent definitions on the 1.2.0 model (WI-M8-15, ruling L12, L15 as corrected, S-012).

The agents are text a model obeys: this file pins what they must not say any more (retired fields and codes, a write of a spec
file, a seed read, hash and timestamp checks of fields a command now writes, the K citations), what they must say (the
allow-list of the impl agent, the command that writes each artifact, the two open-item forms, the `$schema` of a findings file)
and that every command form they give is one the parser has and one the prompts give the same way.  The last tests do what
the agent text tells an agent to do, on a git copy of the worked example.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from unit.generation._contracts_support import _flags, _item_with_findings
from unit.graph._synth import run_cli
from unit.trace._lock_support import git_copy_of_example, run_on_example

ROOT = Path(__file__).parents[3]
AGENTS = ROOT / ".claude" / "agents"
PROMPTS = ROOT / "prompts"
FILES = {"impl": "specdev-trinity-impl.md", "reviewer": "specdev-trinity-reviewer.md"}
ALL = list(FILES)


def _text(key: str) -> str:
    return (AGENTS / FILES[key]).read_text(encoding="utf-8")


def _prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


RETIRED_FIELDS = (
    "execution_results", "final_status", "evidence_binding", "critical_evidence", "fixture_status", "fr_coverage",
    "checklist_status", "blocking_amb_health", "fixtures_exercised", "spec_ref", "linked_test_expectation", "milestone_ref",
    "implementation.status", "trinity_execution", "trinity_review", "reactivation_condition", "impact_routes",
)
RETIRED_CODES = ("E301", "E302", "E305", "E306", "E307", "W599", "W600", "W601")
RETIRED_COMMANDS = ("specdev matrix", "trace_matrix", "forward-replay", "--with-replay", "step 13a", "canon-accept")


@pytest.mark.parametrize("key", ALL)
def test_retired_fields_commands_and_codes_are_gone(key: str) -> None:
    text = _text(key)
    for name in (*RETIRED_FIELDS, *RETIRED_COMMANDS):
        assert name not in text, name
    for code in RETIRED_CODES:
        assert not re.search(rf"\b{code}\b", text), code


@pytest.mark.parametrize("key", ALL)
def test_seeds_hashes_timestamps_and_citations_are_gone(key: str) -> None:
    text = _text(key)
    for name in ("seed_manifest", "seed-grounding", "sha256sum", "T00:00:00Z", "K_agentification", "global_seed_order"):
        assert name not in text, name
    for token in (r"\bK1\b", r"\bK2\b", r"\bE3\b", r"\bE4\b"):
        assert not re.search(token, text), token
    assert "timestamp validity" not in text.lower()


@pytest.mark.parametrize("key", ALL)
def test_no_agent_tells_an_agent_to_run_step_ready_for_16b_or_16c(key: str) -> None:
    assert not re.search(r"step ready 16[bc]", _text(key))


@pytest.mark.parametrize("key", ALL)
def test_no_open_item_carries_a_severity_and_no_example_names_a_plan_item_in_about(key: str) -> None:
    text = _text(key)
    assert '"severity": "medium"' not in text and '"severity": "low"' not in text
    for about in re.findall(r'"about": \[([^\]]*)\]', text):
        assert not re.search(r'"[A-Z][A-Z0-9_]+_\d+"', about), about


# --- who writes what -----------------------------------------------------------------------------------------------


def test_the_impl_agent_has_the_allow_list_once() -> None:
    text = " ".join(_text("impl").split())
    sentence = (
        "This agent writes code under `target_file_patterns`, runs `specdev plan record`, runs `specdev verify run`, and writes "
        "open items into the plan's `execution.emergent_ambiguities`; nothing else."
    )
    assert text.count(sentence) == 1


def test_the_impl_agent_writes_the_plan_only_through_plan_record_and_the_open_item_forms() -> None:
    text = _text("impl")
    for line in text.splitlines():
        if re.search(r"specdev json (patch|insert|delete)|specdev json patch\\\|insert", line):
            undo_of_e702 = "`specdev json delete --id <amb-id>` and write the item again" in line  # the one delete: it undoes an open item that names a plan item (spec-check reports E702)
            assert "'.execution.emergent_ambiguities'" in line or "never use `specdev json patch|insert|delete` on a spec file" in line or undo_of_e702, line
    assert "json patch <plan> '.execution' " not in text
    assert "Never patch `.execution` itself" in text
    assert "specdev plan record <group_id>/<action-id> --outcome done|failed|blocked [--note TEXT]" in text
    assert "specdev verify run <binding-id>" in text
    assert "E822" in text


def test_the_reviewer_agent_writes_only_a_findings_file_and_does_not_record_the_review() -> None:
    text = _text("reviewer")
    assert "does not run\n`specdev review record`: the skill records the review from the converged findings file" in text
    assert "Does not run `specdev plan record` or `specdev review record`" in text
    assert "No `specdev json patch/insert/delete`, no\n`specdev plan record`, no `specdev review record`" in text
    assert '"$schema": "vc:infra:findings"' in text
    assert text.count('"$schema": "vc:infra:findings"') >= 1


def test_each_agent_names_the_pack_of_its_role() -> None:
    assert "specdev trace --recipe 16b <group_id>" in _text("impl")
    assert "specdev trace --recipe 16b <group_id>" in _text("reviewer") and "specdev trace --recipe 16c <milestone_id>" in _text("reviewer")


# --- the open item: both forms, as the 16b prompt gives them -----------------------------------------------------


FORMS = (
    "specdev json read <plan> '.execution.emergent_ambiguities'",
    "specdev json patch <plan> '.execution.emergent_ambiguities' '[<item>]'",
    "specdev json insert <plan> '.execution.emergent_ambiguities' '<item>'",
)


def test_the_two_open_item_forms_are_the_ones_of_the_16b_prompt() -> None:
    for form in FORMS:
        assert form in _text("impl"), form
        assert form.replace("specdev json read", "json read") in _prompt("prompt_16b_impl_coder.md") or form in _prompt("prompt_16b_impl_coder.md")
    assert '{"id": "amb-new-<slug>", "description": "<what and why>", "about": ["<node-id>"]}' in _text("impl")


# --- every command form the agents give is one the parser has ------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "command"),
    [("impl", "plan record"), ("impl", "verify run"), ("impl", "trace"), ("impl", "spec-check"), ("reviewer", "verify run"),
     ("reviewer", "trace"), ("reviewer", "spec-check"), ("reviewer", "validate"), ("reviewer", "upstream-backlog")],
)
def test_every_flag_an_agent_gives_a_command_is_one_its_parser_has(key: str, command: str) -> None:
    flags = _flags(_text(key), command)
    assert flags
    code, help_text = run_cli(*command.split(), "--help")
    assert code == 0
    for flag in flags:
        assert flag in help_text, (key, command, flag)


def test_the_agents_and_the_prompts_give_plan_record_the_same_way() -> None:
    prompt = _prompt("prompt_16b_impl_coder.md")
    assert "specdev plan record <ITEM>/<action-id> --outcome done|failed|blocked [--note TEXT]" in prompt
    assert _flags(_text("impl"), "plan record") <= _flags(prompt, "plan record") | {"--repo-root", "--spec-root", "--git-root"}
    assert "`--note` is at most 200 characters" in prompt and "200-character `--note`" in _text("impl")


def test_the_reviewer_names_the_findings_rules_of_the_16c_prompt() -> None:
    reviewer, prompt = _text("reviewer"), _prompt("prompt_16c_impl_reviewer.md")
    for token in ("at most 600", "E823", "upstream_refs", "plan-item id"):
        assert token in reviewer, token
    assert "`\"$schema\": \"vc:infra:findings\"` is required" in prompt
    assert "--no-record" in reviewer
    code, help_text = run_cli("verify", "run", "--help")
    assert code == 0 and "--no-record" in help_text


def test_the_reviewer_does_not_claim_a_tool_enforces_the_judgement_rules() -> None:
    text = " ".join(_text("reviewer").split())
    assert "no tool enforces them and you never say one does" in text


# --- what the agent text tells an agent to do, done on a git copy of the worked example ------------------------


ITEM = "PWRESET_CONFIRM_EXPIRED_01"
MILESTONE = "ms-account-recovery"


def _plan_path(host: Path) -> str:
    return str(host / "spec" / "impl_context" / "ms_account_recovery_plan.json")


def _with_action_id(host: Path) -> None:
    code, out = run_on_example(host, "json", "patch", "--id", ITEM, ".implementation.actions[0].id", '"a01"')
    assert code == 0, out


def test_the_impl_text_records_an_action_and_writes_an_open_item_by_both_forms(tmp_path: Path) -> None:
    host = git_copy_of_example(tmp_path / "host")
    _with_action_id(host)
    plan = _plan_path(host)
    code, out = run_on_example(host, "plan", "record", f"{ITEM}/a01", "--outcome", "done", "--note", "Expired tokens rejected before the update.")
    assert code == 0 and "recorded rec-0001" in out, out
    code, out = run_cli("json", "read", plan, ".execution.emergent_ambiguities", "--repo-root", str(ROOT))
    assert code == 0 and out.strip() == "null", out
    first = {"id": "amb-new-expiry-clock", "description": "The handler has no stated clock source for the expiry.", "about": ["tc-confirm-expired-token"]}
    second = {"id": "amb-new-expiry-grace", "description": "Is a token at exactly 30 minutes expired?", "about": ["tc-confirm-expired-token"]}
    code, out = run_cli("json", "patch", plan, ".execution.emergent_ambiguities", json.dumps([first]), "--repo-root", str(ROOT))
    assert code == 0, out
    code, out = run_cli("json", "insert", plan, ".execution.emergent_ambiguities", json.dumps(second), "--repo-root", str(ROOT))
    assert code == 0, out
    execution = json.loads(Path(plan).read_text(encoding="utf-8"))["execution"]
    assert [item["id"] for item in execution["emergent_ambiguities"]] == ["amb-new-expiry-clock", "amb-new-expiry-grace"]
    assert [record["record_id"] for record in execution["records"]] == ["rec-0001"], "the open item forms left the record alone"


def test_the_reviewer_text_writes_a_findings_file_that_validates_and_review_record_accepts(tmp_path: Path) -> None:
    host = git_copy_of_example(tmp_path / "host")
    finding = {
        "kind": "bug", "location": "src/routes/password-resets/confirm.ts#L14", "signature": "expired-token-check-after-update",
        "message": "src/routes/password-resets/confirm.ts:14 checks the token age after the password update.", "severity": "P0",
        "evidence": ["npm run test:contract: FAILED expired token, expected 410, got 200"],
        "suggested_fix": "Move the age check before the update.", "upstream_refs": [ITEM],
    }
    document = {"$schema": "vc:infra:findings", "round": 1, "scope": ITEM, "generated_at": 1795305600, "findings": [finding]}
    path = _item_with_findings(host, f"findings_{ITEM}_1_rr1.json", document)
    code, out = run_cli("validate", path, "--repo-root", str(ROOT))
    assert code == 0 and "OK" in out, out
    code, out = run_on_example(host, "review", "record", MILESTONE, "--verdict", "needs_work", "--findings-file", path)
    assert code == 0 and "verdict needs_work, 1 finding(s)" in out, out
    without = {key: value for key, value in document.items() if key != "$schema"}
    bare = _item_with_findings(host, "findings_bare.json", without)
    code, out = run_cli("validate", bare, "--repo-root", str(ROOT))
    assert code != 0 and "E520" in out, out
    code, out = run_on_example(host, "review", "record", MILESTONE, "--verdict", "needs_work", "--findings-file", bare)
    assert code != 0 and "E823" in out, out
