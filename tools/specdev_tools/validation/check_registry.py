"""The registry of ``spec-check`` checks: what a check is, what it is given and how the registered checks run.

A check is a function ``CheckContext -> result`` registered with ``register_check`` under a name and a default owner.
``run_registered_checks`` runs each one once, in registration order, and stamps the owner of every finding that has
none.  Other milestones register their checks by importing this module only; ``validation.spec_check`` holds the checks
of M1 to M6a and the plain run, ``validation.step_gate_run`` the step gate.  Nothing here imports either of them.
"""

from __future__ import annotations

import os
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import cached_property
from pathlib import Path
from typing import Any, NamedTuple

from ..core.ambiguity_items import ItemsRead, read_ambiguity_items
from ..core.errors import FindingError, SpecError
from ..graph.gitview import host_root_of
from ..graph.model import Graph
from ..graph.ownership import OwnerContext, load_owner_context, owner_for
from ..lifecycle.frozen import is_frozen_path
from ..trace.lockfile import MERGE_CHECK_OWNER, Lock, LockError, read_lock
from .linter_utils import build_lint_graph


def _classify(errors: list[SpecError]) -> dict[str, Any]:
    """Return status/counts for a list of errors."""
    e_count = sum(1 for e in errors if not e.code.startswith("W"))
    w_count = sum(1 for e in errors if e.code.startswith("W"))
    if e_count:
        status = "FAIL"
    elif w_count:
        status = "WARN"
    else:
        status = "PASS"
    return {"status": status, "error_count": e_count, "warning_count": w_count}


def check_result(errors: list[SpecError]) -> dict[str, Any]:
    """Build a per-check result dict with W->E promotion applied first.

    Promotion (``SPECDEV_WARNINGS_AS_ERRORS`` / ``SPECDEV_PROMOTE_CODES``) must be
    applied *before* both the status classification and the stored error list, so
    that:
      - ``_classify`` reports FAIL (not WARN) when a check's only errors are
        promotable W-codes under an active promotion contract, and
      - the ``errors`` list — surfaced in the stderr breakdown, the JSON
        per-check ``findings``, and the aggregate returned by ``_collect_errors``
        — carries the promoted E-codes, so downstream consumers parsing the code
        field do not mis-classify promoted errors as warnings.

    ``_apply_we_promotion`` is a no-op (dedup only) when no promotion env is set,
    and is idempotent on already-promoted codes (e.g. schema-validation errors
    promoted inside ``validate_file``). Control-flow gates that branch on raw
    codes (the ``canon_ok`` bootstrap gate) are intentionally left to read the
    unpromoted lists; only result *storage* flows through this helper.
    """
    from .validate import _apply_we_promotion

    promoted = _apply_we_promotion(errors)
    return {**_classify(promoted), "errors": promoted}


def graph_for_checks(repo_root: str, spec_dir: str, spec_root: str | None, lint_graph: Graph | None) -> Graph | None:
    """The graph of *spec_root* for the ``graph`` and ``trace-lock`` checks: the lint graph when that is the same folder as *spec_dir*, else a new build.

    ``None`` when the registry is unavailable (the ``graph`` check then reports that one E520).
    """
    if os.path.abspath(spec_root or spec_dir) == os.path.abspath(spec_dir):
        return lint_graph
    return build_lint_graph(spec_root or spec_dir, repo_root)


def lock_or_error(lock_dir: str) -> tuple[Lock | None, SpecError | None]:
    """The trace lock under *lock_dir* (empty when the file is absent), or the E760 finding when it cannot be read."""
    try:
        return read_lock(lock_dir), None
    except LockError as exc:
        return None, exc.error


