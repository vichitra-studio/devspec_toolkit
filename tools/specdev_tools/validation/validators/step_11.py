from __future__ import annotations

import json
import os
from typing import Any

from ...core.trace_types import normalize_trace_type


def validate_step_11(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    """Validate Step 11 (Red Team / Threat Modeling) logic.

    Checks threat_id uniqueness, target ID cross-references against steps 02/05,
    and mitigation constraints.
    """
    errors: list[str] = []
    allowed_target_types = {"api", "component"}
    allowed_mitigation_types = {"fr", "api", "nfr", "invariant", "fixture", "doc", "capability"}
    seen_ids: set[str] = set()

    # Load cross-reference data for target validation
    component_ids = _load_component_ids(toolkit_root)
    api_ids = _load_api_ids(toolkit_root)

    for i, threat in enumerate(instance.get("threats", [])):
        threat_id = threat.get("threat_id")

        # Duplicate ID check
        if threat_id in seen_ids:
            errors.append(f"Duplicate threat_id '{threat_id}' at index {i}")
        seen_ids.add(threat_id)

        # Target validation
        if not threat.get("target_ids"):
            errors.append(f"Threat '{threat_id}' has no target_ids")
        for target in threat.get("target_ids", []):
            t = normalize_trace_type(target.get("type", ""))
            if t and t not in allowed_target_types:
                errors.append(f"Threat '{threat_id}' has invalid target type '{t}'")

            # Cross-ref validation against steps 02 (components) and 05 (APIs)
            target_id = target.get("id", "")
            if t == "component" and component_ids is not None and target_id:
                if target_id not in component_ids:
                    errors.append(
                        f"Threat '{threat_id}' references unknown component '{target_id}' "
                        "(not in 02_system_sketch.json)"
                    )
            elif t == "api" and api_ids is not None and target_id:
                if target_id not in api_ids:
                    errors.append(
                        f"Threat '{threat_id}' references unknown API '{target_id}' "
                        "(not in 05_interface_contracts.json)"
                    )

        # Mitigation validation
        mitigations = threat.get("mitigations", [])
        if not mitigations:
            errors.append(f"Threat '{threat_id}' has no mitigations")
        for mitigation in mitigations:
            if not isinstance(mitigation, dict):
                errors.append(f"Threat '{threat_id}' has non-object mitigation: {mitigation!r}")
                continue
            t = normalize_trace_type(mitigation.get("type", ""))
            if t and t not in allowed_mitigation_types:
                errors.append(f"Threat '{threat_id}' has invalid mitigation type '{t}'")

            # Evidence field: mitigations should have a description or ref
            if not mitigation.get("description") and not mitigation.get("ref"):
                errors.append(
                    f"Threat '{threat_id}' has mitigation without description or ref"
                )

    return errors


def _load_component_ids(toolkit_root: str) -> set[str] | None:
    """Load component IDs from step 02 if available."""
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None
    for fn in os.listdir(spec_dir):
        if fn.startswith("02_") and fn.endswith(".json") and not fn.startswith("02a_"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    c.get("component_id")
                    for c in data.get("components", [])
                    if isinstance(c, dict) and c.get("component_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None


def _load_api_ids(toolkit_root: str) -> set[str] | None:
    """Load API IDs from step 05 if available."""
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None
    for fn in os.listdir(spec_dir):
        if fn.startswith("05_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                apis = data.get("apis", data.get("endpoints", []))
                return {
                    a.get("api_id", a.get("endpoint_id", ""))
                    for a in apis
                    if isinstance(a, dict)
                } - {""}
            except (OSError, json.JSONDecodeError):
                pass
    return None
