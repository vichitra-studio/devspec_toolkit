#!/usr/bin/env python3
"""Removal audit for devspec_pr_audit P0 phase.

Detects deleted files in the PR diff and emits catalog-tagged findings.
Appends findings to the existing p0/tier0_findings.json (creates if absent).

Design choice: appends to tier0_findings.json (not a separate file) so that
the P4 consolidator's single input path `p0/tier0_findings.json` picks up
all P0 findings without requiring an extra input glob. The caller (Step 0e.5)
must run this AFTER tier0_checks.py so the output file already exists; this
script also handles the case where tier0_findings.json does not yet exist and
creates it from scratch.

Usage:
    python3 removal_audit.py \\
        --run-dir docs/audit/runs/<run-id> \\
        --head-sha <sha> \\
        --base-sha <sha>

Exit code:
    0  — no P0-severity findings from deletions
    1  — one or more P0 deletion findings (e.g. canon/ or generated-artifact removed)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("Error: jsonschema library required. pip install jsonschema", file=sys.stderr)
    sys.exit(1)

# Import manifest helper from sibling script (has if __name__ == "__main__" guard)
try:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("tier0_checks", Path(__file__).resolve().parent / "tier0_checks.py")
    assert _spec and _spec.loader
    _t0 = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_t0)  # type: ignore[union-attr]
    update_manifest_overrides = _t0.update_manifest_overrides
except Exception:
    # Fallback: inline copy of the helper
    def update_manifest_overrides(manifest_path: "Path", check_name: str) -> None:  # type: ignore[misc]
        """Append override entry to manifest.json tier0_overrides[] using atomic pattern."""
        try:
            with manifest_path.open(encoding="utf-8") as fh:
                manifest: dict = json.load(fh)
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

SCRIPT_DIR = Path(__file__).resolve().parent
# SCRIPT_DIR = .claude/skills/devspec_pr_audit/scripts
# parents[0] = .claude/skills/devspec_pr_audit
# parents[1] = .claude/skills
# parents[2] = .claude
# parents[3] = devspec_toolkit  (repo root)
REPO_ROOT = SCRIPT_DIR.parents[3]

FINDINGS_SCHEMA_PATH = REPO_ROOT / "schema" / "infra" / "findings.schema.json"

# High-value, deterministic toolkit files whose deletion is held to a P0 (D9) bar.
# NOTE: despite the historical variable name, NOT all of these are generator
# outputs — only entry_key_registry.json and extraction_paths.json are produced by
# `registry-generate`. schema_registry.json, step_order.json, command_prefixes.json,
# and step_docs.json are manually maintained but equally load-bearing, so their
# deletion is treated with the same severity. (This set is NOT synced to
# slices.yaml's generated_artifacts slice, which now lists only the two true
# generator outputs.)
GENERATED_ARTIFACT_NAMES: set[str] = {
    "schema_registry.json",
    "step_order.json",
    "entry_key_registry.json",
    "extraction_paths.json",
    "command_prefixes.json",
    "step_docs.json",
}

# ---------------------------------------------------------------------------
# Utility helpers (mirrored from tier0_checks.py to keep scripts standalone)
# ---------------------------------------------------------------------------


def _sig(check_id: str, location: str, message: str) -> str:
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


def _infer_catalog_tag(path: str) -> tuple[str, str]:
    """Return (catalog_tag, severity) for a deleted file path.

    A file removal is an *upstream change that downstream dependents must
    reflect* — catalogs.md D7 (Upstream ↔ downstream), whose generic pattern
    explicitly covers a "removed value" not propagated to dependents. So every
    removal is tagged D7, EXCEPT a load-bearing deterministic toolkit artifact
    (the GENERATED_ARTIFACT_NAMES set), whose absence is treated as a D9
    generator-integrity defect. For the true generator outputs
    (entry_key_registry.json, extraction_paths.json) that is literal — the
    generator would re-emit them, so a committed deletion is provably wrong. For
    the manually-maintained members of the set the D9/P0 tag is a deliberate
    high-severity choice (their loss silently breaks routing, ai-help, or
    schema/step resolution), not a claim that a generator owns them. The catalog
    has no dedicated "file removed" code; D7 is the correct generic fit. (Earlier
    revisions mis-tagged removals as D14/D3/D2 — tags whose semantics, per
    catalogs.md, are schema-authority delegation, code↔docs, and producer↔consumer
    shape respectively, none of which describe a deletion.)

    Severity reflects the criticality of the removed artifact, independent of tag.

    Rules (first match wins):
      canon/**                               → D7, P0  (registry everything references)
      tools/{schema_registry,step_order,
             entry_key_registry,extraction_paths,
             command_prefixes,step_docs}.json → D9, P0  (load-bearing toolkit
                                                          data; see note above —
                                                          only 2 are generator outputs)
      *.schema.json                          → D7, P1
      prompts/**/*.md                        → D7, P1
      tools/specdev_tools/**/*.py            → D7, P1
      others                                 → D7, P2  (fallback)
    """
    if path.startswith("canon/"):
        return ("D7", "P0")
    if path.startswith("tools/") and path.endswith(".json"):
        name = Path(path).name
        if name in GENERATED_ARTIFACT_NAMES:
            return ("D9", "P0")
    if path.endswith(".schema.json"):
        return ("D7", "P1")
    if (path.startswith("prompts/") or path.startswith("migration_prompts/")) and path.endswith(".md"):
        return ("D7", "P1")
    if path.startswith("tools/specdev_tools/") and path.endswith(".py"):
        return ("D7", "P1")
    return ("D7", "P2")


def load_deleted_files(base_sha: str, head_sha: str) -> list[str]:
    """Return list of files deleted between base_sha and HEAD."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=D", f"{base_sha}...{head_sha}"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        print(f"WARNING: git diff failed (exit {result.returncode}): {result.stderr.strip()[:200]}",
              file=sys.stderr)
        return []
    return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]