@dataclass
class CheckContext:
    """The arguments of one ``spec-check`` run and the values several checks share.

    A shared value is computed on first use, so a check does not depend on where the registry puts the check that
    needs the same value.  ``quiet`` is set for the run on the baseline tree of the step gate: it says nothing on stderr.
    """

    repo_root: str
    spec_dir: str
    git_root: str | None = None
    spec_root: str | None = None
    project_canon_dir: str | None = None
    quiet: bool = False

    @property
    def effective_spec_root(self) -> str:
        """``--spec-root`` when given, else the spec folder."""
        return self.spec_root or self.spec_dir

    def is_frozen_plan(self, plan_path: Path) -> bool:
        """Whether the plan file *plan_path* is frozen: the anchor row of its milestone is ``done``.

        The one frozen provider of the ``open-items`` check and of the merge gate.  A row that cannot be read is not frozen
        here; the ``frozen-plans`` check reports its E801.
        """
        try:
            return is_frozen_path(self.effective_spec_root, plan_path)
        except FindingError:
            return False

    @cached_property
    def root(self) -> Path:
        """The toolkit root, absolute."""
        return Path(os.path.abspath(self.repo_root))

    @cached_property
    def project_root(self) -> str:
        """The host repository root (``host_root_of``)."""
        return host_root_of(self.spec_dir, self.git_root)

    @cached_property
    def owner_context(self) -> OwnerContext:
        """The ownership table of the toolkit, read once per run.

        Raises:
            FindingError: E520 when ``tools/error_ownership.json`` is missing or unreadable (the run is refused).
        """
        return load_owner_context(self.repo_root)

    @cached_property
    def lint_graph(self) -> Graph | None:
        """The graph the linters share; ``None`` when the registry is unavailable."""
        return build_lint_graph(self.spec_dir, self.repo_root)

    @cached_property
    def check_graph(self) -> Graph | None:
        """The graph of the spec root for the ``graph``, ``computed-fields``, ``records`` and ``trace-lock`` checks."""
        return graph_for_checks(self.repo_root, self.spec_dir, self.spec_root, self.lint_graph)

    @cached_property
    def ambiguity_read(self) -> ItemsRead:
        """The ambiguity items of the spec folder, read once per run for the ``open-items`` check and the step gate's waiting map."""
        return read_ambiguity_items(self.spec_dir)

    @cached_property
    def lock_state(self) -> tuple[Lock | None, SpecError | None]:
        """The trace lock of the spec root, or the E760 finding when it cannot be read."""
        return lock_or_error(self.effective_spec_root)

    @cached_property
    def canon_errors(self) -> list[SpecError]:
        """The findings of the canonical preflight, without repeats."""
        from ..canonical.lint import lint_canon_dirs

        return list(
            dict.fromkeys(
                lint_canon_dirs(
                    self.repo_root,
                    project_canon_dir=self.project_canon_dir,
                    require_manifest_schema_registration=True,
                )
            )
        )

    @cached_property
    def canon_ok(self) -> bool:
        """Whether the canonical preflight has no error; the canon-dependent checks are skipped when it has.

        Read from the unpromoted findings on purpose: promotion must not change which checks run.
        """
        return not any(not e.code.startswith("W") for e in self.canon_errors)


CheckFn = Callable[[CheckContext], dict[str, Any]]
"""``ctx -> result``: ``check_result(errors)`` or ``{"status": "SKIP", "reason": ...}``."""


class CheckSpec(NamedTuple):
    """One registered check: its name in the report, the function that runs it and the owner of a finding that has none."""

    name: str
    fn: CheckFn
    default_owner: str


CHECK_REGISTRY: list[CheckSpec] = []
"""The checks ``spec-check`` runs, in order; ``register_check`` appends to it."""


def unregister_check(name: str) -> None:
    """Remove the check *name* from ``CHECK_REGISTRY`` (for tests: a test undoes its registration with it).

    Raises:
        ValueError: no check of that name is registered.
    """
    for index, spec in enumerate(CHECK_REGISTRY):
        if spec.name == name:
            del CHECK_REGISTRY[index]
            return
    raise ValueError(f"check {name!r} is not registered")


def register_check(name: str, fn: CheckFn, *, default_owner: str = MERGE_CHECK_OWNER) -> None:
    """Append the check *name* to the checks every ``spec-check`` run executes, once, after the ones registered before.

    *default_owner* (``merge-check`` or ``step:<id>``) is stamped on the findings of *fn* that carry no owner of their
    own.  A milestone registers its check from its own module, by a ``register_check`` call in the registration block of
    ``validation/spec_check.py`` (the one place the block lives); a module that registers its check anywhere else is
    imported only if something imports it, and ``spec-check`` then does not run it.

    Raises:
        ValueError: a check of that name is already registered.
    """
    if any(spec.name == name for spec in CHECK_REGISTRY):
        raise ValueError(f"check {name!r} is already registered")
    CHECK_REGISTRY.append(CheckSpec(name, fn, default_owner))


def skip(reason: str) -> dict[str, Any]:
    return {"status": "SKIP", "reason": reason}


def with_default_owner(result: dict[str, Any], owner: str, context: OwnerContext) -> dict[str, Any]:
    """*result* with an owner on each of its findings that has none.

    The owner of a finding is the one it carries; else the row of the ownership table for its code (*context*, asked
    without a node: a ``fixed_step:<id>`` or a gate rule answers); else *owner*, the default of the check.
    """
    errors = result.get("errors")
    if not errors:
        return result
    stamped = [
        err if err.owner is not None else replace(err, owner=owner_for(err.code, None, context) or owner)
        for err in errors
    ]
    return {**result, "errors": stamped}


def run_registered_checks(ctx: CheckContext) -> OrderedDict[str, dict[str, Any]]:
    """Run each check of ``CHECK_REGISTRY`` once, in order, and return the results by check name.

    A finding that has no owner gets the check's default owner.

    Raises:
        RuntimeError: ``CHECK_REGISTRY`` is empty (a programming error: a gate built on no check would say CLEAR).
        FindingError: E520 when the ownership table of the toolkit cannot be read.
    """
    if not CHECK_REGISTRY:
        raise RuntimeError("no check is registered: import specdev_tools.validation.spec_check, whose registration block registers the checks")
    checks: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for spec in CHECK_REGISTRY:
        checks[spec.name] = with_default_owner(spec.fn(ctx), spec.default_owner, ctx.owner_context)
    return checks
