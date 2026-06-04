"""Monolithic CLI dispatcher for all specdev-tools subcommands.

This module wires up every subcommand (validate, canonical-lint, align, etc.)
in a single ``main()`` function.  A future refactor could split the dispatch
into per-subpackage command groups (validation, canonical, generation,
migration) to improve readability and testability (see AUDIT-064).

.. note::

   There are ~128 ``print()`` calls that should eventually migrate to the
   ``logging`` module so output verbosity can be controlled centrally.
   TODO: replace print() with logging in a future pass (AUDIT-065).
"""
from __future__ import annotations
import argparse, os, json, re, sys
from collections.abc import Sequence
from pathlib import Path
# Lazy imports handled inside main/command blocks to improve CLI responsiveness

from .core.config import get_config, reset_config
from .core.errors import SpecError

WARNING_CODE_RE = re.compile(r"^\s*W\d{3}\b")
# Also match warnings prefixed with file paths (e.g., "spec/05_x.json: W590 ...")
WARNING_CODE_PREFIXED_RE = re.compile(r"^[^\s]*:\s*W\d{3}\b")


def _is_warning_message(message: str | SpecError) -> bool:
    if not message:
        return False
    if isinstance(message, SpecError):
        return message.code.startswith("W")
    return bool(WARNING_CODE_RE.match(message) or WARNING_CODE_PREFIXED_RE.match(message))


def _warnings_as_errors() -> bool:
    return get_config().warnings_as_errors


def _has_error_messages(messages: Sequence[str | SpecError]) -> bool:
    if _warnings_as_errors():
        return bool(messages)
    def _is_err(m: str | SpecError) -> bool:
        if isinstance(m, SpecError):
            return not m.code.startswith("W")
        return not _is_warning_message(m)
    return any(_is_err(m) for m in messages)
def _print_and_exit_if_errors(errs: Sequence[str | SpecError]) -> None:
    if errs:
        for e in errs:
            line = e.render() if isinstance(e, SpecError) else e
            print(line, file=sys.stderr)
    if _has_error_messages(errs):
        sys.exit(1)
    if errs:
        print("OK (warnings)")
    else:
        print("OK")


def _json_exit(
    errs: Sequence[str | SpecError],
    command: str,
    extra_context: dict | None = None,
) -> None:
    """Print JSON-formatted output and exit with appropriate code.

    Converts any raw-string errors to ``SpecError`` via ``ensure_spec_errors``,
    then delegates to ``format_errors_json`` for deterministic output.
    """
    from .core.errors import ensure_spec_errors
    from .core.json_output import format_errors_json

    spec_errors = ensure_spec_errors(errs)
    ctx: dict = {"command": command}
    if extra_context:
        ctx.update(extra_context)
    print(format_errors_json(spec_errors, context=ctx))
    has_err = any(not e.code.startswith("W") for e in spec_errors)
    if _warnings_as_errors() and spec_errors:
        sys.exit(1)
    if has_err:
        sys.exit(1)
    sys.exit(0)


def _discover_project_canon_dir(
    git_root: str | None = None,
    spec_root: str | None = None,
    spec_dir: str | None = None,
) -> str | None:
    """Discover project-level canon directory from git_root, spec_root, or spec_dir.

    Returns an absolute path to the project canon dir if it exists, else None.
    """
    candidates: list[str] = []
    if git_root:
        candidates.append(os.path.join(os.path.abspath(git_root), "spec", "canon"))
    if spec_root:
        candidates.append(os.path.join(os.path.abspath(spec_root), "canon"))
    if spec_dir:
        candidates.append(os.path.join(os.path.abspath(spec_dir), "canon"))
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None


def _derive_step_names(repo_root: str) -> dict[str, str]:
    """Derive step ID -> display name mapping from schema_registry.json.

    Falls back to a minimal mapping if the registry cannot be loaded.
    The schema registry keys follow the pattern ``vc:NN-name``; this function
    extracts the step number and converts the kebab-case name to Title Case.
    Keys like ``vc:core:...`` or ``vc:canon:...`` are intentionally skipped.
    """
    registry_path = os.path.join(repo_root, "tools", "schema_registry.json")
    names: dict[str, str] = {}
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
        step_re = re.compile(r"^vc:(\d{2}[a-z]?)-(.+)$")
        for uri in registry:
            m = step_re.search(uri)
            if m:
                step_id = m.group(1)
                raw_name = m.group(2).replace("-", " ").title()
                if step_id not in names:
                    names[step_id] = raw_name
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        pass
    return names


def check_venv():
    # Helper to check if we are running in a virtual environment
    # sys.prefix != sys.base_prefix is the standard check for venv/virtualenv
    if sys.prefix == sys.base_prefix:
        print("Error: Running without a virtual environment. Please activate 'devspec_env' or similar.", file=sys.stderr)
        sys.exit(1)

