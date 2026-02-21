from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from .trinity_runtime_validate import validate_runtime_file

PROTO_VER = "trinity-runtime-v1"


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            stripped = raw_line.strip()
            if not stripped:
                continue
            events.append(json.loads(stripped))
    return events


def _infer_phase(phase_id: Any) -> Optional[str]:
    if not isinstance(phase_id, str):
        return None
    for candidate in ("16a", "16b", "16c"):
        if candidate in phase_id:
            return candidate
    return None


def _find_latest_spawn_task_input_ref(events: List[Dict[str, Any]]) -> Optional[str]:
    for event in reversed(events):
        if event.get("event_type") != "SPAWN":
            continue
        content = event.get("content", {})
        if isinstance(content, dict):
            ref = content.get("task_input_artifact_ref")
            if isinstance(ref, str) and ref:
                return ref
    return None


def _create_actions_from_replay_report(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    warnings = report.get("warnings", [])
    errors = report.get("errors", [])
    issues = []
    if isinstance(warnings, list):
        issues.extend([("warning", w) for w in warnings if isinstance(w, str)])
    if isinstance(errors, list):
        issues.extend([("error", e) for e in errors if isinstance(e, str)])

    for severity, issue in issues:
        if "missing" in issue and "artifact" in issue:
            actions.append(
                {
                    "type": "restore_artifact",
                    "severity": severity,
                    "issue": issue,
                    "operation": "recreate_or_restore_missing_artifact",
                }
            )
        elif "hash mismatch" in issue:
            actions.append(
                {
                    "type": "artifact_hash_mismatch",
                    "severity": severity,
                    "issue": issue,
                    "operation": "regenerate_artifact_and_refresh_hash_binding",
                }
            )
        elif "capture_level" in issue or "capture_policy" in issue:
            actions.append(
                {
                    "type": "capture_policy_violation",
                    "severity": severity,
                    "issue": issue,
                    "operation": "adjust_capture_policy_or_event_capture_fields",
                }
            )
        elif "redaction" in issue:
            actions.append(
                {
                    "type": "redaction_mismatch",
                    "severity": severity,
                    "issue": issue,
                    "operation": "re-run_redaction_pipeline_and_update_stats",
                }
            )
        else:
            actions.append(
                {
                    "type": "manual_review",
                    "severity": severity,
                    "issue": issue,
                    "operation": "manual_triage",
                }
            )

    if not actions:
        actions.append(
            {
                "type": "no_action",
                "severity": "info",
                "issue": "Replay report has no warnings/errors.",
                "operation": "continue",
            }
        )
    return actions


def _resolve_ref(base_path: str, repo_root: str, ref: str) -> str:
    if os.path.isabs(ref):
        return ref
    local = os.path.abspath(os.path.join(os.path.dirname(base_path), ref))
    if os.path.exists(local):
        return local
    return os.path.abspath(os.path.join(repo_root, ref))


def _prepare_resume_task_input(
    repo_root: str,
    session_log_path: str,
    report: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    events = _load_jsonl(session_log_path)
    task_input_ref = _find_latest_spawn_task_input_ref(events)
    if not task_input_ref:
        return None, ["No spawn task_input_artifact_ref found in session log."]

    task_input_path = _resolve_ref(session_log_path, repo_root, task_input_ref)
    if not os.path.exists(task_input_path):
        return None, [f"Resume source task_input not found: {task_input_ref}"]

    payload = _load_json(task_input_path)
    run_id = report.get("summary", {}).get("run_id", "run")
    payload["child_id"] = f"resume-{run_id}"
    payload["task_description"] = f"{payload.get('task_description', 'resume task')} [resume remediation]"
    return payload, errors


def _prepare_session_state(
    report: Dict[str, Any], resume_task_input_ref: Optional[str]
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    run_id = summary.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        errors.append("Resume lineage missing summary.run_id; cannot generate deterministic session_state.")

    timeline = report.get("timeline", []) if isinstance(report.get("timeline"), list) else []
    if not timeline or not isinstance(timeline[-1], dict):
        errors.append("Resume lineage missing timeline events; cannot infer parent_id/phase/last_event_id.")
        return None, errors

    last_event = timeline[-1]
    parent_id = last_event.get("agent_id")
    if not isinstance(parent_id, str) or not parent_id:
        errors.append("Resume lineage missing last timeline agent_id; cannot generate deterministic parent_id.")

    step_ids = summary.get("step_ids", []) if isinstance(summary.get("step_ids"), list) else []
    step_id = step_ids[0] if step_ids and isinstance(step_ids[0], str) and step_ids[0] else None
    if not step_id and isinstance(last_event.get("step_id"), str) and last_event.get("step_id"):
        step_id = last_event.get("step_id")
    if not isinstance(step_id, str) or not step_id:
        errors.append("Resume lineage missing step_id; cannot generate deterministic session_state.")

    phase = _infer_phase(last_event.get("phase_id") if isinstance(last_event, dict) else None)
    if not isinstance(phase, str):
        errors.append("Resume lineage missing parseable phase_id (expected 16a/16b/16c token).")

    event_id = last_event.get("event_id") if isinstance(last_event, dict) else None
    if errors:
        return None, errors

    pending_child_id = f"resume-{run_id}"
    # Session-state deep validation expects canonical spawn refs for resume lineage.
    canonical_pending_spawn_ref = f".trinity/runtime/spawns/{pending_child_id}/task_input.json"
    return {
        "protocol_version": PROTO_VER,
        "run_id": run_id,
        "parent_id": parent_id,
        "active_phase": phase,
        "step_id": step_id,
        "status": "resuming",
        "pending_child_id": pending_child_id,
        "pending_spawn_ref": canonical_pending_spawn_ref if isinstance(resume_task_input_ref, str) and resume_task_input_ref else None,
        "spawn_log_ref": None,
        "scratchpad_ref": None,
        "last_event_id": event_id if isinstance(event_id, str) else None,
        "retry_counters": {"planner": 0, "builder": 0, "verifier": 0, "milestone": 0},
        "updated_at": _utc_now_iso(),
    }, []


def _is_resume_source_issue(message: str) -> bool:
    return (
        "No spawn task_input_artifact_ref found in session log." in message
        or message.startswith("Resume source task_input not found:")
    )


def build_remediation_plan(
    repo_root: str,
    replay_report_path: str,
    session_log_path: Optional[str] = None,
    emit_session_state_path: Optional[str] = None,
    emit_task_input_path: Optional[str] = None,
    missing_resume_source_policy: str = "hard",
) -> Tuple[Dict[str, Any], List[str]]:
    report = _load_json(replay_report_path)
    actions = _create_actions_from_replay_report(report)

    errors: List[str] = []
    warnings: List[str] = []
    resume_task_input: Optional[Dict[str, Any]] = None
    resume_task_input_ref: Optional[str] = None

    if missing_resume_source_policy not in {"soft", "hard"}:
        errors.append(
            f"invalid missing_resume_source_policy '{missing_resume_source_policy}' (expected 'soft' or 'hard')"
        )

    if session_log_path and emit_task_input_path:
        resume_task_input, prep_errors = _prepare_resume_task_input(repo_root, session_log_path, report)
        for issue in prep_errors:
            if _is_resume_source_issue(issue) and missing_resume_source_policy == "soft":
                warnings.append(issue)
            else:
                errors.append(issue)
        if resume_task_input:
            out_abs = os.path.abspath(emit_task_input_path)
            os.makedirs(os.path.dirname(out_abs), exist_ok=True)
            with open(out_abs, "w", encoding="utf-8") as f:
                json.dump(resume_task_input, f, indent=2)
            validation_errors = validate_runtime_file(repo_root, out_abs, "task_input")
            if validation_errors:
                errors.extend(validation_errors)
            else:
                resume_task_input_ref = out_abs

    session_state_payload: Optional[Dict[str, Any]] = None
    if emit_session_state_path:
        session_state_payload, lineage_errors = _prepare_session_state(report, resume_task_input_ref)
        if lineage_errors:
            errors.extend(lineage_errors)
        elif session_state_payload:
            out_abs = os.path.abspath(emit_session_state_path)
            os.makedirs(os.path.dirname(out_abs), exist_ok=True)
            with open(out_abs, "w", encoding="utf-8") as f:
                json.dump(session_state_payload, f, indent=2)
            validation_errors = validate_runtime_file(repo_root, out_abs, "session_state")
            if validation_errors:
                errors.extend(validation_errors)

    plan: Dict[str, Any] = {
        "status": "needs_attention" if errors else ("ready_with_warnings" if warnings else "ready"),
        "generated_at": _utc_now_iso(),
        "source_replay_report": os.path.abspath(replay_report_path),
        "source_session_log": os.path.abspath(session_log_path) if session_log_path else None,
        "missing_resume_source_policy": missing_resume_source_policy,
        "actions": actions,
        "warnings": warnings,
        "resume_outputs": {
            "session_state_path": os.path.abspath(emit_session_state_path) if emit_session_state_path else None,
            "task_input_path": os.path.abspath(emit_task_input_path) if emit_task_input_path else None,
        },
    }
    if session_state_payload is not None:
        plan["resume_preview"] = session_state_payload

    return plan, errors
