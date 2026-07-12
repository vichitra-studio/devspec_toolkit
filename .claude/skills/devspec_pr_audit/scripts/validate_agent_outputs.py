#!/usr/bin/env python3
"""CI / pre-commit gate: validate every agent-produced artifact in a devspec_pr_audit run.

Given a run directory, discovers all known artifact families, validates each against
its JSON Schema (Draft 2020-12), and lints fix_plan.json for vacuous acceptance commands
via assert_meaningful_acceptance.py.

The run_id is taken from the run directory base-name (run_dir.name).

Usage:
    python3 validate_agent_outputs.py --run-dir <path> [--strict] [--write-report <path>]

Exit codes:
    0 — all checks passed (or all issues are warnings and --strict not set)
    1 — one or more violations
    2 — missing inputs or unexpected error
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
except ImportError:  # pragma: no cover
    print(
        "ERROR: jsonschema is not installed. "
        "Activate the project venv before running this script.",
        file=sys.stderr,
    )
    sys.exit(2)

# ---------------------------------------------------------------------------
# Paths anchored to script location
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
# scripts/ → devspec_pr_audit/ → skills/ → .claude/  (parents[0..2])
# → devspec_toolkit/  (parents[3])
_TOOLKIT_ROOT = _SCRIPT_DIR.parents[3]
_INFRA_SCHEMA_DIR = _TOOLKIT_ROOT / "schema" / "infra"
_ASSERT_ACCEPTANCE_SCRIPT = _SCRIPT_DIR / "assert_meaningful_acceptance.py"

_FINDINGS_SCHEMA = _INFRA_SCHEMA_DIR / "findings.schema.json"
_FIX_PLAN_SCHEMA = _INFRA_SCHEMA_DIR / "pr_audit_fix_plan.schema.json"

# Manifest required top-level keys (two accepted timestamp variants)
_MANIFEST_REQUIRED_KEYS: list[str] = [
    "run_id",
    "branch",
    "base_sha",
    "head_sha",
    "phases_completed",
]
# Timestamps: accept either started_at OR created_at (real manifests use created_at)
_MANIFEST_TIMESTAMP_VARIANTS: list[tuple[str, str]] = [
    ("started_at", "updated_at"),
    ("created_at", "updated_at"),
]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

Violation = dict[str, str]  # {json_pointer|rule, message} or {rule, line, message}


class ArtifactResult:
    """Result for a single artifact check."""

    def __init__(
        self,
        artifact: str,
        schema: str,
        status: str,  # pass | fail | skip-no-schema | skip-not-present | warn
        violations: list[Violation] | None = None,
        is_warning: bool = False,
    ) -> None:
        self.artifact = artifact
        self.schema = schema
        self.status = status
        self.violations: list[Violation] = violations or []
        self.is_warning = is_warning


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _load_json_file(path: Path) -> tuple[Any, str | None]:
    """Load and parse a JSON file. Returns (data, error_message)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"cannot read {path}: {exc}"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error in {path}: {exc}"


def _load_schema(schema_path: Path) -> tuple[Any, str | None]:
    """Load and check a JSON Schema file. Returns (schema, error_message)."""
    data, err = _load_json_file(schema_path)
    if err:
        return None, err
    try:
        Draft202012Validator.check_schema(data)
    except SchemaError as exc:
        return None, f"schema at {schema_path} is not valid: {exc.message}"
    return data, None


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------


def _validate_against_schema(
    artifact_path: Path,
    schema_path: Path,
    run_dir: Path,
) -> ArtifactResult:
    """Validate artifact_path against schema_path. Returns ArtifactResult."""
    rel = str(artifact_path.relative_to(run_dir))

    if not artifact_path.exists():
        return ArtifactResult(rel, str(schema_path), "skip-not-present")

    schema_label = schema_path.name

    schema, schema_err = _load_schema(schema_path)
    if schema_err:
        return ArtifactResult(
            rel,
            schema_label,
            "fail",
            [{"json_pointer": "(schema load)", "message": schema_err}],
        )

    data, data_err = _load_json_file(artifact_path)
    if data_err:
        return ArtifactResult(
            rel,
            schema_label,
            "fail",
            [{"json_pointer": "(file load)", "message": data_err}],
        )

    validator = Draft202012Validator(schema)
    raw_errors = sorted(
        validator.iter_errors(data), key=lambda e: list(e.absolute_path)
    )

    if not raw_errors:
        return ArtifactResult(rel, schema_label, "pass")

    violations: list[Violation] = []
    for err in raw_errors:
        parts = list(err.absolute_path)
        if parts:
            pointer = "".join(f"/{p}" for p in parts)
        else:
            pointer = "(document root)"
        violations.append({"json_pointer": pointer, "message": err.message})

    return ArtifactResult(rel, schema_label, "fail", violations)


