from __future__ import annotations

import glob
import json
import os
from typing import Any, Dict, List, Tuple


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            stripped = raw_line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
    return rows


def build_dashboard(
    eval_rows_glob: str,
    replay_reports_glob: str,
) -> Tuple[Dict[str, Any], str]:
    eval_row_files = sorted(glob.glob(eval_rows_glob))
    replay_files = sorted(glob.glob(replay_reports_glob))

    total_rows = 0
    capture_level_counts: Dict[str, int] = {}
    event_type_counts: Dict[str, int] = {}
    token_prompt_total = 0
    token_completion_total = 0
    token_total = 0
    redaction_total = 0

    for path in eval_row_files:
        for row in _load_jsonl(path):
            total_rows += 1
            capture = str(row.get("capture_level", "unknown"))
            capture_level_counts[capture] = capture_level_counts.get(capture, 0) + 1
            event_type = str(row.get("event_type", "UNKNOWN"))
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
            token_prompt_total += int(row.get("token_prompt", 0) or 0)
            token_completion_total += int(row.get("token_completion", 0) or 0)
            token_total += int(row.get("token_total", 0) or 0)
            redaction_total += int(row.get("redaction_total_replacements", 0) or 0)

    replay_status_counts: Dict[str, int] = {}
    replay_warnings = 0
    replay_errors = 0
    replay_artifact_checked = 0
    replay_artifact_mismatch = 0
    replay_artifact_missing = 0
    replay_total_events = 0

    for path in replay_files:
        report = _load_json(path)
        status = str(report.get("status", "unknown"))
        replay_status_counts[status] = replay_status_counts.get(status, 0) + 1
        replay_warnings += len(report.get("warnings", []))
        replay_errors += len(report.get("errors", []))
        summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
        replay_total_events += int(summary.get("total_events", 0) or 0)
        artifact = report.get("artifact_verification", {}) if isinstance(report.get("artifact_verification"), dict) else {}
        replay_artifact_checked += int(artifact.get("checked", 0) or 0)
        replay_artifact_mismatch += int(artifact.get("mismatch", 0) or 0)
        replay_artifact_missing += int(artifact.get("missing", 0) or 0)

    summary: Dict[str, Any] = {
        "files": {
            "eval_row_files": eval_row_files,
            "replay_report_files": replay_files,
        },
        "totals": {
            "sessions": len(replay_files),
            "eval_rows": total_rows,
            "replay_events": replay_total_events,
            "token_prompt": token_prompt_total,
            "token_completion": token_completion_total,
            "token_total": token_total,
            "redaction_total_replacements": redaction_total,
            "replay_warnings": replay_warnings,
            "replay_errors": replay_errors,
            "artifact_checked": replay_artifact_checked,
            "artifact_mismatch": replay_artifact_mismatch,
            "artifact_missing": replay_artifact_missing,
        },
        "capture_level_counts": capture_level_counts,
        "event_type_counts": event_type_counts,
        "replay_status_counts": replay_status_counts,
    }

    lines: List[str] = []
    lines.append("## Trinity Eval Dashboard")
    lines.append("")
    lines.append(f"- Sessions: {summary['totals']['sessions']}")
    lines.append(f"- Eval rows: {summary['totals']['eval_rows']}")
    lines.append(f"- Replay events: {summary['totals']['replay_events']}")
    lines.append(f"- Tokens (prompt/completion/total): {token_prompt_total}/{token_completion_total}/{token_total}")
    lines.append(f"- Redaction replacements: {redaction_total}")
    lines.append(f"- Replay warnings/errors: {replay_warnings}/{replay_errors}")
    lines.append(f"- Artifact checks (checked/mismatch/missing): {replay_artifact_checked}/{replay_artifact_mismatch}/{replay_artifact_missing}")
    lines.append("")
    lines.append("### Replay Status")
    for key in sorted(replay_status_counts):
        lines.append(f"- {key}: {replay_status_counts[key]}")
    lines.append("")
    lines.append("### Capture Levels")
    for key in sorted(capture_level_counts):
        lines.append(f"- {key}: {capture_level_counts[key]}")
    lines.append("")
    lines.append("### Event Types")
    for key in sorted(event_type_counts):
        lines.append(f"- {key}: {event_type_counts[key]}")
    lines.append("")

    return summary, "\n".join(lines)


def write_dashboard(
    eval_rows_glob: str,
    replay_reports_glob: str,
    out_json: str | None = None,
    out_md: str | None = None,
) -> Tuple[Dict[str, Any], str]:
    summary, markdown = build_dashboard(eval_rows_glob, replay_reports_glob)
    if out_json:
        out_json_abs = os.path.abspath(out_json)
        os.makedirs(os.path.dirname(out_json_abs), exist_ok=True)
        with open(out_json_abs, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    if out_md:
        out_md_abs = os.path.abspath(out_md)
        os.makedirs(os.path.dirname(out_md_abs), exist_ok=True)
        with open(out_md_abs, "w", encoding="utf-8") as f:
            f.write(markdown + "\n")
    return summary, markdown
