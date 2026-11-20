"""The graph checks: rules about the nodes of the spec graph (use, verifiers, refinement, routes, prose).

``run_graph_checks(ctx, mode, only)`` runs every rule registered with ``register_graph_check`` and keeps the findings
whose code is in *only*.  The registered ``spec-check`` entries (one per module, in the registration block of
``validation/spec_check.py``) each run one rule through a ``GraphCheckContext``.  Importing this package also
registers the replay gap provider.
"""
from __future__ import annotations

from collections.abc import Callable

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.model import Graph
from specdev_tools.graph.ownership import STEP_PREFIX
from specdev_tools.trace.gaps import CoverageGap, register_gap_provider
from specdev_tools.trace.lockfile import Lock

from .codes import ROLE_GAP_CODES
from .context import MODES, GraphCheckContext, Mode
from .cross_cutting import check_cross_cutting
from .no_dangling import check_no_dangling
from .prose_ids import check_prose_ids
from .refinement import check_refinement
from .scaffold import check_scaffold_paths
from .seed_routes import check_seed_routes
from .term_use import check_term_use
from .verifiers import check_verifier_rules

GraphCheck = Callable[[GraphCheckContext, Mode], list[SpecError]]

GRAPH_CHECKS: list[tuple[str, GraphCheck]] = []
"""The rules ``run_graph_checks`` runs, in order, by name; ``register_graph_check`` appends to it."""


def register_graph_check(name: str, fn: GraphCheck) -> None:
    """Append the rule *fn* (``fn(ctx, mode) -> findings``) under *name* to the rules ``run_graph_checks`` runs.

    Raises:
        ValueError: a rule of that name is already registered.
    """
    if any(registered == name for registered, _ in GRAPH_CHECKS):
        raise ValueError(f"graph check {name!r} is already registered")
    GRAPH_CHECKS.append((name, fn))


def run_graph_checks(ctx: GraphCheckContext, mode: Mode, only: set[str] | None = None) -> list[SpecError]:
    """The findings of every registered rule for *mode*; with *only*, just those whose code is in it.

    Raises:
        ValueError: *mode* is not ``merge``, ``close`` or ``release``.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}, not {mode!r}")
    findings = [error for _, fn in GRAPH_CHECKS for error in fn(ctx, mode)]
    return findings if only is None else [error for error in findings if error.code in only]


def role_gaps(graph: Graph, lock: Lock) -> list[CoverageGap]:
    """The replay gap provider: one gap for each E740, E742 and E743 finding owned by a step; a finding owned by a gate or with no node is left out."""
    findings = run_graph_checks(GraphCheckContext.from_graph(graph, lock), "merge", only=set(ROLE_GAP_CODES))
    return [
        CoverageGap(error.code, error.node_id, error.owner.removeprefix(STEP_PREFIX))
        for error in findings
        if error.node_id is not None and error.owner is not None and error.owner.startswith(STEP_PREFIX)
    ]


for _name, _rule in (
    ("no-dangling", check_no_dangling),
    ("term-use", check_term_use),
    ("verifier-rules", check_verifier_rules),
    ("cross-cutting", check_cross_cutting),
    ("refinement", check_refinement),
    ("scaffold-paths", check_scaffold_paths),
    ("seed-routes", check_seed_routes),
    ("prose-ids", check_prose_ids),
):
    register_graph_check(_name, _rule)

register_gap_provider(role_gaps)
