"""The kind, role and link-verb names that two or more graph check modules use, and ``link_targets``.

A check module imports its vocabulary from here, never from another check's module; a name only one module uses stays in that module.
"""
from __future__ import annotations

from specdev_tools.graph.model import Graph, Node

# link verbs
REFINES = "refines"
VERIFIED_BY = "verified_by"
VERIFIES = "verifies"
REALISES = "realises"
DERIVES_FROM = "derives_from"

# kinds
API = "api"
COMPONENT = "component"
TASK_CRITERION = "task-criterion"
SCAFFOLD_ROW = "scaffold-row"
FIXTURE = "fixture"
JOB = "job"
RULE = "rule"

# roles
VERIFIER_ROLE = "verifier"


def link_targets(graph: Graph, node: Node, field: str) -> list[str]:
    """The ids of the nodes *node* links to through *field*, written as ids and resolved by alias to the current id, in link order; a target no node has is kept as written."""
    return [graph.canonical_id(link.target) for link in node.links if link.field == field]
