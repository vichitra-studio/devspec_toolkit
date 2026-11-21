"""The anchor store: the status rows of ``spec/16_impl_context.json`` and the one function that writes them.

An anchor row is a status record about one roadmap milestone (``plan.milestone_index[]``).  This module reads the rows
and holds ``write_row_state``, the only function of the toolkit that writes an existing row's ``status``,
``deferral_reason`` and ``close``.  The milestone commands are its callers; first authoring of a row is ``step create 16``
or ``json insert --step 16`` and is outside it.

Readers (``read_row``, ``read_statuses``, ``is_legacy_close``) read the raw file and never validate a plan: a legacy
shape reads as it is.  A row with no ``status`` reads as ``pending``; a status outside the four values raises E801 with
subcode ``STATUS_UNKNOWN``.

The writer takes the write lock of the spec folder, edits the row with jq ``patch``/``delete`` on the text and formats the
file as ``json patch --id`` does, refuses (E767) an edit that adds a schema violation to the file, and replaces the file
atomically.  The row's ``status``, ``deferral_reason`` and ``close`` are not part of any lock entry (the contract of an
anchor row is ``summary`` and ``checklist_id_prefix``), so the trace lock stays true without a write.

Stable for M10 (names and signatures are documented here and in the plan; M8 owns the record shape, M10 owns when they
run): ``write_legacy_close(spec_root, milestone_id, source)`` and
``append_close_migration(spec_root, milestone_id, hash_after, note)``.
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..core.errors import FindingError, make_error, refusal
from ..core.json_utils import JsonUtilsError, check_edit, delete_text, json_write_atomic, patch_text
from ..core.loaders import read_json_object
from ..graph.gitview import git_reason, host_root_of, path_exists_at, resolve_ref, run_git, spec_path_in_repo
from ..trace.lockfile import with_write_lock
from . import plans

ANCHOR_FILE = "16_impl_context.json"
LEGACY_MARKER = "legacy-migration"
STATUSES = ("pending", "in_progress", "deferred", "done")
DEFAULT_STATUS = "pending"
_ROWS = ("plan", "milestone_index")
_FIELDS = ("status", "deferral_reason", "close")


@dataclass(frozen=True)
class AnchorState:
    """What a status reader needs of one row: its status, who signed it off (``None`` while not closed) and its ``close`` record."""

    status: str
    signed_off_by: str | None
    close: Mapping[str, Any] | None


@dataclass(frozen=True)
class AnchorRow:
    """One anchor row: ``milestone_id`` is the one id of its ``about``, ``index`` its place in ``plan.milestone_index``."""

    anchor_id: str
    milestone_id: str
    index: int
    status: str
    deferral_reason: str | None
    close: Mapping[str, Any] | None

    @property
    def state(self) -> AnchorState:
        """The row as ``read_statuses`` reports it."""
        return state_of(self.status, self.close)


def state_of(status: str, close: Mapping[str, Any] | None) -> AnchorState:
    """The ``AnchorState`` of a status and a close record."""
    signer = close.get("signed_off_by") if close else None
    return AnchorState(status, signer if isinstance(signer, str) else None, close)


def is_legacy_close(close: Mapping[str, Any] | None) -> bool:
    """Whether *close* is the close record of a legacy-closed milestone: its ``signed_off_by`` is ``legacy-migration``.

    Reads only that one key of the ``close`` object of an anchor row; a ``None`` or a record without the key is not
    legacy.  This is the one test of "legacy-closed" (the step-16 validators call it).
    """
    return bool(close) and close.get("signed_off_by") == LEGACY_MARKER


def anchor_path(spec_root: str | os.PathLike[str]) -> str:
    """The anchor file of the spec folder *spec_root*."""
    return os.path.join(os.fspath(spec_root), ANCHOR_FILE)


def _status_of(raw: Any, milestone_id: str) -> str:
    """The status of a raw row value: absent reads as ``pending``; a value that is not one of ``STATUSES`` raises E801 (``STATUS_UNKNOWN``)."""
    if raw is None:
        return DEFAULT_STATUS
    if raw not in STATUSES:
        raise FindingError(make_error(
            "E801",
            f"the anchor row of {milestone_id} has the status {raw!r}, which is not one of {', '.join(STATUSES)}; "
            f"set it to one of them in {ANCHOR_FILE}",
            subcode="STATUS_UNKNOWN",
            node_id=milestone_id,
        ))
    return raw


def _row_of(index: int, raw: Mapping[str, Any], milestone_id: str) -> AnchorRow:
    reason, close = raw.get("deferral_reason"), raw.get("close")
    return AnchorRow(
        anchor_id=str(raw.get("anchor_id", "")),
        milestone_id=milestone_id,
        index=index,
        status=_status_of(raw.get("status"), milestone_id),
        deferral_reason=reason if isinstance(reason, str) else None,
        close=close if isinstance(close, dict) else None,
    )


def _raw_rows(document: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    """The entries of ``plan.milestone_index`` of an anchor document that are objects; empty for any other shape."""
    held: Any = document
    for key in _ROWS:
        held = held.get(key) if isinstance(held, dict) else None
    return [entry for entry in held if isinstance(entry, dict)] if isinstance(held, list) else []


def _milestone_of(raw: Mapping[str, Any]) -> str | None:
    """The one milestone id of a raw row's ``about`` array; ``None`` for a row of another shape (a legacy row has no ``about``)."""
    about = raw.get("about")
    return about[0] if isinstance(about, list) and len(about) == 1 and isinstance(about[0], str) else None


