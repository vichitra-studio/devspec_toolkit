"""The step gate: sort the findings of one spec-check run by who owns them and whether they are new.

``spec-check --step N`` is the check for finishing step N.  This module is the pure core of it: it takes the errors of
one run (each already carrying its owner), the step order, the errors of the baseline and the open-item closures, and
returns the buckets of ``StepGateResult``.  It reads no file and runs no check, so the hook, the skill and the
migration variant all call it.

Buckets for step N (the first rule that fits):

* owner is a gate, or there is no owner: ``gate_owned``, listed, never blocking;
* owner is N: ``waiting`` when an open item explains it, else ``blocking.own`` (E-code) or ``own_warnings`` (W-code);
* owner is an earlier step: ``upstream_debt`` when the baseline has the same finding, else
  ``blocking.new_upstream`` (E-code) or ``new_upstream_warnings`` (W-code); waiting never applies here;
* owner is a later step: ``pending``, grouped by owner step.

Waiting (``WaitingOn``) is a step-mode rule: with no ``WaitingOn``, or with no step, nothing is waiting.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import NamedTuple, Optional

from specdev_tools.core.ambiguity_items import AmbiguityItem, is_open
from specdev_tools.core.errors import SpecError
from specdev_tools.core.git_base import BaselineResult
from specdev_tools.graph.model import Graph, rank
from specdev_tools.graph.ownership import GATE_OWNERS, STEP_PREFIX
from specdev_tools.graph.queries import require_known_step_in
from specdev_tools.graph.trace import TraceOptions, trace_node

OwnerOf = Callable[[SpecError], Optional[str]]
"""``error -> owner string`` (``step:NN``, ``merge-check``, ...), ``None`` when the error has no owner."""

RouteOf = Callable[[SpecError], Optional[tuple[str, str]]]
"""``error -> (seed id, step)`` for an error that names the route of a seed to a step, else ``None``."""

CanonicalId = Callable[[str], str]
"""``name -> current id`` (``Graph.canonical_id``): maps an id an error carries from before a rename."""

EXIT_CLEAR = 0
EXIT_BLOCKED = 1


class IdentityKey(NamedTuple):
    """What makes two findings the same finding: never the message (messages embed counts and host paths).

    ``location`` is the ``jq_path`` of the finding with every array index removed (``.frs[3].scope`` gives
    ``.frs[].scope``), so an insert before a finding does not change its key.
    """

    code: str
    owner: Optional[str]
    node_id: Optional[str]
    target: Optional[str]
    file: Optional[str]
    location: Optional[str]
    subcode: Optional[str]
    path: Optional[str]


_TARGET_SEPARATOR = "->"
_ERROR_PREFIX = "E"
_ARRAY_INDEX = re.compile(r'"(?:[^"\\]|\\.)*"|\[\d+\]')
"""A quoted key (kept as it is) or an array index (dropped); the quoted key is tried first."""


def declared_owner(error: SpecError) -> str | None:
    """The owner already stamped on *error* (``SpecError.owner``); the ``owner_of`` of a run whose errors are all stamped."""
    return error.owner


def same_id(name: str) -> str:
    """The identity ``CanonicalId``: an id is its own current id (no rename is known)."""
    return name


def _no_route(error: SpecError) -> tuple[str, str] | None:
    return None


# --- identity ---------------------------------------------------------------------------------------------------

def identity_key(error: SpecError, owner_of: OwnerOf, canonical_id: CanonicalId = same_id) -> IdentityKey:
    """The identity key of *error*: its owner by *owner_of*, its node id and the target of its link by *canonical_id*.

    A field an error lacks is ``None`` in the key.  The message is never part of it, and ``location`` has no array
    indexes.  Several findings can share one key (the schema errors at one place of one file do); ``new_since_baseline`` counts them.
    """
    node_id = canonical_id(error.node_id) if error.node_id is not None else None
    target = _canonical_target(error.target, canonical_id)
    location = _ARRAY_INDEX.sub(_without_index, error.jq_path) if error.jq_path is not None else None
    return IdentityKey(error.code, owner_of(error), node_id, target, error.file, location, error.subcode, error.path)


def _without_index(match: re.Match[str]) -> str:
    return match.group(0) if match.group(0).startswith('"') else "[]"


def _canonical_target(target: str | None, canonical_id: CanonicalId) -> str | None:
    """*target* (``<field>-><id>``) with the id part mapped to its current id."""
    if target is None:
        return None
    link_field, separator, target_id = target.partition(_TARGET_SEPARATOR)
    return f"{link_field}{separator}{canonical_id(target_id)}" if separator else target


def dedupe_by_identity(errors: Iterable[SpecError], owner_of: OwnerOf, canonical_id: CanonicalId = same_id) -> list[SpecError]:
    """*errors* without the later copies of a finding with the same key AND the same message; the first of each is kept, in order.

    Two findings with one key and different messages are two findings and both are kept.
    """
    seen: set[tuple[IdentityKey, str]] = set()
    unique: list[SpecError] = []
    for error in errors:
        marker = (identity_key(error, owner_of, canonical_id), error.message)
        if marker not in seen:
            seen.add(marker)
            unique.append(error)
    return unique


def new_since_baseline(
    current: Sequence[SpecError],
    baseline: Iterable[SpecError],
    owner_of: OwnerOf,
    canonical_id: CanonicalId = same_id,
) -> list[bool]:
    """For each of *current*, whether it is new since *baseline* (``True``) or was already there (``False``).

    The rule: a finding is new when its key has more findings now than at the baseline.  For each key, the baseline
    has ``b`` findings and the current tree ``c`` (exact duplicates, the same key and message, count once).  A current
    finding whose message equals a baseline message of its key is old.  Of the other current findings of that key, the
    first ``b - matched`` in the order given are old (their text changed, or the tree they were found in has other
    paths), and the rest are new.  So a reworded message or a shifted array index is never new, and a second schema
    error in a file that already had one is new.  An exact duplicate gets the answer of its first copy.

    A node renamed with ``specdev node rename`` keeps its old error old through its alias; a node renamed by hand, or
    an error in a file that was renamed, counts as new.

    The one known limit: a finding fixed and another of the same key added on the branch is a count that did not grow,
    so the added one stays old; the merge check is where that is caught.  A schema finding has its file and the place of
    the violation in its key (index removed), so this needs the fixed and the added one to be at the same place in
    the same file: fixing ``.frs[1].scope`` and adding ``.frs[0].scope`` is one such case, while fixing a ``priority`` and
    adding a ``scope`` is not.
    """
    baseline_messages: dict[IdentityKey, set[str]] = {}
    for error in baseline:
        baseline_messages.setdefault(identity_key(error, owner_of, canonical_id), set()).add(error.message)
    keyed = [(identity_key(error, owner_of, canonical_id), error.message) for error in current]
    matched: dict[IdentityKey, set[str]] = {}
    for key, message in keyed:
        if message in baseline_messages.get(key, ()):
            matched.setdefault(key, set()).add(message)
    unplaced = {key: len(messages) - len(matched.get(key, ())) for key, messages in baseline_messages.items()}
    answers: dict[tuple[IdentityKey, str], bool] = {}
    for marker in keyed:
        key, message = marker
        if marker in answers:
            continue
        if message in baseline_messages.get(key, ()):
            answers[marker] = False
        elif unplaced.get(key, 0) > 0:
            unplaced[key] -= 1
            answers[marker] = False
        else:
            answers[marker] = True
    return [answers[marker] for marker in keyed]


# --- waiting ----------------------------------------------------------------------------------------------------

def _below(graph: Graph, node_id: str) -> frozenset[str]:
    """Ids of the nodes that link, directly or through any verb, to *node_id*; the node itself and records are not in it."""
    node = graph.find(node_id)
    if node is None:
        return frozenset()
    side = trace_node(graph, node.id, ("down",), TraceOptions()).down
    return frozenset(reached.id for reached in side.nodes) if side is not None else frozenset()


def waiting_map(graph: Graph, items: Iterable[AmbiguityItem]) -> dict[str, frozenset[str]]:
    """For each open item (by id), the node ids in the downstream closure of its ``about`` nodes.

    The ``about`` node itself is not in its closure: it is the thing to correct, so an error on it is real.  Ambiguity
    items are records and are not in a closure.  An ``about`` id no node has gives nothing; items that are not open are
    left out; two items with one id are merged.
    """
    closures: dict[str, frozenset[str]] = {}
    for item in items:
        if is_open(item):
            below = frozenset().union(*(_below(graph, about) for about in item.about_ids))
            closures[item.id] = closures.get(item.id, frozenset()) | below
    return closures


@dataclass(frozen=True)
class WaitingOn:
    """Which open items explain which errors.

    ``closures`` is ``waiting_map``; ``abouts`` maps each open item id to the ids it is about; ``route_of`` reads the
    ``(seed, step)`` route an error names (M6b's route-use check; the default reads none).
    """

    closures: Mapping[str, frozenset[str]]
    abouts: Mapping[str, frozenset[str]]
    route_of: RouteOf = _no_route

    @classmethod
    def from_items(cls, graph: Graph, items: Sequence[AmbiguityItem], route_of: RouteOf = _no_route) -> WaitingOn:
        """The waiting context of the open *items* of *graph*."""
        abouts: dict[str, frozenset[str]] = {}
        for item in items:
            if is_open(item):
                abouts[item.id] = abouts.get(item.id, frozenset()) | frozenset(item.about_ids)
        return cls(waiting_map(graph, items), abouts, route_of)

    def reasons(self, error: SpecError, step: str | None) -> tuple[str, ...]:
        """``waiting on <item id>`` for each open item that explains *error* in step mode; ``()`` when none, or with no *step* (merge mode).

        An item explains an error whose node is in the item's closure, or whose route is ``(seed, step)`` with the seed
        among the item's ``about`` ids.
        """
        if step is None:
            return ()
        route = self.route_of(error)
        matching = [
            item_id for item_id, below in self.closures.items()
            if (error.node_id is not None and error.node_id in below)
            or (route is not None and route[1] == step and route[0] in self.abouts.get(item_id, frozenset()))
        ]
        return tuple(f"waiting on {item_id}" for item_id in sorted(matching))


# --- result -----------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class WaitingError:
    """An error of the step that an open item explains, with its reasons (``waiting on amb-x``)."""

    error: SpecError
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Blocking:
    """The errors that stop the step: its own errors and the new errors of earlier steps."""

    own: tuple[SpecError, ...] = ()
    new_upstream: tuple[SpecError, ...] = ()

    @property
    def errors(self) -> tuple[SpecError, ...]:
        """Own errors, then new upstream errors."""
        return self.own + self.new_upstream


@dataclass(frozen=True)
class StepGateResult:
    """The buckets of one step.  ``blocking`` empty means clear (``clear``)."""

    step: str
    blocking: Blocking = field(default_factory=Blocking)
    own_warnings: tuple[SpecError, ...] = ()
    new_upstream_warnings: tuple[SpecError, ...] = ()
    upstream_debt: tuple[SpecError, ...] = ()
    waiting: tuple[WaitingError, ...] = ()
    gate_owned: tuple[SpecError, ...] = ()
    pending: Mapping[str, tuple[SpecError, ...]] = field(default_factory=dict)
    new_own_warnings: tuple[SpecError, ...] = ()
    """The warnings of ``own_warnings`` that the base did not have (empty when there is no base).  They do not block."""
    no_longer_present: tuple[SpecError, ...] = ()
    """What the base had, owned by this step or a step above it, and the tree no longer has (empty when there is no base)."""

    @property
    def clear(self) -> bool:
        """Whether nothing blocks the step (exit 0)."""
        return not self.blocking.errors


@dataclass
class _Draft:
    """The buckets while they fill."""

    own: list[SpecError] = field(default_factory=list)
    new_upstream: list[SpecError] = field(default_factory=list)
    own_warnings: list[SpecError] = field(default_factory=list)
    new_upstream_warnings: list[SpecError] = field(default_factory=list)
    debt: list[SpecError] = field(default_factory=list)
    waiting: list[WaitingError] = field(default_factory=list)
    gate_owned: list[SpecError] = field(default_factory=list)
    pending: dict[str, list[SpecError]] = field(default_factory=dict)
    new_own_warnings: list[SpecError] = field(default_factory=list)
    no_longer_present: list[SpecError] = field(default_factory=list)

    def freeze(self, step: str) -> StepGateResult:
        return StepGateResult(
            step,
            Blocking(tuple(self.own), tuple(self.new_upstream)),
            tuple(self.own_warnings),
            tuple(self.new_upstream_warnings),
            tuple(self.debt),
            tuple(self.waiting),
            tuple(self.gate_owned),
            {owner_step: tuple(found) for owner_step, found in self.pending.items()},
            tuple(self.new_own_warnings),
            tuple(self.no_longer_present),
        )


# --- classification ---------------------------------------------------------------------------------------------

def _is_error(error: SpecError) -> bool:
    return error.code.startswith(_ERROR_PREFIX)


def _owner_step(owner: str | None) -> str | None:
    """The step of a ``step:<id>`` owner; ``None`` for a gate, an unowned error or an owner string no rule knows."""
    if owner is not None and owner not in GATE_OWNERS and owner.startswith(STEP_PREFIX):
        return owner[len(STEP_PREFIX):]
    return None


def classify_for_step(
    errors: Iterable[SpecError],
    step: str,
    owner_of: OwnerOf,
    order: Mapping[str, int],
    baseline: BaselineResult,
    waiting: WaitingOn | None = None,
    *,
    canonical_id: CanonicalId = same_id,
) -> StepGateResult:
    """Sort *errors* into the buckets of *step*.

    *errors* have W-to-E promotion applied; exact duplicates are reduced to one.  *order* maps each step to its place
    (``Graph.shape.step_ranks``; a step it lacks sorts last).  An upstream error is debt unless ``new_since_baseline``
    says it is new (keys mapped through *canonical_id*, so a node renamed on the branch keeps its old finding old);
    with an ``unavailable`` baseline every upstream error is new.  *waiting* is ``None`` where waiting is off.

    The order of *errors* decides which finding is named new when two of one key are left over (the rule of
    ``new_since_baseline``): the caller fixes it, and ``run_step_gate`` gives the registry order, then the order of each
    check's own findings.

    Raises ``FindingError`` (E706) when *step* is not in *order*.
    """
    require_known_step_in(order, step)
    unique = dedupe_by_identity(errors, owner_of, canonical_id)
    baseline_errors = baseline.errors if baseline.mode == "ok" else ()
    is_new = new_since_baseline(unique, baseline_errors, owner_of, canonical_id)
    draft = _Draft()
    for error, new in zip(unique, is_new):
        owner_step = _owner_step(owner_of(error))
        if owner_step is None:
            draft.gate_owned.append(error)
        elif owner_step == step:
            _place_own(draft, error, waiting.reasons(error, step) if waiting else ())
            if new and baseline.mode == "ok" and error in draft.own_warnings[-1:]:
                draft.new_own_warnings.append(error)
        elif rank(owner_step, order) < rank(step, order):
            _place_upstream(draft, error, not new)
        else:
            draft.pending.setdefault(owner_step, []).append(error)
    if baseline.mode == "ok":
        before = dedupe_by_identity(baseline_errors, owner_of, canonical_id)
        for error, gone in zip(before, new_since_baseline(before, unique, owner_of, canonical_id)):
            owner_step = _owner_step(owner_of(error))
            if gone and owner_step is not None and rank(owner_step, order) <= rank(step, order):
                draft.no_longer_present.append(error)
    return draft.freeze(step)


def _place_own(draft: _Draft, error: SpecError, reasons: tuple[str, ...]) -> None:
    if reasons:
        draft.waiting.append(WaitingError(error, reasons))
    elif _is_error(error):
        draft.own.append(error)
    else:
        draft.own_warnings.append(error)


def _place_upstream(draft: _Draft, error: SpecError, in_baseline: bool) -> None:
    if in_baseline:
        draft.debt.append(error)
    elif _is_error(error):
        draft.new_upstream.append(error)
    else:
        draft.new_upstream_warnings.append(error)


def classify_for_steps(
    errors: Sequence[SpecError],
    steps: Sequence[str],
    owner_of: OwnerOf,
    order: Mapping[str, int],
    baseline: BaselineResult,
    waiting: WaitingOn | None = None,
    *,
    canonical_id: CanonicalId = same_id,
) -> tuple[StepGateResult, ...]:
    """One ``StepGateResult`` per listed step, in the order given; the run blocks if any of them has blocking errors."""
    return tuple(classify_for_step(errors, step, owner_of, order, baseline, waiting, canonical_id=canonical_id) for step in steps)


# --- exit code and the union over steps --------------------------------------------------------------------------

def gate_exit_code(results: Iterable[StepGateResult]) -> int:
    """``EXIT_CLEAR`` when every listed step is ``clear``, else ``EXIT_BLOCKED``: the one exit rule of the gate."""
    return EXIT_CLEAR if all(result.clear for result in results) else EXIT_BLOCKED


def union_errors(groups: Iterable[Iterable[SpecError]]) -> list[SpecError]:
    """The findings of all *groups* once each (same key and message), in order; the owner is the one already stamped."""
    return dedupe_by_identity((error for group in groups for error in group), declared_owner)


def union_waiting(results: Sequence[StepGateResult]) -> list[WaitingError]:
    """The waiting findings of all *results* once each (same key and message), in order."""
    unique: dict[tuple[IdentityKey, str], WaitingError] = {}
    for result in results:
        for entry in result.waiting:
            unique.setdefault((identity_key(entry.error, declared_owner), entry.error.message), entry)
    return list(unique.values())


def reported_errors(results: Sequence[StepGateResult]) -> list[SpecError]:
    """The findings that matter for the steps (blocking, then warnings of the step and new upstream warnings), once each.

    This is the ``errors`` list of the JSON payload, so its ``status`` agrees with the exit code.
    """
    return union_errors(
        [*result.blocking.errors, *result.own_warnings, *result.new_upstream_warnings] for result in results
    )
