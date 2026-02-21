from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .registry import SchemaRegistry
from .trinity_runtime_validate import validate_runtime_file


def _registry_for(registry: SchemaRegistry) -> Registry:
    store = {uri: Resource.from_contents(schema) for uri, schema in registry.store.items()}
    return Registry().with_resources(store.items())


def _load_session_events(session_log_path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    events: List[Dict[str, Any]] = []
    errors: List[str] = []
    with open(session_log_path, "r", encoding="utf-8") as f:
        for idx, raw_line in enumerate(f, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                events.append(json.loads(stripped))
            except json.JSONDecodeError as e:
                errors.append(f"{session_log_path}:{idx}: invalid json line ({e})")
    return events, errors


_FINDING_SEVERITY_RANK = {
    "blocking": 4,
    "major": 3,
    "minor": 2,
    "nit": 1,
}


def _resolve_ref(session_log_path: str, repo_root: str, ref: str) -> str:
    if os.path.isabs(ref):
        return ref
    local = os.path.abspath(os.path.join(os.path.dirname(session_log_path), ref))
    if os.path.exists(local):
        return local
    return os.path.abspath(os.path.join(repo_root, ref))


def _safe_load_json(path: str) -> Dict[str, Any] | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _max_finding_severity(findings: Any) -> str | None:
    if not isinstance(findings, list):
        return None
    best: str | None = None
    best_rank = 0
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severity = finding.get("severity")
        if not isinstance(severity, str):
            continue
        rank = _FINDING_SEVERITY_RANK.get(severity, 0)
        if rank > best_rank:
            best_rank = rank
            best = severity
    return best


def _derive_eval_labels(repo_root: str, session_log_path: str, event: Dict[str, Any]) -> Dict[str, Any]:
    content = event.get("content", {}) if isinstance(event.get("content"), dict) else {}
    task_result_ref = content.get("task_result_artifact_ref")
    labels: Dict[str, Any] = {
        "task_result_artifact_ref": task_result_ref if isinstance(task_result_ref, str) else None,
        "phase_outcome": None,
        "review_verdict": None,
        "checklist_ids": None,
        "finding_count": None,
        "max_finding_severity": None,
        "remediation_required": None,
    }
    if not isinstance(task_result_ref, str) or not task_result_ref:
        return labels

    task_result_path = _resolve_ref(session_log_path, repo_root, task_result_ref)
    task_result = _safe_load_json(task_result_path)
    if not task_result:
        return labels

    status = task_result.get("status")
    if isinstance(status, str) and status in {"success", "blocked", "failed", "questions"}:
        labels["phase_outcome"] = status

    findings = task_result.get("findings", [])
    if isinstance(findings, list):
        labels["finding_count"] = len(findings)
        labels["max_finding_severity"] = _max_finding_severity(findings)

    if labels["phase_outcome"] in {"blocked", "failed"}:
        labels["remediation_required"] = True

    artifacts = task_result.get("artifacts", [])
    if not isinstance(artifacts, list):
        return labels

    checklist_ids: list[str] = []
    for artifact_ref in artifacts:
        if not isinstance(artifact_ref, str) or not artifact_ref.endswith(".json"):
            continue
        artifact_path = _resolve_ref(session_log_path, repo_root, artifact_ref)
        artifact = _safe_load_json(artifact_path)
        if not artifact:
            continue
        if artifact.get("$schema") != "https://specdev.local/schema/16_impl_context.schema.json":
            continue

        review = artifact.get("review", {})
        if isinstance(review, dict):
            verdict = review.get("verdict")
            if isinstance(verdict, str) and verdict in {"verified", "deferred", "rejected"}:
                labels["review_verdict"] = verdict

        plan = artifact.get("plan", {})
        if isinstance(plan, dict):
            checklist = plan.get("spec_alignment", {}).get("checklist", [])
            if isinstance(checklist, list):
                for item in checklist:
                    if not isinstance(item, dict):
                        continue
                    cid = item.get("id")
                    if isinstance(cid, str) and cid and cid not in checklist_ids:
                        checklist_ids.append(cid)

    if checklist_ids:
        labels["checklist_ids"] = checklist_ids

    if labels["remediation_required"] is None:
        max_sev = labels.get("max_finding_severity")
        review_verdict = labels.get("review_verdict")
        labels["remediation_required"] = bool(
            max_sev in {"blocking", "major"} or review_verdict in {"deferred", "rejected"}
        )

    return labels


def _event_to_eval_row(repo_root: str, session_log_path: str, event: Dict[str, Any]) -> Dict[str, Any]:
    content = event.get("content", {}) if isinstance(event.get("content"), dict) else {}
    metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
    token_usage = metadata.get("token_usage", {}) if isinstance(metadata.get("token_usage"), dict) else {}
    redaction_stats = metadata.get("redaction_stats", {}) if isinstance(metadata.get("redaction_stats"), dict) else {}
    redaction_classes = redaction_stats.get("classes_detected", [])
    tool_call = content.get("tool_call", {}) if isinstance(content.get("tool_call"), dict) else {}
    tool_result = content.get("tool_result", {}) if isinstance(content.get("tool_result"), dict) else {}
    validation = content.get("validation", {}) if isinstance(content.get("validation"), dict) else {}
    labels = _derive_eval_labels(repo_root, session_log_path, event)

    return {
        "run_id": event.get("run_id"),
        "event_id": event.get("event_id"),
        "event_sequence": event.get("event_sequence"),
        "timestamp": event.get("timestamp"),
        "event_type": event.get("event_type"),
        "role": event.get("role"),
        "phase_id": event.get("phase_id"),
        "step_id": event.get("step_id"),
        "capture_level": content.get("capture_level"),
        "prompt_artifact_ref": content.get("prompt_artifact_ref"),
        "prompt_sha256": content.get("prompt_sha256"),
        "response_artifact_ref": content.get("response_artifact_ref"),
        "response_sha256": content.get("response_sha256"),
        "artifact_ref": event.get("artifact_ref"),
        "artifact_sha256": event.get("artifact_sha256"),
        "diff_ref": event.get("diff_ref"),
        "task_result_artifact_ref": labels.get("task_result_artifact_ref"),
        "tool_name": tool_call.get("name"),
        "tool_command": tool_result.get("command"),
        "tool_exit_code": tool_result.get("exit_code"),
        "validation_schema": validation.get("schema"),
        "validation_deep_validator": validation.get("deep_validator"),
        "validation_governance": validation.get("governance"),
        "phase_outcome": labels.get("phase_outcome"),
        "review_verdict": labels.get("review_verdict"),
        "checklist_ids": labels.get("checklist_ids"),
        "finding_count": labels.get("finding_count"),
        "max_finding_severity": labels.get("max_finding_severity"),
        "remediation_required": labels.get("remediation_required"),
        "redaction_applied": metadata.get("redaction_applied"),
        "redaction_total_replacements": redaction_stats.get("total_replacements", 0),
        "redaction_classes": redaction_classes if isinstance(redaction_classes, list) else [],
        "token_prompt": token_usage.get("prompt", 0),
        "token_completion": token_usage.get("completion", 0),
        "token_total": token_usage.get("total", 0),
        "event_sha256": event.get("event_sha256"),
        "prev_event_sha256": event.get("prev_event_sha256"),
    }


def _validate_eval_rows(repo_root: str, rows: List[Dict[str, Any]], source_path: str) -> List[str]:
    registry = SchemaRegistry(repo_root)
    schema_uri = "https://specdev.local/schema/trinity/eval_export_row.schema.json"
    schema = registry.load(schema_uri)
    reg = _registry_for(registry)
    validator = Draft202012Validator(
        schema,
        registry=reg,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )

    errors: List[str] = []
    for idx, row in enumerate(rows, start=1):
        row_errors = sorted(validator.iter_errors(row), key=lambda e: list(e.path))
        for e in row_errors:
            path = "/".join(map(str, e.path))
            errors.append(f"{source_path}:row[{idx}]:{path}: {e.message}")
    return errors


def export_eval_rows(
    repo_root: str,
    session_log_path: str,
    out_path: str | None = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Convert a validated Trinity session log into eval-export rows.

    Returns:
        (rows, errors)
    """
    runtime_errors = validate_runtime_file(repo_root, session_log_path, "session_event")
    if runtime_errors:
        return [], runtime_errors

    events, parse_errors = _load_session_events(session_log_path)
    if parse_errors:
        return [], parse_errors

    rows = [_event_to_eval_row(repo_root, session_log_path, event) for event in events]
    row_errors = _validate_eval_rows(repo_root, rows, session_log_path)
    if row_errors:
        return rows, row_errors

    if out_path:
        out_abs = os.path.abspath(out_path)
        os.makedirs(os.path.dirname(out_abs), exist_ok=True)
        with open(out_abs, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return rows, []
