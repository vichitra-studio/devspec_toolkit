"""One reader of the open ambiguity items of a spec folder.

The open-item check, the waiting rule and the upstream backlog must agree on where items live, what "open" means and
what an item is about.  This module is that single answer; it reads files only (no graph, no schema).

Locations are the arrays of kind ``ambiguity-item`` in ``tools/entry_key_registry.json``: ``.ambiguities`` of the step
files 00 to 15 (with 02a), ``.plan.ambiguities`` of the anchor ``16_impl_context.json`` and, in each
``impl_context/ms_*_plan.json``, ``.plan.ambiguities`` (step 16a) and ``.execution.emergent_ambiguities`` (step 16b).
The data files of the extensions folder (the JSON files directly in ``extensions/`` that are no schema file) are files
of step 13: the items of their ``.ambiguities`` are read like the manifest's, after it.  Such a file is the host's and
its own schema judges its shape (the step's validation reports it), so here it is read for what it holds: a file that is
not readable JSON, an ``ambiguities`` that is no list and an entry that is no object yield nothing and raise nothing.

Two item shapes are read (the legacy one stays: a spec that is not migrated yet, and an item the migration leaves in
its 1.1.1 shape for a person to rewrite, still carry it):
``unified`` (has ``about``, no ``severity``) and ``legacy`` (the 1.1.1 shapes with ``severity``/``status``/``impact``).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal, NamedTuple

from .host_schemas import find_host_schemas
from .loaders import load_json_artifact
from .step_paths import EXTENSION_STEP, EXTENSIONS_DIR_NAME, PLAN_DIR_NAME, PLAN_FILE_GLOB, STEP_JSON_RE

Shape = Literal["unified", "legacy"]

PLAN_FILE_RE = re.compile(fnmatch.translate(PLAN_FILE_GLOB))
"""The plan file pattern as a regex, derived from ``PLAN_FILE_GLOB`` (match a bare file name with ``.match``)."""
ANCHOR_STEP = "16"
SILENT_MARKER = "silent"
_RESOLVED = "resolved"
_STEPS_WITH_ITEMS = frozenset(
    {"00", "01", "02", "02a", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15"}
)


class AmbiguityLocation(NamedTuple):
    """One array that holds ambiguity items: its step, its jq path and whether it sits in a milestone plan file."""

    step: str
    array_path: str
    in_plan_file: bool


LOCATIONS: tuple[AmbiguityLocation, ...] = (
    *(AmbiguityLocation(step, ".ambiguities", False) for step in sorted(_STEPS_WITH_ITEMS)),
    AmbiguityLocation(ANCHOR_STEP, ".plan.ambiguities", False),
    AmbiguityLocation("16a", ".plan.ambiguities", True),
    AmbiguityLocation("16b", ".execution.emergent_ambiguities", True),
)

PLAN_ITEM_STEPS: frozenset[str] = frozenset(loc.step for loc in LOCATIONS if loc.in_plan_file)
"""The steps whose items live in a milestone plan file (``16a`` and ``16b``; the anchor's ``16`` is a step file)."""


class AmbiguityReadError(ValueError):
    """A file or array of ambiguity items cannot be read; ``path`` names the file, ``reason`` what is wrong."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


class SilentTarget(NamedTuple):
    """What an item with a ``missing_kind`` is about: a node of that kind missing from the parent."""

    marker: str
    missing_kind: str
    parent: str


@dataclass(frozen=True)
class AmbiguityItem:
    """One ambiguity item as it stands in its file.

    ``artifact_path`` is the file, ``step`` the step that owns the array (``16a`` for ``plan.ambiguities`` of a
    milestone plan, ``16b`` for its ``execution.emergent_ambiguities``, ``16`` for the anchor), ``location`` the jq
    path of the array and ``raw`` the item object, unchanged.
    """

    artifact_path: str
    step: str
    location: str
    raw: dict[str, Any]
    shape: Shape

    @property
    def id(self) -> str:
        """The item id, ``""`` when the item has none."""
        value = self.raw.get("id")
        return value if isinstance(value, str) else ""

    @property
    def description(self) -> str:
        """The item description, ``""`` when it has none."""
        value = self.raw.get("description")
        return value if isinstance(value, str) else ""

    @property
    def decision(self) -> str | None:
        """The recorded answer as authored, ``None`` when it is absent or blank (the item still needs an answer)."""
        value = self.raw.get("decision")
        return value if isinstance(value, str) and value.strip() else None

    @property
    def about_ids(self) -> tuple[str, ...]:
        """The ``about`` ids that are strings, in order (``()`` for a legacy item); ``about_targets`` adds the silent-spec reading."""
        about = self.raw.get("about")
        return tuple(a for a in about if isinstance(a, str)) if isinstance(about, list) else ()


def shape_of(raw: dict[str, Any]) -> Shape:
    """``unified`` when *raw* has ``about`` and no ``severity``, else ``legacy``."""
    return "unified" if "about" in raw and "severity" not in raw else "legacy"


def is_open(item: AmbiguityItem) -> bool:
    """Whether *item* still waits for an answer.

    A unified item is open while it is present (applying it deletes it).  A legacy item is open unless its
    ``status`` is ``resolved``; this is the only place the legacy ``status`` is read.
    """
    return item.shape == "unified" or item.raw.get("status") != _RESOLVED


def about_targets(item: AmbiguityItem) -> tuple[str | SilentTarget, ...]:
    """What *item* is about: its ``about`` ids, or the silent-spec target when ``missing_kind`` is set.

    With a ``missing_kind`` the ``about`` ids name the parent that should hold the missing node, so the result is the
    single ``("silent", missing_kind, about[0])`` target.  A legacy item has no ``about`` and gives ``()``.
    """
    about = item.about_ids
    missing_kind = item.raw.get("missing_kind")
    if isinstance(missing_kind, str) and missing_kind and about:
        return (SilentTarget(SILENT_MARKER, missing_kind, about[0]),)
    return about


def _step_of_file(name: str) -> str | None:
    """The step of a root spec file name (``05_interface_contracts.json`` gives ``05``), ``None`` for others."""
    match = STEP_JSON_RE.match(name)
    return match.group(1) if match else None


def _load(path: str) -> dict[str, Any]:
    """Load one artifact; raises ``AmbiguityReadError`` when it is not readable JSON or not readable at all."""
    try:
        return load_json_artifact(path)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AmbiguityReadError(path, f"not readable JSON ({exc})") from exc
    except OSError as exc:
        raise AmbiguityReadError(path, exc.strerror or str(exc)) from exc


def _array_at(doc: dict[str, Any], array_path: str) -> Any:
    """The value at a dotted ``.a.b`` path of *doc*, ``None`` when a segment is missing."""
    node: Any = doc
    for key in array_path.lstrip(".").split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _items_in(path: str, doc: dict[str, Any], location: AmbiguityLocation) -> Iterator[AmbiguityItem]:
    """The items of one location of one document; raises ``AmbiguityReadError`` on a malformed array."""
    array = _array_at(doc, location.array_path)
    if array is None:
        return
    if not isinstance(array, list):
        raise AmbiguityReadError(path, f"{location.array_path} is not a list")
    for entry in array:
        if not isinstance(entry, dict):
            raise AmbiguityReadError(path, f"{location.array_path} holds an entry that is not an object")
        yield AmbiguityItem(path, location.step, location.array_path, entry, shape_of(entry))


def _extension_files(spec_dir: str) -> list[str]:
    """The data files of the extensions folder (``find_host_schemas``): the JSON files directly in it that are no schema file, in name order."""
    return [os.path.join(spec_dir, EXTENSIONS_DIR_NAME, name) for name in find_host_schemas(spec_dir).data_files]


def _extension_items(path: str, location: AmbiguityLocation) -> list[AmbiguityItem]:
    """The items of one data file of the extensions folder: the objects of its list, none when the file or the list cannot be read as one (never raises)."""
    try:
        array = _array_at(_load(path), location.array_path)
    except AmbiguityReadError:
        return []
    entries = array if isinstance(array, list) else []
    return [AmbiguityItem(path, location.step, location.array_path, entry, shape_of(entry)) for entry in entries if isinstance(entry, dict)]


def _root_files(spec_dir: str) -> Iterator[tuple[str, AmbiguityLocation, bool]]:
    """Each step file with the location of its items and whether it is a file of the host's own shape.

    The root files (00 to 15, 16) come in file-name order; the data files of the extensions folder come at the place of
    step 13, after its root file.
    """
    by_step = {loc.step: loc for loc in LOCATIONS if not loc.in_plan_file}
    of_extensions = [(path, by_step[EXTENSION_STEP], True) for path in _extension_files(spec_dir)]
    for name in sorted(os.listdir(spec_dir)):
        step = _step_of_file(name)
        if step in by_step:
            if step > EXTENSION_STEP:  # the first root file of a later step: the files of the folder come before it
                yield from of_extensions
                of_extensions = []
            yield os.path.join(spec_dir, name), by_step[step], False
    yield from of_extensions


def _plan_files(spec_dir: str) -> list[str]:
    """The milestone plan files ``impl_context/ms_*_plan.json`` (immediate children only), in name order."""
    plan_dir = os.path.join(spec_dir, PLAN_DIR_NAME)
    if not os.path.isdir(plan_dir):
        return []
    return [os.path.join(plan_dir, n) for n in sorted(os.listdir(plan_dir)) if PLAN_FILE_RE.match(n)]


def iter_ambiguity_items(spec_dir: str) -> Iterator[AmbiguityItem]:
    """Yield every ambiguity item of *spec_dir*, open or not, in file order: step files (the data files of the extensions folder with step 13), the anchor, milestone plans.

    Items of a milestone plan come as ``plan.ambiguities`` (step ``16a``) then ``execution.emergent_ambiguities``
    (step ``16b``).  A missing folder, file or array yields nothing.

    Raises:
        AmbiguityReadError: a file is not readable JSON, an array is not a list or holds a non-object entry (not for a
            data file of the extensions folder: its shape is its own schema's to judge).
    """
    if not os.path.isdir(spec_dir):
        return
    for path, location, own_shape in _root_files(spec_dir):
        yield from _extension_items(path, location) if own_shape else _items_in(path, _load(path), location)
    plan_locations = [loc for loc in LOCATIONS if loc.in_plan_file]
    for path in _plan_files(spec_dir):
        doc = _load(path)
        for location in plan_locations:
            yield from _items_in(path, doc, location)


class ItemsRead(NamedTuple):
    """What ``read_ambiguity_items`` found: the items read, and the read error that ended the list (``None`` when it was complete)."""

    items: tuple[AmbiguityItem, ...]
    error: AmbiguityReadError | None


def read_ambiguity_items(spec_dir: str) -> ItemsRead:
    """Every ambiguity item of *spec_dir* up to the first file the reader cannot read, and that read error.

    The items are those of ``iter_ambiguity_items``; a run that reads them once passes this result to each consumer
    instead of reading the folder again.
    """
    items: list[AmbiguityItem] = []
    try:
        items.extend(iter_ambiguity_items(spec_dir))
    except AmbiguityReadError as error:
        return ItemsRead(tuple(items), error)
    return ItemsRead(tuple(items), None)
