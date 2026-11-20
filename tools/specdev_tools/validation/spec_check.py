"""Unified spec-check: runs all applicable validation and lint checks in one pass.

Wraps validate-all as the core, then adds checks that validate-all doesn't run
(seed-lint, fixtures-lint, completeness-check, canon-schema-alignment).
Reports per-check breakdown with PASS/WARN/FAIL/SKIP status.

This module holds the check bodies, their registrations and the plain run with its summary.  The registry they are
registered in is ``validation.check_registry``; the step gate, which runs the same checks once on the working tree and
once on the merge-base tree, is ``validation.step_gate_run``.
"""

from __future__ import annotations

import os
import sys
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from ..core.config import reset_config
from ..core.errors import SpecError
from ..core.json_output import error_to_dict
from ..core.loaders import iter_spec_artifacts, read_json_object
from ..graph.check import run_graph_check
from ..graph.gitview import read_seed_texts, read_seed_texts_noting
from ..graph.model import Graph
from ..graph.ownership import STEP_PREFIX, stamp_file_owner, step_for_file
from ..trace.computed_fields import check_stored_computed
from ..trace.lockfile import Lock, lock_path
from ..trace.records import check_records, record_files
from ..trace.suspects import check_lock
from . import graph_checks
from .check_registry import (
    CheckContext,
    check_result,
    lock_or_error,
    skip,
    register_check,
    run_registered_checks,
)
from .open_items import check_open_items


def _check_toolkit_version(repo_root: str, spec_dir: str) -> list[SpecError]:
    """Return [] if versions match, or [E608] on any error condition.

    Error cases:
    - ``spec/specdev_version`` does not exist (project must always have a recorded version).
    - Toolkit version is unreadable (missing pyproject.toml).
    - Version mismatch between recorded and active toolkit.
    """
    import os as _os
    from pathlib import Path as _Path
    from ..generation.schema_differ import get_user_version
    from ..core.changelog_parser import get_toolkit_version
    from ..core.errors import make_error

    host_version = get_user_version(_Path(_os.path.abspath(spec_dir)))
    if host_version is None:
        _sv_file = _Path(_os.path.abspath(spec_dir)) / "specdev_version"
        if _sv_file.exists():
            return [
                make_error(
                    "E608",
                    "spec/specdev_version exists but is malformed or missing the `toolkit_version` key. "
                    "Re-stamp it by running `specdev update` or fix the file manually.",
                )
            ]
        return [
            make_error(
                "E608",
                "No toolkit version recorded in spec/specdev_version. Run `specdev update` to stamp the project's toolkit version.",
            )
        ]

    toolkit_version = get_toolkit_version(_Path(_os.path.abspath(repo_root)))
    if toolkit_version is None:
        return [
            make_error(
                "E608",
                f"Could not determine the active toolkit version from {_os.path.abspath(repo_root)}/tools/pyproject.toml.",
            )
        ]

    if host_version == toolkit_version:
        return []

    return [
        make_error(
            "E608",
            (
                f"Spec was built against toolkit v{host_version}, but the active "
                f"toolkit is v{toolkit_version}. Run `specdev update` to sync to the current "
                f"toolkit version before editing specs (it re-stamps, or directs you to `align` if a migration is required)."
            ),
        )
    ]


def _trace_lock_result(
    graph: Graph | None,
    lock: Lock | None,
    lock_error: SpecError | None,
    lock_dir: str,
    host_root: str,
    *,
    quiet: bool = False,
) -> dict[str, Any]:
    """The ``trace-lock`` check: E760 for a lock that cannot be read, else E762, E763 and E882 (E761 is the ``graph`` check's).

    SKIP when there is no graph, or the graph has no links and no lock file exists.  A *quiet* run does not say on
    stderr which seed documents were not found.
    """
    if lock_error is not None:
        return check_result([lock_error])
    if graph is None or lock is None:
        return {"status": "SKIP", "reason": "no spec graph"}
    if not any(node.links for node in graph.nodes) and not os.path.isfile(lock_path(lock_dir)):
        return {"status": "SKIP", "reason": "no links and no trace lock"}
    read_seeds = read_seed_texts if quiet else read_seed_texts_noting
    return check_result(check_lock(graph, lock, read_seeds(graph, host_root)))


def _records_result(graph: Graph | None, repo_root: str, records_dir: str) -> dict[str, Any]:
    """The ``records`` check: E774 for the record files under ``extras/verification/``; SKIP with no graph or no record file."""
    if graph is None:
        return {"status": "SKIP", "reason": "no spec graph"}
    if not record_files(records_dir):
        return {"status": "SKIP", "reason": "no record files"}
    return check_result(check_records(records_dir, repo_root, graph))


