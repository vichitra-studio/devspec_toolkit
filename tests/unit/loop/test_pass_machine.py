"""The pass machine (``specdev_tools.loop.pass_machine``): its bounds, its verdict, and the
scenarios the design reviews walked by hand."""

from __future__ import annotations

import random

import pytest

from specdev_tools.loop import pass_machine as p

STEPS = ["00", "01", "02", "03", "04", "05"]


def _view(**flags) -> p.View:
    """A view of six steps; ``flags`` maps a step to the names of the flags it has set."""
    v = p.View()
    for st in STEPS:
        sv = p.StepView(step=st)
        for name in flags.get(f"s{st}", ()):
            setattr(sv, name, not name.startswith("has_") and name != "ready")
        v.steps.append(sv)
    v.pool_unclosed = any(sv.pool_open for sv in v.steps)
    return v


def _drive(s: p.PassState, v: p.View, on_run, on_ask=lambda v: None, limit: int = 200):
    """Run a pass to its verdict. ``on_run(action, view)`` returns the run's verdict and may
    change the view, as a real run changes the spec."""
    log = []
    for _ in range(limit):
        a = p.decide(s, v)
        log.append(a)
        if a.type == "done":
            return a.verdict, log
        if a.type == "ask":
            on_ask(v)
            p.record_answered(s)  # the caller says so once no question of the batch is left
            continue
        run_id = f"run{len(s.runs)}"
        p.record_run(s, run_id, a.step)
        p.record_verdict(s, run_id, on_run(a, v))
        v.pool_unclosed = any(sv.pool_open for sv in v.steps)
    raise AssertionError("the pass did not end")


def _sv(v: p.View, step: str) -> p.StepView:
    return next(sv for sv in v.steps if sv.step == step)


def _clear(sv: p.StepView) -> None:
    sv.pool_open = sv.link_work = sv.gate_work = sv.item_work = sv.suspect = False
    sv.has_artifact = True


# ----------------------------------------------------------------- properties


@pytest.mark.parametrize("entry", ["range", "extend", "review", "replay"])
def test_every_pass_ends_within_two_walks_and_its_verdict_is_true(entry):
    for seed in range(500):
        rng = random.Random(seed)
        v = p.View()
        for st in STEPS:
            v.steps.append(
                p.StepView(
                    step=st,
                    has_artifact=rng.random() < 0.8,
                    ready=rng.random() < 0.9,
                    link_work=rng.random() < 0.2,
                    gate_work=rng.random() < 0.2,
                    open_items=rng.random() < 0.1,
                )
            )
        for sv in v.steps:
            sv.suspect = sv.link_work
        s = p.PassState(entry=entry)
        per_walk: dict[tuple[int, str], int] = {}
        asks = surveys = 0

        def on_run(a, v):
            nonlocal surveys
            if a.step is None:
                surveys += 1
                for sv in v.steps:  # the survey fills the pool
                    sv.pool_open = sv.pool_open or (sv.has_artifact and rng.random() < 0.4)
                return rng.choice(["FINDINGS", "CLEAN"])
            per_walk[(s.walk, a.step)] = per_walk.get((s.walk, a.step), 0) + 1
            i = STEPS.index(a.step)
            sv = v.steps[i]
            if rng.random() < 0.75:
                _clear(sv)
            elif a.mode == "author":
                sv.has_artifact = rng.random() < 0.5
            if i and rng.random() < 0.25:  # a handoff about a step above
                v.steps[rng.randrange(i)].pool_open = True
            for below in v.steps[i + 1 :]:  # an edit makes links below suspect
                if below.has_artifact and rng.random() < 0.2:
                    below.link_work = below.suspect = True
            if rng.random() < 0.15:
                sv.open_items = True
            return rng.choice(["CONVERGED", "CONVERGED", "HALT(cap)", "HALT(stuck)"])

        def on_ask(v):
            nonlocal asks
            asks += 1
            for sv in v.steps:
                if sv.open_items and rng.random() < 0.7:
                    sv.open_items, sv.item_work = False, True

        v.to_ask = any(sv.open_items for sv in v.steps)
        verdict, _ = _drive(s, v, on_run, on_ask)
        assert verdict in ("COMPLETE", "INCOMPLETE"), seed
        assert s.walk <= p.MAX_WALKS and asks <= 1 and surveys <= 1, seed
        assert all(n == 1 for n in per_walk.values()), (seed, per_walk)
        if entry == "extend":
            assert surveys == 0, seed
        if verdict == "COMPLETE":
            assert all(sv.has_artifact for sv in v.steps), seed
            assert not any(sv.pool_open or sv.link_work or sv.gate_work or sv.item_work for sv in v.steps), seed
            assert not any(sv.open_items or sv.suspect for sv in v.steps), seed


