from __future__ import annotations
import argparse, os, json, sys
from .validate import validate_file, validate_dir
from .matrix import build_trace_matrix
from .fixtures_runner import lint_fixtures
from .invariants import run_invariants
from .governance import check_commit_message
from .scaffold import generate_scaffold
from .ci_gen import generate_ci_yaml


def main():
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

    ci = sub.add_parser("gen-ci")
    ci.add_argument("spec_dir")
    ci.add_argument("--out", default="-")
    ci.add_argument("--toolkit-path", default="./devspec_toolkit",
                    help="Relative path to the toolkit inside the host repository (defaults to ./devspec_toolkit)")

    sc = sub.add_parser("scaffold")
    sc.add_argument("spec_dir")
    sc.add_argument("--out", required=True)
    sc.add_argument("--repo-root", default=".")

    # Add a new command for AI interaction help
    ai = sub.add_parser("ai-help")
    ai.add_argument("--step", help="Specific step to get help for")

    # Add a new command for performance benchmarking
    bench = sub.add_parser("benchmark")
    bench.add_argument("--test", help="Test to benchmark")
    bench.add_argument("--iterations", type=int, default=1, help="Number of iterations")

    args = p.parse_args()

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
        if args.out == "-": print(out)
        else:
            with open(args.out, "w", encoding="utf-8") as f: f.write(out)
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
    elif args.cmd == "gen-ci":
        yml = generate_ci_yaml(args.toolkit_path)
        if args.out == "-":
            print(yml)
        else:
            with open(args.out, "w", encoding="utf-8") as f: f.write(yml)
            print(args.out)
    elif args.cmd == "scaffold":
        spec_dir = os.path.abspath(args.spec_dir)
        files = generate_scaffold(spec_dir, args.out)
        print("\n".join(files))
    elif args.cmd == "ai-help":
        if args.step:
            print(f"AI help for step {args.step}:")
            print(f"1. Read the guide: spec/{args.step}_*.guide.md")
            print(f"2. Run the prompt: prompts/prompt_{args.step}_*.md")
            print(f"3. Paste output into spec/{args.step}_*.json")
            print(f"4. Validate: python -m specdev_tools.cli validate spec/{args.step}_*.json")
        else:
            print("AI Interaction Guide:")
            print("1. Read the corresponding guide.md file")
            print("2. Run the prompt from prompts/prompt_XX_stepname.md")
            print("3. Paste only the fenced JSON block into spec/NN_name.json")
            print("4. Validate with: python -m specdev_tools.cli validate spec/NN_name.json")
            print("5. Follow the DoR requirements from the guide")
            print("6. Ensure all IDs use kebab-case format")
            print("7. No examples should be included in the AI output")
    elif args.cmd == "benchmark":
        print("Benchmarking functionality would be implemented here")
        print("(This is a placeholder for performance testing)")
        if args.test:
            print(f"Benchmarking test: {args.test}")
        print(f"Iterations: {args.iterations}")
    else:
        p.print_help()

if __name__ == "__main__":
    main()