def build_findings(deleted_files: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in deleted_files:
        catalog_tag, severity = _infer_catalog_tag(path)
        kind = "drift"
        msg = f"File '{path}' was deleted in this PR. Verify intentional removal."
        findings.append(_finding(
            kind=kind,
            location=path,
            message=msg,
            severity=severity,
            check_id="removal-audit",
            catalog_tag=catalog_tag,
            evidence=[f"File deleted: {path}", f"Catalog classification: {catalog_tag}"],
        ))
    return findings


def load_findings_schema() -> dict[str, Any]:
    with FINDINGS_SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def validate_doc(doc: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    return [f"[{' -> '.join(str(p) for p in e.absolute_path) or '(root)'}] {e.message}"
            for e in errors]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Removal audit: detect deleted files and emit P0/P1/P2 findings"
    )
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--head-sha", required=True)
    ap.add_argument("--base-sha", required=True)
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
    allow_failures: set[str] = set(args.allow_failures)
    manifest_path = run_dir / "manifest.json"
    p0_dir = run_dir / "p0"
    p0_dir.mkdir(parents=True, exist_ok=True)
    output_path = p0_dir / "tier0_findings.json"

    findings_schema = load_findings_schema()

    deleted = load_deleted_files(args.base_sha, args.head_sha)
    print(f"removal-audit: {len(deleted)} deleted file(s) in diff")

    new_findings = build_findings(deleted)

    # Load existing tier0_findings.json (may have been written by tier0_checks.py)
    existing_findings: list[dict[str, Any]] = []
    existing_doc: dict[str, Any] = {
        "round": 1,
        "scope": "tier0",
        "generated_at": int(time.time()),
        "findings": [],
    }
    if output_path.exists():
        try:
            with output_path.open(encoding="utf-8") as fh:
                existing_doc = json.load(fh)
            existing_findings = existing_doc.get("findings", [])
        except (json.JSONDecodeError, KeyError):
            pass  # Start fresh

    # Dedup by (kind, location, signature)
    seen_keys: set[tuple[str, str, str]] = {
        (f["kind"], f["location"], f["signature"]) for f in existing_findings
    }
    deduped_new = [
        f for f in new_findings
        if (f["kind"], f["location"], f["signature"]) not in seen_keys
    ]

    # Filter P0 removal-audit findings BEFORE merging with existing
    # so tier0_checks.py P0s (e.g. T0-06, T0-10) are never dropped.
    if "removal-audit" in allow_failures:
        deduped_new = [f for f in deduped_new if f.get("severity") != "P0"]

    merged = existing_findings + deduped_new

    existing_doc["findings"] = merged
    existing_doc["generated_at"] = int(time.time())

    # Validate before writing
    errs = validate_doc(existing_doc, findings_schema)
    if errs:
        print("ERROR: merged document fails vc:infra:findings validation:", file=sys.stderr)
        for e in errs:
            print(f"  {e}", file=sys.stderr)
        return 2

    tmp = output_path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(existing_doc, fh, indent=2)
    tmp.replace(output_path)

    p0_count = sum(1 for f in deduped_new if f.get("severity") == "P0")
    p1_count = sum(1 for f in deduped_new if f.get("severity") == "P1")
    p2_count = sum(1 for f in deduped_new if f.get("severity") == "P2")

    # IMPT-2: Always record override in manifest when flag is present, regardless
    # of p0_count (idempotent re-runs where deduped_new is empty must still log).
    if "removal-audit" in allow_failures:
        print(f"  [OVERRIDE] removal-audit: {p0_count} P0 finding(s) suppressed by --allow-tier0-failure")
        update_manifest_overrides(manifest_path, "removal-audit")
        gate = "pass (overridden)"
        print(f"removal-audit: {len(deduped_new)} new findings "
              f"(P0={p0_count} P1={p1_count} P2={p2_count}) — gate: {gate}")
        return 0

    gate = "halt" if p0_count > 0 else "pass"
    print(f"removal-audit: {len(deduped_new)} new findings "
          f"(P0={p0_count} P1={p1_count} P2={p2_count}) — gate: {gate}")

    return 1 if p0_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
