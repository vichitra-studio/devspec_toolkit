"""``specdev align propose --kind refines``: which obligation does each legacy task criterion narrow?

1.2.0 asks every step-14 task criterion for ``refines`` (the obligations it makes testable at task level).  A 1.1.1 host
has none; it has the task's ``fr_refs`` and ``invariant_refs``, which the capture keeps per task (``task_status``).  For
each task criterion that has no ``refines`` and no ``removes`` yet, the proposer

1. takes the nodes named by the task's legacy ``fr_refs`` and ``invariant_refs`` (an id the migration renamed is mapped
   through the capture's ``renames``) and reaches the candidates from them: those nodes, their descendants (the
   criteria of an FR, the errors of an API) and the nodes one declared link away in either direction with their
   descendants.  Only kinds the ``refines`` link accepts are candidates; the kinds are read from the link declaration
   of ``task-criterion`` (generated from ``schema/14_roadmap.schema.json``);
2. scores each candidate by the TF-IDF cosine of its text against the criterion's, over lower-cased tokens of three or
   more characters without stop words; the text of a node is its prose: the strings of its contract fields whose schema
   slot does not fix the value (no link field, no id, no enum), with every token that is a node id or an alias left out;
3. classes the criterion.

Classes:

* ``auto-eligible``: the best candidate is an acceptance criterion of step 04 (kind ``criterion``), scores ``MIN_SCORE``
  or more, and no other candidate scores within ``TIE_MARGIN`` of it.  Only these were measured (the fixture gate);
* ``needs-judgement``: a candidate scores, but the case is not auto-eligible: the best candidate is of another kind, or
  below ``MIN_SCORE``, or several nodes state the same rule (then the most downstream of them, by step order, is the
  target and the others are listed as alternatives: the design's rule for a rule stated in several places);
* ``none``: the task names no FR or invariant, none of its nodes reaches a candidate, or nothing scores.

It never matches by id: a task criterion and an obligation that carry the same id, or ids that look alike, are not a
signal, and a node whose id is defined twice is not a candidate (a proposal naming it would name two nodes).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from specdev_tools.graph.contract import path_steps
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.names import CRITERION, REFINES, REMOVES, TASK, TASK_CRITERION
from specdev_tools.migration.proposers import KIND_REFINES, MigratedTree, Proposal, ProposeResult
from specdev_tools.migration.worklist import AUDIENCE_AGENT, make_item
from specdev_tools.trace.label_rename import own_leaves
from specdev_tools.validation.graph_checks.prose_ids import is_fixed_leaf

MIN_SCORE = 0.6
"""The lowest score of an auto-eligible proposal."""
TIE_MARGIN = 0.05
"""Candidates within this score of the best one state the same rule as it does."""
STEP = "14"
CLASS_AUTO = "auto-eligible"
CLASS_JUDGEMENT = "needs-judgement"
CLASS_NONE = "none"
CLASSES = (CLASS_AUTO, CLASS_JUDGEMENT, CLASS_NONE)
ALTERNATIVES_LISTED = 3
MIN_TOKEN_LENGTH = 3
STOP_WORDS = frozenset(
    "the a an and or of to in on for with when then given is are be by as at from that this it its into via must shall "
    "should will not no any all each has have was were which who whose than other only also returns return".split()
)
TOKEN = re.compile(r"[a-z0-9][a-z0-9_./-]*")
_TRIM = "./-_"
LEGACY_FR_REFS = "legacy_fr_refs"
LEGACY_INVARIANT_REFS = "legacy_invariant_refs"
TASK_STATUS = "task_status"


@dataclass(frozen=True)
class Scored:
    """A candidate with its score."""

    node: Node
    score: float


@dataclass(frozen=True)
class Decision:
    """The class of one criterion, its target (``None`` for ``none``) and the other candidates worth naming."""

    klass: str
    target: Scored | None
    alternatives: tuple[Scored, ...]


def tokenize(text: str, ignore: Iterable[str] = ()) -> list[str]:
    """The tokens of *text* the score reads: lower case, trimmed of ``./-_``, three characters or more, no stop word and none of *ignore*."""
    skipped = set(ignore)
    tokens = (token.strip(_TRIM) for token in TOKEN.findall(text.lower()))
    return [token for token in tokens if len(token) >= MIN_TOKEN_LENGTH and token not in STOP_WORDS and token not in skipped]


def idf_table(documents: Iterable[Sequence[str]]) -> dict[str, float]:
    """The inverse document frequency of each token over *documents*: ``log((N + 1) / (df + 1)) + 1``."""
    frequency: Counter[str] = Counter()
    count = 0
    for tokens in documents:
        frequency.update(set(tokens))
        count += 1
    return {token: math.log((count + 1) / (seen + 1)) + 1 for token, seen in frequency.items()}


def vectorise(tokens: Sequence[str], idf: Mapping[str, float]) -> dict[str, float]:
    """The unit TF-IDF vector of *tokens* (a token no document had weighs ``1``); empty for no tokens."""
    weights = {token: count * idf.get(token, 1.0) for token, count in Counter(tokens).items()}
    norm = math.sqrt(sum(weight * weight for weight in weights.values()))
    return {token: weight / norm for token, weight in weights.items()} if norm else {}


def cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    """The dot product of two unit vectors."""
    return sum(weight * right.get(token, 0.0) for token, weight in left.items())


def decide(ranked: Sequence[Scored], rank_of: Callable[[Node], int], min_score: float = MIN_SCORE) -> Decision:
    """The class of a criterion whose candidates, best first, are *ranked*; *rank_of(node)* is the position of a node's step in the waterfall.

    The best candidate and every candidate within ``TIE_MARGIN`` of it state one rule; the target is the most downstream
    of them (the best, then the id, among equals).  The case is ``auto-eligible`` only when that group is the best
    candidate alone, it is an acceptance criterion and it scores ``min_score`` or more.
    """
    if not ranked or ranked[0].score <= 0:
        return Decision(CLASS_NONE, None, ())
    group = [candidate for candidate in ranked if ranked[0].score - candidate.score <= TIE_MARGIN]
    target = max(group, key=lambda candidate: (rank_of(candidate.node), candidate.score, candidate.node.id)) if len(group) > 1 else ranked[0]
    others = tuple(candidate for candidate in ranked if candidate is not target)[:ALTERNATIVES_LISTED]
    eligible = len(group) == 1 and target.node.kind == CRITERION and target.score >= min_score
    return Decision(CLASS_AUTO if eligible else CLASS_JUDGEMENT, target, others)


def candidate_kinds(graph: Graph) -> tuple[str, ...]:
    """The kinds ``refines`` accepts, from the declaration of the ``refines`` link of ``task-criterion`` (empty when the registry has none)."""
    decl = graph.decls.get(TASK_CRITERION)
    link = next((link for link in decl.links if link.field == REFINES), None) if decl else None
    return link.kinds if link else ()


def _with_descendants(graph: Graph, nodes: Iterable[Node]) -> dict[str, Node]:
    found: dict[str, Node] = {}
    pending = list(nodes)
    while pending:
        node = pending.pop()
        if node.id in found:
            continue
        found[node.id] = node
        pending.extend(child for child_id in graph.children.get(node.id, ()) if (child := graph.by_id.get(child_id)) is not None)
    return found


def reach(graph: Graph, roots: Iterable[Node]) -> dict[str, Node]:
    """The nodes reachable from *roots*: the roots and their descendants, and the nodes one declared link away in either direction with their descendants."""
    region = _with_descendants(graph, roots)
    neighbours: list[Node] = []
    for node_id in region:
        outgoing = (graph.find(link.target) for link in graph.outgoing.get(node_id, ()))
        incoming = (graph.by_id.get(link.source) for link in graph.incoming.get(node_id, ()))
        neighbours.extend(found for found in (*outgoing, *incoming) if found is not None)
    return _with_descendants(graph, [*region.values(), *neighbours])


def prose_of(tree: MigratedTree, node: Node) -> str:
    """The prose of *node*: the strings of its contract fields whose schema slot does not fix the value, joined by a space."""
    decl = tree.graph.decls.get(node.kind)
    contract = set(decl.contract) if decl else set()
    parts = []
    for path, text in own_leaves(tree.graph, node):
        steps = path_steps(path)
        if steps and steps[0] in contract and not is_fixed_leaf(tree.checks, node, path):
            parts.append(text)
    return " ".join(parts)


def _legacy_refs(tree: MigratedTree) -> dict[str, tuple[list[str], list[str]]]:
    """``{task id: (fr ids, invariant ids)}`` as the capture holds them, the task id and each ref mapped through the renames of phase 2 when no node has the old id any more."""
    renamed = {old: new for by_kind in tree.renames.values() for old, new in by_kind.items()}

    def current(name: str) -> str:
        return name if tree.graph.find(name) is not None else renamed.get(name, name)

    found: dict[str, tuple[list[str], list[str]]] = {}
    for row in tree.capture.get(TASK_STATUS) or []:
        if isinstance(row, dict) and isinstance(row.get("task"), str):
            found[current(row["task"])] = (
                [current(ref) for ref in row.get(LEGACY_FR_REFS) or [] if isinstance(ref, str)],
                [current(ref) for ref in row.get(LEGACY_INVARIANT_REFS) or [] if isinstance(ref, str)],
            )
    return found


def _task_of(graph: Graph, criterion: Node) -> Node | None:
    """The task that holds *criterion*, found through its parent (an id defined twice cannot be looked up by id)."""
    task = graph.by_id.get(criterion.parent) if criterion.parent else None
    return task if task is not None and task.kind == TASK else None


def _is_unrefined(node: Node) -> bool:
    return not any(link.field in (REFINES, REMOVES) for link in node.links)


def _place(node: Node) -> tuple[str, str]:
    """Where a node is defined: the one key of a node when an id is defined twice."""
    return node.file, node.jq_path


def _vectors(tree: MigratedTree, kinds: Sequence[str]) -> dict[tuple[str, str], dict[str, float]]:
    """The unit TF-IDF vector of every node that can be a candidate and of every task criterion, by ``_place`` (IDF over all of them)."""
    graph = tree.graph
    ignore = frozenset((*graph.by_id, *graph.alias_index))
    tokens = {_place(node): tokenize(prose_of(tree, node), ignore) for node in graph.nodes if node.kind in kinds or node.kind == TASK_CRITERION}
    idf = idf_table(tokens.values())
    return {place: vectorise(found, idf) for place, found in tokens.items()}


def _describe(scored: Scored) -> str:
    return f"{scored.node.id} ({scored.node.kind}, {scored.score:.2f})"


def _proposal_text(decision: Decision, criterion: Node) -> str:
    klass, target = decision.klass, decision.target
    if target is None:
        return (
            f"class: {klass}. No obligation to propose: find the one this criterion narrows. If it narrows none: for a "
            f"criterion of a closed milestone, `specdev node status {criterion.id} not_applicable` (the value is refused "
            f"on any other node); for one of an open milestone, delete it (`specdev json delete --id {criterion.id}`) "
            "or reword it at step 14"
        )
    others = f"; other candidates: {', '.join(_describe(other) for other in decision.alternatives)}" if decision.alternatives else ""
    return (
        f"class: {klass}. refines {target.node.id} ({target.node.kind}, score {target.score:.2f}){others}. "
        f"To confirm: specdev json patch --id {criterion.id} .refines '[\"{target.node.id}\"]'"
    )


def _case(graph: Graph, criterion: Node, names: Sequence[str], unnamed: Sequence[str], decision: Decision, count: int) -> Proposal:
    task = _task_of(graph, criterion)
    where = f"task {task.id}" if task else "no task"
    named = f"names {', '.join(names)}" if names else "names no FR and no invariant"
    missing = f"; no node has {', '.join(unnamed)}" if unnamed else ""
    evidence = f"{where} {named}{missing}; {count} candidate(s) of the kinds refines accepts"
    key = criterion.jq_path if criterion.id in graph.dups else ""
    item = make_item(STEP, KIND_REFINES, criterion.id, audience=AUDIENCE_AGENT, blocking=True, evidence=evidence, proposal=_proposal_text(decision, criterion), key=key)
    target = decision.target
    data = {
        "about": criterion.id,
        "task": task.id if task else None,
        "target": target.node.id if target else None,
        "target_kind": target.node.kind if target else None,
        "score": round(target.score, 4) if target else None,
        "alternatives": [{"id": other.node.id, "kind": other.node.kind, "score": round(other.score, 4)} for other in decision.alternatives],
    }
    arrow = f"-> {target.node.id} ({target.node.kind}, {target.score:.2f})" if target else "(no candidate)"
    return Proposal(item, decision.klass, data, f"{decision.klass:<15} {criterion.id} {arrow}")


def propose(tree: MigratedTree) -> ProposeResult:
    """One proposal per task criterion of the tree that has neither ``refines`` nor ``removes``, in step then id order, with the counts by class."""
    graph = tree.graph
    kinds = candidate_kinds(graph)
    vectors = _vectors(tree, kinds)
    legacy = _legacy_refs(tree)
    proposals: list[Proposal] = []
    for criterion in sorted(graph.by_kind.get(TASK_CRITERION, []), key=graph.shape.order_key):
        if not _is_unrefined(criterion):
            continue
        task = _task_of(graph, criterion)
        frs, invariants = legacy.get(task.id, ([], [])) if task else ([], [])
        names = [*frs, *invariants]
        roots = [found for name in names if (found := graph.find(name)) is not None]
        candidates = [node for node in reach(graph, roots).values() if node.kind in kinds and node.id not in graph.dups]
        ranked = sorted((Scored(node, cosine(vectors[_place(criterion)], vectors[_place(node)])) for node in candidates), key=lambda scored: (-scored.score, scored.node.id))
        decision = decide(ranked, lambda node: graph.shape.rank_of(node.step)) if roots else Decision(CLASS_NONE, None, ())
        unnamed = [name for name in names if graph.find(name) is None]
        proposals.append(_case(graph, criterion, names, unnamed, decision, len(candidates)))
    counts = Counter(proposal.category for proposal in proposals)
    return ProposeResult(KIND_REFINES, tuple(proposals), {"task criteria": len(proposals), **{klass: counts.get(klass, 0) for klass in CLASSES}})
