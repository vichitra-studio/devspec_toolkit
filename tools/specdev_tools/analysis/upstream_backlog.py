"""Upstream-backlog rollup: aggregate execution.emergent_ambiguities across
milestone plans under ``spec/impl_context/*.json``.

Read-only reporter. Four pure layers with one-way deps:
  Loader     -> iter_spec_artifacts + load_json_artifact (FS)
  Classifier -> pure: record -> (bucket, matched_rule, matched_entry)
  Filter     -> pure: records + severity/status thresholds -> records
  Render     -> pure: records -> str (plain) or dict (json)

``run()`` returns ``(stdout_payload, stderr_lines, exit_code)`` — no side
effects — so CLI dispatch owns all I/O. W613 stderr lines are formatted
manually (not via ``SpecError.render()``) because the spec requires the
format ``W613 UPSTREAM_BACKLOG_UNCLASSIFIED <target>`` while ``render()``
places the path between code and message.

Path-separator non-goal: the ``/impl_context/`` path filter hard-codes
forward slashes. The toolkit is darwin/linux-targeted; Windows is not
supported.
"""
from __future__ import annotations

import json
import re
from typing import Iterator, Optional

from ..core.errors import ERROR_CODES
from ..core.loaders import iter_spec_artifacts, load_json_artifact


SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

RULE1_RE = re.compile(r"^spec/([0-9]{2}[a-z]?)_[a-z0-9_]+\.json(?::.+)?$")
RULE2_CODE_RE = re.compile(r"\b[EW][0-9]{3}\b")

_IMPL_CONTEXT_RE = re.compile(r"/impl_context/[^/]+\.json$")


# ---------------------------------------------------------------------------
# Classifier (pure)
# ---------------------------------------------------------------------------

def classify(record: dict) -> tuple[str, int, Optional[str]]:
    """Return ``(bucket, matched_rule, matched_entry)`` for one ambiguity.

    First-match precedence across entries in ``impact[]``. Non-string entries
    are skipped defensively even though the schema guarantees strings.
    """
    impact = record.get("impact")
    if not isinstance(impact, list):
        return ("unclassified", 4, None)
    for entry in impact:
        if not isinstance(entry, str):
            continue
        m = RULE1_RE.match(entry)
        if m:
            return (f"step_{m.group(1)}", 1, entry)
        if "devspec_toolkit" in entry or RULE2_CODE_RE.search(entry):
            return ("toolkit", 2, entry)
        if entry.startswith("plan.") or entry.startswith("execution."):
            return ("plan_level", 3, entry)
    return ("unclassified", 4, None)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _iter_plans(spec_dir: str) -> Iterator[tuple[str, Optional[dict], Optional[str]]]:
    """Yield ``(path, data_or_None, malformed_reason_or_None)`` for every
    ``impl_context/*.json`` plan under *spec_dir*. Nested directories below
    ``impl_context/`` are not scanned (only immediate children, no subdirectories).
    """
    for path in iter_spec_artifacts(spec_dir):
        if not _IMPL_CONTEXT_RE.search(path):
            continue
        try:
            data = load_json_artifact(path)
        except json.JSONDecodeError:
            yield (path, None, f"malformed_plan={path}")
            continue
        except UnicodeDecodeError:
            yield (path, None, f"unicode_decode_error={path}")
            continue
        yield (path, data, None)


# ---------------------------------------------------------------------------
# Record extraction + coercion
# ---------------------------------------------------------------------------

def _coerce_records(
    plan: dict, path: str
) -> tuple[list[dict], list[str]]:
    """Return ``(records, e520_stderr_lines)`` extracted from one plan.

    Applies the null/missing collapse on ``execution`` and
    ``emergent_ambiguities`` uniformly (both ``missing`` and explicit
    ``null`` become an empty list). Skips records with missing/invalid
    ``id`` or ``severity`` and emits E520 per skip.
    """
    records: list[dict] = []
    errors: list[str] = []
    milestone_id = plan.get("id") if isinstance(plan.get("id"), str) else ""
    execution = plan.get("execution") or {}
    if not isinstance(execution, dict):
        return records, errors
    ambiguities = execution.get("emergent_ambiguities") or []
    if not isinstance(ambiguities, list):
        return records, errors

    e520 = ERROR_CODES["E520"]
    for amb in ambiguities:
        if not isinstance(amb, dict):
            errors.append(f"E520 {e520} non_dict_ambiguity in {path}")
            continue
        amb_id = amb.get("id")
        if not isinstance(amb_id, str) or not amb_id:
            errors.append(
                f"E520 {e520} missing_id in {path} "
                f"(milestone={milestone_id or '?'})"
            )
            continue
        severity = amb.get("severity")
        if not isinstance(severity, str) or severity not in SEVERITY_ORDER:
            errors.append(
                f"E520 {e520} invalid_severity={severity!r} in {path} "
                f"(milestone={milestone_id or '?'}, ambiguity={amb_id})"
            )
            continue

        status_raw = amb.get("status")
        status_unset = status_raw in (None, "")
        status = "tracking" if status_unset else status_raw
        description = amb.get("description")
        if not isinstance(description, str):
            description = ""
        impact_raw = amb.get("impact")
        if not isinstance(impact_raw, list):
            impact_raw = []

        bucket, matched_rule, matched_entry = classify({"impact": impact_raw})
        records.append({
            "milestone_id": milestone_id,
            "ambiguity_id": amb_id,
            "severity": severity,
            "status": status,
            "status_unset": status_unset,
            "description": description,
            "impact": impact_raw,
            "bucket": bucket,
            "matched_rule": matched_rule,
            "matched_impact_entry": matched_entry,
        })
    return records, errors


