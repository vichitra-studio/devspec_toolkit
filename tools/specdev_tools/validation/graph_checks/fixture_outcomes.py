"""The fixture outcome rules: a fixture that expects an error status names the error (E754), agrees with it (E755) and with the invariants it verifies (E756).

A fixture in play that has a document item reads ``expected.status`` only when ``expected`` is an object and the value is an integer (a boolean is not).

**Not named (E754).**  The status is 400 or more and the fixture has no ``expects`` link.  A fixture that holds ``removes`` is skipped: it
proves that a deleted node answers 404, and no API error exists for it.

**Differs (E755).**  The fixture names an API error in ``expects`` and gives a status, and the error has no ``http_status`` or another one.

**Not constrained (E756).**  The fixture names an API error in ``expects`` and verifies an invariant in play that does not list the error in ``constrains``;
one finding for each such invariant.

A link target that no node has, or that is of another kind, is a finding of E700 and E701 and is skipped here.  The owner of each code is the one the
ownership table gives (step 08).  ``check_fixture_outcomes`` is called by ``check_verifier_rules``.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.graph.contract import item_of
from specdev_tools.graph.model import Node
from specdev_tools.graph.names import API_ERROR, CONSTRAINS, EXPECTS, FIXTURE, REMOVES, VERIFIES, link_targets

from .codes import FIXTURE_ERROR_NOT_CONSTRAINED, FIXTURE_ERROR_NOT_NAMED, FIXTURE_STATUS_DIFFERS_FROM_ERROR
from .context import GraphCheckContext

INVARIANT = "invariant"
HTTP_STATUS = "http_status"
"""The field of an API error that holds its HTTP status; the fixture's number is ``expected.status``."""
ERROR_STATUS_FLOOR = 400
"""The lowest status that is an error outcome."""


def _integer(container: Mapping[str, Any] | None, key: str) -> int | None:
    """The integer under *key* of *container*, else ``None`` (a boolean, a float or a string is not a status)."""
    value = container.get(key) if container is not None else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _expected_status(item: Mapping[str, Any] | None) -> int | None:
    expected = item.get("expected") if item is not None else None
    return _integer(expected, "status") if isinstance(expected, dict) else None


def _fixtures(ctx: GraphCheckContext) -> list[tuple[Node, int | None]]:
    """The fixtures in play with a document item and the integer ``expected.status`` of each (``None`` when it has none), in step then id order."""
    found = []
    for node in ctx.in_play_nodes():
        if node.kind != FIXTURE:
            continue
        item = item_of(ctx.graph, node)
        if item is not None:
            found.append((node, _expected_status(item)))
    return found


def _error_node(ctx: GraphCheckContext, fixture: Node) -> Node | None:
    """The API error the fixture names in ``expects``, or ``None`` when it names none or the target is no API error."""
    for target_id in link_targets(ctx.graph, fixture, EXPECTS):
        target = ctx.graph.by_id.get(target_id)
        if target is not None and target.kind == API_ERROR:
            return target
    return None


def check_fixture_outcomes(ctx: GraphCheckContext) -> list[SpecError]:
    """E754, E755 and E756 for the fixtures in play, in step then id order, the three codes of one fixture together."""
    findings: list[SpecError] = []
    for fixture, status in _fixtures(ctx):
        error = _error_node(ctx, fixture)
        if status is not None and status >= ERROR_STATUS_FLOOR and not link_targets(ctx.graph, fixture, EXPECTS) and not link_targets(ctx.graph, fixture, REMOVES):
            findings.append(ctx.finding(
                FIXTURE_ERROR_NOT_NAMED, fixture,
                f"fixture {fixture.id} expects status {status} but names no API error: add expects naming the API error "
                f"(step 05) it expects, then run specdev attest {fixture.id} --yes",
            ))
        if error is None:
            continue
        if status is not None:
            error_status = _integer(item_of(ctx.graph, error), HTTP_STATUS)
            if error_status != status:
                states = f"has http_status {error_status}" if error_status is not None else "has no http_status"
                findings.append(ctx.finding(
                    FIXTURE_STATUS_DIFFERS_FROM_ERROR, fixture,
                    f"fixture {fixture.id} expects status {status} but the API error {error.id} {states}: make them equal: "
                    f"set http_status of {error.id} or fix expected.status of {fixture.id}, then run specdev attest {fixture.id} --yes",
                    target=link_target(EXPECTS, error.id),
                ))
        for invariant_id in link_targets(ctx.graph, fixture, VERIFIES):
            invariant = ctx.graph.by_id.get(invariant_id)
            if invariant is None or invariant.kind != INVARIANT or not ctx.in_play(invariant):
                continue
            if error.id not in link_targets(ctx.graph, invariant, CONSTRAINS):
                findings.append(ctx.finding(
                    FIXTURE_ERROR_NOT_CONSTRAINED, fixture,
                    f"fixture {fixture.id} verifies invariant {invariant.id} but expects the API error {error.id}, which {invariant.id} "
                    f"does not constrain: add {error.id} to constrains of {invariant.id} (then run specdev attest {invariant.id} --yes), "
                    f"or expect an error it constrains (then run specdev attest {fixture.id} --yes)",
                    target=link_target(VERIFIES, invariant.id),
                ))
    return findings
