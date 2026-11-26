"""The run machine (``specdev_tools.loop.machine``): its bounds, its verdicts, and the
scenarios the design reviews walked by hand."""

from __future__ import annotations

import pytest

from specdev_tools.loop import machine as m

from . import _sim

SEEDS = range(400)


def _blocking_left(s: m.RunState) -> list[m.Finding]:
    return m.with_status(s, m.OPEN, m.AWAITING, m.CONTESTED, m.PARKED)


# ----------------------------------------------------------------- properties


@pytest.mark.parametrize("kind", ["step", "plan", "code-group", "code-milestone"])
@pytest.mark.parametrize("mode", [None, "author", "extend", "review-only"])
def test_every_run_reaches_a_verdict_and_keeps_its_promises(kind, mode):
    if kind.startswith("code") and mode in ("author", "extend"):
        mode = "execute" if kind == "code-group" else None
    for seed in SEEDS:
        w = _sim.make(seed, kind=kind, mode=mode, defer=seed % 3 == 0)
        verdict = _sim.run(w)
        s = w.state
        assert verdict in (
            "CONVERGED", "CLEAN", "FINDINGS", "HALT(cap)", "HALT(stuck)",
            "HALT(agent_failed)", "HALT(operator)", "HALT(blocked)",
        ), (seed, verdict)
        if verdict == "CONVERGED":
            assert not _blocking_left(s), (seed, [f.key for f in _blocking_left(s)])
            assert not m.unread(s), (seed, m.unread(s))
            # after partial rounds the whole scope was read once more, unless the cap left no round for it
            assert s.rounds_used <= 1 or s.final_read or s.rounds_used >= s.cap or s.full_read == m._reviewed(s), seed
        if verdict == "HALT(stuck)":
            assert s.defer and m.with_status(s, m.PARKED)
            assert not m.with_status(s, m.OPEN, m.AWAITING, m.CONTESTED), seed
        if s.defer and kind in m.SPEC_KINDS:
            assert w.asks == 0, seed  # a deferred spec run never asks
        # a fix is always reviewed: no fix pass is handed out at the cap
        assert all(r < s.cap for r in w.fix_dispatches), seed
        assert all(r < s.cap for r in w.review_dispatches), seed
        # no more than three fix passes between two rounds
        for r in set(w.fix_dispatches):
            assert w.fix_dispatches.count(r) <= m.MAX_FIX_STREAK + w.asks, seed


def test_spec_runs_never_exceed_the_cap():
    for seed in SEEDS:
        w = _sim.make(seed, cap=3)
        _sim.run(w)
        assert w.state.rounds_used <= 3, seed


def test_review_only_spends_one_round_and_fixes_nothing():
    seen: dict[str, int] = {}
    for seed in SEEDS:
        w = _sim.make(seed, mode="review-only")
        verdict = _sim.run(w)
        assert verdict in ("CLEAN", "FINDINGS", "HALT(agent_failed)", "HALT(operator)"), (seed, verdict)  # never a fix verdict
        assert w.state.rounds_used <= 1 and not w.fix_dispatches, seed
        seen[verdict] = seen.get(verdict, 0) + 1
        if not verdict.startswith("HALT"):
            assert w.state.rounds_used == 1, seed
            assert (verdict == "CLEAN") == (not m.with_status(w.state, m.OPEN, m.PARKED)), seed
    assert seen.get("CLEAN") and seen.get("FINDINGS"), seen  # both ends are reached, so the checks above ran


# ----------------------------------------------------------------- scenarios


def _state(**over) -> m.RunState:
    s = m.RunState(**{"readers": 2, **over})
    s.content = {"a": "0", "b": "0", "c": "0"}
    return s


def _arrive(s: m.RunState) -> m.Dispatch:
    d = s.dispatch
    assert d is not None
    for e in d.entries:
        e.arrived = True
    return d


