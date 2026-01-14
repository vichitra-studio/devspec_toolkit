from __future__ import annotations
import argparse, os, json, sys
from pathlib import Path
from .validate import validate_file, validate_dir
from .matrix import build_trace_matrix
from .fixtures_lint import lint_fixtures
from .invariants import run_invariants
from .governance import check_commit_message
from .changelog_parser import (
    list_versions,
    load_version,
    get_toolkit_version,
    validate_changelog,
)
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


def check_venv():
    # Helper to check if we are running in a virtual environment
    # sys.prefix != sys.base_prefix is the standard check for venv/virtualenv
    if sys.prefix == sys.base_prefix:
        print("Warning: Running without a virtual environment. Please activate 'devspec_env' or similar.", file=sys.stderr)

def main():
    check_venv()
    p = argparse.ArgumentParser(prog="specdev-tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate")
    v.add_argument("file")
    v.add_argument("--repo-root", default=".")

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
        # Auto-detect toolkit root if running from project root
        potential_submodule = Path("devspec_toolkit")
        if potential_submodule.exists() and (potential_submodule / "tools" / "pyproject.toml").exists():
             args.repo_root = str(potential_submodule)
             
    if args.cmd == "validate":
        repo_root = os.path.abspath(args.repo_root)
        file_path = os.path.abspath(args.file)
        errs = validate_file(repo_root, file_path)
        if errs:
            for e in errs: print(e, file=sys.stderr)
            sys.exit(1)
        print("OK")
    elif args.cmd == "validate-all":
        repo_root = os.path.abspath(args.repo_root)
        spec_dir = os.path.abspath(args.spec_dir)
        errs = validate_dir(repo_root, spec_dir)
        if errs:
            for e in errs: print(e, file=sys.stderr)
            sys.exit(1)
        print("OK")
    elif args.cmd == "matrix":
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
    elif args.cmd == "fixtures-lint":
        spec_dir = os.path.abspath(args.spec_dir)
        errs = lint_fixtures(spec_dir)
        if errs:
            for e in errs: print(e, file=sys.stderr)
            sys.exit(1)
        print("OK")
    elif args.cmd == "invariants-check":
        spec_dir = os.path.abspath(args.spec_dir)
        sample = json.load(open(args.sample, "r", encoding="utf-8"))
        res = run_invariants(spec_dir, sample)
        print(json.dumps(res, indent=2))
    elif args.cmd == "governance-check":
        spec_dir = os.path.abspath(args.spec_dir)
        errs = check_commit_message(spec_dir, args.message)
        if errs:
            for e in errs: print(e, file=sys.stderr)
            sys.exit(1)
        print("OK")
    elif args.cmd == "ai-help":
        if args.step:
            print(f"AI help for step {args.step}:")
            print(f"1. Open the prompt file: prompts/prompt_{args.step}_*.md")
            print(f"2. Copy the content into your AI assistant")
            print(f"3. Paste the AI output into spec/{args.step}_*.json")
            print(f"4. Validate: python -m specdev_tools.cli validate spec/{args.step}_*.json --repo-root ./devspec_toolkit")
        else:
            print("AI Interaction Guide:")
            print("1. Locate the prompt file in prompts/prompt_XX_stepname.md")
            print("2. Copy the full content into your AI assistant")
            print("3. Paste only the fenced JSON block into spec/NN_name.json")
            print("4. Validate with: python -m specdev_tools.cli validate spec/NN_name.json --repo-root ./devspec_toolkit")
            print("5. Ensure all IDs use kebab-case format")
            print("6. No examples should be included in the AI output")
    elif args.cmd == "changelog":
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
