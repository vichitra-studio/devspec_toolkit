"""The context every graph check runs on: the graph, the lock, the play state of a node, the owner of a finding.

``GraphCheckContext`` is not the registry's ``CheckContext`` (the argument of a registered check): it holds what the
graph checks read from one, built once through ``GraphCheckContext.from_registry``.  The replay gap provider has no
registry context and builds one from a graph and a lock (``GraphCheckContext.from_graph``).

Four seams are left for the proof milestone (M7).  Each has a default that says "nothing known" and is replaced
through ``bind_seams``, which returns the function that puts the previous binding back.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from functools import cached_property
from typing import Any, Literal, get_args

from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.core.json_utils import resolve_effective_toolkit_root
from specdev_tools.core.scope_helpers import as_dict
from specdev_tools.graph.gitview import read_seed_texts, read_seed_texts_noting
from specdev_tools.graph.model import NOT_APPLICABLE, Graph, Node
from specdev_tools.graph.ownership import OwnerContext, OwnershipTableError, load_ownership_table, owner_for
from specdev_tools.trace.history import done_milestones
from specdev_tools.trace.lockfile import Lock
from specdev_tools.validation.check_registry import CheckContext

from .use_table import VERIFIER_ROLE, furthest_steps

Mode = Literal["merge", "close", "release"]
"""When a rule runs: at merge (the step view ``spec-check`` always runs), at milestone close, at release."""
MODES: tuple[str, ...] = get_args(Mode)
GRAPH_NOT_BUILT = "graph could not be built (see the `graph` check)"
SEED_MANIFEST_PATH = "common/seed_manifest.json"
OUT_OF_PLAY_SCOPES = frozenset({"later", "out"})
IN_SCOPES = frozenset({"in"})
PIN_UNKNOWN = "UNKNOWN"


def _no_ids(_node: Node) -> set[str]:
    return set()


def _pin_unknown(_third_party: Node) -> str:
    return PIN_UNKNOWN


@dataclass(frozen=True)
class Seams:
    """The four answers the proof milestone supplies; each default says that nothing is known.

    ``retired_bindings(verifier)``: the retired bindings of a verifier whose bindings are all retired, else empty.
    ``record_users(verifier)``: the verification or evidence records that name the verifier.
    ``extra_verifiers(verifier)``: the ids the verifier covers beyond its ``verifies``.
    ``pin_matches(third_party)``: ``OK``, ``MISMATCH`` or ``UNKNOWN`` for the pin of a third party.
    """

    retired_bindings: Callable[[Node], set[str]] = _no_ids
    record_users: Callable[[Node], set[str]] = _no_ids
    extra_verifiers: Callable[[Node], set[str]] = _no_ids
    pin_matches: Callable[[Node], str] = _pin_unknown


_bound = Seams()


def bind_seams(**seams: Callable[..., Any]) -> Callable[[], None]:
    """Replace the named seams of ``Seams`` for every context built afterwards; returns the function that restores the previous binding.

    Raises:
        TypeError: a name is not a seam.
    """
    global _bound
    previous = _bound
    _bound = replace(previous, **seams)

    def restore() -> None:
        global _bound
        _bound = previous

    return restore


def ownership_context(repo_root: str) -> OwnerContext:
    """The ownership table of the toolkit at *repo_root*, with no furthest steps.

    Raises:
        FindingError: E520 when ``tools/error_ownership.json`` is missing or unreadable.
    """
    try:
        return OwnerContext(rows=load_ownership_table(repo_root))
    except OwnershipTableError as error:
        raise FindingError(make_error("E520", f"UNRESOLVED_INPUT ownership_table {error}")) from error


@dataclass(eq=False)
class GraphCheckContext:
    """The graph, the lock and the helpers every graph check shares, built once per run.

    ``git_root`` is the host repository root and ``spec_root`` the spec folder; both are ``None`` for a context built
    from a graph alone, which has no seed texts.  ``owner_context`` carries the furthest step that can use each kind.
    """

    graph: Graph
    lock: Lock | None
    owner_context: OwnerContext
    repo_root: str
    git_root: str | None = None
    spec_root: str | None = None
    quiet: bool = False
    seams: Seams = field(default_factory=lambda: _bound)

    @classmethod
    def from_registry(cls, ctx: CheckContext) -> GraphCheckContext | None:
        """The context of a registered check, built from the registry context *ctx*; ``None`` when no graph could be built (the check then skips with ``GRAPH_NOT_BUILT``).

        Raises:
            FindingError: E520 when the ownership table of the toolkit cannot be read.
        """
        graph = ctx.check_graph
        if graph is None:
            return None
        return cls(
            graph=graph,
            lock=ctx.lock_state[0],
            owner_context=cls._with_furthest_steps(ctx.owner_context, graph),
            repo_root=ctx.repo_root,
            git_root=ctx.project_root,
            spec_root=ctx.effective_spec_root,
            quiet=ctx.quiet,
        )

    @classmethod
    def from_graph(cls, graph: Graph, lock: Lock | None, repo_root: str | None = None) -> GraphCheckContext:
        """The context of a caller that has a graph and a lock but no registry context (the replay gap provider, a test); *repo_root* defaults to the toolkit this package belongs to.

        Raises:
            FindingError: E520 when the ownership table of the toolkit cannot be read.
        """
        root = repo_root or resolve_effective_toolkit_root(None)
        return cls(graph=graph, lock=lock, owner_context=cls._with_furthest_steps(ownership_context(root), graph), repo_root=root)

    @staticmethod
    def _with_furthest_steps(owner_context: OwnerContext, graph: Graph) -> OwnerContext:
        return replace(owner_context, furthest_step=furthest_steps(graph.decls, graph.shape))

    @cached_property
    def closed_milestones(self) -> set[str]:
        """Ids of the milestones whose anchor row says ``done``."""
        return done_milestones(self.graph)

    @cached_property
    def manifest(self) -> Mapping[str, Any]:
        """The seed manifest as the graph read it; empty when the spec has none."""
        return as_dict(self.graph.documents.get(SEED_MANIFEST_PATH))

    @cached_property
    def seed_texts(self) -> dict[str, str]:
        """The text of each seed document under the host root (empty without a host root); a missing document is noted on stderr unless the run is quiet."""
        if self.git_root is None:
            return {}
        read = read_seed_texts if self.quiet else read_seed_texts_noting
        return read(self.graph, self.git_root)

    @staticmethod
    def in_scope(node: Node) -> bool:
        """Whether *node* is in scope: ``scope`` is ``in`` or omitted (the builder keeps an omitted or wrong-typed scope as ``None``)."""
        return node.scope is None or node.scope in IN_SCOPES

    def retired_bindings(self, node: Node) -> set[str]:
        """The seam ``Seams.retired_bindings``."""
        return self.seams.retired_bindings(node)

    def record_users(self, node: Node) -> set[str]:
        """The seam ``Seams.record_users``."""
        return self.seams.record_users(node)

    def extra_verifiers(self, node: Node) -> set[str]:
        """The seam ``Seams.extra_verifiers``."""
        return self.seams.extra_verifiers(node)

    def pin_matches(self, third_party: Node) -> str:
        """The seam ``Seams.pin_matches``."""
        return self.seams.pin_matches(third_party)

    def in_play(self, node: Node) -> bool:
        """Whether the checks read *node*.

        Out of play: lifecycle ``not_applicable``, scope ``later`` or ``out``, or a verifier whose bindings are all
        retired.  A ``deprecated`` node stays in play (it is still binding and fully gated).
        """
        if node.lifecycle == NOT_APPLICABLE or node.scope in OUT_OF_PLAY_SCOPES:
            return False
        return not (node.role == VERIFIER_ROLE and self.retired_bindings(node))

    def in_play_nodes(self) -> list[Node]:
        """The in-play nodes in the order of every listing (step, then id); the one place a check starts from."""
        return sorted((node for node in self.graph.gated_nodes() if self.in_play(node)), key=self.graph.shape.order_key)

    def finding(
        self, code: str, node: Node, message: str, *, target: str | None = None, owner: str | None = None,
        route: tuple[str, str] | None = None,
    ) -> SpecError:
        """The finding *code* about *node*: it carries the node's file, jq path and id, and the owner the ownership table gives for *code* and *node* (``None`` when the table has none).

        *target* names the one link a finding is about; *owner*, when given, wins over the table's; *route* is the
        ``(seed id, step)`` of a seed-route finding (``SpecError.route``).
        """
        return make_error(
            code, message, file=node.file, jq_path=node.jq_path or None, node_id=node.id,
            owner=owner if owner is not None else owner_for(code, node, self.owner_context), target=target, route=route,
        )
