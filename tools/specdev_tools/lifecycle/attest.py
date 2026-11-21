"""``specdev verify attest``: a person attests a manual fixture, a review-enforced rule or an at-deploy action; and ``review_rule_attested``.

Not ``specdev attest`` (``trace/attest.py``), which re-accepts links.  This command writes evidence the proof reads: for a
node, one evidence record of type ``attestation`` (``extras/verification/evd-<node id>-attested.json``); for a plan action
``<ITEM>/<action-id>`` marked ``at_deploy``, the deploy record ``plan record --at-deploy`` writes (``record_at_deploy``).

The file name of an attestation ends in ``-attested``: a stage ends a run's evidence (``evd-<binding>-<stage>``) and
``-install`` ends an install check, so an attestation and a run, or an install check, never share a file.  One file per node: a
second attestation of the node replaces the first.  The stage an attestation claims is the stage its node needs
(``computed_stage``, the function a binding's stage comes from) unless ``--stage`` says another.

All-or-nothing: every target is checked before one record is written.  The git author is recorded for the audit trail; nothing
checks who runs the command (the ask rule of the host is the operator's approval).
"""
from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..core.errors import FindingError, SpecError, make_error, refusal
from ..core.json_utils import resolve_effective_toolkit_root
from ..graph.commands import print_json, resolve_git_root, run_on_graph, usage_error
from ..graph.contract import item_of
from ..graph.model import Graph, Node
from ..graph.names import FIXTURE, PLAN_ITEM, RULE
from ..graph.ownership import load_owner_context, owner_for
from ..graph.queries import nearest_suffix
from ..graph.stages import UnknownStageForEnvironment
from ..proof.proof import NOT_REQUIRED, PROVEN, is_attested_by_person, verifier_proof
from ..proof.validity import NO_EVIDENCE, ProofContext
from ..trace.writing import locked_graph
from ..verify.bind import computed_stage, targets_of
from ..verify.records import ATTESTATION_TYPE, EVIDENCE_PREFIX, records_folder, write_evidence
from . import executed
from .plan_records import Address, parse_address, record_at_deploy
from .records import git_author

ATTESTED_SUFFIX = "-attested"
NO_ATTESTATION = "NO_ATTESTATION"
RELEASE_CAP = "prod"


def attestation_id(node_id: str) -> str:
    """The id (and file stem) of the attestation record of *node_id*: ``evd-``, the id, ``-attested``."""
    return f"{EVIDENCE_PREFIX}{node_id}{ATTESTED_SUFFIX}"


@dataclass(frozen=True)
class NodeTarget:
    """A node to attest: the claim it is made at and where that stage came from (``stage_given`` false: the stage the node needs)."""

    node: Node
    text: str
    stage: str
    stage_given: bool


@dataclass(frozen=True)
class ActionTarget:
    """A plan action to attest as done: its address and the action's description."""

    address: Address
    text: str


@dataclass(frozen=True)
class AttestPlan:
    """What a command will write: the node attestations and the at-deploy records, in the order the ids were given."""

    nodes: tuple[NodeTarget, ...]
    actions: tuple[ActionTarget, ...]
    env: str | None


@dataclass(frozen=True)
class Attested:
    """One record written: the id it is about, its kind (``attestation`` or ``at-deploy``), the record file and the record."""

    about: str
    type: str
    file: str
    record: dict[str, Any]


@dataclass(frozen=True)
class AttestResult:
    """What a command did: the plan it carried out and the records it wrote, in the order of the plan (nodes, then actions)."""

    plan: AttestPlan
    written: tuple[Attested, ...]


def _text_of(item: Mapping[str, Any] | None) -> str:
    """The sentence a person reads to know what is attested: a rule's ``text``, else a fixture's or an action's ``description``."""
    body = item or {}
    return str(body.get("text") or body.get("description") or "")


def _not_attestable(node: Node, graph: Graph) -> FindingError:
    item = item_of(graph, node) or {}
    if node.kind == FIXTURE:
        return refusal(
            "E824",
            f"fixture {node.id} has mode {item.get('mode')}, not manual, so it is bound and run, not attested; "
            f"bind it with `specdev verify bind {node.id} --command CMD --guard REGEX`",
        )
    if node.kind == RULE:
        return refusal(
            "E824",
            f"rule {node.id} is not enforced by review, so no person attests it; a rule enforced by a job or a command is proved by that job or command",
        )
    return refusal("E824", f"{node.id} is a {node.kind}; verify attest takes a manual fixture, a rule enforced by review, or a plan action ITEM/action marked at_deploy")


def _stage_of(node: Node, graph: Graph, given: str | None) -> tuple[str, bool]:
    """The stage the attestation of *node* claims, and whether it was given: ``--stage``, else the stage the node needs.

    Raises:
        FindingError: E334 when the stage the node needs cannot be told (an NFR it verifies declares a stage that is not one).
    """
    if given is not None:
        return given, True
    try:
        return computed_stage(targets_of(node, graph), node, graph), False
    except (UnknownStageForEnvironment, ValueError) as exc:
        raise refusal("E334", f"the stage {node.id} needs cannot be told ({exc}); give --stage dev, ci, staging or prod") from exc


