"""The open-item check and the deletion of resolved items.

An open item (an ``ambiguity-item``) is a question the spec cannot answer yet.  ``check_open_items`` reports the live
ones at one of three gates and ``delete_resolved_items`` removes the 1.1.1 items already marked ``resolved``.  Where the
items are and what "open" means is the single answer of ``core.ambiguity_items``; this module only decides what each
gate does with them.

======  ================================================  ====================================
Gate    Finding                                           Owner
======  ================================================  ====================================
step    W630 per unified item, one summary W630 per        ``step:<step of the array>``
        (artifact, step) for items of the legacy shape
merge   E631 per live item, W633 per item of a frozen      ``merge-check``
        plan (listed for triage, does not fail)
close   E632 per item of the given milestone plan          ``close-gate``
======  ================================================  ====================================

W630 and W633 are not in ``PROMOTABLE_PAIRS``: ``SPECDEV_WARNINGS_AS_ERRORS`` does not turn them into blockers.
"""
from __future__ import annotations

import os
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Literal

from specdev_tools.core.ambiguity_items import (
    AmbiguityItem,
    AmbiguityReadError,
    SilentTarget,
    about_targets,
    is_open,
    iter_ambiguity_items,
)
from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.core.json_utils import delete_text, json_write_atomic
from specdev_tools.graph.ownership import STEP_PREFIX
from specdev_tools.trace.writing import writing_graph

Gate = Literal["step", "merge", "close"]
FrozenProvider = Callable[[Path], bool]

MERGE_OWNER = "merge-check"
CLOSE_OWNER = "close-gate"
_PLAN_STEPS = frozenset({"16a", "16b"})
_ANSWER_KNOWN = "known: apply in the batch pass"
_ANSWER_NEEDED = "needed from the operator"


def default_frozen(plan_path: Path) -> bool:
    """The frozen-plan provider until a close record exists (M8): no plan is frozen.

    M8 passes ``functools.partial(plans.is_frozen_path, spec_root)`` instead; merge and release gates pass that
    provider, never this one.
    """
    return False


def check_open_items(
    spec_dir: str | os.PathLike[str],
    *,
    gate: Gate,
    plan_path: str | os.PathLike[str] | None = None,
    frozen: FrozenProvider = default_frozen,
) -> list[SpecError]:
    """The findings of the open items of *spec_dir* at *gate* (``step``, ``merge`` or ``close``).

    *plan_path* is the milestone plan the ``close`` gate is about and is required there; the other gates ignore it.
    *frozen* tells whether a milestone plan file is frozen (an open item in a frozen plan is a legacy item: not live at
    the step gate, W633 at the merge gate); anchor and step-file items are never legacy.  A file the reader cannot read
    ends the list with one E520 (``cannot read <file>: <reason>``).

    Raises:
        ValueError: *gate* is not one of the three, or the ``close`` gate has no *plan_path*.
    """
    root = os.fspath(spec_dir)
    items, unreadable = _open_items(root)
    if gate == "close":
        if plan_path is None:
            raise ValueError("the close gate needs the plan_path of the milestone plan")
        findings = _close_findings(items, root, os.fspath(plan_path))
    elif gate == "merge":
        findings = _merge_findings(items, root, frozen)
    elif gate == "step":
        findings = _step_findings(items, root, frozen)
    else:
        raise ValueError(f"unknown open-item gate {gate!r}; expected step, merge or close")
    return findings + unreadable


def delete_resolved_items(
    spec_dir: str | os.PathLike[str], repo_root: str | os.PathLike[str], *, apply: bool = False
) -> dict[str, int]:
    """Count (and with *apply* delete) the legacy items whose ``status`` is ``resolved``; the count is per file.

    Looks in ``plan.ambiguities`` and ``execution.emergent_ambiguities`` of every milestone plan and in the anchor's
    ``plan.ambiguities`` (the arrays of ``core.ambiguity_items``).  Items that are not resolved are never touched.  The
    keys of the result are file paths relative to *spec_dir*, only for files that hold at least one resolved item.
    A dry run reads only; a write holds the write lock and each file is replaced atomically (a failure on a later file
    leaves the earlier ones written).  It does not decide whether a plan is frozen: M10 runs it before the close hash.

    Raises:
        FindingError: E520 when a spec file cannot be read or written (``cannot write <file>: <reason>``), E769 when
            another write holds the lock.
    """
    root = os.fspath(spec_dir)
    with writing_graph(None, root, os.fspath(repo_root), "delete resolved open items", write=apply):
        positions = _resolved_positions(root)
        if apply:
            for path, by_location in positions.items():
                _rewrite_without(path, root, by_location)
    return {_relative(root, path): sum(map(len, by_location.values())) for path, by_location in positions.items()}


def _relative(root: str, path: str) -> str:
    return os.path.relpath(path, root)


