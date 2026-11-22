"""``specdev align bind-legacy``: the pass that turns the legacy commands of a migrated host into verifier bindings.

``align propose --kind bindings`` classes every fixture and adds worklist items; this driver is what acts on the ``certain``
groups.  It is not a migration script and not a phase: ``align apply --auto`` never runs it, because it writes a record a
person confirmed, and a command must not be run or recorded by the mechanical pass.

For each ``certain`` group it prints the exact ``specdev verify bind`` lines.  When a person confirms (the prompt, or
``--yes``), it writes one binding per line through ``verify.bind.apply_bind``, the function ``specdev verify bind`` calls, so
every check of that command applies and a line it would refuse is refused with the same code.  There is no second writer
and no relaxed path.  Nothing else is written except the worklist: an item whose case is settled (a group whose lines are
all bound, a fixture that is bound or ``manual`` now) is closed with a note.

A binding written here proves nothing by itself.  The fixture is proven only when ``specdev verify run`` has run its command
on the migrated tree and the guard matched: until then the node reads ``NO_EVIDENCE``.  ``--summary`` counts where the host
stands (bindings, fixtures covered, fixtures made ``manual`` and attested, fixtures still open: it must be zero before the
host's first release).  A fixture without a binding is no merge-time error: the merge check runs the bindings that exist.
"""

from __future__ import annotations

import shlex
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specdev_tools.core.errors import FindingError
from specdev_tools.graph.contract import item_of
from specdev_tools.graph.model import NOT_APPLICABLE, Graph
from specdev_tools.graph.names import BINDING_KIND, FIXTURE, MANUAL_MODE
from specdev_tools.migration.proposers import MigratedTree, ProposeError, context_of, load_tree
from specdev_tools.migration.proposers.bindings import (
    CERTAIN,
    KIND_FIXTURE,
    KIND_GROUP,
    BindGroup,
    BindLine,
    BindingsPlan,
    bind_line,
    group_item_id,
    is_covered,
    plan_bindings,
)
from specdev_tools.migration.triage import TriageError, resolve_item
from specdev_tools.migration.worklist import WorklistError, read_items
from specdev_tools.migration.writer import WriterError
from specdev_tools.trace.records import RECORDS_DIR
from specdev_tools.trace.writing import locked_graph
from specdev_tools.verify.bind import apply_bind
from specdev_tools.verify.records import attestations_about, binding_of

Answer = Callable[[BindGroup], bool]
"""What the command asks a person: ``True`` writes the group's lines.  ``None`` stands for nobody to ask (nothing is written)."""

CLOSED_BY_BINDING = "every `verify bind` line of the group exists (align bind-legacy)"
CLOSED_BY_MANUAL = "the fixture is bound or manual now (align bind-legacy); a manual fixture is attested with `specdev verify attest`"
NEXT_STEP = "run `specdev verify run <binding-id>` for each binding: a binding proves nothing until a run matched its guard"


@dataclass(frozen=True)
class Written:
    """A binding written: the fixture, the record id, its stage, the nodes it proves and its file under ``extras/verification``."""

    fixture: str
    record_id: str
    stage: str
    proves: tuple[str, ...]
    file: str


@dataclass(frozen=True)
class Refused:
    """A line ``verify bind`` would refuse: the fixture, the line, the code and the message it gives."""

    fixture: str
    line: str
    code: str
    message: str


@dataclass(frozen=True)
class GroupResult:
    """What happened to one ``certain`` group: its pending lines, whether a person was asked and the answer."""

    group: BindGroup
    pending: tuple[tuple[str, BindLine], ...]
    answered: bool | None


