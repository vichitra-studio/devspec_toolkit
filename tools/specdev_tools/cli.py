from __future__ import annotations
import argparse, os, json, re, sys
from pathlib import Path
# Lazy imports handled inside main/command blocks to improve CLI responsiveness

WARNING_CODE_RE = re.compile(r"^\s*W\d{3}\b")


def _is_warning_message(message: str) -> bool:
    return bool(WARNING_CODE_RE.match(message or ""))


def _warnings_as_errors() -> bool:
    return os.getenv("SPECDEV_WARNINGS_AS_ERRORS", "").strip().lower() in {"1", "true", "yes"}


def _has_error_messages(messages: list[str]) -> bool:
    if _warnings_as_errors():
        return bool(messages)
    return any(not _is_warning_message(message) for message in messages)
def _print_and_exit_if_errors(errs: list[str]) -> None:
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
    if _has_error_messages(errs):
        sys.exit(1)
    if errs:
        print("OK (warnings)")
    else:
        print("OK")


def check_venv():
    # Helper to check if we are running in a virtual environment
    # sys.prefix != sys.base_prefix is the standard check for venv/virtualenv
    if sys.prefix == sys.base_prefix:
        print("Error: Running without a virtual environment. Please activate 'devspec_env' or similar.", file=sys.stderr)
        sys.exit(1)

