"""The run machine of ``specdev loop``: state in, one action out.

This module does no I/O. The caller reads the files of a run, turns them into the plain
values the ``apply_*`` functions take, and then asks :func:`decide` what comes next. The
rule of :func:`decide` is the table of section 6.3 of the agent harness design
(``docs/architecture/agent-harness/agent_harness_design.md``); the two are kept the same.

A blocking finding has one of six statuses. Only ``open`` findings go to the fixer, only
``awaiting`` and ``contested`` findings are judged by a reviewer, and only ``parked``
findings reach the operator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

OPEN = "open"
AWAITING = "awaiting"
CONTESTED = "contested"
PARKED = "parked"
RESOLVED = "resolved"
SETTLED = "settled"

REVIEW = "review"  # raised by a reviewer
GATE = "gate"  # an own blocking error of the step gate
LINK = "link"  # a suspect link the scope holds and could accept

SPEC_KINDS = ("step", "plan")
CODE_KINDS = ("code-group", "code-milestone")
START_MODES = ("author", "extend", "execute")

MAX_ATTEMPTS = 2
MAX_TRIES = 2
MAX_FIX_STREAK = 3
"""Fix passes in a row with no round between them. Two attempts need two; the third lets a
fix that itself raised a gate or link finding be answered once. After that, whatever is
still open is parked, so a fixer that keeps undoing its own work ends at the operator."""

BLOCKING = ("P0", "P1")


@dataclass
class Finding:
    key: str
    source: str = REVIEW
    status: str = OPEN
    attempts: int = 0
    target: str = ""
    instruction: str = ""
    no_decline: bool = False
    left_as_is: bool = False
    settled_hash: str | None = None
    target_hash: str | None = None  # link findings: the target's content when listed
    from_upstream: bool = False  # this key was the source of an ``upstream`` re-target


@dataclass
class Entry:
    id: str
    agent: str
    nodes: list[str] = field(default_factory=list)
    judge: list[str] = field(default_factory=list)
    tries: int = 0
    handed_out: bool = False
    arrived: bool = False


@dataclass
class Dispatch:
    role: str  # review | fix | author | execute
    entries: list[Entry] = field(default_factory=list)
    keys: list[str] = field(default_factory=list)  # fix: the findings handed to the fixer


@dataclass
class RunState:
    kind: str = "step"
    mode: str | None = None  # author | extend | execute | review-only | worklist | None
    defer: bool = False
    cap: int = 5
    readers: int = 2
    wave: int = 6
    rounds_used: int = 0
    fix_streak: int = 0
    stop: bool = False
    verdict: str | None = None
    start_done: bool = False  # the author or executor outcome with a result has arrived
    refusal: str | None = None
    plan_blocked: bool = False  # code kinds: an open item of the plan is in the way
    dispatch: Dispatch | None = None
    dispatches: int = 0
    findings: dict[str, Finding] = field(default_factory=dict)
    read: dict[str, str] = field(default_factory=dict)  # the read-record: node -> hash read
    content: dict[str, str] = field(default_factory=dict)  # node -> hash now
    cluster: dict[str, int] = field(default_factory=dict)  # node -> reviewer cluster
    confirmations: dict[str, str | None] = field(default_factory=dict)  # code-group
    notes: list[str] = field(default_factory=list)
    handoffs: list[str] = field(default_factory=list)
    pending_ask: str | None = None  # parked | cap | confirm
    final_read: bool = False  # the one full re-read before CONVERGED was handed out
    full_read: dict[str, str] | None = None  # the content when one round last read everything in ``seen``
    seen: list[str] = field(default_factory=list)  # what a reviewer of this run was given to read, ever


@dataclass
class Action:
    type: str  # dispatch | wait | ask | done
    entries: list[Entry] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    ask: str | None = None
    keys: list[str] = field(default_factory=list)
    verdict: str | None = None


# --------------------------------------------------------------------------- views


def unread(s: RunState) -> list[str]:
    """The nodes whose content now differs from what a reviewer last read."""
    return sorted(n for n, h in s.content.items() if s.read.get(n) != h)


def with_status(s: RunState, *statuses: str) -> list[Finding]:
    return [f for f in s.findings.values() if f.status in statuses]


def _is_spec(s: RunState) -> bool:
    return s.kind in SPEC_KINDS


def _park_exhausted(s: RunState) -> None:
    streak_used = s.fix_streak >= MAX_FIX_STREAK
    for f in s.findings.values():
        if f.status == OPEN and (f.attempts >= MAX_ATTEMPTS or streak_used):
            f.status = PARKED


def _fail(f: Finding) -> None:
    f.status = OPEN
    f.attempts += 1


# --------------------------------------------------------------------------- intake


def apply_gate(s: RunState, blocking: dict[str, str], after_fix: bool = False) -> None:
    """Take a gate run. ``blocking`` maps the key of each own blocking error to its target.

    Only the gate moves a gate finding: gone from ``blocking`` it is resolved, still there
    after a fix pass it has one more attempt, back after it was resolved the same.
    """
    for key, target in blocking.items():
        f = s.findings.get(key)
        if f is None:
            s.findings[key] = Finding(key=key, source=GATE, target=target)
        elif f.source != GATE:
            continue
        elif f.status == RESOLVED:
            _fail(f)
        elif f.status == OPEN and after_fix and key in _handed(s):
            f.attempts += 1
    for f in s.findings.values():
        if f.source == GATE and f.key not in blocking and f.status in (OPEN, PARKED):
            f.status = RESOLVED
    _park_exhausted(s)


def apply_links(s: RunState, listed: dict[str, tuple[str, str]]) -> None:
    """Take a ``specdev stale`` run. ``listed`` maps each link finding's key (holder, field
    and target) to ``(holder, target content hash)``: the links the scope could accept.

    A link that is listed again after its target changed again is a new finding and starts
    at zero; listed again with the target unchanged, it is an attempt.
    """
    for key, (holder, target_hash) in listed.items():
        f = s.findings.get(key)
        if f is None:
            s.findings[key] = Finding(key=key, source=LINK, target=holder, target_hash=target_hash)
        elif f.source != LINK:
            continue
        elif f.target_hash != target_hash:
            if f.status != PARKED or not f.left_as_is:
                f.status, f.attempts = OPEN, 0
                f.instruction, f.no_decline = "", False
            f.target_hash = target_hash
        elif f.status in (RESOLVED, AWAITING):
            _fail(f)
    handed = _handed(s)
    for f in s.findings.values():
        if f.source == LINK and f.key not in listed and f.status in (OPEN, PARKED):
            # accepted by the fixer of this dispatch without a checked outcome: a reviewer judges it;
            # otherwise it was accepted or edited by hand
            f.status = AWAITING if f.key in handed else RESOLVED
    _park_exhausted(s)


def _handed(s: RunState) -> list[str]:
    return s.dispatch.keys if s.dispatch and s.dispatch.role == "fix" else []


def apply_fix(s: RunState, outcomes: dict[str, dict[str, Any]]) -> None:
    """Take a fixer's outcome file, one entry per key it was handed.

    Each entry carries ``outcome`` and what the caller checked for it:
    ``changed`` (a named thing's hash changed), ``basis_ok`` (the basis quote occurs in its
    source, or none was needed), ``item_exists`` (the recorded open item is there),
    ``listed`` (a link is still in ``specdev stale``), and for ``upstream`` the ``named``
    key with ``in_scope``.
    """
    s.fix_streak += 1
    for key in _handed(s):
        f = s.findings.get(key)
        if f is None or f.status != OPEN or f.source == GATE:
            continue  # the gate alone moves a gate finding (apply_gate, after this)
        o = outcomes.get(key, {})
        kind = o.get("outcome")
        if f.source == LINK:
            done = kind in ("accepted", "fixed") and not o.get("listed", True)
            if done and (kind == "accepted" or o.get("changed")):
                f.status = AWAITING
            elif kind == "recorded" and o.get("item_exists"):
                f.status = SETTLED
            else:
                _fail(f)
        elif kind == "fixed":
            if o.get("changed") and o.get("basis_ok", True):
                f.status = AWAITING
            else:
                _fail(f)
        elif kind == "declined":
            if f.no_decline or f.instruction:
                _fail(f)
            else:
                f.status = CONTESTED
        elif kind == "recorded":
            if o.get("item_exists"):
                f.status, f.settled_hash = SETTLED, s.content.get(f.target)
            else:
                _fail(f)
        elif kind == "upstream" and o.get("named"):
            _retarget(s, f, o["named"], bool(o.get("in_scope")), o.get("target", ""))
        else:
            _fail(f)
    _park_exhausted(s)


def _retarget(s: RunState, f: Finding, named: str, in_scope: bool, target: str) -> None:
    f.status, f.settled_hash, f.from_upstream = SETTLED, s.content.get(f.target), True
    other = s.findings.get(named)
    if other is not None and other.from_upstream:
        other.status = PARKED  # sent there and back: the operator decides
        return
    if not in_scope and _is_spec(s):
        if named not in s.handoffs:
            s.handoffs.append(named)
        return
    if other is None:
        s.findings[named] = Finding(key=named, target=target)
    elif other.status in (RESOLVED, SETTLED):
        other.status = OPEN


def apply_review(
    s: RunState,
    read: dict[str, str],
    raised: list[dict[str, Any]],
    judgements: dict[str, str],
) -> None:
    """Take a merged round.

    ``read`` is what every reader of a cluster listed as read, with the hash it was given.
    ``raised`` holds the accepted findings, merged by key: ``key``, ``severity``,
    ``target`` and ``in_scope``. ``judgements`` maps a key to ``resolved``,
    ``not_resolved``, ``decline_right`` or ``finding_right``.
    """
    s.rounds_used += 1
    s.fix_streak = 0
    s.read.update(read)
    s.seen = sorted(set(s.seen) | set(read))
    if set(_reviewed(s)) <= set(read):
        s.full_read = {n: read[n] for n in _reviewed(s)}
    for r in raised:
        key = r["key"]
        f = s.findings.get(key)
        blocking = r.get("severity") in BLOCKING
        if f is not None and f.status == SETTLED and f.settled_hash == s.content.get(f.target):
            continue  # already known
        if f is not None and f.status == PARKED or key in s.handoffs:
            continue  # already known
        if f is not None and f.status in (AWAITING, CONTESTED) and blocking:
            judgements[key] = "not_resolved" if f.status == AWAITING else "finding_right"
            continue
        if not blocking:
            s.notes.append(key)
            continue
        if _is_spec(s) and not r.get("in_scope", True):
            s.handoffs.append(key)
            continue
        if f is None:
            s.findings[key] = Finding(key=key, target=r.get("target", ""))
        elif f.status == SETTLED and f.left_as_is:
            f.status = PARKED
        elif f.status in (RESOLVED, SETTLED):
            f.status = OPEN
    for key, verdict in judgements.items():
        f = s.findings.get(key)
        if f is None:
            continue
        if f.status == AWAITING:
            if verdict == "resolved":
                f.status = RESOLVED
            else:
                _fail(f)
        elif f.status == CONTESTED:
            if verdict == "decline_right":
                f.status, f.settled_hash = SETTLED, s.content.get(f.target)
            else:
                f.status, f.no_decline = OPEN, True
    _park_exhausted(s)


def apply_answers(s: RunState, answers: dict[str, str]) -> None:
    """Take the operator's answers to the question that is pending.

    Parked findings: ``again`` (one more attempt), ``leave`` or ``stop``, per key.
    The cap of a code run: ``{"cap": "2"}``, ``{"cap": "5"}`` or ``{"cap": "stop"}``.
    Manual verification: ``yes`` or ``no`` per action id.
    """
    if s.pending_ask == "cap":
        choice = answers.get("cap", "stop")
        if choice == "stop":
            s.stop = True
        else:
            s.cap += int(choice)
    elif s.pending_ask == "confirm":
        for action_id, a in answers.items():
            if action_id in s.confirmations:
                s.confirmations[action_id] = a
    elif s.pending_ask == "parked":
        for key, a in answers.items():
            f = s.findings.get(key)
            if f is None or f.status != PARKED:
                continue
            if a == "again":
                f.status, f.attempts = OPEN, MAX_ATTEMPTS - 1
                s.fix_streak = 0
            elif a == "leave" and f.source == REVIEW:
                f.status, f.left_as_is = SETTLED, True
                f.settled_hash = s.content.get(f.target)
            elif a == "stop":
                s.stop = True
    s.pending_ask = None


# --------------------------------------------------------------------------- the rule


def _done(s: RunState, verdict: str) -> Action:
    s.verdict = verdict
    s.dispatch = None
    return Action(type="done", verdict=verdict)


def _hand_out(s: RunState, entries: list[Entry]) -> Action:
    batch = entries[: s.wave]
    for e in batch:
        e.handed_out, e.tries = True, e.tries + 1
    return Action(type="dispatch", entries=batch)


def _start(s: RunState, d: Dispatch) -> Action:
    s.dispatch = d
    s.dispatches += 1
    return _hand_out(s, d.entries)


def _review_dispatch(s: RunState) -> Dispatch:
    nodes = unread(s)
    by_cluster: dict[int, list[str]] = {}
    for n in nodes:
        by_cluster.setdefault(s.cluster.get(n, 0), []).append(n)
    if not by_cluster:
        by_cluster[0] = []
    entries: list[Entry] = []
    first_of: dict[int, Entry] = {}
    for c in sorted(by_cluster):
        fresh = any(n not in s.read for n in by_cluster[c])
        for k in range(s.readers if fresh else 1):
            e = Entry(id=f"r{c}.{k}", agent="reviewer", nodes=list(by_cluster[c]))
            entries.append(e)
            first_of.setdefault(c, e)
    for f in sorted(with_status(s, AWAITING, CONTESTED), key=lambda f: f.key):
        first_of.get(s.cluster.get(f.target, -1), entries[0]).judge.append(f.key)
    return Dispatch(role="review", entries=entries)


def _reviewed(s: RunState) -> dict[str, str]:
    """What this run reviews, as it is now: the nodes a reviewer of the run was given. A node counted as read from
    the start (``--extend``, ``--about``, a carried read-record) is not among them."""
    return {n: s.content[n] for n in s.seen if n in s.content}


def _final_dispatch(s: RunState) -> Dispatch:
    """The full re-read before CONVERGED: every node the run reviews, as it is now, one reviewer per cluster."""
    by_cluster: dict[int, list[str]] = {}
    for n in sorted(_reviewed(s)):
        by_cluster.setdefault(s.cluster.get(n, 0), []).append(n)
    entries = [Entry(id=f"full{c}", agent="reviewer", nodes=by_cluster[c]) for c in sorted(by_cluster)]
    return Dispatch(role="review", entries=entries)


def _at_cap(s: RunState) -> Action:
    if _is_spec(s):
        return _done(s, "HALT(cap)")
    s.pending_ask = "cap"
    return Action(type="ask", ask="cap")


def decide(s: RunState, redispatch: bool = False) -> Action:
    """The next action of a run: the first row of section 6.3 that fits."""
    if s.verdict is not None:
        return Action(type="done", verdict=s.verdict)
    # 1
    if s.stop:
        return _done(s, "HALT(operator)")
    # 2
    if s.dispatch is not None:
        d = s.dispatch
        if s.refusal:
            return _done(s, "HALT(agent_failed)")
        missing = [e for e in d.entries if e.handed_out and not e.arrived]
        if missing:
            if not redispatch:
                return Action(type="wait", missing=[e.id for e in missing])
            if any(e.tries >= MAX_TRIES for e in missing):
                return _done(s, "HALT(agent_failed)")
            for e in missing:
                e.tries += 1
            return Action(type="dispatch", entries=missing)
        rest = [e for e in d.entries if not e.handed_out]
        if rest:
            return _hand_out(s, rest)
        raise RuntimeError("a finished dispatch must be taken in before decide()")
    # 3
    if s.kind == "code-group" and any(v is None for v in s.confirmations.values()):
        s.pending_ask = "confirm"
        return Action(type="ask", ask="confirm", keys=sorted(k for k, v in s.confirmations.items() if v is None))
    # 4
    if s.mode in START_MODES and not s.start_done:
        role = "execute" if s.mode == "execute" else "author"
        return _start(s, Dispatch(role=role, entries=[Entry(id=role, agent=role)]))
    # 5
    if s.mode == "review-only":
        if s.rounds_used == 0:
            return _start(s, _review_dispatch(s))
        return _done(s, "FINDINGS" if with_status(s, OPEN, PARKED) else "CLEAN")
    opens = with_status(s, OPEN)
    # 6
    if opens and s.rounds_used >= s.cap:
        return _at_cap(s)
    # 7
    if opens:
        keys = sorted(f.key for f in opens)
        return _start(s, Dispatch(role="fix", entries=[Entry(id="fix", agent="fixer")], keys=keys))
    # 8
    if with_status(s, AWAITING, CONTESTED) or unread(s):
        if s.rounds_used < s.cap:
            return _start(s, _review_dispatch(s))
        return _at_cap(s)
    # 9
    parked = with_status(s, PARKED)
    if parked:
        if s.defer:
            return _done(s, "HALT(stuck)")
        s.pending_ask = "parked"
        return Action(type="ask", ask="parked", keys=sorted(f.key for f in parked))
    # 10
    if s.kind in CODE_KINDS and s.plan_blocked:
        return _done(s, "HALT(blocked)")
    # 11: the rounds after the first read only what a fix changed, so one reviewer reads the whole scope once more,
    # when the scope changed since a round last read all of it and a round is left under the cap
    if 1 < s.rounds_used < s.cap and not s.final_read and _reviewed(s) and s.full_read != _reviewed(s):
        s.final_read = True
        return _start(s, _final_dispatch(s))
    return _done(s, "CONVERGED")


def complete(d: Dispatch) -> bool:
    """Every entry of the dispatch has been handed out and has arrived."""
    return all(e.handed_out and e.arrived for e in d.entries)


def close_dispatch(s: RunState) -> None:
    """Called by the caller after it has taken in a finished dispatch."""
    s.dispatch = None