@dataclass(frozen=True)
class PassOutcome:
    """The result of ``bind-legacy``: what was offered, written and refused, the items closed and the groups left for a person."""

    offered: tuple[GroupResult, ...]
    written: tuple[Written, ...]
    refused: tuple[Refused, ...]
    closed: tuple[str, ...]
    left: tuple[BindGroup, ...]
    root_flags: tuple[str, ...]
    dry_run: bool

    def render(self) -> str:
        """The text the command prints: each offered group with its exact lines, then what was written, refused and closed."""
        lines = [f"align bind-legacy: {len(self.offered)} certain group(s) offered, {len(self.written)} binding(s) written, {len(self.refused)} refused, {len(self.left)} group(s) left for a person"]
        for result in self.offered:
            group = result.group
            lines.append(f"certain  {' && '.join(group.commands)}  ({len(group.members)} fixture(s))")
            lines.extend(f"  {bind_line(line.request, self.root_flags)}" for _fixture, line in result.pending)
            lines.append(f"  {_verdict(result.answered, self.dry_run)}")
        lines.extend(f"written  {w.fixture}: binding {w.record_id} (stage {w.stage}, {RECORDS_DIR}/{w.file})" for w in self.written)
        lines.extend(f"refused  {r.fixture}: {r.code} {r.message}" for r in self.refused)
        lines.extend(f"closed   {item}" for item in self.closed)
        lines.extend(f"left     {' && '.join(group.commands)} ({group.category}: see `specdev align triage --step 08`)" for group in self.left)
        if self.written:
            lines.append(NEXT_STEP)
        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        """The ``--json`` output: the envelope of the other ``align`` actions plus what was offered, written, refused and closed."""
        return {
            "status": "FAIL" if self.refused else "PASS",
            "error_count": len(self.refused),
            "warning_count": 0,
            "command": "align",
            "action": "bind-legacy",
            "errors": [{"code": r.code, "message": f"{r.fixture}: {r.message}", "severity": "error"} for r in self.refused],
            "dry_run": self.dry_run,
            "offered": [
                {"commands": list(r.group.commands), "guard": r.group.guard, "answered": r.answered, "lines": [bind_line(line.request, self.root_flags) for _fixture, line in r.pending]} for r in self.offered
            ],
            "written": [{"fixture": w.fixture, "record_id": w.record_id, "stage": w.stage, "proves": list(w.proves), "file": f"{RECORDS_DIR}/{w.file}"} for w in self.written],
            "closed": list(self.closed),
            "left": [{"commands": list(group.commands), "category": group.category} for group in self.left],
        }


def _verdict(answered: bool | None, dry_run: bool) -> str:
    if dry_run:
        return "dry run: nothing asked, nothing written"
    if answered is None:
        return "not written: no person answered (run the lines yourself, or run the command at a terminal or with --yes)"
    return "confirmed" if answered else "declined: nothing written"


def _write(spec_root: str, toolkit_root: str, fixture: str, line: BindLine, flags: tuple[str, ...]) -> Written | Refused:
    """Write one line through ``apply_bind`` under its own lock and graph (a second line of the same verifier must see the first)."""
    try:
        with locked_graph(spec_root, toolkit_root, "align bind-legacy") as graph:
            result = apply_bind(graph, spec_root, toolkit_root, line.request)
    except FindingError as error:
        return Refused(fixture, bind_line(line.request, flags), error.error.code, error.error.message)
    plan = result.plan
    return Written(fixture, plan.record_id, plan.stage, plan.proves, result.file)


def _pending(group: BindGroup) -> tuple[tuple[str, BindLine], ...]:
    return tuple((member.fixture, line) for member in group.members for line in member.lines if not line.present)


def _settled(tree: MigratedTree, plan: BindingsPlan) -> list[tuple[str, str]]:
    """``(item id, closing note)`` of the open worklist items of kinds ``legacy-binding`` and ``legacy-fixture`` whose case is settled in *tree*."""
    complete = {group_item_id(group) for group in plan.groups if group.complete}
    graph = tree.graph
    settled = []
    for item in read_items(tree.ctx):
        if item.resolved:
            continue
        node = graph.find(item.about) if item.kind == KIND_FIXTURE else None
        if item.kind == KIND_GROUP and item.id in complete:
            settled.append((item.id, CLOSED_BY_BINDING))
        elif node is not None and ((item_of(graph, node) or {}).get("mode") == MANUAL_MODE or is_covered(node, graph)):
            settled.append((item.id, CLOSED_BY_MANUAL))
    return settled


def _close(spec_dir: Path, toolkit_root: Path, git_root: Path | None, tree: MigratedTree) -> tuple[str, ...]:
    closed = []
    for item_id, note in _settled(tree, plan_bindings(tree)):
        resolve_item(spec_dir, toolkit_root, item_id, note, git_root)
        closed.append(item_id)
    return tuple(closed)


def root_flags(spec_dir: Path, toolkit_root: Path, git_root: Path | None) -> tuple[str, ...]:
    """The root flags (quoted words) that make a printed ``verify bind`` line run against this host from any folder."""
    flags = ["--repo-root", shlex.quote(str(toolkit_root)), "--spec-root", shlex.quote(str(spec_dir))]
    return tuple(flags + ["--git-root", shlex.quote(str(git_root))] if git_root else flags)