# ---------------------------------------------------------------------------
# Filter (pure)
# ---------------------------------------------------------------------------

def filter_records(
    records: list[dict], severity_min: str, status_filter: str
) -> list[dict]:
    min_rank = SEVERITY_ORDER[severity_min]
    out: list[dict] = []
    for r in records:
        if SEVERITY_ORDER[r["severity"]] < min_rank:
            continue
        if status_filter == "open" and r["status"] == "resolved":
            continue
        if status_filter == "resolved" and r["status"] != "resolved":
            continue
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Sort keys
# ---------------------------------------------------------------------------

def _bucket_sort_key(bucket: str) -> tuple:
    if bucket.startswith("step_"):
        suffix = bucket[5:]
        m = re.match(r"(\d+)([a-z]*)", suffix)
        num = int(m.group(1)) if m else 0
        letter = m.group(2) if m else ""
        return (0, num, letter)
    return ({"plan_level": 1, "toolkit": 2, "unclassified": 3}[bucket],)


def _record_sort_key(r: dict) -> tuple:
    return (
        _bucket_sort_key(r["bucket"]),
        -SEVERITY_ORDER[r["severity"]],
        r["milestone_id"],
        r["ambiguity_id"],
    )


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

_BUCKET_LABELS = {
    "plan_level": "Plan-level",
    "toolkit": "Toolkit",
    "unclassified": "Unclassified",
}


def _bucket_label(bucket: str) -> str:
    if bucket.startswith("step_"):
        return f"Step {bucket[5:]}"
    return _BUCKET_LABELS[bucket]


def _status_display(r: dict) -> str:
    if r["status_unset"]:
        return "(unset status → tracking)"
    return r["status"]


def _wrap_impact(impact: list, indent: int, width: int = 80) -> list[str]:
    """Join string entries of *impact* with ' | ', soft-wrap to *width* chars.

    Continuation lines align with the first entry column and start with
    ``| `` to preserve the separator visually in the plain-text report.
    Non-string entries are filtered out for plain-text rendering (JSON
    output preserves them verbatim for auditability).
    """
    strings = [e for e in impact if isinstance(e, str)]
    if not strings:
        return []
    prefix = " " * indent + "impact: "
    cont_prefix = " " * (indent + len("impact: "))
    lines: list[str] = []
    current = prefix + strings[0]
    for entry in strings[1:]:
        addition = " | " + entry
        if len(current) + len(addition) <= width:
            current += addition
        else:
            lines.append(current)
            current = cont_prefix + "| " + entry
    lines.append(current)
    return lines


