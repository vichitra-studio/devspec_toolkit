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

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Optional

from specdev_tools.core.ambiguity_items import AmbiguityItem, about_targets, is_open
from specdev_tools.core.errors import SpecError
from specdev_tools.core.git_base import BaselineResult
from specdev_tools.graph.model import Graph, SpecShape, rank
from specdev_tools.graph.ownership import GATE_OWNERS, STEP_PREFIX
from specdev_tools.graph.queries import require_known_step
from specdev_tools.graph.trace import TraceOptions, trace_node

OwnerOf = Callable[[SpecError], Optional[str]]
"""``error -> owner string`` (``step:NN``, ``merge-check``, ...), ``None`` when the error has no owner."""

RouteOf = Callable[[SpecError], Optional[tuple[str, str]]]
"""``error -> (seed id, step)`` for an error that names the route of a seed to a step, else ``None``."""

CanonicalId = Callable[[str], str]
"""``name -> current id`` (``Graph.canonical_id``): maps an id an error carries from before a rename."""

IdentityKey = tuple[str, Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]
"""``(code, owner, node_id, target, file, jq_path, subcode)``: what makes two findings the same finding.  Never the message."""

_TARGET_SEPARATOR = "->"
_ERROR_PREFIX = "E"


def declared_owner(error: SpecError) -> str | None:
    """The owner already stamped on *error* (``SpecError.owner``); the ``owner_of`` of a run whose errors are all stamped."""
    return error.owner


def _same(name: str) -> str:
    return name


def _no_route(error: SpecError) -> tuple[str, str] | None:
    return None


# --- identity ---------------------------------------------------------------------------------------------------

def identity_key(error: SpecError, owner_of: OwnerOf, canonical_id: CanonicalId = _same) -> IdentityKey:
    """The identity key of *error*: its owner by *owner_of*, its node id and the target of its link by *canonical_id*.

    A field an error lacks is ``None`` in the tuple.  The message is never part of the key (messages embed counts).
    ``path`` is part of it: the older checks name their artifact there and nowhere else, so without it two findings of
    one code in two files would be one finding, and a new one would hide behind an old one.
    """
    node_id = canonical_id(error.node_id) if error.node_id is not None else None
    target = _canonical_target(error.target, canonical_id)
    return (error.code, owner_of(error), node_id, target, error.file, error.jq_path, error.subcode, error.path)


def _canonical_target(target: str | None, canonical_id: CanonicalId) -> str | None:
    """*target* (``<field>-><id>``) with the id part mapped to its current id."""
    if target is None:
        return None
    link_field, separator, target_id = target.partition(_TARGET_SEPARATOR)
    return f"{link_field}{separator}{canonical_id(target_id)}" if separator else target


def dedupe_by_identity(errors: Iterable[SpecError], owner_of: OwnerOf, canonical_id: CanonicalId = _same) -> list[SpecError]:
    """*errors* without the later copies of a finding with the same identity key; the first of each is kept, in order."""
    seen: set[IdentityKey] = set()
    unique: list[SpecError] = []
    for error in errors:
        key = identity_key(error, owner_of, canonical_id)
        if key not in seen:
            seen.add(key)
            unique.append(error)
    return unique


# --- waiting ----------------------------------------------------------------------------------------------------

def _about_ids(item: AmbiguityItem) -> list[str]:
    """The ids *item* is about; the silent-spec target names no node and is left out."""
    return [target for target in about_targets(item) if isinstance(target, str)]


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
            below = frozenset().union(*(_below(graph, about) for about in _about_ids(item)))
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
                abouts[item.id] = abouts.get(item.id, frozenset()) | frozenset(_about_ids(item))
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
        )


# --- classification ---------------------------------------------------------------------------------------------

def require_known_order_step(order: Mapping[str, int], step: str) -> None:
    """Raise the E706 finding (``FindingError``) unless *step* is a step of *order*; the message names the known steps."""
    require_known_step(Graph.from_nodes([], shape=SpecShape(step_ranks=order)), step)


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
    canonical_id: CanonicalId = _same,
) -> StepGateResult:
    """Sort *errors* into the buckets of *step*.

    *errors* have W-to-E promotion applied; they are first reduced to one per identity key.  *order* maps each step to
    its place (``Graph.shape.step_ranks``; a step it lacks sorts last).  *baseline* errors, keyed the same way and
    mapped through *canonical_id* (so a node renamed on the branch keeps its old finding old), make an upstream error
    debt; with an ``unavailable`` baseline every upstream error is new.  *waiting* is ``None`` where waiting is off.

    Raises ``FindingError`` (E706) when *step* is not in *order*.
    """
    require_known_order_step(order, step)
    debt_keys = {identity_key(error, owner_of, canonical_id) for error in baseline.errors}
    draft = _Draft()
    for error in dedupe_by_identity(errors, owner_of, canonical_id):
        owner_step = _owner_step(owner_of(error))
        if owner_step is None:
            draft.gate_owned.append(error)
        elif owner_step == step:
            _place_own(draft, error, waiting.reasons(error, step) if waiting else ())
        elif rank(owner_step, order) < rank(step, order):
            _place_upstream(draft, error, identity_key(error, owner_of, canonical_id) in debt_keys)
        else:
            draft.pending.setdefault(owner_step, []).append(error)
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
    canonical_id: CanonicalId = _same,
) -> tuple[StepGateResult, ...]:
    """One ``StepGateResult`` per listed step, in the order given; the run blocks if any of them has blocking errors."""
    return tuple(classify_for_step(errors, step, owner_of, order, baseline, waiting, canonical_id=canonical_id) for step in steps)