def main():
    # --version must bypass venv check so it works in any environment.
    # We short-circuit here before check_venv() and before argparse, because
    # required=True on add_subparsers would otherwise reject bare --version.
    if "--version" in sys.argv[1:]:
        _toolkit_root = Path(__file__).resolve().parent.parent.parent
        from .core.changelog_parser import get_toolkit_version as _gtv
        _ver = _gtv(_toolkit_root) or "unknown"
        print(f"specdev {_ver}")
        sys.exit(0)

    check_venv()
    # Reset config singleton so each CLI invocation reads current env vars
    reset_config()
    p = argparse.ArgumentParser(prog="specdev-tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate")
    v.add_argument("file")
    v.add_argument("--repo-root", default=".")
    v.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    v.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    v.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    va = sub.add_parser("validate-all")
    va.add_argument("spec_dir")
    va.add_argument("--repo-root", default=".")
    va.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    va.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    va.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    m = sub.add_parser("matrix")
    m.add_argument("spec_dir")
    # Default: write to <spec_dir>/extras/trace_matrix.json (resolved at action
    # time once spec_dir is known). Pass --out - explicitly for stdout, or
    # --out <path> for a non-canonical location.
    m.add_argument("--out", default=None)
    m.add_argument("--repo-root", default=".")
    m.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    m.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    m.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    fx = sub.add_parser("fixtures-lint")
    fx.add_argument("spec_dir")
    fx.add_argument("--repo-root", default=".")
    fx.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    fx.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    fx.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    inv = sub.add_parser("invariants-check")
    inv.add_argument("spec_dir")
    inv.add_argument("--sample", required=True)
    inv.add_argument("--repo-root", default=".")
    inv.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    inv.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    inv.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")
    inv.add_argument("--strict", action="store_true", help="Promote unevaluable rules to errors (also: SPECDEV_INVARIANTS_STRICT=1)")

    sl = sub.add_parser("seed-lint")
    sl.add_argument("spec_dir")
    sl.add_argument("--repo-root", default=".")
    sl.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    sl.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    sl.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    si = sub.add_parser("seed-index")
    si.add_argument("spec_dir")
    si.add_argument("--repo-root", default=".")
    si.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    si.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    ps = sub.add_parser("prompt-sync")
    ps.add_argument("spec_dir", nargs="?")
    ps.add_argument("--repo-root", default=".")
    ps.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    ps.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    ps.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    cl = sub.add_parser("canonical-lint")
    cl.add_argument("canon_dir", nargs="?", default="canon")
    cl.add_argument("--repo-root", default=".")
    cl.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    cl.add_argument("--git-root", default=None, help="Host repo git root (for two-tier canon)")
    cl.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    ci = sub.add_parser("canonical-integrity")
    ci.add_argument("spec_dir")
    ci.add_argument("--repo-root", default=".")
    ci.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    ci.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    ci.add_argument("--canon-dir", default="canon")
    ci.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    ca = sub.add_parser("canonical-autofix")
    ca.add_argument("spec_dir")
    ca.add_argument("--repo-root", default=".")
    ca.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    ca.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    ca.add_argument("--canon-dir", default="canon")
    ca_mode = ca.add_mutually_exclusive_group()
    ca_mode.add_argument("--write", action="store_true", help="Write changes to files")
    ca_mode.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    ca.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    sql = sub.add_parser("spec-quality-lint")
    sql.add_argument("spec_dir")
    sql.add_argument("--repo-root", default=".")
    sql.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    sql.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    sql.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    hl = sub.add_parser("hallucination-lint")
    hl.add_argument("spec_dir")
    hl.add_argument("--repo-root", default=".")
    hl.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    hl.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    hl.add_argument("--canon-dir", default="canon")
    hl.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    gd = sub.add_parser(
        "glossary-drift-check",
        help="Validate definition parity across glossary terms, proposals, and canon registry.",
    )
    gd.add_argument("spec_dir", help="Path to the spec directory (e.g. spec/)")
    gd.add_argument("--repo-root", default=".", help="Toolkit repo root (default: .)")
    gd.add_argument("--spec-root", default=None, help="Host repo spec root for submodule deployments")
    gd.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    gd.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")

    tc = sub.add_parser("traceability-check")
    tc.add_argument("spec_dir")
    tc.add_argument("--repo-root", default=".")
    tc.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    tc.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    tc.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    cc = sub.add_parser("completeness-check", help="Run pairwise completeness checks (W564–W568) and report coverage ratios")
    cc.add_argument("spec_dir")
    cc.add_argument("--repo-root", default=".")
    cc.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    cc.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    cc.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    sc = sub.add_parser("spec-check", help="Run all applicable validation/lint checks in one pass with per-check breakdown")
    sc.add_argument("spec_dir")
    sc.add_argument("--repo-root", default=".")
    sc.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    sc.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    sc.add_argument("--include-forward-replay", action="store_true", default=False, help="Include forward-replay check")
    sc.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    rc = sub.add_parser("registry-check", help="Validate entry_key_registry.json: coverage, phantom basenames, and drift")
    rc.add_argument("--spec-root", required=True, help="Project spec directory (used for R003 drift check against live spec files)")
    rc.add_argument("--repo-root", default=".")
    rc.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    rc.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    rg = sub.add_parser(
        "registry-generate",
        help="Regenerate the entry-key registry and extraction-paths from toolkit schemas.",
        description=(
            "Regenerate the entry-key registry and extraction-paths from toolkit schemas.\n\n"
            "Output is byte-deterministic across runs (sort_keys + indent=2 + trailing newline)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rg.add_argument(
        "--repo-root",
        required=True,
        help="Toolkit root directory containing schema/ and tools/ (required).",
    )
    rg.add_argument(
        "--out",
        default=None,
        help="Output path for entry_key_registry.json (default: <repo-root>/tools/entry_key_registry.json).",
    )
    rg.add_argument(
        "--extraction-paths-out",
        default=None,
        dest="extraction_paths_out",
        help="Output path for extraction_paths.json (default: <repo-root>/tools/extraction_paths.json).",
    )

    gd = sub.add_parser("guide", help="Show remediation guide for an error code")
    gd.add_argument("code", help="Error code to look up, e.g. E110 or E530-INVENTED_ENUM_OR_ID")
    gd.add_argument("--repo-root", default=".", help="Toolkit root directory (unused for resolution, accepted for consistency)")
    gd.add_argument("--json", action="store_true", help="Output result as JSON", dest="json_output")


    dol = sub.add_parser("dependency-order-lint")
    dol.add_argument("--repo-root", default=".")
    dol.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    frc = sub.add_parser("forward-replay-check")
    frc.add_argument("--repo-root", default=".")
    frc.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    frc.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    frc.add_argument("--base-ref", help="Diff base ref (default: auto-resolved in validate-all)")
    frc.add_argument("--diff-error-mode", choices=["error", "ignore"], default="error")
    frc.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    gov = sub.add_parser("governance-check")
    gov.add_argument("spec_dir")
    gov.add_argument("--message", required=True)
    gov.add_argument("--repo-root", default=".")
    gov.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    gov.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")
    gov.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    ai = sub.add_parser("ai-help")
    ai.add_argument("--step", help="Specific step to get help for")
    ai.add_argument("--repo-root", default=".", help="Toolkit root directory")
    ai.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    # Changelog commands (Phase 2: Changelog Parser)
    ch = sub.add_parser("changelog", help="Changelog and version utilities")
    ch.add_argument("--list", action="store_true", help="List all available versions")
    ch.add_argument("--version", help="Show details for a specific version")
    ch.add_argument("--validate", help="Validate a version's changelog")
    ch.add_argument("--repo-root", default=".")
    ch.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    # Align commands (Phase 3-6: Schema Differ + Apply + Prompts)
    al = sub.add_parser("align", help="Toolkit alignment and migration")
    al.add_argument("action", choices=["status", "diff", "plan", "apply", "prompts", "rollback", "validate"],
                    help="Alignment action")
    al.add_argument("spec_dir", help="Path to user spec/ directory")
    al.add_argument("--repo-root", default=".", help="Toolkit root directory")
    al.add_argument("--auto", action="store_true", help="Apply only auto-fixable changes")
    al.add_argument("--dry-run", action="store_true", help="Show what would be done")
    al.add_argument("--output", help="Output directory for generated prompts")
    al.add_argument("--mode", choices=["bootstrap", "upgrade"], default="upgrade",
                    help="Prompt generation mode (default: upgrade)")
    al.add_argument("--backup-dir", help="Backup directory to restore from (for rollback)")
    al.add_argument("--yes", "-y", action="store_true",
                    help="Skip confirmation prompts (for non-interactive use)")
    al.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    pc = sub.add_parser("prompt-context", help="Show downstream consumers for a step")
    pc.add_argument("step", help="Step ID (e.g., '04', '16c')")
    pc.add_argument("--repo-root", default=".")
    pc.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    sp_alignment = sub.add_parser("canon-schema-alignment", help="Check canon/schema alignment")
    sp_alignment.add_argument("--repo-root", default=".")
    sp_alignment.add_argument("--canon-dir", default="canon", help="Canon directory relative to repo root")
    sp_alignment.add_argument("--spec-root", default=None, help="Spec directory (for submodule deployments)")
    sp_alignment.add_argument("--git-root", default=None, help="Host repo git root (for two-tier canon)")
    sp_alignment.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    # R9: New commands
    ec = sub.add_parser("env-check", help="Diagnostic: show active validation config")
    ec.add_argument("--repo-root", default=".")
    ec.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    dgl = sub.add_parser("dag-lint", help="Validate DAG completeness in step_order.json")
    dgl.add_argument("--repo-root", default=".")
    dgl.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    eic = sub.add_parser("extraction-intent-check", help="Validate extraction intent sections against step_order.json")
    eic.add_argument("--repo-root", default=".")
    eic.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    hsc = sub.add_parser("hardcoded-seed-check", help="Detect literal seed-doc filenames in prompts (W554 regression guard)")
    hsc.add_argument("--repo-root", default=".")
    hsc.add_argument("--git-root", default=None, help="Host-repo root; when set and different from --repo-root, also scans <git-root>/prompts/ (submodule deployments)")
    hsc.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    ub = sub.add_parser(
        "upstream-backlog",
        help="Aggregate emergent_ambiguities across impl_context plans by implicated upstream step (read-only)",
    )
    ub.add_argument("spec_dir")
    ub.add_argument("--repo-root", default=".")
    ub.add_argument("--spec-root", default=None,
                    help="(reserved; no effect in MVP — accepted for submodule CLI symmetry)")
    ub.add_argument("--severity", choices=["low", "medium", "high", "critical"], default="low",
                    help="Minimum severity (default: low)")
    ub.add_argument("--status", choices=["open", "resolved", "all"], default="open",
                    help="Status filter (default: open = status != resolved)")
    ub.add_argument("--json", action="store_true", dest="json_output",
                    help="Emit JSON instead of plain text")

    cca = sub.add_parser("canon-accept", help="Promote canonical_proposals from a spec file to canon/manifest.json")
    cca.add_argument("--from", dest="spec_file", required=True, help="Path to spec file (e.g., spec/03_glossary.json)")
    cca.add_argument("--namespace", default="cn:project:", help="Target namespace prefix (default: cn:project:)")
    cca.add_argument("--repo-root", default=".")
    cca.add_argument("--git-root", default=None, help="Host repo git root (writes to <git-root>/spec/canon/ as project canon)")
    cca.add_argument("--owner", default=None, help="Owner to assign to accepted entries (default: no owner)")
    cca.add_argument("--dry-run", action="store_true", help="Report what would be added without writing")
    cca.add_argument("--json", action="store_true", help="Output results as JSON", dest="json_output")

    # --- milestone-state subcommand ---
    ms = sub.add_parser(
        "milestone-state",
        help="Compute deterministic milestone state from plan file and findings filesystem",
        description=(
            "Read ms_<batch_id>_plan.json from <spec-root>/impl_context/ and probe "
            ".specdev/findings/ under <git-root> to derive per-group state and the "
            "milestone-level derived_phase_position.  Emits a single JSON object to "
            "stdout; no extra text.  (DEVSPEC-38 D7 — replaces the LLM-evaluated "
            "milestone_state mode of specdev-scope.)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ms.add_argument(
        "--batch-id",
        required=True,
        help="Milestone batch identifier, e.g. 'phase2_newsletter_send'.",
    )
    ms.add_argument(
        "--repo-root",
        default=".",
        help="Toolkit root directory (schema tier).  Default: cwd.",
    )
    ms.add_argument(
        "--spec-root",
        default=None,
        help=(
            "Host spec directory (e.g. ./spec).  Used to locate "
            "spec/impl_context/ms_<batch-id>_plan.json.  Default: <repo-root>/spec."
        ),
    )
    ms.add_argument(
        "--git-root",
        default=None,
        help=(
            "Host repo git root.  Used to locate .specdev/findings/ (host-relative, "
            "NOT under spec-root).  Default: <repo-root>."
        ),
    )

    # --- context subcommand group ---
    ctx_p = sub.add_parser("context", help="Context preparation commands")
    ctx_sub = ctx_p.add_subparsers(dest="context_cmd", help="Context subcommand")

    ctx_struct = ctx_sub.add_parser("structure")
    ctx_struct.add_argument("spec_dir")
    ctx_struct.add_argument("--step", required=True)
    ctx_struct.add_argument("--repo-root", default=".")

    ctx_scope = ctx_sub.add_parser("scope")
    ctx_scope.add_argument("spec_dir")
    ctx_scope.add_argument("--entry", required=True)
    ctx_scope.add_argument("--repo-root", default=".")

    # DEPRECATED: extract is removed; all args are optional so the handler always
    # fires and emits the migration message regardless of what the user passed.
    ctx_extract = ctx_sub.add_parser("extract", add_help=False)
    ctx_extract.add_argument("args", nargs=argparse.REMAINDER)

    ctx_canon = ctx_sub.add_parser("canon")
    ctx_canon.add_argument("--step", required=True)
    ctx_canon.add_argument("--repo-root", default=".")
    ctx_canon.add_argument("--spec-root", default=None, help="Host project spec dir (e.g. ./spec) to include project-tier canon entries")

    ctx_fresh = ctx_sub.add_parser("freshness")
    ctx_fresh.add_argument("spec_dir")
    ctx_fresh.add_argument("--repo-root", default=".")
    ctx_fresh.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")

    ctx_review = ctx_sub.add_parser("review")
    ctx_review.add_argument("artifact_path")
    ctx_review.add_argument("--step", required=True)
    ctx_review.add_argument("--entry", default=None)
    ctx_review.add_argument("--spec-dir", default=None)
    ctx_review.add_argument("--repo-root", default=".")
    ctx_review.add_argument("--git-root", default=None, help="Host repo git root (for submodule deployments)")

    # --- json subcommand group ---
    json_p = sub.add_parser(
        "json",
        help="Targeted JSON read/edit/validate operations on spec artifacts",
        description=(
            "Targeted JSON read/edit/validate operations on spec artifacts.\n\n"
            "Available subcommands:\n"
            "  read               Read a value at a jq path\n"
            "  read-multi         Read multiple jq paths in one call\n"
            "  patch              Replace a value at a jq path\n"
            "  insert             Append to an array at a jq path\n"
            "  delete             Remove a value at a jq path\n"
            "  schema             Resolve the schema URI for a file\n"
            "  structure          Print the structural outline of a file\n"
            "  resolve-pointers   Verify a list of file:jq pointers\n\n"
            "Run 'specdev json <subcommand> --help' for subcommand details."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    json_p.add_argument("args", nargs=argparse.REMAINDER, help="json subcommand and arguments")

    args = p.parse_args()

    if getattr(args, "repo_root", None) == ".":
        # Auto-detect toolkit root by scanning immediate subdirectories
        current_dir = Path(".")
        for child in current_dir.iterdir():
            if child.is_dir():
                potential_marker = child / "tools" / "specdev_tools" / "__init__.py"
                if potential_marker.exists():
                    args.repo_root = str(child)
                    break

    if args.cmd == "validate":
        from .validation.validate import validate_file
        repo_root = os.path.abspath(args.repo_root)
        file_path = os.path.abspath(args.file)
        git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        spec_root = os.path.abspath(args.spec_root) if getattr(args, "spec_root", None) else None
        spec_dir = os.path.dirname(file_path)
        project_canon_dir = _discover_project_canon_dir(git_root=git_root, spec_root=spec_root, spec_dir=spec_dir)
        errs = validate_file(repo_root, file_path, project_canon_dir=project_canon_dir, git_root=git_root, spec_root=spec_root)
        if getattr(args, "json_output", False):
            _json_exit(errs, "validate", {"file": file_path})
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "validate-all":
        from .validation.validate import validate_dir
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        spec_root = os.path.abspath(args.spec_root) if getattr(args, "spec_root", None) else None
        project_canon_dir = _discover_project_canon_dir(git_root=git_root, spec_root=spec_root, spec_dir=spec_dir)
        errs = validate_dir(repo_root, spec_dir, project_canon_dir=project_canon_dir, git_root=git_root, spec_root=spec_root)
        if getattr(args, "json_output", False):
            _json_exit(errs, "validate-all", {"spec_dir": spec_dir})
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "matrix":
        from .validation.matrix import build_trace_matrix
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        spec_root = os.path.abspath(args.spec_root) if getattr(args, "spec_root", None) else None
        project_canon_dir = _discover_project_canon_dir(git_root=git_root, spec_root=spec_root, spec_dir=spec_dir)
        res = build_trace_matrix(repo_root, spec_dir, project_canon_dir=project_canon_dir)
        if getattr(args, "json_output", False):
            cfg = get_config()
            integrity_errors = res.get("integrity_errors")
            has_integrity_err = (
                cfg.matrix_strict
                and isinstance(integrity_errors, list)
                and bool(integrity_errors)
            )
            envelope = {
                "status": "FAIL" if has_integrity_err else "PASS",
                "error_count": len(integrity_errors) if has_integrity_err and integrity_errors is not None else 0,
                "warning_count": 0,
                "errors": [],
                "command": "matrix",
                "matrix": res,
            }
            print(json.dumps(envelope, indent=2))
            if has_integrity_err:
                sys.exit(1)
        else:
            out = json.dumps(res, indent=2, sort_keys=True) + "\n"
            if args.out == "-":
                print(out, end="")
            else:
                from .core.constants import resolve_extras_path
                out_arg = args.out if args.out else resolve_extras_path(spec_dir, "trace_matrix.json")
                out_path = os.path.abspath(out_arg)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(out)
                print(out_arg)
            cfg = get_config()
            matrix_strict = cfg.matrix_strict
            integrity_errors = res.get("integrity_errors")
            if matrix_strict and isinstance(integrity_errors, list) and integrity_errors:
                print(f"E210 TRACE_INTEGRITY matrix_failed count={len(integrity_errors)}", file=sys.stderr)
                for error in integrity_errors:
                    print(error, file=sys.stderr)
                sys.exit(1)
    elif args.cmd == "fixtures-lint":
        from .validation.fixtures_lint import lint_fixtures
        spec_dir = os.path.abspath(args.spec_dir)
        errs = lint_fixtures(spec_dir)
        if getattr(args, "json_output", False):
            _json_exit(errs, "fixtures-lint")
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "invariants-check":
        from .validation.invariants import run_invariants
        spec_dir = os.path.abspath(args.spec_dir)
        with open(args.sample, "r", encoding="utf-8") as fh:
            sample = json.load(fh)
        res = run_invariants(spec_dir, sample)

        strict = bool(getattr(args, "strict", False)) or os.environ.get(
            "SPECDEV_INVARIANTS_STRICT", ""
        ).lower() in ("1", "true", "yes")

        failed = [r for r in res if r.get("evaluable") and not r.get("result")]
        unevaluable = [r for r in res if not r.get("evaluable")]

        errors_list = [
            {
                "code": "E_INVARIANT_VIOLATION",
                "inv_id": r.get("inv_id"),
                "description": r.get("description"),
            }
            for r in failed
        ]
        warnings_list = [
            {
                "code": "W_INVARIANT_UNEVALUABLE",
                "inv_id": r.get("inv_id"),
                "description": r.get("description"),
                "reason": r.get("unevaluable_reason", "unknown"),
            }
            for r in unevaluable
        ]

        if strict:
            errors_list = errors_list + [
                {
                    "code": "E_INVARIANT_UNEVALUABLE",
                    "inv_id": w["inv_id"],
                    "description": w["description"],
                    "reason": w["reason"],
                }
                for w in warnings_list
            ]
            warnings_list = []

        status = "FAIL" if errors_list else "PASS"
        exit_code = 1 if errors_list else 0

        if getattr(args, "json_output", False):
            envelope = {
                "status": status,
                "error_count": len(errors_list),
                "warning_count": len(warnings_list),
                "command": "invariants-check",
                "errors": errors_list,
                "warnings": warnings_list,
                "result": res,
            }
            print(json.dumps(envelope, indent=2))
        else:
            total = len(res)
            print(
                f"invariants-check: {total} rules, "
                f"{len(failed)} failed, {len(unevaluable)} unevaluable"
            )
            for r in failed:
                print(f"  FAIL {r.get('inv_id')}: {r.get('description')}")
            for r in unevaluable:
                reason = r.get("unevaluable_reason", "unknown")
                label = "ERROR" if strict else "WARN"
                print(f"  {label} {r.get('inv_id')}: {r.get('description')} ({reason})")
        sys.exit(exit_code)
    elif args.cmd == "seed-lint":
        from .validation.seed_lint import lint_seeds
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        git_root = os.path.abspath(args.git_root) if getattr(args, 'git_root', None) else None
        # In submodule deployments, git_root is the host repo root where seed
        # files and seed_manifest.json live.  Pass it as project_root so that
        # seed paths are resolved against the host repo, not the toolkit.
        errs = lint_seeds(repo_root, spec_dir, project_root=git_root)
        if getattr(args, "json_output", False):
            _json_exit(errs, "seed-lint")
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "seed-index":
        from .context.seed_indexer import build_seed_index
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        git_root = os.path.abspath(args.git_root) if getattr(args, 'git_root', None) else None
        result, warnings = build_seed_index(spec_dir, repo_root, git_root=git_root)
        if getattr(args, "json_output", False):
            _json_exit(warnings, "seed-index", extra_context={"result": result})
        else:
            if _has_error_messages(warnings):
                _print_and_exit_if_errors(warnings)
            if warnings:
                for w in warnings:
                    print(w, file=sys.stderr)
            print(json.dumps(result, indent=2))
    elif args.cmd == "prompt-sync":
        from .generation.prompt_schema_sync import run_prompt_schema_sync
        repo_root = os.path.abspath(args.repo_root)
        git_root = os.path.abspath(args.git_root) if getattr(args, 'git_root', None) else None
        spec_root = os.path.abspath(args.spec_root) if getattr(args, 'spec_root', None) else None
        # In submodule deployments, spec_dir lives in the host repo, not the toolkit.
        effective_spec_base = git_root or repo_root
        expected_spec_dir = os.path.abspath(os.path.join(effective_spec_base, "spec"))
        if args.spec_dir:
            spec_dir = os.path.abspath(args.spec_dir)
            if spec_dir != expected_spec_dir:
                err_msg = (
                    f"E520 UNRESOLVED_INPUT prompt_sync_spec_dir_must_equal_repo_spec "
                    f"provided={spec_dir} expected={expected_spec_dir}"
                )
                if getattr(args, "json_output", False):
                    _json_exit([err_msg], "prompt-sync")
                else:
                    print(err_msg, file=sys.stderr)
                    sys.exit(1)
        else:
            spec_dir = expected_spec_dir
        if not os.path.isdir(spec_dir):
            err_msg = f"E520 UNRESOLVED_INPUT missing_spec_dir {spec_dir}"
            if getattr(args, "json_output", False):
                _json_exit([err_msg], "prompt-sync")
            else:
                print(err_msg, file=sys.stderr)
                sys.exit(1)
        errs = run_prompt_schema_sync(repo_root)
        if getattr(args, "json_output", False):
            _json_exit(errs, "prompt-sync")
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "canonical-lint":
        repo_root = os.path.abspath(args.repo_root)
        git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        spec_root = os.path.abspath(args.spec_root) if getattr(args, "spec_root", None) else None
        project_canon_dir = _discover_project_canon_dir(git_root=git_root, spec_root=spec_root)
        if project_canon_dir:
            from .canonical.lint import lint_canon_dirs
            errs = lint_canon_dirs(
                repo_root,
                canon_dir=args.canon_dir,
                project_canon_dir=project_canon_dir,
                require_manifest_schema_registration=True,
            )
        else:
            from .canonical.lint import lint_canon_dir
            errs = lint_canon_dir(
                repo_root,
                canon_dir=args.canon_dir,
                require_manifest_schema_registration=True,
            )
        if getattr(args, "json_output", False):
            _json_exit(errs, "canonical-lint")
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "canonical-integrity":
        from .canonical.integrity import validate_canonical_integrity
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        spec_root = os.path.abspath(args.spec_root) if getattr(args, "spec_root", None) else None
        project_canon_dir = _discover_project_canon_dir(git_root=git_root, spec_root=spec_root, spec_dir=spec_dir)
        errs = validate_canonical_integrity(
            repo_root,
            spec_dir,
            canon_dir=args.canon_dir,
            require_manifest_schema_registration=True,
            project_canon_dir=project_canon_dir,
        )
        if getattr(args, "json_output", False):
            _json_exit(errs, "canonical-integrity")
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "canonical-autofix":
        from .canonical.autofix import canonical_autofix
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        if not os.path.isdir(spec_dir):
            err_msg = f"E520 UNRESOLVED_INPUT missing_spec_dir {spec_dir}"
            if getattr(args, "json_output", False):
                _json_exit([err_msg], "canonical-autofix")
            else:
                print(err_msg, file=sys.stderr)
                sys.exit(1)
        git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        spec_root = os.path.abspath(args.spec_root) if getattr(args, "spec_root", None) else None
        project_canon_dir = _discover_project_canon_dir(git_root=git_root, spec_root=spec_root, spec_dir=spec_dir)
        write = bool(args.write and not args.dry_run)
        changes = canonical_autofix(
            repo_root,
            spec_dir,
            write=write,
            canon_dir=args.canon_dir,
            require_manifest_schema_registration=True,
            project_canon_dir=project_canon_dir,
        )
        if getattr(args, "json_output", False):
            # Flatten changes dict into a list of SpecError / str items
            all_items: list[str | SpecError] = []
            if changes:
                for _, file_changes in sorted(changes.items()):
                    for change in file_changes:
                        all_items.append(change)
            # Separate real errors from informational change descriptions
            # so that informational strings don't get misclassified as E521
            from .core.errors import SpecError as _SE, ensure_spec_errors
            from .core.json_output import format_errors_json
            def _is_error_item_json(item: str | SpecError) -> bool:
                if isinstance(item, _SE):
                    return item.code.startswith("E")
                return isinstance(item, str) and item.startswith("E")
            error_items = [item for item in all_items if _is_error_item_json(item)]
            change_items = [item for item in all_items if not _is_error_item_json(item)]
            spec_errors = ensure_spec_errors(error_items) if error_items else []
            changes_rendered = [
                item.render() if isinstance(item, _SE) else str(item)
                for item in change_items
            ]
            print(format_errors_json(
                spec_errors,
                context={"command": "canonical-autofix", "write": write, "changes": changes_rendered},
            ))
            sys.exit(1 if any(e.code.startswith("E") for e in spec_errors) else 0)
        else:
            if not changes:
                print("OK (no changes)")
                return
            from .core.errors import SpecError as _SE
            def _is_error_item(item):
                if isinstance(item, _SE):
                    return item.code.startswith("E")
                return isinstance(item, str) and item.startswith("E")
            def _render_item(item):
                if isinstance(item, _SE):
                    return item.render()
                return str(item)
            has_errors = False
            error_lines: list[str] = []
            non_error_by_file: list[tuple[str, list[str]]] = []
            for file_path, file_changes in sorted(changes.items()):
                non_error_changes = []
                for change in file_changes:
                    if _is_error_item(change):
                        error_lines.append(_render_item(change))
                        has_errors = True
                    else:
                        non_error_changes.append(_render_item(change))
                if non_error_changes:
                    non_error_by_file.append((file_path, non_error_changes))
            for line in error_lines:
                print(line, file=sys.stderr)
            if has_errors and write:
                sys.exit(1)
            for file_path, non_error_changes in non_error_by_file:
                if non_error_changes:
                    print(file_path)
                    for change in non_error_changes:
                        print(f"  - {change}")
            if has_errors:
                sys.exit(1)
            if write:
                print("OK (changes written)")
            else:
                print("OK (dry-run)")
    elif args.cmd == "spec-quality-lint":
        from .validation.spec_quality_lint import lint_spec_quality
        spec_dir = os.path.abspath(args.spec_dir)
        errs = lint_spec_quality(spec_dir)
        if getattr(args, "json_output", False):
            _json_exit(errs, "spec-quality-lint")
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "hallucination-lint":
        from .validation.hallucination_lint import lint_hallucinations
        spec_dir = os.path.abspath(args.spec_dir)
        repo_root = os.path.abspath(args.repo_root)
        if not os.path.isdir(spec_dir):
            err_msg = f"E520 UNRESOLVED_INPUT missing_spec_dir {spec_dir}"
            if getattr(args, "json_output", False):
                _json_exit([err_msg], "hallucination-lint")
            else:
                print(err_msg, file=sys.stderr)
                sys.exit(1)
        git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        spec_root = os.path.abspath(args.spec_root) if getattr(args, "spec_root", None) else None
        project_canon_dir = _discover_project_canon_dir(git_root=git_root, spec_root=spec_root, spec_dir=spec_dir)
        errs = lint_hallucinations(
            spec_dir,
            repo_root=repo_root,
            canon_dir=args.canon_dir,
            require_canon_dir=True,
            require_manifest_schema_registration=True,
            project_canon_dir=project_canon_dir,
            git_root=git_root,
        )
        if getattr(args, "json_output", False):
            _json_exit(errs, "hallucination-lint")
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "glossary-drift-check":
        from .validation.glossary_drift_lint import lint_glossary_drift
        spec_dir = os.path.abspath(args.spec_dir)
        repo_root = os.path.abspath(args.repo_root)
        if not os.path.isdir(spec_dir):
            err_msg = f"E520 UNRESOLVED_INPUT missing_spec_dir {spec_dir}"
            if getattr(args, "json_output", False):
                _json_exit([err_msg], "glossary-drift-check")
            else:
                print(err_msg, file=sys.stderr)
                sys.exit(1)
        git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        spec_root = os.path.abspath(args.spec_root) if getattr(args, "spec_root", None) else None
        # Use _discover_project_canon_dir — same convention as all other lint handlers.
        # Returns spec/canon (the canon/ dir), NOT spec/canon/kinds.
        project_canon_dir = _discover_project_canon_dir(
            git_root=git_root, spec_root=spec_root, spec_dir=spec_dir
        )
        errs = lint_glossary_drift(
            spec_dir,
            repo_root=repo_root,
            project_canon_dir=project_canon_dir,
        )
        if getattr(args, "json_output", False):
            _json_exit(errs, "glossary-drift-check")
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "traceability-check":
        from .validation.traceability_closure import check_traceability_closure
        spec_dir = os.path.abspath(args.spec_dir)
        repo_root = os.path.abspath(args.repo_root)
        errs = check_traceability_closure(spec_dir, repo_root)
        if getattr(args, "json_output", False):
            _json_exit(errs, "traceability-check", {"spec_dir": spec_dir})
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "completeness-check":
        from .validation.traceability_closure import check_traceability_closure
        spec_dir = os.path.abspath(args.spec_dir)
        repo_root = os.path.abspath(args.repo_root)
        all_errs = check_traceability_closure(spec_dir, repo_root)

        # Filter for pairwise completeness codes W564–W568 (and E-code counterparts).
        # W561 (UNCOVERED_FR legacy co-fire) is intentionally excluded — W566 covers the same FRs
        # and is the promotable pairwise code for completeness reporting.
        _completeness_codes = frozenset({
            "W564", "W565", "W566", "W567", "W568",
            "E564", "E565", "E566", "E567", "E568",
        })
        from .core.errors import SpecError
        completeness_errs = [
            e for e in all_errs
            if (isinstance(e, SpecError) and e.code in _completeness_codes)
            or (isinstance(e, str) and any(e.lstrip().startswith(c) for c in _completeness_codes))
        ]

        # Compute per-check coverage ratios by counting uncovered IDs.
        # Each warning message has the form: "LABEL {id} [optional tail...]"
        # For W564–W568 the uncovered ID is always the second token (parts[1]).
        # Message forms:
        #   W564: "UNCOVERED_FR_API {fr_id}"
        #   W565: "UNCOVERED_FR_FIXTURE {fr_id}"
        #   W566: "UNCOVERED_FR_MILESTONE {fr_id}"
        #   W567: "INCOMPLETE_MILESTONE_DECOMPOSITION {ms_id}" or
        #          "INCOMPLETE_MILESTONE_DECOMPOSITION {ms_id}: fr_ref {fr_id} not covered ..."
        #   W568: "UNCOVERED_CAPABILITY {cap_id}"
        _PAIRWISE_CODES = frozenset({"W564", "W565", "W566", "W567", "W568",
                                     "E564", "E565", "E566", "E567", "E568"})

        def _extract_ids_for_code(code: str) -> list[str]:
            result = []
            # e_variant: the E-code counterpart of the W-code passed by callers (e.g. "W564" → "E564").
            # Callers always pass W-codes (W564–W568); e_variant lets us match promoted E-code errors too.
            e_variant = code.replace("W", "E", 1)
            for e in completeness_errs:
                msg = e.message if isinstance(e, SpecError) else e
                # Match both W-code and promoted E-code
                if isinstance(e, SpecError) and e.code in (code, e_variant):
                    parts = msg.split()
                    if len(parts) >= 2 and code in _PAIRWISE_CODES:
                        # ID is always the second token for W564–W568.
                        # Strip trailing colon: the fr_ref W567 variant emits
                        # "INCOMPLETE_MILESTONE_DECOMPOSITION ms-id: fr_ref ..."
                        # so parts[1] is "ms-id:" — normalise to "ms-id".
                        result.append(parts[1].rstrip(':'))
                    elif parts:
                        result.append(parts[1] if len(parts) >= 2 else parts[-1])
                # String format: legacy support; check_traceability_closure always returns SpecError objects
                elif isinstance(e, str) and (e.lstrip().startswith(code) or e.lstrip().startswith(e_variant)):
                    parts = e.split()
                    if len(parts) >= 2:
                        result.append(parts[1] if code in _PAIRWISE_CODES else parts[-1])
            return list(dict.fromkeys(result))

        # Gather totals by loading spec data inline (cheap re-read for ratio computation).
        # We parse the raw spec files directly to avoid coupling with internal state.
        def _load_spec_json(filename: str) -> dict:
            import json as _json
            path = os.path.join(spec_dir, filename)
            if not os.path.isfile(path):
                return {}
            try:
                with open(path, encoding="utf-8") as _f:
                    return _json.load(_f)
            except (OSError, ValueError):
                return {}

        frs_data = _load_spec_json("04_fr_list.json")
        total_frs = len(frs_data.get("functional_requirements", [])) if frs_data else 0

        caps_data = _load_spec_json("01_capabilities.json")
        total_caps = len(caps_data.get("capabilities", [])) if caps_data else 0

        roadmap_data = _load_spec_json("14_roadmap.json")
        total_milestones = len(roadmap_data.get("milestones", [])) if roadmap_data else 0

        def _ratio(total: int, uncovered_count: int) -> float:
            if total == 0:
                return 1.0
            return round((total - uncovered_count) / total, 4)

        uncovered_w564 = _extract_ids_for_code("W564")
        uncovered_w565 = _extract_ids_for_code("W565")
        uncovered_w566 = _extract_ids_for_code("W566")
        uncovered_w567 = _extract_ids_for_code("W567")
        uncovered_w568 = _extract_ids_for_code("W568")

        def _dim(total: int, uncovered: list) -> dict:
            covered = max(0, total - len(uncovered))
            return {
                "covered_count": covered,
                "total_count": total,
                "ratio": _ratio(total, len(uncovered)),
                "uncovered_ids": uncovered,
            }

        coverage = {
            "fr_api_coverage":               _dim(total_frs,        uncovered_w564),
            "fr_fixture_coverage":           _dim(total_frs,        uncovered_w565),
            "fr_milestone_coverage":         _dim(total_frs,        uncovered_w566),
            "milestone_decomp_completeness": _dim(total_milestones, uncovered_w567),
            "capability_fr_coverage":        _dim(total_caps,       uncovered_w568),
        }

        if getattr(args, "json_output", False):
            from .core.errors import ensure_spec_errors
            from .core.json_output import format_errors_json
            spec_errors = ensure_spec_errors(completeness_errs)
            ctx: dict = {
                "command": "completeness-check",
                "spec_dir": spec_dir,
                "coverage": coverage,
            }
            print(format_errors_json(spec_errors, context=ctx))
            has_ecodes = any(not e.code.startswith("W") for e in spec_errors)
            if _warnings_as_errors() and spec_errors:
                sys.exit(1)
            if has_ecodes:
                sys.exit(1)
            sys.exit(0)
        else:
            print("=== Pairwise Completeness Check ===")
            print()
            labels = [
                ("W564", "FR → API coverage",              coverage["fr_api_coverage"]),
                ("W565", "FR → Fixture coverage",          coverage["fr_fixture_coverage"]),
                ("W566", "FR → Milestone coverage",        coverage["fr_milestone_coverage"]),
                ("W567", "Milestone decomp completeness",  coverage["milestone_decomp_completeness"]),
                ("W568", "Capability → FR coverage",       coverage["capability_fr_coverage"]),
            ]
            for _, label, dim in labels:
                ratio = dim["ratio"]
                uncovered = dim["uncovered_ids"]
                pct = f"{ratio * 100:.1f}%"
                status = "OK" if ratio == 1.0 else "WARN"
                print(f"  [{status}] {label}: {pct}")
                for uid in uncovered:
                    print(f"        - uncovered: {uid}")
            print()
            if _has_error_messages(completeness_errs):
                sys.exit(1)
    elif args.cmd == "dependency-order-lint":
        from .validation.dependency_order_lint import lint_dependency_order
        repo_root = os.path.abspath(args.repo_root)
        errs = lint_dependency_order(repo_root)
        if getattr(args, "json_output", False):
            _json_exit(errs, "dependency-order-lint")
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "forward-replay-check":
        from .validation.forward_replay_check import check_forward_replay
        from .validation.validate import _resolve_replay_base_ref
        repo_root = os.path.abspath(args.repo_root)
        git_root = os.path.abspath(args.git_root) if getattr(args, 'git_root', None) else None
        spec_root = os.path.abspath(args.spec_root) if getattr(args, 'spec_root', None) else None
        base_ref = args.base_ref or _resolve_replay_base_ref(Path(git_root or repo_root))
        errs = check_forward_replay(
            repo_root,
            base_ref=base_ref,
            diff_error_mode=args.diff_error_mode,
            git_root=git_root,
            spec_root=spec_root,
        )
        if getattr(args, "json_output", False):
            _json_exit(errs, "forward-replay-check")
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "governance-check":
        from .validation.governance import check_commit_message
        spec_dir = os.path.abspath(args.spec_dir)
        msg = args.message
        if os.path.exists(msg) and os.path.isfile(msg):
            try:
                msg = open(msg, "r", encoding="utf-8").read().strip()
            except Exception:
                pass
        errs = check_commit_message(spec_dir, msg)
        if getattr(args, "json_output", False):
            _json_exit(errs, "governance-check")
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "ai-help":
        # Load step_docs.json for reference doc lookup
        _ai_help_repo_root = os.path.abspath(getattr(args, "repo_root", "."))
        _step_docs_path = os.path.join(_ai_help_repo_root, "tools", "step_docs.json")
        _step_docs: dict = {}
        try:
            with open(_step_docs_path) as _f:
                _step_docs = json.load(_f).get("step_docs", {})
        except (OSError, KeyError, json.JSONDecodeError):
            pass  # silently skip if file missing or malformed

        if getattr(args, "json_output", False):
            lines = []
            if args.step:
                lines = [
                    f"AI help for step {args.step}:",
                    f"1. Open the prompt file: prompts/prompt_{args.step}_*.md",
                    f"2. Copy the content into your AI assistant",
                    f"3. Write the AI-produced JSON directly to spec/{args.step}_*.json",
                    f"4. Validate: python -m specdev_tools.cli validate spec/{args.step}_*.json --repo-root <toolkit_dir>",
                ]
            else:
                lines = [
                    "AI Interaction Guide:",
                    "1. Locate the prompt file in prompts/prompt_XX_stepname.md",
                    "2. Copy the full content into your AI assistant",
                    "3. Write the JSON artifact directly to spec/NN_name.json",
                    "4. Validate with: python -m specdev_tools.cli validate spec/NN_name.json --repo-root <toolkit_dir>",
                    "5. Ensure all IDs use kebab-case format",
                    "6. No examples should be included in the AI output",
                ]
            if args.step and args.step in _step_docs:
                lines.append("")
                lines.append("Reference docs:")
                for _doc in _step_docs[args.step]:
                    lines.append(f"  - {_doc}")
            output = {
                "status": "PASS",
                "error_count": 0,
                "warning_count": 0,
                "command": "ai-help",
                "errors": [],
                "output": "\n".join(lines),
            }
            print(json.dumps(output, indent=2))
        else:
            if args.step:
                print(f"AI help for step {args.step}:")
                print(f"1. Open the prompt file: prompts/prompt_{args.step}_*.md")
                print(f"2. Copy the content into your AI assistant")
                print(f"3. Write the AI-produced JSON directly to spec/{args.step}_*.json")
                print(f"4. Validate: python -m specdev_tools.cli validate spec/{args.step}_*.json --repo-root <toolkit_dir>")
                if args.step in _step_docs:
                    print("")
                    print("Reference docs:")
                    for _doc in _step_docs[args.step]:
                        print(f"  - {_doc}")
            else:
                print("AI Interaction Guide:")
                print("1. Locate the prompt file in prompts/prompt_XX_stepname.md")
                print("2. Copy the full content into your AI assistant")
                print("3. Write the JSON artifact directly to spec/NN_name.json")
                print("4. Validate with: python -m specdev_tools.cli validate spec/NN_name.json --repo-root <toolkit_dir>")
                print("5. Ensure all IDs use kebab-case format")
                print("6. No examples should be included in the AI output")
    elif args.cmd == "changelog":
        from .core.changelog_parser import (
            list_versions,
            load_version,
            get_toolkit_version,
            validate_changelog,
        )
        repo_root = Path(os.path.abspath(args.repo_root))
        changelog_dir = repo_root / "changelog"

        if args.list:
            if getattr(args, "json_output", False):
                toolkit_ver = get_toolkit_version(repo_root)
                versions = list_versions(changelog_dir)
                output = {
                    "status": "PASS",
                    "error_count": 0,
                    "warning_count": 0,
                    "command": "changelog",
                    "action": "list",
                    "errors": [],
                    "toolkit_version": toolkit_ver or None,
                    "versions": versions,
                }
                print(json.dumps(output, indent=2))
            else:
                # List all versions
                toolkit_ver = get_toolkit_version(repo_root)
                if toolkit_ver:
                    print(f"Toolkit version: {toolkit_ver}")
                versions = list_versions(changelog_dir)
                if versions:
                    print(f"Available versions: {', '.join(versions)}")
                else:
                    print("No versions found in changelog/")
        elif args.version:
            if getattr(args, "json_output", False):
                try:
                    changelog = load_version(changelog_dir, args.version)
                    output = {
                        "status": "PASS",
                        "error_count": 0,
                        "warning_count": 0,
                        "command": "changelog",
                        "action": "version",
                        "errors": [],
                        "version": changelog.version,
                        "breaking": changelog.breaking,
                        "description": changelog.description.strip() if changelog.description else None,
                        "steps": [s.id for s in changelog.steps] if changelog.steps else [],
                        "changes": [
                            {
                                "type": c.type,
                                "description": c.description,
                                "step_id": c.step_id if hasattr(c, "step_id") else None,
                                "path": c.path if hasattr(c, "path") else None,
                            }
                            for c in changelog.changes
                        ] if changelog.changes else [],
                    }
                    print(json.dumps(output, indent=2))
                except (FileNotFoundError, ValueError) as e:
                    _json_exit([f"E521 {e}"], "changelog")
            else:
                # Show details for a specific version
                try:
                    changelog = load_version(changelog_dir, args.version)
                    print(f"Version: {changelog.version}")
                    print(f"Breaking: {'Yes' if changelog.breaking else 'No'}")
                    if changelog.description:
                        print(f"Description: {changelog.description.strip()}")
                    print(f"Steps: {len(changelog.steps)}")
                    if changelog.steps:
                        for step in changelog.steps:
                            print(f"  - {step.id}")
                    print(f"Changes: {len(changelog.changes)}")
                    if changelog.changes:
                        for change in changelog.changes:
                            print(f"  - [{change.type}] {change.description or change.step_id or change.path}")
                except (FileNotFoundError, ValueError) as e:
                    print(f"Error: {e}", file=sys.stderr)
                    sys.exit(1)
        elif args.validate:
            # Validate a version's changelog
            errs = validate_changelog(changelog_dir, args.validate)
            if getattr(args, "json_output", False):
                _json_exit(errs, "changelog")
            else:
                _print_and_exit_if_errors(errs)
        else:
            if getattr(args, "json_output", False):
                output = {
                    "status": "PASS",
                    "error_count": 0,
                    "warning_count": 0,
                    "command": "changelog",
                    "errors": [],
                    "output": "Usage: specdev changelog [--list] [--version X.Y.Z] [--validate X.Y.Z]",
                }
                print(json.dumps(output, indent=2))
            else:
                print("Usage: specdev changelog [--list] [--version X.Y.Z] [--validate X.Y.Z]")
                print("  --list       List all available versions")
                print("  --version    Show details for a specific version")
                print("  --validate   Validate a version's changelog against format.yaml")
    elif args.cmd == "align":
        from .generation.schema_differ import (
            diff_spec_directory,
            format_status_report,
            format_diff_report,
            format_plan_report,
            apply_auto_fixes,
            format_apply_report,
            list_backups,
            restore_backup,
            validate_pre_migration,
            log_operation,
        )
        from .generation.prompt_generator import (
            generate_prompts,
            write_prompts,
            format_prompts_report,
        )
        repo_root = Path(os.path.abspath(args.repo_root))
        spec_dir = Path(os.path.abspath(args.spec_dir))

        if not spec_dir.exists():
            err_msg = f"E520 UNRESOLVED_INPUT missing_spec_dir {spec_dir}"
            if getattr(args, "json_output", False):
                _json_exit([err_msg], "align")
            else:
                print(f"Error: Spec directory not found: {spec_dir}", file=sys.stderr)
                sys.exit(1)

        diff = diff_spec_directory(spec_dir, repo_root)

        if args.action == "status":
            if getattr(args, "json_output", False):
                report = format_status_report(diff)
                output = {
                    "status": "PASS",
                    "error_count": 0,
                    "warning_count": 0,
                    "command": "align",
                    "action": "status",
                    "errors": [],
                    "output": report,
                }
                print(json.dumps(output, indent=2))
            else:
                print(format_status_report(diff))
        elif args.action == "diff":
            if getattr(args, "json_output", False):
                report = format_diff_report(diff)
                output = {
                    "status": "PASS",
                    "error_count": 0,
                    "warning_count": 0,
                    "command": "align",
                    "action": "diff",
                    "errors": [],
                    "output": report,
                }
                print(json.dumps(output, indent=2))
            else:
                print(format_diff_report(diff))
        elif args.action == "plan":
            if getattr(args, "json_output", False):
                report = format_plan_report(diff)
                output = {
                    "status": "PASS",
                    "error_count": 0,
                    "warning_count": 0,
                    "command": "align",
                    "action": "plan",
                    "errors": [],
                    "output": report,
                }
                print(json.dumps(output, indent=2))
            else:
                # Show detailed execution plan
                print(format_plan_report(diff))
        elif args.action == "apply":
            if not args.auto:
                if getattr(args, "json_output", False):
                    _json_exit(
                        ["E520 UNRESOLVED_INPUT use_--auto_flag_to_apply_mechanical_fixes"],
                        "align",
                    )
                else:
                    print("Error: Use --auto flag to apply mechanical fixes", file=sys.stderr)
                    print("       Full apply (including AI-assisted) is not yet supported")
                    sys.exit(1)

            # Pre-migration validation
            validation = validate_pre_migration(spec_dir, repo_root)
            if not validation.can_proceed:
                if getattr(args, "json_output", False):
                    err_items = [f"E520 {e}" for e in validation.errors]
                    _json_exit(err_items, "align")
                else:
                    for warning in validation.warnings:
                        print(f"\u26a0\ufe0f  Warning: {warning}", file=sys.stderr)
                    for error in validation.errors:
                        print(f"\u274c Error: {error}", file=sys.stderr)
                    sys.exit(1)
            else:
                if not getattr(args, "json_output", False):
                    for warning in validation.warnings:
                        print(f"\u26a0\ufe0f  Warning: {warning}", file=sys.stderr)

            result = apply_auto_fixes(diff, spec_dir, repo_root, dry_run=args.dry_run)
            if getattr(args, "json_output", False):
                report = format_apply_report(result)
                pre_warnings = list(validation.warnings) if validation.warnings else []
                output = {
                    "status": "PASS",
                    "error_count": 0,
                    "warning_count": len(pre_warnings),
                    "command": "align",
                    "action": "apply",
                    "errors": [],
                    "warnings": pre_warnings,
                    "output": report,
                }
                print(json.dumps(output, indent=2))
            else:
                print(format_apply_report(result))
        elif args.action == "prompts":
            # Generate AI prompts for semantic migrations
            prompts = generate_prompts(
                diff,
                repo_root,
                spec_dir,
                mode=args.mode,
            )

            if not getattr(args, "json_output", False):
                if args.output:
                    output_dir = Path(args.output)
                    write_prompts(prompts, output_dir)
                    print(f"\u2705 Generated {len(prompts)} prompt(s) in {output_dir}/")
                print(format_prompts_report(prompts))
            else:
                if args.output:
                    output_dir = Path(args.output)
                    write_prompts(prompts, output_dir)
                report = format_prompts_report(prompts)
                output = {
                    "status": "PASS",
                    "error_count": 0,
                    "warning_count": 0,
                    "command": "align",
                    "action": "prompts",
                    "errors": [],
                    "prompt_count": len(prompts),
                    "output": report,
                }
                print(json.dumps(output, indent=2))
        elif args.action == "rollback":
            if getattr(args, "json_output", False):
                output = {
                    "status": "FAIL",
                    "error_count": 1,
                    "warning_count": 0,
                    "command": "align",
                    "action": "rollback",
                    "errors": [{"code": "E521", "message": "JSON output not yet supported for align rollback", "severity": "error"}],
                }
                print(json.dumps(output, indent=2))
                sys.exit(1)
            else:
                backups = list_backups(spec_dir)
                if not backups:
                    print("No backups found in spec/migration_backups/")
                    sys.exit(0)

                selected = None

                # Non-interactive: --backup-dir selects directly
                if getattr(args, 'backup_dir', None):
                    from pathlib import Path as _Path
                    target_name = _Path(args.backup_dir).name
                    for b in backups:
                        if b.backup_dir.name == target_name:
                            selected = b
                            break
                    if selected is None:
                        print(f"Error: backup '{args.backup_dir}' not found", file=sys.stderr)
                        sys.exit(1)
                else:
                    # Interactive mode requires TTY
                    if not sys.stdin.isatty() and not getattr(args, 'yes', False):
                        print("Error: rollback requires --backup-dir or --yes in non-interactive mode", file=sys.stderr)
                        sys.exit(1)

                    print("\n\U0001f519 Available Backups")
                    print("\u2501" * 20)
                    for i, backup in enumerate(backups, 1):
                        print(f"  {i}. {backup.backup_dir.name}")

                    try:
                        choice = input("\nSelect backup to restore [1]: ").strip()
                        idx = int(choice) - 1 if choice else 0
                        if 0 <= idx < len(backups):
                            selected = backups[idx]
                        else:
                            print("Invalid selection.")
                            sys.exit(1)
                    except (ValueError, EOFError, KeyboardInterrupt):
                        print("\nCancelled.")
                        sys.exit(1)

                # Confirm unless --yes
                if selected and not getattr(args, 'yes', False):
                    try:
                        confirm = input(f"Restore from {selected.backup_dir.name}? [y/N]: ").strip().lower()
                        if confirm != 'y':
                            print("Cancelled.")
                            sys.exit(0)
                    except (EOFError, KeyboardInterrupt):
                        print("\nCancelled.")
                        sys.exit(1)

                if selected:
                    restore_backup(spec_dir, selected)
                    log_operation(spec_dir, f"Restored from {selected.backup_dir.name}", "success")
                    print(f"\u2705 Restored from {selected.backup_dir.name}")
        elif args.action == "validate":
             # Post-migration validation
            from .generation.schema_differ import validate_post_migration, get_toolkit_version

            toolkit_version = get_toolkit_version(repo_root)
            if not toolkit_version:
                if getattr(args, "json_output", False):
                    _json_exit(
                        ["E520 UNRESOLVED_INPUT could_not_determine_toolkit_version"],
                        "align",
                    )
                else:
                    print("Error: Could not determine toolkit version", file=sys.stderr)
                    sys.exit(1)

            assert toolkit_version is not None  # guarded by sys.exit above
            result = validate_post_migration(spec_dir, repo_root, toolkit_version)

            if getattr(args, "json_output", False):
                err_items = [f"E520 {e}" for e in result.errors]
                warn_items = [f"W570 {w}" for w in result.warnings]
                _json_exit(err_items + warn_items, "align")
            else:
                print("\U0001f50d Post-Migration Validation")
                print("\u2501" * 27)

                # Print warnings
                if result.warnings:
                    print("\n\u26a0\ufe0f  Warnings:")
                    for w in result.warnings:
                        print(f"  - {w}")

                # Print errors
                if result.errors:
                    print("\n\u274c Errors:")
                    for e in result.errors:
                        print(f"  - {e}")
                    print("\nResult: \u274c FAILED")
                    sys.exit(1)

                print("\n\u2705 Trace Integrity: OK")
                print(f"\u2705 Toolkit Version: {toolkit_version}")
                print("\nResult: \u2705 PASSED")
                print("Migration complete. spec/specdev_version updated.")

    elif args.cmd == "prompt-context":
        repo_root = os.path.abspath(args.repo_root)
        step_order_path = os.path.join(repo_root, "tools", "step_order.json")
        if not os.path.exists(step_order_path):
            err_msg = f"E520 UNRESOLVED_INPUT missing_step_order {step_order_path}"
            if getattr(args, "json_output", False):
                _json_exit([err_msg], "prompt-context")
            else:
                print(err_msg, file=sys.stderr)
                sys.exit(1)

        with open(step_order_path, "r", encoding="utf-8") as f:
            step_order = json.load(f)

        normalized_step = args.step.zfill(2) if args.step.isdigit() else args.step

        if normalized_step not in step_order.get("steps", []):
            err_msg = f"E520 UNRESOLVED_INPUT unknown_step {args.step}"
            if getattr(args, "json_output", False):
                _json_exit([err_msg], "prompt-context")
            else:
                print(f"Error: Unknown step '{args.step}'", file=sys.stderr)
                sys.exit(1)

        downstream_consumers = step_order.get("downstream_consumers", {})
        consumer_ids = downstream_consumers.get(normalized_step, [])

        STEP_NAMES = _derive_step_names(repo_root)

        if getattr(args, "json_output", False):
            consumers = [
                {"step": cid, "name": STEP_NAMES.get(cid, f"Step {cid}")}
                for cid in consumer_ids
            ]
            output = {
                "status": "PASS",
                "error_count": 0,
                "warning_count": 0,
                "command": "prompt-context",
                "errors": [],
                "step": normalized_step,
                "consumers": consumers,
            }
            print(json.dumps(output, indent=2))
        else:
            print("| Step | Name |")
            print("|------|------|")
            for cid in consumer_ids:
                name = STEP_NAMES.get(cid, f"Step {cid}")
                print(f"| {cid} | {name} |")

    elif args.cmd == "canon-schema-alignment":
        from .validation.canon_schema_alignment import lint_canon_schema_alignment
        repo_root = os.path.abspath(args.repo_root)
        git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        spec_root = os.path.abspath(args.spec_root) if getattr(args, "spec_root", None) else None
        project_canon_dir = _discover_project_canon_dir(git_root=git_root, spec_root=spec_root)
        errors = lint_canon_schema_alignment(
            repo_root,
            canon_dir=getattr(args, "canon_dir", "canon"),
            project_canon_dir=project_canon_dir,
        )
        if getattr(args, "json_output", False):
            _json_exit(errors, "canon-schema-alignment")
        else:
            _print_and_exit_if_errors(errors)

    elif args.cmd == "env-check":
        # R9/T28: Read-only diagnostic — prints all SPECDEV_* env vars and active config
        from .core.errors import PROMOTABLE_PAIRS
        repo_root = os.path.abspath(args.repo_root)

        if getattr(args, "json_output", False):
            specdev_vars = {k: v for k, v in sorted(os.environ.items()) if k.startswith("SPECDEV_")}
            env_cfg = get_config()
            warn_as_error = env_cfg.warnings_as_errors
            promote_codes_list = sorted(env_cfg.promote_codes) if env_cfg.promote_codes else []
            spec_dir = os.path.join(repo_root, "spec")
            step_order_path = os.path.join(repo_root, "tools", "step_order.json")
            coverage_thresholds = None
            if os.path.isfile(step_order_path):
                try:
                    with open(step_order_path, "r", encoding="utf-8") as f:
                        so_data = json.load(f)
                    coverage_thresholds = so_data.get("coverage_thresholds")
                except (OSError, json.JSONDecodeError):
                    pass
            output = {
                "status": "PASS",
                "error_count": 0,
                "warning_count": 0,
                "command": "env-check",
                "errors": [],
                "environment_variables": specdev_vars,
                "warnings_as_errors": warn_as_error,
                "promote_codes": promote_codes_list,
                "promotable_pairs_count": len(PROMOTABLE_PAIRS),
                "repo_root": repo_root,
                "spec_dir": spec_dir,
                "spec_dir_exists": os.path.isdir(spec_dir),
                "step_order_path": step_order_path,
                "step_order_exists": os.path.isfile(step_order_path),
                "coverage_thresholds": coverage_thresholds,
                "replay_base_ref": env_cfg.replay_base_ref or None,
                "matrix_strict": env_cfg.matrix_strict,
            }
            print(json.dumps(output, indent=2))
        else:
            print("=== SPECDEV Environment Check ===")
            print()
            # SPECDEV_* env vars
            specdev_vars = {k: v for k, v in sorted(os.environ.items()) if k.startswith("SPECDEV_")}
            if specdev_vars:
                print("Active SPECDEV_* environment variables:")
                for k, v in specdev_vars.items():
                    print(f"  {k}={v}")
            else:
                print("No SPECDEV_* environment variables set.")
            print()
            # W->E promotion status
            env_cfg = get_config()
            warn_as_error = env_cfg.warnings_as_errors
            promote_codes = ",".join(sorted(env_cfg.promote_codes)) if env_cfg.promote_codes else ""
            if warn_as_error:
                print(f"W\u2192E Promotion: ALL ({len(PROMOTABLE_PAIRS)} pairs)")
            elif promote_codes:
                selected = [c.strip() for c in promote_codes.split(",") if c.strip()]
                print(f"W\u2192E Promotion: SELECTIVE ({len(selected)} codes: {', '.join(selected)})")
            else:
                print("W\u2192E Promotion: OFF (no promotion active)")
            print(f"Promotable pairs registered: {len(PROMOTABLE_PAIRS)}")
            print()
            # Spec dir and replay base ref
            spec_dir = os.path.join(repo_root, "spec")
            print(f"Repo root: {repo_root}")
            print(f"Spec dir: {spec_dir} ({'exists' if os.path.isdir(spec_dir) else 'NOT FOUND'})")
            step_order_path = os.path.join(repo_root, "tools", "step_order.json")
            print(f"Step order: {step_order_path} ({'exists' if os.path.isfile(step_order_path) else 'NOT FOUND'})")
            # Coverage thresholds
            if os.path.isfile(step_order_path):
                try:
                    with open(step_order_path, "r", encoding="utf-8") as f:
                        so_data = json.load(f)
                    ct = so_data.get("coverage_thresholds")
                    if ct:
                        print(f"Coverage thresholds: {json.dumps(ct)}")
                    else:
                        print("Coverage thresholds: not configured")
                except (OSError, json.JSONDecodeError):
                    print("Coverage thresholds: error reading step_order.json")
            replay_base = env_cfg.replay_base_ref or ""
            print(f"Replay base ref: {replay_base or '(auto-resolved)'}")
            matrix_strict_val = env_cfg.matrix_strict
            print(f"Matrix strict mode: {'ON' if matrix_strict_val else 'OFF'}")
            print()
            print("=== End Environment Check ===")

    elif args.cmd == "dag-lint":
        from .validation.dag_lint import lint_dag
        repo_root = os.path.abspath(args.repo_root)
        errs = lint_dag(repo_root)
        if getattr(args, "json_output", False):
            _json_exit(errs, "dag-lint")
        else:
            _print_and_exit_if_errors(errs)

    elif args.cmd == "extraction-intent-check":
        from .validation.extraction_intent_check import check_extraction_intent
        repo_root = os.path.abspath(args.repo_root)
        errs = check_extraction_intent(repo_root)
        if getattr(args, "json_output", False):
            _json_exit(errs, "extraction-intent-check")
        else:
            _print_and_exit_if_errors(errs)

    elif args.cmd == "hardcoded-seed-check":
        from .validation.seed_lint import check_hardcoded_seed_reference
        repo_root = os.path.abspath(args.repo_root)
        git_root_arg = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        errs = check_hardcoded_seed_reference(repo_root, git_root=git_root_arg)
        if getattr(args, "json_output", False):
            _json_exit(errs, "hardcoded-seed-check")
        else:
            _print_and_exit_if_errors(errs)

    elif args.cmd == "upstream-backlog":
        from .analysis.upstream_backlog import run as run_upstream_backlog
        spec_dir_abs = os.path.abspath(args.spec_dir)
        stdout_payload, stderr_lines, exit_code = run_upstream_backlog(
            spec_dir=spec_dir_abs,
            repo_root=args.repo_root,
            spec_root=args.spec_root,
            severity=args.severity,
            status=args.status,
            json_output=args.json_output,
        )
        for line in stderr_lines:
            print(line, file=sys.stderr)
        if stdout_payload:
            print(stdout_payload)
        sys.exit(exit_code)

    elif args.cmd == "canon-accept":
        from .canonical.accept import run_canon_accept
        repo_root = os.path.abspath(args.repo_root)
        spec_file = os.path.abspath(args.spec_file)
        git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        if git_root:
            canon_dir = os.path.join(git_root, "spec", "canon")
            project_canon = True
        else:
            canon_dir = None
            project_canon = False
        result = run_canon_accept(
            spec_file=spec_file,
            namespace=args.namespace,
            repo_root=repo_root,
            dry_run=args.dry_run,
            owner=getattr(args, "owner", None),
            canon_dir=canon_dir,
            project_canon=project_canon,
        )
        if getattr(args, "json_output", False):
            error_str = result.get("error")
            added = result.get("added", [])
            skipped = result.get("skipped", [])
            malformed = result.get("malformed", 0)
            errs_list = [f"E521 CANON_ACCEPT_FAILED {error_str}"] if error_str else []
            from .core.errors import ensure_spec_errors
            from .core.json_output import format_errors_json
            spec_errors = ensure_spec_errors(errs_list)
            ctx: dict = {
                "command": "canon-accept",
                "added": added,
                "skipped": skipped,
                "malformed": malformed,
                "dry_run": args.dry_run,
            }
            print(format_errors_json(spec_errors, context=ctx))
            sys.exit(1 if error_str else 0)
        else:
            error_str = result.get("error")
            if error_str:
                print(f"E521 CANON_ACCEPT_FAILED {error_str}", file=sys.stderr)
                sys.exit(1)
            added = result.get("added", [])
            skipped = result.get("skipped", [])
            malformed = result.get("malformed", 0)
            if added:
                label = "would add" if args.dry_run else "added"
                for cid in added:
                    print(f"  + {label}: {cid}")
            if skipped:
                for cid in skipped:
                    print(f"  ~ skipped (duplicate): {cid}")
            if malformed:
                print(f"  ! {malformed} malformed proposal(s) skipped (missing required fields)")
            if not added and not skipped and not malformed:
                print("OK (no proposals found)")
            elif args.dry_run:
                print(f"OK (dry-run: {len(added)} would be added, {len(skipped)} skipped, {malformed} malformed)")
            else:
                print(f"OK ({len(added)} added, {len(skipped)} skipped, {malformed} malformed)")

    elif args.cmd == "milestone-state":
        from .context.milestone_state import compute_milestone_state

        repo_root = os.path.abspath(args.repo_root)
        batch_id: str = args.batch_id

        # Locate the plan file: <spec_root>/impl_context/ms_<batch_id>_plan.json
        if getattr(args, "spec_root", None):
            spec_root = os.path.abspath(args.spec_root)
        else:
            spec_root = os.path.join(repo_root, "spec")
        plan_path = os.path.join(
            spec_root, "impl_context", f"ms_{batch_id}_plan.json"
        )
        if not os.path.isfile(plan_path):
            print(
                f"E520 UNRESOLVED_INPUT missing_plan_file {plan_path}",
                file=sys.stderr,
            )
            sys.exit(1)

        # Locate .specdev/findings/ — host-relative (under git_root, NOT spec_root).
        # glob() returns [] for a missing/empty directory — no extra check needed.
        if getattr(args, "git_root", None):
            git_root = os.path.abspath(args.git_root)
        else:
            git_root = repo_root
        findings_dir = os.path.join(git_root, ".specdev", "findings")

        with open(plan_path, "r", encoding="utf-8") as _fh:
            plan = json.load(_fh)

        result = compute_milestone_state(plan, findings_dir, batch_id)
        print(json.dumps(result, indent=2))

    elif args.cmd == "context":
        from .context import (
            get_step_structure, resolve_scope, extract_context,
            extract_canon, check_freshness,
        )
        context_cmd = getattr(args, "context_cmd", None)
        if context_cmd is None:
            ctx_p.print_help()
        elif context_cmd == "extract":
            # DEPRECATED: extract_context is now a deprecation stub that
            # prints a migration message and exits 1.
            extract_context()
        else:
            # All non-deprecated subcommands need repo_root
            repo_root = os.path.abspath(args.repo_root)
            if context_cmd == "structure":
                spec_dir = os.path.abspath(args.spec_dir)
                result = get_step_structure(args.step, spec_dir, repo_root)
                print(json.dumps(result, indent=2))
            elif context_cmd == "scope":
                spec_dir = os.path.abspath(args.spec_dir)
                result = resolve_scope(args.entry, spec_dir, repo_root)
                print(json.dumps(result, indent=2))
            elif context_cmd == "canon":
                spec_root = os.path.abspath(args.spec_root) if getattr(args, "spec_root", None) else None
                result = extract_canon(args.step, repo_root, spec_root=spec_root)
                print(json.dumps(result, indent=2))
            elif context_cmd == "freshness":
                spec_dir = os.path.abspath(args.spec_dir)
                git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
                result = check_freshness(spec_dir, repo_root, git_root=git_root)
                print(json.dumps(result, indent=2))
                # Emit W595 (CONTENT_STALENESS) for any stale seed — §A6
                stale_seeds = [
                    sid for sid, info in result.items()
                    if isinstance(info, dict) and info.get("stale")
                ]
                if stale_seeds:
                    cfg = get_config()
                    warn_or_error = "error" if cfg.warnings_as_errors else "warning"
                    for sid in stale_seeds:
                        print(
                            f"specdev: {warn_or_error} W595: seed '{sid}' is stale — "
                            "re-index with /specdev-step (CONTENT_STALENESS)",
                            file=sys.stderr,
                        )
                    if cfg.warnings_as_errors:
                        sys.exit(1)
            elif context_cmd == "review":
                from .context.reviewer import review_artifact
                import dataclasses
                artifact_path = os.path.abspath(args.artifact_path)
                git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
                result = review_artifact(
                    artifact_path,
                    args.step,
                    os.path.abspath(args.spec_dir) if getattr(args, "spec_dir", None) else os.path.dirname(artifact_path),
                    repo_root,
                    entry_id=getattr(args, "entry", None),
                    git_root=git_root,
                )
                print(json.dumps(dataclasses.asdict(result), indent=2))
            else:
                ctx_p.print_help()

    elif args.cmd == "json":
        from .core.json_utils import main as json_main
        # Strip --spec-root / --git-root if present — the json subcommand family
        # accepts --repo-root only, but agents frequently over-apply the
        # validation/governance flag-set (per CLAUDE.md guidance) and pass all
        # three. Silently dropping these prevents a high-volume class of
        # "unrecognized arguments" failures.
        #
        # Exception: `resolve-pointers` legitimately accepts --git-root (anchors
        # relative file-path resolution) and warns-then-ignores --spec-root.
        # Skip the strip entirely for that subcommand so both signals reach
        # json_main unchanged.
        subcmd = args.args[0] if args.args else None
        if subcmd == "resolve-pointers":
            filtered = list(args.args)
        else:
            filtered = []
            i = 0
            while i < len(args.args):
                tok = args.args[i]
                if tok in ("--spec-root", "--git-root"):
                    # Drop the flag plus its value, but only when the next token
                    # looks like a value (not another flag). This protects other
                    # flags from being silently swallowed if a user wrote
                    # `--spec-root --repo-root foo` (omitted value).
                    nxt = args.args[i + 1] if i + 1 < len(args.args) else None
                    i += 2 if (nxt is not None and not nxt.startswith("--")) else 1
                    continue
                if tok.startswith("--spec-root=") or tok.startswith("--git-root="):
                    i += 1
                    continue
                filtered.append(tok)
                i += 1
        sys.argv = [sys.argv[0]] + filtered
        json_main()

    elif args.cmd == "guide":
        from .core.guide import format_guide_text, load_guides, lookup_guide
        code_arg = args.code
        guides = load_guides()
        entry = lookup_guide(code_arg, guides)
        if getattr(args, "json_output", False):
            if entry is not None:
                print(json.dumps({"code": code_arg, "guide": entry}, indent=2))
                sys.exit(0)
            else:
                print(json.dumps({"code": code_arg, "error": "no remediation guide"}, indent=2))
                sys.exit(1)
        else:
            if entry is not None:
                sys.stdout.write(format_guide_text(entry, code_arg=code_arg))
                sys.exit(0)
            else:
                print(f"no remediation guide for {code_arg}", file=sys.stderr)
                sys.exit(1)

    elif args.cmd == "registry-check":
        repo_root = os.path.abspath(args.repo_root)
        spec_root = os.path.abspath(args.spec_root)
        git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        from .validation.registry_check import run_registry_check
        errs = run_registry_check(spec_root=spec_root, repo_root=repo_root, git_root=git_root)
        if getattr(args, "json_output", False):
            _json_exit(errs, "registry-check")
        else:
            _print_and_exit_if_errors(errs)

    elif args.cmd == "registry-generate":
        repo_root = os.path.abspath(args.repo_root)
        out_path = (
            os.path.abspath(args.out)
            if args.out
            else os.path.join(repo_root, "tools", "entry_key_registry.json")
        )
        extraction_paths_out = (
            os.path.abspath(args.extraction_paths_out)
            if args.extraction_paths_out
            else os.path.join(repo_root, "tools", "extraction_paths.json")
        )
        from .registry.generate import run as registry_generate_run
        registry_generate_run(
            repo_root=repo_root,
            out_path=out_path,
            extraction_paths_out=extraction_paths_out,
        )

    elif args.cmd == "spec-check":
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        git_root = os.path.abspath(args.git_root) if getattr(args, "git_root", None) else None
        spec_root = os.path.abspath(args.spec_root) if getattr(args, "spec_root", None) else None
        project_canon_dir = _discover_project_canon_dir(git_root=git_root, spec_root=spec_root, spec_dir=spec_dir)
        if getattr(args, "json_output", False):
            from .validation.spec_check import run_spec_check_json
            errs, ctx = run_spec_check_json(repo_root, spec_dir, args.include_forward_replay, git_root, spec_root, project_canon_dir=project_canon_dir)
            _json_exit(errs, "spec-check", extra_context=ctx)
        else:
            from .validation.spec_check import run_spec_check
            errs = run_spec_check(repo_root, spec_dir, args.include_forward_replay, git_root, spec_root, project_canon_dir=project_canon_dir)
            _print_and_exit_if_errors(errs)

    else:
        p.print_help()

def cli_entry() -> None:
    """Entry point with global exception handling.

    Wraps ``main()`` so unhandled exceptions produce a clean error message
    instead of a raw traceback.  Pass ``--verbose`` (future) for full
    tracebacks during development.
    """
    try:
        main()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"specdev: fatal error: {exc}", file=sys.stderr)
        # Uncomment for development debugging:
        # traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli_entry()