def render_plain(
    records: list[dict],
    *,
    status_filter: str,
    total_records: int,
    open_count: int,
    resolved_count: int,
    milestones_scanned: int,
    unclassified_w613_count: int,
) -> str:
    """Render the plain-text report of upstream ambiguity backlog items."""
    if status_filter == "resolved":
        unit = "resolved"
    elif status_filter == "all":
        unit = "records"
    else:
        unit = "open"

    # Group by bucket, preserving the record-level sort already applied.
    buckets: dict[str, list[dict]] = {}
    for r in records:
        buckets.setdefault(r["bucket"], []).append(r)

    ordered_buckets = sorted(buckets.keys(), key=_bucket_sort_key)

    sections: list[str] = []
    for bucket in ordered_buckets:
        label = _bucket_label(bucket)
        recs = buckets[bucket]
        header = f"{label} — {len(recs)} {unit}"
        if bucket == "unclassified" and unclassified_w613_count > 0:
            header += f"  [{unclassified_w613_count} x W613 — see stderr]"
        lines = [header]
        for r in recs:
            sev = r["severity"]
            pad = " " * max(1, 9 - len(sev))
            lines.append(
                f"  [{sev}]{pad}{r['milestone_id']} / {r['ambiguity_id']} — "
                f"{_status_display(r)}"
            )
            desc = r["description"]
            if desc:
                first_line = desc.split("\n", 1)[0].strip()
                if first_line:
                    lines.append(f"           {first_line}")
            lines.extend(_wrap_impact(r["impact"], indent=11))
        sections.append("\n".join(lines))

    body = "\n\n".join(sections)
    ms_word = "milestone" if milestones_scanned == 1 else "milestones"
    rec_word = "record" if total_records == 1 else "records"
    totals = (
        f"Totals: {open_count} open / {resolved_count} resolved across "
        f"{milestones_scanned} {ms_word} / {total_records} {rec_word}."
    )
    if body:
        return f"{body}\n\n{totals}"
    return totals


def render_json(
    records: list[dict],
    *,
    total_records: int,
    open_count: int,
    resolved_count: int,
    milestones_scanned: int,
    unclassified_count: int,
    warnings: list[dict],
) -> str:
    payload = {
        "schema_version": "1",
        "summary": {
            "total_records": total_records,
            "open_count": open_count,
            "resolved_count": resolved_count,
            "milestones_scanned": milestones_scanned,
            "unclassified_count": unclassified_count,
        },
        "records": [
            {
                "bucket": r["bucket"],
                "milestone_id": r["milestone_id"],
                "ambiguity_id": r["ambiguity_id"],
                "severity": r["severity"],
                "status": r["status"],
                "description": r["description"],
                "impact": r["impact"],
                "matched_rule": r["matched_rule"],
                "matched_impact_entry": r["matched_impact_entry"],
            }
            for r in records
        ],
        "warnings": warnings,
    }
    return json.dumps(payload, indent=2, sort_keys=False)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run(
    spec_dir: str,
    *,
    repo_root: str = ".",
    spec_root: Optional[str] = None,
    severity: str = "low",
    status: str = "open",
    json_output: bool = False,
) -> tuple[str, list[str], int]:
    """Return ``(stdout_payload, stderr_lines, exit_code)``.

    ``repo_root`` / ``spec_root`` are accepted for submodule CLI symmetry;
    this command consults neither in the MVP.
    """
    del repo_root, spec_root  # reserved for CLI symmetry; unused in MVP
    stderr_lines: list[str] = []
    exit_code = 0
    all_records: list[dict] = []
    milestones: set[str] = set()

    for path, data, malformed in _iter_plans(spec_dir):
        if malformed:
            stderr_lines.append(
                f"E520 {ERROR_CODES.get('E520', 'UNRESOLVED_INPUT')} {malformed}"
            )
            exit_code = 2
            continue
        if not isinstance(data, dict) or not data:
            continue
        records, e520s = _coerce_records(data, path)
        if e520s:
            stderr_lines.extend(e520s)
            exit_code = 2
        for r in records:
            if r["milestone_id"]:
                milestones.add(r["milestone_id"])
            all_records.append(r)

    total_records = len(all_records)
    open_count = sum(1 for r in all_records if r["status"] != "resolved")
    resolved_count = total_records - open_count
    unclassified_count = sum(
        1 for r in all_records if r["bucket"] == "unclassified"
    )

    filtered = filter_records(all_records, severity, status)
    filtered.sort(key=_record_sort_key)

    w613_targets: list[str] = []
    for r in filtered:
        if r["bucket"] == "unclassified":
            target = f"{r['milestone_id']}:{r['ambiguity_id']}"
            w613_targets.append(target)
            stderr_lines.append(
                f"W613 {ERROR_CODES['W613']} {target}"
            )
    warnings_payload = [
        {"code": "W613", "target": t} for t in w613_targets
    ]

    if json_output:
        stdout = render_json(
            filtered,
            total_records=total_records,
            open_count=open_count,
            resolved_count=resolved_count,
            milestones_scanned=len(milestones),
            unclassified_count=unclassified_count,
            warnings=warnings_payload,
        )
    else:
        stdout = render_plain(
            filtered,
            status_filter=status,
            total_records=total_records,
            open_count=open_count,
            resolved_count=resolved_count,
            milestones_scanned=len(milestones),
            unclassified_w613_count=len(w613_targets),
        )

    return stdout, stderr_lines, exit_code
