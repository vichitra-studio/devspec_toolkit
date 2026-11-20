"""E741 (WI-M6b-03): a glossary term that no user mentions by its current label.

Terms store no links, so a term is used when its label appears in the text of a user: a string leaf of a node of steps
04 to 15 that is not a record (the set ``trace.label_rename`` rewrites, read through ``label_users`` and ``own_leaves``
so that the rename and this check share one definition of a use).  The matcher is looser than the rename's: both sides
are normalised (NFKC, case-fold, ``-``, ``_`` and ``/`` read as a space, runs of space collapsed) and the label must
stand on token boundaries, with ``s`` or ``es`` allowed after its last word.  Only the current label matches; there are
no label aliases.  A term is checked unless its lifecycle is ``not_applicable``; ``scope`` does not apply to it.
"""
from __future__ import annotations

import re
import unicodedata
from specdev_tools.core.errors import SpecError
from specdev_tools.graph.contract import item_of
from specdev_tools.graph.model import Graph
from specdev_tools.trace.label_rename import LABEL_KEY, TERM_KIND, label_users, own_leaves

from .codes import TERM_NOT_USED_BY_LABEL
from .context import GraphCheckContext, Mode

_SEPARATORS = re.compile(r"[-_/\s]+")


def normalise(text: str) -> str:
    """*text* as the matcher compares it: NFKC, case-folded, ``-``, ``_`` and ``/`` read as a space, whitespace collapsed and trimmed."""
    return _SEPARATORS.sub(" ", unicodedata.normalize("NFKC", text).casefold()).strip()


def label_pattern(label: str) -> re.Pattern[str] | None:
    """The pattern that finds *label* in a normalised text: whole tokens, an ``s`` or ``es`` allowed after the last word; ``None`` when the label normalises to nothing."""
    words = normalise(label)
    if not words:
        return None
    return re.compile(rf"(?<!\w){re.escape(words)}(?:es|s)?(?!\w)")


def label_matches(label: str, text: str) -> bool:
    """Whether *text* uses *label*: both normalised, the label on token boundaries (``Tag`` is not in ``Tagline``)."""
    pattern = label_pattern(label)
    return pattern is not None and pattern.search(normalise(text)) is not None


def _user_texts(graph: Graph) -> list[str]:
    """The normalised string leaves of every user of the graph, read once for all terms."""
    return [normalise(text) for node in sorted(label_users(graph), key=graph.shape.order_key) for _path, text in own_leaves(graph, node)]


def check_term_use(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """E741 for each term (not ``not_applicable``) whose current label no user holds; in step then id order."""
    graph = ctx.graph
    terms = sorted((node for node in graph.gated_nodes() if node.kind == TERM_KIND), key=graph.shape.order_key)
    texts = _user_texts(graph) if terms else []
    findings: list[SpecError] = []
    for term in terms:
        label = (item_of(graph, term) or {}).get(LABEL_KEY)
        pattern = label_pattern(label) if isinstance(label, str) else None
        if pattern is None or any(pattern.search(text) for text in texts):
            continue
        findings.append(ctx.finding(
            TERM_NOT_USED_BY_LABEL, term,
            f"term {term.id!r} ({label!r}) is not used: no node of steps 04 to 15 mentions its label; use it in the text of a "
            f"requirement, contract, invariant, task or other non-record node, or mark the term not_applicable",
        ))
    return findings
