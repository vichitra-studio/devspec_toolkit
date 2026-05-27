#!/usr/bin/env python3
"""Tier-0 deterministic checks for devspec_pr_audit P0 phase.

Executes checks T0-04 through T0-11 against the diff/working-tree and writes
findings to <run-dir>/p0/tier0_findings.json conformant to vc:infra:findings.

Usage:
    python3 tier0_checks.py \\
        --run-dir docs/audit/runs/<run-id> \\
        --routing docs/audit/runs/<run-id>/p0/routing.json \\
        --head-sha <sha> \\
        --base-sha <sha> \\
        [--allow-tier0-failure=<check-name>]...

Exit code:
    0  — no P0-severity unoverridden findings
    1  — one or more P0 failures (halt condition for orchestrator)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator, SchemaError
except ImportError:
    print("Error: jsonschema library required. pip install jsonschema", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
# SCRIPT_DIR = .claude/skills/devspec_pr_audit/scripts
# parents[0] = .claude/skills/devspec_pr_audit
# parents[1] = .claude/skills
# parents[2] = .claude
# parents[3] = devspec_toolkit  (repo root)
REPO_ROOT = SCRIPT_DIR.parents[3]

FINDINGS_SCHEMA_PATH = REPO_ROOT / "schema" / "infra" / "findings.schema.json"

# Slices that are "user-visible semantic" for T0-09 purposes (per task spec:
# migration_versioning slice changed OR any schema change OR cli.py changed).
# We detect these directly from the changed file lists rather than by slice flag.

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _sig(check_id: str, location: str, message: str) -> str:
    """Deterministic 12-char hex signature for dedup."""
    raw = f"{check_id}|{location}|{message}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _finding(
    *,
    kind: str,
    location: str,
    message: str,
    severity: str,
    check_id: str,
    catalog_tag: str | None = None,
    evidence: list[str] | None = None,
    suggested_fix: str | None = None,
) -> dict[str, Any]:
    f: dict[str, Any] = {
        "kind": kind,
        "location": location,
        "signature": _sig(check_id, location, message),
        "message": message,
        "severity": severity,
    }
    if catalog_tag is not None:
        f["catalog_tag"] = catalog_tag
    if evidence:
        f["evidence"] = evidence
    if suggested_fix:
        f["suggested_fix"] = suggested_fix
    return f


def _load_findings_schema() -> dict[str, Any]:
    with FINDINGS_SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _validate_findings_doc(doc: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    return [f"[{' -> '.join(str(p) for p in e.absolute_path) or '(root)'}] {e.message}"
            for e in errors]


# ---------------------------------------------------------------------------
# Recursive additionalProperties walker (for T0-07)
# ---------------------------------------------------------------------------

def _walk_addl_props(
    schema_node: Any,
    path: str = "",
) -> dict[str, bool | None]:
    """Return a mapping of JSON-pointer-like path → additionalProperties value.

    `None` means the key was absent at that level (treated as 'not set').
    Only visits dict nodes that look like JSON Schema sub-schemas.
    """
    result: dict[str, bool | None] = {}
    if not isinstance(schema_node, dict):
        return result

    # Record this node's additionalProperties if the node is schema-like
    # (has 'type' or 'properties' or '$defs' or 'allOf'/etc.)
    schema_like_keys = {"type", "properties", "$defs", "allOf", "anyOf", "oneOf",
                        "then", "else", "patternProperties", "items", "additionalProperties"}
    if schema_like_keys & set(schema_node.keys()):
        val = schema_node.get("additionalProperties", None)
        if isinstance(val, bool) or val is None:
            result[path or "/"] = val

    # Recurse into child schema locations
    for key in ("properties", "patternProperties", "$defs"):
        if isinstance(schema_node.get(key), dict):
            for k, child in schema_node[key].items():
                child_path = f"{path}/{key}/{k}"
                result.update(_walk_addl_props(child, child_path))

    for key in ("allOf", "anyOf", "oneOf"):
        if isinstance(schema_node.get(key), list):
            for i, child in enumerate(schema_node[key]):
                result.update(_walk_addl_props(child, f"{path}/{key}/{i}"))

    for key in ("then", "else", "items"):
        child = schema_node.get(key)
        if isinstance(child, dict):
            result.update(_walk_addl_props(child, f"{path}/{key}"))

    return result


# ---------------------------------------------------------------------------
# Individual check implementations
# ---------------------------------------------------------------------------


def check_t04_schema_metaschema_valid(
    changed_files: list[str],
) -> list[dict[str, Any]]:
    """T0-04: Each changed *.schema.json validates against Draft 2020-12 metaschema."""
    findings: list[dict[str, Any]] = []
    schema_files = [f for f in changed_files if f.endswith(".schema.json")]
    for path in schema_files:
        p = REPO_ROOT / path
        if not p.exists():
            # Deleted file — skip
            continue
        try:
            with p.open(encoding="utf-8") as fh:
                schema = json.load(fh)
        except json.JSONDecodeError as exc:
            # T0-05 will catch this; skip here
            continue
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            msg = f"Metaschema validation error: {exc.message}"
            findings.append(_finding(
                kind="bug",
                location=path,
                message=msg,
                severity="P0",
                check_id="schema-metaschema-valid",
                catalog_tag="D5",
                evidence=[f"Metaschema validation error: {exc.message}"],
            ))
    return findings


def check_t05_json_parse_clean(
    changed_files: list[str],
) -> list[dict[str, Any]]:
    """T0-05: Every changed *.json parses cleanly.

    Skips files under tests/fixtures/ whose basename starts with 'invalid'
    or 'malformed' — those are intentionally-broken test fixtures.
    """
    findings: list[dict[str, Any]] = []
    json_files = [f for f in changed_files if f.endswith(".json")]
    for path in json_files:
        # Skip intentionally-malformed test fixtures.
        # Convention: files under tests/fixtures/ with "invalid" or "malformed"
        # anywhere in the stem are intentionally broken.
        parts = Path(path).parts
        if "fixtures" in parts:
            stem = Path(path).stem.lower()
            if "invalid" in stem or "malformed" in stem:
                continue
        p = REPO_ROOT / path
        if not p.exists():
            continue
        try:
            with p.open(encoding="utf-8") as fh:
                json.load(fh)
        except json.JSONDecodeError as exc:
            msg = f"JSON parse error: {exc}"
            findings.append(_finding(
                kind="bug",
                location=path,
                message=msg,
                severity="P0",
                check_id="json-parse-clean",
                catalog_tag="I3",
                evidence=[f"JSON parse error: {exc}"],
            ))
    return findings


def check_t06_schema_registry_targets_exist() -> list[dict[str, Any]]:
    """T0-06: Every target path in tools/schema_registry.json must exist."""
    findings: list[dict[str, Any]] = []
    registry_path = REPO_ROOT / "tools" / "schema_registry.json"
    if not registry_path.exists():
        findings.append(_finding(
            kind="gap",
            location="tools/schema_registry.json",
            message="tools/schema_registry.json not found on disk",
            severity="P0",
            check_id="schema-registry-targets-exist",
            catalog_tag="I4",
            evidence=["Registry file missing entirely"],
        ))
        return findings
    try:
        with registry_path.open(encoding="utf-8") as fh:
            registry: dict[str, Any] = json.load(fh)
    except json.JSONDecodeError as exc:
        findings.append(_finding(
            kind="bug",
            location="tools/schema_registry.json",
            message=f"schema_registry.json parse error: {exc}",
            severity="P0",
            check_id="schema-registry-targets-exist",
            catalog_tag="I4",
            evidence=[str(exc)],
        ))
        return findings

    for key, target_path in registry.items():
        if not isinstance(target_path, str):
            continue
        full = REPO_ROOT / target_path
        if not full.exists():
            findings.append(_finding(
                kind="gap",
                location=f"tools/schema_registry.json#/{key}",
                message=f"Registry entry '{key}' points to '{target_path}' which does not exist on disk",
                severity="P0",
                check_id="schema-registry-targets-exist",
                catalog_tag="I4",
                evidence=[f"Registry entry '{key}' points to '{target_path}' which does not exist on disk"],
            ))
    return findings


def check_t07_no_addl_props_regression(
    changed_files: list[str],
    base_sha: str,
) -> list[dict[str, Any]]:
    """T0-07: No additionalProperties: false → true regression in changed schemas."""
    findings: list[dict[str, Any]] = []
    schema_files = [f for f in changed_files if f.endswith(".schema.json")]
    for path in schema_files:
        head_path = REPO_ROOT / path
        if not head_path.exists():
            continue  # Deleted — no regression possible

        # Fetch base version via git show
        result = subprocess.run(
            ["git", "show", f"{base_sha}:{path}"],
            capture_output=True, text=True,
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            # File didn't exist at base (new file) — no regression to detect
            continue

        try:
            base_schema = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue  # Can't compare — skip
        try:
            with head_path.open(encoding="utf-8") as fh:
                head_schema = json.load(fh)
        except json.JSONDecodeError:
            continue  # T0-05 handles this

        base_map = _walk_addl_props(base_schema)
        head_map = _walk_addl_props(head_schema)

        for node_path, base_val in base_map.items():
            head_val = head_map.get(node_path)
            # Regression: base explicitly had false and head sets true.
            # Absent base (None) is not treated as a regression trigger.
            base_was_closed = (base_val is False)
            head_is_open = (head_val is True)
            if base_was_closed and head_is_open:
                before_str = "false"
                loc = f"{path}#/additionalProperties" if node_path == "/" else f"{path}#{node_path}/additionalProperties"
                msg = (f"additionalProperties regression: '{node_path}' changed from "
                       f"{before_str} to true")
                # MINR-1: Third evidence item should be a diff hunk (per protocol §4 T0-07
                # template: Before / After / <diff hunk>). Fetch a trimmed git diff.
                diff_result = subprocess.run(
                    ["git", "diff", f"{base_sha}..HEAD", "--", path],
                    capture_output=True, text=True,
                    cwd=REPO_ROOT,
                )
                diff_lines = diff_result.stdout.splitlines()
                if len(diff_lines) > 12:
                    diff_lines = diff_lines[:12] + ["..."]
                diff_hunk = "\n".join(diff_lines) if diff_lines else f"Schema node: {node_path}"
                findings.append(_finding(
                    kind="regression",
                    location=loc,
                    message=msg,
                    severity="P1",
                    check_id="no-addl-props-true-regression",
                    catalog_tag="D14",
                    evidence=[
                        f"Before: additionalProperties: {before_str}",
                        "After: additionalProperties: true",
                        diff_hunk,
                    ],
                ))
    return findings


def check_t08_unrouted_files(
    unrouted: list[str],
) -> list[dict[str, Any]]:
    """T0-08: Emit one P2 finding per unrouted file."""
    findings: list[dict[str, Any]] = []
    for path in unrouted:
        findings.append(_finding(
            kind="gap",
            location=path,
            message=f"Unrouted file '{path}': does not match any glob in slices.yaml",
            severity="P2",
            check_id="unrouted-files",
            catalog_tag="I2",
            evidence=["File does not match any glob in slices.yaml; excluded from audit scope"],
        ))
    return findings


def check_t09_changelog_entry_present(
    routing: dict[str, list[str]],
    changed_files: list[str],
) -> list[dict[str, Any]]:
    """T0-09: If migration_versioning, schemas, or cli.py changed, require unreleased entry."""
    # Determine if there are triggering changes
    migration_files = routing.get("migration_versioning", [])
    schema_files = [f for f in changed_files if f.endswith(".schema.json")]
    cli_files = [f for f in changed_files if f == "tools/specdev_tools/cli.py"]

    # Filter out changelog files themselves from migration trigger
    non_changelog_migration = [
        f for f in migration_files
        if not (f == "CHANGELOG.md" or f.startswith("changelog/"))
    ]

    if not (non_changelog_migration or schema_files or cli_files):
        return []  # No trigger

    # Check for unreleased entry in three locations
    has_entry = False

    # 1. changelog/unreleased.md
    unreleased_md = REPO_ROOT / "changelog" / "unreleased.md"
    if unreleased_md.exists():
        content = unreleased_md.read_text(encoding="utf-8").strip()
        # Non-empty beyond a bare header line?
        non_header = [ln for ln in content.splitlines() if ln.strip() and not ln.startswith("#")]
        if non_header:
            has_entry = True

    # 2. changelog/unreleased.yaml
    if not has_entry:
        unreleased_yaml = REPO_ROOT / "changelog" / "unreleased.yaml"
        if unreleased_yaml.exists():
            content = unreleased_yaml.read_text(encoding="utf-8").strip()
            non_comment = [ln for ln in content.splitlines()
                           if ln.strip() and not ln.startswith("#")]
            if non_comment:
                has_entry = True

    # 3. CHANGELOG.md — look for ## [Unreleased] section with content
    if not has_entry:
        changelog_md = REPO_ROOT / "CHANGELOG.md"
        if changelog_md.exists():
            text = changelog_md.read_text(encoding="utf-8")
            in_unreleased = False
            for line in text.splitlines():
                if line.strip().lower().startswith("## [unreleased]"):
                    in_unreleased = True
                    continue
                if in_unreleased:
                    if line.startswith("## "):
                        break  # Next version section
                    if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("<!--"):
                        has_entry = True
                        break

    if has_entry:
        return []

    # Build evidence
    trigger_files: list[str] = non_changelog_migration + schema_files + cli_files
    trigger_slices: list[str] = []
    if non_changelog_migration:
        trigger_slices.append("migration_versioning")
    if schema_files:
        trigger_slices.append("schemas")
    if cli_files:
        trigger_slices.append("cli_surface")

    return [_finding(
        kind="gap",
        location="CHANGELOG.md",
        message=(f"Slices {', '.join(trigger_slices)} have changed files but no unreleased changelog entry found. "
                 "Add an entry to changelog/unreleased.md, changelog/unreleased.yaml, "
                 "or CHANGELOG.md ## [Unreleased] section."),
        severity="P1",
        check_id="changelog-entry-present",
        catalog_tag="D11",
        evidence=[
            (
                f"Slice '{trigger_slices[0]}' has changed files but no unreleased changelog entry found"
                if len(trigger_slices) == 1
                else f"Slices {', '.join(trigger_slices)} have changed files but no unreleased changelog entry found"
            ),
            f"Changed files in triggering slices: {', '.join(trigger_files[:10])}{' ...' if len(trigger_files) > 10 else ''}",
        ],
    )]


def check_t10_generated_artifacts_clean() -> list[dict[str, Any]]:
    """T0-10: Re-run registry-generate to temp files; diff against committed files.

    The generator supports: --repo-root, --out (entry_key_registry),
    --extraction-paths-out. We generate to temp paths then diff.

    Falls back to a P2 informational finding if specdev is unavailable.
    """
    findings: list[dict[str, Any]] = []

    # Try to locate specdev on PATH (activate devspec_env if present)
    activate = REPO_ROOT / "devspec_env" / "bin" / "activate"
    env_setup = f"source {activate} && " if activate.exists() else ""

    check_cmd = f"{env_setup}command -v specdev"
    check_result = subprocess.run(
        ["bash", "-c", check_cmd],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    specdev_available = check_result.returncode == 0

    if not specdev_available:
        findings.append(_finding(
            kind="gap",
            location="tools/",
            message=(
                "T0-10 skipped: specdev not found on PATH. "
                "Activate the virtualenv and re-run to detect generator drift. "
                "Run `specdev registry-generate --repo-root .` to regenerate."
            ),
            severity="P2",
            check_id="generated-artifacts-clean",
            catalog_tag="D9",
            evidence=["specdev not available; T0-10 check skipped"],
            suggested_fix="source devspec_env/bin/activate && specdev registry-generate --repo-root .",
        ))
        return findings

    # The generator supports --out and --extraction-paths-out for redirect output.
    # Generate to temp files, then diff against committed files.
    # The two generator-owned artifacts are entry_key_registry.json and extraction_paths.json.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_ekr = Path(tmpdir) / "entry_key_registry.json"
        tmp_ep = Path(tmpdir) / "extraction_paths.json"

        gen_cmd = (
            f"{env_setup}specdev registry-generate --repo-root . "
            f"--out {tmp_ekr} --extraction-paths-out {tmp_ep}"
        )
        gen_result = subprocess.run(
            ["bash", "-c", gen_cmd],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        if gen_result.returncode != 0:
            findings.append(_finding(
                kind="bug",
                location="tools/",
                message=(
                    f"specdev registry-generate failed (exit {gen_result.returncode}): "
                    f"{gen_result.stderr[:200]}"
                ),
                severity="P0",
                check_id="generated-artifacts-clean",
                catalog_tag="D9",
                evidence=[
                    f"Generator exit code: {gen_result.returncode}",
                    f"stderr: {gen_result.stderr[:400]}",
                ],
            ))
            return findings

        tmp_paths = [tmp_ekr, tmp_ep]
        disk_rels = ["tools/entry_key_registry.json", "tools/extraction_paths.json"]
        for tmp_file, rel in zip(tmp_paths, disk_rels):
            disk_file = REPO_ROOT / rel
            if not tmp_file.exists():
                continue
            if not disk_file.exists():
                findings.append(_finding(
                    kind="gap",
                    location=rel,
                    message=f"Generator output '{rel}' not found on disk but would be generated",
                    severity="P0",
                    check_id="generated-artifacts-clean",
                    catalog_tag="D9",
                    evidence=[f"Expected at {rel} but file does not exist"],
                ))
                continue
            diff_result = subprocess.run(
                ["diff", "-u", str(disk_file), str(tmp_file)],
                capture_output=True, text=True,
            )
            if diff_result.returncode != 0:
                diff_excerpt = diff_result.stdout[:800]
                findings.append(_finding(
                    kind="drift",
                    location=rel,
                    message=(
                        f"Generator drift detected in '{rel}'. "
                        "Run `specdev registry-generate --repo-root .` to regenerate."
                    ),
                    severity="P0",
                    check_id="generated-artifacts-clean",
                    catalog_tag="D9",
                    evidence=[
                        "Generator drift detected. Run `specdev registry-generate --repo-root .` to regenerate.",
                        f"Diff excerpt: {diff_excerpt}",
                    ],
                ))

    return findings


def check_t11_new_module_has_test(
    base_sha: str,
) -> list[dict[str, Any]]:
    """T0-11: Every new tools/specdev_tools/**/*.py must have tests/**/test_<module>*.py."""
    findings: list[dict[str, Any]] = []

    # Find added Python files in tools/specdev_tools/
    diff_result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=A", f"{base_sha}...HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if diff_result.returncode != 0:
        # Non-fatal: can't determine added files
        return findings

    added_py = [
        f for f in diff_result.stdout.splitlines()
        if f.startswith("tools/specdev_tools/")
        and f.endswith(".py")
        and not f.endswith("__init__.py")
        and not f.endswith("py.typed")
    ]

    for path in added_py:
        module_name = Path(path).stem  # e.g. "foo_bar"
        # Look for any test file matching tests/**/test_<module>*.py
        tests_dir = REPO_ROOT / "tests"
        pattern = f"test_{module_name}*.py"
        matches = list(tests_dir.rglob(pattern))
        if not matches:
            findings.append(_finding(
                kind="coverage",
                location=path,
                message=(f"New module '{path}' introduced in this PR has no matching test file. "
                         f"Expected pattern: tests/**/test_{module_name}*.py"),
                severity="P1",
                check_id="new-module-has-test",
                catalog_tag="I8",
                evidence=[
                    f"New module introduced in this PR; no matching test file found under tests/",
                    f"Expected pattern: tests/**/test_{module_name}*.py",
                ],
            ))
    return findings


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def load_routing(routing_path: Path) -> dict[str, Any]:
    with routing_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def update_manifest_overrides(
    manifest_path: Path,
    check_name: str,
) -> None:
    """Append override entry to manifest.json tier0_overrides[] using atomic pattern."""
    try:
        with manifest_path.open(encoding="utf-8") as fh:
            manifest: dict[str, Any] = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"WARNING: could not record tier0 override in manifest: {exc}", file=sys.stderr)
        return
    overrides = manifest.get("tier0_overrides", [])
    if check_name not in overrides:
        overrides.append(check_name)
    manifest["tier0_overrides"] = overrides
    manifest["updated_at"] = int(time.time())
    tmp = manifest_path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    tmp.replace(manifest_path)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run Tier-0 deterministic checks (T0-04 through T0-11)"
    )
    ap.add_argument("--run-dir", required=True, help="Path to run directory (docs/audit/runs/<run-id>)")
    ap.add_argument("--routing", required=True, help="Path to routing.json")
    ap.add_argument("--head-sha", required=True, help="HEAD commit SHA")
    ap.add_argument("--base-sha", required=True, help="Base commit SHA (merge-base)")
    ap.add_argument(
        "--allow-tier0-failure",
        action="append",
        default=[],
        dest="allow_failures",
        metavar="CHECK_NAME",
        help="Override a P0 failure by check name; may repeat",
    )
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    p0_dir = run_dir / "p0"
    p0_dir.mkdir(parents=True, exist_ok=True)

    routing_path = Path(args.routing)
    routing_data = load_routing(routing_path)

    routing: dict[str, list[str]] = routing_data.get("routing", {})
    unrouted: list[str] = routing_data.get("unrouted", [])

    # All changed files (union of all routed + unrouted)
    all_changed: set[str] = set()
    for files in routing.values():
        all_changed.update(files)
    all_changed.update(unrouted)
    changed_files = sorted(all_changed)

    manifest_path = run_dir / "manifest.json"
    allow_failures: set[str] = set(args.allow_failures)

    findings_schema = _load_findings_schema()

    # Collect all findings, indexed by check_id for override handling
    all_findings: list[dict[str, Any]] = []
    p0_halt = False

    def run_check(check_id: str, check_findings: list[dict[str, Any]]) -> None:
        nonlocal p0_halt
        if not check_findings:
            return
        # Determine max severity for this check
        has_p0 = any(f["severity"] == "P0" for f in check_findings)
        if has_p0 and check_id in allow_failures:
            print(f"  [OVERRIDE] {check_id}: {len(check_findings)} finding(s) suppressed by --allow-tier0-failure")
            update_manifest_overrides(manifest_path, check_id)
            return
        all_findings.extend(check_findings)
        if has_p0 and check_id not in allow_failures:
            p0_halt = True

    print("tier0: running T0-04 schema-metaschema-valid...")
    run_check("schema-metaschema-valid", check_t04_schema_metaschema_valid(changed_files))

    print("tier0: running T0-05 json-parse-clean...")
    run_check("json-parse-clean", check_t05_json_parse_clean(changed_files))

    print("tier0: running T0-06 schema-registry-targets-exist...")
    run_check("schema-registry-targets-exist", check_t06_schema_registry_targets_exist())

    print("tier0: running T0-07 no-addl-props-true-regression...")
    run_check("no-addl-props-true-regression", check_t07_no_addl_props_regression(changed_files, args.base_sha))

    print("tier0: running T0-08 unrouted-files...")
    run_check("unrouted-files", check_t08_unrouted_files(unrouted))

    print("tier0: running T0-09 changelog-entry-present...")
    run_check("changelog-entry-present", check_t09_changelog_entry_present(routing, changed_files))

    print("tier0: running T0-10 generated-artifacts-clean...")
    run_check("generated-artifacts-clean", check_t10_generated_artifacts_clean())

    print("tier0: running T0-11 new-module-has-test...")
    run_check("new-module-has-test", check_t11_new_module_has_test(args.base_sha))

    # --- Build output document ---
    doc: dict[str, Any] = {
        "round": 1,
        "scope": "tier0",
        "generated_at": int(time.time()),
        "findings": all_findings,
    }

    # Validate against schema before writing
    validation_errors = _validate_findings_doc(doc, findings_schema)
    if validation_errors:
        print("ERROR: output document fails vc:infra:findings validation:", file=sys.stderr)
        for err in validation_errors:
            print(f"  {err}", file=sys.stderr)
        return 2

    # Write (or merge into existing) tier0_findings.json
    output_path = p0_dir / "tier0_findings.json"
    if output_path.exists():
        # Merge is a no-op in normal orchestrated flow (Step 0e deletes the file first). Defensive: preserves content if invoked directly outside the orchestrator.
        try:
            with output_path.open(encoding="utf-8") as fh:
                existing: dict[str, Any] = json.load(fh)
            existing_findings: list[dict[str, Any]] = existing.get("findings", [])
            seen_keys: set[tuple[str, str, str]] = {
                (f["kind"], f["location"], f["signature"]) for f in existing_findings
            }
            new_findings = [
                f for f in all_findings
                if (f["kind"], f["location"], f["signature"]) not in seen_keys
            ]
            merged = existing_findings + new_findings
            doc["findings"] = merged
        except (json.JSONDecodeError, KeyError):
            pass  # Overwrite corrupted file

    # Re-validate after merge (merged document may differ from pre-merge doc)
    post_merge_errors = _validate_findings_doc(doc, findings_schema)
    if post_merge_errors:
        print("ERROR: merged document fails vc:infra:findings validation:", file=sys.stderr)
        for err in post_merge_errors:
            print(f"  {err}", file=sys.stderr)
        return 2

    tmp_path = output_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    tmp_path.replace(output_path)

    # Counts
    p0_count = sum(1 for f in doc["findings"] if f.get("severity") == "P0")
    p1_count = sum(1 for f in doc["findings"] if f.get("severity") == "P1")
    p2_count = sum(1 for f in doc["findings"] if f.get("severity") == "P2")
    total = len(doc["findings"])
    gate = "halt" if p0_halt else "pass"

    print(f"tier0: {total} findings (P0={p0_count} P1={p1_count} P2={p2_count}) — gate: {gate}")

    return 1 if p0_halt else 0


if __name__ == "__main__":
    sys.exit(main())