def _round(s, raised=(), judgements=None):
    a = m.decide(s)
    assert a.type == "dispatch" and s.dispatch.role == "review", a
    d = _arrive(s)
    read = {n: s.content[n] for e in d.entries for n in e.nodes}
    m.apply_review(s, read, [dict(r) for r in raised], dict(judgements or {}))
    m.close_dispatch(s)
    return d


def _fix(s, outcomes, edits=()):
    a = m.decide(s)
    assert a.type == "dispatch" and s.dispatch.role == "fix", a
    d = _arrive(s)
    for n in edits:
        s.content[n] = str(int(s.content[n]) + 1)
    m.apply_fix(s, outcomes)
    m.close_dispatch(s)
    return d


def _f(key, target, sev="P1", in_scope=True):
    return {"key": key, "severity": sev, "target": target, "in_scope": in_scope}


def test_one_step_two_fixes_one_upheld_decline_converges_in_three_rounds():
    s = _state()
    d = _round(s, [_f("gap|a", "a"), _f("gap|b", "b"), _f("gap|c", "c"), _f("style|a", "a", "P2")])
    assert len(d.entries) == 2  # two readers on a first read
    _fix(s, {"gap|a": {"outcome": "fixed", "changed": True},
             "gap|b": {"outcome": "fixed", "changed": True},
             "gap|c": {"outcome": "declined"}}, edits=["a", "b"])
    assert m.unread(s) == ["a", "b"]
    d = _round(s, [_f("gap|b#new", "b")],
               {"gap|a": "resolved", "gap|b": "resolved", "gap|c": "finding_right"})
    assert len(d.entries) == 1 and sorted(d.entries[0].nodes) == ["a", "b"]  # only what changed
    assert s.findings["gap|c"].status == m.OPEN and s.findings["gap|c"].no_decline
    assert s.findings["gap|c"].attempts == 0  # an upheld decline is not an attempt
    _fix(s, {"gap|c": {"outcome": "fixed", "changed": True},
             "gap|b#new": {"outcome": "fixed", "changed": True}}, edits=["b", "c"])
    _round(s, [], {"gap|c": "resolved", "gap|b#new": "resolved"})
    d = _round(s)  # the full re-read: one reviewer, every node, whatever was read before
    assert [e.id for e in d.entries] == ["full0"] and sorted(d.entries[0].nodes) == sorted(s.content)
    assert m.decide(s).verdict == "CONVERGED"
    assert s.rounds_used == 4 and s.notes == ["style|a"]


def test_a_clean_first_round_converges_at_once():
    s = _state()
    _round(s)
    assert m.decide(s).verdict == "CONVERGED" and s.rounds_used == 1


def test_extend_with_nothing_to_add_spends_no_round():
    s = _state(mode="extend")
    s.read = dict(s.content)
    assert m.decide(s).entries[0].agent == "author"
    _arrive(s)
    s.start_done = True
    m.close_dispatch(s)
    assert m.decide(s).verdict == "CONVERGED" and s.rounds_used == 0


def test_extend_reads_only_what_it_added():
    s = _state(mode="extend")
    s.read = dict(s.content)
    m.decide(s)
    _arrive(s)
    s.start_done, s.content["d"] = True, "0"
    m.close_dispatch(s)
    d = _round(s)
    assert [e.nodes for e in d.entries] == [["d"], ["d"]]  # a node nobody has read: two readers


def test_a_finding_is_parked_after_two_failed_attempts_and_deferred_runs_do_not_ask():
    s = _state(defer=True)
    _round(s, [_f("gap|a", "a")])
    _fix(s, {"gap|a": {"outcome": "fixed", "changed": False}})
    _fix(s, {})
    assert s.findings["gap|a"].status == m.PARKED
    assert m.decide(s).verdict == "HALT(stuck)"


