#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

def _build_pre_commit_config(rel_toolkit_root: str, venv_name: str = "devspec_env") -> str:
    """Read the host pre-commit template and substitute the toolkit root path."""
    template_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "templates", "pre-commit-config.host.yaml",
    )
    template_path = os.path.abspath(template_path)
    if os.path.exists(template_path):
        with open(template_path) as f:
            content = f.read()
        # Replace ./devspec_toolkit (flags) and bare devspec_toolkit/ (files: patterns)
        content = content.replace("./devspec_toolkit", f"./{rel_toolkit_root}")
        content = content.replace("devspec_toolkit/", f"{rel_toolkit_root}/")
        content = content.replace("devspec_env", venv_name)
        return content
    # Fallback: minimal config if template is missing
    repo_root_flag = f"--repo-root ./{rel_toolkit_root}"
    return f"""# Pre-commit hooks — template not found, minimal config generated.
repos:
  - repo: local
    hooks:
      - id: spec-check
        name: Validate all spec files
        entry: {venv_name}/bin/python -m specdev_tools.cli spec-check spec {repo_root_flag} --spec-root ./spec --git-root .
        language: system
        pass_filenames: false
        files: spec/.*\\.json$
        types: [file]
"""

CI_WORKFLOW_TEMPLATE = """name: SpecDev CI

on:
  push:
    branches: ["**"]
  pull_request:
  workflow_dispatch:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  validate:
    name: Schema & Spec Validation
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          submodules: recursive
      - name: Setup uv
        uses: astral-sh/setup-uv@v8.1.0
      - name: Setup virtualenv & install tooling
        run: |
          uv python install 3.13
          uv venv devspec_env --python 3.13  # Matches default --venv-name
          # $GITHUB_PATH applies to LATER steps; this step targets the interpreter explicitly.
          echo "$PWD/devspec_env/bin" >> $GITHUB_PATH
          uv pip install --python devspec_env/bin/python -e devspec_toolkit/tools/
      - name: Validate all specs
        run: ./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
      - name: Governance check (PR Title)
        if: github.event_name == 'pull_request'
        run: ./tools/run_specdev.sh governance-check spec --message "${{ github.event.pull_request.title }}" --repo-root ./devspec_toolkit
      - name: Fixtures lint
        run: ./tools/run_specdev.sh fixtures-lint spec --repo-root ./devspec_toolkit
      - name: Build trace matrix
        run: ./tools/run_specdev.sh matrix spec --out trace_matrix.json --repo-root ./devspec_toolkit
      - name: Upload matrix
        uses: actions/upload-artifact@v4
        with:
          name: trace-matrix
          path: trace_matrix.json
          if-no-files-found: ignore
"""

def _render_ci_workflow(rel_toolkit_root: str, venv_name: str) -> str:
    """Render the CI workflow content with toolkit-path and venv-name substitutions."""
    content = CI_WORKFLOW_TEMPLATE
    content = content.replace("devspec_toolkit/tools", f"{rel_toolkit_root}/tools" if rel_toolkit_root != "." else "tools")
    content = content.replace("./devspec_toolkit", f"./{rel_toolkit_root}" if rel_toolkit_root != "." else ".")
    content = content.replace("devspec_env", venv_name)
    return content


def run_cmd(cmd, cwd=None, check=True):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=check)

def get_git_root(path):
    try:
        res = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def _find_seed_templates(toolkit_path, script_dir):
    # Priority 1: direct (standard submodule checkout)
    direct = os.path.join(toolkit_path, "seed_templates")
    if os.path.isdir(direct):
        return direct
    # Priority 2: nested (repo has inner devspec_toolkit/ folder)
    nested = os.path.join(toolkit_path, "devspec_toolkit", "seed_templates")
    if os.path.isdir(nested):
        return nested
    # Priority 3: relative to script location (running from source)
    source = os.path.abspath(os.path.join(script_dir, "..", "seed_templates"))
    if os.path.isdir(source):
        return source
    return None

def _get_toolkit_root(toolkit_path, script_dir):
    seed_dir = _find_seed_templates(toolkit_path, script_dir)
    if seed_dir:
        return os.path.dirname(seed_dir)
    return toolkit_path