def main():
    check_venv()
    p = argparse.ArgumentParser(prog="specdev-tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate")
    v.add_argument("file")
    v.add_argument("--repo-root", default=".")
    v.add_argument("--json", action="store_true", help="Output results as JSON")

    va = sub.add_parser("validate-all")
    va.add_argument("spec_dir")
    va.add_argument("--repo-root", default=".")

    m = sub.add_parser("matrix")
    m.add_argument("spec_dir")
    m.add_argument("--out", default="-")
    m.add_argument("--repo-root", default=".")

    fx = sub.add_parser("fixtures-lint")
    fx.add_argument("spec_dir")
    fx.add_argument("--repo-root", default=".")

    inv = sub.add_parser("invariants-check")
    inv.add_argument("spec_dir")
    inv.add_argument("--sample", required=True)
    inv.add_argument("--repo-root", default=".")

    sl = sub.add_parser("seed-lint")
    sl.add_argument("spec_dir")
    sl.add_argument("--repo-root", default=".")

    dl = sub.add_parser("docs-lint")
    dl.add_argument("spec_dir")
    dl.add_argument("--repo-root", default=".")

    ps = sub.add_parser("prompt-sync")
    ps.add_argument("spec_dir", nargs="?")
    ps.add_argument("--repo-root", default=".")

    cl = sub.add_parser("canonical-lint")
    cl.add_argument("canon_dir", nargs="?", default="canon")
    cl.add_argument("--repo-root", default=".")

    ci = sub.add_parser("canonical-integrity")
    ci.add_argument("spec_dir")
    ci.add_argument("--repo-root", default=".")
    ci.add_argument("--canon-dir", default="canon")

    ca = sub.add_parser("canonical-autofix")
    ca.add_argument("spec_dir")
    ca.add_argument("--repo-root", default=".")
    ca.add_argument("--canon-dir", default="canon")
    ca_mode = ca.add_mutually_exclusive_group()
    ca_mode.add_argument("--write", action="store_true", help="Write changes to files")
    ca_mode.add_argument("--dry-run", action="store_true", help="Report changes without writing files")

    sql = sub.add_parser("spec-quality-lint")
    sql.add_argument("spec_dir")
    sql.add_argument("--repo-root", default=".")

    hl = sub.add_parser("hallucination-lint")
    hl.add_argument("spec_dir")
    hl.add_argument("--repo-root", default=".")
    hl.add_argument("--canon-dir", default="canon")

    tc = sub.add_parser("traceability-check")
    tc.add_argument("spec_dir")
    tc.add_argument("--repo-root", default=".")
    tc.add_argument("--json", action="store_true", help="Output results as JSON")

    dol = sub.add_parser("dependency-order-lint")
    dol.add_argument("--repo-root", default=".")

    frc = sub.add_parser("forward-replay-check")
    frc.add_argument("--repo-root", default=".")
    frc.add_argument("--base-ref", help="Diff base ref (default: auto-resolved in validate-all)")
    frc.add_argument("--diff-error-mode", choices=["error", "ignore"], default="error")

    gov = sub.add_parser("governance-check")
    gov.add_argument("spec_dir")
    gov.add_argument("--message", required=True)
    gov.add_argument("--repo-root", default=".")

    ai = sub.add_parser("ai-help")
    ai.add_argument("--step", help="Specific step to get help for")

    # Changelog commands (Phase 2: Changelog Parser)
    ch = sub.add_parser("changelog", help="Changelog and version utilities")
    ch.add_argument("--list", action="store_true", help="List all available versions")
    ch.add_argument("--version", help="Show details for a specific version")
    ch.add_argument("--validate", help="Validate a version's changelog")
    ch.add_argument("--repo-root", default=".")

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

    args = p.parse_args()

    if args.repo_root == ".":
        # Auto-detect toolkit root by scanning immediate subdirectories
        current_dir = Path(".")
        found = False
        for child in current_dir.iterdir():
            if child.is_dir():
                 potential_marker = child / "tools" / "specdev_tools" / "__init__.py"
                 if potential_marker.exists():
                     args.repo_root = str(child)
                     found = True
                     break
             
    if args.cmd == "validate":
        from .validate import validate_file
        repo_root = os.path.abspath(args.repo_root)
        file_path = os.path.abspath(args.file)
        errs = validate_file(repo_root, file_path)
        if args.json:
            output = []
            if errs:
                for e in errs:
                    output.append(
                        {
                            "file": file_path,
                            "error": e,
                            "status": "WARN" if _is_warning_message(e) else "FAIL",
                        }
                    )
            else:
                output.append({"file": file_path, "status": "PASS"})
            print(json.dumps(output, indent=2))
            if _has_error_messages(errs):
                sys.exit(1)
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "validate-all":
        from .validate import validate_dir
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        errs = validate_dir(repo_root, spec_dir)
        _print_and_exit_if_errors(errs)
    elif args.cmd == "matrix":
        from .matrix import build_trace_matrix
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        res = build_trace_matrix(repo_root, spec_dir)
        out = json.dumps(res, indent=2)
        if args.out == "-":
            print(out)
        else:
            out_path = os.path.abspath(args.out)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(out)
            print(args.out)
        matrix_strict = os.getenv("SPECDEV_MATRIX_STRICT", "").strip().lower() in {"1", "true", "yes"}
        integrity_errors = res.get("integrity_errors")
        if matrix_strict and isinstance(integrity_errors, list) and integrity_errors:
            print(f"E210 TRACE_INTEGRITY matrix_failed count={len(integrity_errors)}", file=sys.stderr)
            for error in integrity_errors:
                print(error, file=sys.stderr)
            sys.exit(1)
    elif args.cmd == "fixtures-lint":
        from .fixtures_lint import lint_fixtures
        spec_dir = os.path.abspath(args.spec_dir)
        errs = lint_fixtures(spec_dir)
        _print_and_exit_if_errors(errs)
    elif args.cmd == "invariants-check":
        from .invariants import run_invariants
        spec_dir = os.path.abspath(args.spec_dir)
        sample = json.load(open(args.sample, "r", encoding="utf-8"))
        res = run_invariants(spec_dir, sample)
        print(json.dumps(res, indent=2))
    elif args.cmd == "seed-lint":
        from .seed_lint import lint_seeds
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        errs = lint_seeds(repo_root, spec_dir)
        _print_and_exit_if_errors(errs)
    elif args.cmd == "docs-lint":
        from .docs_lint import lint_docs
        spec_dir = os.path.abspath(args.spec_dir)
        errs = lint_docs(spec_dir)
        _print_and_exit_if_errors(errs)
    elif args.cmd == "prompt-sync":
        from .prompt_schema_sync import run_prompt_schema_sync
        repo_root = os.path.abspath(args.repo_root)
        expected_spec_dir = os.path.abspath(os.path.join(repo_root, "spec"))
        if args.spec_dir:
            spec_dir = os.path.abspath(args.spec_dir)
            if spec_dir != expected_spec_dir:
                print(
                    f"E520 UNRESOLVED_INPUT prompt_sync_spec_dir_must_equal_repo_spec "
                    f"provided={spec_dir} expected={expected_spec_dir}",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            spec_dir = expected_spec_dir
        if not os.path.isdir(spec_dir):
            print(f"E520 UNRESOLVED_INPUT missing_spec_dir {spec_dir}", file=sys.stderr)
            sys.exit(1)
        errs = run_prompt_schema_sync(repo_root)
        _print_and_exit_if_errors(errs)
    elif args.cmd == "canonical-lint":
        from .canonical_lint import lint_canon_dir
        repo_root = os.path.abspath(args.repo_root)
        errs = lint_canon_dir(
            repo_root,
            canon_dir=args.canon_dir,
            require_manifest_schema_registration=True,
        )
        _print_and_exit_if_errors(errs)
    elif args.cmd == "canonical-integrity":
        from .canonical_integrity import validate_canonical_integrity
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        errs = validate_canonical_integrity(
            repo_root,
            spec_dir,
            canon_dir=args.canon_dir,
            require_manifest_schema_registration=True,
        )
        _print_and_exit_if_errors(errs)
    elif args.cmd == "canonical-autofix":
        from .canonical_autofix import canonical_autofix
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        if not os.path.isdir(spec_dir):
            print(f"E520 UNRESOLVED_INPUT missing_spec_dir {spec_dir}", file=sys.stderr)
            sys.exit(1)
        write = bool(args.write and not args.dry_run)
        changes = canonical_autofix(
            repo_root,
            spec_dir,
            write=write,
            canon_dir=args.canon_dir,
            require_manifest_schema_registration=True,
        )
        if not changes:
            print("OK (no changes)")
            return
        has_errors = False
        error_lines: list[str] = []
        non_error_by_file: list[tuple[str, list[str]]] = []
        for file_path, file_changes in sorted(changes.items()):
            non_error_changes = []
            for change in file_changes:
                if change.startswith("E"):
                    error_lines.append(change)
                    has_errors = True
                else:
                    non_error_changes.append(change)
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
        from .spec_quality_lint import lint_spec_quality
        spec_dir = os.path.abspath(args.spec_dir)
        errs = lint_spec_quality(spec_dir)
        _print_and_exit_if_errors(errs)
    elif args.cmd == "hallucination-lint":
        from .hallucination_lint import lint_hallucinations
        spec_dir = os.path.abspath(args.spec_dir)
        repo_root = os.path.abspath(args.repo_root)
        if not os.path.isdir(spec_dir):
            print(f"E520 UNRESOLVED_INPUT missing_spec_dir {spec_dir}", file=sys.stderr)
            sys.exit(1)
        errs = lint_hallucinations(
            spec_dir,
            repo_root=repo_root,
            canon_dir=args.canon_dir,
            require_canon_dir=True,
            require_manifest_schema_registration=True,
        )
        _print_and_exit_if_errors(errs)
    elif args.cmd == "traceability-check":
        from .traceability_closure import check_traceability_closure
        spec_dir = os.path.abspath(args.spec_dir)
        repo_root = os.path.abspath(args.repo_root)
        errs = check_traceability_closure(spec_dir, repo_root)
        if getattr(args, "json", False):
            output = []
            if errs:
                for e in errs:
                    output.append(
                        {
                            "file": spec_dir,
                            "error": e,
                            "status": "WARN" if _is_warning_message(e) else "FAIL",
                        }
                    )
            else:
                output.append({"file": spec_dir, "status": "PASS"})
            print(json.dumps(output, indent=2))
            if _has_error_messages(errs):
                sys.exit(1)
        else:
            _print_and_exit_if_errors(errs)
    elif args.cmd == "dependency-order-lint":
        from .dependency_order_lint import lint_dependency_order
        repo_root = os.path.abspath(args.repo_root)
        errs = lint_dependency_order(repo_root)
        _print_and_exit_if_errors(errs)
    elif args.cmd == "forward-replay-check":
        from .forward_replay_check import check_forward_replay
        from .validate import _resolve_replay_base_ref
        repo_root = os.path.abspath(args.repo_root)
        base_ref = args.base_ref or _resolve_replay_base_ref(repo_root)
        errs = check_forward_replay(
            repo_root,
            base_ref=base_ref,
            diff_error_mode=args.diff_error_mode,
        )
        _print_and_exit_if_errors(errs)
    elif args.cmd == "governance-check":
        from .governance import check_commit_message
        spec_dir = os.path.abspath(args.spec_dir)
        msg = args.message
        if os.path.exists(msg) and os.path.isfile(msg):
            try:
                msg = open(msg, "r", encoding="utf-8").read().strip()
            except Exception:
                pass
        errs = check_commit_message(spec_dir, msg)
        _print_and_exit_if_errors(errs)
    elif args.cmd == "ai-help":
        if args.step:
            print(f"AI help for step {args.step}:")
            print(f"1. Open the prompt file: prompts/prompt_{args.step}_*.md")
            print(f"2. Copy the content into your AI assistant")
            print(f"3. Write the AI-produced JSON directly to spec/{args.step}_*.json")
            print(f"4. Validate: python -m specdev_tools.cli validate spec/{args.step}_*.json --repo-root <toolkit_dir>")
        else:
            print("AI Interaction Guide:")
            print("1. Locate the prompt file in prompts/prompt_XX_stepname.md")
            print("2. Copy the full content into your AI assistant")
            print("3. Write the JSON artifact directly to spec/NN_name.json")
            print("4. Validate with: python -m specdev_tools.cli validate spec/NN_name.json --repo-root <toolkit_dir>")
            print("5. Ensure all IDs use kebab-case format")
            print("6. No examples should be included in the AI output")
    elif args.cmd == "changelog":
        from .changelog_parser import (
            list_versions,
            load_version,
            get_toolkit_version,
            validate_changelog,
        )
        repo_root = Path(os.path.abspath(args.repo_root))
        changelog_dir = repo_root / "changelog"
        
        if args.list:
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
            # Show details for a specific version
            try:
                changelog = load_version(changelog_dir, args.version)
                print(f"Version: {changelog.version}")
                print(f"Release Date: {changelog.release_date}")
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
            if errs:
                for e in errs:
                    print(e, file=sys.stderr)
                sys.exit(1)
            print(f"OK - v{args.validate} is valid")
        else:
            print("Usage: specdev changelog [--list] [--version X.Y.Z] [--validate X.Y.Z]")
            print("  --list       List all available versions")
            print("  --version    Show details for a specific version")
            print("  --validate   Validate a version's changelog against format.yaml")
    elif args.cmd == "align":
        from .schema_differ import (
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
        from .prompt_generator import (
            generate_prompts,
            write_prompts,
            format_prompts_report,
        )
        repo_root = Path(os.path.abspath(args.repo_root))
        spec_dir = Path(os.path.abspath(args.spec_dir))
        
        if not spec_dir.exists():
            print(f"Error: Spec directory not found: {spec_dir}", file=sys.stderr)
            sys.exit(1)
        
        diff = diff_spec_directory(spec_dir, repo_root)
        
        if args.action == "status":
            print(format_status_report(diff))
        elif args.action == "diff":
            print(format_diff_report(diff))
        elif args.action == "plan":
            # Show detailed execution plan
            print(format_plan_report(diff))
        elif args.action == "apply":
            if not args.auto:
                print("Error: Use --auto flag to apply mechanical fixes", file=sys.stderr)
                print("       Full apply (including AI-assisted) is not yet supported")
                sys.exit(1)
            
            # Pre-migration validation
            validation = validate_pre_migration(spec_dir, repo_root)
            for warning in validation.warnings:
                print(f"⚠️  Warning: {warning}", file=sys.stderr)
            if not validation.can_proceed:
                for error in validation.errors:
                    print(f"❌ Error: {error}", file=sys.stderr)
                sys.exit(1)
            
            result = apply_auto_fixes(diff, spec_dir, repo_root, dry_run=args.dry_run)
            print(format_apply_report(result))
        elif args.action == "prompts":
            # Generate AI prompts for semantic migrations
            prompts = generate_prompts(
                diff, 
                repo_root, 
                spec_dir, 
                mode=args.mode,
            )
            
            if args.output:
                output_dir = Path(args.output)
                write_prompts(prompts, output_dir)
                print(f"✅ Generated {len(prompts)} prompt(s) in {output_dir}/")
            
            print(format_prompts_report(prompts))
        elif args.action == "rollback":
            backups = list_backups(spec_dir)
            if not backups:
                print("No backups found in spec/migration_backups/")
                sys.exit(0)
            print("\n🔙 Available Backups")
            print("━" * 20)
            for i, backup in enumerate(backups, 1):
                print(f"  {i}. {backup.backup_dir.name}")
            
            # Interactive selection
            try:
                choice = input("\nSelect backup to restore [1]: ").strip()
                idx = int(choice) - 1 if choice else 0
                if 0 <= idx < len(backups):
                    selected = backups[idx]
                    confirm = input(f"Restore from {selected.backup_dir.name}? [y/N]: ").strip().lower()
                    if confirm == 'y':
                        restore_backup(spec_dir, selected)
                        log_operation(spec_dir, f"Restored from {selected.backup_dir.name}", "success")
                        print(f"✅ Restored from {selected.backup_dir.name}")
                    else:
                        print("Cancelled.")
                else:
                    print("Invalid selection.")
            except (ValueError, EOFError, KeyboardInterrupt):
                print("\nCancelled.")
        elif args.action == "validate":
             # Post-migration validation
            from .schema_differ import validate_post_migration, get_toolkit_version
            
            toolkit_version = get_toolkit_version(repo_root)
            if not toolkit_version:
                print("Error: Could not determine toolkit version", file=sys.stderr)
                sys.exit(1)

            print("🔍 Post-Migration Validation")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            result = validate_post_migration(spec_dir, repo_root, toolkit_version)
            
            # Print warnings
            if result.warnings:
                print("\n⚠️  Warnings:")
                for w in result.warnings:
                    print(f"  - {w}")

            # Print errors
            if result.errors:
                print("\n❌ Errors:")
                for e in result.errors:
                    print(f"  - {e}")
                print("\nResult: ❌ FAILED")
                sys.exit(1)
            
            print("\n✅ Trace Integrity: OK")
            print(f"✅ Toolkit Version: {toolkit_version}")
            print("\nResult: ✅ PASSED")
            print("Migration complete. spec/specdev_version updated.")

    else:
        p.print_help()

if __name__ == "__main__":
    main()
