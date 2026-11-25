"""A seeded stand-in for the agents, the gate and the operator, to drive the run machine.

The simulated agents are deliberately bad: reviewers raise findings at random, fixers answer
at random and edit nodes nobody asked them to, entries go missing. The machine must reach a
verdict anyway, within its bounds.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from specdev_tools.loop import machine as m


@dataclass
class World:
    rng: random.Random
    state: m.RunState
    gate: dict[str, str] = field(default_factory=dict)  # blocking own errors: key -> target
    links: dict[str, tuple[str, str]] = field(default_factory=dict)  # key -> (holder, target hash)
    steps: int = 0
    fix_dispatches: list[int] = field(default_factory=list)  # rounds used at each fix dispatch
    review_dispatches: list[int] = field(default_factory=list)
    asks: int = 0
    lose: float = 0.1  # chance that an entry's file never arrives on a try
    defect: float = 0.25  # chance that a reviewer raises a finding on a node it reads
    good_fixer: float = 0.6  # chance that a fixer's answer is "fixed" and holds

    def bump(self, node: str) -> None:
        self.state.content[node] = str(int(self.state.content.get(node, "0")) + 1)


def make(seed: int, kind: str = "step", nodes: int = 6, **over) -> World:
    rng = random.Random(seed)
    s = m.RunState(kind=kind, readers=2 if kind == "step" else 1)
    for k, v in over.items():
        setattr(s, k, v)
    for i in range(nodes):
        s.content[f"n{i}"] = "0"
        s.cluster[f"n{i}"] = i % 2
    if s.mode == "extend":
        s.read = dict(s.content)
    w = World(rng=rng, state=s)
    if kind == "step":
        for i in range(rng.randint(0, 2)):
            w.gate[f"E5{i}0|n{i}"] = f"n{i}"
        for i in range(rng.randint(0, 2)):
            w.links[f"E763|n{i}|derives_from|up{i}"] = (f"n{i}", "0")
    if kind == "code-group" and rng.random() < 0.5:
        s.confirmations = {"a1": None}
    return w


def _review(w: World, d: m.Dispatch) -> None:
    s, rng = w.state, w.rng
    read = {n: s.content[n] for e in d.entries for n in e.nodes if n in s.content}
    raised = []
    for n in read:
        if rng.random() < w.defect:
            raised.append(
                {
                    "key": f"gap|{n}#f{rng.randint(0, 1)}",
                    "severity": rng.choice(["P0", "P1", "P1", "P2"]),
                    "target": n,
                    "in_scope": rng.random() < 0.9,
                }
            )
    judgements = {}
    for e in d.entries:
        for key in e.judge:
            f = s.findings[key]
            good = rng.random() < 0.7
            if f.status == m.AWAITING:
                judgements[key] = "resolved" if good else "not_resolved"
            else:
                judgements[key] = "decline_right" if good else "finding_right"
    m.apply_review(s, read, raised, judgements)


def _fix(w: World, d: m.Dispatch) -> None:
    s, rng = w.state, w.rng
    outcomes = {}
    for key in d.keys:
        f = s.findings[key]
        roll = rng.random()
        if f.source == m.GATE:
            if roll < w.good_fixer:
                w.gate.pop(key, None)
                w.bump(f.target)
            continue
        if f.source == m.LINK:
            if roll < w.good_fixer:
                w.links.pop(key, None)
                outcomes[key] = {"outcome": "accepted", "listed": False}
            elif roll < 0.9:
                outcomes[key] = {"outcome": "accepted", "listed": True}
            continue
        if roll < w.good_fixer:
            w.bump(f.target)
            outcomes[key] = {"outcome": "fixed", "changed": True}
        elif roll < 0.7:
            outcomes[key] = {"outcome": "fixed", "changed": False}
        elif roll < 0.8:
            outcomes[key] = {"outcome": "declined"}
        elif roll < 0.87:
            outcomes[key] = {"outcome": "recorded", "item_exists": rng.random() < 0.8}
        elif roll < 0.94:
            other = rng.choice(sorted(s.content))
            outcomes[key] = {
                "outcome": "upstream",
                "named": f"gap|{other}#up",
                "in_scope": rng.random() < 0.7,
                "target": other,
            }
        # else: no outcome for this key
    if rng.random() < 0.3:  # an edit nobody asked for
        w.bump(rng.choice(sorted(s.content)))
    if rng.random() < 0.15 and s.kind == "step":  # a fix that breaks the gate
        n = rng.choice(sorted(s.content))
        w.gate[f"E599|{n}"] = n
    if rng.random() < 0.15 and s.kind == "step":  # a fix that edits a link's target
        n = rng.choice(sorted(s.content))
        key = f"E763|{n}|refines|t{n}"
        old = w.links.get(key, (n, "0"))[1]
        w.links[key] = (n, str(int(old) + 1))
    m.apply_fix(s, outcomes)


def _take_in(w: World, d: m.Dispatch) -> None:
    s = w.state
    if d.role == "review":
        _review(w, d)
    elif d.role == "fix":
        _fix(w, d)
        if s.kind == "step":
            m.apply_gate(s, dict(w.gate), after_fix=True)
            m.apply_links(s, dict(w.links))
    else:
        s.start_done = True
        if s.mode != "extend" or w.rng.random() < 0.6:
            for n in sorted(s.content)[:2]:
                w.bump(n)
        if s.kind == "step":
            m.apply_gate(s, dict(w.gate))
            m.apply_links(s, dict(w.links))
    m.close_dispatch(s)


def run(w: World, limit: int = 400) -> str:
    """Drive the run to a verdict; raises when it does not end within ``limit`` actions."""
    s, rng = w.state, w.rng
    if s.kind == "step" and s.mode not in ("author",):
        m.apply_gate(s, dict(w.gate))
        m.apply_links(s, dict(w.links))
    redispatch = False
    while True:
        w.steps += 1
        if w.steps > limit:
            raise AssertionError(f"no verdict after {limit} actions")
        a = m.decide(s, redispatch=redispatch)
        redispatch = False
        if a.type == "done":
            return a.verdict or ""
        if a.type == "dispatch":
            d = s.dispatch
            assert d is not None
            if d.role == "fix" and a.entries[0].tries == 1:
                w.fix_dispatches.append(s.rounds_used)
            if d.role == "review" and all(e.tries == 1 for e in a.entries):
                w.review_dispatches.append(s.rounds_used)
            for e in a.entries:
                if rng.random() >= w.lose:
                    e.arrived = True
            if m.complete(d):
                _take_in(w, d)
        elif a.type == "wait":
            redispatch = True
        elif a.type == "ask":
            w.asks += 1
            if a.ask == "cap":
                m.apply_answers(s, {"cap": rng.choice(["2", "stop"])})
            elif a.ask == "confirm":
                m.apply_answers(s, {k: rng.choice(["yes", "no"]) for k in a.keys})
            else:
                m.apply_answers(s, {k: rng.choice(["again", "leave", "again", "stop"]) for k in a.keys})