def _node_target(graph: Graph, node: Node, given_stage: str | None) -> NodeTarget:
    if not is_attested_by_person(node, graph):
        raise _not_attestable(node, graph)
    stage, stage_given = _stage_of(node, graph, given_stage)
    return NodeTarget(node, _text_of(item_of(graph, node)), stage, stage_given)


def _action_target(graph: Graph, address: Address, env: str) -> ActionTarget:
    """The action *address* when it is marked ``at_deploy`` for *env*.

    Raises:
        FindingError: E824 when there is no such plan item or action, or the action is not marked for *env*.
    """
    item = graph.find(address.item)
    if item is None or item.kind != PLAN_ITEM:
        raise refusal("E824", f"{address} is not a plan action: no plan item {address.item}{nearest_suffix(address.item, (n.id for n in graph.by_kind.get(PLAN_ITEM, ())))}")
    actions = [action for action in executed.actions_of(item_of(graph, item) or {}) if action.get("id") == address.action]
    if len(actions) != 1:
        known = ", ".join(str(action["id"]) for action in executed.actions_of(item_of(graph, item) or {}) if "id" in action) or "none with an id"
        raise refusal("E824", f"{address} is not a plan action: {item.id} has no single action {address.action} (its actions: {known})")
    marked = executed.at_deploy_of(actions[0])
    if env not in marked:
        now = f"marked at_deploy for {', '.join(marked)}" if marked else "not marked at_deploy"
        raise refusal("E824", f"{address} is {now}, not for {env}; only an action marked at_deploy for the environment is attested with --env {env}")
    return ActionTarget(address, _text_of(actions[0]))


def plan_attest(graph: Graph, ids: Sequence[str], stage: str | None = None, env: str | None = None) -> AttestPlan:
    """The records ``verify attest`` of *ids* would write, or the first refusal: nothing is written for any id when one is refused.

    An id with a ``/`` is a plan action ``<ITEM>/<action-id>`` (it needs *env*); any other id is a node.  *stage* overrides the
    stage a node attestation claims.  An id given twice, or by an old name, is one target.

    Raises:
        FindingError: E824 for an id that is not attestable (unknown, a fixture that is not manual, a rule not enforced by
            review, another kind of node, an action not marked ``at_deploy`` for *env*); E334 when a node's stage cannot be told.
    """
    nodes: dict[str, NodeTarget] = {}
    actions: dict[str, ActionTarget] = {}
    for name in dict.fromkeys(ids):
        if "/" in name:
            address = parse_address(name)
            if address is None or env is None:
                raise refusal("E824", f"{name!r} is not <plan item id>/<action id>, for example PWRESET_CONFIRM_EXPIRED_01/a01")
            actions[str(address)] = _action_target(graph, address, env)
            continue
        node = graph.find(name)
        if node is None:
            raise refusal("E824", f"no node with the id {name!r}{nearest_suffix(name, graph.by_id)}")
        nodes[node.id] = _node_target(graph, node, stage)
    return AttestPlan(tuple(nodes.values()), tuple(actions.values()), env)


def _write_nodes(graph: Graph, spec_root: str, repo_root: str, git_root: str, targets: Sequence[NodeTarget], author: dict[str, str]) -> list[Attested]:
    """Write one attestation record for each of *targets*: on the code tree of the host now, with the content hash of the node now.

    The caller holds the write lock and built *graph* under it.

    Raises:
        FindingError: E774 when a record would break its schema; E520 for an unreadable host declarations file.
        GitViewError: E708 when git fails.
    """
    if not targets:
        return []
    ctx = ProofContext(git_root, spec_root, records_folder(spec_root))
    hashes = ctx.content_hashes(graph)
    written: list[Attested] = []
    for target in targets:
        node_id = target.node.id
        item: dict[str, Any] = {
            "evidence_id": attestation_id(node_id), "about": [node_id], "type": ATTESTATION_TYPE, "stage": target.stage,
            "tested_tree": ctx.code_tree, "recorded_hashes": {node_id: hashes[node_id]}, "git_author": author,
        }
        name = write_evidence(records_folder(spec_root), repo_root, item)
        written.append(Attested(node_id, ATTESTATION_TYPE, os.path.join(os.path.relpath(records_folder(spec_root), spec_root), name), item))
    return written


def _plan_lines(plan: AttestPlan) -> list[str]:
    lines = [f"attesting {len(plan.nodes) + len(plan.actions)} target(s):"]
    for target in plan.nodes:
        source = "given by --stage" if target.stage_given else "the stage it needs; --stage overrides it"
        lines.append(f"  {target.node.id} ({target.node.kind}) at stage {target.stage} ({source}): {target.text}")
    lines.extend(f"  {target.address} (plan action) done at {plan.env}: {target.text}" for target in plan.actions)
    return lines


