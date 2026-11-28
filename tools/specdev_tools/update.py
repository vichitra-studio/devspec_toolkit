"""specdev update — sync a project to the current toolkit version.

Thin orchestrator that:
1. Resolves host version (spec/specdev_version) and toolkit version (pyproject.toml).
2. Short-circuits when already current.
3. Refreshes the venv installation via uv (handles uv-absent and wrong-Python edges).
4. Computes the schema diff and asks whether a data migration is needed (``_data_migration_reason``).
5. Re-stamps spec/specdev_version when no migration is needed, or directs the user to ``specdev align apply --auto``
   and the steps after it when one is.  A host whose stamp says ``migration_status: in_progress`` is told to finish
   with ``specdev align validate`` and is not re-stamped.

Before steps 1 to 5 the host installer (``host_install.py``) installs its pieces into the host repository, unless
``no_install``; ``install_only`` runs the installer alone.

Two things block a plain re-stamp of a spec that records a version:
  - a structural change: steps_missing | steps_needs_update | steps_needs_rename | paradigm_shifts > 0
    (unknown steps, i.e. user extensions, and extension steps never block);
  - a data migration: a migration script is registered for a version above the host's up to the toolkit's, the changelog
    between them has an entry with a ``script`` or ``kind: mechanical``, or the host's version is not one the changelog
    lists.  The structural diff compares only the top level of each schema, so it cannot see this.
A spec with no ``specdev_version`` is re-stamped after the structural diff, as before.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .core.changelog_parser import get_changes_between, list_versions
from .generation.schema_differ import read_stamp
from .core.constants import STATUS_IN_PROGRESS
from .migration import registry

if TYPE_CHECKING:
    from .host_install import InstallReport


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class UpdateResult:
    """Structured result returned by run_update()."""

    exit_code: int
    status: str  # "already_current" | "updated" | "would_update" | "needs_migration" | "migration_in_progress" | "installed" | "would_install" | "error"
    from_version: Optional[str]
    to_version: Optional[str]
    needs_migration: bool = False
    migration_details: str = ""
    refresh_ok: Optional[bool] = None       # None → skipped (already current / dry-run)
    refresh_message: str = ""
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False
    host_install: dict = field(default_factory=dict)  # InstallReport.to_dict() of the run, on every path


# ---------------------------------------------------------------------------
# Venv refresh
# ---------------------------------------------------------------------------

def refresh_venv_installation(toolkit_tools_dir: Path) -> tuple[bool, str]:
    """Run ``uv pip install -e <toolkit_tools_dir>`` against the active venv.

    Returns ``(success, message)``.

    Handles three edge cases:
    - uv absent (pre-DEVSPEC-88 setup): returns False with migration instructions.
    - Python < 3.13: returns False — the native google-re2 wheel requires 3.13;
      instructs the user to rebuild via setup_devspec_env.sh.
    - subprocess failure: returns False with stderr.
    """
    uv = shutil.which("uv")
    if not uv:
        return (
            False,
            (
                "uv is not installed.\n"
                "This toolkit requires uv for dependency management (DEVSPEC-88).\n"
                "Install uv and re-run environment setup:\n"
                "  curl -LsSf https://astral.sh/uv/install.sh | sh\n"
                "  bash devspec_toolkit/scripts/setup_devspec_env.sh\n"
                "Python source is already current (editable install), "
                "but newly-added toolkit dependencies may be missing."
            ),
        )

    _vi = sys.version_info[:2]  # (major, minor) — sliceable from both real and mocked vi
    if _vi < (3, 13):
        return (
            False,
            (
                f"Active venv is running Python {_vi[0]}.{_vi[1]}, "
                "but the toolkit requires Python 3.13 "
                "(google-re2 only ships a prebuilt wheel for cp313).\n"
                "Rebuild the environment on Python 3.13:\n"
                "  bash devspec_toolkit/scripts/setup_devspec_env.sh"
            ),
        )

    try:
        # Pass --python sys.executable so uv targets the active venv regardless
        # of whether VIRTUAL_ENV is exported (wrapper path never sets it).
        # Mirrors init_project.py:698 which uses the same pattern.
        result = subprocess.run(
            [uv, "pip", "install", "-e", str(toolkit_tools_dir),
             "--python", sys.executable, "--quiet"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return False, f"uv pip install failed:\n{result.stderr.strip()}"
        return True, "Toolkit dependencies refreshed via uv."
    except subprocess.TimeoutExpired:
        return False, "uv pip install timed out after 120 s."
    except Exception as exc:
        return False, f"Failed to refresh toolkit dependencies: {exc}"


# ---------------------------------------------------------------------------
# Update logic
# ---------------------------------------------------------------------------

def _needs_migration(summary: dict) -> bool:
    """Return True iff the diff requires schema migration (not just a re-stamp).

    Only structural changes block a plain re-stamp.  steps_unknown (user
    extensions not in toolkit schemas) and steps_extension never block it.
    """
    return (
        summary.get("steps_missing", 0) > 0
        or summary.get("steps_needs_update", 0) > 0
        or summary.get("steps_needs_rename", 0) > 0
        or summary.get("paradigm_shifts", 0) > 0
    )


def _data_migration_reason(host_version: str, toolkit_version: str, repo_root: Path) -> Optional[str]:
    """Why the host recorded at *host_version* cannot simply be re-stamped to *toolkit_version*; ``None`` when it can.

    Three reasons, any one is enough: the registry has migration scripts for a version above the host's up to the
    toolkit's (``chain_for``); the changelog between the two has an entry that names a ``script`` or is
    ``kind: mechanical``; the changelog lists releases and the host's version is not one of them (the scripts that
    apply to it cannot be told).  A toolkit root with no changelog gives the last two nothing to read.
    """
    chain = registry.chain_for(registry.discover_scripts(), host_version, toolkit_version)
    if chain:
        return f"{len(chain)} migration script(s) are registered for v{host_version} -> v{toolkit_version}: {', '.join(script.id for script in chain)}"
    changelog = repo_root / "changelog"
    listed = list_versions(changelog)
    if listed and host_version not in listed:
        return f"v{host_version} is not a release the changelog lists, so the migration scripts that apply to it cannot be told"
    scripted = [
        change.migration.script or change.migration.kind
        for change in get_changes_between(changelog, host_version, toolkit_version)
        if change.migration is not None and (change.migration.script or change.migration.kind == "mechanical")
    ]
    if scripted:
        return f"the changelog between v{host_version} and v{toolkit_version} has {len(scripted)} entry(ies) that migrate host data"
    return None


def _migration_message(spec_dir: Path, repo_root: Path, details: str, from_version: Optional[str], to_version: str, prompts: bool) -> str:
    """What ``update`` prints when the spec needs a migration: the reason, then the commands in the order they are run."""
    steps = [
        ("check again, writing nothing and touching no venv", f"specdev update {spec_dir} --repo-root {repo_root} --no-install --dry-run"),
        ("review what the mechanical pass would change", f"specdev align apply {spec_dir} --auto --dry-run --repo-root {repo_root}"),
        ("run it (it writes under the spec folder only; the git history is the undo)", f"specdev align apply {spec_dir} --auto --repo-root {repo_root}"),
        ("commit it; --no-verify because the old hooks still name retired commands", f'git add {spec_dir} && git commit --no-verify -m "Migrate the spec to toolkit v{to_version}"'),
        ("install the host files for the new version", f"specdev update {spec_dir} --repo-root {repo_root} --adopt"),
        ("the pass: list the decisions the scripts left, work through them", f"specdev align triage {spec_dir} --repo-root {repo_root}"),
        ("finish: clears migration_status when spec-check --merge is clean", f"specdev align validate {spec_dir} --repo-root {repo_root}"),
    ]
    lines = [f"The spec needs a migration, not a re-stamp (v{from_version or 'unknown'} -> v{to_version}): {details}."]
    if prompts:
        lines.append(
            "A change that no script makes (a missing step, a field the scripts do not know) is written as prompts for an agent: "
            f"specdev align prompts {spec_dir} --output prompts/migration/ --mode upgrade --repo-root {repo_root}"
        )
    lines.append("spec/specdev_version is left as it is. Run, in this order:")
    lines.extend(f"  {number}. {command}\n       {why}" for number, (why, command) in enumerate(steps, 1))
    return "\n".join(lines)


def _migration_in_progress(spec_dir: Path, repo_root: Path, host_version: Optional[str], toolkit_version: str) -> UpdateResult:
    """The result for a spec whose stamp says ``migration_status: in_progress``: nothing is re-stamped; the next command is ``align validate``."""
    current = host_version == toolkit_version
    return UpdateResult(
        exit_code=0 if current else 1,
        status="migration_in_progress",
        from_version=host_version,
        to_version=toolkit_version,
        message=(
            f"A migration is in progress: spec/specdev_version records v{host_version} with migration_status: in_progress"
            + (f", the toolkit is at v{toolkit_version}; finish the migration first.\n" if not current else ", the toolkit's own version, so there is nothing to re-stamp.\n")
            + f"  specdev align triage {spec_dir} --repo-root {repo_root}      (what is left for a person)\n"
            f"  specdev align validate {spec_dir} --repo-root {repo_root}    (finish it: clears migration_status)"
        ),
    )


def _toolkit_version_error(repo_root: Path) -> UpdateResult:
    """The E608 result for a toolkit root whose version cannot be read."""
    return UpdateResult(
        exit_code=1,
        status="error",
        from_version=None,
        to_version=None,
        message=(
            f"E608 TOOLKIT_VERSION_MISMATCH: Could not read toolkit version from "
            f"{repo_root / 'tools' / 'pyproject.toml'}. "
            "Ensure the toolkit is correctly installed."
        ),
    )


def _install_only_result(report: InstallReport, repo_root: Path, dry_run: bool) -> UpdateResult:
    """The result of ``--install-only``: no version logic, no stamp; the exit code is 0 whatever the pieces did."""
    from .core.changelog_parser import get_toolkit_version

    toolkit_version = get_toolkit_version(repo_root)
    if toolkit_version is None:
        return _toolkit_version_error(repo_root)
    return UpdateResult(
        exit_code=0,
        status="would_install" if dry_run else "installed",
        from_version=None,
        to_version=toolkit_version,
        message=report.summary(),
        dry_run=dry_run,
    )


def run_update(
    spec_dir: Path,
    repo_root: Path,
    dry_run: bool = False,
    git_root: Optional[Path] = None,
    install_only: bool = False,
    no_install: bool = False,
    adopt: bool = False,
    force_claude: bool = False,
) -> UpdateResult:
    """Sync a host to the current toolkit: install the host pieces, then re-stamp or direct to ``align``.

    Args:
        spec_dir: Absolute path to the project's spec/ directory.
        repo_root: Absolute path to the toolkit root (contains tools/pyproject.toml).
        dry_run: When True, report what would be done without writing any files or running any command.
        git_root: The host root; default the git top folder of ``spec_dir``.
        install_only: Install the host pieces and skip the version logic and the stamp.
        no_install: Skip the host install (detection only).
        adopt: Let pieces rewrite drifted host content they would otherwise only report.
        force_claude: Let the symlink piece replace stale skill and agent links (never a real file).

    Returns:
        An UpdateResult describing outcome and exit code; ``host_install`` holds the install report on every path.
        A piece that is refused or drifts adds warnings and never changes the exit code.
    """
    from .host_install import NO_INSTALL_REQUESTED, InstallReport, run_host_install

    report = (
        InstallReport(skipped=NO_INSTALL_REQUESTED)
        if no_install
        else run_host_install(
            spec_dir, repo_root, git_root=git_root, dry_run=dry_run, adopt=adopt, force_claude=force_claude
        )
    )
    result = _install_only_result(report, repo_root, dry_run) if install_only else _run_update_core(spec_dir, repo_root, dry_run)
    if report.pieces and not install_only:
        result.message = f"{result.message}\n{report.summary()}"
    result.warnings = [*result.warnings, *report.warnings()]
    result.host_install = report.to_dict()
    return result


def _run_update_core(
    spec_dir: Path,
    repo_root: Path,
    dry_run: bool = False,
) -> UpdateResult:
    """The version logic of ``update``: re-stamp ``spec/specdev_version`` or direct to ``align``."""
    from .core.changelog_parser import get_toolkit_version
    from .generation.schema_differ import (
        diff_spec_directory,
        stamp_specdev_version,
    )

    toolkit_version = get_toolkit_version(repo_root)
    if toolkit_version is None:
        return _toolkit_version_error(repo_root)

    stamp = read_stamp(spec_dir) or {}
    host_version = stamp.get("toolkit_version")

    if stamp.get("migration_status") == STATUS_IN_PROGRESS:
        return _migration_in_progress(spec_dir, repo_root, host_version, toolkit_version)

    if host_version == toolkit_version:
        return UpdateResult(
            exit_code=0,
            status="already_current",
            from_version=host_version,
            to_version=toolkit_version,
            message=f"Already at toolkit v{toolkit_version}. Nothing to do.",
        )

    # Versions differ — refresh deps before computing the diff so that any
    # newly-added toolkit dependencies are available for the subsequent steps.
    refresh_ok: Optional[bool] = None
    refresh_message = ""
    warnings: list[str] = []
    if not dry_run:
        toolkit_tools_dir = repo_root / "tools"
        refresh_ok, refresh_message = refresh_venv_installation(toolkit_tools_dir)
        if not refresh_ok:
            warnings.append(f"Dependency refresh skipped: {refresh_message}")

    # Compute diff (handles host_version=None for new/unrecorded projects)
    diff = diff_spec_directory(spec_dir, repo_root)

    data_reason = _data_migration_reason(host_version, toolkit_version, repo_root) if host_version else None
    if _needs_migration(diff.summary) or data_reason:
        s = diff.summary
        parts: list[str] = []
        if s.get("steps_missing", 0):
            parts.append(f"{s['steps_missing']} missing step(s)")
        if s.get("steps_needs_update", 0):
            parts.append(f"{s['steps_needs_update']} step(s) needing field updates")
        if s.get("steps_needs_rename", 0):
            parts.append(f"{s['steps_needs_rename']} step(s) needing rename")
        if s.get("paradigm_shifts", 0):
            parts.append(f"{s['paradigm_shifts']} paradigm shift(s)")
        details = "; ".join(found for found in (", ".join(parts), data_reason) if found)
        # `apply --auto` makes the changes a script knows (the migration runner); a missing step, a paradigm shift or a
        # field update the scripts do not make is not one of them: for those the prompts are the way forward.
        prompts = bool(s.get("paradigm_shifts", 0) or s.get("steps_missing", 0) or s.get("steps_needs_update", 0))
        return UpdateResult(
            exit_code=1,
            status="needs_migration",
            from_version=host_version,
            to_version=toolkit_version,
            needs_migration=True,
            migration_details=details,
            refresh_ok=refresh_ok,
            refresh_message=refresh_message,
            message=_migration_message(spec_dir, repo_root, details, host_version, toolkit_version, prompts),
            warnings=warnings,
            dry_run=dry_run,
        )

    # No structural schema changes — re-stamp only.
    from_ver = host_version or "unknown"
    if not dry_run:
        stamp_err = stamp_specdev_version(spec_dir, toolkit_version, is_migration=False)
        if stamp_err:
            return UpdateResult(
                exit_code=1,
                status="error",
                from_version=host_version,
                to_version=toolkit_version,
                refresh_ok=refresh_ok,
                refresh_message=refresh_message,
                message=f"Failed to write spec/specdev_version: {stamp_err}",
                warnings=warnings,
                dry_run=dry_run,
            )
        return UpdateResult(
            exit_code=0,
            status="updated",
            from_version=host_version,
            to_version=toolkit_version,
            refresh_ok=refresh_ok,
            refresh_message=refresh_message,
            message=f"spec/specdev_version updated: v{from_ver} → v{toolkit_version}",
            warnings=warnings,
            dry_run=dry_run,
        )

    # dry-run path
    return UpdateResult(
        exit_code=0,
        status="would_update",
        from_version=host_version,
        to_version=toolkit_version,
        refresh_ok=None,
        refresh_message="",
        message=f"[dry-run] Would update spec/specdev_version: v{from_ver} → v{toolkit_version}",
        warnings=warnings,
        dry_run=True,
    )
