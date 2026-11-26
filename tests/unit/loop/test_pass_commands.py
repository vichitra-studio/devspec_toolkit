"""``specdev pass start|next`` on a copy of the worked example, with scripted agents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from unit.loop.test_loop_commands import FINDING, KEY, loop, review, run_json
from unit.trace._lock_support import git_copy_of_example, run_on_example

MISSING = ("13_extension_manifest.json", "14_roadmap.json")
NEW_TEXT = "A user who holds a valid reset token sets a new password; every open session ends."


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return git_copy_of_example(tmp_path / "host")


def pas(host: Path, *argv: str) -> dict[str, Any]:
    code, out = run_on_example(host, "pass", *argv)
    assert code in (0, 1), out
    return json.loads(out[out.index("{"):])


def pump(host: Path, run_id: str, findings: Any = (), fix: Any = None) -> dict[str, Any]:
    """Pump one run to its end: reviewers raise *findings* in the first round only; *fix* answers a fix dispatch."""
    first = True
    for _ in range(30):
        action = loop(host, "next", run_id)
        if action["type"] == "done":
            return action
        assert action["type"] == "dispatch", action
        if action["entries"][0]["agent"] == "specdev-reviewer":
            review(host, run_id, action, findings if first else ())
            first = False
        else:
            assert fix is not None, "an unexpected fix dispatch"
            fix(action)
    raise AssertionError("the run did not end")


def test_a_clean_range_is_one_survey_and_complete(host: Path) -> None:
    pass_id = pas(host, "start", "03-05")["pass_id"]
    assert pas(host, "start", "03-05") == {"pass_id": pass_id, "resumed": True}
    action = pas(host, "next", pass_id)
    assert (action["type"], action["step"]) == ("run", "survey")
    meta = run_json(host, action["run_id"])["meta"]
    assert meta["steps"] == ["03", "04", "05"] and meta["mode"] == "review-only" and meta["pass_id"] == pass_id
    assert pas(host, "next", pass_id)["run_id"] == action["run_id"]  # an unfinished run is named again
    pump(host, action["run_id"])
    done = pas(host, "next", pass_id)
    assert (done["type"], done["verdict"]) == ("done", "COMPLETE")
    assert Path(done["report"]).is_file()


def test_a_survey_finding_is_fixed_in_the_walk_and_what_it_makes_suspect_is_walked_too(host: Path) -> None:
    pass_id = pas(host, "start", "04-05")["pass_id"]
    survey = pas(host, "next", pass_id)
    pump(host, survey["run_id"], [FINDING])
    walk = pas(host, "next", pass_id)
    assert (walk["step"], walk["walk"]) == ("04", 1)
    run = run_json(host, walk["run_id"])
    assert run["meta"]["mode"] == "worklist" and run["meta"]["carry"] == survey["run_id"] and run["state"]["defer"]
    assert list(run["state"]["findings"]) == [KEY]

    def fix(action: dict[str, Any]) -> None:
        code, out = run_on_example(host, "json", "patch", "--id", "fr-password-reset", ".statement", json.dumps(NEW_TEXT))
        assert code == 0, out
        Path(action["entries"][0]["expect"]).write_text(json.dumps(
            {"outcomes": [{"key": KEY, "outcome": "fixed", "changed": ["fr-password-reset"]}]}))

    assert pump(host, walk["run_id"], fix=fix)["verdict"] == "CONVERGED"
    below = pas(host, "next", pass_id)
    assert (below["type"], below["step"]) == ("run", "05")
    before_next = run_json(host, below["run_id"])["state"]["findings"]  # the links are taken in by the run's first `loop next`

    def accept(action: dict[str, Any]) -> None:
        keys = sorted(run_json(host, below["run_id"])["state"]["dispatch"]["keys"])
        assert keys and all(k.startswith("E763|") for k in keys)
        outcomes = []
        for key in keys:  # upward first: the link to the changed node, then the link below it
            _, holder, field, target = key.split("|")
            code, out = run_on_example(host, "attest", holder, "--field", field, "--target", target, "--yes")
            assert code == 0, out
            outcomes.append({"key": key, "outcome": "accepted", "reason": "the holder still follows"})
        Path(action["entries"][0]["expect"]).write_text(json.dumps({"outcomes": outcomes}))

    assert before_next == {}
    assert pump(host, below["run_id"], fix=accept)["verdict"] == "CONVERGED"
    done = pas(host, "next", pass_id)
    assert (done["type"], done["verdict"]) == ("done", "COMPLETE"), done
    text = Path(done["report"]).read_text()
    assert "Outside the pass" in text and "step 06: suspect links" in text  # below the range: reported, not worked


def test_stop_and_unknown_pass(host: Path) -> None:
    pass_id = pas(host, "start", "04")["pass_id"]
    assert pas(host, "next", pass_id, "--stop")["verdict"] == "HALT(operator)"
    assert pas(host, "next", "pass-none")["code"] == "E850"
    assert pas(host, "start")["code"] == "E850"
    assert pas(host, "start", "04", "--replay")["code"] == "E850"


def test_replay_starts_at_the_topmost_step_with_something_to_take(host: Path) -> None:
    pass_id = pas(host, "start", "--replay")["pass_id"]
    action = pas(host, "next", pass_id)
    # the worked example has own gate errors at step 07 and below, and nothing above: the replay starts there
    assert action["type"] == "run" and run_json(host, action["run_id"])["meta"]["steps"][0] == "07"


def test_review_about_surveys_only_the_steps_that_hold_the_set(host: Path) -> None:
    pass_id = pas(host, "start", "--review", "--about", "fr-password-reset")["pass_id"]
    action = pas(host, "next", pass_id)
    run = run_json(host, action["run_id"])
    assert run["meta"]["mode_arg"]["about"] == "fr-password-reset" and "04" in run["meta"]["steps"]
    assert "00" not in run["meta"]["steps"]
    assert pas(host, "start", "--review", "--about", "nope")["code"] == "E850"


# --- the entries and endings of a pass that only the machine tests reached ------------------------------------------


def _fix_that_changes_nothing(action: dict[str, Any]) -> None:
    Path(action["entries"][0]["expect"]).write_text(json.dumps(
        {"outcomes": [{"key": KEY, "outcome": "fixed", "changed": ["fr-password-reset"]}]}))


def _pass_json(host: Path, pass_id: str) -> dict[str, Any]:
    return json.loads((host / ".specdev" / "passes" / pass_id / "pass.json").read_text())


def _parked_pass(host: Path) -> tuple[str, dict[str, Any]]:
    """A pass over step 04 whose one finding had two failed fixes: the pass asks the operator about it."""
    pass_id = pas(host, "start", "04")["pass_id"]
    pump(host, pas(host, "next", pass_id)["run_id"], [dict(FINDING, origin="introduced-on-branch", evidence=["cited"])])
    walk = pas(host, "next", pass_id)
    stuck = pump(host, walk["run_id"], fix=_fix_that_changes_nothing)
    assert stuck["verdict"] == "HALT(stuck)"  # a walk run never asks
    (left,) = json.loads(Path(stuck["final"]).read_text())["findings"]
    assert (left["origin"], left["evidence"]) == ("introduced-on-branch", ["cited"])  # the pass hands on what the reviewer cited
    return pass_id, pas(host, "next", pass_id)


def test_start_refuses_a_mixed_entry(host: Path) -> None:
    def refusal(*argv: str) -> str:
        out = pas(host, "start", *argv)
        assert out["code"] == "E850", out
        return out["message"]

    assert "--seed and --from go with --extend" in refusal("04", "--seed", "seed.md")  # one entry, a flag of another
    assert "--seed and --from go with --extend" in refusal("--replay", "--from", "04")
    assert "--about goes with --review" in refusal("04", "--about", "fr-password-reset")
    assert "--review takes --about" in refusal("--review")
    assert "is not a step" in refusal("--extend", "x", "--from", "99")
    two_entries = refusal("04", "--extend", "x")
    assert two_entries == refusal("--replay", "--review", "--about", "fr-password-reset") == refusal()  # none, or two


def test_an_extend_pass_gives_the_intent_to_each_step_from_the_first(host: Path, tmp_path: Path) -> None:
    seed = tmp_path / "seed.md"
    seed.write_text("Passwords have a minimum strength.\n")
    pass_id = pas(host, "start", "--extend", "Add password strength rules.", "--seed", str(seed), "--from", "04")["pass_id"]
    for step in ("04", "05"):  # no survey: each step from --from gets the intent, top down
        action = pas(host, "next", pass_id)
        assert (action["type"], action["step"], action["walk"]) == ("run", step, 1), action
        meta = run_json(host, action["run_id"])["meta"]
        assert meta["mode"] == "extend" and meta["steps"] == [step] and meta["pass_id"] == pass_id
        assert meta["mode_arg"]["extend"] == "Add password strength rules." and meta["mode_arg"]["seed"] == str(seed)
        author = loop(host, "next", action["run_id"])
        assert "Intent: Add password strength rules." in Path(author["entries"][0]["brief"]).read_text()
        Path(author["entries"][0]["expect"]).write_text(json.dumps({"result": "nothing_to_add", "reason": "not this step"}))
        assert loop(host, "next", action["run_id"])["type"] == "done"


def test_all_surveys_every_step_of_the_spec(host: Path) -> None:
    action = pas(host, "next", pas(host, "start", "all")["pass_id"])
    steps = run_json(host, action["run_id"])["meta"]["steps"]
    assert action["step"] == "survey" and (steps[0], steps[-1]) == ("00", "15") and "02a" in steps


def test_a_missing_step_is_authored_and_a_refusal_of_its_author_ends_the_pass(host: Path) -> None:
    (host / "spec" / "15_scaffold.json").unlink()
    pass_id = pas(host, "start", "15")["pass_id"]
    action = pas(host, "next", pass_id)  # no artifact in the range: no survey, the walk authors
    assert (action["type"], action["step"]) == ("run", "15")
    assert run_json(host, action["run_id"])["meta"]["mode"] == "author"
    author = loop(host, "next", action["run_id"])
    assert "Provenance and citations" in Path(author["entries"][0]["brief"]).read_text()  # DEVSPEC-220: in the author brief too
    Path(author["entries"][0]["expect"]).write_text(json.dumps({"refusal": "the roadmap names no first milestone"}))
    assert loop(host, "next", action["run_id"])["verdict"] == "HALT(agent_failed)"
    assert pas(host, "next", pass_id)["verdict"] == "HALT(agent_failed)"


def test_a_missing_step_whose_inputs_are_missing_is_not_authored_and_the_pass_is_incomplete(host: Path) -> None:
    for name in MISSING:
        (host / "spec" / name).unlink()
    pass_id = pas(host, "start", "14")["pass_id"]  # step 14 reads step 13, which is outside the pass and has no artifact
    done = pas(host, "next", pass_id)
    assert (done["type"], done["verdict"]) == ("done", "INCOMPLETE"), done
    assert "INCOMPLETE" in Path(done["report"]).read_text()
    assert not (host / ".specdev" / "runs").exists() or not list((host / ".specdev" / "runs").iterdir())  # no run was started


def test_the_pass_asks_about_a_parked_finding_and_try_once_more_starts_a_run_with_the_guidance(host: Path) -> None:
    pass_id, ask = _parked_pass(host)
    assert ask["type"] == "ask" and [q["id"] for q in ask["questions"]] == [f"finding:{KEY}"]
    assert [o["label"] for o in ask["questions"][0]["options"]] == ["Try once more", "Leave as is"]
    answers = Path(ask["answers_path"])
    answers.write_text(json.dumps({}))
    assert pas(host, "next", pass_id, "--answers", str(answers))["type"] == "ask"  # nothing answered: asked again
    answers.write_text("[]")
    assert pas(host, "next", pass_id, "--answers", str(answers))["code"] == "E850"
    answers.write_text(json.dumps({f"finding:{KEY}": {"label": "Try once more", "notes": "End every open session."}}))
    again = pas(host, "next", pass_id, "--answers", str(answers))
    assert (again["type"], again["step"], again["walk"]) == ("run", "04", 2), again
    finding = run_json(host, again["run_id"])["state"]["findings"][KEY]
    assert finding["instruction"] == "The operator: End every open session." and finding["status"] == "open"
    assert _pass_json(host, pass_id)["meta"]["asked"] == [
        {"id": f"finding:{KEY}", "answer": "Try once more", "notes": "End every open session."}]


def test_leave_as_is_closes_the_finding_and_the_pass_ends(host: Path) -> None:
    pass_id, ask = _parked_pass(host)
    answers = Path(ask["answers_path"])
    answers.write_text(json.dumps({f"finding:{KEY}": "Leave as is"}))
    done = pas(host, "next", pass_id, "--answers", str(answers))
    assert (done["type"], done["verdict"], done["left"]) == ("done", "COMPLETE", 0), done
    assert pas(host, "next", pass_id) == done  # a finished pass answers the same again


def test_a_failed_run_ends_the_pass_and_retry_starts_it_anew(host: Path) -> None:
    pass_id = pas(host, "start", "04")["pass_id"]
    survey = pas(host, "next", pass_id)
    loop(host, "next", survey["run_id"])
    for _ in range(4):  # no reviewer ever writes its file
        last = loop(host, "next", survey["run_id"], "--redispatch")
    assert last["verdict"] == "HALT(agent_failed)"
    assert pas(host, "next", pass_id)["verdict"] == "HALT(agent_failed)"
    assert pas(host, "next", pass_id)["verdict"] == "HALT(agent_failed)"  # without --retry it stays ended
    again = pas(host, "next", pass_id, "--retry")
    assert (again["type"], again["step"]) == ("run", "survey") and again["run_id"] != survey["run_id"]
    pump(host, again["run_id"])
    assert pas(host, "next", pass_id)["verdict"] == "COMPLETE"


def test_retry_goes_on_after_a_stop(host: Path) -> None:
    pass_id = pas(host, "start", "04")["pass_id"]
    assert pas(host, "next", pass_id, "--stop")["verdict"] == "HALT(operator)"
    assert pas(host, "next", pass_id)["verdict"] == "HALT(operator)"
    assert pas(host, "next", pass_id, "--stop", "--retry")["verdict"] == "HALT(operator)"  # with both, the stop wins
    again = pas(host, "next", pass_id, "--retry")
    assert (again["type"], again["step"]) == ("run", "survey"), again
    pump(host, again["run_id"])
    assert pas(host, "next", pass_id)["verdict"] == "COMPLETE"


def test_replay_takes_the_open_finding_an_earlier_run_left(host: Path) -> None:
    earlier = loop(host, "start", "--kind", "step", "04", "--readers", "1", "--cap", "1")["run_id"]
    review(host, earlier, loop(host, "next", earlier), [FINDING])
    assert loop(host, "next", earlier)["verdict"] == "HALT(cap)"
    pass_id = pas(host, "start", "--replay")["pass_id"]
    survey = pas(host, "next", pass_id)
    assert run_json(host, survey["run_id"])["meta"]["steps"][0] == "04"  # without the finding the replay starts at 07
    pump(host, survey["run_id"])
    walk = pas(host, "next", pass_id)
    assert (walk["type"], walk["step"]) == ("run", "04"), walk
    run = run_json(host, walk["run_id"])
    assert run["meta"]["mode"] == "worklist" and list(run["state"]["findings"]) == [KEY]


def test_two_pass_starts_in_one_second_get_two_folders(host: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two passes of one entry started in the same second are two passes, each with its own folder."""
    import time

    monkeypatch.setattr(time, "strftime", lambda *_: "20260101T000000Z")
    first = pas(host, "start", "--review", "--about", "fr-password-reset")
    second = pas(host, "start", "--review", "--about", "fr-password-reset-request")
    assert first["pass_id"] == "pass-review-20260101T000000Z" and second["pass_id"] == first["pass_id"] + "b"
    assert not second["resumed"]
    assert _pass_json(host, first["pass_id"])["meta"]["entry_args"] != _pass_json(host, second["pass_id"])["meta"]["entry_args"]


