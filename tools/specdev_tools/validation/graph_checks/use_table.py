"""What "used" means per kind, as data: the use table of the no-dangling check (E740) and the owner step it derives.

The table is the transcription of the role rules of the design (the "Who uses what" table): for a target kind, the
(holder kind, verb) pairs whose stored link is a use of it.  A kind with a row is used by those pairs only; a kind with
no row (segment, metric and "every other kind") is used by any link of a holder that is not a record or a verifier,
except the verbs that never count.  A term has a row with no pair: it is used by its label (the term-use check).
Verifier kinds (fixture, job) have no row: their use rule is E742.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple

from specdev_tools.graph.kinds import RECORD_ROLE, KindDecl
from specdev_tools.graph.model import SpecShape

from specdev_tools.graph.names import EXPECTS, REALISES, REMOVES, VERIFIED_BY, VERIFIER_ROLE, VERIFIES

EXCLUDED_VERBS = frozenset({"about", "replaces", EXPECTS, REMOVES, VERIFIES, VERIFIED_BY})
"""Verbs that are never a use: a record's ``about``, the id-history links, the verifier verbs (a fixture that verifies a node does not use it) and ``expects`` (a fixture that expects an error does not use it)."""
NON_HOLDER_ROLES = frozenset({RECORD_ROLE, VERIFIER_ROLE})
VERIFIER_USE_VERB = REALISES
"""The one verb through which a verifier is a use: a job that ``realises`` a rule uses it (DOC: a job is used through what it realises)."""


class Use(NamedTuple):
    """One way to use a node: a node of ``holder_kind`` links to it through ``verb``."""

    holder_kind: str
    verb: str


def _uses(verb: str, *holder_kinds: str) -> tuple[Use, ...]:
    return tuple(Use(kind, verb) for kind in holder_kinds)


_ASSUMING_KINDS = (
    "api", "api-error", "capability", "component", "connection", "constraint", "criterion", "edge-case", "environment",
    "fr", "gate", "invariant", "metric", "need", "nfr", "risk", "rule", "scope-item", "secret", "segment", "stakeholder",
    "third-party", "threat",
)
"""The obligation and context kinds of steps 00 to 11 that declare ``assumes``."""

USE_TABLE: Mapping[str, tuple[Use, ...]] = {
    "assumption": (*_uses("assumes", *_ASSUMING_KINDS), *_uses("derives_from", "risk")),
    "need": _uses("derives_from", "metric", "scope-item", "constraint"),
    "stakeholder": _uses("derives_from", "rule"),
    "component": (
        *_uses("provided_by", "api"),
        *_uses("constrains", "invariant", "nfr"),
        *_uses("threatens", "threat"),
        *_uses("connects_to", "connection"),
        *_uses("derives_from", "gate", "secret"),
    ),
    "connection": (*_uses("constrains", "invariant", "nfr"), *_uses("threatens", "threat"), *_uses("derives_from", "secret")),
    "third-party": (
        *_uses("relies_on", "api", "nfr"),
        *_uses("part_of", "third-party"),
        *_uses("connects_to", "connection"),
    ),
    "environment": _uses("realises", "job"),
    "gate": _uses("realises", "job"),
    "secret": _uses("realises", "job"),
    "term": (),
    "threat": _uses("refines", "task-criterion"),
    "edge-case": _uses("refines", "task-criterion"),
    "risk": (*_uses("derives_from", "threat", "rule"), *_uses("schedules", "design-milestone")),
    "constraint": _uses("derives_from", "third-party", "component", "environment", "gate", "secret", "rule"),
}


def _can_hold(holder: KindDecl, verb: str) -> bool:
    return holder.role not in NON_HOLDER_ROLES or (holder.role == VERIFIER_ROLE and verb == VERIFIER_USE_VERB)


def use_pairs(kind: str, decls: Mapping[str, KindDecl]) -> frozenset[Use]:
    """The (holder kind, verb) pairs whose link uses a node of *kind*.

    A kind with a row of ``USE_TABLE`` gets that row.  Any other kind gets every link declaration of *decls* that
    accepts it, except the ``EXCLUDED_VERBS`` and the holders whose role is record or verifier (a verifier holds a use only through ``VERIFIER_USE_VERB``).
    """
    row = USE_TABLE.get(kind)
    if row is not None:
        return frozenset(row)
    return frozenset(
        Use(holder.kind, link.field)
        for holder in decls.values()
        for link in holder.links
        if link.field not in EXCLUDED_VERBS and link.accepts(kind) and _can_hold(holder, link.field)
    )


def step_of(kind: str, shape: SpecShape) -> str | None:
    """The step of *kind*: the latest (by the waterfall rank of *shape*) of the steps whose files declare it; ``None`` for a kind no step declares."""
    steps = shape.kind_steps.get(kind, ())
    return max(steps, key=shape.step_key) if steps else None


def furthest_steps(decls: Mapping[str, KindDecl], shape: SpecShape) -> dict[str, str]:
    """For each kind with a way to be used, the furthest step among the holder kinds of ``use_pairs``: the owner step of its E740.

    A kind with no holder kind that has a step is left out, so ``owner_for`` answers ``None`` for it.
    """
    furthest: dict[str, str] = {}
    for kind in decls:
        steps = [step for use in use_pairs(kind, decls) if (step := step_of(use.holder_kind, shape)) is not None]
        if steps:
            furthest[kind] = max(steps, key=shape.step_key)
    return furthest
