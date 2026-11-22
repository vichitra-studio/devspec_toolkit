"""The two release sections of ``specdev status``: the merge and release gates as they stand, and the production verification of the previous release.

``install(canon_dir_of)`` registers both through ``lifecycle.status.register_status_section`` under the names the lifecycle package
keeps (``MERGE_RELEASE_SECTION``, ``PRODUCTION_SECTION``), in the places its defaults hold.  ``cli.build_parser`` calls it, because
``lifecycle`` does not import this package.  Neither section runs a bound command or writes: the first runs the release gate
(``release.gate``: the merge-mode open-items and pin checks are part of it), the second asks the next-release check.

``production_verification`` names the state of the previous release: ``verified in production``, ``rollback recorded``, ``not
verified`` (released, awaiting production proof), ``none (previous tag predates 1.2.0)`` or ``none`` (a first release).
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from specdev_tools.core.errors import FindingError
from specdev_tools.lifecycle.status import MERGE_RELEASE_SECTION, MERGE_RELEASE_TITLE, PRODUCTION_SECTION, PRODUCTION_TITLE, Section, StatusContext, register_status_section
from specdev_tools.graph.ownership import RELEASE_OWNER
from specdev_tools.release.gate import run_release_gate
from specdev_tools.release.previous import check_next_release
from specdev_tools.release.records import read_rollback

CanonDirOf = Callable[..., str | None]
"""The function that finds the project canon folder (``cli._discover_project_canon_dir``): keywords ``git_root``, ``spec_root``, ``spec_dir``."""
VERIFIED = "verified in production"
ROLLBACK = "rollback recorded"
NOT_VERIFIED = "not verified"
PREDATES = "none (previous tag predates 1.2.0)"
NONE = "none"
_PREDATES_CODE = "W938"


@dataclass(frozen=True)
class ProductionVerification:
    """The previous release (``tag``, ``None`` for a first release), its ``state`` (one of the constants above) and what is missing (the E920 text of ``not verified``, else empty)."""

    tag: str | None
    state: str
    missing: tuple[str, ...] = ()


def production_verification(git_root: str, spec_root: str, repo_root: str) -> ProductionVerification:
    """The verification state of the release before the checkout's HEAD, from the next-release check.

    Raises:
        FindingError: E911 when the host declares no ``release_tag_pattern``; E774 for a damaged rollback record; E708 when git cannot answer.
    """
    result = check_next_release(git_root, spec_root, repo_root)
    if result.previous is None:
        return ProductionVerification(None, NONE)
    tag = result.previous.tag
    if any(warning.code == _PREDATES_CODE for warning in result.warnings):
        return ProductionVerification(tag, PREDATES)
    if read_rollback(spec_root, tag) is not None:
        return ProductionVerification(tag, ROLLBACK)
    if result.errors:
        return ProductionVerification(tag, NOT_VERIFIED, tuple(error.render() for error in result.errors))
    return ProductionVerification(tag, VERIFIED)


def _production(sc: StatusContext) -> Section:
    try:
        found = production_verification(sc.git_root, sc.spec_root, sc.repo_root)
    except FindingError as error:
        return Section(PRODUCTION_SECTION, PRODUCTION_TITLE, (f"not read: {error.error.render()}",), None)
    shown = f"{found.state} (released, awaiting production proof)" if found.state == NOT_VERIFIED else found.state
    lines = (f"previous release: {found.tag or NONE}", f"state: {shown}", *found.missing)
    return Section(PRODUCTION_SECTION, PRODUCTION_TITLE, lines, {"tag": found.tag, "state": found.state, "missing": list(found.missing)})


def _merge_release(canon_dir_of: CanonDirOf) -> Callable[[StatusContext], Section]:
    def section(sc: StatusContext) -> Section:
        canon = canon_dir_of(git_root=sc.git_root, spec_root=sc.spec_root, spec_dir=sc.spec_root)
        try:
            result = run_release_gate(sc.repo_root, sc.spec_root, sc.git_root, sc.spec_root, canon)
        except FindingError as error:
            return Section(MERGE_RELEASE_SECTION, MERGE_RELEASE_TITLE, (f"the release gate was not run: {error.error.render()}",), None)
        by_owner: dict[str, list[str]] = defaultdict(list)
        for found in result.errors:
            by_owner[found.owner or RELEASE_OWNER].append(found.render())
        head = f"release gate: {len(result.errors)} error(s), {len(result.warnings)} warning(s), {len(result.listed)} listed (not blocking)"
        lines = [head, *(line for owner, found in sorted(by_owner.items()) for line in (f"{owner} ({len(found)}):", *(f"  {text}" for text in found)))]
        lines += [warning.render() for warning in result.warnings] + [f"note: {note}" for note in result.notes]
        data = {
            "errors": {owner: found for owner, found in sorted(by_owner.items())},
            "warnings": [warning.render() for warning in result.warnings],
            "listed": [listed.render() for listed in result.listed],
            "notes": list(result.notes),
        }
        return Section(MERGE_RELEASE_SECTION, MERGE_RELEASE_TITLE, tuple(lines), data)

    return section


def install(canon_dir_of: CanonDirOf) -> None:
    """Register the two release sections of ``status`` (replacing the "release gate not installed" defaults in their places).

    *canon_dir_of* finds the project canon folder, as ``spec-check`` does, so the gate reads the same canon (without it the gate reports false E110).
    """
    register_status_section(MERGE_RELEASE_SECTION, _merge_release(canon_dir_of))
    register_status_section(PRODUCTION_SECTION, _production)
