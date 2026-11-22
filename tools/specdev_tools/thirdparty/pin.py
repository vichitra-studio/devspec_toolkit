"""``specdev third-party pin``: what an exact pin is, and the write of a new pin into a third-party node.

A pin is written to the ``pin`` field of the node through the id-keyed write path (``trace/id_writes.execute_write``), the
same path as ``specdev json patch --id``: it recomputes the node's content hash, so every link into the node goes suspect
through the closure that follows it, and it reports the links it made suspect.  The pin is a contract field, so no
other flagging code exists.
"""
from __future__ import annotations

import json

from specdev_tools.core.errors import FindingError, SpecError, make_error, refusal
from specdev_tools.graph.model import Graph
from specdev_tools.graph.names import THIRD_PARTY
from specdev_tools.graph.queries import pin_of, unknown_node_error
from specdev_tools.trace.id_writes import WriteRequest, WriteResult, execute_write

PIN_FIELD = ".pin"
_FLOATING_WORDS = frozenset({"latest", "any"})
_WILDCARD_SEGMENTS = frozenset({"x", "*"})
_RANGE_OPERATORS = ("^", "~", ">", "<", "=")
_RANGE_MARKERS = (" || ", " - ", ",")


def pin_is_exact(value: str) -> bool:
    """Whether *value* names one version: not empty, not ``latest`` or ``any``, no ``*`` or ``x`` segment, no range syntax.

    Any other non-empty text is exact: a semantic version, a commit sha, an API or contract version such as ``api-v3``.
    There is no grammar and no version parsing.
    """
    text = value.strip()
    if not text or text.lower() in _FLOATING_WORDS or "*" in text:
        return False
    if text.startswith(_RANGE_OPERATORS) or any(marker in text for marker in _RANGE_MARKERS):
        return False
    return not any(segment.lower() in _WILDCARD_SEGMENTS for segment in text.split("."))


def not_exact_error(node_id: str, value: str) -> SpecError:
    """The E336 finding for the pin *value* of the third party *node_id*."""
    return make_error(
        "E336",
        f"the pin '{value}' of '{node_id}' is not an exact version; give one version, a commit or a contract id such as 0.41.1",
        node_id=node_id,
    )


def pin_third_party(
    graph: Graph, spec_root: str, repo_root: str, git_root: str, third_party_id: str, version: str, *, dry_run: bool = False
) -> WriteResult | None:
    """Write *version* (stripped of surrounding space) as the pin of the third-party node *third_party_id* (an id or an alias); returns what the write did.

    ``None`` when the node already has that pin: nothing is written (no lock entry, no content-hash change, no suspect link).

    Raises:
        FindingError: E706 when the id names no node or a node that is not a third party, E336 when *version* is not
            an exact pin (nothing is written in either case); the errors of ``execute_write`` (E767, E769, E760).
    """
    node = graph.find(third_party_id)
    if node is None:
        raise unknown_node_error(graph, third_party_id)
    if node.kind != THIRD_PARTY:
        raise refusal("E706", f"'{node.id}' is of kind {node.kind}, not a third party; give the id of a third-party node")
    if not pin_is_exact(version):
        raise FindingError(not_exact_error(node.id, version))
    value = version.strip()
    if pin_of(graph, node.id) == value:
        return None
    request = WriteRequest(action="patch", node_id=node.id, path=PIN_FIELD, value=json.dumps(value))
    return execute_write(graph, spec_root, repo_root, git_root, request, dry_run=dry_run)
