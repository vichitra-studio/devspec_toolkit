#!/usr/bin/env python3
"""p6_verify — Post-fix verification for devspec_pr_audit.

Reads a fix_plan.json produced by the devspec_pr_audit skill (Part B), executes each
task's acceptance_command in topological order (respecting deps), and reports PASS/FAIL
per task.

After all acceptance commands pass, the documented next step is to re-run
/devspec_pr_audit against the branch to confirm that previously-found findings are
closed. The re-run is a separate manual or skill-orchestrated step; this script only
validates the per-task acceptance gates.

Usage:
    python3 p6_verify.py <fix_plan_path>
    python3 p6_verify.py --fix-plan docs/audit/runs/<run-id>/fix_plan.json
    python3 p6_verify.py --run-dir docs/audit/runs/<run-id>

Exit codes:
    0 — all acceptance commands passed
    1 — one or more acceptance commands failed
    2 — input missing, JSON parse error, or cycle detected in deps
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path, label: str) -> Any:
    """Load and parse a JSON file; exit 2 on any I/O or parse error."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {label} at {path}: {exc}", file=sys.stderr)
        sys.exit(2)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"ERROR: {label} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(2)


def _topo_sort(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return tasks in topological order, validating deps and detecting cycles.

    fix_plan.json guarantees tasks are already in topological order (schema invariant:
    every dep must appear earlier in the array). This function validates that invariant
    and aborts with exit 2 on a cycle or unknown dep reference.
    """
    id_to_task: dict[str, dict[str, Any]] = {t["id"]: t for t in tasks}
    seen: set[str] = set()
    in_stack: set[str] = set()
    ordered: list[dict[str, Any]] = []

    def visit(task_id: str) -> None:
        if task_id in in_stack:
            print(
                f"ERROR: dependency cycle detected involving task '{task_id}'.",
                file=sys.stderr,
            )
            sys.exit(2)
        if task_id in seen:
            return
        in_stack.add(task_id)
        for dep_id in id_to_task.get(task_id, {}).get("deps", []):
            if dep_id not in id_to_task:
                print(
                    f"ERROR: task '{task_id}' declares unknown dep '{dep_id}'.",
                    file=sys.stderr,
                )
                sys.exit(2)
            visit(dep_id)
        in_stack.discard(task_id)
        seen.add(task_id)
        ordered.append(id_to_task[task_id])

    for task in tasks:
        visit(task["id"])

    return ordered


def _run_acceptance(cmd: str) -> tuple[bool, int]:
    """Run an acceptance_command via the shell. Returns (passed, returncode)."""
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0, result.returncode


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Post-fix verification: run each fix_plan.json task's acceptance_command "
            "in topological order and report PASS/FAIL per task."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "fix_plan_positional",
        nargs="?",
        metavar="FIX_PLAN_PATH",
        help="Path to fix_plan.json (positional form).",
    )
    ap.add_argument(
        "--fix-plan",
        dest="fix_plan_flag",
        metavar="PATH",
        help=(
            "Path to fix_plan.json (flag form; takes precedence over positional)."
        ),
    )
    ap.add_argument(
        "--run-dir",
        metavar="PATH",
        help=(
            "Audit run directory; loads fix_plan.json from <run-dir>/fix_plan.json "
            "if neither positional nor --fix-plan is given."
        ),
    )
    args = ap.parse_args(argv)

    # Resolve fix_plan path — flag > positional > --run-dir
    if args.fix_plan_flag:
        fix_plan_path = Path(args.fix_plan_flag)
    elif args.fix_plan_positional:
        fix_plan_path = Path(args.fix_plan_positional)
    elif args.run_dir:
        fix_plan_path = Path(args.run_dir) / "fix_plan.json"
    else:
        ap.error(
            "Provide fix_plan_path (positional), --fix-plan PATH, or --run-dir PATH."
        )
        return 2  # unreachable; satisfies type checker

    if not fix_plan_path.exists():
        print(f"ERROR: fix_plan not found: {fix_plan_path}", file=sys.stderr)
        return 2

    fix_plan_doc = _load_json(fix_plan_path, "fix_plan.json")
    tasks: list[dict[str, Any]] = fix_plan_doc.get("tasks", [])

    if not tasks:
        print("OK: fix_plan.json has no tasks — nothing to verify.")
        return 0

    # Topological sort validates the dep graph and detects cycles.
    ordered_tasks = _topo_sort(tasks)
    n_tasks = len(ordered_tasks)

    print(f"p6_verify: {n_tasks} task(s) from {fix_plan_path}")
    print()

    n_pass = 0
    n_fail = 0
    results: list[dict[str, Any]] = []

    for task in ordered_tasks:
        task_id = task["id"]
        cmd = task.get("acceptance_command", "")
        file_ = task.get("file", "")
        summary = task.get("change_summary", "")
        deps = task.get("deps", [])

        deps_str = f"  deps: [{', '.join(deps)}]" if deps else ""
        print(f"  [{task_id}] {file_}{deps_str}")
        print(f"   change : {summary}")
        print(f"   command: {cmd}")

        if not cmd:
            print("   result : SKIP (no acceptance_command)")
            print()
            results.append(
                {"id": task_id, "file": file_, "status": "SKIP", "exit_code": None, "command": cmd}
            )
            continue

        passed, rc = _run_acceptance(cmd)
        status = "PASS" if passed else "FAIL"
        if passed:
            n_pass += 1
        else:
            n_fail += 1

        print(f"   result : {status} (exit {rc})")
        print()
        results.append(
            {"id": task_id, "file": file_, "status": status, "exit_code": rc, "command": cmd}
        )

    # Summary
    n_run = n_pass + n_fail
    print(f"Summary: {n_pass}/{n_run} PASS, {n_fail}/{n_run} FAIL")
    print()

    if n_fail == 0:
        print("All acceptance commands passed.")
        print(
            "Next step: re-run /devspec_pr_audit against the branch to confirm "
            "previously-found findings are closed (see protocol §12)."
        )
        return 0

    failed_ids = [r["id"] for r in results if r["status"] == "FAIL"]
    print(
        f"FAIL: {n_fail} acceptance command(s) failed "
        f"({', '.join(failed_ids)}). "
        "Repair the listed tasks before re-running the audit."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
