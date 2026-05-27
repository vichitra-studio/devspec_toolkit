#!/usr/bin/env python3
"""Self-validation helper for devspec_pr_audit agents.

Validates a JSON output file against a JSON Schema using
jsonschema.Draft202012Validator.  Intended to be invoked as the
final step in every schema-producing agent's procedure.

Usage:
    python3 scripts/self_validate.py \\
        --schema schema/infra/findings.schema.json \\
        --input  docs/audit/runs/<run-id>/p2/tier2_1_findings.json

    python3 scripts/self_validate.py \\
        --schema schema/infra/pr_audit_fix_plan.schema.json \\
        --input  docs/audit/runs/<run-id>/fix_plan.json \\
        --write-violations /tmp/violations.json

Exit codes:
    0 — document is valid; prints "OK" to stdout.
    1 — document is invalid; prints each error (JSON-pointer path + message)
        to stderr; exits 1.  If --write-violations is supplied, also writes a
        JSON report.
    2 — usage or I/O error (schema or input not readable, not valid JSON).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
except ImportError:  # pragma: no cover
    print(
        "ERROR: jsonschema is not installed. "
        "Activate the project venv before running this script.",
        file=sys.stderr,
    )
    sys.exit(2)


def _load_json(path: Path, label: str) -> Any:
    """Load and parse a JSON file; exit 2 on any error."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {label} at {path}: {exc}", file=sys.stderr)
        sys.exit(2)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"ERROR: {label} at {path} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(2)


def _format_path(error: jsonschema.ValidationError) -> str:
    """Return an RFC 6901 JSON pointer for the error location."""
    parts = list(error.absolute_path)
    if not parts:
        return "(document root)"
    segments: list[str] = []
    for part in parts:
        segments.append(f"/{part}")
    return "".join(segments)


def _is_findings_artifact(document: Any, schema_path: Path) -> bool:
    """Detect a vc:infra:findings artifact via schema path or shape."""
    if "findings.schema.json" in schema_path.name:
        return True
    if isinstance(document, dict) and isinstance(document.get("findings"), list):
        return True
    return False


def _check_upstream_refs(
    document: Any,
    schema_path: Path,
    skip: bool,
) -> list[tuple[str, str]]:
    """F6 rule: P0/P1 findings require non-empty upstream_refs[].

    Returns a list of (json_pointer, message) tuples for each violation.
    Returns an empty list if the rule is skipped, not applicable, or all
    P0/P1 findings carry at least one upstream_ref.
    """
    if skip:
        return []
    if not _is_findings_artifact(document, schema_path):
        return []
    if not isinstance(document, dict):
        return []
    findings = document.get("findings")
    if not isinstance(findings, list):
        return []

    violations: list[tuple[str, str]] = []
    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            continue
        severity = finding.get("severity")
        if severity not in ("P0", "P1"):
            continue
        refs = finding.get("upstream_refs")
        if not isinstance(refs, list) or len(refs) < 1:
            finding_id = finding.get("id", f"<index {idx}>")
            violations.append(
                (
                    f"/findings/{idx}/upstream_refs",
                    (
                        f"F6: {severity} finding {finding_id!r} must include "
                        "at least one upstream_refs[] entry "
                        "(pass --skip-upstream-refs-check to opt out for "
                        "observational review artifacts)."
                    ),
                )
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Validate a JSON output against a JSON Schema (Draft 2020-12).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--schema",
        required=True,
        metavar="PATH",
        help="Path to the JSON Schema file.",
    )
    ap.add_argument(
        "--input",
        required=True,
        metavar="PATH",
        help="Path to the JSON document to validate.",
    )
    ap.add_argument(
        "--write-violations",
        metavar="OUT_PATH",
        default=None,
        help=(
            "Optional path to write a JSON violations report "
            "{valid: bool, errors: [{path, message}]}."
        ),
    )
    ap.add_argument(
        "--skip-upstream-refs-check",
        action="store_true",
        default=False,
        help=(
            "Skip the F6 rule requiring non-empty upstream_refs[] on P0/P1 "
            "findings. Use for observational findings artifacts produced by "
            "review/audit-loop stages (e.g. iter_p*_review.json)."
        ),
    )
    args = ap.parse_args(argv)

    schema_path = Path(args.schema)
    input_path = Path(args.input)

    schema = _load_json(schema_path, "schema")
    document = _load_json(input_path, "input")

    # Check the schema itself is well-formed before using it.
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        print(
            f"ERROR: schema at {schema_path} is not a valid JSON Schema: {exc.message}",
            file=sys.stderr,
        )
        sys.exit(2)

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))

    if not errors:
        # Schema validation passed. Apply F6 cross-field rule: P0/P1 findings
        # in a vc:infra:findings artifact must carry at least one upstream_ref.
        f6_errors = _check_upstream_refs(
            document,
            schema_path,
            skip=args.skip_upstream_refs_check,
        )
        if f6_errors:
            for path_str, msg in f6_errors:
                print(f"  {path_str}: {msg}", file=sys.stderr)
            if args.write_violations:
                report_fail: dict[str, Any] = {
                    "valid": False,
                    "errors": [
                        {"path": p, "message": m} for p, m in f6_errors
                    ],
                }
                out = Path(args.write_violations)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(
                    json.dumps(report_fail, indent=2), encoding="utf-8"
                )
            return 1

        print("OK")
        if args.write_violations:
            report: dict[str, Any] = {"valid": True, "errors": []}
            out = Path(args.write_violations)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 0

    # Validation failed — report all errors.
    error_records: list[dict[str, str]] = []
    for error in errors:
        path_str = _format_path(error)
        msg = error.message
        print(f"  {path_str}: {msg}", file=sys.stderr)
        error_records.append({"path": path_str, "message": msg})

    if args.write_violations:
        report = {"valid": False, "errors": error_records}
        out = Path(args.write_violations)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return 1


if __name__ == "__main__":
    sys.exit(main())
