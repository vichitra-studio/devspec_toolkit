"""``specdev align propose --kind prose-ids``: every node id a node's prose names, and what to do with each (DEVSPEC-158).

The id-in-prose check (``validation/graph_checks/prose_ids``, E752) reports each mention of a live id, a retired name or a
seed id in the prose of a node.  Before the step-14 pass the load is large and no one rule clears it, so this proposer
lists it: ONE worklist item per node (not per token) with each id-shaped token of the node's prose, whether it
resolves, and a proposal.  It uses the check's own scanner (``id_tokens``, ``mentions``, ``is_fixed_leaf`` and the leaf
walker ``own_leaves``), so the number of RESOLVED mentions equals the number of E752 findings of the same tree.

A resolved mention is proposed as the link it states when exactly one declared link field of the holder's kind accepts
the target's kind (the ``removes`` and ``replaces`` history links do not count: they accept any kind), as a reword when
the holder already has that link or no field fits, and as a decision when several fit.  A token that looks like an id
(it starts with the id prefix of a kind, ``fr-``, ``ac-``, ...) and resolves to nothing is a review item, never a finding:
it is listed with a class: ``retired`` (the migration renamed it), ``relative`` (``ac-2``: a number after a prefix),
``placeholder`` (``fr-xxx``), ``near-miss`` (one edit from a live id) or ``never-defined``.

A token that the collision script already put in a ``collided-id-citation`` item of the same node is listed here and left
to that item: the item decides WHICH of the colliding nodes the text meant; this one decides link or reword after it.

Not built: canon ids (``cn:...``): the scanner splits a token at ``:``, and no second scanner for them is added.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

from specdev_tools.graph.ids import suggest_prefix
from specdev_tools.graph.model import Node
from specdev_tools.graph.resolve import HISTORY_FIELDS
from specdev_tools.migration.proposers import KIND_PROSE_IDS, MigratedTree, Proposal, ProposeResult
from specdev_tools.migration.worklist import AUDIENCE_AGENT, make_item, read_items
from specdev_tools.trace.label_rename import own_leaves
from specdev_tools.validation.graph_checks.prose_ids import TOKEN, id_tokens, is_fixed_leaf, mentions

CITATION_KIND = "collided-id-citation"
"""The worklist kind ``p2_id_collisions`` gives a prose citation of an id that two nodes defined."""
STEP_PATTERN = re.compile(r"[0-9]{2}[a-z]?")
STEP_FALLBACK = "00"
"""The step of an item whose holder is no step node (a seed document: phase 0)."""
NEAR_MISS_CUTOFF = 0.85
NEAR_MISS_LISTED = 3
PLACEHOLDER_WORDS = frozenset({"x", "xx", "xxx", "n", "nn", "nnn", "foo", "bar", "baz", "example", "slug", "name", "id", "todo", "tbd", "placeholder"})
RELATIVE = re.compile(r"^[a-z]+-[0-9]+$")

RESOLVED = "resolved"
RETIRED = "retired"
RELATIVE_NOTATION = "relative"
PLACEHOLDER = "placeholder"
NEAR_MISS = "near-miss"
NEVER_DEFINED = "never-defined"
UNRESOLVED_CLASSES = (RETIRED, RELATIVE_NOTATION, PLACEHOLDER, NEAR_MISS, NEVER_DEFINED)
BLOCKING = "blocking"
REVIEW = "review"


@dataclass(frozen=True)
class Mention:
    """One id-shaped token of one leaf: where it is, what it is (``RESOLVED`` or an unresolved class), the node it names (resolved only) and the proposal."""

    field: str
    token: str
    klass: str
    target: str | None
    proposal: str

    def line(self) -> str:
        """The evidence line: the field, the token and what it is."""
        what = f"resolved: {self.target}" if self.klass == RESOLVED else f"unresolved: {self.klass}"
        return f"{self.field}: {self.token} ({what})"


@dataclass(frozen=True)
class Scan:
    """What a scan of the prose needs besides the tree: the names a mention may match, the id prefixes, the ids the migration renamed and the collision script's citation items."""

    names: Mapping[str, str]
    prefixes: frozenset[str]
    renamed: Mapping[str, str]
    citations: Mapping[str, list[tuple[str, str]]]


def build_scan(tree: MigratedTree) -> Scan:
    """The ``Scan`` of *tree*: ``id_tokens`` of its graph, the id prefix of each registry kind (``graph.ids.suggest_prefix``), the renames of phase 2 and the ``collided-id-citation`` items of its worklist."""
    prefixes = frozenset(prefix for kind in tree.graph.decls if (prefix := suggest_prefix(kind)))
    renamed = {old: new for by_kind in tree.renames.values() for old, new in by_kind.items()}
    citations: dict[str, list[tuple[str, str]]] = {}
    for item in read_items(tree.ctx):
        if item.kind == CITATION_KIND:
            citations.setdefault(item.about, []).append((item.id, item.evidence))
    return Scan(id_tokens(tree.graph), prefixes, renamed, citations)


def _looks_like_an_id(token: str, prefixes: frozenset[str]) -> bool:
    return token.lower().startswith(tuple(prefixes))


def _live_ids(tree: MigratedTree, token: str) -> list[str]:
    prefix = token.split("-", 1)[0] + "-"
    return [name for name in tree.graph.by_id if name.startswith(prefix)]


