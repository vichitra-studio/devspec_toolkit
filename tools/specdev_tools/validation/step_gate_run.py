"""The run of the step gate: which steps to gate, every check once, the baseline once, and the notes for stderr.

``run_step_gate`` runs the registered checks (``validation.check_registry``) once on the working tree, measures the
baseline once, and sorts the findings by the step that owns them (``validation.step_gate``).  ``gate_run`` is what
``spec-check --step`` and ``--paths`` do before they print: it takes steps or touched paths and returns the run, with the
notes the caller prints in the order it prints them, the empty run included.  ``gate_usage_error`` says which
flag combinations ``spec-check`` refuses.  Nothing here prints.
"""
from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ..core.config import reset_config
from ..core.errors import FindingError, SpecError, make_error
from ..core.git_base import BaselineChecks, BaselineProvider, BaselineResult, SeedPaths, merge_base_provider
from ..core.loaders import read_json_object
from ..graph.build import build_graph, step_order_ranks
from ..graph.gitview import host_root_of
from ..graph.kinds import SEED_KIND
from ..graph.model import Graph
from ..graph.queries import require_known_step_in
from .check_registry import CheckContext, run_registered_checks
from .spec_check import check_findings, run_checks, warn_ignored_promotions
from .step_gate import StepGateResult, WaitingOn, classify_for_steps, declared_owner, same_id
from .touched_steps import (
    SEED_EDIT_NOTE,
    SEED_MANIFEST_FILE,
    TouchedSteps,
    outside_root_note,
    steps_for_paths,
    steps_without_artifact,
)

NO_STEP_NOTE = "no step gated: no listed path maps to a step"
FORWARD_REPLAY_USAGE = (
    "spec-check: --include-forward-replay cannot be combined with --step or --paths (id regressions are suspects there)"
)
GATE_ONLY_USAGE = "spec-check: --base-ref and --detail apply only with --step or --paths"
EMPTY_BASE_REF_USAGE = "spec-check: --base-ref needs a ref name, not an empty one"


@dataclass(frozen=True)
class StepGateRun:
    """The outcome of ``run_step_gate``: one result per gated step, the baseline "new" was measured against, and the stderr notes.

    ``notes`` are lines the caller prints on stderr, in order (what the touched paths mapped to, files the graph could
    not read, why a baseline is ``unavailable``, a baseline that is HEAD itself).
    """

    results: tuple[StepGateResult, ...]
    baseline: BaselineResult
    notes: tuple[str, ...] = ()


def gate_usage_error(
    *, steps: Sequence[str] | None, paths: Sequence[str] | None, include_forward_replay: bool, base_ref: str | None, detail: str | None
) -> str | None:
    """The usage error for a flag combination of ``spec-check`` that the step gate refuses, or ``None``.

    ``--step`` and ``--paths`` (*steps*, *paths*) start the gate; ``--include-forward-replay`` cannot be combined with
    them, ``--base-ref`` and ``--detail`` need them, and ``--base-ref`` names a ref.
    """
    gating = steps is not None or paths is not None
    if gating and include_forward_replay:
        return FORWARD_REPLAY_USAGE
    if not gating and (base_ref is not None or detail is not None):
        return GATE_ONLY_USAGE
    if base_ref == "":
        return EMPTY_BASE_REF_USAGE
    return None


def _touched_steps_of(
    repo_root: str,
    spec_dir: str,
    paths: Sequence[str],
    ranks: Mapping[str, int],
    git_root: str | None = None,
    spec_root: str | None = None,
) -> TouchedSteps:
    """The steps the touched *paths* (``--paths``) put under the gate; see ``validation.touched_steps``.

    Reads the seed manifest of *spec_dir* (none is an empty manifest) and builds the graph of the spec root only when a
    listed seed document is among the paths.  *ranks* is the step order (``step_order_ranks``).

    Raises:
        FindingError: E708 when the spec folder is outside the host root.
    """
    manifest = read_json_object(os.path.join(spec_dir, SEED_MANIFEST_FILE)) or {}
    return steps_for_paths(
        paths, spec_dir, manifest, lambda: build_graph(spec_root or spec_dir, repo_root),
        step_order=list(ranks), git_root=git_root,
    )


def _baseline_checks(repo_root: str, *, with_project_canon: bool) -> BaselineChecks:
    """The check runner of the baseline provider: all checks on a materialised tree, quiet, with that tree as git root and spec root.

    The baseline run takes the project canon of its own tree (``<spec>/canon``) exactly when the current run has one
    (*with_project_canon*), so both runs read the same kind of canon.
    """

    def compute(baseline_root: Path, baseline_spec_dir: Path) -> list[SpecError]:
        spec = str(baseline_spec_dir)
        canon = os.path.join(spec, "canon")
        checks = run_checks(
            repo_root, spec, git_root=str(baseline_root), spec_root=spec,
            project_canon_dir=canon if with_project_canon and os.path.isdir(canon) else None, quiet=True,
        )
        return check_findings(checks)

    return compute


def _seed_paths_of(graph: Graph | None) -> SeedPaths:
    """The seed documents of *graph* (paths relative to the host root), as the baseline provider asks for them."""
    paths = sorted({node.file for node in graph.nodes if node.kind == SEED_KIND}) if graph is not None else []
    return lambda _spec_dir: paths


