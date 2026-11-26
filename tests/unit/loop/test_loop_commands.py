"""``specdev loop start|next|status`` on a copy of the worked example, with scripted agents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from unit.trace._lock_support import git_copy_of_example, run_on_example


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return git_copy_of_example(tmp_path / "host")


def loop(host: Path, *argv: str) -> dict[str, Any]:
    code, out = run_on_example(host, "loop", *argv)
    assert code in (0, 1), out
    return json.loads(out[out.index("{"):])


def run_json(host: Path, run_id: str) -> dict[str, Any]:
    return json.loads((host / ".specdev" / "runs" / run_id / "run.json").read_text())


def review(host: Path, run_id: str, action: dict[str, Any], findings: Any = (), verdict: str = "resolved", **over: Any) -> None:
    """Every reviewer of *action* writes a complete file with *findings* and a judgement for each key it was given."""
    doc = run_json(host, run_id)
    entries = {e["id"]: e for e in doc["state"]["dispatch"]["entries"]}
    for item in action["entries"]:
        entry = entries[Path(item["expect"]).name.rsplit(".t", 1)[0]]
        body = {
            "round": doc["state"]["rounds_used"] + 1, "scope": doc["meta"]["scope_label"], "generated_at": 1,
            "coverage": {"read": [*entry["nodes"], *doc["meta"]["contract"]], "not_run": []},
            "judgements": [{"key": k, "verdict": verdict, "quote": "q"} for k in entry["judge"]],
            "findings": list(findings), **over,
        }
        Path(item["expect"]).write_text(json.dumps(body))


FINDING = {
    "kind": "ambiguity", "location": "fr-password-reset#statement", "severity": "P1",
    "message": "The statement does not say what happens to open sessions.",
    "evidence_quotes": [{"source": "fr-password-reset", "text": "fr-password-reset"}],
}
KEY = "ambiguity|fr-password-reset#statement"


def test_review_only_clean(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--review-only")["run_id"]
    action = loop(host, "next", run_id)
    assert action["type"] == "dispatch" and len(action["entries"]) == 2
    assert all(e["agent"] == "specdev-reviewer" and Path(e["brief"]).is_file() for e in action["entries"])
    review(host, run_id, action)
    done = loop(host, "next", run_id)
    assert (done["type"], done["verdict"]) == ("done", "CLEAN")
    assert Path(done["report"]).is_file() and json.loads(Path(done["summary"]).read_text())["verdict"] == "CLEAN"
    assert loop(host, "next", run_id)["verdict"] == "CLEAN"  # a finished run answers the same again


def test_start_resumes_the_unfinished_run_and_refuses_another_mode(host: Path) -> None:
    first = loop(host, "start", "--kind", "step", "04")
    assert loop(host, "start", "--kind", "step", "04") == {"run_id": first["run_id"], "resumed": True}
    assert loop(host, "start", "--kind", "step", "04", "--review-only")["code"] == "E850"


def test_start_refusals(host: Path) -> None:
    assert loop(host, "start", "--kind", "step", "04", "--author")["code"] == "E850"  # the artifact exists
    assert loop(host, "start", "--kind", "step", "99")["code"] == "E850"
    assert loop(host, "start", "--kind", "step", "04-05", "--extend", "x")["code"] == "E850"


def test_missing_and_refused_files_wait_then_redispatch_then_fail(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--review-only", "--readers", "1")["run_id"]
    action = loop(host, "next", run_id)
    expect = Path(action["entries"][0]["expect"])
    expect.write_text(json.dumps({"round": 1, "scope": "04", "generated_at": 1, "findings": []}))  # no coverage
    waiting = loop(host, "next", run_id)
    assert waiting["type"] == "wait" and waiting["missing"] == [str(expect)]
    again = loop(host, "next", run_id, "--redispatch")
    assert again["type"] == "dispatch" and again["entries"][0]["expect"].endswith(".t2.json")
    assert "coverage.read lacks" in Path(again["entries"][0]["brief"]).read_text()
    assert loop(host, "next", run_id, "--redispatch")["verdict"] == "HALT(agent_failed)"


def test_a_finding_with_a_false_quote_is_rejected_and_listed(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--review-only", "--readers", "1")["run_id"]
    action = loop(host, "next", run_id)
    bad = dict(FINDING, evidence_quotes=[{"source": "fr-password-reset", "text": "text that is not there at all"}])
    indexed = dict(FINDING, location="spec/04_fr_list.json#/requirements/0")
    review(host, run_id, action, [bad, indexed])
    done = loop(host, "next", run_id)
    assert done["verdict"] == "CLEAN"
    rejected = json.loads((host / ".specdev" / "runs" / run_id / "d1" / "rejected.json").read_text())
    assert len(rejected) == 2 and json.loads(Path(done["summary"]).read_text())["rejected"] == 2


def test_review_only_reports_findings_and_fixes_nothing(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--review-only")["run_id"]
    review(host, run_id, loop(host, "next", run_id), [FINDING])
    done = loop(host, "next", run_id)
    assert done["verdict"] == "FINDINGS"
    final = json.loads(Path(done["summary"]).read_text())
    assert [f["key"] for f in final["findings"]] == [KEY]  # two reviewers, one entry


def test_fix_then_confirm_converges(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04")["run_id"]
    review(host, run_id, loop(host, "next", run_id), [FINDING])
    fix = loop(host, "next", run_id)
    assert fix["type"] == "dispatch" and [e["agent"] for e in fix["entries"]] == ["specdev-impl"]
    assert KEY in Path(fix["entries"][0]["brief"]).read_text()
    code, out = run_on_example(host, "json", "patch", "--id", "fr-password-reset", ".statement",
                               json.dumps("A user who holds a valid reset token sets a new password; every open session ends."))
    assert code == 0, out
    Path(fix["entries"][0]["expect"]).write_text(json.dumps(
        {"outcomes": [{"key": KEY, "outcome": "fixed", "changed": ["fr-password-reset"], "reason": "said it"}]}))
    confirm = loop(host, "next", run_id)
    assert confirm["type"] == "dispatch" and len(confirm["entries"]) == 1  # one reader for a change
    state = run_json(host, run_id)["state"]
    assert state["dispatch"]["entries"][0]["judge"] == [KEY]
    assert state["dispatch"]["entries"][0]["nodes"] == ["fr-password-reset"]  # only what changed is read again
    review(host, run_id, confirm)
    done = loop(host, "next", run_id)
    assert done["verdict"] == "CONVERGED", done
    status = loop(host, "status", run_id)["runs"][0]
    assert status["verdict"] == "CONVERGED" and status["rounds"] == 2 and status["findings"] == {"resolved": 1}


def test_a_fix_that_changed_nothing_is_not_a_fix(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--readers", "1")["run_id"]
    review(host, run_id, loop(host, "next", run_id), [FINDING])
    for _ in range(2):
        fix = loop(host, "next", run_id)
        assert fix["entries"][0]["agent"] == "specdev-impl"
        Path(fix["entries"][0]["expect"]).write_text(json.dumps(
            {"outcomes": [{"key": KEY, "outcome": "fixed", "changed": ["fr-password-reset"]}]}))
    ask = loop(host, "next", run_id)
    assert ask["type"] == "ask" and ask["questions"][0]["id"] == KEY
    answers = Path(ask["answers_path"])
    answers.write_text(json.dumps({KEY: "Leave as is"}))
    done = loop(host, "next", run_id, "--answers", str(answers))
    assert done["verdict"] == "CONVERGED"  # the operator's answer closes it, and the report says so
    assert "Left as is by the operator" in Path(done["report"]).read_text()
    assert json.loads(Path(done["summary"]).read_text())["findings"][0]["left_as_is"] is True


def test_stop_ends_the_run(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04")["run_id"]
    loop(host, "next", run_id)
    assert loop(host, "next", run_id, "--stop")["verdict"] == "HALT(operator)"
    assert loop(host, "start", "--kind", "step", "04")["resumed"] is False


def test_final_json_is_a_findings_file_and_a_worklist_run_fixes_first(host: Path) -> None:
    first = loop(host, "start", "--kind", "step", "04", "--review-only")["run_id"]
    review(host, first, loop(host, "next", first), [FINDING])
    done = loop(host, "next", first)
    final = json.loads(Path(done["final"]).read_text())
    assert final["$schema"] == "vc:infra:findings" and [f["signature"] for f in final["findings"]] == [KEY]
    second = loop(host, "start", "--kind", "step", "04", "--worklist", done["final"])["run_id"]
    assert run_json(host, second)["meta"]["carry"] == first  # a final.json names its run
    fix = loop(host, "next", second)
    assert [e["agent"] for e in fix["entries"]] == ["specdev-impl"]  # nothing is read again before the fix
    assert loop(host, "start", "--kind", "step", "04")["resumed"] is True
    assert loop(host, "start", "--kind", "step", "04", "--extend", "x")["code"] == "E850"


def test_a_worklist_finding_outside_the_scope_is_rejected(host: Path, tmp_path: Path) -> None:
    other = dict(FINDING, location="cap-account-recovery", signature="x")
    gone = dict(FINDING, location="fr-not-there", signature="y")
    path = tmp_path / "w.json"
    path.write_text(json.dumps({"round": 1, "scope": "04", "generated_at": 1, "findings": [other, gone]}))
    run_id = loop(host, "start", "--kind", "step", "04", "--worklist", str(path))["run_id"]
    rejected = json.loads((host / ".specdev" / "runs" / run_id / "rejected.json").read_text())
    assert [r["reason"].split(" is ")[-1].split(" no ")[-1] for r in rejected] == ["outside this run's scope", "longer exists"]
    assert loop(host, "next", run_id)["entries"][0]["agent"] == "specdev-reviewer"  # nothing to fix: a round


def test_about_limits_what_is_read(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--review-only", "--about", "fr-password-reset")["run_id"]
    loop(host, "next", run_id)
    nodes = run_json(host, run_id)["state"]["dispatch"]["entries"][0]["nodes"]
    assert "fr-password-reset" in nodes and "fr-password-reset-request" not in nodes
    assert loop(host, "start", "--kind", "step", "04", "--about", "no-such-node")["code"] == "E850"


def test_partial_answers_are_kept_and_the_rest_is_asked_again(host: Path) -> None:
    second = dict(FINDING, kind="gap")
    keys = [KEY, "gap|fr-password-reset#statement"]
    run_id = loop(host, "start", "--kind", "step", "04", "--readers", "1")["run_id"]
    review(host, run_id, loop(host, "next", run_id), [FINDING, second])
    action = loop(host, "next", run_id)
    for _ in range(4):
        if action["type"] != "dispatch":
            break
        Path(action["entries"][0]["expect"]).write_text(json.dumps(
            {"outcomes": [{"key": k, "outcome": "fixed", "changed": ["fr-password-reset"]} for k in keys]}))
        action = loop(host, "next", run_id)
    assert action["type"] == "ask" and sorted(q["id"] for q in action["questions"]) == sorted(keys)
    answers = Path(action["answers_path"])
    answers.write_text(json.dumps({keys[0]: "Leave as is"}))
    rest = loop(host, "next", run_id, "--answers", str(answers))
    assert rest["type"] == "ask" and [q["id"] for q in rest["questions"]] == [keys[1]]
    answers.write_text(json.dumps({keys[1]: "Leave as is"}))
    assert loop(host, "next", run_id, "--answers", str(answers))["verdict"] == "CONVERGED"



def test_a_refusal_is_not_carried_into_the_next_dispatch(host: Path) -> None:
    """Entry ids repeat in every dispatch: the reviewer of round 2 is not told that its first file was refused."""
    run_id = loop(host, "start", "--kind", "step", "04", "--readers", "1")["run_id"]
    first = loop(host, "next", run_id)
    Path(first["entries"][0]["expect"]).write_text(json.dumps({"round": 1, "scope": "04", "generated_at": 1, "findings": []}))
    waiting = loop(host, "next", run_id)
    assert list(waiting["refused"].values())[0].startswith("coverage.read lacks")
    review(host, run_id, loop(host, "next", run_id, "--redispatch"), [FINDING])
    fix = loop(host, "next", run_id)
    code, out = run_on_example(host, "json", "patch", "--id", "fr-password-reset", ".statement",
                               json.dumps("A user who holds a valid reset token sets a new password; every open session ends."))
    assert code == 0, out
    Path(fix["entries"][0]["expect"]).write_text(json.dumps(
        {"outcomes": [{"key": KEY, "outcome": "fixed", "changed": ["fr-password-reset"], "reason": "said it"}]}))
    confirm = loop(host, "next", run_id)
    assert confirm["type"] == "dispatch" and confirm["entries"][0]["expect"].endswith(".t1.json")
    assert "refused" not in Path(confirm["entries"][0]["brief"]).read_text()
    waiting = loop(host, "next", run_id)
    assert waiting["type"] == "wait" and "refused" not in waiting


# --- the modes and verdicts of `loop start` that only the machine tests reached ------------------------------------
# HALT(blocked) needs a milestone plan with an open item: its command test is in test_loop_kinds.py
# (test_a_milestone_run_with_an_open_item_of_the_plan_ends_blocked).


NEW_STATEMENT = "A user who holds a valid reset token sets a new password; every open session ends."


def _patch_statement(host: Path) -> None:
    code, out = run_on_example(host, "json", "patch", "--id", "fr-password-reset", ".statement", json.dumps(NEW_STATEMENT))
    assert code == 0, out


def _claim_a_fix_that_changes_nothing(action: dict[str, Any]) -> None:
    Path(action["entries"][0]["expect"]).write_text(json.dumps(
        {"outcomes": [{"key": KEY, "outcome": "fixed", "changed": ["fr-password-reset"]}]}))


def test_extend_dispatches_the_author_with_the_intent_then_reviews_what_was_written(host: Path, tmp_path: Path) -> None:
    seed = tmp_path / "seed.md"
    seed.write_text("Passwords have a minimum strength.\n")
    assert loop(host, "start", "--kind", "step", "04", "--seed", str(seed))["code"] == "E850"  # --seed goes with --extend
    run_id = loop(host, "start", "--kind", "step", "04", "--extend", "Add a rule for password strength.", "--seed", str(seed))["run_id"]
    meta = run_json(host, run_id)["meta"]
    assert meta["mode"] == "extend" and meta["mode_arg"]["seed"] == str(seed)
    author = loop(host, "next", run_id)
    assert [e["agent"] for e in author["entries"]] == ["specdev-impl"]
    brief = Path(author["entries"][0]["brief"]).read_text()
    assert "Intent: Add a rule for password strength." in brief and str(seed) in brief and "`nothing_to_add`" in brief
    _patch_statement(host)  # what the author wrote
    Path(author["entries"][0]["expect"]).write_text(json.dumps({"result": "written", "written": ["fr-password-reset"]}))
    round_one = loop(host, "next", run_id)
    assert {e["agent"] for e in round_one["entries"]} == {"specdev-reviewer"}
    read = {n for e in run_json(host, run_id)["state"]["dispatch"]["entries"] for n in e["nodes"]}
    assert "fr-password-reset" in read
    review(host, run_id, round_one)
    assert loop(host, "next", run_id)["verdict"] == "CONVERGED"


def test_an_extend_that_adds_nothing_ends_without_a_round(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--extend", "Nothing for this step.")["run_id"]
    author = loop(host, "next", run_id)
    Path(author["entries"][0]["expect"]).write_text(json.dumps({"result": "nothing_to_add", "reason": "the intent is about step 05"}))
    done = loop(host, "next", run_id)
    assert done["type"] == "done" and run_json(host, run_id)["state"]["rounds_used"] == 0


def test_author_on_a_missing_step_dispatches_the_author_and_a_refusal_ends_the_run(host: Path) -> None:
    (host / "spec" / "15_scaffold.json").unlink()
    run_id = loop(host, "start", "--kind", "step", "15", "--author")["run_id"]
    author = loop(host, "next", run_id)
    assert [e["agent"] for e in author["entries"]] == ["specdev-impl"]
    brief = Path(author["entries"][0]["brief"]).read_text()
    assert "prompt_15_scaffold.md" in brief and "specdev step create 15" in brief
    Path(author["entries"][0]["expect"]).write_text(json.dumps({"refusal": "step 14 has no roadmap to scaffold from"}))
    done = loop(host, "next", run_id)
    assert done["type"] == "done" and done["verdict"].startswith("HALT("), done
    assert "step 14 has no roadmap" in Path(done["report"]).read_text() + json.dumps(run_json(host, run_id))


def test_carry_counts_as_read_what_the_earlier_run_read_and_has_not_changed(host: Path) -> None:
    assert loop(host, "start", "--kind", "step", "04", "--carry", "step-none")["code"] == "E850"
    earlier = loop(host, "start", "--kind", "step", "04", "--review-only", "--readers", "1")["run_id"]
    review(host, earlier, loop(host, "next", earlier))
    assert loop(host, "next", earlier)["verdict"] == "CLEAN"
    unchanged = loop(host, "start", "--kind", "step", "04", "--carry", earlier)["run_id"]
    assert run_json(host, unchanged)["meta"]["carry"] == earlier
    assert loop(host, "next", unchanged)["verdict"] == "CONVERGED"  # nothing changed: nothing is read again
    assert run_json(host, unchanged)["state"]["rounds_used"] == 0
    _patch_statement(host)
    changed = loop(host, "start", "--kind", "step", "04", "--carry", earlier)["run_id"]
    action = loop(host, "next", changed)
    assert {e["agent"] for e in action["entries"]} == {"specdev-reviewer"}
    read = {n for e in run_json(host, changed)["state"]["dispatch"]["entries"] for n in e["nodes"]}
    assert "fr-password-reset" in read and "fr-password-reset-request" not in read  # only what changed


def test_two_failed_fixes_ask_the_operator_and_with_defer_end_stuck(host: Path) -> None:
    def two_failed_fixes(*flags: str) -> dict[str, Any]:
        run_id = loop(host, "start", "--kind", "step", "04", "--readers", "1", *flags)["run_id"]
        review(host, run_id, loop(host, "next", run_id), [FINDING])
        for _ in range(2):
            fix = loop(host, "next", run_id)
            assert [e["agent"] for e in fix["entries"]] == ["specdev-impl"]
            _claim_a_fix_that_changes_nothing(fix)
        return loop(host, "next", run_id)

    stuck = two_failed_fixes("--defer")
    assert (stuck["type"], stuck["verdict"]) == ("done", "HALT(stuck)")
    summary = json.loads(Path(stuck["summary"]).read_text())
    assert [(f["key"], f["attempts"]) for f in summary["findings"]] == [(KEY, 2)]
    assert [f["signature"] for f in json.loads(Path(stuck["final"]).read_text())["findings"]] == [KEY]
    asked = two_failed_fixes()  # the same without --defer, in a new run: the operator is asked
    assert asked["type"] == "ask" and [o["label"] for o in asked["questions"][0]["options"]] == ["Try once more", "Leave as is"]


def test_a_spec_run_ends_at_its_cap_with_what_is_left(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--readers", "1", "--cap", "1")["run_id"]
    review(host, run_id, loop(host, "next", run_id), [FINDING])
    done = loop(host, "next", run_id)
    assert done["verdict"] == "HALT(cap)"
    assert [f["signature"] for f in json.loads(Path(done["final"]).read_text())["findings"]] == [KEY]
    assert "HALT(cap)" in Path(done["report"]).read_text()


def test_status_lists_every_run_and_the_runs_of_a_pass(host: Path) -> None:
    first = loop(host, "start", "--kind", "step", "04", "--review-only")["run_id"]
    second = loop(host, "start", "--kind", "step", "05", "--review-only", "--pass", "pass-x")["run_id"]
    assert [r["run_id"] for r in loop(host, "status")["runs"]] == [first, second]
    assert [r["run_id"] for r in loop(host, "status", "--pass", "pass-x")["runs"]] == [second]
    assert loop(host, "status", "--pass", "pass-none")["runs"] == []


def test_what_a_reviewer_cites_and_the_origin_reach_the_final_file(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--review-only", "--readers", "1")["run_id"]
    cited = dict(FINDING, origin="introduced-on-branch", evidence=["minLength: 1 in the schema of step 04"])
    review(host, run_id, loop(host, "next", run_id), [cited])
    done = loop(host, "next", run_id)
    (final,) = json.loads(Path(done["final"]).read_text())["findings"]
    assert final["origin"] == "introduced-on-branch" and final["evidence"] == ["minLength: 1 in the schema of step 04"]
    again = loop(host, "start", "--kind", "step", "04", "--worklist", done["final"], "--cap", "1")["run_id"]
    assert run_json(host, again)["state"]["findings"][KEY]["status"] == "open"  # the file is a findings file the loop takes
    fix = loop(host, "next", again)
    _claim_a_fix_that_changes_nothing(fix)
    loop(host, "next", again, "--stop")
    (kept,) = json.loads(Path(loop(host, "next", again)["final"]).read_text())["findings"]
    assert (kept["origin"], kept["evidence"]) == (final["origin"], final["evidence"])  # and a worklist run keeps them


# --- what a run records and carries (DEVSPEC-172, 174, 197, 222) ----------------------------------------------------


def test_the_summary_and_the_report_state_the_stop_rule_of_the_run(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--readers", "1", "--cap", "3", "--defer")["run_id"]
    review(host, run_id, loop(host, "next", run_id))
    done = loop(host, "next", run_id)
    rule = json.loads(Path(done["summary"]).read_text())["stop_rule"]
    assert (rule["blocking"], rule["cap"], rule["max_attempts"], rule["defer"], rule["readers"]) == (["P0", "P1"], 3, 2, True, 1)
    assert "at 3 rounds it ends HALT(cap)" in rule["text"] and "ends the run HALT(stuck)" in rule["text"]
    assert f"Stop rule: {rule['text']}" in Path(done["report"]).read_text()
    once = loop(host, "start", "--kind", "step", "05", "--review-only", "--readers", "1")["run_id"]
    review(host, once, loop(host, "next", once))
    text = json.loads(Path(loop(host, "next", once)["summary"]).read_text())["stop_rule"]["text"]
    assert text.startswith("review-only: one round and nothing is fixed") and "HALT" not in text


def test_a_finding_with_no_quote_or_an_unknown_source_is_refused_and_counted(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--review-only", "--readers", "1")["run_id"]
    no_quote = {k: v for k, v in FINDING.items() if k != "evidence_quotes"}
    no_source = dict(FINDING, kind="gap", evidence_quotes=[{"source": "no-such-node", "text": "fr-password-reset"}])
    review(host, run_id, loop(host, "next", run_id), [no_quote, no_source])
    done = loop(host, "next", run_id)
    assert done["verdict"] == "CLEAN"  # neither reached the run
    rejected = json.loads((host / ".specdev" / "runs" / run_id / "d1" / "rejected.json").read_text())
    assert [r["reason"] for r in rejected] == ["no evidence quote", "a quote does not occur in 'no-such-node'"]
    assert json.loads(Path(done["summary"]).read_text())["rejected"] == 2
    assert "Findings refused at intake: 2" in Path(done["report"]).read_text()


def test_a_decline_a_reviewer_upheld_is_known_to_the_run_that_follows(host: Path) -> None:
    first = loop(host, "start", "--kind", "step", "04", "--readers", "1")["run_id"]
    review(host, first, loop(host, "next", first), [FINDING])
    fix = loop(host, "next", first)
    Path(fix["entries"][0]["expect"]).write_text(json.dumps({"outcomes": [{
        "key": KEY, "outcome": "declined", "quote": {"source": "fr-password-reset", "text": "fr-password-reset"}}]}))
    review(host, first, loop(host, "next", first), verdict="decline_right")
    done = loop(host, "next", first)
    assert done["verdict"] == "CONVERGED" and run_json(host, first)["state"]["findings"][KEY]["status"] == "settled"
    assert json.loads(Path(done["final"]).read_text())["findings"] == []  # the final file holds only what is left
    second = loop(host, "start", "--kind", "step", "04", "--worklist", done["final"])["run_id"]
    known = run_json(host, second)["state"]["findings"][KEY]
    assert known["status"] == "settled" and known["settled_hash"] == run_json(host, first)["state"]["findings"][KEY]["settled_hash"]
    assert loop(host, "next", second)["verdict"] == "CONVERGED"  # nothing changed: nothing is read or raised again


def _break_the_priority_of(host: Path, node_id: str) -> None:
    path = next((host / "spec").glob("04_*.json"))
    text = path.read_text()
    document = json.loads(text)

    def walk(value: Any) -> bool:
        if isinstance(value, dict):
            if value.get("fr_id") == node_id:
                value["priority"] = "no-such-priority"
                return True
            return any(walk(v) for v in value.values())
        return isinstance(value, list) and any(walk(v) for v in value)

    assert walk(document)
    path.write_text(json.dumps(document, indent=2) + "\n")


def test_a_gate_error_is_a_finding_of_its_own_and_stays_when_the_fixer_leaves_it(host: Path) -> None:
    _break_the_priority_of(host, "fr-password-reset-request")
    run_id = loop(host, "start", "--kind", "step", "04", "--readers", "1")["run_id"]
    fix = loop(host, "next", run_id)  # the tool read the gate itself: the error is handed to a fixer before any review
    assert [e["agent"] for e in fix["entries"]] == ["specdev-impl"]
    (gate_key,) = run_json(host, run_id)["state"]["dispatch"]["keys"]
    assert gate_key.startswith("E") and "[gate]" in Path(fix["entries"][0]["brief"]).read_text()
    Path(fix["entries"][0]["expect"]).write_text(json.dumps({"outcomes": []}))  # the fixer leaves it
    loop(host, "next", run_id)
    run = run_json(host, run_id)
    left = run["state"]["findings"][gate_key]
    assert (left["source"], left["status"], left["attempts"]) == ("gate", "open", 1)  # still there, one failed attempt
    assert run["meta"]["unasked_changes"] == []


def test_an_edit_outside_the_findings_is_listed_in_the_report(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--readers", "1")["run_id"]
    review(host, run_id, loop(host, "next", run_id), [FINDING])
    fix = loop(host, "next", run_id)
    _patch_statement(host)
    code, out = run_on_example(host, "json", "patch", "--id", "fr-password-reset-request", ".statement",
                               json.dumps("A member asks for a reset token by email; the answer never says whether the address is known."))
    assert code == 0, out  # an edit of a node no finding names
    Path(fix["entries"][0]["expect"]).write_text(json.dumps(
        {"outcomes": [{"key": KEY, "outcome": "fixed", "changed": ["fr-password-reset"]}]}))
    loop(host, "next", run_id)
    assert run_json(host, run_id)["meta"]["unasked_changes"] == ["fr-password-reset-request"]
    done = loop(host, "next", run_id, "--stop")
    assert "## Changed without a finding\n- fr-password-reset-request" in Path(done["report"]).read_text()


def test_the_tool_stamps_the_arrival_time_and_a_recorded_open_item_is_not_an_unasked_change(host: Path) -> None:
    run_id = loop(host, "start", "--kind", "step", "04", "--readers", "1")["run_id"]
    action = loop(host, "next", run_id)
    review(host, run_id, action, [FINDING], generated_at="not a number")  # an agent has no clock: the tool sets it
    fix = loop(host, "next", run_id)
    assert [e["agent"] for e in fix["entries"]] == ["specdev-impl"], fix
    merged = json.loads((host / ".specdev" / "runs" / run_id / "d1" / "r0.0.t1.json").read_text())
    assert merged["generated_at"] == "not a number"  # the agent's file is left as written; the stamp is the tool's own
    item = {"description": "What happens to open sessions?", "about": ["cap-account-recovery"]}
    code, out = run_on_example(host, "json", "insert", "--step", "04", ".ambiguities", json.dumps(item))
    assert code == 0, out
    (item_id,) = [i["id"] for i in json.loads(next((host / "spec").glob("04_*.json")).read_text())["ambiguities"]]
    Path(fix["entries"][0]["expect"]).write_text(json.dumps(
        {"outcomes": [{"key": KEY, "outcome": "recorded", "item_id": item_id}]}))
    loop(host, "next", run_id)
    meta = run_json(host, run_id)["meta"]
    assert meta["recorded_items"] == [item_id] and item_id not in meta["unasked_changes"]
    assert run_json(host, run_id)["state"]["findings"][KEY]["status"] == "settled"


def test_an_edit_of_another_steps_node_or_of_a_seed_during_a_fix_is_listed(host: Path) -> None:
    """DEVSPEC-222: what a fixer changed outside the run's scope is in the report, whatever its outcome file says."""
    run_id = loop(host, "start", "--kind", "step", "04", "--readers", "1")["run_id"]
    review(host, run_id, loop(host, "next", run_id), [FINDING])
    fix = loop(host, "next", run_id)
    _patch_statement(host)
    code, out = run_on_example(host, "json", "patch", "--id", "cap-account-recovery", ".description",
                               json.dumps("Members regain access to an account they are locked out of, by email."))
    assert code == 0, out  # a node of step 01
    seed = host / "docs" / "seed" / "seed_accounts.md"
    seed.write_text(seed.read_text() + "\nA reset token is valid for 45 minutes.\n")
    Path(fix["entries"][0]["expect"]).write_text(json.dumps(
        {"outcomes": [{"key": KEY, "outcome": "fixed", "changed": ["fr-password-reset"]}]}))
    loop(host, "next", run_id)
    listed = run_json(host, run_id)["meta"]["unasked_changes"]
    assert "cap-account-recovery (outside the scope)" in listed, listed
    assert any(entry.startswith("seed document ") and entry.endswith("(outside the scope)") for entry in listed), listed
    assert "fr-password-reset" not in " ".join(listed).replace("fr-password-reset-request", "")  # the target is no unasked change