def _validate_manifest_keys(manifest_path: Path, run_dir: Path) -> ArtifactResult:
    """Validate manifest.json has required top-level keys (no schema file present)."""
    rel = str(manifest_path.relative_to(run_dir))
    schema_label = "(key-presence check)"

    if not manifest_path.exists():
        return ArtifactResult(rel, schema_label, "skip-not-present")

    data, err = _load_json_file(manifest_path)
    if err:
        return ArtifactResult(
            rel, schema_label, "fail", [{"json_pointer": "(file load)", "message": err}]
        )

    violations: list[Violation] = []

    for key in _MANIFEST_REQUIRED_KEYS:
        if key not in data:
            violations.append({"json_pointer": f"/{key}", "message": f"required key '{key}' is missing"})

    # phases_completed must be an array
    if "phases_completed" in data and not isinstance(data["phases_completed"], list):
        violations.append({
            "json_pointer": "/phases_completed",
            "message": "must be an array of integers",
        })

    # Accept either (started_at + updated_at) OR (created_at + updated_at)
    ts_ok = any(
        ts_start in data and ts_end in data
        for ts_start, ts_end in _MANIFEST_TIMESTAMP_VARIANTS
    )
    if not ts_ok:
        violations.append({
            "json_pointer": "/(timestamps)",
            "message": (
                "manifest must contain either 'started_at'+'updated_at' "
                "or 'created_at'+'updated_at'"
            ),
        })

    status = "fail" if violations else "pass"
    return ArtifactResult(rel, schema_label, status, violations)