def test_the_operator_is_asked_last_and_guidance_gives_one_more_attempt():
    s = _state()
    _round(s, [_f("gap|a", "a"), _f("gap|b", "b")])
    _fix(s, {"gap|b": {"outcome": "fixed", "changed": True}}, edits=["b"])
    _fix(s, {})  # gap|a fails twice
    a = m.decide(s)
    assert a.type == "dispatch" and _arrive(s).role == "review"  # the round comes before the question
    m.apply_review(s, {"b": s.content["b"]}, [], {"gap|b": "resolved"})
    m.close_dispatch(s)
    a = m.decide(s)
    assert a.type == "ask" and a.keys == ["gap|a"]
    m.apply_answers(s, {"gap|a": "again"})
    _fix(s, {})
    assert s.findings["gap|a"].status == m.PARKED
    m.decide(s)
    m.apply_answers(s, {"gap|a": "leave"})
    assert _round(s).entries[0].id == "full0"
    assert m.decide(s).verdict == "CONVERGED"


def test_the_full_re_read_happens_once_and_never_past_the_cap():
    s = _state()
    _round(s, [_f("gap|a", "a")])
    _fix(s, {"gap|a": {"outcome": "fixed", "changed": True}}, edits=["a"])
    _round(s, [], {"gap|a": "resolved"})
    _round(s, [_f("gap|b", "b")])  # the full re-read finds something
    assert s.final_read
    _fix(s, {"gap|b": {"outcome": "fixed", "changed": True}}, edits=["b"])
    _round(s, [], {"gap|b": "resolved"})
    assert m.decide(s).verdict == "CONVERGED" and s.rounds_used == 4  # no second full re-read
    s = _state(cap=2)
    _round(s, [_f("gap|a", "a")])
    _fix(s, {"gap|a": {"outcome": "fixed", "changed": True}}, edits=["a"])
    _round(s, [], {"gap|a": "resolved"})
    assert m.decide(s).verdict == "CONVERGED" and not s.final_read  # at the cap: no round is left for it
    s = _state()
    s.read = {"c": "0"}  # counted as read from the start (--extend, --about, a carried read-record)
    _round(s, [_f("gap|a", "a")])
    _fix(s, {"gap|a": {"outcome": "fixed", "changed": True}}, edits=["a"])
    _round(s, [], {"gap|a": "resolved"})
    assert sorted(_round(s).entries[0].nodes) == ["a", "b"]  # the re-read keeps to what the run reviews
    assert m.decide(s).verdict == "CONVERGED"


def test_a_finding_left_as_is_is_parked_not_reopened_when_raised_again():
    s = _state()
    _round(s, [_f("gap|a", "a")])
    _fix(s, {})
    _fix(s, {})
    m.decide(s)
    m.apply_answers(s, {"gap|a": "leave"})
    s.content["a"] = "9"
    _round(s, [_f("gap|a", "a")])
    assert s.findings["gap|a"].status == m.PARKED


def test_a_settled_finding_is_not_raised_again_unless_its_target_changed():
    s = _state()
    _round(s, [_f("gap|a", "a")])
    _fix(s, {"gap|a": {"outcome": "declined"}})
    _round(s, [], {"gap|a": "decline_right"})
    s.content["b"] = "1"
    _round(s, [_f("gap|a", "a")])
    assert s.findings["gap|a"].status == m.SETTLED
    s.content["a"] = "1"
    _round(s, [_f("gap|a", "a")])
    assert s.findings["gap|a"].status == m.OPEN


def test_a_finding_with_an_instruction_cannot_be_declined():
    s = _state()
    _round(s, [_f("gap|a", "a")])
    _fix(s, {"gap|a": {"outcome": "declined"}})
    _round(s, [], {"gap|a": "finding_right"})
    _fix(s, {"gap|a": {"outcome": "declined"}})
    assert s.findings["gap|a"].attempts == 1 and s.findings["gap|a"].status == m.OPEN


def test_a_choice_without_a_checked_basis_is_not_a_fix():
    s = _state()
    _round(s, [_f("gap|a", "a")])
    _fix(s, {"gap|a": {"outcome": "fixed", "changed": True, "basis_ok": False}}, edits=["a"])
    assert s.findings["gap|a"].status == m.OPEN and s.findings["gap|a"].attempts == 1