def run_pass(spec_dir: Path, *, toolkit_root: Path, git_root: Path | None, answer: Answer | None, dry_run: bool) -> PassOutcome:
    """Offer the ``certain`` groups, write the lines of those a person confirms and close the items whose case is settled.

    *answer* is asked once per group with lines still to bind; ``None`` means nobody can answer and nothing is written.  With
    *dry_run* nobody is asked and nothing, not even the worklist, is written.

    Raises:
        ProposeError: the folder is not in migration, its tree cannot be read, or the worklist is not a worklist.
    """
    flags = root_flags(spec_dir, toolkit_root, git_root)
    tree = load_tree(context_of(spec_dir, toolkit_root, git_root))
    plan = plan_bindings(tree)
    offered: list[GroupResult] = []
    written: list[Written] = []
    refused: list[Refused] = []
    for group in (g for g in plan.groups if g.category == CERTAIN and _pending(g)):
        confirmed = None if dry_run or answer is None else answer(group)
        offered.append(GroupResult(group, _pending(group), confirmed))
        if confirmed:
            outcomes = [_write(tree.ctx.spec_root, str(toolkit_root), fixture, line, flags) for fixture, line in _pending(group)]
            written += [o for o in outcomes if isinstance(o, Written)]
            refused += [o for o in outcomes if isinstance(o, Refused)]
    closed: tuple[str, ...] = ()
    if not dry_run:
        try:
            after = load_tree(context_of(spec_dir, toolkit_root, git_root)) if written else tree
            closed = _close(spec_dir, toolkit_root, git_root, after)
        except (TriageError, WorklistError, WriterError) as error:
            raise ProposeError(str(error)) from None
    left = tuple(group for group in plan.groups if group.category != CERTAIN and not group.complete)
    return PassOutcome(tuple(offered), tuple(written), tuple(refused), closed, left, flags, dry_run)


@dataclass(frozen=True)
class Summary:
    """Where the host stands: the bindings of fixtures, the fixtures they cover, the manual fixtures and which of them are attested, and what is still open."""

    bindings: int
    covered: tuple[str, ...]
    manual: tuple[str, ...]
    attested: tuple[str, ...]
    unbound: tuple[str, ...]
    unattested: tuple[str, ...]

    @property
    def open(self) -> int:
        """Fixtures with neither a binding nor an attestation: must be 0 before the host's first release."""
        return len(self.unbound) + len(self.unattested)

    def render(self) -> str:
        """The text of ``--summary``."""
        lines = [
            f"bindings written: {self.bindings}",
            f"fixtures covered by a binding: {len(self.covered)}",
            f"fixtures made manual: {len(self.manual)} ({len(self.attested)} attested)",
            f"fixtures still without a binding or attestation: {self.open} (must be 0 before the first release)",
        ]
        lines.extend(f"  no binding: {fixture}" for fixture in self.unbound)
        lines.extend(f"  manual, not attested: {fixture}" for fixture in self.unattested)
        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        """The ``--json`` output of ``--summary``."""
        return {
            "status": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "command": "align",
            "action": "bind-legacy",
            "errors": [],
            "bindings": self.bindings,
            "covered": list(self.covered),
            "manual": list(self.manual),
            "attested": list(self.attested),
            "unbound": list(self.unbound),
            "unattested": list(self.unattested),
            "open": self.open,
        }


def summarise(graph: Graph) -> Summary:
    """The summary of *graph*: a binding counts when its verifier is a fixture; ``not_applicable`` fixtures are left out."""
    fixtures = [node for node in sorted(graph.by_kind.get(FIXTURE, ()), key=lambda node: node.id) if node.lifecycle != NOT_APPLICABLE]
    manual = [node.id for node in fixtures if (item_of(graph, node) or {}).get("mode") == MANUAL_MODE]
    bindings = sum(1 for node in graph.by_kind.get(BINDING_KIND, ()) if (found := graph.find(binding_of(node, graph).verifier)) is not None and found.kind == FIXTURE)
    covered = [node.id for node in fixtures if node.id not in manual and is_covered(node, graph)]
    attested = [fixture for fixture in manual if attestations_about(graph, fixture)]
    return Summary(
        bindings,
        tuple(covered),
        tuple(manual),
        tuple(attested),
        tuple(node.id for node in fixtures if node.id not in manual and node.id not in covered),
        tuple(fixture for fixture in manual if fixture not in attested),
    )


def summary_of(spec_dir: Path, *, toolkit_root: Path, git_root: Path | None) -> Summary:
    """The summary of the spec folder *spec_dir* (read-only).

    Raises:
        ProposeError: the folder is not in migration or its tree cannot be read.
    """
    return summarise(load_tree(context_of(spec_dir, toolkit_root, git_root)).graph)
