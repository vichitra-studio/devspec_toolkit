"""The ``plan``, ``code-group`` and ``code-milestone`` kinds of ``specdev loop``, on the worked example's milestone."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from unit.loop.test_loop_commands import loop, review, run_json
from unit.trace._lock_support import git_copy_of_example, run_on_example

MS, ITEM, CODE = "ms-account-recovery", "PWRESET_CONFIRM_EXPIRED_01", "src/routes/password-resets/confirm.ts"


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return git_copy_of_example(tmp_path / "host")


def test_plan_run_reads_the_plan_items_and_the_plan_file(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "plan", MS, "--review-only")["run_id"]
    action = loop(host, "next", run_id)
    assert [e["agent"] for e in action["entries"]] == ["specdev-reviewer"]  # one reader for a plan
    run = run_json(host, run_id)
    assert run["state"]["dispatch"]["entries"][0]["nodes"] == [ITEM, "spec/impl_context/ms_account_recovery_plan.json"]
    assert run["meta"]["scope_label"] == f"{MS}-plan" and "prompt_16a" in " ".join(run["meta"]["contract"])
    review(host, run_id, action)
    assert loop(host, "next", run_id)["verdict"] == "CLEAN"


def test_plan_scope_refusals(host: Path) -> None:
    assert loop(host, "start", "--kind", "plan", "ms-none")["code"] == "E850"
    assert loop(host, "start", "--kind", "plan", MS, "--author")["code"] == "E850"  # the plan exists
    assert loop(host, "start", "--kind", "code-group", MS)["code"] == "E850"  # no item named
    assert loop(host, "start", "--kind", "code-group", f"{MS}/NO_SUCH_ITEM")["code"] == "E850"
    assert loop(host, "start", "--kind", "step", "04", "--execute")["code"] == "E850"
    assert loop(host, "start", "--kind", "code-milestone", MS, "--execute")["code"] == "E850"


def execute(host: Path, run_id: str, **outcome: Any) -> dict[str, Any]:
    action = loop(host, "next", run_id)
    assert [e["agent"] for e in action["entries"]] == ["specdev-trinity-impl"]
    assert f"{ITEM}/<action id>" in Path(action["entries"][0]["brief"]).read_text()
    (host / CODE).parent.mkdir(parents=True, exist_ok=True)
    (host / CODE).write_text("export function confirm() { /* rejects expired tokens */ }\n")
    Path(action["entries"][0]["expect"]).write_text(json.dumps({"result": "executed", "recorded": ["a01"], **outcome}))
    return loop(host, "next", run_id)


def test_code_group_executes_reviews_and_writes_the_file_milestone_state_reads(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "code-group", f"{MS}/{ITEM}", "--execute")["run_id"]
    round_one = execute(host, run_id)
    assert [e["agent"] for e in round_one["entries"]] == ["specdev-trinity-reviewer"]
    assert CODE in run_json(host, run_id)["state"]["dispatch"]["entries"][0]["nodes"]
    review(host, run_id, round_one)
    done = loop(host, "next", run_id)
    assert done["verdict"] == "CONVERGED"
    copy = Path(done["milestone_state_file"])
    assert copy.name == f"findings_{ITEM}_1.json" and json.loads(copy.read_text())["findings"] == []
    code, out = run_on_example(host, "milestone-state", "--batch-id", "account_recovery")
    assert ITEM in out and "code_converged" in out, out


def test_a_finding_outside_the_item_is_recorded_as_an_open_item_not_fixed(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "code-group", f"{MS}/{ITEM}", "--execute")["run_id"]
    round_one = execute(host, run_id)
    outside = {"kind": "gap", "location": "fr-password-reset", "severity": "P1", "message": "The requirement is silent on reuse.",
               "evidence_quotes": [{"source": "fr-password-reset", "text": "fr-password-reset"}]}
    review(host, run_id, round_one, [outside])
    fix = loop(host, "next", run_id)
    assert [e["agent"] for e in fix["entries"]] == ["specdev-trinity-impl"]
    assert "Record it as an open item of the plan" in Path(fix["entries"][0]["brief"]).read_text()
    assert run_json(host, run_id)["state"]["handoffs"] == []  # a code run has no handoffs


def test_manual_verification_is_asked_and_the_cap_of_a_code_run_is_asked(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "code-group", f"{MS}/{ITEM}", "--execute", "--cap", "1")["run_id"]
    ask = execute(host, run_id, awaiting_confirmation=["a09"])
    assert ask["type"] == "ask" and ask["questions"][0]["id"] == "a09"
    assert f"plan record {ITEM}/a09 --outcome done" in ask["questions"][0]["options"][0]["command"]
    answers = Path(ask["answers_path"])
    answers.write_text(json.dumps({"a09": "No"}))
    round_one = loop(host, "next", run_id, "--answers", str(answers))
    finding = {"kind": "bug", "location": f"{CODE}#confirm", "severity": "P1", "message": "Reused tokens are accepted.",
               "evidence_quotes": [{"source": CODE, "text": "rejects expired tokens"}]}
    review(host, run_id, round_one, [finding])
    cap = loop(host, "next", run_id)
    assert cap["type"] == "ask" and [o["label"] for o in cap["questions"][0]["options"]][-1] == "Stop"
    answers.write_text(json.dumps({"cap": "Stop"}))
    done = loop(host, "next", run_id, "--answers", str(answers))
    assert done["verdict"] == "HALT(operator)"
    copy = Path(done["milestone_state_file"])  # findings are left: the newest file must not be an older empty one
    assert len(json.loads(copy.read_text())["findings"]) == 1


def test_code_milestone_reads_the_files_of_the_plan_patterns(host: Path) -> None:
    (host / CODE).parent.mkdir(parents=True, exist_ok=True)
    (host / CODE).write_text("export function confirm() {}\n")
    run_id = loop(host, "start", "--kind", "code-milestone", MS)["run_id"]
    action = loop(host, "next", run_id)
    assert [e["agent"] for e in action["entries"]] == ["specdev-trinity-reviewer"]
    assert CODE in run_json(host, run_id)["state"]["dispatch"]["entries"][0]["nodes"]
    review(host, run_id, action)
    done = loop(host, "next", run_id)
    assert done["verdict"] == "CONVERGED"
    assert Path(done["milestone_state_file"]).name == "findings_account_recovery_review_1.json"


def test_a_spec_common_file_is_a_read_only_scope(host: Path) -> None:
    assert loop(host, "start", "--kind", "step", "seed_manifest.json")["code"] == "E850"
    run_id = loop(host, "start", "--kind", "step", "seed_manifest.json", "--review-only")["run_id"]
    action = loop(host, "next", run_id)
    assert run_json(host, run_id)["state"]["dispatch"]["entries"][0]["nodes"] == ["spec/common/seed_manifest.json"]
    assert "seed-lint" in Path(action["entries"][0]["brief"]).read_text()
    review(host, run_id, action)
    assert loop(host, "next", run_id)["verdict"] == "CLEAN"


def test_a_second_group_run_does_not_execute_again(host: Path) -> None:
    first = loop(host, "start", "--kind", "code-group", f"{MS}/{ITEM}", "--execute", "--base-ref", "HEAD")["run_id"]
    round_one = execute(host, first)
    assert "Base ref for `git diff`" in Path(round_one["entries"][0]["brief"]).read_text()
    loop(host, "next", first, "--stop")
    second = loop(host, "start", "--kind", "code-group", f"{MS}/{ITEM}", "--execute")["run_id"]
    assert second != first
    assert [e["agent"] for e in loop(host, "next", second)["entries"]] == ["specdev-trinity-reviewer"]


def test_plan_author_needs_the_batch_and_names_the_create_command(host: Path) -> None:
    assert loop(host, "start", "--kind", "plan", "ms-new", "--author")["code"] == "E850"
    assert loop(host, "start", "--kind", "plan", MS, "--batch", "x")["code"] == "E850"
    run_id = loop(host, "start", "--kind", "plan", "ms-new", "--author", "--batch", "new_thing")["run_id"]
    action = loop(host, "next", run_id)
    assert [e["agent"] for e in action["entries"]] == ["specdev-impl"]
    brief = Path(action["entries"][0]["brief"]).read_text()
    assert "specdev step create 16a new_thing --from .specdev/drafts/plan_new_thing.json" in brief
    assert "specdev trace --recipe 16a <task-id>" in brief
    Path(action["entries"][0]["expect"]).write_text(json.dumps({"refusal": "the milestone has no row in the anchor file"}))
    assert loop(host, "next", run_id)["verdict"] == "HALT(agent_failed)"


# --------------------------------------------------------------------- what a review of the code found


def test_a_second_try_is_read_when_the_first_file_was_unusable(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "code-group", f"{MS}/{ITEM}", "--execute")["run_id"]
    first = loop(host, "next", run_id)
    Path(first["entries"][0]["expect"]).write_text(json.dumps({"note": "oops"}))
    assert loop(host, "next", run_id)["type"] == "wait"
    again = loop(host, "next", run_id, "--redispatch")
    assert "neither a result nor a refusal" in run_json(host, run_id)["meta"]["retry"]["execute"]
    Path(again["entries"][0]["expect"]).write_text(json.dumps({"result": "executed", "recorded": []}))
    assert [e["agent"] for e in loop(host, "next", run_id)["entries"]] == ["specdev-trinity-reviewer"]


def test_a_finished_code_run_writes_its_milestone_state_file_once(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "code-group", f"{MS}/{ITEM}", "--execute")["run_id"]
    review(host, run_id, execute(host, run_id))
    done = loop(host, "next", run_id)
    assert loop(host, "next", run_id) == done and loop(host, "next", run_id) == done
    assert [p.name for p in (host / ".specdev" / "findings").glob(f"findings_{ITEM}_*.json")] == [f"findings_{ITEM}_1.json"]


def test_an_upstream_outcome_in_a_code_run_becomes_a_finding_to_record_and_malformed_fields_do_not_crash(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "code-group", f"{MS}/{ITEM}", "--execute")["run_id"]
    wrong = {"kind": "bug", "location": CODE, "severity": "P1", "message": "The check runs after the update.",
             "evidence_quotes": [{"source": CODE, "text": "rejects expired tokens"}]}
    review(host, run_id, execute(host, run_id), [wrong])
    fix = loop(host, "next", run_id)
    key = f"bug|{CODE}"
    Path(fix["entries"][0]["expect"]).write_text(json.dumps({"outcomes": [{
        "key": key, "outcome": "upstream", "basis": "a string, not an object", "quote": 7,
        "named": {"kind": "gap", "location": "fr-password-reset"}}]}))
    fix_two = loop(host, "next", run_id)
    assert fix_two["type"] == "dispatch"
    brief = Path(fix_two["entries"][0]["brief"]).read_text()
    assert "gap|fr-password-reset" in brief and "Record it as an open item of the plan" in brief
    Path(fix_two["entries"][0]["expect"]).write_text(json.dumps({"outcomes": [{
        "key": "gap|fr-password-reset", "outcome": "declined", "quote": "also a string"}]}))
    after = loop(host, "next", run_id)  # no crash on the malformed quote; a finding to record cannot be declined
    assert after["type"] == "dispatch" and [e["agent"] for e in after["entries"]] == ["specdev-trinity-impl"]
    retargeted = run_json(host, run_id)["state"]["findings"]["gap|fr-password-reset"]
    assert (retargeted["status"], retargeted["attempts"]) == ("open", 1)  # the decline is a failed attempt


def test_review_record_takes_the_final_file_of_a_milestone_run(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "code-milestone", MS)["run_id"]
    review(host, run_id, loop(host, "next", run_id))
    done = loop(host, "next", run_id)
    assert done["verdict"] == "CONVERGED" and Path(done["milestone_state_file"]).name == "findings_account_recovery_review_1.json"
    code, out = run_on_example(host, "review", "record", MS, "--verdict", "verified", "--findings-file", done["final"])
    assert code == 0 and "verdict verified, 0 finding(s)" in out, out


def test_a_milestone_run_with_an_open_item_of_the_plan_ends_blocked(host: Path) -> None:
    """HALT(blocked): an open item of the plan is in the way; the run names it and writes no file for milestone-state."""
    plan = host / "spec" / "impl_context" / "ms_account_recovery_plan.json"
    document = json.loads(plan.read_text())
    document["plan"]["ambiguities"] = [{"id": "amb-where-to-store", "description": "Where does the token live?", "about": [ITEM]}]
    plan.write_text(json.dumps(document, indent=2) + "\n")
    run_id = loop(host, "start", "--kind", "code-milestone", MS)["run_id"]
    round_one = loop(host, "next", run_id)  # the code is read first: blocked is the end of a run with nothing else left
    assert {e["agent"] for e in round_one["entries"]} == {"specdev-trinity-reviewer"}
    review(host, run_id, round_one)
    done = loop(host, "next", run_id)
    assert (done["type"], done["verdict"]) == ("done", "HALT(blocked)"), done
    assert done["open_items"] == ["amb-where-to-store"] and "milestone_state_file" not in done


def test_the_stop_rule_of_a_code_run_says_the_operator_is_asked_at_the_cap_even_with_defer(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "code-group", f"{MS}/{ITEM}", "--execute", "--cap", "1", "--defer")["run_id"]
    finding = {"kind": "bug", "location": f"{CODE}#confirm", "severity": "P1", "message": "Reused tokens are accepted.",
               "evidence_quotes": [{"source": CODE, "text": "rejects expired tokens"}]}
    review(host, run_id, execute(host, run_id), [finding])
    cap = loop(host, "next", run_id)
    assert cap["type"] == "ask" and cap["questions"][0]["id"] == "cap"  # what the machine does
    answers = Path(cap["answers_path"])
    answers.write_text(json.dumps({"cap": "Stop"}))
    done = loop(host, "next", run_id, "--answers", str(answers))
    assert "at 1 rounds the operator is asked" in json.loads(Path(done["summary"]).read_text())["stop_rule"]["text"]


def test_the_manual_verification_question_says_what_the_action_is(host: Path) -> None:
    """DEVSPEC-204: an action id in a question comes with the action's own description."""
    run_id = loop(host, "start", "--kind", "code-group", f"{MS}/{ITEM}", "--execute")["run_id"]
    ask = execute(host, run_id, recorded=[], awaiting_confirmation=["a01"])
    assert ask["type"] == "ask", ask
    assert f"{ITEM}/a01 (Reject expired tokens before the password update.) carried out?" in ask["questions"][0]["question"]


def test_a_warning_the_base_did_not_have_is_listed_and_does_not_block(host: Path, monkeypatch: Any) -> None:
    """DEVSPEC-207: the run lists the own warnings that are new since the base; the exit code and the verdict do not change."""
    from types import SimpleNamespace as N

    from specdev_tools.loop import spec_io

    warning = N(code="W576", node_id="fr-password-reset", message="a task has no test")
    result = N(step="04", clear=True, blocking=N(errors=[]), new_own_warnings=[warning], waiting=[])
    monkeypatch.setattr(spec_io, "gate_run", lambda *a, **k: N(results=[result], notes=[]))
    roots = spec_io.Roots(str(Path(__file__).resolve().parents[3]), str(host / "spec"), str(host))
    view = spec_io.SpecIO(roots, ["04"]).gate(None)
    assert view.new_warnings == ["step 04: W576 fr-password-reset a task has no test"] and not view.blocking
    assert view.result == {"04": "clear"}
