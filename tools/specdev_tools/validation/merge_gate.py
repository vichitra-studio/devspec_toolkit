"""The merge gate: the checks ``spec-check --merge`` adds to the plain run.

Merge mode is explicit (``--merge``); it is not inferred from git state.  ``run_merge_checks`` returns three checks,
appended by ``spec_check.run_checks`` after the registered ones (they are not registered: a registered check would be a
line of every plain run):

* ``merge-open-items``: open items are errors (E631); an item in the plan of a closed milestone is listed (W633).
* ``merge-pins``: a third-party pin that differs from the file that declares its source (E336 to E338).
* ``merge-bindings``: the dev- and CI-stage bindings of every milestone this branch closes run in this run and must
  pass (E901).  Nothing is stored: the run is the proof.

Suspect links and orphan lock entries (E763, E762) are not here: the registered ``trace-lock`` check reports them in
every mode.  The module must not import ``spec_check``, which imports it.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from ..core.errors import FindingError, SpecError, make_error, refusal
from ..core.git_base import resolve_baseline
from ..graph.gitview import GitViewError, resolve_ref
from ..graph.model import Graph
from ..graph.names import ROW_DONE
from ..lifecycle.anchor_store import AnchorState, is_legacy_close, read_statuses
from ..thirdparty.check import check_pins
from ..trace.lockfile import MERGE_CHECK_OWNER
from ..verify.code_tree import declarations_of
from ..verify.records import records_folder
from ..verify.run import run_bindings, selected_ids
from .check_registry import CheckContext, check_result, skip, with_default_owner
from .open_items import check_open_items

MERGE_OPEN_ITEMS = "merge-open-items"
MERGE_PINS = "merge-pins"
MERGE_BINDINGS = "merge-bindings"

_FULL_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_BINDING_STAGE = "ci"
_NO_GRAPH = "no spec graph"


@dataclass(frozen=True)
class MergeBase:
    """Where "closed by this branch" is measured from.

    ``commit`` is the base commit id; ``None`` for a root commit, where nothing existed at the base (the empty tree is not
    a commit, so no reader is asked to look at it).  ``ref`` names what the base was taken from; ``note`` is one line
    on a fallback that was used.
    """

    ref: str | None
    commit: str | None
    note: str | None = None


def _is_commit(ref: str, git_root: str) -> bool:
    try:
        resolve_ref(ref, git_root)
    except GitViewError:
        return False
    return True


def _first_parent(git_root: str, why: str) -> MergeBase:
    """The base for a flag that names no commit here: the first parent of HEAD, or none on a root commit."""
    if _is_commit("HEAD^1", git_root):
        return MergeBase("HEAD^1", resolve_ref("HEAD^1", git_root), f"{why}; the base is the first parent of HEAD")
    return MergeBase(None, None, f"{why}; HEAD has no parent, so nothing existed at the base")


def resolve_merge_base(flag: str | None, git_root: str) -> MergeBase:
    """The base of the merge gate.

    One chain, the shipped one (``core.git_base.resolve_baseline``): *flag* (``--base-ref``), ``SPECDEV_REPLAY_BASE_REF``,
    the ``origin/HEAD`` symbolic ref, the first existing default branch, then its merge-base with HEAD.  A *flag* that
    is a full commit id which this clone does not have (the all-zero id of a first push, a force-pushed ``before``, a
    shallow clone) falls back to the first parent of HEAD; on a root commit the result has ``commit = None``.

    Raises:
        FindingError: E900 when git cannot answer (not a repository, no commit yet, git missing) or when no base can be
            named: a flag that is no ref, no default branch found, no common history.
    """
    try:
        resolve_ref("HEAD", git_root)
    except GitViewError as error:
        raise refusal("E900", f"the merge base cannot be resolved: {error.error.message}") from error
    if flag is not None and _FULL_SHA.fullmatch(flag) and not _is_commit(flag, git_root):
        return _first_parent(git_root, f"the base ref {flag} names no commit in this clone")
    resolution = resolve_baseline(git_root, flag)
    if resolution.commit is None:
        raise refusal("E900", f"the merge base cannot be resolved: {resolution.note}")
    return MergeBase(resolution.ref, resolution.commit, resolution.note)


def closed_by_branch(head: dict[str, AnchorState], base: dict[str, AnchorState]) -> list[str]:
    """The milestones whose anchor status is ``done`` in *head* and not in *base*, in anchor order.

    A milestone with no row in *base* counts as not done.  A milestone whose close record is the migration's
    (``legacy-migration``) is left out: migration records closes that happened before this branch.
    """
    return [
        milestone
        for milestone, state in head.items()
        if state.status == ROW_DONE
        and (milestone not in base or base[milestone].status != ROW_DONE)
        and not is_legacy_close(state.close)
    ]


def _open_items_check(ctx: CheckContext) -> dict[str, Any]:
    return check_result(check_open_items(ctx.spec_dir, gate="merge", frozen=ctx.is_frozen_plan, read=ctx.ambiguity_read))


def _pins_check(ctx: CheckContext) -> dict[str, Any]:
    if ctx.check_graph is None:
        return skip(_NO_GRAPH)
    return check_result(check_pins(ctx.check_graph, declarations_of(ctx.effective_spec_root), ctx.project_root))


def _base_statuses(ctx: CheckContext, base: MergeBase) -> dict[str, AnchorState]:
    if base.commit is None:
        return {}
    return read_statuses(ctx.effective_spec_root, git_ref=base.commit, git_root=ctx.git_root)


def _binding_ids(graph: Graph, milestones: list[str]) -> dict[str, str]:
    """``{binding id: the first closed milestone that names it}`` for the dev and CI bindings of *milestones*."""
    owners: dict[str, str] = {}
    for milestone in milestones:
        for binding_id in selected_ids(graph, every=False, milestone=milestone, stage=_BINDING_STAGE, only_stage=False):
            owners.setdefault(binding_id, milestone)
    return owners


def _failed_binding(binding_id: str, milestone: str, exit_code: int, guard_matched: bool) -> SpecError:
    guard = "matched" if guard_matched else "did not match"
    return make_error(
        "E901",
        f"binding '{binding_id}' of {milestone}, which this branch closes, failed in this run: exit code {exit_code}, "
        f"its guard {guard} the output; make the bound command pass or change the binding",
        node_id=binding_id,
    )


def _bindings_check(ctx: CheckContext, base_ref: str | None) -> dict[str, Any]:
    if ctx.check_graph is None:
        return skip(_NO_GRAPH)
    spec_root = ctx.effective_spec_root
    base = resolve_merge_base(base_ref, ctx.project_root)
    closed = closed_by_branch(read_statuses(spec_root), _base_statuses(ctx, base))
    owners = _binding_ids(ctx.check_graph, closed)
    if not owners:
        return skip("this branch closes no milestone with a dev or CI binding")
    evidence = run_bindings(
        list(owners), ctx.spec_dir, records_folder(spec_root), ctx.project_root, record=False,
        stage=_BINDING_STAGE, only_stage=False, repo_root=ctx.repo_root, graph=ctx.check_graph,
    )
    return check_result([
        _failed_binding(item.about[0], owners[item.about[0]], item.exit_code, item.guard_matched)
        for item in evidence
        if not item.passed
    ])


def run_merge_checks(ctx: CheckContext, base_ref: str | None) -> OrderedDict[str, dict[str, Any]]:
    """The three merge checks, in order, as ``spec-check`` results by name; owners are stamped like the registered checks'.

    A ``FindingError`` of one check (E520 for an unreadable declarations file or a seed document, E706, E332, E708, E801,
    E900) is that check's one finding; the other checks still run.
    """
    merge_checks: tuple[tuple[str, Callable[[CheckContext], dict[str, Any]]], ...] = (
        (MERGE_OPEN_ITEMS, _open_items_check),
        (MERGE_PINS, _pins_check),
        (MERGE_BINDINGS, partial(_bindings_check, base_ref=base_ref)),
    )
    checks: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, check in merge_checks:
        try:
            result = check(ctx)
        except FindingError as exc:
            result = check_result([exc.error])
        checks[name] = with_default_owner(result, MERGE_CHECK_OWNER, ctx.owner_context)
    return checks
