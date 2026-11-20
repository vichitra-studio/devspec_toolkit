"""The kind, role, field and link-verb names that two or more modules use, and ``link_targets``.

A module imports its vocabulary from here, never from another module of the same layer; a name only one module uses stays in that module.
"""
from __future__ import annotations

from typing import Final

from specdev_tools.graph.model import Graph, Node

# link verbs
REFINES = "refines"
VERIFIED_BY = "verified_by"
VERIFIES = "verifies"
REALISES = "realises"
DERIVES_FROM = "derives_from"
CONSTRAINS = "constrains"
PROVIDED_BY = "provided_by"
REMOVES = "removes"
SCHEDULES = "schedules"
MITIGATED_BY = "mitigated_by"
RELIES_ON = "relies_on"
CONNECTS_TO = "connects_to"
ABOUT = "about"

# kinds
API = "api"
API_ERROR = "api-error"
COMPONENT = "component"
CAPABILITY = "capability"
CONNECTION = "connection"
CONSTRAINT = "constraint"
CRITERION = "criterion"
DESIGN_MILESTONE = "design-milestone"
THIRD_PARTY = "third-party"
TASK_CRITERION = "task-criterion"
SCAFFOLD_ROW = "scaffold-row"
FIXTURE = "fixture"
FR = "fr"
JOB = "job"
RULE = "rule"
TASK = "task"
ROADMAP_MILESTONE = "roadmap-milestone"
NFR = "nfr"
ENVIRONMENT = "environment"
BINDING_KIND = "verification-record"

# values of a field
MERGE: Final = "merge"  # the merge-driver mode
MANUAL_MODE = "manual"  # ``mode`` of a fixture that a person attests
REVIEW_ENFORCER = "review"  # ``enforcer`` of a rule that a review enforces

# roles
VERIFIER_ROLE = "verifier"
OBLIGATION_ROLES = frozenset({"obligation-system", "obligation-delivery"})


def link_targets(graph: Graph, node: Node, field: str) -> list[str]:
    """The ids of the nodes *node* links to through *field*, written as ids and resolved by alias to the current id, in link order; a target no node has is kept as written."""
    return [graph.canonical_id(link.target) for link in node.links if link.field == field]
