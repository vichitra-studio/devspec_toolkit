"""The worklist: one item per decision a migration script could not make, kept in ``spec/extras/migration/worklist.json``.

A script that meets a case it must not guess (two readings of a host's text, a reference whose field does not fix its
kind, a status conflict) leaves the content as it is and adds an item here.  A person (or the step pass of an agent)
works through the list; an item they have settled is closed by editing its own ``resolved`` and ``note`` fields.

Items are stable across a rerun: the id is built from ``(step, kind, about, key)``, so a script that finds the same case
again computes the same id, ``add_items`` skips an id that is already listed (closed or not) and a closed item is never
reopened.  The file is written through the runner's ``DocumentSet`` and kept in one order (step, kind, id), so two runs
that add the same items write the same bytes whatever the order they added them in.

The API for a script: ``make_item`` builds an item, ``missing_items`` is the list ``detect`` counts (the items not yet
listed), ``add_items`` is what ``apply`` calls, ``read_items`` lists what is there.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from specdev_tools.migration.context import CAPTURE_FILE, MigrationContext
from specdev_tools.migration.writer import StyledDocument

WORKLIST_FILE = os.path.join(os.path.dirname(CAPTURE_FILE), "worklist.json")
WORKLIST_SCHEMA = "vc:infra:migration-worklist"
AUDIENCE_AGENT = "agent"
AUDIENCE_OPERATOR = "operator"
AUDIENCES = (AUDIENCE_AGENT, AUDIENCE_OPERATOR)

_ITEMS = "items"
_SLUG_LIMIT = 60
_NON_SLUG = re.compile(r"[^a-z0-9]+")


class WorklistError(Exception):
    """The worklist file is not a worklist, an item is malformed, or two different cases map to one id."""


@dataclass(frozen=True)
class WorklistItem:
    """One decision for a person.

    ``id`` is ``wl-<step>-<kind>-<slug of about and key>``; ``step`` the step the decision belongs to (``"04"``,
    ``"02a"``, ``"16"``); ``kind`` a kebab-case name of the sort of decision; ``audience`` ``agent`` (an agent in the
    step pass proposes, a person confirms) or ``operator`` (a person decides); ``blocking`` is a display hint (sort
    order and wording on the triage list), nothing gates on it; ``about`` the node id or file path the case is about;
    ``evidence`` what the script saw; ``proposal`` what it would do (``""`` when it has none); ``resolved`` and ``note``
    record a closed item.
    """

    id: str
    step: str
    kind: str
    audience: str
    blocking: bool
    about: str
    evidence: str
    proposal: str
    resolved: bool = False
    note: str = ""

    def to_json(self) -> dict[str, Any]:
        """The item as it stands in the file (field order as declared)."""
        return asdict(self)


def _slug(text: str) -> str:
    slug = _NON_SLUG.sub("-", text.lower()).strip("-")
    if len(slug) <= _SLUG_LIMIT:
        return slug
    return f"{slug[: _SLUG_LIMIT - 8].rstrip('-')}-{hashlib.sha1(text.encode('utf-8')).hexdigest()[:7]}"


def item_id(step: str, kind: str, about: str, key: str = "") -> str:
    """The id of the item for this case; the same four values always give the same id.

    *key* tells apart several items of one ``(step, kind, about)`` (one per criterion, say); it is part of the id only.
    """
    return "-".join(part for part in ("wl", step, kind, _slug(about), _slug(key)) if part)


def make_item(
    step: str,
    kind: str,
    about: str,
    *,
    audience: str,
    blocking: bool,
    evidence: str = "",
    proposal: str = "",
    key: str = "",
) -> WorklistItem:
    """An open item for the case ``(step, kind, about, key)``.

    Raises:
        WorklistError: *audience* is neither ``agent`` nor ``operator``, or *step*, *kind* or *about* is empty.
    """
    if audience not in AUDIENCES:
        raise WorklistError(f"audience {audience!r} is not one of {', '.join(AUDIENCES)}")
    if not (step and kind and about):
        raise WorklistError("an item needs a step, a kind and an about")
    return WorklistItem(item_id(step, kind, about, key), step, kind, audience, blocking, about, evidence, proposal)


def _item_from(raw: Any) -> WorklistItem:
    if not isinstance(raw, dict):
        raise WorklistError(f"{WORKLIST_FILE}: an item is not an object")
    try:
        return WorklistItem(**raw)
    except TypeError as error:
        raise WorklistError(f"{WORKLIST_FILE}: an item does not have the fields of a worklist item ({error})") from None


def _items_of(document: StyledDocument) -> list[Any]:
    items = document.data.get(_ITEMS) if isinstance(document.data, dict) else None
    if not isinstance(items, list):
        raise WorklistError(f"{WORKLIST_FILE}: no list of items")
    return items


def _exists(ctx: MigrationContext) -> bool:
    return os.path.isfile(os.path.join(ctx.spec_root, WORKLIST_FILE))


def new_worklist_data() -> dict[str, Any]:
    """The content of a worklist with no item."""
    return {"$schema": WORKLIST_SCHEMA, _ITEMS: []}


def read_items(ctx: MigrationContext) -> list[WorklistItem]:
    """Every item of the worklist, in file order; empty when the file does not exist.

    Raises:
        WorklistError: the file is not a worklist.
    """
    if not _exists(ctx):
        return []
    return [_item_from(raw) for raw in _items_of(ctx.documents.load(WORKLIST_FILE))]


def missing_items(ctx: MigrationContext, items: Iterable[WorklistItem]) -> list[WorklistItem]:
    """The items of *items* whose id is not listed yet (a closed item counts as listed), each id once.

    This is what a script's ``detect`` counts: it finds nothing once its items are listed, however a person has closed them.

    Raises:
        WorklistError: the file is not a worklist, or an item has the id of a listed item that is about another case.
    """
    listed = {item.id: item for item in read_items(ctx)}
    missing: dict[str, WorklistItem] = {}
    for item in items:
        known = listed.get(item.id) or missing.get(item.id)
        if known is None:
            missing[item.id] = item
        elif (known.step, known.kind, known.about) != (item.step, item.kind, item.about):
            raise WorklistError(f"{item.id} names two cases: {known.about!r} and {item.about!r}; give one of them a key")
    return list(missing.values())


def add_items(ctx: MigrationContext, items: Iterable[WorklistItem]) -> int:
    """Add the items that are not listed yet and return how many were added (the file is created when it is missing and an item is added).

    An item whose id is listed, closed or open, is left exactly as it is.  The runner writes the file after ``apply``.

    Raises:
        WorklistError: as ``missing_items``.
    """
    new = missing_items(ctx, items)
    if not new:
        return 0
    document = ctx.documents.load(WORKLIST_FILE) if _exists(ctx) else ctx.documents.create(WORKLIST_FILE, new_worklist_data())
    listed = _items_of(document)
    listed.extend(item.to_json() for item in new)
    listed.sort(key=lambda raw: (raw["step"], raw["kind"], raw["id"]))
    return len(new)
