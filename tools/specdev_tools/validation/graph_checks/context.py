"""The context every graph check runs on: the graph, the lock, the play state of a node, the owner of a finding.

``GraphCheckContext`` is not the registry's ``CheckContext`` (the argument of a registered check): it holds what the
graph checks read from one, built once through ``GraphCheckContext.from_registry``.  The replay gap provider has no
registry context and builds one from a graph and a lock (``GraphCheckContext.from_graph``).

Four seams carry what the proof package (``specdev_tools.proof``) knows.  Each is a function of the context and the
node, has a default that says "nothing known" and is replaced through ``bind_seams``, which returns the function that
removes that binding.  This package cannot import ``proof``, so the callers bind its three implementations
(``proof.built_evidence.bind_proof_seams``): ``cli.py`` when it builds the parser and ``validation/spec_check.py`` when it is imported.
A path that builds a context without either has the defaults.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from functools import cached_property
from typing import Any, Literal, get_args

from specdev_tools.core.constants import SEED_MANIFEST_FILE
from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.core.json_utils import resolve_effective_toolkit_root
from specdev_tools.core.scope_helpers import as_dict
from specdev_tools.graph.gitview import read_seed_texts, read_seed_texts_noting
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.ownership import OwnerContext, load_owner_context, owner_for
from specdev_tools.trace.coverage import exemption
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.trace.lockfile import Lock
from specdev_tools.validation import check_registry
from specdev_tools.validation.check_registry import CheckContext, CheckFn

from specdev_tools.graph.names import MERGE, VERIFIER_ROLE
from .schema_slots import SchemaSlots
from .use_table import furthest_steps

Mode = Literal["merge", "close", "release"]
"""When a rule runs: at merge (the step view ``spec-check`` always runs), at milestone close, at release."""
MODES: tuple[str, ...] = get_args(Mode)
GRAPH_NOT_BUILT = "graph could not be built (see the `graph` check)"
PIN_UNKNOWN = "UNKNOWN"


def _no_ids(_ctx: GraphCheckContext, _node: Node) -> set[str]:
    return set()


def _pin_unknown(_ctx: GraphCheckContext, _third_party: Node) -> str:
    return PIN_UNKNOWN


@dataclass(frozen=True)
class Seams:
    """The four answers the proof package supplies (three of them: ``extra_verifiers`` is unbound by design), each a function of the context and the node; each default says that nothing is known.

    ``retired_bindings(ctx, verifier)``: the retired bindings of a verifier whose bindings are all retired, else empty.
    ``record_users(ctx, verifier)``: the verification or evidence records that name the verifier.
    ``extra_verifiers(ctx, verifier)``: the ids the verifier covers beyond its ``verifies``.
    ``pin_matches(ctx, third_party)``: ``OK``, ``MISMATCH`` or ``UNKNOWN`` for the pin of a third party.
    """

    retired_bindings: Callable[[GraphCheckContext, Node], set[str]] = _no_ids
    record_users: Callable[[GraphCheckContext, Node], set[str]] = _no_ids
    extra_verifiers: Callable[[GraphCheckContext, Node], set[str]] = _no_ids  # unbound by design: no package supplies it; two checks read it
    pin_matches: Callable[[GraphCheckContext, Node], str] = _pin_unknown


_NOTHING_KNOWN = Seams()
_bindings: list[dict[str, Callable[..., Any]]] = []
_bound = _NOTHING_KNOWN


def bind_seams(**seams: Callable[..., Any]) -> Callable[[], None]:
    """Bind the named seams of ``Seams`` for every context built afterwards; returns the function that removes this binding.

    A later binding of the same seam wins while both are in place; the restore function removes only its own binding,
    in whatever order the restores are called, and a second call does nothing.

    Raises:
        TypeError: a name is not a seam.
    """
    global _bound
    replace(_NOTHING_KNOWN, **seams)
    mine = dict(seams)
    _bindings.append(mine)
    _bound = _merged_bindings()

    def restore() -> None:
        global _bound
        for index, binding in enumerate(_bindings):
            if binding is mine:
                del _bindings[index]
                _bound = _merged_bindings()
                return

    return restore


def _merged_bindings() -> Seams:
    return replace(_NOTHING_KNOWN, **{name: fn for binding in _bindings for name, fn in binding.items()})


def merge_check(rule: Callable[[GraphCheckContext, Mode], list[SpecError]]) -> CheckFn:
    """The ``spec-check`` function of *rule*: its findings at ``merge`` mode, or a skip with ``GRAPH_NOT_BUILT`` when no graph could be built."""

    def run(ctx: CheckContext) -> dict[str, Any]:
        graph_ctx = GraphCheckContext.from_registry(ctx)
        if graph_ctx is None:
            return check_registry.skip(GRAPH_NOT_BUILT)
        return check_registry.check_result(rule(graph_ctx, MERGE))

    return run


@dataclass(eq=False)
class GraphCheckContext:
    """The graph, the lock and the helpers every graph check shares, built once for each registered check of a run (``merge_check``), not once per run.

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
    memo: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    """What a seam computes once for this context, by key (the proof package keeps its proof context and the pin results here); a copy made with ``replace`` starts empty."""

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
    def from_graph(
        cls, graph: Graph, lock: Lock | None, repo_root: str | None = None, *, git_root: str | None = None, spec_root: str | None = None,
    ) -> GraphCheckContext:
        """The context of a caller that has a graph and a lock but no registry context (the replay gap provider, a gate, a test); *repo_root* defaults to the toolkit this package belongs to.

        *git_root* and *spec_root* are the host repository and its spec folder; without *git_root* the context has no seed
        texts and the scaffold check has nothing to read.

        Raises:
            FindingError: E520 when the ownership table of the toolkit cannot be read.
        """
        root = repo_root or resolve_effective_toolkit_root(None)
        return cls(
            graph=graph, lock=lock, owner_context=cls._with_furthest_steps(load_owner_context(root), graph), repo_root=root,
            git_root=git_root, spec_root=spec_root,
        )

    @staticmethod
    def _with_furthest_steps(owner_context: OwnerContext, graph: Graph) -> OwnerContext:
        return replace(owner_context, furthest_step=furthest_steps(graph.decls, graph.shape))

    @cached_property
    def historical(self) -> set[str]:
        """Ids of the closed work: each milestone whose anchor row says ``done``, what it contains and the nodes its plans name (``trace.history.historical_node_ids``), computed once per context."""
        return historical_node_ids(self.graph)

    @cached_property
    def slots(self) -> SchemaSlots:
        """The schema slots of the nodes' files (``SchemaSlots``), read from the toolkit at ``repo_root`` and the extension schemas of ``spec_root``; each file's schema is loaded once per context."""
        return SchemaSlots(self.repo_root, self.spec_root)

    @cached_property
    def manifest(self) -> Mapping[str, Any]:
        """The seed manifest as the graph read it; empty when the spec has none."""
        return as_dict(self.graph.documents.get(SEED_MANIFEST_FILE))

    @cached_property
    def seed_texts(self) -> dict[str, str]:
        """The text of each seed document under the host root (empty without a host root); a missing document is noted on stderr unless the run is quiet."""
        if self.git_root is None:
            return {}
        read = read_seed_texts if self.quiet else read_seed_texts_noting
        return read(self.graph, self.git_root)

    def retired_bindings(self, node: Node) -> set[str]:
        """The seam ``Seams.retired_bindings``."""
        return self.seams.retired_bindings(self, node)

    def record_users(self, node: Node) -> set[str]:
        """The seam ``Seams.record_users``."""
        return self.seams.record_users(self, node)

    def extra_verifiers(self, node: Node) -> set[str]:
        """The seam ``Seams.extra_verifiers``."""
        return self.seams.extra_verifiers(self, node)

    def pin_matches(self, third_party: Node) -> str:
        """The seam ``Seams.pin_matches``."""
        return self.seams.pin_matches(self, third_party)

    def in_play(self, node: Node) -> bool:
        """Whether the checks read *node*.

        Out of play: what ``trace.coverage.exemption`` leaves out of every denominator (lifecycle ``not_applicable``,
        scope ``later`` or ``out``), or a verifier whose bindings are all retired.  A ``deprecated`` node stays in play
        (it is still binding and fully gated).
        """
        if exemption(node) is not None:
            return False
        return not (node.role == VERIFIER_ROLE and self.retired_bindings(node))

    def in_play_nodes(self) -> list[Node]:
        """The in-play nodes in the order of every listing (step, then id); the one place a check starts from."""
        return sorted((node for node in self.graph.gated_nodes() if self.in_play(node)), key=self.graph.shape.order_key)

    def finding(
        self, code: str, node: Node, message: str, *, target: str | None = None, owner: str | None = None,
        route: tuple[str, str] | None = None, file: str | None = None, jq_path: str | None = None,
    ) -> SpecError:
        """The finding *code* about *node*: it carries the node's file, jq path and id, and the owner the ownership table gives for *code* and *node* (``None`` when the table has none).

        *target* names the one link a finding is about; *owner*, *file* and *jq_path*, when given, win over the table's
        and the node's; *route* is the ``(seed id, step)`` of a seed-route finding (``SpecError.route``).
        """
        return make_error(
            code, message, file=file if file is not None else node.file,
            jq_path=jq_path if jq_path is not None else (node.jq_path or None), node_id=node.id,
            owner=owner if owner is not None else owner_for(code, node, self.owner_context), target=target, route=route,
        )