def _waiting_on(ctx: CheckContext) -> WaitingOn | None:
    """The open items that explain errors of their steps; ``None`` with no graph or an unreadable artifact (``open-items`` reports that)."""
    read = ctx.ambiguity_read
    if ctx.check_graph is None or read.error is not None:
        return None
    return WaitingOn.from_items(ctx.check_graph, read.items)


def _gate_notes(ctx: CheckContext, baseline: BaselineResult) -> tuple[str, ...]:
    """The notes of a run: the spec files the graph could not read, then the note of the baseline resolution (why it is unavailable, or that it is HEAD)."""
    notes: list[str] = []
    unreadable = [error.file for error in ctx.check_graph.load_errors] if ctx.check_graph is not None else []
    if unreadable:
        notes.append(f"specdev spec-check: could not read {', '.join(unreadable)}; the answer may be incomplete")
    if baseline.resolution is not None and baseline.resolution.note:
        notes.append(f"note: {baseline.resolution.note}")
    return tuple(notes)


def run_step_gate(
    repo_root: str,
    spec_dir: str,
    *,
    steps: Sequence[str],
    git_root: str | None = None,
    spec_root: str | None = None,
    project_canon_dir: str | None = None,
    base_ref: str | None = None,
    provider: BaselineProvider | None = None,
    ranks: Mapping[str, int] | None = None,
) -> StepGateRun:
    """Run every check once and the baseline once, and sort the findings into the buckets of each of *steps*.

    The step gate is the check for finishing a step: a finding of the step blocks it, a new finding of an earlier step
    blocks it, everything else is listed (see ``validation.step_gate``).  The baseline comes from *provider* (the
    migration-mode gate passes its own); without one it is ``merge_base_provider`` against *base_ref* (``--base-ref``).
    *ranks* is the step order, read from ``tools/step_order.json`` when absent.  Nothing is printed except what the
    checks print themselves; the caller prints the notes and the report.

    Raises:
        FindingError: E706 when a step is not a step of ``tools/step_order.json`` (before any check runs); E520 when the
            ownership table of the toolkit cannot be read.
    """
    reset_config()
    order = ranks if ranks is not None else step_order_ranks(repo_root)
    for step in steps:
        require_known_step_in(order, step)
    ctx = CheckContext(
        repo_root=repo_root, spec_dir=spec_dir, git_root=git_root, spec_root=spec_root, project_canon_dir=project_canon_dir
    )
    warn_ignored_promotions()
    errors = check_findings(run_registered_checks(ctx))
    measure = provider or merge_base_provider(_baseline_checks(repo_root, with_project_canon=project_canon_dir is not None), _seed_paths_of(ctx.check_graph), base_ref)
    baseline = measure(Path(ctx.spec_dir), host_root_of(ctx.effective_spec_root, ctx.git_root))
    graph = ctx.check_graph
    results = classify_for_steps(
        errors, steps, declared_owner, order, baseline, _waiting_on(ctx),
        canonical_id=graph.canonical_id if graph is not None else same_id,
    )
    return StepGateRun(results, baseline, _gate_notes(ctx, baseline))


def gate_run(
    repo_root: str,
    spec_dir: str,
    *,
    steps: Sequence[str] | None,
    paths: Sequence[str] | None,
    git_root: str | None = None,
    spec_root: str | None = None,
    project_canon_dir: str | None = None,
    base_ref: str | None = None,
    provider: BaselineProvider | None = None,
) -> StepGateRun:
    """What ``spec-check --step`` (*steps*) or ``--paths`` (*paths*) runs: the gate of those steps, or of the steps the paths map to.

    A step given twice is gated once.  The notes come in this order: what the touched paths mapped to (paths outside
    the host root, a seed edit, no step gated for the paths given), the steps with no artifact in *spec_dir*, then the notes of the run.  A
    run with no step to gate is empty (no result, no baseline, no baseline note) and nothing is checked.

    Raises:
        FindingError: E520 when *spec_dir* does not exist or the toolkit's ownership table cannot be read; E706 when a
            step is not a step of ``tools/step_order.json``; E708 when the spec folder is outside the host root, under
            ``--paths`` only (under ``--step`` that layout gives ``base: unavailable`` and its note).
    """
    if not os.path.isdir(spec_dir):
        raise FindingError(make_error("E520", f"UNRESOLVED_INPUT missing_spec_dir {spec_dir}"))
    ranks = step_order_ranks(repo_root)
    notes: list[str] = []
    if steps is None:
        touched = _touched_steps_of(repo_root, spec_dir, paths or (), ranks, git_root, spec_root)
        notes.extend(note for note in (outside_root_note(touched, git_root_given=git_root is not None), SEED_EDIT_NOTE if touched.seed_edited else None) if note)
        gated = list(touched.steps)
        if paths and not gated:
            notes.append(NO_STEP_NOTE)
    else:
        gated = list(dict.fromkeys(steps))
        for step in gated:
            require_known_step_in(ranks, step)
        notes.extend(f"step {step} has no artifact in {spec_dir}" for step in steps_without_artifact(gated, spec_dir))
    if not gated:
        return StepGateRun((), BaselineResult("unavailable"), tuple(notes))
    run = run_step_gate(
        repo_root, spec_dir, steps=gated, git_root=git_root, spec_root=spec_root, project_canon_dir=project_canon_dir,
        base_ref=base_ref, provider=provider, ranks=ranks,
    )
    return replace(run, notes=(*notes, *run.notes))
