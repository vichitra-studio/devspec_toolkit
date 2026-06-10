"""specdev update — sync a project to the current toolkit version.

Thin orchestrator that:
1. Resolves host version (spec/specdev_version) and toolkit version (pyproject.toml).
2. Short-circuits when already current.
3. Refreshes the venv installation via uv (handles uv-absent and wrong-Python edges).
4. Computes the schema diff.
5. Re-stamps spec/specdev_version when no structural changes are required,
   or directs the user to run ``specdev align`` when migration is needed.

Only structural changes block a plain re-stamp:
  steps_missing | steps_needs_update | steps_needs_rename | paradigm_shifts > 0
Unknown steps (user extensions) and extension steps never block a re-stamp.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class UpdateResult:
    """Structured result returned by run_update()."""

    exit_code: int
    status: str  # "already_current" | "updated" | "would_update" | "needs_migration" | "error"
    from_version: Optional[str]
    to_version: Optional[str]
    needs_migration: bool = False
    migration_details: str = ""
    refresh_ok: Optional[bool] = None       # None → skipped (already current / dry-run)
    refresh_message: str = ""
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False


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


def run_update(
    spec_dir: Path,
    repo_root: Path,
    dry_run: bool = False,
) -> UpdateResult:
    """Core update logic — sync project to the current toolkit version.

    Args:
        spec_dir: Absolute path to the project's spec/ directory.
        repo_root: Absolute path to the toolkit root (contains tools/pyproject.toml).
        dry_run: When True, report what would be done without writing any files.

    Returns:
        An UpdateResult describing outcome and exit code.
    """
    from .core.changelog_parser import get_toolkit_version
    from .generation.schema_differ import (
        diff_spec_directory,
        get_user_version,
        stamp_specdev_version,
    )

    toolkit_version = get_toolkit_version(repo_root)
    if toolkit_version is None:
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

    host_version = get_user_version(spec_dir)

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

    if _needs_migration(diff.summary):
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

        details = ", ".join(parts)
        # Build remediation commands. `--repo-root` is mandatory in submodule
        # deployments so align can find the toolkit schemas.
        align_lines = [
            f"  specdev align apply {spec_dir} --auto --repo-root {repo_root}",
        ]
        # `apply --auto` provably handles only two things: renames and
        # SCHEMA_REF_OUTDATED field diffs.  Any other field update
        # (TYPE_MISMATCH, MISSING_REQUIRED, EXTRA_FIELD) is auto_fixable=False,
        # so steps_needs_update > 0 may include cases that apply --auto cannot
        # clear.  Paradigm shifts and missing steps are always non-auto-fixable.
        # For all three, guide the user to `align prompts` (generate prompts,
        # then paste the AI output into the target spec files).
        if (
            s.get("paradigm_shifts", 0) > 0
            or s.get("steps_missing", 0) > 0
            or s.get("steps_needs_update", 0) > 0
        ):
            align_lines.append(
                f"  specdev align prompts {spec_dir} --output prompts/migration/"
                f" --mode upgrade --repo-root {repo_root}"
            )
        # Finalize with `align validate`, NOT a re-run of `update`.  validate runs
        # full post-migration validation (schema compliance + trace integrity) and
        # stamps spec/specdev_version with a migration_history entry + last_migration
        # timestamp (is_migration=True).  Re-running `update` would only re-stamp
        # (is_migration=False) after a weaker structural-diff check — losing the audit
        # trail and risking marking a half-migrated spec as "current".
        align_lines.append(
            f"  specdev align validate {spec_dir} --repo-root {repo_root}"
        )
        return UpdateResult(
            exit_code=1,
            status="needs_migration",
            from_version=host_version,
            to_version=toolkit_version,
            needs_migration=True,
            migration_details=details,
            refresh_ok=refresh_ok,
            refresh_message=refresh_message,
            message=(
                f"Schema changes detected ({details}).\n"
                f"Run schema migration:\n" + "\n".join(align_lines)
            ),
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