def read_row(spec_root: str | os.PathLike[str], milestone_id: str) -> AnchorRow | None:
    """The anchor row whose ``about`` holds *milestone_id*, or ``None`` when the file or the row is absent or unreadable.

    Raises:
        FindingError: E801 (``STATUS_UNKNOWN``) when the row's ``status`` is not one of the four values.
    """
    rows = _raw_rows(read_json_object(anchor_path(spec_root)))
    return next((_row_of(i, raw, milestone_id) for i, raw in enumerate(rows) if _milestone_of(raw) == milestone_id), None)


def _statuses_of(document: Mapping[str, Any] | None) -> dict[str, AnchorState]:
    states: dict[str, AnchorState] = {}
    for index, raw in enumerate(_raw_rows(document)):
        milestone_id = _milestone_of(raw)
        if milestone_id is not None:
            states.setdefault(milestone_id, _row_of(index, raw, milestone_id).state)
    return states


def _anchor_at(spec_root: str, git_ref: str, git_root: str | None) -> Mapping[str, Any] | None:
    """The anchor document as committed at *git_ref*; ``None`` when the file is absent at that commit or is not a JSON object."""
    root = host_root_of(spec_root, git_root)
    path = f"{spec_path_in_repo(spec_root, root)}/{ANCHOR_FILE}"
    if not path_exists_at(git_ref, root, path):
        return None
    process = run_git(root, ["show", f"{resolve_ref(git_ref, root)}:./{path}"])
    if process.returncode != 0:
        raise refusal("E708", f"{path} cannot be read at ref '{git_ref}': {git_reason(process)}")
    try:
        document = json.loads(process.stdout)
    except ValueError:
        return None
    return document if isinstance(document, dict) else None


def read_statuses(
    spec_root: str | os.PathLike[str], git_ref: str | None = None, git_root: str | None = None
) -> dict[str, AnchorState]:
    """``{milestone id: AnchorState}`` of every anchor row that has an ``about``, in the working tree or at *git_ref*.

    With *git_ref* the anchor file is read through ``git show`` from the repository at *git_root* (default: the folder
    that holds the spec folder, ``host_root_of``); a file that does not exist at the commit gives ``{}``.  An unreadable
    file gives ``{}``.

    Raises:
        FindingError: E801 (``STATUS_UNKNOWN``) for a row with an unknown status; E708 when the ref does not resolve or
            git fails.
    """
    spec = os.fspath(spec_root)
    document = read_json_object(anchor_path(spec)) if git_ref is None else _anchor_at(spec, git_ref, git_root)
    return _statuses_of(document)