_LOCK_LINK_CODES = frozenset({"E761", "W720", "E778"})


def lock_link_findings(
    graph: Graph | None, lock_dir: str, repo_root: str, host_root: str, *, step: str | None = None
) -> list[SpecError]:
    """The suspect-link findings of the trace lock under *lock_dir*, for the paths that do not run the whole ``spec-check``.

    E760 when the lock cannot be read, E761, W720 and E778 from one resolver run, then E762, E763 and E882 (what
    ``spec-check`` reports in its ``graph`` and ``trace-lock`` checks).  Nothing when *graph* is ``None`` or the graph
    has no links and no lock file exists.  *step* keeps the findings whose node belongs to that step.
    """
    if graph is None:
        return []
    lock, lock_error = lock_or_error(lock_dir)
    if lock is None:
        return [] if lock_error is None else [lock_error]
    if not any(node.links for node in graph.nodes) and not os.path.isfile(lock_path(lock_dir)):
        return []
    link_errs = [e for e in run_graph_check(lock_dir, repo_root, graph=graph, lock=lock) if e.code in _LOCK_LINK_CODES]
    findings = [*link_errs, *check_lock(graph, lock, read_seed_texts_noting(graph, host_root))]
    if step is None:
        return findings
    return [e for e in findings if (node := graph.by_id.get(e.node_id or "")) is not None and node.step == step]




def _owned_by_file(errors: Sequence[SpecError], spec_dir: str) -> list[SpecError]:
    """*errors* with the step of the spec file each one names (``file``, relative to *spec_dir*) as its owner, where it has none."""
    stamped: list[SpecError] = []
    for err in errors:
        if err.owner is None and err.file:
            path = err.file if os.path.isabs(err.file) else os.path.join(spec_dir, err.file)
            err = stamp_file_owner([err], step_for_file(path, read_json_object(path)))[0]
        stamped.append(err)
    return stamped


# --- the checks, in report order ---------------------------------------------------------------------------------

def _check_schema_validation(ctx: CheckContext) -> dict[str, Any]:
    from .validate import validate_file

    schema_errs: list[SpecError] = []
    if os.path.isdir(ctx.spec_dir):
        for file_path in iter_spec_artifacts(ctx.spec_dir):
            file_errs = validate_file(
                ctx.repo_root,
                file_path,
                include_quality_lint=False,
                include_canonical_integrity=False,
                git_root=ctx.git_root,
                spec_root=ctx.spec_root,
                include_id_slice=False,
            )
            where = os.path.relpath(file_path, ctx.spec_dir)
            owned = stamp_file_owner(file_errs, step_for_file(file_path, read_json_object(file_path)))
            schema_errs.extend(err if err.file is not None else replace(err, file=where) for err in owned)
    return check_result(schema_errs)


def _check_toolkit_version_result(ctx: CheckContext) -> dict[str, Any]:
    return check_result(_check_toolkit_version(ctx.repo_root, ctx.spec_dir))


def _check_spec_quality_lint(ctx: CheckContext) -> dict[str, Any]:
    from .spec_quality_lint import lint_spec_quality

    return check_result(lint_spec_quality(ctx.spec_dir, graph=ctx.lint_graph))


def _check_canonical_lint(ctx: CheckContext) -> dict[str, Any]:
    return check_result(ctx.canon_errors)


def _check_canonical_integrity(ctx: CheckContext) -> dict[str, Any]:
    if not ctx.canon_ok:
        return skip("canonical preflight failed")
    from ..canonical.integrity import validate_canonical_integrity

    return check_result(
        validate_canonical_integrity(
            ctx.repo_root, ctx.spec_dir,
            require_manifest_schema_registration=True,
            project_canon_dir=ctx.project_canon_dir,
        )
    )


def _check_hallucination_lint(ctx: CheckContext) -> dict[str, Any]:
    if not ctx.canon_ok:
        return skip("canonical preflight failed")
    from .hallucination_lint import lint_hallucinations

    hall_errs = lint_hallucinations(
        ctx.spec_dir,
        repo_root=ctx.repo_root,
        require_canon_dir=True,
        require_manifest_schema_registration=True,
        project_canon_dir=ctx.project_canon_dir,
        git_root=ctx.git_root,
        graph=ctx.lint_graph,
    )
    return check_result(_owned_by_file(hall_errs, ctx.spec_dir))


def _check_traceability_closure(ctx: CheckContext) -> dict[str, Any]:
    return check_result(ctx.closure_errors)


_COMPLETENESS_CHECK = "completeness-check"
_COMPLETENESS_CODES = frozenset({
    "W564", "W565", "W566", "W567", "W568",
    "E564", "E565", "E566", "E567", "E568",
})


