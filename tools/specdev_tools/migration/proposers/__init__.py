"""The proposers of the judgement pass: what ``specdev align propose <spec_dir> --kind <kind>`` runs.

A proposer is not a migration script.  It is never run by ``align apply --auto``, is not found by the script registry
(it lives in this package, not in ``migration/scripts/``) and writes no spec file.  It reads the migrated tree (the graph
of the spec folder after the mechanical scripts) and ``capture.json``, and returns one ``Proposal`` per case.  The command
adds the proposals to ``spec/extras/migration/worklist.json`` as items (``migration.worklist``: stable ids, so a rerun adds
none and a closed item stays closed) and prints them.  A person or an agent applies a proposal with the ordinary id-keyed
commands (``specdev json patch --id``, ``specdev node status``).

Each kind is a module of this package with ``propose(tree) -> ProposeResult``; ``_MODULES`` names it.  A later kind adds
one entry to ``KINDS`` and ``_MODULES`` and one module.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specdev_tools.core.changelog_parser import get_toolkit_version
from specdev_tools.core.errors import FindingError
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.model import Graph
from specdev_tools.migration.context import MigrationContext
from specdev_tools.migration.runner import CAPTURE_FILE, read_stamp
from specdev_tools.migration.scripts.v1_2_0.p1_capture import CAPTURE_REL, capture_renames
from specdev_tools.migration.worklist import WorklistError, WorklistItem, add_items
from specdev_tools.migration.writer import DocumentSet, WriterError
from specdev_tools.validation.graph_checks.context import GraphCheckContext

KIND_REFINES = "refines"
KIND_PROSE_IDS = "prose-ids"
KINDS = (KIND_REFINES, KIND_PROSE_IDS)
_MODULES = {KIND_REFINES: "refines", KIND_PROSE_IDS: "prose_ids"}


class ProposeError(Exception):
    """The proposers cannot run on this spec folder: it is not in migration, or its tree or its capture cannot be read."""


@dataclass(frozen=True)
class Proposal:
    """One case: the worklist item for it, its class, the fields ``--json`` prints and the one line the text output prints.

    ``category`` is the class of the case (what the counts are made of); it is also written into the item's proposal text,
    never into its ``kind``, so the id of the item does not change when a rerun classes the case another way.
    """

    item: WorklistItem
    category: str
    data: Mapping[str, Any]
    summary: str


@dataclass(frozen=True)
class ProposeResult:
    """What a proposer found: the proposals in a fixed order, its counts (name to number, in print order) and notes for the reader."""

    kind: str
    proposals: tuple[Proposal, ...]
    counts: Mapping[str, int]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MigratedTree:
    """What a proposer reads: the migration context of the spec folder, its graph and check context, the capture and the renames of phase 2.

    ``renames`` is ``{kind: {old id: new id}}`` from the capture (empty when it has no ``renames`` section).
    """

    ctx: MigrationContext
    graph: Graph
    checks: GraphCheckContext
    capture: Mapping[str, Any]
    renames: Mapping[str, Mapping[str, str]]


@dataclass(frozen=True)
class ProposeOutcome:
    """The result of the command: the proposals, how many items were added to the worklist (``0`` on a dry run) and whether it was a dry run."""

    result: ProposeResult
    added: int
    dry_run: bool

    def render(self) -> str:
        """The text the command prints."""
        counts = ", ".join(f"{number} {name}" for name, number in self.result.counts.items())
        lines = [f"align propose --kind {self.result.kind}: {counts}"]
        lines.extend(f"  {proposal.summary}" for proposal in self.result.proposals)
        lines.extend(f"note: {note}" for note in self.result.notes)
        if self.dry_run:
            lines.append("dry run: nothing was added to the worklist")
        else:
            listed = len(self.result.proposals) - self.added
            lines.append(f"worklist: {self.added} item(s) added, {listed} already listed")
        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        """The ``--json`` output: the envelope of the other ``align`` actions plus the kind, the counts, the proposals and the number added."""
        return {
            "status": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "command": "align",
            "action": "propose",
            "errors": [],
            "kind": self.result.kind,
            "dry_run": self.dry_run,
            "counts": dict(self.result.counts),
            "added": self.added,
            "notes": list(self.result.notes),
            "proposals": [{"worklist_id": proposal.item.id, "class": proposal.category, **proposal.data} for proposal in self.result.proposals],
        }


def load_tree(ctx: MigrationContext) -> MigratedTree:
    """The tree of the spec folder of *ctx* as a proposer reads it.

    Raises:
        ProposeError: the toolkit registry or the capture cannot be read, or a spec file is unreadable.
    """
    try:
        graph = build_graph(ctx.spec_root, ctx.toolkit_root)
        checks = GraphCheckContext.from_graph(graph, None, ctx.toolkit_root, git_root=ctx.git_root, spec_root=ctx.spec_root)
        capture = ctx.documents.load(CAPTURE_REL).data
    except (FindingError, WriterError) as error:
        raise ProposeError(str(getattr(error, "error", error))) from None
    if graph.load_errors:
        raise ProposeError("; ".join(f"{found.file}: {found.message}" for found in graph.load_errors))
    return MigratedTree(ctx, graph, checks, capture, capture_renames(ctx))


def _context(spec_dir: Path, toolkit_root: Path, git_root: Path | None) -> MigrationContext:
    if not os.path.isfile(spec_dir / CAPTURE_FILE):
        raise ProposeError(
            f"{spec_dir} is not in migration: it has no {CAPTURE_FILE}; run `specdev align apply --auto` first "
            "(the proposers read what the mechanical scripts left)"
        )
    stamp = read_stamp(str(spec_dir)) or {}
    host_root = str(git_root or spec_dir.parent)
    version = get_toolkit_version(toolkit_root) or ""
    return MigrationContext(str(spec_dir), host_root, host_root, str(toolkit_root), False, DocumentSet(str(spec_dir)), str(stamp.get("toolkit_version", "")), version)


def propose(spec_dir: Path, *, kind: str, toolkit_root: Path, git_root: Path | None, dry_run: bool) -> ProposeOutcome:
    """Run the proposer *kind* on *spec_dir* and add its items to the worklist (unless *dry_run*); the only file written is ``extras/migration/worklist.json``.

    Raises:
        ProposeError: the folder is not in migration, the tree cannot be read, or the worklist is not a worklist.
    """
    ctx = _context(spec_dir, toolkit_root, git_root)
    tree = load_tree(ctx)
    result = importlib.import_module(f"{__name__}.{_MODULES[kind]}").propose(tree)
    items = [proposal.item for proposal in result.proposals]
    try:
        added = 0 if dry_run else add_items(ctx, items)
        ctx.documents.write()
    except (WorklistError, WriterError) as error:
        raise ProposeError(str(error)) from None
    return ProposeOutcome(result, added, dry_run)
