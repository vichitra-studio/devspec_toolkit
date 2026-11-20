"""E752: a node id written in the prose of a node.

A prose mention is not a link: the resolver never sees it, so the lock, the suspect check and the use rules miss the
relation it states.  The check reads every string leaf of every node that is not ``not_applicable`` (records included;
a node parked with ``scope: later`` or ``out`` comes back into play with its prose) except the id and link fields (the
walker ``trace.label_rename.own_leaves`` skips those) and the leaves whose schema slot is a fixed value (contract
values: paths, codes, field names): it carries ``enum``, ``const`` or ``format``, or a ``pattern`` that no ordinary
sentence satisfies (a pattern that some sentence satisfies, such as one that only asks for a non-space character or for lower-case words, fixes nothing).
A token of ``[A-Za-z0-9_-]``, case
sensitive, that equals the id of a live node, a retired name (alias) of a renamed node or a seed id is a finding.

Not built, by ruling: a token that looks like an id but names nothing is a review item, not a finding; third-party
versions in prose (E753) have no detection rule.  Name-like ids (single words such as ``dev`` or ``ci``) are left out of
the token set: they are ordinary words.
"""
from __future__ import annotations

import re
from typing import Any

from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.graph.model import Graph, Node
from specdev_tools.trace.label_rename import own_leaves

from .codes import NODE_ID_IN_PROSE
from .context import GraphCheckContext, Mode

TOKEN = re.compile(r"[A-Za-z0-9_-]+")
INDEX = re.compile(r"\[\d+\]")
FIXED_VALUE_KEYWORDS = ("enum", "const", "format")
"""Schema keywords that make a string a contract value, not prose."""
SENTENCES = ("two plain words", "An ordinary sentence of several plain words, with a comma, and a full stop.")
"""Texts of prose (a lower-case pair of words; a capitalised sentence with punctuation): a ``pattern`` that any of them satisfies does not fix the value of its slot."""


def id_tokens(graph: Graph) -> dict[str, str]:
    """The names a prose mention may match, each with the id of the node it names: live node ids, retired aliases and seed ids, without the name-like ones (no ``-``)."""
    names = {node.id: node.id for node in graph.gated_nodes()}
    names.update({alias: graph.canonical_id(alias) for alias in graph.alias_index if alias not in names})
    return {name: current for name, current in names.items() if "-" in name}


def _is_fixed(slot: dict[str, Any]) -> bool:
    """Whether the schema slot *slot* fixes the value of its leaf: ``enum``, ``const`` or ``format``, or a ``pattern`` that none of the ``SENTENCES`` satisfies (a pattern that is not a regular expression fixes it)."""
    if any(keyword in slot for keyword in FIXED_VALUE_KEYWORDS):
        return True
    pattern = slot.get("pattern")
    if not isinstance(pattern, str):
        return False
    try:
        return not any(re.search(pattern, sentence) for sentence in SENTENCES)
    except re.error:
        return True


def _all_fixed(alternatives: list[dict[str, Any]]) -> bool:
    """Whether every one of *alternatives* (the branches a slot may take) fixes its value: a slot that is a union fixes it only when each branch does, so one free-string branch makes it prose.  No alternative is not fixed."""
    return bool(alternatives) and all(_is_fixed(alternative) for alternative in alternatives)


def _is_fixed_leaf(ctx: GraphCheckContext, node: Node, leaf_path: str) -> bool:
    """Whether the schema slot of the leaf at *leaf_path* of *node* fixes its value (``_is_fixed`` on every branch of an ``anyOf`` or ``oneOf``, ``$ref`` resolved); ``False`` when the slot cannot be resolved (a leaf with no schema slot, such as the free-form ``input`` of a fixture, is read as prose)."""
    return _all_fixed(ctx.slots.alternatives(ctx.graph, node, leaf_path))


def _mentions(text: str, tokens: dict[str, str]) -> list[str]:
    """The distinct names of *tokens* that *text* holds as whole tokens, in order of first appearance."""
    found: list[str] = []
    for match in TOKEN.finditer(text):
        if match.group() in tokens and match.group() not in found:
            found.append(match.group())
    return found


def _finding(ctx: GraphCheckContext, node: Node, leaf_path: str, name: str, current: str) -> SpecError:
    field = INDEX.sub("", leaf_path).lstrip(".")
    retired = f" (a retired name of {current})" if name != current else ""
    message = (
        f"{node.kind} {node.id} mentions the id {name}{retired} in its text at {field}: a prose mention is not a link "
        f"and the resolver never sees it; turn a mention that states a relation into the link, or reword it"
    )
    return ctx.finding(NODE_ID_IN_PROSE, node, message, target=link_target(field, current), jq_path=node.jq_path + leaf_path)


def check_prose_ids(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """E752 for each id a string leaf of a node that is not ``not_applicable`` mentions, one per leaf and id, in step then id order of the node.

    A node's own id (or a retired name of it) is not reported: a link to itself cannot be written.  A finding carries the node that holds the leaf (a child of a nested array is its own node), the leaf's path and
    ``<leaf field>-><id>`` as target.
    """
    tokens = id_tokens(ctx.graph)
    findings: list[SpecError] = []
    for node in sorted(ctx.graph.gated_nodes(), key=ctx.graph.shape.order_key):
        for leaf_path, text in own_leaves(ctx.graph, node):
            names = [name for name in _mentions(text, tokens) if tokens[name] != node.id]
            if names and not _is_fixed_leaf(ctx, node, leaf_path):
                findings.extend(_finding(ctx, node, leaf_path, name, tokens[name]) for name in names)
    return findings
