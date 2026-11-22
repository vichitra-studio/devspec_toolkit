"""The commands around the migration: ``align triage`` (read and close the worklist) and ``align validate`` (the end).

``align triage`` lists the items of ``spec/extras/migration/worklist.json`` (the decisions the scripts left for a person),
closes one (``resolved: true`` plus a note, the format of ``migration/worklist.py``) and prints the pre-migration values
of a step (``git show`` of the commit the capture names).  It writes the worklist file only, and only on ``--resolve``.

``align validate`` is the step that decides a migration is finished.  In this order, stopping at the first that fails:

1. the stamp records the toolkit's own version (a spec that was never migrated is refused, not stamped);
2. ``spec-check --merge`` (the whole spec in merge mode, against the merge base) has no error;
3. the stamp is finished: ``migration_status`` is cleared and ``last_migration`` refreshed, through
   ``schema_differ.stamp_specdev_version``, the one writer of the stamp.  No history entry is added: the runner wrote
   the one entry of this migration.  When this write fails the run stops here and nothing else is touched;
4. the files ``capture.json`` and ``worklist.json`` are deleted when no item is open (``keep_worklist`` keeps them);
   otherwise they are kept and the number of open items, and of those marked blocking, is told (information only: an
   open item, blocking or not, never fails validate; merge mode is the gate).

Nothing is written before step 3, so a refused validate leaves the tree as it was.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from specdev_tools.core.changelog_parser import compare_versions, get_toolkit_version
from specdev_tools.core.config import get_config
from specdev_tools.core.constants import STAMP_FILE, STATUS_IN_PROGRESS
from specdev_tools.core.errors import FindingError, SpecError
from specdev_tools.core.step_paths import get_step_from_path
from specdev_tools.generation.schema_differ import read_stamp, stamp_specdev_version
from specdev_tools.graph.gitview import host_root_of
from specdev_tools.migration.context import CAPTURE_FILE, GitReadError, MigrationContext, read_git
from specdev_tools.migration.worklist import (
    AUDIENCE_AGENT,
    AUDIENCE_OPERATOR,
    WORKLIST_FILE,
    WorklistError,
    WorklistItem,
    read_items,
)
from specdev_tools.migration.writer import DocumentSet, WriterError
from specdev_tools.validation.spec_check import run_spec_check

_AUDIENCE_ORDER = (AUDIENCE_OPERATOR, AUDIENCE_AGENT)
_STEP_ARGUMENT = re.compile(r"^(\d{1,2})([a-z]?)$")


class TriageError(Exception):
    """A triage request that cannot be answered (an unknown item, a missing capture); the message is for the person."""


# ---------------------------------------------------------------------------
# The worklist
# ---------------------------------------------------------------------------


def _context(spec_dir: str | os.PathLike[str], toolkit_root: str | os.PathLike[str], git_root: str | os.PathLike[str] | None) -> MigrationContext:
    spec = os.path.abspath(spec_dir)
    git = host_root_of(spec, git_root)
    version = (read_stamp(spec) or {}).get("toolkit_version", "")
    return MigrationContext(spec, git, git, os.path.abspath(toolkit_root), False, DocumentSet(spec), str(version), str(version))


def read_worklist(spec_dir: str | os.PathLike[str], toolkit_root: str | os.PathLike[str], git_root: str | os.PathLike[str] | None = None) -> list[WorklistItem]:
    """Every item of the worklist in file order (empty when the file does not exist).

    Raises:
        TriageError: the file is not a worklist.
    """
    try:
        return read_items(_context(spec_dir, toolkit_root, git_root))
    except (WorklistError, WriterError) as error:
        raise TriageError(str(error)) from None


def open_items(items: Sequence[WorklistItem]) -> list[WorklistItem]:
    """The items not closed."""
    return [item for item in items if not item.resolved]


def ordered(items: Sequence[WorklistItem]) -> list[WorklistItem]:
    """The items by audience (operator, then agent), blocking first, then step, kind and id."""
    return sorted(items, key=lambda item: (_AUDIENCE_ORDER.index(item.audience), not item.blocking, item.step, item.kind, item.id))


def select(items: Sequence[WorklistItem], step: str | None = None, audience: str | None = None) -> list[WorklistItem]:
    """The items of *step* (``"4"`` and ``"04"`` are the same) and of *audience*; ``None`` selects all."""
    wanted = normalize_step(step) if step else None
    return [item for item in items if (wanted is None or item.step == wanted) and (audience is None or item.audience == audience)]


def normalize_step(step: str) -> str:
    """``"4"`` as ``"04"``, ``"2A"`` as ``"02a"``; anything else is returned as given."""
    match = _STEP_ARGUMENT.match(step.strip().lower())
    return f"{int(match.group(1)):02d}{match.group(2)}" if match else step.strip()


def render_triage(items: Sequence[WorklistItem], spec_dir: str | os.PathLike[str], *, selection: str = "") -> str:
    """The list ``align triage`` prints: open items grouped by audience, blocking first, each with its id, then the count of closed ones."""
    still_open = ordered(open_items(items))
    closed = len(items) - len(open_items(items))
    blocking = sum(1 for item in still_open if item.blocking)
    lines = [f"Worklist{selection}: {len(still_open)} open item(s), {blocking} blocking; {closed} resolved"]
    for audience in _AUDIENCE_ORDER:
        group = [item for item in still_open if item.audience == audience]
        if not group:
            continue
        lines.append(f"\n{audience} ({len(group)} open):")
        for item in group:
            lines.append(f"  {'BLOCKING' if item.blocking else 'optional'}  {item.id}")
            lines.append(f"      step {item.step}, {item.kind}, about {item.about}")
            if item.evidence:
                lines.append(f"      evidence: {item.evidence}")
            if item.proposal:
                lines.append(f"      proposal: {item.proposal}")
    if still_open:
        lines.append(f'\nClose an item: specdev align triage {spec_dir} --resolve <id> --note "<what was decided>"')
    return "\n".join(lines)


def resolve_item(
    spec_dir: str | os.PathLike[str],
    toolkit_root: str | os.PathLike[str],
    item_id: str,
    note: str,
    git_root: str | os.PathLike[str] | None = None,
) -> str:
    """Close the item *item_id* (``resolved: true`` and *note*), editing ``worklist.json`` only; return the line to print.

    An item that is closed already is left as it is (its note is kept).

    Raises:
        TriageError: *note* is empty, the worklist does not exist or has no such item.
    """
    if not note.strip():
        raise TriageError("an item is closed by a note that says what was decided: pass --note with text")
    context = _context(spec_dir, toolkit_root, git_root)
    if not os.path.isfile(os.path.join(context.spec_root, WORKLIST_FILE)):
        raise TriageError(f"there is no worklist ({WORKLIST_FILE} does not exist under {context.spec_root})")
    try:
        document = context.documents.load(WORKLIST_FILE)
        raw_items = document.data.get("items", []) if isinstance(document.data, dict) else []
    except WriterError as error:
        raise TriageError(str(error)) from None
    for raw in raw_items:
        if isinstance(raw, dict) and raw.get("id") == item_id:
            if raw.get("resolved") is True:
                return f"{item_id}: already resolved (note: {raw.get('note', '')!r}); nothing written"
            raw["resolved"] = True
            raw["note"] = note.strip()
            context.documents.write()
            return f"{item_id}: resolved ({WORKLIST_FILE})"
    ids = ", ".join(str(raw.get("id")) for raw in raw_items if isinstance(raw, dict))
    raise TriageError(f"no worklist item has the id {item_id!r}" + (f"; the items are: {ids}" if ids else "; the worklist is empty"))


def legacy_text(spec_dir: str | os.PathLike[str], toolkit_root: str | os.PathLike[str], step: str, git_root: str | os.PathLike[str] | None = None) -> str:
    """The files of *step* as they were before the migration: ``git show <source commit>:<spec>/<file>`` of each, read-only.

    The commit, the spec folder and the list of files come from the capture (``source``); a file the migration deleted
    is still listed there.

    Raises:
        TriageError: there is no capture, the step has no file in it, or git cannot show a file.
    """
    context = _context(spec_dir, toolkit_root, git_root)
    capture_path = os.path.join(context.spec_root, CAPTURE_FILE)
    try:
        source = context.documents.load(CAPTURE_FILE).data["source"]
        commit, folder, files = source["commit"], source["spec_dir"], sorted(source["file_hashes"])
    except (OSError, WriterError, KeyError, TypeError):
        raise TriageError(f"there is no capture ({capture_path} is missing or not a capture): `specdev align apply --auto` writes it") from None
    wanted = normalize_step(step)
    chosen = [rel for rel in files if get_step_from_path(rel) == wanted]
    if not chosen:
        raise TriageError(f"the capture lists no file of step {wanted} (it lists the files of the spec as they were at {commit[:12]})")
    parts: list[str] = []
    for rel in chosen:
        try:
            text = read_git(context.git_root, "show", f"{commit}:{folder}/{rel}")
        except GitReadError as error:
            raise TriageError(str(error)) from None
        parts.append(f"=== {rel} at {commit[:12]} (git show {commit[:12]}:{folder}/{rel})\n{text.rstrip()}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# align validate
# ---------------------------------------------------------------------------


@dataclass
class ValidateReport:
    """What ``align validate`` found and did.

    ``refused`` is the reason it stopped before changing anything (``None`` when it did not); ``errors`` the findings
    of ``spec-check --merge`` (warnings included); ``unresolved`` the number of open items and ``blocking`` how many of
    those are marked blocking (information); ``deleted`` the files removed; ``stamp_finished`` whether
    ``migration_status`` was cleared.
    """

    refused: str | None = None
    blocking: int = 0
    errors: list[SpecError] = field(default_factory=list)
    unresolved: int = 0
    deleted: list[str] = field(default_factory=list)
    kept: str = ""
    stamp_finished: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def failed_errors(self) -> list[SpecError]:
        """The findings that fail the run: every one but a warning (every one, under ``SPECDEV_WARNINGS_AS_ERRORS``)."""
        return self.errors if get_config().warnings_as_errors else [error for error in self.errors if not error.code.startswith("W")]

    @property
    def ok(self) -> bool:
        return self.refused is None and not self.failed_errors


def validate_migration(
    spec_dir: str | os.PathLike[str],
    toolkit_root: str | os.PathLike[str],
    *,
    git_root: str | os.PathLike[str] | None = None,
    project_canon_dir: str | None = None,
    base_ref: str | None = None,
    keep_worklist: bool = False,
) -> ValidateReport:
    """Decide whether the migration of *spec_dir* is finished and, when it is, finish it (see the module text for the order).

    A step that fails stops the run with the report's ``refused`` or ``errors`` set and nothing written.
    """
    spec = os.path.abspath(spec_dir)
    toolkit = os.path.abspath(toolkit_root)
    git = host_root_of(spec, git_root)
    report = ValidateReport()

    stamp = read_stamp(spec) or {}
    recorded, current = stamp.get("toolkit_version"), get_toolkit_version(Path(toolkit))
    if not isinstance(recorded, str) or current is None:
        report.refused = f"{spec}/{STAMP_FILE} records no toolkit_version, or the toolkit version cannot be read from {toolkit}/tools/pyproject.toml"
        return report
    try:
        behind = compare_versions(recorded, current) != 0
    except ValueError:
        behind = True
    if behind:
        report.refused = (
            f"the spec records toolkit v{recorded} and this toolkit is v{current}: the migration has not been run. "
            f"Run `specdev update {spec} --repo-root {toolkit}` first; validate does not stamp a spec that was not migrated"
        )
        return report

    try:
        items = read_worklist(spec, toolkit, git)
    except TriageError as error:
        report.refused = str(error)
        return report
    report.unresolved = len(open_items(items))
    report.blocking = sum(1 for item in open_items(items) if item.blocking)

    try:
        report.errors = run_spec_check(
            toolkit, spec, git_root=git, spec_root=spec, project_canon_dir=project_canon_dir, merge=True, base_ref=base_ref
        )
    except FindingError as error:
        report.refused = error.error.render()
        return report
    if report.failed_errors:
        return report

    _finish(spec, current, stamp, report, keep_worklist)
    return report


def _finish(spec: str, version: str, stamp: dict, report: ValidateReport, keep_worklist: bool) -> None:
    """Clear ``migration_status`` first, then delete the migration files (no item open, ``keep_worklist`` not given).

    The stamp goes first: when its write fails the run stops with the capture and the worklist still in place.
    """
    if stamp.get("migration_status") == STATUS_IN_PROGRESS:
        error = stamp_specdev_version(Path(spec), version, is_migration=True, migration_status=None)
        if error:
            report.refused = error
            return
        report.stamp_finished = True
    else:
        report.notes.append(f"{STAMP_FILE} has no migration_status: in_progress, so the stamp was not rewritten")
    folder = os.path.dirname(os.path.join(spec, WORKLIST_FILE))
    present = [rel for rel in (CAPTURE_FILE, WORKLIST_FILE) if os.path.isfile(os.path.join(spec, rel))]
    if report.unresolved:
        report.kept = f"{len(present)} file(s) of spec/extras/migration/ kept: {report.unresolved} item(s) are not resolved"
    elif keep_worklist:
        if present:
            report.kept = "spec/extras/migration/ kept (--keep-worklist)"
    else:
        for rel in present:
            os.remove(os.path.join(spec, rel))
            report.deleted.append(rel)
        if os.path.isdir(folder) and not os.listdir(folder):
            os.rmdir(folder)
    if not (report.stamp_finished or report.deleted or report.kept):
        report.notes.append("nothing to do: the migration was finished before and no migration file is left")
