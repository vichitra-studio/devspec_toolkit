"""The coverage-gap seam: where replay and ``step ready`` learn which nodes are unused or unproved.

A coverage gap is a finding of the role rules of the graph checks (an in-play node nothing uses, a verifier that is
unused or missing), grouped by the step that owns the node.  The toolkit computes none of them here: the checks that
decide what a gap is register a *provider* (``register_gap_provider``), and ``coverage_gaps`` concatenates what the
registered providers report.  With no provider registered there are no gaps.

The registered providers are module state (``_providers``): they live as long as the process.  M6b's provider is
installed by ``validation.graph_checks.install_gap_provider()``, which the CLI calls.  A test that registers one uses the ``gap_providers`` fixture of ``tests/unit/trace/_lock_support.py``,
which puts the list back when the test ends.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from specdev_tools.graph.model import Graph
from specdev_tools.trace.lockfile import Lock


@dataclass(frozen=True)
class CoverageGap:
    """A coverage gap: the error *code* of the role rule, the *node* it is about and the step that owns it (``None``: no home step)."""

    code: str
    node: str
    owner_step: str | None


GapProvider = Callable[[Graph, Lock], list[CoverageGap]]

_providers: list[GapProvider] = []


def register_gap_provider(provider: GapProvider) -> Callable[[], None]:
    """Add *provider* to the ones ``coverage_gaps`` asks; returns a function that removes it again.

    A provider takes the graph and the lock and returns its gaps.  Registering the same function twice makes it count
    twice.
    """
    _providers.append(provider)

    def unregister() -> None:
        _providers.remove(provider)

    return unregister


def has_gap_provider(provider: GapProvider) -> bool:
    """Whether *provider* is registered."""
    return provider in _providers


def coverage_gaps(graph: Graph, lock: Lock) -> list[CoverageGap]:
    """The gaps of every registered provider, in registration order; an empty list when none is registered."""
    return [gap for provider in tuple(_providers) for gap in provider(graph, lock)]
