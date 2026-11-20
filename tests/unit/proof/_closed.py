"""Builders of closed milestones on the worked example: closing one, accepting links into the lock, adding milestones, fixtures and removals."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from specdev_tools.graph.model import Graph
from specdev_tools.proof.realisation import Realisation, UnresolvedRealisation, realisation_status, unresolved_realisations
from specdev_tools.trace.lockfile import Lock, read_lock, write_lock
from unit.trace._lock_support import lock_for
from unit.verify._support import edit_doc, example_host, graph_of

from ._support import add_fixture

MILESTONE = "ms-account-recovery"
FR, CRITERION, API, INVARIANT = "fr-password-reset", "ac-password-reset-3", "api-password-reset-confirm", "inv-reset-token-single-use"
TASK_CRITERION = "tc-confirm-expired-token"
ROADMAP, ANCHORS, FIXTURES, FR_LIST = "14_roadmap.json", "16_impl_context.json", "08_fixtures.json", "04_fr_list.json"


def _seed_texts(host: Path) -> dict[str, str]:
    from specdev_tools.graph.gitview import read_seed_texts

    return read_seed_texts(graph_of(host), str(host))


def closed_example(tmp_path: Path, name: str = "host") -> Path:
    """The worked example with its milestone closed (anchor status ``done``); the lock is the example's, which accepted every link as it is."""
    host = example_host(tmp_path, name)
    set_status(host, MILESTONE, "done")
    return host


def set_status(host: Path, milestone: str, status: str) -> None:
    """Set the status of the anchor row about *milestone*."""
    def edit(doc: dict[str, Any]) -> None:
        for row in doc["plan"]["milestone_index"]:
            if milestone in row["about"]:
                row["status"] = status

    edit_doc(host, ANCHORS, edit)


def accept(host: Path, *holders: str) -> None:
    """Write into the lock the links of *holders* as they are now (all holders when none are named); entries of other holders stay."""
    graph = graph_of(host)
    spec = str(host / "spec")
    fresh = lock_for(graph, host, only_holders=holders or None)
    kept = [entry for entry in read_lock(spec).entries if holders and entry.source not in holders]
    write_lock(spec, Lock((*kept, *fresh.entries)))


def add_milestone(host: Path, milestone: str, criteria: Iterable[dict[str, Any]], *, done: bool) -> list[str]:
    """Add a milestone with one task holding *criteria* and its anchor row; the links of its criteria are accepted into the lock. Returns the criterion ids."""
    criteria = list(criteria)
    task = {"task_id": f"task-{milestone}", "description": "Carry out the work of this milestone.", "acceptance_criteria": criteria}
    entry = {"milestone_id": milestone, "name": milestone, "target_date": "2027-01-15", "user_story": "As a member, I want the work done, so that I can use it.", "tasks": [task]}
    edit_doc(host, ROADMAP, lambda doc: doc["milestones"].append(entry))
    row = {"anchor_id": f"anchor-{milestone}", "about": [milestone], "status": "done" if done else "in_progress", "checklist_id_prefix": milestone[3:9].upper(), "summary": "The work of this milestone is done." if done else "The work of this milestone is open."}
    edit_doc(host, ANCHORS, lambda doc: doc["plan"]["milestone_index"].append(row))
    ids = [criterion["criterion_id"] for criterion in criteria]
    accept(host, *ids)
    return ids


def criterion(criterion_id: str, **fields: Any) -> dict[str, Any]:
    """A task criterion with a sentence of text and *fields* (``refines``, ``removes``, ``verified_by``)."""
    return {"criterion_id": criterion_id, "text": "The work this criterion names is done and its verifier shows it.", **fields}


def delete_criterion(host: Path, criterion_id: str) -> None:
    """Delete the acceptance criterion *criterion_id* from the FR list."""
    def edit(doc: dict[str, Any]) -> None:
        for fr in doc["functional_requirements"]:
            fr["acceptance_criteria"] = [c for c in fr["acceptance_criteria"] if c["criterion_id"] != criterion_id]

    edit_doc(host, FR_LIST, edit)


def reword_criterion(host: Path, criterion_id: str, text: str) -> None:
    """Change the text of the acceptance criterion *criterion_id*."""
    def edit(doc: dict[str, Any]) -> None:
        for fr in doc["functional_requirements"]:
            for c in fr["acceptance_criteria"]:
                if c["criterion_id"] == criterion_id:
                    c["text"] = text

    edit_doc(host, FR_LIST, edit)


def delete_fr(host: Path, fr_id: str) -> None:
    """Delete the functional requirement *fr_id* and its criteria."""
    edit_doc(host, FR_LIST, lambda doc: doc["functional_requirements"].__setitem__(slice(None), [fr for fr in doc["functional_requirements"] if fr["fr_id"] != fr_id]))


def statuses(host: Path) -> dict[tuple[str, str], str]:
    """``(criterion, target) -> state`` of every realisation of *host*, with the lock on disk."""
    return {(row.criterion, row.target): row.state for row in rows(host)}


def rows(host: Path) -> list[Realisation]:
    graph: Graph = graph_of(host)
    return realisation_status(graph, read_lock(str(host / "spec")), _seed_texts(host))


def unresolved(host: Path) -> list[UnresolvedRealisation]:
    return unresolved_realisations(graph_of(host), read_lock(str(host / "spec")), _seed_texts(host))


def with_removal(host: Path, *, removes: list[str], milestone: str = "ms-retire-reset", done: bool = True, fixture_removes: list[str] | None = None) -> None:
    """Add a removal fixture and a milestone whose criterion removes *removes* and lists that fixture."""
    add_fixture(host, fixture_id="fix-reset-gone", removes=fixture_removes if fixture_removes is not None else removes)
    add_milestone(host, milestone, [criterion("tc-retire-reset", removes=removes, verified_by=["fix-reset-gone"])], done=done)


Edit = Callable[[dict[str, Any]], None]