def install_claude_symlinks(host_root, actual_toolkit_root, force=False):
    """Walk the toolkit's .claude/skills/ and .claude/agents/ directories and create
    relative symlinks under the host repo's .claude/skills/ and .claude/agents/.

    Symlinks (not copies) are used so the toolkit remains the single source of truth —
    skills stay current when the submodule is updated without requiring a re-init.

    Only entries in KNOWN_SKILLS / KNOWN_AGENT_PREFIXES are linked. If a new toolkit
    skill or agent should be exposed, add it to the allowlist below.

    Skills (directories) are linked as dir-to-dir; agents (.md files) as file-to-file.
    Dotfiles, lock files, and non-directory/non-md-file entries are skipped automatically.

    Idempotency rules:
    - Symlink already pointing at the correct relative target → skip (counted as "in sync").
    - Symlink pointing elsewhere → warn and skip unless ``force=True``, in which case
      the old symlink is removed and recreated.
    - Regular file or directory occupying the target name → always skip with a warning;
      never overwritten even with ``force=True``.

    Args:
        host_root (str): Absolute path to the host repo root (== args.target resolved).
        actual_toolkit_root (str): Absolute path to the resolved toolkit root.
        force (bool): When True, replace stale symlinks. Never removes real files/dirs.

    Returns:
        dict with counts: created_skills, created_agents, refreshed_skills,
        refreshed_agents, in_sync, skipped_conflict, skipped_manual, skipped_error.
    """
    # Allowlist of skills and agent name-prefixes to expose in the host repo.
    # Update this list when a new toolkit skill/agent should be propagated by default.
    KNOWN_SKILLS = {
        "specdev-context",
        "specdev-step",
        "specdev-review",
        "specdev-trinity",
        "specdev-trinity-plan",
        "devspec_pr_audit",
    }
    KNOWN_AGENT_PREFIXES = ("specdev-", "pr-audit-")
    toolkit_claude = os.path.join(actual_toolkit_root, ".claude")
    host_claude = os.path.join(host_root, ".claude")

    counts = {
        "created_skills": 0,
        "created_agents": 0,
        "refreshed_skills": 0,
        "refreshed_agents": 0,
        "in_sync": 0,
        "skipped_conflict": 0,
        "skipped_manual": 0,
        "skipped_error": 0,
    }

    # ---- skills (directories) ------------------------------------------------
    toolkit_skills_dir = os.path.join(toolkit_claude, "skills")
    host_skills_dir = os.path.join(host_claude, "skills")

    if os.path.isdir(toolkit_skills_dir):
        os.makedirs(host_skills_dir, exist_ok=True)
        for entry in sorted(os.listdir(toolkit_skills_dir)):
            if entry.startswith("."):
                continue
            if entry not in KNOWN_SKILLS:
                print(f"Warning: skipped skill {entry!r} (not in KNOWN_SKILLS allowlist; update init_project.py to expose it).")
                continue
            src_abs = os.path.join(toolkit_skills_dir, entry)
            if os.path.islink(src_abs) and not os.path.exists(src_abs):
                print(f"Warning: Broken symlink in toolkit skills dir: {src_abs!r}; skipping.")
                continue
            if not os.path.isdir(src_abs):
                # Not a directory → not a skill package, skip
                continue
            dst_abs = os.path.join(host_skills_dir, entry)
            rel_target = os.path.relpath(src_abs, start=os.path.dirname(dst_abs))
            result = _install_one_symlink(dst_abs, rel_target, force=force, label=f"skill '{entry}'")
            if result == "created":
                counts["created_skills"] += 1
            elif result == "refreshed":
                counts["refreshed_skills"] += 1
            elif result == "in_sync":
                counts["in_sync"] += 1
            elif result == "skipped_conflict":
                counts["skipped_conflict"] += 1
            elif result == "skipped_manual":
                counts["skipped_manual"] += 1
            elif result == "skipped_error":
                counts["skipped_error"] += 1
    else:
        print(f"Warning: toolkit has no .claude/skills/ directory at {toolkit_skills_dir}; skipping skills.")

    # ---- agents (.md files) --------------------------------------------------
    toolkit_agents_dir = os.path.join(toolkit_claude, "agents")
    host_agents_dir = os.path.join(host_claude, "agents")

    if os.path.isdir(toolkit_agents_dir):
        os.makedirs(host_agents_dir, exist_ok=True)
        for entry in sorted(os.listdir(toolkit_agents_dir)):
            if entry.startswith("."):
                continue
            if not entry.endswith(".md"):
                print(f"Warning: skipped non-.md agent entry {entry!r} (expected .md file; update init_project.py if this is intentional).")
                continue
            if not entry.startswith(KNOWN_AGENT_PREFIXES):
                print(f"Warning: skipped agent {entry!r} (not in KNOWN_AGENT_PREFIXES allowlist; update init_project.py to expose it).")
                continue
            src_abs = os.path.join(toolkit_agents_dir, entry)
            if os.path.islink(src_abs) and not os.path.exists(src_abs):
                print(f"Warning: Broken symlink in toolkit agents dir: {src_abs!r}; skipping.")
                continue
            if not os.path.isfile(src_abs):
                continue
            dst_abs = os.path.join(host_agents_dir, entry)
            rel_target = os.path.relpath(src_abs, start=os.path.dirname(dst_abs))
            result = _install_one_symlink(dst_abs, rel_target, force=force, label=f"agent '{entry}'")
            if result == "created":
                counts["created_agents"] += 1
            elif result == "refreshed":
                counts["refreshed_agents"] += 1
            elif result == "in_sync":
                counts["in_sync"] += 1
            elif result == "skipped_conflict":
                counts["skipped_conflict"] += 1
            elif result == "skipped_manual":
                counts["skipped_manual"] += 1
            elif result == "skipped_error":
                counts["skipped_error"] += 1
    else:
        print(f"Warning: toolkit has no .claude/agents/ directory at {toolkit_agents_dir}; skipping agents.")

    # ---- summary -------------------------------------------------------------
    print(
        f"Claude symlinks: Created {counts['created_skills']} skill symlink(s), "
        f"{counts['created_agents']} agent symlink(s). "
        f"Refreshed {counts['refreshed_skills']} skill symlink(s), "
        f"{counts['refreshed_agents']} agent symlink(s). "
        f"{counts['in_sync']} already in sync. "
        f"{counts['skipped_conflict']} skipped (stale symlink — rerun with --force-claude). "
        f"{counts['skipped_manual']} skipped (manual content — remove manually to allow linking)."
    )
    if counts["skipped_error"]:
        print(
            f"Warning: {counts['skipped_error']} symlink(s) could not be created due to OS errors "
            f"(check filesystem permissions; --force-claude does not help here)."
        )
    return counts


