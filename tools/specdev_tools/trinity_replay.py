from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from .trinity_runtime_validate import validate_runtime_file


def _normalize_hash(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.startswith("sha256:"):
        raw = raw[len("sha256:") :]
    if len(raw) != 64:
        return None
    try:
        int(raw, 16)
    except ValueError:
        return None
    return raw.lower()


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _sha256_canonical_json(path: str) -> Optional[str]:
    try:
        payload = json.load(open(path, "r", encoding="utf-8"))
    except Exception:
        return None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_ref(session_log_path: str, repo_root: str, ref: str) -> str:
    if os.path.isabs(ref):
        return ref
    local = os.path.abspath(os.path.join(os.path.dirname(session_log_path), ref))
    if os.path.exists(local):
        return local
    return os.path.abspath(os.path.join(repo_root, ref))


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


def replay_session(repo_root: str, session_log_path: str, strict: bool = True) -> Dict[str, Any]:
    """
    Standalone replay analyzer for a validated Trinity session log.
    Verifies artifact/hash lineage and reconstructs timeline summary.
    """
    report: Dict[str, Any] = {
        "status": "ok",
        "strict": strict,
        "session_log": os.path.abspath(session_log_path),
        "errors": [],
        "warnings": [],
        "summary": {},
        "timeline": [],
        "artifact_verification": {
            "checked": 0,
            "matched": 0,
            "missing": 0,
            "mismatch": 0,
        },
    }

    runtime_errors = validate_runtime_file(repo_root, session_log_path, "session_event")
    if runtime_errors:
        report["status"] = "failed"
        report["errors"].extend(runtime_errors)
        return report

    events, parse_errors = _load_session_events(session_log_path)
    if parse_errors:
        report["status"] = "failed"
        report["errors"].extend(parse_errors)
        return report

    event_type_counts: Dict[str, int] = {}
    role_counts: Dict[str, int] = {}
    phase_sequence: List[str] = []
    step_ids: List[str] = []
    agents: Dict[str, Dict[str, Any]] = {}
    lineage_edges: set[Tuple[str, str]] = set()

    for event in events:
        event_type = event.get("event_type", "UNKNOWN")
        role = event.get("role", "UNKNOWN")
        phase = event.get("phase_id")
        step_id = event.get("step_id")
        agent_id = event.get("agent_id")
        parent_id = event.get("parent_id")

        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        role_counts[role] = role_counts.get(role, 0) + 1
        if isinstance(phase, str) and phase and (not phase_sequence or phase_sequence[-1] != phase):
            phase_sequence.append(phase)
        if isinstance(step_id, str) and step_id and step_id not in step_ids:
            step_ids.append(step_id)

        if isinstance(agent_id, str) and agent_id:
            seq = event.get("event_sequence")
            state = agents.setdefault(
                agent_id,
                {
                    "role": role,
                    "parent_id": parent_id,
                    "first_sequence": seq,
                    "last_sequence": seq,
                    "last_event_type": event_type,
                },
            )
            state["last_sequence"] = seq
            state["last_event_type"] = event_type
            if isinstance(parent_id, str) and parent_id:
                lineage_edges.add((parent_id, agent_id))

        summary_text = None
        content = event.get("content", {}) if isinstance(event.get("content"), dict) else {}
        if isinstance(content.get("summary"), str):
            summary_text = content.get("summary")
        report["timeline"].append(
            {
                "event_sequence": event.get("event_sequence"),
                "event_id": event.get("event_id"),
                "event_type": event_type,
                "agent_id": agent_id,
                "parent_id": parent_id,
                "phase_id": phase,
                "step_id": step_id,
                "summary": summary_text,
            }
        )

        artifact_checks: List[Tuple[str, Any, str, str]] = []
        artifact_ref = event.get("artifact_ref")
        artifact_sha = event.get("artifact_sha256")
        if isinstance(artifact_ref, str) and artifact_ref and artifact_sha is not None:
            artifact_checks.append(("artifact_ref", artifact_ref, artifact_sha, "file"))

        if isinstance(content, dict):
            prompt_ref = content.get("prompt_artifact_ref")
            prompt_sha = content.get("prompt_sha256")
            if isinstance(prompt_ref, str) and prompt_ref and prompt_sha is not None:
                artifact_checks.append(("prompt_artifact_ref", prompt_ref, prompt_sha, "file"))

            response_ref = content.get("response_artifact_ref")
            response_sha = content.get("response_sha256")
            if isinstance(response_ref, str) and response_ref and response_sha is not None:
                artifact_checks.append(("response_artifact_ref", response_ref, response_sha, "file"))

        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        policy_ref = metadata.get("capture_policy_ref")
        policy_sha = metadata.get("capture_policy_sha256")
        if isinstance(policy_ref, str) and policy_ref and policy_sha is not None:
            artifact_checks.append(("capture_policy_ref", policy_ref, policy_sha, "json_canonical"))

        for label, ref, expected_sha_raw, mode in artifact_checks:
            expected_sha = _normalize_hash(expected_sha_raw)
            if expected_sha is None:
                report["warnings"].append(
                    f"{session_log_path}: event {event.get('event_id')} has invalid hash format for {label}"
                )
                continue

            report["artifact_verification"]["checked"] += 1
            resolved = _resolve_ref(session_log_path, repo_root, ref)
            if not os.path.exists(resolved):
                report["artifact_verification"]["missing"] += 1
                report["warnings"].append(
                    f"{session_log_path}: event {event.get('event_id')} missing {label} artifact: {ref}"
                )
                continue

            if mode == "json_canonical":
                actual_sha = _sha256_canonical_json(resolved)
                if actual_sha is None:
                    report["artifact_verification"]["mismatch"] += 1
                    report["warnings"].append(
                        f"{session_log_path}: event {event.get('event_id')} {label} is not valid JSON: {ref}"
                    )
                    continue
            else:
                actual_sha = _sha256_file(resolved)

            if actual_sha != expected_sha:
                report["artifact_verification"]["mismatch"] += 1
                report["warnings"].append(
                    f"{session_log_path}: event {event.get('event_id')} hash mismatch for {label}: {ref}"
                )
            else:
                report["artifact_verification"]["matched"] += 1

    report["summary"] = {
        "run_id": events[0].get("run_id") if events else None,
        "total_events": len(events),
        "event_type_counts": event_type_counts,
        "role_counts": role_counts,
        "phase_sequence": phase_sequence,
        "step_ids": step_ids,
        "agents": agents,
        "lineage_edges": sorted([{"parent_id": p, "agent_id": a} for p, a in lineage_edges], key=lambda x: (x["parent_id"], x["agent_id"])),
    }

    if strict and report["warnings"]:
        report["status"] = "failed"
        report["errors"].append("Strict replay failed due to warnings.")
    elif report["warnings"]:
        report["status"] = "warnings"
    else:
        report["status"] = "ok"

    return report
