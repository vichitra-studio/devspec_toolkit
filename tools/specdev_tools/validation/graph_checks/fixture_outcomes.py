"""The fixture outcome rules: a fixture that expects an error status names the error (E754), agrees with it (E755) and with the invariants it verifies (E756).

A fixture in play that has a document item reads ``expected.status`` only when ``expected`` is an object and the value is an integer (a boolean is not).
The rules read no protocol: the number of an error is its ``protocol_status``, whatever the protocol of its API.

**Not named (E754).**  The status is in the HTTP error range (400 to 599) and the fixture has no ``expects`` link.  A status number of another
protocol is not recognised as an error, so this rule is silent for it.  A fixture that holds ``removes`` is skipped: it proves that a deleted
node answers 404, and no API error exists for it.

**Differs (E755).**  The fixture names API errors in ``expects`` and gives a status; one finding for each named error that has no
``protocol_status`` or another one.

**Not constrained (E756).**  The fixture names API errors in ``expects`` and verifies an invariant in play that lists none of them in
``constrains``; one finding for each such invariant.

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
PROTOCOL_STATUS = "protocol_status"
"""The field of an API error that holds the status number of its protocol; the fixture's number is ``expected.status``."""
HTTP_ERROR_STATUSES = range(400, 600)
"""The statuses that E754 recognises as an error outcome without a named error: the HTTP error range."""


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


def _error_nodes(ctx: GraphCheckContext, fixture: Node) -> list[Node]:
    """The API errors the fixture names in ``expects``, each once, in the order it lists them (a target that is no API error is left out)."""
    targets = (ctx.graph.by_id.get(target_id) for target_id in link_targets(ctx.graph, fixture, EXPECTS))
    return list({target.id: target for target in targets if target is not None and target.kind == API_ERROR}.values())


def check_fixture_outcomes(ctx: GraphCheckContext) -> list[SpecError]:
    """E754, E755 and E756 for the fixtures in play, in step then id order, the three codes of one fixture together."""
    findings: list[SpecError] = []
    for fixture, status in _fixtures(ctx):
        errors = _error_nodes(ctx, fixture)
        if status in HTTP_ERROR_STATUSES and not link_targets(ctx.graph, fixture, EXPECTS) and not link_targets(ctx.graph, fixture, REMOVES):
            findings.append(ctx.finding(
                FIXTURE_ERROR_NOT_NAMED, fixture,
                f"fixture {fixture.id} expects status {status} but names no API error: add expects naming the API error "
                f"(step 05) it expects, then run specdev attest {fixture.id} --yes",
            ))
        if not errors:
            continue
        for error in errors if status is not None else ():
            error_status = _integer(item_of(ctx.graph, error), PROTOCOL_STATUS)
            if error_status != status:
                states = f"has protocol_status {error_status}" if error_status is not None else "has no protocol_status"
                findings.append(ctx.finding(
                    FIXTURE_STATUS_DIFFERS_FROM_ERROR, fixture,
                    f"fixture {fixture.id} expects status {status} but the API error {error.id} {states}: make them equal: "
                    f"set protocol_status of {error.id} or fix expected.status of {fixture.id}, then run specdev attest {fixture.id} --yes",
                    target=link_target(EXPECTS, error.id),
                ))
        expected_ids = [error.id for error in errors]
        listed = ", ".join(expected_ids)
        for invariant_id in link_targets(ctx.graph, fixture, VERIFIES):
            invariant = ctx.graph.by_id.get(invariant_id)
            if invariant is None or invariant.kind != INVARIANT or not ctx.in_play(invariant):
                continue
            if not set(expected_ids) & set(link_targets(ctx.graph, invariant, CONSTRAINS)):
                if len(expected_ids) == 1:
                    gap, named = f"the API error {listed}, which {invariant.id} does not constrain", listed
                else:
                    gap, named = f"the API errors {listed}, none of which {invariant.id} constrains", f"one of {listed}"
                findings.append(ctx.finding(
                    FIXTURE_ERROR_NOT_CONSTRAINED, fixture,
                    f"fixture {fixture.id} verifies invariant {invariant.id} but expects {gap}: "
                    f"add {named} to constrains of {invariant.id} (then run specdev attest {invariant.id} --yes), "
                    f"or expect an error it constrains (then run specdev attest {fixture.id} --yes)",
                    target=link_target(VERIFIES, invariant.id),
                ))
    return findings