def _install_one_symlink(dst_abs, rel_target, force, label):
    """Create (or verify) a single symlink at ``dst_abs`` pointing to ``rel_target``.

    Returns one of: 'created', 'refreshed', 'in_sync', 'skipped_conflict',
    'skipped_manual', 'skipped_error'.  'refreshed' is returned when force=True
    replaced an existing stale symlink; 'created' is returned for net-new symlinks.
    """
    # lexists detects broken symlinks; os.path.exists() returns False for them.
    if os.path.lexists(dst_abs):
        if os.path.islink(dst_abs):
            existing = os.readlink(dst_abs)
            if existing == rel_target:
                # Already points to the correct target — nothing to do.
                return "in_sync"
            # Symlink exists but points elsewhere.
            if force:
                print(f"[force] Replacing stale symlink for {label}: {existing!r} → {rel_target!r}")
                # Remove and recreate inside one try so a failed symlink() doesn't
                # leave dst_abs missing (dangling-removal window closed).
                try:
                    os.remove(dst_abs)
                    os.symlink(rel_target, dst_abs)
                    print(f"Linked {label}: {dst_abs!r} → {rel_target!r}")
                    return "refreshed"
                except OSError as exc:
                    print(
                        f"Warning: Could not replace symlink for {label} at {dst_abs!r}: {exc}. "
                        f"On Windows, enable Developer Mode or run as administrator."
                    )
                    return "skipped_error"
            else:
                print(
                    f"Warning: Stale symlink for {label} at {dst_abs!r} points to {existing!r}; "
                    f"expected {rel_target!r}. Skipping (use --force-claude to replace)."
                )
                return "skipped_conflict"
        else:
            # Real file or directory — never overwrite.
            print(
                f"Warning: {label} target {dst_abs!r} is a real file/directory (not a symlink). "
                f"Remove it manually if you want the toolkit symlink installed here."
            )
            return "skipped_manual"

    # Create the symlink.
    try:
        os.symlink(rel_target, dst_abs)
        print(f"Linked {label}: {dst_abs!r} → {rel_target!r}")
        return "created"
    except OSError as exc:
        # Windows without Developer Mode raises PermissionError (OSError subclass).
        print(
            f"Warning: Could not create symlink for {label} at {dst_abs!r}: {exc}. "
            f"On Windows, enable Developer Mode or run as administrator."
        )
        return "skipped_error"