def test_an_open_item_question_names_the_nodes_it_is_about_with_their_labels(host: Path) -> None:
    """DEVSPEC-204: no bare internal id in a question to the operator; a node id comes with its label."""
    path = next((host / "spec").glob("04_*.json"))
    document = json.loads(path.read_text())
    document["ambiguities"] = [{"id": "amb-token-lifetime", "description": "How long is a reset token valid?",
                                "about": ["cap-account-recovery"], "proposed_assumption": "30 minutes."}]
    path.write_text(json.dumps(document, indent=2) + "\n")
    pass_id = pas(host, "start", "04")["pass_id"]
    pump(host, pas(host, "next", pass_id)["run_id"])
    ask = pas(host, "next", pass_id)
    assert ask["type"] == "ask", ask
    (question,) = [q for q in ask["questions"] if q["id"] == "item:amb-token-lifetime"]
    assert "about cap-account-recovery (" in question["question"], question["question"]
    assert question["recommended"] == "Accept the proposal" == question["options"][0]["label"]  # the item's own proposal


def test_a_pass_keeps_what_its_runs_settled_and_a_replay_takes_it_from_earlier_runs(host: Path) -> None:
    """DEVSPEC-174: a decline a reviewer upheld is handed to every later run of the pass, and to a replay."""
    key = f"{FINDING['kind']}|{FINDING['location']}"
    pass_id = pas(host, "start", "04")["pass_id"]
    pump(host, pas(host, "next", pass_id)["run_id"], [FINDING])
    walk = pas(host, "next", pass_id)["run_id"]
    fix = loop(host, "next", walk)
    target = FINDING["location"].split("#")[0]
    Path(fix["entries"][0]["expect"]).write_text(json.dumps(
        {"outcomes": [{"key": key, "outcome": "declined", "quote": {"source": target, "text": target}}]}))
    review(host, walk, loop(host, "next", walk), verdict="decline_right")
    assert loop(host, "next", walk)["verdict"] == "CONVERGED"
    done = pas(host, "next", pass_id)
    assert done["type"] == "done", done
    kept = _pass_json(host, pass_id)["meta"]["settled"]
    assert kept[key]["target"] == target and kept[key]["settled_hash"]
    text = Path(done["report"]).read_text()
    assert "| Rounds | P0 | P1 | P2 |" in text and "Findings by kind, over the runs:" in text and "## Step gate at the end" in text
    replay = pas(host, "start", "--replay")["pass_id"]
    assert _pass_json(host, replay)["meta"]["settled"][key] == kept[key]
    from specdev_tools.loop.pass_commands import _Pass
    from specdev_tools.loop.pass_machine import PassAction

    started = _Pass(str(host), replay).start_run(PassAction(type="run", step="04", mode="worklist"))
    assert run_json(host, started)["state"]["findings"][key]["status"] == "settled"  # the run the pass starts knows it
