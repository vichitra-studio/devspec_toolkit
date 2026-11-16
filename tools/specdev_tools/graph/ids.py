"""Id rules of the spec graph: uniqueness (E704), slug minting and the suggested id prefix of each kind.

An id is unique among every node of every file whatever its lifecycle (a deleted node is in no file, so its id is free
again).  Minting a slug is a pure function of the text and the ids already taken; it never changes an id that exists.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection, Iterable

from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.ownership import step_owner

DEFAULT_SLUG_MAX_LEN = 48
_NON_SLUG = re.compile(r"[^a-z0-9]+")

# Suggested id prefix per kind (PD-18).  A suggestion only: nothing enforces it.  A kind that is absent has no
# prefix: a gate keeps its kebab name, a plan item is upper-case, a component or a term is named by its author.
_PREFIXES: dict[str, str] = {
    "scope-item": "scope-",
    "assumption": "asm-",
    "need": "need-",
    "stakeholder": "sh-",
    "segment": "seg-",
    "metric": "metric-",
    "risk": "risk-",
    "capability": "cap-",
    "third-party": "tp-",
    "connection": "conn-",
    "constraint": "con-",
    "fr": "fr-",
    "criterion": "ac-",
    "api": "api-",
    "api-error": "err-",
    "invariant": "inv-",
    "nfr": "nfr-",
    "fixture": "fix-",
    "design-milestone": "ms-",
    "roadmap-milestone": "ms-",
    "task": "task-",
    "task-criterion": "tc-",
    "threat": "threat-",
    "edge-case": "ec-",
    "job": "job-",
    "scaffold-row": "scaffold-",
    "anchor-row": "anchor-",
    "rule": "rule-",
    "secret": "secret-",
}


def suggest_prefix(kind: str) -> str | None:
    """The id prefix suggested for a new node of *kind* (``"fr-"`` for ``fr``), or ``None`` when the kind has none."""
    return _PREFIXES.get(kind)


def first_free_id(base: str, taken: Collection[str]) -> str:
    """*base* when it is free, else the first of ``base-2``, ``base-3``, ... that is not in *taken*."""
    if base not in taken:
        return base
    number = 2
    while f"{base}-{number}" in taken:
        number += 1
    return f"{base}-{number}"


def _ascii_slug(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return _NON_SLUG.sub("-", folded).strip("-")


def _cut_on_word(slug: str, max_len: int) -> str:
    """*slug* cut to at most *max_len* characters at the last ``-`` before the limit (a hard cut when it has none)."""
    if len(slug) <= max_len:
        return slug
    boundary = slug.rfind("-", 0, max_len + 1)
    return slug[:boundary] if boundary > 0 else slug[:max_len].rstrip("-")


def mint_slug(text: str, taken: Collection[str], *, prefix: str | None = None, max_len: int = DEFAULT_SLUG_MAX_LEN) -> str:
    """A new id made from *text*: lowercase ASCII words joined by ``-``, cut at *max_len*, after *prefix*, and free.

    The slug is cut on a word boundary at *max_len* characters (the prefix is not counted).  When the result is in
    *taken*, the first free ``-2``, ``-3``, ... suffix is added.  The same text and taken set always give the same id.
    Callers mint only for an item that has no id; an id that exists is never re-derived.

    Raises:
        ValueError: *text* holds no ASCII letter or digit, so no slug can be made.
    """
    slug = _cut_on_word(_ascii_slug(text), max_len)
    if not slug:
        raise ValueError("text has no ASCII letters or digits to make an id from")
    return first_free_id((prefix or "") + slug, taken)


def _definition(node: Node) -> str:
    return f"{node.file} {node.jq_path or '.'}"


def _duplicate_error(first: Node, extra: Node, hint: str) -> SpecError:
    message = (
        f"Duplicate node id '{extra.id}': defined at {_definition(first)} ({first.kind}) and again at "
        f"{_definition(extra)} ({extra.kind}); rename the later one, for example to '{hint}'"
    )
    return make_error(
        "E704", message, file=extra.file, jq_path=extra.jq_path or None, owner=step_owner(extra), node_id=extra.id
    )


def check_unique_ids(graph: Graph, *, steps: Iterable[str] | None = None) -> list[SpecError]:
    """E704 for every extra definition of an id, across files, steps and nesting.

    The first definition (in step order, then path) is the established one; each later definition is reported once,
    owned by its own step, with the first free numeric-suffixed id as a hint.  Lifecycle never exempts a node.  With
    *steps*, only extra definitions that sit in one of those steps are reported.
    """
    wanted = None if steps is None else set(steps)
    taken = set(graph.by_id)
    errors: list[SpecError] = []
    for node_id, found in graph.dups.items():
        first = found[0]
        for extra in found[1:]:
            hint = first_free_id(node_id, taken)
            taken.add(hint)
            if wanted is None or extra.step in wanted:
                errors.append(_duplicate_error(first, extra, hint))
    return errors
