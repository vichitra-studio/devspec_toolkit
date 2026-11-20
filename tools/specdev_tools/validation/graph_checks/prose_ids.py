"""E752: a node id written in the prose of a node.

A prose mention is not a link: the resolver never sees it, so the lock, the suspect check and the use rules miss the
relation it states.  The check reads every string leaf of every node in play (records included) except the id and link
fields (the walker ``trace.label_rename.own_leaves`` skips those) and the leaves whose schema slot carries ``enum``,
``const``, ``pattern`` or ``format`` (contract values: paths, codes, field names).  A token of ``[A-Za-z0-9_-]``, case
sensitive, that equals the id of a live node, a retired name (alias) of a renamed node or a seed id is a finding.

Not built, by ruling: a token that looks like an id but names nothing is a review item, not a finding; third-party
versions in prose (E753) have no detection rule.  Name-like ids (single words such as ``dev`` or ``ci``) are left out of
the token set: they are ordinary words.
"""
from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any

from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.core.schema_nav import effective_schema
from specdev_tools.graph.contract import PATH_STEP
from specdev_tools.graph.model import Graph, Node
from specdev_tools.trace.label_rename import own_leaves
from specdev_tools.validation import check_registry
from specdev_tools.validation.check_registry import CheckContext
from specdev_tools.validation.hallucination_lint import _SchemaResolverCtx

from .codes import NODE_ID_IN_PROSE
from .context import GRAPH_NOT_BUILT, GraphCheckContext, Mode

TOKEN = re.compile(r"[A-Za-z0-9_-]+")
INDEX = re.compile(r"\[\d+\]")
FIXED_VALUE_KEYWORDS = ("enum", "const", "pattern", "format")
"""Schema keywords that make a string a contract value, not prose."""


def id_tokens(graph: Graph) -> dict[str, str]:
    """The names a prose mention may match, each with the id of the node it names: live node ids, retired aliases and seed ids, without the name-like ones (no ``-``)."""
    names = {node.id: node.id for node in graph.gated_nodes()}
    names.update({alias: graph.canonical_id(alias) for alias in graph.alias_index if alias not in names})
    return {name: current for name, current in names.items() if "-" in name}


def _steps(path: str) -> list[str | int]:
    """The object keys and array indexes of a jq path, in order."""
    steps: list[str | int] = []
    for name, index, quoted in PATH_STEP.findall(path):
        steps.append(name or (int(index) if index else json.loads(quoted)))
    return steps


def _child_schema(schema: dict[str, Any], resolve: Any, step: str | int) -> dict[str, Any] | None:
    """The schema of the member *step* of a value described by *schema*: ``items`` for an index, else the property, the first matching pattern property, or a schema ``additionalProperties``."""
    effective = effective_schema(schema, resolve, include_conditionals=True)
    if isinstance(step, int):
        found = effective.get("items")
    else:
        found = effective.get("properties", {}).get(step)
        if found is None:
            found = next((sub for pattern, sub in effective.get("patternProperties", {}).items() if re.search(pattern, step)), None)
        if found is None:
            found = effective.get("additionalProperties")
    return found if isinstance(found, dict) else None


class _SlotReader:
    """Whether the schema of a file says a leaf is a fixed value; the schema of each file is loaded once."""

    def __init__(self, repo_root: str) -> None:
        self._resolver = _SchemaResolverCtx(repo_root)
        self._files: dict[str, tuple[Any, Any]] = {}

    def is_fixed(self, graph: Graph, node: Node, leaf_path: str) -> bool:
        """Whether the schema slot of the leaf at *leaf_path* of *node* carries ``enum``, ``const``, ``pattern`` or ``format``; ``False`` when the slot cannot be resolved."""
        if node.file not in self._files:
            document = graph.documents.get(node.file)
            self._files[node.file] = self._resolver.load_file_schema(document) if isinstance(document, dict) else (None, None)
        schema, resolve = self._files[node.file]
        if schema is None:
            return False
        for step in _steps(node.jq_path + leaf_path):
            schema = _child_schema(schema, resolve, step)
            if schema is None:
                return False
        slot = effective_schema(schema, resolve, include_conditionals=True)
        return any(keyword in slot for keyword in FIXED_VALUE_KEYWORDS)


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
    return replace(ctx.finding(NODE_ID_IN_PROSE, node, message, target=link_target(field, current)), jq_path=node.jq_path + leaf_path)


def check_prose_ids(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """E752 for each id a string leaf of a node in play mentions, one per leaf and id, in step then id order of the node.

    A finding carries the node that holds the leaf (a child of a nested array is its own node), the leaf's path and
    ``<leaf field>-><id>`` as target.
    """
    tokens = id_tokens(ctx.graph)
    slots = _SlotReader(ctx.repo_root)
    findings: list[SpecError] = []
    for node in ctx.in_play_nodes():
        for leaf_path, text in own_leaves(ctx.graph, node):
            names = _mentions(text, tokens)
            if names and not slots.is_fixed(ctx.graph, node, leaf_path):
                findings.extend(_finding(ctx, node, leaf_path, name, tokens[name]) for name in names)
    return findings


def run_prose_ids(ctx: CheckContext) -> dict[str, Any]:
    """The registered function: E752 findings of ``check_prose_ids`` at merge, or a skip when no graph could be built."""
    gctx = GraphCheckContext.from_registry(ctx)
    if gctx is None:
        return check_registry.skip(GRAPH_NOT_BUILT)
    return check_registry.check_result(check_prose_ids(gctx, "merge"))