def _check_completeness(ctx: CheckContext) -> dict[str, Any]:
    return check_result([e for e in ctx.closure_errors if isinstance(e, SpecError) and e.code in _COMPLETENESS_CODES])


def _check_seed_lint(ctx: CheckContext) -> dict[str, Any]:
    if not os.path.exists(os.path.join(ctx.project_root, "spec", "common", "seed_manifest.json")):
        return skip("seed_manifest.json not present")
    from .seed_lint import lint_seeds

    # For submodule deployments, seed docs are in the host repo (git_root), not in the toolkit root.
    return check_result(lint_seeds(ctx.repo_root, ctx.spec_dir, project_root=ctx.project_root))


def _check_fixtures_lint(ctx: CheckContext) -> dict[str, Any]:
    if not os.path.isfile(os.path.join(ctx.spec_dir, "08_fixtures.json")):
        return skip("step 08 not present")
    from .fixtures_lint import lint_fixtures

    return check_result(lint_fixtures(ctx.spec_dir))


def _check_dependency_order_lint(ctx: CheckContext) -> dict[str, Any]:
    if not (ctx.root / "tools" / "step_order.json").exists():
        return skip("step_order.json not found")
    from .dependency_order_lint import lint_dependency_order

    return check_result(lint_dependency_order(ctx.repo_root))


def _check_graph(ctx: CheckContext) -> dict[str, Any]:
    lock, _lock_error = ctx.lock_state
    return check_result(run_graph_check(ctx.effective_spec_root, ctx.repo_root, graph=ctx.check_graph, lock=lock))


def _check_computed_fields(ctx: CheckContext) -> dict[str, Any]:
    if ctx.check_graph is None:
        return skip("no spec graph")
    return check_result(check_stored_computed(ctx.check_graph))


def _check_records(ctx: CheckContext) -> dict[str, Any]:
    return _records_result(ctx.check_graph, ctx.repo_root, ctx.effective_spec_root)


def _check_registry(ctx: CheckContext) -> dict[str, Any]:
    # The registry lives toolkit-side at <repo_root>/tools/entry_key_registry.json
    if not os.path.isfile(os.path.join(ctx.repo_root, "tools", "entry_key_registry.json")):
        return skip("entry_key_registry.json not present")
    from .registry_check import run_registry_check

    return check_result(
        run_registry_check(spec_root=ctx.effective_spec_root, repo_root=ctx.repo_root, git_root=ctx.git_root)
    )


def _check_hardcoded_seed(ctx: CheckContext) -> dict[str, Any]:
    # Always runs when a prompts/ directory exists under repo_root.
    if not os.path.isdir(os.path.join(ctx.repo_root, "prompts")):
        return skip("prompts/ directory not present")
    from .seed_lint import check_hardcoded_seed_reference

    return check_result(check_hardcoded_seed_reference(ctx.repo_root, git_root=ctx.git_root))


def _check_glossary_drift(ctx: CheckContext) -> dict[str, Any]:
    if not os.path.isfile(os.path.join(ctx.spec_dir, "03_glossary.json")):
        return skip("03_glossary.json not present")
    from .glossary_drift_lint import lint_glossary_drift

    return check_result(
        lint_glossary_drift(ctx.spec_dir, repo_root=ctx.repo_root, project_canon_dir=ctx.project_canon_dir)
    )


def _check_trace_lock(ctx: CheckContext) -> dict[str, Any]:
    """Suspect links, orphan entries, baseline markers."""
    lock, lock_error = ctx.lock_state
    return _trace_lock_result(
        ctx.check_graph, lock, lock_error, ctx.effective_spec_root, ctx.project_root, quiet=ctx.quiet
    )


def _check_open_items(ctx: CheckContext) -> dict[str, Any]:
    return check_result(check_open_items(ctx.spec_dir, gate="step", read=ctx.ambiguity_read))


register_check("schema-validation", _check_schema_validation)
register_check("toolkit-version", _check_toolkit_version_result)
register_check("spec-quality-lint", _check_spec_quality_lint)
register_check("canonical-lint", _check_canonical_lint)
register_check("canonical-integrity", _check_canonical_integrity)
register_check("hallucination-lint", _check_hallucination_lint)
register_check("traceability-closure", _check_traceability_closure)
register_check(_COMPLETENESS_CHECK, _check_completeness)
register_check("seed-lint", _check_seed_lint)
register_check("fixtures-lint", _check_fixtures_lint, default_owner=STEP_PREFIX + "08")
register_check("dependency-order-lint", _check_dependency_order_lint)
register_check("graph", _check_graph)
register_check("computed-fields", _check_computed_fields)
register_check("records", _check_records)
register_check("registry-check", _check_registry)
register_check("hardcoded-seed-check", _check_hardcoded_seed)
register_check("glossary-drift-check", _check_glossary_drift, default_owner=STEP_PREFIX + "03")
register_check("trace-lock", _check_trace_lock)
graph_checks.publish_graph_checks()
register_check("open-items", _check_open_items)