# ----------------------------------------------------------------- scenarios


def test_replay_of_one_upstream_finding_fixes_the_top_step_first_then_what_became_suspect():
    v = _view(s03=["pool_open"])
    s = p.PassState(entry="replay")

    def on_run(a, v):
        if a.step == "03":
            _clear(_sv(v, "03"))
            for st in ("04", "05"):  # the edit of 03 makes the links below suspect
                _sv(v, st).link_work = _sv(v, st).suspect = True
        elif a.step:
            _clear(_sv(v, a.step))
        return "CONVERGED" if a.step else "FINDINGS"

    verdict, log = _drive(s, v, on_run)
    assert [(a.step, a.mode) for a in log if a.type == "run"] == [
        (None, "review-only"), ("03", "worklist"), ("04", "worklist"), ("05", "worklist"),
    ]
    assert verdict == "COMPLETE" and s.walk == 2  # the second walk found nothing to do


def test_a_handoff_raised_during_the_walk_is_taken_by_the_second_walk_and_no_third():
    v = _view(s04=["pool_open"])
    s = p.PassState(entry="range")
    seen = []

    def on_run(a, v):
        seen.append((s.walk, a.step))
        if a.step == "04":
            _clear(_sv(v, "04"))
            _sv(v, "02").pool_open = True  # every run of 04 finds something in 02
        elif a.step == "02":
            _clear(_sv(v, "02"))
            _sv(v, "04").link_work = _sv(v, "04").suspect = True
        return "CONVERGED" if a.step else "FINDINGS"

    verdict, _ = _drive(s, v, on_run)
    assert seen == [(1, None), (1, "04"), (2, "02"), (2, "04")]
    assert verdict == "INCOMPLETE"  # what the second walk raised is reported, not chased


def test_complete_is_not_said_while_a_pool_finding_is_unclosed():
    v = _view(s02=["pool_open"])
    s = p.PassState(entry="range", surveyed=True)
    verdict, _ = _drive(s, v, lambda a, v: "HALT(cap)")  # the run leaves the finding open
    assert verdict == "INCOMPLETE" and len(s.runs) == 2  # tried once in each walk


def test_an_extend_pass_dispatches_the_intent_once_per_step_and_only_in_the_first_walk():
    v = _view()
    s = p.PassState(entry="extend")
    seen = []

    def on_run(a, v):
        seen.append((s.walk, a.step, a.mode))
        if a.step == "04" and s.walk == 1:
            _sv(v, "04").pool_open = True
            return "HALT(cap)"
        _sv(v, a.step).pool_open = False
        return "CONVERGED"

    verdict, _ = _drive(s, v, on_run)
    assert [x for x in seen if x[0] == 1] == [(1, st, "extend") for st in STEPS]
    assert [x for x in seen if x[0] == 2] == [(2, "04", "worklist")]
    assert verdict == "COMPLETE"


def test_the_operator_is_asked_once_between_the_walks_and_the_answer_is_applied():
    v = _view(s04=["gate_work", "open_items"])
    v.to_ask = True
    s = p.PassState(entry="range", surveyed=True)
    seen = []

    def on_run(a, v):
        seen.append((s.walk, a.step))
        sv = _sv(v, a.step)
        sv.gate_work = sv.item_work = False
        return "CONVERGED"

    def on_ask(v):
        _sv(v, "04").open_items, v.to_ask = False, False
        _sv(v, "02").item_work = True  # apply the decision at the step of the about node
        _sv(v, "04").item_work = True  # then do what waited, and delete the item

    verdict, log = _drive(s, v, on_run, on_ask)
    assert [a.type for a in log] == ["run", "ask", "run", "run", "done"]
    assert seen == [(1, "04"), (2, "02"), (2, "04")] and verdict == "COMPLETE"