def test_recording_an_open_item_settles_only_when_the_item_exists():
    s = _state()
    _round(s, [_f("gap|a", "a"), _f("gap|b", "b")])
    _fix(s, {"gap|a": {"outcome": "recorded", "item_exists": True},
             "gap|b": {"outcome": "recorded", "item_exists": False}})
    assert s.findings["gap|a"].status == m.SETTLED
    assert s.findings["gap|b"].status == m.OPEN and s.findings["gap|b"].attempts == 1


def test_a_finding_about_another_step_is_a_handoff_and_never_blocks():
    s = _state()
    _round(s, [_f("gap|up", "up", in_scope=False)])
    assert s.handoffs == ["gap|up"] and m.decide(s).verdict == "CONVERGED"


def test_upstream_back_and_forth_ends_at_the_operator():
    s = _state(defer=True)
    _round(s, [_f("gap|a", "a")])
    _fix(s, {"gap|a": {"outcome": "upstream", "named": "gap|b", "in_scope": True, "target": "b"}})
    assert s.findings["gap|a"].status == m.SETTLED and s.findings["gap|b"].status == m.OPEN
    assert s.findings["gap|b"].attempts == 0
    _fix(s, {"gap|b": {"outcome": "upstream", "named": "gap|a", "in_scope": True, "target": "a"}})
    assert s.findings["gap|a"].status == m.PARKED
    assert m.decide(s).verdict == "HALT(stuck)"


def test_an_upstream_target_outside_the_scope_is_a_handoff():
    s = _state()
    _round(s, [_f("gap|a", "a")])
    _fix(s, {"gap|a": {"outcome": "upstream", "named": "gap|up", "in_scope": False}})
    assert s.handoffs == ["gap|up"] and m.decide(s).verdict == "CONVERGED"


def test_only_the_gate_moves_a_gate_finding():
    s = _state()
    m.apply_gate(s, {"E500|a": "a"})
    m.decide(s)
    d = _arrive(s)
    assert d.role == "fix" and d.keys == ["E500|a"]  # the gate before any review
    m.apply_fix(s, {"E500|a": {"outcome": "fixed", "changed": True}})
    m.apply_gate(s, {"E500|a": "a"}, after_fix=True)  # the fixer said fixed; the gate says no
    m.close_dispatch(s)
    assert s.findings["E500|a"].status == m.OPEN and s.findings["E500|a"].attempts == 1
    m.decide(s)
    _arrive(s)
    m.apply_fix(s, {})
    m.apply_gate(s, {}, after_fix=True)
    m.close_dispatch(s)
    assert s.findings["E500|a"].status == m.RESOLVED
    m.apply_gate(s, {"E500|a": "a"})  # it comes back
    assert s.findings["E500|a"].status == m.PARKED  # two fixes that undo each other


def test_a_link_is_accepted_then_judged_and_a_new_change_starts_at_zero():
    s = _state()
    key = "E763|a|derives_from|up"
    m.apply_links(s, {key: ("a", "h1")})
    m.decide(s)
    _arrive(s)
    m.apply_fix(s, {key: {"outcome": "accepted", "listed": False}})
    m.apply_links(s, {})
    m.close_dispatch(s)
    assert s.findings[key].status == m.AWAITING
    _round(s, [], {key: "not_resolved"})  # the acceptance was wrong
    assert s.findings[key].status == m.OPEN and s.findings[key].attempts == 1
    m.apply_links(s, {key: ("a", "h2")})  # the target changed again
    assert s.findings[key].attempts == 0


def test_a_link_still_listed_after_the_fix_is_an_attempt():
    s = _state()
    key = "E763|a|derives_from|up"
    m.apply_links(s, {key: ("a", "h1")})
    m.decide(s)
    _arrive(s)
    m.apply_fix(s, {key: {"outcome": "accepted", "listed": True}})
    m.close_dispatch(s)
    assert s.findings[key].status == m.OPEN and s.findings[key].attempts == 1


