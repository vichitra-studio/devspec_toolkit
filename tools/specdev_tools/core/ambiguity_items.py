"""One reader of the open ambiguity items of a spec folder.

The open-item check, the waiting rule and the upstream backlog must agree on where items live, what "open" means and
what an item is about.  This module is that single answer; it reads files only (no graph, no schema).

Locations are the arrays of kind ``ambiguity-item`` in ``tools/entry_key_registry.json``: ``.ambiguities`` of the step
files 00 to 15 (with 02a), ``.plan.ambiguities`` of the anchor ``16_impl_context.json`` and, in each
``impl_context/ms_*_plan.json``, ``.plan.ambiguities`` (step 16a) and ``.execution.emergent_ambiguities`` (step 16b).

Two item shapes are read until the hosts are migrated (the legacy branch goes with that migration):
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

from .loaders import load_json_artifact

Shape = Literal["unified", "legacy"]

STEP_FILE_RE = re.compile(r"^(\d{2}[a-z]?)_[^/]*\.json$")
PLAN_DIR = "impl_context"
PLAN_FILE_GLOB = "ms_*_plan.json"
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
    raw_about = item.raw.get("about")
    about = tuple(a for a in raw_about if isinstance(a, str)) if isinstance(raw_about, list) else ()
    missing_kind = item.raw.get("missing_kind")
    if isinstance(missing_kind, str) and missing_kind and about:
        return (SilentTarget(SILENT_MARKER, missing_kind, about[0]),)
    return about


def _step_of_file(name: str) -> str | None:
    """The step of a root spec file name (``05_interface_contracts.json`` gives ``05``), ``None`` for others."""
    match = STEP_FILE_RE.match(name)
    return match.group(1) if match else None


def _load(path: str) -> dict[str, Any]:
    """Load one artifact; raises ``AmbiguityReadError`` when it is not readable JSON."""
    try:
        return load_json_artifact(path)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AmbiguityReadError(path, f"not readable JSON ({exc})") from exc


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


def _root_files(spec_dir: str) -> Iterator[tuple[str, AmbiguityLocation]]:
    """Each root step file (00 to 15, 16) with the location of its items, in file-name order."""
    by_step = {loc.step: loc for loc in LOCATIONS if not loc.in_plan_file}
    for name in sorted(os.listdir(spec_dir)):
        step = _step_of_file(name)
        if step in by_step:
            yield os.path.join(spec_dir, name), by_step[step]


def _plan_files(spec_dir: str) -> list[str]:
    """The milestone plan files ``impl_context/ms_*_plan.json`` (immediate children only), in name order."""
    plan_dir = os.path.join(spec_dir, PLAN_DIR)
    if not os.path.isdir(plan_dir):
        return []
    return [os.path.join(plan_dir, n) for n in sorted(os.listdir(plan_dir)) if fnmatch.fnmatch(n, PLAN_FILE_GLOB)]


def iter_ambiguity_items(spec_dir: str) -> Iterator[AmbiguityItem]:
    """Yield every ambiguity item of *spec_dir*, open or not, in file order: step files, the anchor, milestone plans.

    Items of a milestone plan come as ``plan.ambiguities`` (step ``16a``) then ``execution.emergent_ambiguities``
    (step ``16b``).  A missing folder, file or array yields nothing.

    Raises:
        AmbiguityReadError: a file is not readable JSON, an array is not a list or holds a non-object entry.
    """
    if not os.path.isdir(spec_dir):
        return
    for path, location in _root_files(spec_dir):
        yield from _items_in(path, _load(path), location)
    plan_locations = [loc for loc in LOCATIONS if loc.in_plan_file]
    for path in _plan_files(spec_dir):
        doc = _load(path)
        for location in plan_locations:
            yield from _items_in(path, doc, location)