def test_an_item_left_open_makes_the_pass_incomplete_and_starts_no_walk():
    v = _view(s04=["open_items"])
    v.to_ask = True
    s = p.PassState(entry="range", surveyed=True)
    verdict, log = _drive(s, v, lambda a, v: "CONVERGED")
    assert [a.type for a in log] == ["ask", "done"] and verdict == "INCOMPLETE"


def test_a_question_raised_in_the_second_walk_is_reported_not_asked():
    v = _view(s03=["pool_open"])
    s = p.PassState(entry="range", surveyed=True)

    def on_run(a, v):
        sv = _sv(v, a.step)
        if s.walk == 1:
            _sv(v, "02").pool_open = True
        else:
            sv.open_items, v.to_ask = True, True
        sv.pool_open = sv.step == "02" and s.walk == 1
        return "CONVERGED"

    verdict, log = _drive(s, v, on_run)
    assert "ask" not in [a.type for a in log] and verdict == "INCOMPLETE"


def test_a_step_that_cannot_be_authored_ends_the_walk_there():
    v = _view(s02=["has_artifact", "ready"], s03=["has_artifact"])
    s = p.PassState(entry="range")
    verdict, log = _drive(s, v, lambda a, v: "CLEAN" if a.step is None else "CONVERGED")
    assert [a.step for a in log if a.type == "run"] == [None]  # 02 is not ready: 03 is not tried
    assert verdict == "INCOMPLETE"


def test_authoring_from_seeds_walks_every_missing_step_in_order_with_no_survey():
    v = p.View(steps=[p.StepView(step=st, has_artifact=False) for st in STEPS])
    s = p.PassState(entry="range")

    def on_run(a, v):
        _sv(v, a.step).has_artifact = True
        return "CONVERGED"

    verdict, log = _drive(s, v, on_run)
    assert [(a.step, a.mode) for a in log if a.type == "run"] == [(st, "author") for st in STEPS]
    assert verdict == "COMPLETE"


def test_a_failed_run_ends_the_pass_and_retry_runs_that_step_again():
    v = _view(s02=["pool_open"], s03=["pool_open"])
    s = p.PassState(entry="range", surveyed=True)
    a = p.decide(s, v)
    p.record_run(s, "r1", a.step)
    p.record_verdict(s, "r1", "HALT(agent_failed)")
    assert p.decide(s, v).verdict == "HALT(agent_failed)"
    assert p.decide(s, v).verdict == "HALT(agent_failed)"
    a = p.decide(s, v, retry=True)
    assert (a.type, a.step) == ("run", "02")


def test_an_unfinished_run_is_resumed_before_anything_else():
    v = _view(s02=["pool_open"])
    s = p.PassState(entry="range", surveyed=True)
    a = p.decide(s, v)
    p.record_run(s, "r1", a.step)
    again = p.decide(s, v)
    assert (again.type, again.run_id) == ("run", "r1")


def test_a_stop_ends_the_pass():
    s = p.PassState(entry="range", stop=True)
    assert p.decide(s, _view()).verdict == "HALT(operator)"


def test_the_batch_is_asked_again_until_it_is_answered():
    v = _view(s04=["open_items"])
    v.to_ask = True
    s = p.PassState(entry="range", surveyed=True)
    assert [p.decide(s, v).type for _ in range(3)] == ["ask", "ask", "ask"]
    p.record_answered(s)
    assert p.decide(s, v).type == "done"


def test_a_walk_keeps_its_place_when_the_list_of_steps_changes():
    """A replay's steps are computed at every call: the walk goes on below the step it ran, by pipeline rank."""
    def view(steps):
        return p.View(steps=[p.StepView(step=st, rank=int(st), pool_open=st in ("03", "05", "07")) for st in steps])

    s = p.PassState(entry="replay", surveyed=True, survey_decided=True)
    first = p.decide(s, view(["03", "04", "05", "06", "07"]))
    assert first.step == "03"
    p.record_run(s, "r1", "03")
    p.record_verdict(s, "r1", "CONVERGED")
    assert p.decide(s, view(["05", "06", "07"])).step == "05"


def test_something_the_operator_kept_makes_the_pass_incomplete():
    v = _view()
    _sv(v, "04").kept = True
    s = p.PassState(entry="range", surveyed=True, survey_decided=True)
    assert p.decide(s, v).verdict == "INCOMPLETE"