def warn_ignored_promotions() -> None:
    """Surface (once per run) any SPECDEV_PROMOTE_CODES entries that will be silently ignored because they are not promotable.

    spec-check loops ``validate_file`` directly (never ``validate_dir``), so it needs its own call.
    """
    from .validate import _warn_ignored_promote_codes

    _warn_ignored_promote_codes()


def run_checks(
    repo_root: str,
    spec_dir: str,
    git_root: str | None = None,
    spec_root: str | None = None,
    project_canon_dir: str | None = None,
    *,
    quiet: bool = False,
) -> OrderedDict[str, dict[str, Any]]:
    """Run all applicable checks and return per-check results.

    Each value is either:
    - ``{"status": "SKIP", "reason": "..."}`` for skipped checks, or
    - ``{"status": "PASS"|"WARN"|"FAIL", "error_count": int, "warning_count": int, "errors": list}``
    """
    ctx = CheckContext(
        repo_root=repo_root,
        spec_dir=spec_dir,
        git_root=git_root,
        spec_root=spec_root,
        project_canon_dir=project_canon_dir,
        quiet=quiet,
    )
    if not quiet:
        warn_ignored_promotions()
    return run_registered_checks(ctx)


def check_findings(checks: Mapping[str, dict[str, Any]]) -> list[SpecError]:
    """Every finding of *checks*, in check order, except those of ``completeness-check``.

    The completeness findings are a subset of the ``traceability-closure`` ones, so counting both would count them
    twice.  This is the one place that rule is coded; ``_collect_errors`` and the step gate both read it.
    """
    return [e for name, info in checks.items() if name != _COMPLETENESS_CHECK for e in info.get("errors", ())]


def _collect_errors(checks: OrderedDict[str, dict[str, Any]]) -> list[SpecError]:
    """Collect and deduplicate all errors across checks."""
    combined: list[SpecError] = []
    seen: set[tuple[str, str]] = set()
    for e in check_findings(checks):
        key = (e.code, e.message)
        if key not in seen:
            seen.add(key)
            combined.append(e)
    return combined


def run_spec_check(
    repo_root: str,
    spec_dir: str,
    git_root: str | None = None,
    spec_root: str | None = None,
    project_canon_dir: str | None = None,
) -> list[SpecError]:
    """Run all applicable checks and return combined deduplicated errors.

    Prints a per-check summary to stderr before returning.
    """
    reset_config()
    checks = run_checks(repo_root, spec_dir, git_root, spec_root, project_canon_dir=project_canon_dir)
    _print_summary(checks)
    return _collect_errors(checks)


def run_spec_check_json(
    repo_root: str,
    spec_dir: str,
    git_root: str | None = None,
    spec_root: str | None = None,
    project_canon_dir: str | None = None,
) -> tuple[list[SpecError], dict[str, Any]]:
    """Run all checks and return (errors, json_context) for ``_json_exit``."""
    reset_config()
    checks = run_checks(repo_root, spec_dir, git_root, spec_root, project_canon_dir=project_canon_dir)
    checks_summary: dict[str, Any] = {}
    for name, info in checks.items():
        if info.get("status") == "SKIP":
            checks_summary[name] = {"status": "SKIP", "reason": info.get("reason", "")}
        else:
            checks_summary[name] = {
                "status": info["status"],
                "error_count": info["error_count"],
                "warning_count": info["warning_count"],
                "findings": [error_to_dict(e) for e in info.get("errors", [])],
            }
    return _collect_errors(checks), {"checks": checks_summary}


def _print_summary(checks: OrderedDict[str, dict[str, Any]]) -> None:
    """Print per-check breakdown to stderr."""
    run_count = 0
    total_e = 0
    total_w = 0
    lines: list[str] = []
    for name, info in checks.items():
        if info.get("status") == "SKIP":
            lines.append(f"  [SKIP] {name:<30s} ({info.get('reason', '')})")
        else:
            run_count += 1
            ec = info["error_count"]
            wc = info["warning_count"]
            total_e += ec
            total_w += wc
            tag = info["status"]
            lines.append(f"  [{tag:4s}] {name:<30s} {ec} errors  {wc} warnings")

    print(f"spec-check: {run_count} checks run, {total_e} errors, {total_w} warnings\n", file=sys.stderr)
    for line in lines:
        print(line, file=sys.stderr)
    print(file=sys.stderr)