def _unreadable(root: str, error: AmbiguityReadError) -> SpecError:
    return make_error("E520", f"cannot read {error.path}: {error.reason}", file=_relative(root, error.path))


def _open_items(root: str) -> tuple[list[AmbiguityItem], list[SpecError]]:
    """The open items of *root* read before the first unreadable file, and the E520 for that file (or nothing)."""
    items: list[AmbiguityItem] = []
    try:
        items.extend(item for item in iter_ambiguity_items(root) if is_open(item))
    except AmbiguityReadError as error:
        return items, [_unreadable(root, error)]
    return items, []


def _frozen_paths(items: Iterable[AmbiguityItem], frozen: FrozenProvider) -> set[str]:
    """The milestone plan files among the files of *items* that *frozen* says are frozen."""
    plan_files = {item.artifact_path for item in items if item.step in _PLAN_STEPS}
    return {path for path in plan_files if frozen(Path(path))}


def _about_text(item: AmbiguityItem) -> str:
    targets = about_targets(item)
    if not targets:
        return "nothing recorded"
    return ", ".join(
        f"missing {target.missing_kind} in {target.parent}" if isinstance(target, SilentTarget) else target
        for target in targets
    )


def _answer_text(item: AmbiguityItem) -> str:
    decision = item.raw.get("decision")
    return _ANSWER_KNOWN if isinstance(decision, str) and decision.strip() else _ANSWER_NEEDED


def _item_error(code: str, item: AmbiguityItem, root: str, owner: str, what: str) -> SpecError:
    artifact = _relative(root, item.artifact_path)
    return make_error(
        code,
        f"open item {item.id} in {artifact}: about {_about_text(item)}; {what}",
        file=artifact,
        node_id=item.id or None,
        owner=owner,
    )


def _step_findings(items: list[AmbiguityItem], root: str, frozen: FrozenProvider) -> list[SpecError]:
    frozen_files = _frozen_paths(items, frozen)
    live = [item for item in items if item.artifact_path not in frozen_files]
    findings = [
        _item_error("W630", item, root, STEP_PREFIX + item.step, f"answer {_answer_text(item)}")
        for item in live
        if item.shape == "unified"
    ]
    legacy = Counter((item.artifact_path, item.step) for item in live if item.shape == "legacy")
    findings.extend(_legacy_summary(path, step, count, root) for (path, step), count in legacy.items())
    return findings


def _legacy_summary(path: str, step: str, count: int, root: str) -> SpecError:
    artifact = _relative(root, path)
    noun = "legacy open item" if count == 1 else "legacy open items"
    return make_error(
        "W630",
        f"{count} {noun} in {artifact}; see `upstream-backlog`",
        file=artifact,
        owner=STEP_PREFIX + step,
    )


def _merge_findings(items: list[AmbiguityItem], root: str, frozen: FrozenProvider) -> list[SpecError]:
    frozen_files = _frozen_paths(items, frozen)
    return [
        _item_error("W633", item, root, MERGE_OWNER, "in a frozen plan: listed for triage, does not fail the merge")
        if item.artifact_path in frozen_files
        else _item_error("E631", item, root, MERGE_OWNER, f"apply the answer ({_answer_text(item)}), then delete the item")
        for item in items
    ]


def _close_findings(items: list[AmbiguityItem], root: str, plan_path: str) -> list[SpecError]:
    plan = Path(plan_path).resolve()
    return [
        _item_error("E632", item, root, CLOSE_OWNER, "answer it and delete the item before the milestone closes")
        for item in items
        if item.step in _PLAN_STEPS and Path(item.artifact_path).resolve() == plan
    ]


def _read_all(root: str) -> Iterator[AmbiguityItem]:
    try:
        yield from iter_ambiguity_items(root)
    except AmbiguityReadError as error:
        raise FindingError(_unreadable(root, error)) from error


def _resolved_positions(root: str) -> dict[str, dict[str, list[int]]]:
    """Per file and array location, the list indices of the resolved items (the arrays are read in file order)."""
    seen: Counter[tuple[str, str]] = Counter()
    found: dict[str, dict[str, list[int]]] = {}
    for item in _read_all(root):
        key = (item.artifact_path, item.location)
        index, seen[key] = seen[key], seen[key] + 1
        if not is_open(item):
            found.setdefault(item.artifact_path, {}).setdefault(item.location, []).append(index)
    return found


def _rewrite_without(path: str, root: str, by_location: dict[str, list[int]]) -> None:
    """Write *path* without the items at the given indices of each array; E520 when it cannot be written."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    for location, indices in by_location.items():
        text = delete_text(text, f"{location}[{','.join(map(str, indices))}]")
    try:
        json_write_atomic(path, text)
    except OSError as error:
        artifact = _relative(root, path)
        raise FindingError(make_error(
            "E520", f"cannot write {artifact}: {error.strerror or error}", file=artifact
        )) from error
