from __future__ import annotations

import datetime as dt
import glob
import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _ci_context() -> Dict[str, str]:
    keys = [
        "GITHUB_REPOSITORY",
        "GITHUB_SHA",
        "GITHUB_REF",
        "GITHUB_RUN_ID",
        "GITHUB_RUN_ATTEMPT",
        "GITHUB_WORKFLOW",
        "GITHUB_ACTOR",
    ]
    out: Dict[str, str] = {}
    for key in keys:
        value = os.getenv(key)
        if value:
            out[key] = value
    return out


def _summarize_replay_report(path: str, report: Dict[str, Any]) -> Dict[str, Any]:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    artifact = report.get("artifact_verification", {}) if isinstance(report.get("artifact_verification"), dict) else {}
    warnings = report.get("warnings", [])
    errors = report.get("errors", [])
    warning_count = len(warnings) if isinstance(warnings, list) else 0
    error_count = len(errors) if isinstance(errors, list) else 0
    return {
        "path": path,
        "status": report.get("status", "unknown"),
        "run_id": summary.get("run_id"),
        "total_events": int(summary.get("total_events", 0) or 0),
        "warning_count": warning_count,
        "error_count": error_count,
        "artifact_checked": int(artifact.get("checked", 0) or 0),
        "artifact_mismatch": int(artifact.get("mismatch", 0) or 0),
        "artifact_missing": int(artifact.get("missing", 0) or 0),
    }


def _default_summary(rows: List[Dict[str, Any]], replay_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    token_prompt = 0
    token_completion = 0
    token_total = 0
    capture_level_counts: Dict[str, int] = {}
    replay_status_counts: Dict[str, int] = {}
    replay_warnings = 0
    replay_errors = 0
    replay_events = 0
    artifact_checked = 0
    artifact_mismatch = 0
    artifact_missing = 0

    for row in rows:
        capture = str(row.get("capture_level", "unknown"))
        capture_level_counts[capture] = capture_level_counts.get(capture, 0) + 1
        token_prompt += int(row.get("token_prompt", 0) or 0)
        token_completion += int(row.get("token_completion", 0) or 0)
        token_total += int(row.get("token_total", 0) or 0)

    for replay in replay_summaries:
        status = str(replay.get("status", "unknown"))
        replay_status_counts[status] = replay_status_counts.get(status, 0) + 1
        replay_warnings += int(replay.get("warning_count", 0) or 0)
        replay_errors += int(replay.get("error_count", 0) or 0)
        replay_events += int(replay.get("total_events", 0) or 0)
        artifact_checked += int(replay.get("artifact_checked", 0) or 0)
        artifact_mismatch += int(replay.get("artifact_mismatch", 0) or 0)
        artifact_missing += int(replay.get("artifact_missing", 0) or 0)

    return {
        "totals": {
            "sessions": len(replay_summaries),
            "eval_rows": len(rows),
            "replay_events": replay_events,
            "token_prompt": token_prompt,
            "token_completion": token_completion,
            "token_total": token_total,
            "replay_warnings": replay_warnings,
            "replay_errors": replay_errors,
            "artifact_checked": artifact_checked,
            "artifact_mismatch": artifact_mismatch,
            "artifact_missing": artifact_missing,
        },
        "capture_level_counts": capture_level_counts,
        "replay_status_counts": replay_status_counts,
    }


def _resolve_env_or_value(value: Optional[str], env_name: Optional[str]) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(env_name, str) and env_name.strip():
        env_value = os.getenv(env_name.strip(), "").strip()
        if env_value:
            return env_value
    return None


def _publish_json(
    endpoint: str,
    payload: Dict[str, Any],
    auth_token: Optional[str] = None,
    timeout_seconds: int = 20,
) -> Tuple[Optional[int], Optional[str], List[str]]:
    errors: List[str] = []
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "specdev-tools/trinity-publish-eval",
    }
    if isinstance(auth_token, str) and auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = response.getcode()
            response_body = response.read(4096).decode("utf-8", errors="replace")
            if status >= 400:
                errors.append(f"publish failed with HTTP status {status}")
            return status, response_body, errors
    except urllib.error.HTTPError as e:
        response_body = e.read(4096).decode("utf-8", errors="replace")
        errors.append(f"publish failed with HTTP status {e.code}")
        return e.code, response_body, errors
    except urllib.error.URLError as e:
        errors.append(f"publish failed ({e})")
        return None, None, errors
    except Exception as e:
        errors.append(f"publish failed ({e})")
        return None, None, errors


def publish_eval_bundle(
    rows_glob: str,
    replay_glob: str,
    dashboard_json: Optional[str] = None,
    out_path: Optional[str] = None,
    source: Optional[str] = None,
    max_rows: int = 50000,
    endpoint: Optional[str] = None,
    endpoint_env: Optional[str] = None,
    auth_token: Optional[str] = None,
    auth_token_env: Optional[str] = None,
    require_publish: bool = False,
    timeout_seconds: int = 20,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    errors: List[str] = []

    row_files = sorted(glob.glob(rows_glob))
    replay_files = sorted(glob.glob(replay_glob))

    rows: List[Dict[str, Any]] = []
    rows_truncated = False
    for path in row_files:
        for row in _load_jsonl(path):
            if len(rows) >= max_rows:
                rows_truncated = True
                break
            rows.append(row)
        if rows_truncated:
            break

    replay_summaries: List[Dict[str, Any]] = []
    for path in replay_files:
        report = _load_json(path)
        replay_summaries.append(_summarize_replay_report(path, report))

    dashboard: Optional[Dict[str, Any]] = None
    if dashboard_json:
        dashboard_path = os.path.abspath(dashboard_json)
        if os.path.exists(dashboard_path):
            dashboard = _load_json(dashboard_path)
        else:
            errors.append(f"dashboard JSON not found: {dashboard_path}")

    summary = dashboard if isinstance(dashboard, dict) else _default_summary(rows, replay_summaries)
    bundle: Dict[str, Any] = {
        "schema_version": "trinity-eval-export-v1",
        "generated_at": _utc_now_iso(),
        "source": source or "local",
        "ci_context": _ci_context(),
        "files": {
            "row_files": row_files,
            "replay_files": replay_files,
            "dashboard_json": os.path.abspath(dashboard_json) if dashboard_json else None,
        },
        "summary": summary,
        "row_count_exported": len(rows),
        "rows_truncated": rows_truncated,
        "rows": rows,
        "replay_reports": replay_summaries,
    }

    resolved_endpoint = _resolve_env_or_value(endpoint, endpoint_env)
    resolved_auth = _resolve_env_or_value(auth_token, auth_token_env)
    publish_result: Dict[str, Any] = {
        "status": "skipped",
        "endpoint": resolved_endpoint,
        "http_status": None,
        "response_body_preview": None,
    }

    if resolved_endpoint:
        status, response_preview, publish_errors = _publish_json(
            endpoint=resolved_endpoint,
            payload=bundle,
            auth_token=resolved_auth,
            timeout_seconds=timeout_seconds,
        )
        publish_result["http_status"] = status
        publish_result["response_body_preview"] = response_preview
        if publish_errors:
            publish_result["status"] = "failed"
            errors.extend(publish_errors)
        else:
            publish_result["status"] = "published"
    elif require_publish:
        publish_result["status"] = "failed"
        errors.append("publish endpoint is not configured")

    if out_path:
        out_abs = os.path.abspath(out_path)
        os.makedirs(os.path.dirname(out_abs), exist_ok=True)
        payload = {"bundle": bundle, "publish_result": publish_result}
        with open(out_abs, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    return bundle, publish_result, errors