def copy_seeds_from_manifest(
    target_dir: str,
    seed_templates_dir: str,
    seed_manifest_path: str,
) -> set:
    """Copy .md seed templates into the locations declared in the manifest.

    Reads ``seeds[].path`` from *seed_manifest_path*, builds a stem→declared-path
    map, derives unique seed parent directories, creates them if necessary, then
    copies each ``.md`` template from *seed_templates_dir* to its manifest-declared
    destination (relative to *target_dir*).

    Templates with no manifest entry fall back to the lexicographically first seed
    parent directory (deterministic across multiple declared parent dirs).  When the
    manifest is absent or unparseable the fallback directory is ``docs/seed/``.

    Existing destination files are never overwritten.

    Args:
        target_dir: Absolute path to the host repo root (copy destinations are
            relative to this directory).
        seed_templates_dir: Directory containing the ``.md`` template files.
        seed_manifest_path: Path to the (already-copied) ``seed_manifest.json``.

    Returns:
        The set of absolute destination paths where files were copied (excludes
        destinations that were skipped because they already existed).
    """
    import json as _json

    stem_to_declared_path: dict = {}
    if os.path.isfile(seed_manifest_path):
        try:
            with open(seed_manifest_path, "r", encoding="utf-8") as _mf:
                _manifest_data = _json.load(_mf)
            for _seed_entry in _manifest_data.get("seeds", []):
                _rel = _seed_entry.get("path", "")
                if _rel:
                    _stem = os.path.splitext(os.path.basename(_rel))[0]
                    stem_to_declared_path[_stem] = _rel
        except (OSError, _json.JSONDecodeError):
            pass  # fall back to docs/seed/ default below

    if stem_to_declared_path:
        seed_parent_dirs = {
            os.path.join(target_dir, os.path.dirname(p))
            for p in stem_to_declared_path.values()
        }
    else:
        seed_parent_dirs = {os.path.join(target_dir, "docs", "seed")}

    for _seed_dir in seed_parent_dirs:
        if not os.path.exists(_seed_dir):
            print(f"Creating {os.path.relpath(_seed_dir, target_dir)}/ directory...")
            os.makedirs(_seed_dir)

    # Deterministic fallback — sorted() ensures a stable choice when the manifest
    # declares multiple distinct parent directories.
    fallback_seed_dir = sorted(seed_parent_dirs)[0]

    copied: set = set()
    for item in os.listdir(seed_templates_dir):
        s = os.path.join(seed_templates_dir, item)
        if os.path.isfile(s):
            # Only copy Markdown templates — seed_manifest.json belongs in
            # spec/common/ (handled above in step 3a), not in a seed dir.
            if not item.endswith(".md"):
                continue
            stem = os.path.splitext(item)[0]
            if stem in stem_to_declared_path:
                # Copy to the path declared in the manifest (authoritative)
                d = os.path.join(target_dir, stem_to_declared_path[stem])
            else:
                # Template file has no manifest entry — fall back to the
                # first declared seed parent dir (or docs/seed/ default)
                d = os.path.join(fallback_seed_dir, item)
            if not os.path.exists(d):
                print(f"Copying {item} to {os.path.relpath(d, target_dir)}...")
                shutil.copy2(s, d)
                copied.add(d)
            else:
                print(f"Skipping {item} (already exists)")
    return copied


