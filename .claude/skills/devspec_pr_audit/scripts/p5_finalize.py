#!/usr/bin/env python3
"""p5_finalize — Phase 5 finalization script for devspec_pr_audit.

Reads findings.json and manifest.json (required) and fix_plan.json
(optional — required only when findings are non-empty) from a completed
audit run directory and produces a human-readable SUMMARY.md.

Usage:
    python3 p5_finalize.py --run-dir docs/audit/runs/<run-id> [--output PATH]

Exit codes:
    0 — SUMMARY.md written successfully.
    1 — Missing input files or schema-validation failure.
    2 — Unexpected I/O or JSON-parsing error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
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
        print(f"ERROR: {label} at {path} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(2)


def _format_error_path(error: Any) -> str:
    """Return an RFC 6901 JSON pointer for a jsonschema ValidationError."""
    parts = list(error.absolute_path)
    if not parts:
        return "(document root)"
    return "".join(f"/{part}" for part in parts)


def _validate_document(
    document: Any,
    schema: dict[str, Any],
    schema_path: Path,
    label: str,
) -> None:
    """Validate *document* against *schema*; exit 1 listing all violations."""
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
    if errors:
        print(f"ERROR: {label} failed schema validation:", file=sys.stderr)
        for error in errors:
            print(f"  {_format_error_path(error)}: {error.message}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Slice routing
# ---------------------------------------------------------------------------

# Files whose primary path belongs to the pipeline_topology display slice.
_PIPELINE_TOPOLOGY_FILES: frozenset[str] = frozenset(
    [
        "tools/schema_registry.json",
        "tools/step_order.json",
        "tools/extraction_paths.json",
        "tools/entry_key_registry.json",
        "tools/command_prefixes.json",
        "tools/step_docs.json",
        "tools/specdev_tools/validation/dag_lint.py",
        "tools/specdev_tools/validation/extraction_intent_check.py",
        "tools/specdev_tools/validation/_extraction_intent_parser.py",
    ]
)


def _primary_path(location: str) -> str:
    """Extract the first/primary file path from a (possibly cross-file) location."""
    # Strip cross-reference markers and fragment identifiers.
    primary = location.replace(" and ", " vs ").split(" vs ")[0].strip()
    if "#" in primary:
        primary = primary.split("#")[0].strip()
    return primary


def _classify_slice(location: str) -> str:
    """Route a finding location to a display-slice name.

    Display slices used:
      - pipeline_topology  (schema_registry, step_order, extraction_paths, dag_lint, …)
      - prompts            (prompts/*.md only — NOT docs/prompts/)
      - migration_versioning (changelog/*, CHANGELOG.md)
      - tests_fixtures     (tests/)
      - docs               (docs/, README.md, CLAUDE.md)
      - validators/cli     (tools/, but NOT the pipeline_topology files above)
      - other              (digests/, unrecognised prefixes)
    """
    primary = _primary_path(location).lower()

    if primary in {p.lower() for p in _PIPELINE_TOPOLOGY_FILES}:
        return "pipeline_topology"

    if primary.startswith("prompts/"):
        return "prompts"

    if primary.startswith("changelog/") or primary == "changelog.md":
        return "migration_versioning"

    if primary.startswith("tests/"):
        return "tests_fixtures"

    if primary.startswith("docs/") or primary in ("readme.md", "claude.md"):
        return "docs"

    if primary.startswith("tools/"):
        return "validators/cli"

    return "other"


# ---------------------------------------------------------------------------
# Catalog-tag sorting
# ---------------------------------------------------------------------------

# D1..D14 then I1..I13, in numeric order within each prefix.
def _catalog_tag_sort_key(tag: str) -> tuple[int, int]:
    prefix_order = {"D": 0, "I": 1}
    prefix = tag[0].upper()
    num = int(tag[1:])
    return (prefix_order.get(prefix, 2), num)


# ---------------------------------------------------------------------------
# Markdown table helpers
# ---------------------------------------------------------------------------

def _cell(value: str) -> str:
    """Format a table cell: non-empty values get surrounding spaces; empty values have one space."""
    return f" {value} " if value else " "


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a Markdown table. All values are strings.

    Separator width = max(4, len(header) + 2) (two-pad) to match the reference SUMMARY.md style.
    Separator row uses compact ``|---|`` notation (no surrounding spaces).
    Empty cell values render as bare ``||`` (no interior spaces).
    """
    sep = ["-" * max(4, len(h) + 2) for h in headers]
    lines: list[str] = [
        "|" + "|".join(_cell(h) for h in headers) + "|",
        "|" + "|".join(sep) + "|",
    ]
    for row in rows:
        lines.append("|" + "|".join(_cell(v) for v in row) + "|")
    return "\n".join(lines)


def _two_col_catalog_table(tag_counts: Counter[str]) -> str:
    """Render the two-column D-tags / I-tags catalog table.

    Left column: D1..D14 (present only), right column: I1..I13 (present only).
    Shorter column is padded with empty cells.
    """
    d_tags = sorted(
        [t for t in tag_counts if t.startswith("D")], key=_catalog_tag_sort_key
    )
    i_tags = sorted(
        [t for t in tag_counts if t.startswith("I")], key=_catalog_tag_sort_key
    )

    max_rows = max(len(d_tags), len(i_tags), 1)
    rows: list[list[str]] = []
    for idx in range(max_rows):
        d_tag = d_tags[idx] if idx < len(d_tags) else ""
        d_count = str(tag_counts[d_tag]) if idx < len(d_tags) else ""
        i_tag = i_tags[idx] if idx < len(i_tags) else ""
        i_count = str(tag_counts[i_tag]) if idx < len(i_tags) else ""
        rows.append([d_tag, d_count, i_tag, i_count])

    return _md_table(["Tag", "Count", "Tag", "Count"], rows)


# ---------------------------------------------------------------------------
# Phase display name
# ---------------------------------------------------------------------------

_PHASE_DISPLAY_NAMES: dict[int, str] = {
    0: "P0 deterministic",
    1: "P1 context (L1)",
    2: "P2 discovery",
    3: "P3 cross-boundary",
    4: "P4 consolidation (L2)",
    5: "P5 finalize",
}


def _phase_label(phase: int) -> str:
    return _PHASE_DISPLAY_NAMES.get(phase, f"P{phase}")


# Phases that run an iterative review loop (others are single-pass).
_LOOP_PHASES: frozenset[int] = frozenset({1, 4})


def _phase_done_marker(run_dir: Path, phase: int) -> Path:
    return run_dir / f".phase_{phase}.done"


def _iter_review_files(run_dir: Path, phase: int) -> list[Path]:
    """Return iter_p{phase}_*_review.json files in *run_dir*, sorted by name."""
    pattern = re.compile(rf"^iter_p{phase}_(\d+)_review\.json$")
    matches: list[tuple[int, Path]] = []
    if not run_dir.is_dir():
        return []
    for entry in run_dir.iterdir():
        if not entry.is_file():
            continue
        m = pattern.match(entry.name)
        if m:
            matches.append((int(m.group(1)), entry))
    matches.sort(key=lambda pair: pair[0])
    return [p for _, p in matches]


def _derive_loop_iterations(run_dir: Path, phase: int) -> str:
    """Best-effort iteration count for *phase* derived from filesystem state."""
    if phase not in _LOOP_PHASES:
        return "—"
    return str(len(_iter_review_files(run_dir, phase)))


def _derive_outcome(run_dir: Path, phase: int) -> str:
    """Best-effort outcome string for *phase* derived from filesystem state."""
    marker = _phase_done_marker(run_dir, phase)
    if not marker.exists():
        return "—"

    # Phase 4 records degraded=true in its marker payload when consolidation degraded.
    if phase == 4:
        try:
            payload_text = marker.read_text(encoding="utf-8").strip()
        except OSError:
            payload_text = ""
        if payload_text:
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict) and payload.get("degraded") is True:
                return "DEGRADED"

    if phase in _LOOP_PHASES:
        iter_files = _iter_review_files(run_dir, phase)
        if iter_files:
            last = iter_files[-1]
            try:
                last_doc = json.loads(last.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                last_doc = None
            if isinstance(last_doc, dict) and last_doc.get("findings") == []:
                return f"Converged at iter {len(iter_files)}"
        return "completed"

    return "completed"


# ---------------------------------------------------------------------------
# Artifacts section
# ---------------------------------------------------------------------------

def _artifacts_section(run_dir: Path, n_findings: int, n_tasks: int) -> str:
    """Build the Artifacts section, listing files and subdirs present."""
    lines: list[str] = ["## Artifacts", ""]

    # Core outputs
    findings_path = run_dir / "findings.json"
    fix_plan_path = run_dir / "fix_plan.json"
    manifest_path = run_dir / "manifest.json"

    if findings_path.exists():
        size_kb = findings_path.stat().st_size // 1000
        lines.append(
            f"- Part A: `findings.json` ({size_kb} KB, {n_findings} findings, schema-valid)"
        )
    if fix_plan_path.exists():
        size_kb = fix_plan_path.stat().st_size // 1000
        lines.append(
            f"- Part B: `fix_plan.json` ({size_kb} KB, {n_tasks} tasks, schema-valid)"
        )

    # Per-phase intermediate subdirectories — phase dirs (p\d+) sorted by phase number
    # first, then remaining dirs alphabetically.
    def _subdir_sort_key(name: str) -> tuple[int, int, str]:
        m = re.match(r"^p(\d+)$", name)
        if m:
            return (0, int(m.group(1)), name)
        return (1, 0, name)

    phase_subdirs = sorted(
        (d.name for d in run_dir.iterdir() if d.is_dir() and not d.name.startswith(".")),
        key=_subdir_sort_key,
    )
    if phase_subdirs:
        subdir_str = ", ".join(f"`{d}/`" for d in phase_subdirs)
        lines.append(f"- Per-phase intermediates: {subdir_str}")

    # Loop iter artifacts (iter_*.json files)
    iter_files = sorted(
        f.name for f in run_dir.iterdir() if f.is_file() and f.name.startswith("iter_")
    )
    if iter_files:
        lines.append("- Loop audit trail: " + ", ".join(f"`{n}`" for n in iter_files))

    # Run metadata
    if manifest_path.exists():
        lines.append("- Run metadata: `manifest.json`")

    # Phase markers
    markers = sorted(
        f.name for f in run_dir.iterdir() if f.is_file() and f.name.startswith(".phase_")
    )
    if markers:
        first = markers[0].replace(".done", "")
        last = markers[-1].replace(".done", "")
        lines.append(f"- Phase markers: `{first}.done` through `{last}.done`")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_summary(
    run_dir: Path,
    findings_doc: dict[str, Any],
    fix_plan_doc: dict[str, Any],
    manifest: dict[str, Any],
) -> str:
    """Construct the full SUMMARY.md content from the three input documents."""
    parts: list[str] = []

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    run_id: str = manifest.get("run_id", "unknown")
    branch: str = manifest.get("branch", "unknown")
    base_sha_full: str = manifest.get("base_sha", "unknown")
    # Display only first 12 chars of base SHA (matching reference convention).
    base_sha_display = base_sha_full[:12] if len(base_sha_full) >= 12 else base_sha_full
    scope_note: str = manifest.get("scope_note", "")

    head_sha: str = manifest.get("head_sha", "unknown")
    status: str = manifest.get("status", "UNKNOWN")
    phases_completed: list[int] = sorted(manifest.get("phases_completed", []))

    parts.append("# devspec_pr_audit — Run Summary\n")
    parts.append(f"**Run ID:** `{run_id}`")
    parts.append(f"**Branch:** `{branch}`")
    if scope_note:
        parts.append(f"**Base:** `{base_sha_display}` ({scope_note})")
    else:
        parts.append(f"**Base:** `{base_sha_display}`")
    parts.append(f"**Head:** `{head_sha}`")
    parts.append(f"**Status:** {status}")
    parts.append(f"**Phases completed:** {phases_completed!r}")
    parts.append("")

    # ------------------------------------------------------------------
    # Part A — Findings
    # ------------------------------------------------------------------
    findings: list[dict[str, Any]] = findings_doc.get("findings", [])
    n_findings = len(findings)

    parts.append(f"## Part A — Findings ({n_findings} total)\n")

    # Severity table
    sev_counter: Counter[str] = Counter(f["severity"] for f in findings)
    parts.append("### Severity")
    parts.append(_md_table(
        ["P0", "P1", "P2"],
        [[str(sev_counter.get("P0", 0)), str(sev_counter.get("P1", 0)), str(sev_counter.get("P2", 0))]],
    ))
    parts.append("")

    # Kind table (sorted descending by count)
    kind_counter: Counter[str] = Counter(f["kind"] for f in findings)
    parts.append("### Kind")
    kind_rows = [[k, str(kind_counter[k])] for k in sorted(kind_counter, key=lambda k: -kind_counter[k])]
    parts.append(_md_table(["Kind", "Count"], kind_rows))
    parts.append("")

    # Catalog tag two-column table
    tag_counter: Counter[str] = Counter(
        f["catalog_tag"] for f in findings if "catalog_tag" in f
    )
    parts.append("### Catalog tag (drift D1-D14, invariant I1-I13)")
    parts.append(_two_col_catalog_table(tag_counter))
    parts.append("")

    # By-slice table (alphabetically sorted by slice name)
    slice_counter: Counter[str] = Counter(_classify_slice(f["location"]) for f in findings)
    parts.append("### By slice")
    # Sort by descending count, then alpha for ties (matches reference ordering)
    slice_rows = [
        [s, str(slice_counter[s])]
        for s in sorted(slice_counter, key=lambda s: (-slice_counter[s], s))
    ]
    parts.append(_md_table(["Slice", "Findings"], slice_rows))
    parts.append("")

    # ------------------------------------------------------------------
    # Part B — Fix Plan
    # ------------------------------------------------------------------
    tasks: list[dict[str, Any]] = fix_plan_doc.get("tasks", [])
    n_tasks = len(tasks)

    parts.append(f"## Part B — Fix Plan ({n_tasks} tasks)\n")

    task_kind_counter: Counter[str] = Counter(t["kind"] for t in tasks)
    task_kind_rows = [
        [k, str(task_kind_counter[k])]
        for k in sorted(task_kind_counter)
    ]
    parts.append(_md_table(["Kind", "Count"], task_kind_rows))
    parts.append("")

    # ------------------------------------------------------------------
    # Phase trace
    # ------------------------------------------------------------------
    parts.append("## Phase trace\n")

    # Phase 5 (finalize) is the phase that writes this summary — exclude it from the
    # trace table so it doesn't appear as a self-referential entry.
    _FINALIZE_PHASE = 5
    trace_phases = [p for p in phases_completed if p != _FINALIZE_PHASE]

    # Prefer manifest-supplied trace (either spelling); otherwise derive from filesystem.
    phase_traces: list[dict[str, Any]] = (
        manifest.get("phase_trace") or manifest.get("phase_traces") or []
    )
    if phase_traces:
        # Full trace available — render with loop iterations and outcome columns.
        trace_by_phase: dict[int, dict[str, Any]] = {
            t.get("phase", -1): t for t in phase_traces
        }
        trace_rows: list[list[str]] = []
        for phase in trace_phases:
            trace = trace_by_phase.get(phase, {})
            raw_iters = trace.get("loop_iterations") if trace else None
            loop_iters = "—" if raw_iters is None else str(raw_iters)
            outcome = (trace.get("outcome") or "—") if trace else "—"
            trace_rows.append([_phase_label(phase), loop_iters, outcome])
        parts.append(_md_table(["Phase", "Loop iterations", "Outcome"], trace_rows))
    else:
        # Derive a best-effort trace from filesystem state.
        derived_rows: list[list[str]] = []
        for phase in trace_phases:
            derived_rows.append([
                _phase_label(phase),
                _derive_loop_iterations(run_dir, phase),
                _derive_outcome(run_dir, phase),
            ])
        parts.append(_md_table(["Phase", "Loop iterations", "Outcome"], derived_rows))

    parts.append("")

    # ------------------------------------------------------------------
    # Audit-of-audit issues
    # ------------------------------------------------------------------
    audit_issues: list[dict[str, Any]] = manifest.get("meta_findings", [])
    parts.append("## Audit-of-audit issues\n")
    if audit_issues:
        parts.append("Recorded in `manifest.json:meta_findings[]`:\n")
        for idx, issue in enumerate(audit_issues, start=1):
            issue_text = issue.get("description", issue.get("issue", "(no description)"))
            parts.append(f"{idx}. {issue_text}")
    else:
        parts.append("Audit-of-audit: 0 issues (meta-review verified).")
    parts.append("")

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------
    parts.append(_artifacts_section(run_dir, n_findings, n_tasks))
    parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate SUMMARY.md for a completed devspec_pr_audit run.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--run-dir",
        required=True,
        metavar="PATH",
        help="Path to the audit run directory (must contain findings.json and manifest.json; fix_plan.json is optional and required only when findings are non-empty).",
    )
    ap.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Output path for SUMMARY.md (default: <run-dir>/SUMMARY.md).",
    )
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"ERROR: --run-dir '{run_dir}' does not exist or is not a directory.", file=sys.stderr)
        return 1

    # Locate schema files relative to this script's location.
    # The script lives at .claude/skills/devspec_pr_audit/scripts/p5_finalize.py
    # Schemas live at  schema/infra/*.schema.json  (toolkit root)
    script_dir = Path(__file__).resolve().parent
    toolkit_root = script_dir.parent.parent.parent.parent  # scripts -> devspec_pr_audit -> skills -> .claude -> toolkit root

    findings_schema_path = toolkit_root / "schema" / "infra" / "findings.schema.json"
    fix_plan_schema_path = toolkit_root / "schema" / "infra" / "pr_audit_fix_plan.schema.json"

    # Fallback: search relative to cwd if toolkit structure isn't found.
    if not findings_schema_path.exists():
        findings_schema_path = Path("schema/infra/findings.schema.json")
    if not fix_plan_schema_path.exists():
        fix_plan_schema_path = Path("schema/infra/pr_audit_fix_plan.schema.json")

    # Input paths
    findings_path = run_dir / "findings.json"
    fix_plan_path = run_dir / "fix_plan.json"
    manifest_path = run_dir / "manifest.json"

    # Check presence — fix_plan.json is optional; zero-findings runs may omit it
    missing: list[str] = []
    for p, name in [
        (findings_path, "findings.json"),
        (manifest_path, "manifest.json"),
    ]:
        if not p.exists():
            missing.append(f"  {name} at {p}")
    if missing:
        print("ERROR: missing required inputs in --run-dir:", file=sys.stderr)
        for m in missing:
            print(m, file=sys.stderr)
        return 1

    # Check findings schema (always required); fix_plan schema is checked inside the conditional below
    if not findings_schema_path.exists():
        print(
            f"ERROR: schema file not found: findings.schema.json (tried {findings_schema_path}). "
            "Run from the toolkit root or ensure schema/infra/ is present.",
            file=sys.stderr,
        )
        return 1

    try:
        # Load required inputs
        findings_doc = _load_json(findings_path, "findings.json")
        manifest = _load_json(manifest_path, "manifest.json")

        # G3: exit early if a prior phase (e.g. validate_agent_outputs) set status=blocked
        if manifest.get("status") == "blocked":
            reason = manifest.get("blocked_reason", "(no reason recorded)")
            print(f"ERROR: run is blocked — {reason}; skipping summary generation.", file=sys.stderr)
            return 1

        # Load and validate findings
        findings_schema = _load_json(findings_schema_path, "findings.schema.json")
        _validate_document(findings_doc, findings_schema, findings_schema_path, "findings.json")

        # fix_plan.json is optional — zero-findings runs do not produce one.
        # Non-empty findings without a fix_plan is an error (P4 consolidation was not run).
        if fix_plan_path.exists():
            if not fix_plan_schema_path.exists():
                print(
                    f"ERROR: schema file not found: pr_audit_fix_plan.schema.json (tried {fix_plan_schema_path}). "
                    "Run from the toolkit root or ensure schema/infra/ is present.",
                    file=sys.stderr,
                )
                return 1
            fix_plan_doc = _load_json(fix_plan_path, "fix_plan.json")
            fix_plan_schema = _load_json(fix_plan_schema_path, "pr_audit_fix_plan.schema.json")
            _validate_document(fix_plan_doc, fix_plan_schema, fix_plan_schema_path, "fix_plan.json")
        else:
            if findings_doc.get("findings"):
                print(
                    "ERROR: fix_plan.json absent but findings.json contains findings — "
                    "run consolidation (P4) before finalizing.",
                    file=sys.stderr,
                )
                return 1
            fix_plan_doc = {}

        # Build summary
        summary = build_summary(run_dir, findings_doc, fix_plan_doc, manifest)

        # Write output
        output_path = Path(args.output) if args.output else run_dir / "SUMMARY.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(summary, encoding="utf-8")
        print(f"OK: wrote {output_path}")
        return 0

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: unexpected error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
