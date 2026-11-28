"""The graph checks: rules about the nodes of the spec graph (use, verifiers, refinement, routes, prose).

``register_graph_check(name, rule)`` is the one place a graph check is registered: it makes the rule known to
``run_graph_checks(ctx, mode, only)`` and gives it the ``spec-check`` check of the same name, so the plain run and
the step gate run it too.  The eight rules of this package (``BUILTIN_GRAPH_CHECKS``) are in the rule
table ``GRAPH_CHECKS`` as soon as the package is imported (plain data: no other module is touched); the ``spec-check``
side is published by ``publish_graph_checks()``, which the registration block of ``validation/spec_check.py`` calls at
the place of the checks in the order.  The replay gap provider is installed by ``install_gap_provider()``, which the CLI
calls.
"""
from __future__ import annotations

from collections.abc import Callable

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.model import Graph
from specdev_tools.graph.ownership import STEP_PREFIX
from specdev_tools.trace.gaps import CoverageGap, has_gap_provider, register_gap_provider
from specdev_tools.trace.lockfile import Lock
from specdev_tools.validation import check_registry
from specdev_tools.validation.check_registry import CheckFn

from .codes import ROLE_GAP_CODES
from .context import MODES, GraphCheckContext, Mode, merge_check
from .cross_cutting import check_cross_cutting
from .no_dangling import check_no_dangling
from .prose_ids import check_prose_ids
from .refinement import check_refinement
from specdev_tools.graph.names import MERGE
from .scaffold import check_scaffold_paths, run_scaffold_paths
from .seed_routes import check_seed_routes
from .term_use import check_term_use
from .verifiers import check_verifier_rules

GraphCheck = Callable[[GraphCheckContext, Mode], list[SpecError]]
"""A rule: ``rule(ctx, mode) -> findings``.  A rule that does not differ by *mode* ignores it."""

BUILTIN_GRAPH_CHECKS: tuple[tuple[str, GraphCheck, CheckFn | None], ...] = (
    ("no-dangling", check_no_dangling, None),
    ("term-use", check_term_use, None),
    ("verifier-rules", check_verifier_rules, None),
    ("cross-cutting", check_cross_cutting, None),
    ("refinement", check_refinement, None),
    ("scaffold-paths", check_scaffold_paths, run_scaffold_paths),
    ("seed-routes", check_seed_routes, None),
    ("prose-ids", check_prose_ids, None),
)
"""The rules of this package, in the order of their ``spec-check`` entries: name, rule and, for a rule that needs more than the merge wrapper, its own ``spec-check`` function."""

GRAPH_CHECKS: list[tuple[str, GraphCheck]] = [(name, rule) for name, rule, _check in BUILTIN_GRAPH_CHECKS]
"""The rules ``run_graph_checks`` runs, in order, by name: the built-in ones from the import on, then each ``register_graph_check`` appends."""

_BUILTIN_CHECK_FUNCTIONS: dict[str, tuple[GraphCheck, CheckFn]] = {name: (rule, check) for name, rule, check in BUILTIN_GRAPH_CHECKS if check is not None}
_registered_check_functions: dict[str, CheckFn] = {}
_published = False


def register_graph_check(name: str, rule: GraphCheck, *, check: CheckFn | None = None) -> None:
    """Register the rule *rule* (``rule(ctx, mode) -> findings``) under *name*: ``run_graph_checks`` runs it and ``spec-check`` runs the check *name*, after the checks registered before.

    The ``spec-check`` check is *check* when given, else the merge wrapper of *rule* (``merge_check``: the rule at
    ``merge`` mode, a skip with ``GRAPH_NOT_BUILT`` when no graph could be built).  Called before
    ``publish_graph_checks`` has run, the rule only joins the table and the publication gives it its check; called
    after, the check is registered at once.

    A registration that raises changes nothing.  A built-in rule that was unregistered and is registered again gets
    its own ``spec-check`` function back (the scaffold rule keeps its note and skip), at the end of the table.

    Raises:
        ValueError: a rule or a check of that name is already registered.
    """
    if any(registered == name for registered, _ in GRAPH_CHECKS):
        raise ValueError(f"graph check {name!r} is already registered")
    function = _check_function(name, rule, check)
    if _published:
        check_registry.register_check(name, function)
    if check is not None:
        _registered_check_functions[name] = check
    GRAPH_CHECKS.append((name, rule))


def _check_function(name: str, rule: GraphCheck, check: CheckFn | None = None) -> CheckFn:
    """The ``spec-check`` function of the rule *name*: the one given at registration, else the built-in rule's own (only when *rule* IS the built-in rule of that name), else the merge wrapper."""
    builtin_rule, builtin_check = _BUILTIN_CHECK_FUNCTIONS.get(name, (None, None))
    return check or _registered_check_functions.get(name) or (builtin_check if rule is builtin_rule else None) or merge_check(rule)


def unregister_graph_check(name: str) -> None:
    """Remove the rule *name* and its ``spec-check`` check (for tests: a test undoes its ``register_graph_check`` with it).

    Raises:
        ValueError: no rule of that name is registered.
    """
    for index, (registered, _) in enumerate(GRAPH_CHECKS):
        if registered == name:
            if _published:
                check_registry.unregister_check(name)
            _registered_check_functions.pop(name, None)
            del GRAPH_CHECKS[index]
            return
    raise ValueError(f"graph check {name!r} is not registered")


def publish_graph_checks() -> None:
    """Register the ``spec-check`` check of every rule of the table, in order; ``validation/spec_check.py`` calls it once, in its registration block.

    Raises:
        ValueError: it was called before.
    """
    global _published
    if _published:
        raise ValueError("the graph checks are already published")
    for name, rule in GRAPH_CHECKS:
        check_registry.register_check(name, _check_function(name, rule))
    _published = True


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
    findings = run_graph_checks(GraphCheckContext.from_graph(graph, lock), MERGE, only=set(ROLE_GAP_CODES))
    return [
        CoverageGap(error.code, error.node_id, error.owner.removeprefix(STEP_PREFIX))
        for error in findings
        if error.node_id is not None and error.owner is not None and error.owner.startswith(STEP_PREFIX)
    ]


def install_gap_provider() -> None:
    """Make ``specdev stale``, ``coverage`` and ``step ready`` report the role gaps (``role_gaps``) from now on; does nothing when it is installed already.

    A caller that reads coverage gaps in process and does not go through the CLI calls it too: ``trace`` does not
    import this package, so without the call there are no gaps.
    """
    if not has_gap_provider(role_gaps):
        register_gap_provider(role_gaps)
