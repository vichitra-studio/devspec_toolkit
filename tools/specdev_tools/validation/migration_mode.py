"""The step gate in migration mode: while a host moves to a new toolkit version, a step is judged by whether it has been passed, not by the merge-base.

A branch that migrates a host changes ``spec/specdev_version``.  The merge-base then holds a spec the old toolkit
wrote, so measured against it every error of an earlier step looks new.  ``migration_aware_provider`` wraps the
default baseline provider: when the stamp of the working tree differs from the stamp at the merge-base, the
baseline is the set of findings owned by the steps that are *not passed*, and the merge-base is not consulted.  A
step is not passed while it owns an E882 finding (a live trace-lock link still carrying the migration baseline
marker); every other step is passed, a step with no converted links included.  So an error of a passed upstream step
is a new upstream error (blocking), and an error of an upstream step that still carries markers is upstream debt.
Any other host, and any run with no stamp or no resolvable base, gets the default provider unchanged.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from specdev_tools.core.errors import SpecError
from specdev_tools.core.git_base import BaselineProvider, BaselineResult, BaseResolution, resolve_baseline
from specdev_tools.generation.schema_differ import get_user_version
from specdev_tools.graph.gitview import GitViewError, toolkit_stamp_at

BASELINE_MARKER_CODE = "E882"
"""The finding that says a step still carries a migration baseline marker: the step is not passed."""
MIGRATION_NOTE = (
    "migration mode: the toolkit stamp differs from the merge-base's, so an error of a step that still carries "
    "migration baseline markers is debt and an error of any other earlier step is new"
)


def migration_resolution(spec_dir: Path, git_root: str, base_ref: str | None = None) -> BaseResolution | None:
    """The resolution of the merge-base when the run is in migration mode, else ``None``.

    Migration mode is on when the spec folder has a stamp and it differs from the stamp at the merge-base commit
    (read with ``git archive``, no write); a stamp absent at the base counts as different.  No stamp in the working
    tree, no resolvable base, or a spec folder outside *git_root* means it is off.
    """
    tree_stamp = get_user_version(spec_dir)
    if tree_stamp is None:
        return None
    resolution = resolve_baseline(git_root, base_ref)
    if resolution.commit is None:
        return None
    try:
        base_stamp = toolkit_stamp_at(resolution.commit, git_root, str(spec_dir))
    except GitViewError:
        return None
    return resolution if base_stamp != str(tree_stamp) else None


def not_passed_owners(errors: Sequence[SpecError]) -> frozenset[str]:
    """The owners of the E882 findings in *errors*: the steps that still carry migration baseline markers."""
    return frozenset(error.owner for error in errors if error.code == BASELINE_MARKER_CODE and error.owner)


def migration_aware_provider(
    errors: Sequence[SpecError], default: BaselineProvider, base_ref: str | None = None
) -> BaselineProvider:
    """A provider that is *default* outside migration mode and the migration baseline inside it.

    *errors* are the findings of the current run: the baseline in migration mode is those owned by a step that owns
    an E882 finding.  *base_ref* is the ``--base-ref`` the default provider reads, so both resolve the same base.
    """

    def provider(spec_dir: Path, git_root: str) -> BaselineResult:
        resolution = migration_resolution(spec_dir, git_root, base_ref)
        if resolution is None:
            return default(spec_dir, git_root)
        carried = not_passed_owners(errors)
        debt = tuple(error for error in errors if error.owner in carried)
        return BaselineResult("ok", debt, replace(resolution, note=MIGRATION_NOTE))

    return provider