def main():
    parser = argparse.ArgumentParser(description="Initialize DevSpec Toolkit in a project")
    parser.add_argument("--target", default=".", help="Target project directory")
    parser.add_argument("--toolkit-url", default="https://github.com/vichitra-studio/devspec_toolkit.git", help="URL of the devspec_toolkit repo")
    parser.add_argument("--toolkit-root", help="Explicit path to devspec_toolkit source directory")
    parser.add_argument("--venv-name", default="devspec_env", help="Name for the virtual environment (default: devspec_env)")
    parser.add_argument("--strict", action="store_true", help="Enable strict governance (commit-msg hooks)")
    parser.add_argument(
        "--force-claude",
        action="store_true",
        # Scoped deliberately: wrapper-script and seed-template copies have no force path
        # (they are skip-if-exists idempotent). Only symlink installs support forced replacement.
        help="Replace stale .claude/skills/ and .claude/agents/ symlinks (never overwrites real files/dirs).",
    )
    args = parser.parse_args()

    target_dir = os.path.abspath(args.target)

    if not os.path.exists(target_dir):
        print(f"Error: Target directory {target_dir} does not exist.")
        sys.exit(1)

    # Fail fast if uv is missing: the environment setup (step 6) is uv-driven, so
    # check up front rather than scaffolding a half-built repo and erroring out later.
    if shutil.which("uv") is None:
        print(
            "Error: 'uv' is not installed, but it is required to set up the "
            "Python 3.13 environment.\n"
            "Install it (user-local; does not touch system Python):\n"
            "  curl -LsSf https://astral.sh/uv/install.sh | sh\n"
            "  (or: brew install uv)",
            file=sys.stderr,
        )
        sys.exit(1)

    # 1. Check if git repo
    git_root = get_git_root(target_dir)
    if not git_root:
        print("Initializing git repo...")
        run_cmd(["git", "init"], cwd=target_dir)
        git_root = target_dir
    else:
        # Ensure we are at root if possible, or just work relative
        pass

    # 2. Add Submodule
    toolkit_path = os.path.abspath(args.toolkit_root) if args.toolkit_root else os.path.join(target_dir, "devspec_toolkit")
    
    if args.toolkit_root:
        print(f"Using explicit toolkit root at {toolkit_path}. Skipping submodule add.")
    elif os.path.exists(toolkit_path):
        print("devspec_toolkit directory already exists. Skipping submodule add.")
    else:
        print(f"Adding submodule from {args.toolkit_url}...")
        try:
            run_cmd(["git", "submodule", "add", args.toolkit_url, "devspec_toolkit"], cwd=target_dir)
            run_cmd(["git", "submodule", "update", "--init", "--recursive"], cwd=target_dir)
        except subprocess.CalledProcessError as e:
            print(f"Failed to add submodule: {e}")
            print("Please check the URL, your network connection, or if 'devspec_toolkit' matches .gitignore.")
            print("If a partial directory exists, try: rm -rf devspec_toolkit")
            sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    actual_toolkit_root = _get_toolkit_root(toolkit_path, script_dir)

    # 3. Init spec/ directory
    spec_dir = os.path.join(target_dir, "spec")
    if not os.path.exists(spec_dir):
        print("Creating spec/ directory...")
        os.makedirs(spec_dir)
        # Create .gitkeep
        with open(os.path.join(spec_dir, ".gitkeep"), "w") as f:
            f.write("")
    else:
        print("spec/ directory already exists.")

    # 3a. Init spec/common/ directory and seed manifest
    spec_common_dir = os.path.join(spec_dir, "common")
    if not os.path.exists(spec_common_dir):
        print("Creating spec/common/ directory...")
        os.makedirs(spec_common_dir)
    else:
        print("spec/common/ directory already exists.")

    seed_manifest_target = os.path.join(spec_common_dir, "seed_manifest.json")
    if not os.path.exists(seed_manifest_target):
        manifest_src = os.path.join(actual_toolkit_root, "seed_templates", "seed_manifest.json")
        if os.path.exists(manifest_src):
            print("Copying seed_manifest.json to spec/common/...")
            shutil.copy2(manifest_src, seed_manifest_target)
        else:
            print("Warning: seed_manifest.json template not found. Please add it manually to spec/common/.")
    else:
        print("spec/common/seed_manifest.json already exists.")

    # 3b. Init spec/canon/ directory (project-level canonical registry)
    spec_canon_dir = os.path.join(spec_dir, "canon")
    if not os.path.exists(spec_canon_dir):
        print("Creating spec/canon/ directory...")
        os.makedirs(spec_canon_dir)
        kinds_dir = os.path.join(spec_canon_dir, "kinds")
        os.makedirs(kinds_dir)
        manifest = {
            "$schema": "vc:core:canon",
            "registry_version": "1.0.0",
            "entries": [],
            "aliases": [],
        }
        manifest_path = os.path.join(spec_canon_dir, "manifest.json")
        import json as _json
        with open(manifest_path, "w", encoding="utf-8") as f:
            _json.dump(manifest, f, indent=2)
            f.write("\n")
    else:
        print("spec/canon/ directory already exists.")

    # 3c. Init spec/impl_context/ directory
    impl_context_dir = os.path.join(spec_dir, "impl_context")
    if not os.path.exists(impl_context_dir):
        print("Creating spec/impl_context/ directory...")
        os.makedirs(impl_context_dir)
        # Create .gitkeep
        with open(os.path.join(impl_context_dir, ".gitkeep"), "w") as f:
            f.write("")
    else:
        print("spec/impl_context/ directory already exists.")

    # 3d. Write spec/specdev_version (idempotent — only if not already present)
    specdev_version_path = os.path.join(spec_dir, "specdev_version")
    if not os.path.exists(specdev_version_path):
        print("Creating spec/specdev_version...")
        # Read toolkit version directly from pyproject.toml (package may not be installed yet)
        _toolkit_root = Path(__file__).resolve().parent.parent
        _pyproject = _toolkit_root / "tools" / "pyproject.toml"
        _toolkit_ver = None
        try:
            import tomllib as _tomllib  # type: ignore[import-not-found]  # Python 3.11+
        except ModuleNotFoundError:
            _tomllib = None  # type: ignore[assignment]
        if _pyproject.exists():
            if _tomllib is not None:
                with open(_pyproject, "rb") as _f:
                    _toml_data = _tomllib.load(_f)
                _toolkit_ver = _toml_data.get("project", {}).get("version")
            else:
                import re as _re
                with open(_pyproject, "r", encoding="utf-8") as _f:
                    _lines = _f.readlines()
                _in_project = False
                for _line in _lines:
                    _stripped = _line.strip()
                    if _stripped == "[project]":
                        _in_project = True
                        continue
                    if _stripped.startswith("[") and _stripped != "[project]":
                        _in_project = False
                        continue
                    if _in_project and _stripped.startswith("version"):
                        _m = _re.search(r'version\s*=\s*["\']([^"\']+)["\']', _stripped)
                        if _m:
                            _toolkit_ver = _m.group(1)
                            break
        if _toolkit_ver is None:
            print(
                f"ERROR: could not determine toolkit version from {_pyproject}; "
                "cannot stamp spec/specdev_version. Aborting init.",
                file=sys.stderr,
            )
            sys.exit(1)
        _ver_str = _toolkit_ver
        import datetime as _datetime
        _created_at = _datetime.datetime.now(_datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(specdev_version_path, "w", encoding="utf-8") as _svf:
            _svf.write(
                f'toolkit_version: "{_ver_str}"\n'
                f'created_at: "{_created_at}"\n'
                f'last_migration: null\n'
                f'migration_history: []\n'
            )
    else:
        print("spec/specdev_version already exists.")

    # 4. Init seed directories and copy templates, deriving locations from the
    #    template manifest's seeds[].path rather than hardcoding docs/seed/.
    #    This honours the North Star: seed_manifest.json is authoritative for
    #    seed routing AND location.  seed_manifest.json was already copied in
    #    step 3a so it is available here.

    # 4a. Emit wrapper scripts for venv-enforced CLI usage
    tools_dir = os.path.join(target_dir, "tools")
    if not os.path.exists(tools_dir):
        print("Creating tools/ directory...")
        os.makedirs(tools_dir)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    wrapper_templates_dir = os.path.join(script_dir, "templates")
    run_specdev_src = os.path.join(wrapper_templates_dir, "run_specdev.sh")
    ensure_venv_src = os.path.join(wrapper_templates_dir, "ensure_venv.py")

    run_specdev_target = os.path.join(tools_dir, "run_specdev.sh")
    ensure_venv_target = os.path.join(tools_dir, "ensure_venv.py")

    if os.path.exists(run_specdev_src) and not os.path.exists(run_specdev_target):
        print("Creating tools/run_specdev.sh...")
        shutil.copy2(run_specdev_src, run_specdev_target)
        os.chmod(run_specdev_target, 0o755)
    elif os.path.exists(run_specdev_target):
        print("tools/run_specdev.sh already exists.")
    else:
        print("Warning: run_specdev.sh template not found; skipping.")

    if os.path.exists(ensure_venv_src) and not os.path.exists(ensure_venv_target):
        print("Creating tools/ensure_venv.py...")
        shutil.copy2(ensure_venv_src, ensure_venv_target)
    elif os.path.exists(ensure_venv_target):
        print("tools/ensure_venv.py already exists.")
    else:
        print("Warning: ensure_venv.py template not found; skipping.")

    seed_templates_dir = _find_seed_templates(toolkit_path, script_dir)
    if seed_templates_dir:
        print(f"Found seed templates at {seed_templates_dir}")
        copy_seeds_from_manifest(target_dir, seed_templates_dir, seed_manifest_target)
    else:
        print("Warning: Seed templates not found. Could not copy seed templates.")

    rel_toolkit_root = os.path.relpath(actual_toolkit_root, target_dir).replace("\\", "/")

    # Detect if toolkit is a git submodule
    is_submodule = os.path.isfile(os.path.join(actual_toolkit_root, ".git")) or (
        os.path.isfile(os.path.join(target_dir, ".gitmodules"))
    )

    # 4b. Install .claude/skills/ and .claude/agents/ symlinks into the host repo
    print("Installing Claude Code skill/agent symlinks...")
    install_claude_symlinks(target_dir, actual_toolkit_root, force=args.force_claude)
    print(
        "Note: Symlinks at .claude/skills/ and .claude/agents/ should be committed; "
        "submodule bumps will track upstream."
    )
    if is_submodule:
        print(
            "Note: Symlinks point into the devspec_toolkit submodule; "
            "removing the submodule will dangle them."
        )

    # 5. Hook setup (Pre-commit)
    pre_commit_file = os.path.join(target_dir, ".pre-commit-config.yaml")
    if not os.path.exists(pre_commit_file):
        print("Creating .pre-commit-config.yaml...")
        config_content = _build_pre_commit_config(rel_toolkit_root, args.venv_name)
        with open(pre_commit_file, "w") as f:
            f.write(config_content)
        print("Note: pre-commit will be installed into the virtualenv and 'pre-commit install' run automatically.")
    else:
        print(".pre-commit-config.yaml exists. Please manually ensure devspec hooks are configured.")

    # 6. Setup Virtual Environment (uv-managed Python 3.13) via the shared primitive.
    # setup_devspec_env.sh provisions a managed CPython 3.13, (re)creates the venv, and
    # installs the toolkit + deps editable from pyproject.toml. It is idempotent (reuses
    # an existing 3.13 venv), so no exists/else split is needed here. macOS/Linux only.
    venv_name = args.venv_name
    venv_dir = os.path.join(target_dir, venv_name)
    setup_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup_devspec_env.sh")
    print(f"Setting up virtual environment '{venv_name}' (uv / Python 3.13)...")
    run_cmd(
        ["bash", setup_script,
         "--tools-dir", os.path.join(actual_toolkit_root, "tools"),
         "--venv-name", venv_name],
        cwd=target_dir,
    )

    venv_bin = os.path.join(venv_dir, "bin")

    # pre-commit is a host-repo dev tool (not a toolkit runtime dep), so install it
    # into the venv explicitly. --python targets the venv interpreter (no activation needed).
    print("Installing pre-commit into the virtual environment...")
    run_cmd(
        ["uv", "pip", "install", "pre-commit",
         "--python", os.path.join(venv_bin, "python")],
        cwd=target_dir,
    )

    # 7. Setup Git Hooks (Always run/check)
    print("Ensuring git hooks are installed...")
    pre_commit_bin = os.path.join(venv_bin, "pre-commit")
    if os.path.exists(pre_commit_bin):
        # Run pre-commit install (basic)
        run_cmd([pre_commit_bin, "install"], cwd=target_dir)
        
        # If strict mode, install commit-msg hook
        if args.strict:
            print("Strict mode enabled: Installing commit-msg hook...")
            run_cmd([pre_commit_bin, "install", "--hook-type", "commit-msg"], cwd=target_dir)
            
            # Append governance commit-msg hook if not already present
            config_path = os.path.join(target_dir, ".pre-commit-config.yaml")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config_content = f.read()
                if "devspec-governance" not in config_content:
                    print("Enabling governance check in pre-commit config...")
                    repo_root_flag = f"--repo-root ./{rel_toolkit_root}"
                    governance_hook = f"""      - id: devspec-governance
        name: DevSpec Governance Check
        entry: {venv_name}/bin/python -m specdev_tools.cli governance-check spec {repo_root_flag} --spec-root ./spec --git-root . --message
        language: system
        pass_filenames: true
        stages: [commit-msg]
"""
                    with open(config_path, "a") as f:
                        f.write(governance_hook)
    else:
        print(f"Warning: pre-commit binary not found in {venv_name}. Skipping hook install.")

    # 7b. Generate CI Workflow
    workflows_dir = os.path.join(target_dir, ".github", "workflows")
    if not os.path.exists(workflows_dir):
        os.makedirs(workflows_dir)
    
    ci_file = os.path.join(workflows_dir, "spec_validation.yml")
    if not os.path.exists(ci_file):
        print("Creating CI workflow .github/workflows/spec_validation.yml...")
        ci_content = _render_ci_workflow(rel_toolkit_root, venv_name)
        # Add submodule-aware flags to CI commands
        if is_submodule:
            ci_content = ci_content.replace(
                f"--repo-root ./{rel_toolkit_root}",
                f"--repo-root ./{rel_toolkit_root} --spec-root ./spec --git-root .",
            )
        with open(ci_file, "w") as f:
            f.write(ci_content)
    else:
        print("CI workflow already exists.")

    # 8. Gitignore
    gitignore_path = os.path.join(target_dir, ".gitignore")
    ignore_entry = f"{venv_name}/"
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            content = f.read()
        if ignore_entry not in content:
            print(f"Adding {venv_name}/ to .gitignore...")
            with open(gitignore_path, "a") as f:
                f.write(f"\n{ignore_entry}\n")
    else:
        print(f"Creating .gitignore with {venv_name}/...")
        with open(gitignore_path, "w") as f:
            f.write(f"{ignore_entry}\n")

    # 9. Update README
    readme_path = os.path.join(target_dir, "README.md")
    setup_docs = f"""
## Development Setup
This project uses the [DevSpec Toolkit](https://github.com/vichitracollective/devspec_toolkit) for specification-driven development.

1. **Activate Environment**:
   ```bash
   source {venv_name}/bin/activate
   ```
2. **Run Toolkit Commands**:
   ```bash
   ./tools/run_specdev.sh --help
   ```
"""
    if not os.path.exists(readme_path):
        print("Creating README.md...")
        with open(readme_path, "w") as f:
            f.write(f"# Project\n{setup_docs}")
    else:
        with open(readme_path, "r") as f:
            content = f.read()
        if "## Development Setup" not in content:
            print("Appending Development Setup to README.md...")
            with open(readme_path, "a") as f:
                f.write(f"\n{setup_docs}")
        else:
             print("README.md already contains Development Setup.")

    print("\nInitialization complete!")
    print("Next steps:")
    print("1. Fill out the seed files declared in spec/common/seed_manifest.json")
    print(f"2. Activate your environment: source {venv_name}/bin/activate")
    print("3. Start your first spec or run `./tools/run_specdev.sh --help`")

if __name__ == "__main__":
    main()