def _written_lines(written: Sequence[Attested]) -> list[str]:
    return [f"attested {entry.about}: {entry.file}" if entry.type == ATTESTATION_TYPE else f"recorded {entry.record['deploy_id']}: {entry.about} done at {entry.record['env']} ({entry.file})" for entry in written]


def attest(
    spec_root: str, repo_root: str, git_root: str, plan_for: Callable[[Graph], AttestPlan], announce: Callable[[AttestPlan], None] | None = None,
) -> AttestResult:
    """Plan with *plan_for* (a function of the graph built under the write lock), then write what it planned.

    *announce*, when given, is called with the plan before anything is written.  The node attestations are written under that
    lock; the at-deploy records follow, each through ``record_at_deploy`` (it takes the lock itself).

    Raises:
        FindingError: what *plan_for* raises; E767 when git names no author for a node attestation; E774 and E520 from the writer; E821, E803, E774 or E769 from ``record_at_deploy``; E769 when another write holds the lock.
        GitViewError: E708 when git fails.
    """
    with locked_graph(spec_root, repo_root, "verify attest") as graph:
        plan = plan_for(graph)
        author = git_author(git_root).as_record() if plan.nodes else {}
        if announce is not None:
            announce(plan)
        written = _write_nodes(graph, spec_root, repo_root, git_root, plan.nodes, author)
    for target in plan.actions:
        deployed = record_at_deploy(spec_root, repo_root, git_root, target.address, plan.env or "", "done")
        written.append(Attested(str(target.address), "at-deploy", deployed.file, deployed.record))
    return AttestResult(plan, tuple(written))


def _document(result: AttestResult) -> dict[str, Any]:
    plan = result.plan
    return {
        "command": "verify attest",
        "targets": [{"id": t.node.id, "kind": t.node.kind, "stage": t.stage, "stage_given": t.stage_given, "text": t.text} for t in plan.nodes]
        + [{"id": str(t.address), "kind": "plan-action", "env": plan.env, "text": t.text} for t in plan.actions],
        "records": [{"about": entry.about, "type": entry.type, "file": entry.file, "record": entry.record} for entry in result.written],
    }


def _usage_problem(ids: Sequence[str], env: str | None) -> str | None:
    has_action = any("/" in name for name in ids)
    if has_action and env is None:
        return "an at-deploy action <plan item id>/<action id> needs --env staging or --env prod"
    return "--env goes with a plan action <plan item id>/<action id>" if env is not None and not has_action else None


def run_verify_attest(args: argparse.Namespace) -> int:
    """Run ``specdev verify attest`` on the parsed *args*; returns the exit code (0 written, 1 refused, 2 usage)."""
    problem = _usage_problem(args.node_ids, args.env)
    if problem is not None:
        return usage_error("verify attest", problem)
    spec_root, repo_root, git_root = os.path.abspath(args.spec_root), os.path.abspath(args.repo_root), resolve_git_root(args)

    def announce(plan: AttestPlan) -> None:
        if not args.json_output:
            print("\n".join(_plan_lines(plan)))

    def run(_graph: Graph) -> int:
        result = attest(spec_root, repo_root, git_root, lambda graph: plan_attest(graph, args.node_ids, args.stage, args.env), announce)
        if args.json_output:
            print_json(_document(result))
        else:
            print("\n".join(_written_lines(result.written)))
        return 0

    return run_on_graph("verify attest", args, run)


def review_rule_attested(rule_id: str, graph: Graph, ctx: ProofContext) -> list[SpecError]:
    """The finding of the release gate for the rule *rule_id* (enforced by ``review``): ``[]`` when a valid attestation of it exists, else one E830.

    A thin layer over ``verifier_proof`` at the release cap: one definition of "attested".  The E830 carries the shortfall's
    reason as its subcode: ``NO_ATTESTATION`` when the rule has no attestation, ``STALE_HASH`` when it was attested before the
    rule changed, ``STALE_TREE`` when it was attested on another code tree.  Its owner is the release gate.

    Raises:
        KeyError: no node has the id *rule_id*.
        ValueError: the node is not a rule enforced by ``review``.
        GitViewError: E708 when git fails.
        FindingError: E520 when the host declarations cannot be read.
    """
    node = graph.find(rule_id)
    if node is None:
        raise KeyError(rule_id)
    if node.kind != RULE or not is_attested_by_person(node, graph):
        raise ValueError(f"{node.id} is not a rule enforced by review")
    result = verifier_proof(graph, ctx, node.id, RELEASE_CAP)
    if result.status in (PROVEN, NOT_REQUIRED):
        return []
    reason = result.shortfalls[0].reason if result.shortfalls else NO_EVIDENCE
    subcode = NO_ATTESTATION if reason == NO_EVIDENCE else reason
    owners = load_owner_context(resolve_effective_toolkit_root(None))
    return [make_error(
        "E830",
        f"rule {node.id} is enforced by review and has no valid attestation ({subcode}); run `specdev verify attest {node.id}` after the review",
        file=node.file, jq_path=node.jq_path or None, node_id=node.id, subcode=subcode, owner=owner_for("E830", node, owners),
    )]