def _run_acceptance_lint(fix_plan_path: Path, run_dir: Path) -> ArtifactResult:
    """Run assert_meaningful_acceptance.py on fix_plan.json and return supplemental result."""
    rel = str(fix_plan_path.relative_to(run_dir))
    label = "acceptance-lint"

    if not _ASSERT_ACCEPTANCE_SCRIPT.exists():
        return ArtifactResult(
            rel,
            label,
            "skip-no-schema",
            [],
            is_warning=True,
        )

    result = subprocess.run(
        [sys.executable, str(_ASSERT_ACCEPTANCE_SCRIPT), "--fix-plan", str(fix_plan_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return ArtifactResult(rel, label, "pass")

    if result.returncode == 2:
        # Input error from the lint script
        return ArtifactResult(
            rel,
            label,
            "fail",
            [{"rule": "input-error", "message": result.stderr.strip()}],
        )

    # returncode == 1: violations found
    violations: list[Violation] = []
    for line in result.stderr.splitlines():
        line = line.strip()
        if line.startswith("VIOLATION"):
            violations.append({"rule": "acceptance-lint", "message": line})

    # Also capture the summary from stdout
    summary = result.stdout.strip()
    if summary:
        violations.append({"rule": "acceptance-lint-summary", "message": summary})

    return ArtifactResult(rel, label, "fail", violations)


# ---------------------------------------------------------------------------
# Discovery and orchestration
# ---------------------------------------------------------------------------


def _discover_and_validate(run_dir: Path) -> list[ArtifactResult]:
    """Discover all artifact families and validate each.

    Produces facts only — policy decisions (strict mode, exit code) belong to main().
    skip-no-schema entries are informational (is_warning=False): they represent
    files that legitimately have no registered schema, not defects. --strict only
    escalates real warnings (e.g., schema-validation issues on files that do have
    a schema).

    Returns list of results.
    """
    results: list[ArtifactResult] = []

    # 1. findings.json (P4 consolidated)
    findings_path = run_dir / "findings.json"
    results.append(_validate_against_schema(findings_path, _FINDINGS_SCHEMA, run_dir))

    # 2. fix_plan.json (P4 consolidated) — schema validation
    fix_plan_path = run_dir / "fix_plan.json"
    results.append(_validate_against_schema(fix_plan_path, _FIX_PLAN_SCHEMA, run_dir))

    # 2b. fix_plan.json — acceptance lint (supplemental check)
    if fix_plan_path.exists():
        results.append(_run_acceptance_lint(fix_plan_path, run_dir))

    # 3. p2/tier1_*_findings.json and p2/tier2_*_findings.json
    p2_dir = run_dir / "p2"
    if p2_dir.is_dir():
        tier_files = sorted(
            list(p2_dir.glob("tier1_*_findings.json"))
            + list(p2_dir.glob("tier2_*_findings.json"))
        )
        for tf in tier_files:
            results.append(_validate_against_schema(tf, _FINDINGS_SCHEMA, run_dir))
    else:
        # Record as skip-not-present so the report is informative
        results.append(
            ArtifactResult("p2/", "(directory)", "skip-not-present")
        )

    # 4. p3/cross_boundary_findings.json (optional)
    p3_path = run_dir / "p3" / "cross_boundary_findings.json"
    if p3_path.exists():
        results.append(_validate_against_schema(p3_path, _FINDINGS_SCHEMA, run_dir))
    else:
        results.append(
            ArtifactResult(
                "p3/cross_boundary_findings.json",
                _FINDINGS_SCHEMA.name,
                "skip-not-present",
            )
        )

    # 5. iter_p1_*_review.json and iter_p4_*_review.json — schema optional
    iter_schema_names = ["iter_review.schema.json", "iter_p1_review.schema.json", "iter_p4_review.schema.json"]
    iter_schema: Path | None = None
    for sn in iter_schema_names:
        candidate = _INFRA_SCHEMA_DIR / sn
        if candidate.exists():
            iter_schema = candidate
            break

    iter_files = sorted(
        list(run_dir.glob("iter_p1_*_review.json"))
        + list(run_dir.glob("iter_p4_*_review.json"))
    )
    for itf in iter_files:
        rel = str(itf.relative_to(run_dir))
        if iter_schema is None:
            print(
                f"INFO: no schema for iter review artifacts; skipping {rel}",
                file=sys.stdout,
            )
            results.append(ArtifactResult(rel, "(none)", "skip-no-schema", is_warning=False))
        else:
            results.append(_validate_against_schema(itf, iter_schema, run_dir))

    # 6. manifest.json — key-presence check (no schema file)
    manifest_schema = _INFRA_SCHEMA_DIR / "manifest.schema.json"
    manifest_path = run_dir / "manifest.json"
    if manifest_schema.exists():
        results.append(_validate_against_schema(manifest_path, manifest_schema, run_dir))
    else:
        results.append(_validate_manifest_keys(manifest_path, run_dir))

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _summarize(results: list[ArtifactResult]) -> dict[str, int]:
    total = len(results)
    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    skipped = sum(
        1 for r in results if r.status in ("skip-no-schema", "skip-not-present", "warn")
    )
    return {"total": total, "passed": passed, "failed": failed, "skipped": skipped}


def _print_summary(run_id: str, results: list[ArtifactResult]) -> None:
    summary = _summarize(results)
    warned = [r for r in results if r.is_warning]
    print(f"validate_agent_outputs.py — run {run_id}")
    print(f"  {summary['total']} artifacts scanned")
    skipped_no_schema = sum(1 for r in results if r.status == "skip-no-schema")
    print(
        f"  {summary['passed']} passed, "
        f"{summary['failed']} failed, "
        f"{summary['skipped']} skipped ({skipped_no_schema} no-schema info)"
    )
    if warned:
        print(f"  WARNINGS: {len(warned)}")
    failed_results = [r for r in results if r.status == "fail"]
    if failed_results:
        print()
        for r in failed_results:
            first = r.violations[0] if r.violations else {}
            first_msg = (
                first.get("message") or first.get("rule") or "(unknown violation)"
            )
            pointer = first.get("json_pointer") or first.get("rule") or ""
            loc = f" at {pointer}" if pointer else ""
            print(f"  FAIL  {r.artifact}  [{r.schema}]{loc}: {first_msg}")
    overall = "FAIL" if failed_results else "PASS"
    print(f"Result: {overall}")


def _build_report(
    run_id: str,
    run_dir: Path,
    results: list[ArtifactResult],
) -> dict[str, Any]:
    summary = _summarize(results)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "scanned_at": int(time.time()),
        "summary": summary,
        "results": [
            {
                "artifact": r.artifact,
                "schema": r.schema,
                "status": r.status,
                "violations": r.violations,
            }
            for r in results
        ],
    }


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def _write_blocked_manifest(manifest_path: Path, blocked_reason: str) -> None:
    """Merge-write status=blocked and blocked_reason into manifest.json.

    Reads the existing manifest (if any), updates only 'status' and
    'blocked_reason', and writes it back.  Never clobbers other keys.
    """
    data: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass  # Start with an empty dict; the merge-write still records the block.
    data["status"] = "blocked"
    data["blocked_reason"] = blocked_reason
    try:
        manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        print(
            f"WARNING: could not write blocked status to {manifest_path}: {exc}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Validate every agent-produced artifact in a devspec_pr_audit run directory."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--run-dir",
        required=True,
        metavar="PATH",
        help="Path to the audit run directory (e.g. docs/audit/runs/<run-id>/).",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Treat warnings as fatal (exit 1).",
    )
    ap.add_argument(
        "--write-report",
        metavar="PATH",
        default=None,
        help="Write a JSON summary report to the given path.",
    )
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        print(f"ERROR: --run-dir does not exist or is not a directory: {run_dir}", file=sys.stderr)
        return 2

    run_id = run_dir.name

    try:
        results = _discover_and_validate(run_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: unexpected error during validation: {exc}", file=sys.stderr)
        return 2

    _print_summary(run_id, results)

    if args.write_report:
        report = _build_report(run_id, run_dir, results)
        report_path = Path(args.write_report)
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: cannot write report to {report_path}: {exc}", file=sys.stderr)
            return 2

    failed = [r for r in results if r.status == "fail"]
    if failed:
        first = failed[0]
        blocked_reason = f"{first.schema} failed validation for {first.artifact}"
        _write_blocked_manifest(run_dir / "manifest.json", blocked_reason)
        return 1
    if args.strict:
        warned = [r for r in results if r.is_warning]
        if warned:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
