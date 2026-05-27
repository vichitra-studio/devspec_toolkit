#!/usr/bin/env python3
"""Validate all digest JSON files in a directory against their matching schemas.

Usage:
    validate_digests.py <digests_dir>

Exit codes:
    0 — all digests valid
    1 — one or more digests invalid (all failures printed before exit)

Output:
    Human-readable lines for each invalid file, followed by a machine-readable
    JSON summary on the final line:
        {"total": N, "valid": M, "invalid": K, "failures": [{"path": ..., "errors": [...]}]}

Dependencies: jsonschema (Draft 2020-12), standard library only.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("Error: jsonschema library is required. Install with: pip install jsonschema", file=sys.stderr)
    sys.exit(1)


# Digest type → schema filename mapping
DIGEST_TYPE_TO_SCHEMA: dict[str, str] = {
    "digest_schema":    "digest_schema.schema.json",
    "digest_prompt":    "digest_prompt.schema.json",
    "digest_validator": "digest_validator.schema.json",
    "digest_cli":       "digest_cli.schema.json",
    "digest_canon":     "digest_canon.schema.json",
    "digest_changelog": "digest_changelog.schema.json",
    "digest_test":      "digest_test.schema.json",
    "digest_doc":       "digest_doc.schema.json",
    "digest_migration": "digest_migration.schema.json",
}


def load_schemas(schemas_dir: pathlib.Path) -> dict[str, Any]:
    """Load all digest schemas from the schemas directory.

    Returns a mapping of digest_type → parsed schema dict.
    Raises FileNotFoundError if any schema file is missing.
    """
    schemas: dict[str, Any] = {}
    for digest_type, schema_filename in DIGEST_TYPE_TO_SCHEMA.items():
        schema_path = schemas_dir / schema_filename
        if not schema_path.exists():
            raise FileNotFoundError(
                f"Schema file not found: {schema_path}. "
                f"Expected at {schemas_dir}/{schema_filename}"
            )
        with schema_path.open(encoding="utf-8") as f:
            schemas[digest_type] = json.load(f)
    return schemas


def validate_digest(
    digest_path: pathlib.Path,
    schemas: dict[str, Any],
) -> list[str]:
    """Validate a single digest file against its schema.

    Returns a list of error message strings. Empty list = valid.
    """
    # Parse the JSON
    try:
        with digest_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return [f"JSON parse error: {exc}"]

    # Determine digest type
    digest_type = data.get("digest_type")
    if not digest_type:
        return ["Missing required field: digest_type"]

    schema = schemas.get(digest_type)
    if schema is None:
        return [
            f"Unknown digest_type: {digest_type!r}. "
            f"Known types: {', '.join(sorted(DIGEST_TYPE_TO_SCHEMA))}"
        ]

    # Run Draft 2020-12 validation
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(data),
        key=lambda e: list(e.absolute_path),
    )

    if not errors:
        return []

    messages = []
    for err in errors:
        # Build a readable path string
        path = " -> ".join(str(p) for p in err.absolute_path) if err.absolute_path else "(root)"
        messages.append(f"  [{path}] {err.message}")

    return messages


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_digests.py <digests_dir>", file=sys.stderr)
        return 1

    digests_dir = pathlib.Path(sys.argv[1])
    if not digests_dir.is_dir():
        print(f"Error: not a directory: {digests_dir}", file=sys.stderr)
        return 1

    # Schemas live in ../schemas/ relative to this script
    script_dir = pathlib.Path(__file__).parent
    schemas_dir = script_dir.parent / "schemas"

    try:
        schemas = load_schemas(schemas_dir)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Walk the digests directory recursively for *.json files
    digest_files = sorted(digests_dir.rglob("*.json"))

    if not digest_files:
        print(f"No *.json files found under {digests_dir}")
        summary = {"total": 0, "valid": 0, "invalid": 0, "failures": []}
        print(json.dumps(summary))
        return 0

    total = len(digest_files)
    failures: list[dict[str, Any]] = []

    for digest_path in digest_files:
        errors = validate_digest(digest_path, schemas)
        if errors:
            rel = digest_path.relative_to(digests_dir)
            print(f"INVALID: {rel}")
            for msg in errors:
                print(msg)
            failures.append({"path": str(rel), "errors": errors})
        else:
            rel = digest_path.relative_to(digests_dir)
            print(f"OK:      {rel}")

    valid = total - len(failures)
    invalid = len(failures)

    print()  # blank line before summary
    if invalid > 0:
        print(f"RESULT: {invalid}/{total} digest(s) INVALID")
    else:
        print(f"RESULT: all {total} digest(s) valid")

    summary = {
        "total": total,
        "valid": valid,
        "invalid": invalid,
        "failures": failures,
    }
    print(json.dumps(summary))

    return 1 if invalid > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