def _edited_text(content: str, row_path: str, status: str, deferral_reason: str | None, close: Mapping[str, Any] | None) -> str:
    """*content* with the row at *row_path* given exactly this status, deferral reason and close (``None`` removes the field)."""
    values = {"status": status, "deferral_reason": deferral_reason, "close": close}
    for name in _FIELDS:
        path = f"{row_path}.{name}"
        content = delete_text(content, path) if values[name] is None else patch_text(content, path, json.dumps(values[name]))
    return content


def write_row_state(
    spec_root: str | os.PathLike[str],
    milestone_id: str,
    status: str,
    *,
    deferral_reason: str | None = None,
    close: Mapping[str, Any] | None = None,
    repo_root: str | None = None,
) -> None:
    """Set the ``status``, ``deferral_reason`` and ``close`` of the anchor row of *milestone_id*.

    The three fields are set together: ``deferral_reason`` and ``close`` that are ``None`` are removed from the row.  The
    write holds the write lock of the spec folder, changes only the row and replaces the file atomically (formatted as
    ``json patch`` formats), after the schema check of ``json patch`` (the edit may not add a violation the file did not have; *repo_root* is the
    toolkit, default the one the code is in).  Nothing is written when any step is refused.

    Raises:
        FindingError: E767 when the file has no row for *milestone_id* or the edit would add a schema violation (a
            ``done`` row without ``close``, a status that is not one of the four, a ``deferred`` row without a reason);
            E769 when another write holds the lock.
    """
    spec = os.fspath(spec_root)
    path = anchor_path(spec)
    with with_write_lock(spec):
        try:
            with open(path, encoding="utf-8") as handle:
                content = handle.read()
        except OSError as error:
            raise refusal("E767", f"cannot read {ANCHOR_FILE}: {error.strerror or error}") from None
        rows = _raw_rows(read_json_object(path))
        index = next((i for i, raw in enumerate(rows) if _milestone_of(raw) == milestone_id), None)
        if index is None:
            raise refusal("E767", f"{ANCHOR_FILE} has no anchor row about {milestone_id}; add the row first (`specdev json insert --step 16 .plan.milestone_index '<row>'`)")
        try:
            new_text = _edited_text(content, f".plan.milestone_index[{index}]", status, deferral_reason, close)
            check_edit(path, content, new_text, repo_root)
            json_write_atomic(path, new_text)
        except JsonUtilsError as error:
            raise refusal("E767", f"the anchor row of {milestone_id} was not written: {error}") from None


def write_legacy_close(
    spec_root: str | os.PathLike[str], milestone_id: str, source: str, *, repo_root: str | None = None
) -> None:
    """Close *milestone_id* as a legacy close: status ``done`` and the record ``{signed_off_by: legacy-migration, source, signoff: null, plan_hash}``.

    ``plan_hash`` is the hash of the milestone's plan file now (``plans.plan_hash``), so ``frozen_plan_drift`` is quiet
    right after the call; every later change of the plan is recorded with ``append_close_migration``.

    Raises:
        FindingError: E803 when no plan names the milestone; E767 as ``write_row_state``.
    """
    spec = os.fspath(spec_root)
    close = {
        "signed_off_by": LEGACY_MARKER,
        "source": source,
        "signoff": None,
        "plan_hash": plans.plan_hash(plans.require_plan(spec, milestone_id)),
    }
    write_row_state(spec, milestone_id, "done", close=close, repo_root=repo_root)


def append_close_migration(
    spec_root: str | os.PathLike[str], milestone_id: str, hash_after: str, note: str, *, repo_root: str | None = None
) -> None:
    """Record a migration of the frozen plan of *milestone_id*: append ``{hash_after, note}`` to ``close.migrations``.

    The only change a plan may have after its close; the ``frozen-plans`` check compares the plan with the last
    ``hash_after``.

    Raises:
        FindingError: E801 when the milestone is not closed; E767 as ``write_row_state``.
    """
    row = read_row(spec_root, milestone_id)
    if row is None or row.status != "done" or row.close is None:
        raise refusal("E801", f"{milestone_id} is not closed (no anchor row with status done and a close record), so its close record cannot be extended")
    migrations = [*row.close.get("migrations", []), {"hash_after": hash_after, "note": note}]
    write_row_state(spec_root, milestone_id, "done", close={**row.close, "migrations": migrations}, repo_root=repo_root)
