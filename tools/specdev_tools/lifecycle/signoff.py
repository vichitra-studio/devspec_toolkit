"""``specdev milestone sign-off``: record that a person signed a milestone off against one code tree.

The record is ``extras/signoff/so-<milestone>-<NNNN>.json`` (schema ``vc:extras:signoff-record``): the milestone, the code tree
now, the git author, the time and what was listed to the person (the counts and ids of ``status --milestone``).  Several
sign-offs per milestone are allowed and each gets the number after the highest existing one.  Nothing checks who runs the command, whether the tree is the
current one or whether the verdict is ``verified``: the record carries the tree and the author, ``milestone close`` prints the
sign-off tree next to the tree it closes at, and the ask rule of the host is the operator's approval.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from ..graph.names import ROW_IN_PROGRESS
from ..trace.lockfile import Lock
from ..trace.records import SIGNOFF_DIR
from ..trace.writing import locked_graph
from ..verify.records import signoff_records, write_signoff
from . import executed, plans
from .milestone import ProviderFactory, milestone_id_of, refuse_not_in_progress, require_row
from .records import git_author, mint_id, now_utc
from .status import MilestoneView, milestone_view, status_context



@dataclass(frozen=True)
class SignoffResult:
    """What ``milestone sign-off`` did: the record, its file (relative to the spec folder) and the view the person was shown."""

    record: dict[str, Any]
    file: str
    view: MilestoneView


def _listed(view: MilestoneView) -> dict[str, Any]:
    """The ``listed`` object of the record: what the person was shown, counted as the view counts it."""
    return {
        "manual_fixtures": len(view.manual),
        "attested": view.manual_attested,
        "deferred_tasks": [t.task_id for t in view.paused if t.disposition == "deferred"],
        "wont_do_tasks": [t.task_id for t in view.paused if t.disposition == "wont_do"],
        "open_items": len(view.open_items),
        "staging_prod_proof_owed": list(view.proof_owed_later),
    }


def sign_off(spec_root: str, repo_root: str, git_root: str, given: str, providers: ProviderFactory) -> SignoffResult:
    """Record a sign-off of the milestone *given* (``in_progress``, with a plan) and return the record and the view shown with it.

    Raises:
        FindingError: E801 when the row is not ``in_progress``; E800 (``ANCHOR_ROW_MISSING``) without a row; E803 when no plan
            names the milestone or *given* is a batch id; E767 when git names no author; E774 when the record breaks its schema.
    """
    with locked_graph(spec_root, repo_root, "milestone sign-off") as graph:
        milestone_id = milestone_id_of(graph, spec_root, given)
        row = require_row(spec_root, milestone_id)
        if row.status != ROW_IN_PROGRESS:
            raise refuse_not_in_progress(milestone_id, row.status, "signed off")
        plans.require_plan(spec_root, milestone_id)
        author = git_author(git_root)
        lock: Lock | None = executed.lock_if_present(spec_root)
        view = milestone_view(status_context(spec_root, repo_root, git_root, lock, graph, providers), milestone_id)
        signoff_id = mint_id(f"so-{milestone_id}", [r.signoff_id for r in signoff_records(spec_root, milestone_id)])
        record = {
            "signoff_id": signoff_id, "about": [milestone_id], "tree": view.tree, "git_author": author.as_record(),
            "recorded_at": now_utc(), "listed": _listed(view),
        }
        file = f"{SIGNOFF_DIR}/{write_signoff(os.path.join(spec_root, SIGNOFF_DIR), repo_root, record)}"
    return SignoffResult(record, file, view)
