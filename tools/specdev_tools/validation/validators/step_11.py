from __future__ import annotations

from typing import Any

from ...core.trace_types import normalize_trace_type


def validate_step_11(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    allowed_target_types = {"api", "component"}
    allowed_mitigation_types = {"fr", "api", "nfr", "invariant", "fixture", "doc", "capability"}
    seen_ids: set[str] = set()
    for i, threat in enumerate(instance.get("threats", [])):
        threat_id = threat.get("threat_id")
        if threat_id in seen_ids:
            errors.append(f"Duplicate threat_id '{threat_id}' at index {i}")
        seen_ids.add(threat_id)
        if not threat.get("target_ids"):
            errors.append(f"Threat '{threat_id}' has no target_ids")
        for target in threat.get("target_ids", []):
            t = normalize_trace_type(target.get("type", ""))
            if t and t not in allowed_target_types:
                errors.append(f"Threat '{threat_id}' has invalid target type '{t}'")
        for mitigation in threat.get("mitigations", []):
            t = normalize_trace_type(mitigation.get("type", ""))
            if t and t not in allowed_mitigation_types:
                errors.append(f"Threat '{threat_id}' has invalid mitigation type '{t}'")
    return errors