def test_a_fixer_that_keeps_breaking_things_is_stopped_after_three_passes():
    s = _state(defer=True)
    _round(s)
    for i in range(3):
        m.apply_links(s, {f"E763|a|f|t{i}": ("a", "h")})
        _fix(s, {})
    assert not m.with_status(s, m.OPEN)
    assert m.decide(s).verdict == "HALT(stuck)"


def test_a_spec_run_halts_at_the_cap_and_a_code_run_asks():
    s = _state(cap=1)
    _round(s, [_f("gap|a", "a")])
    assert m.decide(s).verdict == "HALT(cap)"
    s = _state(cap=1, kind="code-milestone")
    _round(s, [_f("gap|a", "a")])
    assert m.decide(s).ask == "cap"
    m.apply_answers(s, {"cap": "2"})
    assert s.cap == 3 and m.decide(s).type == "dispatch"


def test_an_entry_that_fails_twice_ends_the_run_and_a_refusal_ends_it_at_once():
    s = _state()
    m.decide(s)
    assert m.decide(s).type == "wait"
    assert m.decide(s, redispatch=True).type == "dispatch"
    assert m.decide(s, redispatch=True).verdict == "HALT(agent_failed)"
    s = _state(mode="author")
    m.decide(s)
    s.refusal = "the artifact already exists"
    assert m.decide(s).verdict == "HALT(agent_failed)"


def test_a_round_is_handed_out_one_wave_at_a_time_and_merged_only_when_whole():
    s = _state(wave=1)
    s.cluster = {"a": 0, "b": 1, "c": 1}
    a = m.decide(s)
    d = s.dispatch
    assert d is not None and len(a.entries) == 1 and len(d.entries) == 4
    assert m.decide(s).type == "wait"
    a.entries[0].arrived = True
    assert m.decide(s).type == "dispatch"
    assert not m.complete(d)


def test_a_code_run_with_an_open_item_in_the_way_is_blocked_not_converged():
    s = _state(kind="code-milestone", readers=1)
    s.plan_blocked = True
    _round(s)
    assert m.decide(s).verdict == "HALT(blocked)"


def test_manual_verification_is_asked_before_anything_else_in_a_code_group():
    s = _state(kind="code-group", mode="execute", readers=1)
    m.decide(s)
    _arrive(s)
    s.start_done, s.confirmations = True, {"act-1": None}
    m.close_dispatch(s)
    a = m.decide(s)
    assert a.ask == "confirm" and a.keys == ["act-1"]
    m.apply_answers(s, {"act-1": "no"})
    assert m.decide(s).type == "dispatch"


def test_a_stop_ends_the_run():
    s = _state()
    m.decide(s)
    s.stop = True
    assert m.decide(s).verdict == "HALT(operator)"
    assert m.decide(s).verdict == "HALT(operator)"


def test_a_link_the_fixer_accepted_without_a_checked_outcome_is_judged_not_closed():
    s = _state()
    key = "E763|a|derives_from|up"
    m.apply_links(s, {key: ("a", "h1")})
    m.decide(s)
    for e in s.dispatch.entries:
        e.arrived = True
    m.apply_fix(s, {})  # the fixer ran `attest` and wrote no outcome for the link
    m.apply_links(s, {})
    m.close_dispatch(s)
    assert s.findings[key].status == m.AWAITING
    assert m.decide(s).type == "dispatch" and s.dispatch.role == "review"


def test_a_link_accepted_by_hand_between_calls_is_closed():
    s = _state()
    key = "E763|a|derives_from|up"
    m.apply_links(s, {key: ("a", "h1")})
    m.apply_links(s, {})  # no fix dispatch is open: a person accepted it
    assert s.findings[key].status == m.RESOLVED
