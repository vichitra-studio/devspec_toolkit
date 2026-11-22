"""The production-deploy gate (``specdev release check --stage prod --tag <t>``): is the release at a tag fit to deploy to production?

The spec is read AT the tag (ruling N3: its node set, the nodes it relieved, its environments and its declarations, through
``release.tag_state``); the evidence records are read from the CHECKOUT, which holds the staging evidence that reached the
repository later through the evidence pull request.  The code tree the evidence must name is the tag's, with the spec folder left
out, so a descendant commit that only adds evidence leaves it as it was.  Nothing is checked about the tag itself: no signature,
no history, no first-parent rule.  Nothing is written.

In this order:

1. the tag must name a commit (E921);
2. every in-play obligation of the tag that is not a delivery obligation has valid evidence for every binding up to ``staging``
   (E347 / E348 from ``proof_errors``, with the owner ``release-gate``: ruling N2, one fact one code);
3. every in-play delivery obligation is built at ``staging`` (E923);
4. every node the tag relieved at ``ci`` (its proof waited for staging or production) is built at ``staging`` or waits only for
   ``prod`` (E924; a delivery obligation E923 names is not named again);
5. a retired staging environment (``scope: out``) is skipped with W934.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.graph.gitview import GitViewError
from specdev_tools.graph.model import Node
from specdev_tools.graph.names import DELIVERY_ROLE, ENVIRONMENT, OBLIGATION_ROLES
from specdev_tools.graph.stages import CI_STAGE, DEPLOY_ENVIRONMENTS
from specdev_tools.proof.built_evidence import built_at_cap, relieved_nodes
from specdev_tools.proof.proof import proof_errors
from specdev_tools.graph.ownership import RELEASE_OWNER
from specdev_tools.release.tag_state import TagState, resolve_tag, tag_state
from specdev_tools.trace.coverage import PARKED_SCOPES
from specdev_tools.validation.graph_checks.built import BuiltResult, BuiltState

STAGING_STAGE = DEPLOY_ENVIRONMENTS[0]
_SCOPE_OUT = PARKED_SCOPES[-1]


@dataclass(frozen=True)
class ProdGateResult:
    """What the production-deploy gate found at *tag* (resolved to *commit*, whose code tree is *code_tree*): ``errors`` block the deploy, ``warnings`` do not."""

    tag: str
    commit: str
    code_tree: str
    errors: tuple[SpecError, ...]
    warnings: tuple[SpecError, ...]

    @property
    def passed(self) -> bool:
        """Whether nothing blocks the deploy."""
        return not self.errors


def _commit_of(git_root: str, tag: str) -> str:
    try:
        return resolve_tag(tag, git_root)
    except GitViewError as error:
        raise FindingError(make_error("E921", f"'{tag}' names no commit in this repository; fetch the tags (`git fetch --tags`) or name an existing release tag")) from error


def _in_play_obligations(state: TagState) -> list[Node]:
    return [node for node in state.checks.in_play_nodes() if node.role in OBLIGATION_ROLES]


def _evidence_errors(state: TagState, scope: list[Node]) -> list[SpecError]:
    """E347 / E348 for the obligations of *scope* that are not delivery obligations, owned by the release gate (ruling N2)."""
    ids = [node.id for node in scope if node.role != DELIVERY_ROLE]
    return [replace(error, owner=RELEASE_OWNER) for error in proof_errors(state.graph, state.proof, ids, STAGING_STAGE)]


def _delivery_errors(state: TagState, scope: list[Node], built: dict[str, BuiltResult]) -> list[SpecError]:
    """E923 for each in-play delivery obligation that is not built at ``staging``."""
    return [
        state.checks.finding("E923", node, f"delivery obligation {node.id} is not built at staging ({built[node.id].reason}); build it before the release is deployed to production")
        for node in scope if node.role == DELIVERY_ROLE and built[node.id].state is BuiltState.NOT_BUILT
    ]


def _relieved_errors(state: TagState, built: dict[str, BuiltResult], delivery: list[SpecError]) -> list[SpecError]:
    """E924 for each node relieved at ``ci`` that is not built at ``staging``, except the delivery obligations *delivery* (E923) already names."""
    reported = {error.node_id for error in delivery}
    return [
        state.checks.finding("E924", node, f"{node.kind} {node.id} was relieved at the release gate (its proof waited for a later stage) and is not built at staging ({built[node.id].reason}); run its staging proof")
        for node in relieved_nodes(state.checks, CI_STAGE)
        if node.id not in reported and built[node.id].state is BuiltState.NOT_BUILT
    ]


def _staging_skipped(state: TagState) -> list[SpecError]:
    """W934 when the staging environment of the tag is retired (``scope: out``)."""
    retired = [node for node in state.graph.gated_nodes() if node.kind == ENVIRONMENT and node.id == STAGING_STAGE and node.scope == _SCOPE_OUT]
    return [make_error("W934", f"stage {STAGING_STAGE} is skipped: its environment is retired (scope out), so no staging evidence is asked for", node_id=node.id, owner=RELEASE_OWNER) for node in retired]


def run_prod_gate(git_root: str, spec_root: str, repo_root: str, tag: str) -> ProdGateResult:
    """The production-deploy gate for *tag* in the host at *git_root* whose checkout spec folder is *spec_root* (see the module text).

    Raises:
        FindingError: E921 when *tag* names no commit; E708 when git cannot answer or the spec folder is absent at the tag;
            E760 when the lock at the tag cannot be read; E520 when the declarations cannot be read.
    """
    commit = _commit_of(git_root, tag)
    with tag_state(git_root, spec_root, repo_root, commit) as state:
        scope = _in_play_obligations(state)
        built = built_at_cap(state.checks, STAGING_STAGE)
        evidence = _evidence_errors(state, scope)
        delivery = _delivery_errors(state, scope, built)
        errors = [*evidence, *delivery, *_relieved_errors(state, built, delivery)]
        return ProdGateResult(tag, commit, state.proof.code_tree, tuple(errors), tuple(_staging_skipped(state)))
