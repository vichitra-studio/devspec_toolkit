"""Stored computed fields (WI-M5-13, E768): a spec node that stores a value the toolkit computes.

``COMPUTED_VIEWS`` has one row for each computed view of the design (DOC section 4.6, "Computed, never stored").  A row
names the field names that are rejected when a node of the row's scope stores them, or, when no name is enforced, the
reason none is.  Only names that the 1.2.0 schemas no longer declare are enforced: a name that is authored somewhere
else (``impact``, ``baseline``) is not listed.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.graph.contract import item_of
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.ownership import step_owner

TRACE_SOURCE = "specdev trace <id>"
_NO_FIELD = "no stored field exists in the schemas, so there is no name to reject"
_UNVERIFIED = "no schema stored this view, so the field name would be a guess"


@dataclass(frozen=True)
class ComputedView:
    """One computed view: its DOC wording, the ``names`` that may not be stored, where, and how to compute it.

    ``scope`` is the node kinds the names are rejected on; ``None`` means every node.  ``reason`` is non-empty exactly
    when ``names`` is empty: why no name is enforced.  ``remedy`` is the whole sentence that says what to do with a stored
    name when there is no command that computes it (then ``source`` is empty).
    """

    view: str
    names: tuple[str, ...]
    scope: tuple[str, ...] | None
    source: str
    reason: str = ""
    remedy: str = ""


COMPUTED_VIEWS: tuple[ComputedView, ...] = (
    ComputedView("a link target's kind", (), None, "the id, through the kind registry", _NO_FIELD),
    ComputedView("impact, coverage, suspects, replay list", (), None, "specdev coverage, specdev stale", _UNVERIFIED),
    ComputedView(
        "built, proven, realisation status, release status", (), None, "links, evidence and tags", _UNVERIFIED
    ),
    ComputedView(
        "a plan item's task, milestone, fixture and NFRs",
        ("milestone_ref", "nfr_refs", "fixture_ref"),
        ("plan-item",),
        TRACE_SOURCE,
    ),
    ComputedView("task progress", (), None, "its plan items", _UNVERIFIED),
    ComputedView(
        "a 14 milestone's 09 milestones",
        ("deliverables", "source_milestones"),
        ("roadmap-milestone",),
        TRACE_SOURCE,
    ),
    ComputedView("09 capability placement", (), None, "the FRs a 09 milestone schedules", _UNVERIFIED),
    ComputedView(
        "14 milestone fr_refs and capability_refs; task fr_refs and invariant_refs",
        ("fr_refs", "capability_refs", "invariant_refs"),
        ("roadmap-milestone", "task", "anchor-row"),
        TRACE_SOURCE,
    ),
    ComputedView("a component's reliance on a third party", (), None, "its connections' connects_to", _UNVERIFIED),
    ComputedView("glossary use", (), None, "label matching", _UNVERIFIED),
    ComputedView("step order", (), None, "the x-link declarations", _NO_FIELD),
    ComputedView("context packs", (), None, "links, per role recipe", _NO_FIELD),
    ComputedView(
        "content hash and chain stamp",
        ("content_hash", "chain_stamp"),
        None,
        "",
        remedy="remove it; the content hash and the chain stamp are computed from the node's text and are kept in the trace lock, not in a spec file",
    ),
)


def _message(node: Node, name: str, view: ComputedView) -> str:
    if view.remedy:
        return f"{node.id} ({node.kind}) stores '{name}', which is computed ({view.view}). {view.remedy[0].upper()}{view.remedy[1:]}"
    return (
        f"{node.id} ({node.kind}) stores '{name}', which is computed ({view.view}); "
        f"remove it and compute it with {view.source}"
    )


def _stored_names(node: Node, view: ComputedView, item: Mapping[str, Any]) -> list[str]:
    if view.scope is not None and node.kind not in view.scope:
        return []
    return [name for name in view.names if name in item]


def check_stored_computed(graph: Graph) -> list[SpecError]:
    """E768 for every node object that stores a name of ``COMPUTED_VIEWS`` inside the view's scope.

    Reads the parsed documents the graph already holds and builds nothing.  A node whose document is not on the graph
    (a graph built from nodes alone) is skipped.  Each finding names the node id, the view and the command that
    computes it, and carries the owner ``step:<node step>``; order is graph node order, then view order.
    """
    findings: list[SpecError] = []
    for node in graph.nodes:
        item = item_of(graph, node)
        if item is None:
            continue
        for view in COMPUTED_VIEWS:
            for name in _stored_names(node, view, item):
                findings.append(
                    make_error(
                        "E768",
                        _message(node, name, view),
                        file=node.file,
                        jq_path=f"{node.jq_path}.{name}",
                        owner=step_owner(node),
                        node_id=node.id,
                    )
                )
    return findings
