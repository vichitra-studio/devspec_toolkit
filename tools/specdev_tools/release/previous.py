"""The previous release and the next-release check: a release is cut only after the one before it was verified in production.

``previous_release`` is one tag lookup, not a walk of history: the nearest ancestor of the release commit whose tag matches the
host's ``release_tag_pattern`` (a tag on the release commit itself is not an ancestor; a tag the pattern does not match, such as
a candidate's ``-stage`` tag, is outside the gate).  ``check_next_release`` then asks, for that release P:

1. none exists: pass with W937;
2. P's commit has no 1.2.0 spec (``<spec>/specdev_version`` absent, unreadable or below 1.2.0): pass with W938;
3. a rollback record of P exists in the checkout: pass;
4. else P must be verified in production, read AT P (ruling N3: its graph, declarations and exclusions, through ``tag_state``) with
   the checkout's evidence: every node that waited for a stage above ``ci`` at P is built and proven at ``prod`` for P's code tree, and every
   ``at_deploy`` action of the milestones P closed has a ``done`` record for each of its environments.  A shortfall is E920.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.graph.gitview import git_stdout, resolve_ref, toolkit_stamp_at
from specdev_tools.graph.ownership import RELEASE_OWNER
from specdev_tools.graph.stages import CI_STAGE, PROD_STAGE
from specdev_tools.lifecycle import executed
from specdev_tools.lifecycle.anchor_store import read_statuses
from specdev_tools.proof.built_evidence import built_at_cap, relieved_nodes
from specdev_tools.proof.proof import proof_errors
from specdev_tools.release.records import read_rollback
from specdev_tools.release.tag_state import release_tag_pattern, tag_matches, tag_state
from specdev_tools.validation.graph_checks.built import BuiltState
from specdev_tools.validation.merge_gate import closed_by_branch
from specdev_tools.verify.code_tree import declarations_of

FIRST_SPEC_VERSION = (1, 2, 0)
"""The first toolkit version whose spec declares production bindings and ``at_deploy`` actions."""
_VERSION = re.compile(r"\s*(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True)
class PreviousRelease:
    """A release tag and the commit it names."""

    tag: str
    commit: str


@dataclass(frozen=True)
class NextReleaseResult:
    """The outcome of the next-release check: the previous release (``None`` for a first release) and what it found."""

    previous: PreviousRelease | None
    errors: tuple[SpecError, ...] = ()
    warnings: tuple[SpecError, ...] = ()


def previous_release(git_root: str, ref: str, pattern: str) -> PreviousRelease | None:
    """The previous release of the commit *ref* names: among the tags that are ancestors of it and match *pattern*, the one the fewest commits behind it (a tie goes to the newest tag).

    Lightweight and annotated tags both count.  A tag on the commit itself is left out.

    Raises:
        FindingError: E708 when *ref* does not resolve or git fails.
    """
    commit = resolve_ref(ref, git_root)
    listed = [line.split("\t") for line in git_stdout(git_root, ["tag", "--merged", commit, "--format=%(refname:strip=2)\t%(creatordate:unix)"]).splitlines()]
    found: list[tuple[int, int, str, str]] = []
    for tag, stamp in (row for row in listed if len(row) == 2 and tag_matches(pattern, row[0])):
        tagged = resolve_ref(tag, git_root)
        if tagged != commit:
            found.append((int(git_stdout(git_root, ["rev-list", "--count", f"{tagged}..{commit}"])), -int(stamp or 0), tag, tagged))
    if not found:
        return None
    _, _, tag, tagged = min(found)
    return PreviousRelease(tag, tagged)


def predates_1_2_0(git_root: str, spec_root: str, commit: str) -> bool:
    """Whether the spec at *commit* is not a 1.2.0 spec: its ``specdev_version`` is absent there, has no ``toolkit_version`` or reads below 1.2.0.

    A pre-release suffix (``1.2.0rc1``) reads as 1.2.0.

    Raises:
        FindingError: E708 when git cannot answer (a failing read is not "predates").
    """
    stamp = toolkit_stamp_at(commit, git_root, spec_root)
    matched = _VERSION.match(stamp) if stamp else None
    return matched is None or tuple(int(part) for part in matched.groups()) < FIRST_SPEC_VERSION


def _closed_at(git_root: str, spec_root: str, release: PreviousRelease, pattern: str) -> list[str]:
    """The milestones *release* closed: ``done`` at its commit and not ``done`` at the release before it (all of them when none exists)."""
    before = previous_release(git_root, release.commit, pattern)
    earlier = read_statuses(spec_root, before.commit, git_root) if before is not None else {}
    return closed_by_branch(read_statuses(spec_root, release.commit, git_root), earlier)


def _missing_in_production(git_root: str, spec_root: str, repo_root: str, release: PreviousRelease, pattern: str) -> list[str]:
    """What is still missing for *release* to count as verified in production, one line each (empty when it is verified)."""
    missing: list[str] = []
    with tag_state(git_root, spec_root, repo_root, release.commit) as state:
        waiting = relieved_nodes(state.checks, CI_STAGE)
        built = built_at_cap(state.checks, PROD_STAGE) if waiting else {}
        missing += [f"{node.id} is not built at prod ({built[node.id].reason})" for node in waiting if built[node.id].state is not BuiltState.BUILT]
        missing += [error.message for error in proof_errors(state.graph, state.proof, [node.id for node in waiting], PROD_STAGE)]
        for item, action, env in executed.at_deploy_required(state.spec_dir, _closed_at(git_root, spec_root, release, pattern)):
            if not executed.at_deploy_recorded(spec_root, item, action, env):
                missing.append(f"at-deploy action {item}/{action} has no done record for {env}")
    return list(dict.fromkeys(missing))


def check_next_release(git_root: str, spec_root: str, repo_root: str, ref: str = "HEAD") -> NextReleaseResult:
    """The next-release check of the release at *ref*: the previous release must have been verified in production (see the module text).

    Raises:
        FindingError: E911 when the host declares no ``release_tag_pattern``; E774 when the rollback record of the previous release is
            not valid; E708 when git cannot answer; E520 when the host declarations cannot be read.
    """
    pattern = release_tag_pattern(declarations_of(spec_root))
    previous = previous_release(git_root, ref, pattern)
    if previous is None:
        return NextReleaseResult(None, warnings=(make_error("W937", "this is the first release: no earlier release tag matches the release tag pattern, so there is nothing to verify", owner=RELEASE_OWNER),))
    return _verified_in_production(git_root, spec_root, repo_root, previous, pattern)


def release_at(git_root: str, ref: str, pattern: str) -> PreviousRelease | None:
    """The release tagged on the commit *ref* names (the newest tag that matches *pattern*), or ``None`` when no matching tag is on it.

    Raises:
        FindingError: E708 when *ref* does not resolve or git fails.
    """
    commit = resolve_ref(ref, git_root)
    listed = [line.split("\t") for line in git_stdout(git_root, ["tag", "--points-at", commit, "--format=%(refname:strip=2)\t%(creatordate:unix)"]).splitlines()]
    found = sorted(((-int(stamp or 0), tag) for tag, stamp in (row for row in listed if len(row) == 2 and tag_matches(pattern, row[0]))))
    return PreviousRelease(found[0][1], commit) if found else None


def check_release_at(git_root: str, spec_root: str, repo_root: str, ref: str = "HEAD") -> NextReleaseResult | None:
    """The verification state of the release tagged on the commit *ref* names, judged as ``check_next_release`` judges the previous release; ``None`` when no release is tagged there.

    Raises:
        FindingError: as ``check_next_release``.
    """
    pattern = release_tag_pattern(declarations_of(spec_root))
    tagged = release_at(git_root, ref, pattern)
    return _verified_in_production(git_root, spec_root, repo_root, tagged, pattern) if tagged is not None else None


def _verified_in_production(git_root: str, spec_root: str, repo_root: str, previous: PreviousRelease, pattern: str) -> NextReleaseResult:
    """The outcome for the release *previous*: the checks 2 to 4 of the module text."""
    if predates_1_2_0(git_root, spec_root, previous.commit):
        return NextReleaseResult(previous, warnings=(make_error("W938", f"the previous release {previous.tag} predates the 1.2.0 spec, which declared no production bindings or at-deploy actions, so there is nothing to verify", owner=RELEASE_OWNER),))
    if read_rollback(spec_root, previous.tag) is not None:
        return NextReleaseResult(previous)
    missing = _missing_in_production(git_root, spec_root, repo_root, previous, pattern)
    if not missing:
        return NextReleaseResult(previous)
    shortfall = make_error(
        "E920",
        f"the previous release {previous.tag} is not verified in production: {'; '.join(missing)}; "
        f"verify it, or waive it with `specdev release rollback {previous.tag} --reason \"...\"`",
        owner=RELEASE_OWNER,
    )
    return NextReleaseResult(previous, errors=(shortfall,))

