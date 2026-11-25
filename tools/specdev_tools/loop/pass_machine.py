"""The pass machine of ``specdev pass``: which run comes next when several steps are involved.

This module does no I/O. The caller computes a :class:`View` from the spec and the run
folders at every call; the machine keeps only what cannot be computed: the entry, the walk
it is in, which step each walk has reached, and whether the operator was asked. The rule of
:func:`decide` is the table of section 8.3 of the agent harness design.

"A step has work" is always read from the view, never from a list the pass keeps, so the
pass cannot disagree with the state of the spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_WALKS = 2
FAILED = ("HALT(agent_failed)", "HALT(operator)")


@dataclass
class StepView:
    step: str
    has_artifact: bool = True
    ready: bool = True  # `specdev step ready NN`, asked only before authoring
    pool_open: bool = False  # a pool finding about one of its nodes is not closed
    link_work: bool = False  # a suspect link it could accept, not kept by the operator
    gate_work: bool = False  # an own blocking gate error, not kept by the operator
    item_work: bool = False  # an answered open item it holds, or that is about its node
    open_items: bool = False  # it holds an open item with no decision
    suspect: bool = False  # it holds any suspect link at all
    kept: bool = False  # the operator kept an open item, a gate error or a link of it: not complete
    rank: int = -1  # its place in the pipeline's order; -1: its index in the view


@dataclass
class View:
    steps: list[StepView] = field(default_factory=list)  # the steps of the pass, in order
    to_ask: bool = False  # the batch has at least one item
    pool_unclosed: bool = False  # a pool finding of a step of the pass is not closed


@dataclass
class RunRef:
    run_id: str
    step: str | None  # None: the survey
    walk: int  # 0: the survey
    verdict: str | None = None


@dataclass
class PassState:
    entry: str = "range"  # range | extend | review | replay
    stop: bool = False
    verdict: str | None = None
    surveyed: bool = False
    survey_decided: bool = False
    walk: int = 1
    reached: int = -1  # the pipeline rank of the last step this walk ran (the view's steps change between calls)
    walk_ended: bool = False
    asked: bool = False
    runs: list[RunRef] = field(default_factory=list)


@dataclass
class PassAction:
    type: str  # run | ask | done
    step: str | None = None
    steps: list[str] = field(default_factory=list)
    mode: str | None = None  # review-only | author | extend | worklist
    run_id: str | None = None
    verdict: str | None = None


def has_work(sv: StepView, s: PassState) -> bool:
    """One of the six kinds of work of section 8.3."""
    return (
        not sv.has_artifact
        or (s.entry == "extend" and s.walk == 1)
        or sv.pool_open
        or sv.link_work
        or sv.gate_work
        or sv.item_work
    )


def _mode(sv: StepView, s: PassState) -> str:
    if not sv.has_artifact:
        return "author"
    if s.entry == "extend" and s.walk == 1:
        return "extend"
    return "worklist"


def _complete(v: View, s: PassState) -> bool:
    return (
        all(sv.has_artifact for sv in v.steps)
        and not any(has_work(sv, s) for sv in v.steps)
        and not v.pool_unclosed
        and not any(sv.open_items for sv in v.steps)
        and not any(sv.suspect for sv in v.steps)
        and not any(sv.kept for sv in v.steps)
    )


def _done(s: PassState, verdict: str) -> PassAction:
    s.verdict = verdict
    return PassAction(type="done", verdict=verdict)


def record_run(s: PassState, run_id: str, step: str | None) -> None:
    """The caller started the run a ``run`` action named."""
    s.runs.append(RunRef(run_id=run_id, step=step, walk=0 if step is None else s.walk))
    if step is None:
        s.surveyed = True


def record_answered(s: PassState) -> None:
    """The caller applied the operator's answers and no question of the batch is left."""
    s.asked = True


def _rank(sv: StepView, index: int) -> int:
    return sv.rank if sv.rank >= 0 else index


def record_verdict(s: PassState, run_id: str, verdict: str) -> None:
    for r in s.runs:
        if r.run_id == run_id:
            r.verdict = verdict


def decide(s: PassState, v: View, retry: bool = False) -> PassAction:
    """The next action of a pass: the first row of section 8.3 that fits."""
    if s.verdict is not None and not (retry and s.verdict in FAILED):
        return PassAction(type="done", verdict=s.verdict)
    if retry and s.verdict in FAILED:
        s.stop, s.verdict = False, None  # the pass was stopped or a run of it failed, and the operator goes on
    # 1
    if s.stop:
        return _done(s, "HALT(operator)")
    # 2
    if s.runs:
        last = s.runs[-1]
        if last.verdict is None:
            return PassAction(type="run", run_id=last.run_id, step=last.step)
        if last.verdict in FAILED:
            if not retry:
                return _done(s, last.verdict)
            s.verdict = None
            s.runs.pop()
            if last.step is None:
                s.surveyed = s.survey_decided = False
            else:
                s.reached = _index(v, last.step) - 1
    # 3
    if not s.survey_decided:  # once, before the first walk: later artifacts are read by their own run
        s.survey_decided = True
        existing = [sv.step for sv in v.steps if sv.has_artifact]
        if s.entry in ("range", "review", "replay") and existing and not s.surveyed:
            return PassAction(type="run", steps=existing, mode="review-only")
    # 4
    if not s.walk_ended:
        for i, sv in enumerate(v.steps):
            if _rank(sv, i) <= s.reached or not has_work(sv, s):
                continue
            mode = _mode(sv, s)
            if mode == "author" and not sv.ready:
                break  # the walk ends at this step
            s.reached = _rank(sv, i)
            return PassAction(type="run", step=sv.step, mode=mode)
        s.walk_ended = True
    # 5
    if s.walk < MAX_WALKS and not s.asked and v.to_ask:
        return PassAction(type="ask")  # asked again until the caller says it was answered (record_answered)
    # 6
    if s.walk < MAX_WALKS:
        s.walk += 1
        s.reached, s.walk_ended = -1, False
        if any(has_work(sv, s) for sv in v.steps):
            return decide(s, v)
    # 7
    return _done(s, "COMPLETE" if _complete(v, s) else "INCOMPLETE")


def _index(v: View, step: str) -> int:
    for i, sv in enumerate(v.steps):
        if sv.step == step:
            return _rank(sv, i)
    return 0