def classify_unresolved(tree: MigratedTree, token: str, renamed: Mapping[str, str]) -> tuple[str, str]:
    """The class of an id-shaped token that resolves to nothing, with the proposal for it."""
    if token in renamed:
        return RETIRED, f"the migration renamed it to {renamed[token]}: write that id, then treat it as a resolved mention"
    if RELATIVE.match(token):
        return RELATIVE_NOTATION, "a number after a prefix names no node: name the criterion in full, or reword out"
    last = token.lower().rstrip("-").rsplit("-", 1)[-1]
    if token.endswith("-") or last in PLACEHOLDER_WORDS:
        return PLACEHOLDER, "a placeholder, not an id: reword out"
    close = difflib.get_close_matches(token, _live_ids(tree, token), n=NEAR_MISS_LISTED, cutoff=NEAR_MISS_CUTOFF)
    if close:
        return NEAR_MISS, f"one edit from {', '.join(close)}: fix the spelling, then link it or reword out"
    return NEVER_DEFINED, "no node has this id: reword out, or the node it names is missing (an author's decision)"


def _fitting_fields(tree: MigratedTree, holder: Node, target: Node) -> list[str]:
    decl = tree.graph.decls.get(holder.kind)
    return [link.field for link in decl.links if link.field not in HISTORY_FIELDS and link.accepts(target.kind)] if decl else []


def resolved_proposal(tree: MigratedTree, holder: Node, target: Node, citation: str | None) -> str:
    """The proposal for a mention of the node *target* in the prose of *holder*; *citation* is the id of the ``collided-id-citation`` item that covers it, if any."""
    if citation:
        return f"decide worklist item {citation} first (which colliding node the text means); then link it or reword out"
    linked = sorted({link.field for link in holder.links if tree.graph.canonical_id(link.target) == target.id})
    if linked:
        return f"{holder.id} already links {target.id} through {', '.join(linked)}: reword out"
    fields = _fitting_fields(tree, holder, target)
    if len(fields) == 1:
        return f"states a relation if it reads as one: the declared field {fields[0]} of {holder.kind} accepts the kind {target.kind}; link it there, or reword out"
    if fields:
        return f"several fields of {holder.kind} accept the kind {target.kind} ({', '.join(fields)}): decide which relation it states, or reword out"
    return f"no declared field of {holder.kind} accepts the kind {target.kind}: reword out"


def _covering(scan: Scan, holder: Node, token: str) -> str | None:
    return next((item_id for item_id, evidence in scan.citations.get(holder.id, []) if f"`{token}`" in evidence), None)


def _leaf_mentions(tree: MigratedTree, scan: Scan, holder: Node, path: str, text: str) -> list[Mention]:
    found = [
        Mention(path, name, RESOLVED, scan.names[name], resolved_proposal(tree, holder, tree.graph.by_id[scan.names[name]], _covering(scan, holder, name)))
        for name in mentions(text, dict(scan.names))
        if scan.names[name] != holder.id
    ]
    seen = {mention.token for mention in found}
    for match in TOKEN.finditer(text):
        token = match.group()
        if token in seen or token in scan.names or tree.graph.find(token) is not None or not _looks_like_an_id(token, scan.prefixes):
            continue
        seen.add(token)
        klass, proposal = classify_unresolved(tree, token, scan.renamed)
        found.append(Mention(path, token, klass, None, proposal))
    return found


def node_mentions(tree: MigratedTree, scan: Scan, holder: Node) -> list[Mention]:
    """Every id-shaped token in the prose of *holder* (the leaves ``own_leaves`` gives, without those whose schema slot fixes the value), in leaf order."""
    found: list[Mention] = []
    for path, text in own_leaves(tree.graph, holder):
        leaf = _leaf_mentions(tree, scan, holder, path, text)
        if leaf and not is_fixed_leaf(tree.checks, holder, path):
            found.extend(leaf)
    return found


def _step_of(node: Node) -> str:
    return node.step if node.step and STEP_PATTERN.fullmatch(node.step) else STEP_FALLBACK


def _proposal(tree: MigratedTree, holder: Node, found: list[Mention]) -> Proposal:
    resolved = sum(1 for mention in found if mention.klass == RESOLVED)
    unresolved = len(found) - resolved
    key = f"{holder.file} {holder.jq_path}" if holder.id in tree.graph.dups else ""
    evidence = "\n".join(mention.line() for mention in found)
    text = "\n".join(f"{mention.token}: {mention.proposal}" for mention in found)
    item = make_item(_step_of(holder), KIND_PROSE_IDS, holder.id, audience=AUDIENCE_AGENT, blocking=resolved > 0, evidence=evidence, proposal=text, key=key)
    data = {
        "about": holder.id,
        "file": holder.file,
        "resolved": resolved,
        "unresolved": unresolved,
        "mentions": [{"field": m.field, "token": m.token, "class": m.klass, "target": m.target, "proposal": m.proposal} for m in found],
    }
    category = BLOCKING if resolved else REVIEW
    return Proposal(item, category, data, f"{category:<8} {holder.id} ({_step_of(holder)}): {resolved} resolved, {unresolved} unresolved")


def propose(tree: MigratedTree) -> ProposeResult:
    """One proposal per node that has an id-shaped token in its prose, in step then id order, with the counts of nodes, resolved mentions and each unresolved class."""
    graph = tree.graph
    scan = build_scan(tree)
    proposals: list[Proposal] = []
    classes: Counter[str] = Counter()
    for holder in sorted(graph.gated_nodes(), key=graph.shape.order_key):
        found = node_mentions(tree, scan, holder)
        if found:
            proposals.append(_proposal(tree, holder, found))
            classes.update(mention.klass for mention in found)
    counts = {"nodes": len(proposals), RESOLVED: classes[RESOLVED], **{klass: classes[klass] for klass in UNRESOLVED_CLASSES}}
    return ProposeResult(KIND_PROSE_IDS, tuple(proposals), counts)
