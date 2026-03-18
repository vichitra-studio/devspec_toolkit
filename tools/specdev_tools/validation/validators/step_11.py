from __future__ import annotations

import json
import os
import warnings
from typing import Any

from ...core.errors import make_error, SpecError
from ...core.trace_types import is_valid_trace_type, normalize_trace_type
from ...validation.linter_utils import check_no_duplicates

# ---------------------------------------------------------------------------
# Business-rule trace-type sets
# ---------------------------------------------------------------------------

# Business rule: threats can only target APIs or components.
# Rationale: attack surfaces are runtime artifacts (endpoints, services,
# modules) -- not requirements (FRs, NFRs) or test artefacts (fixtures).
_ALLOWED_THREAT_TARGET_TYPES: frozenset[str] = frozenset({"api", "component"})

# Business rule: mitigations reference requirement-level or documentation
# artifacts that *prove* a threat is addressed.
# Rationale: a mitigation can cite an FR (feature guards the path), an API
# (endpoint enforces auth), an NFR (latency SLA limits blast radius), an
# invariant (system-wide rule), a fixture (regression test), a doc (runbook
# or ADR), or a capability (high-level feature that covers the risk).
# Threats themselves are never mitigations (circular), nor are components
# (components are targets, not evidence).
_ALLOWED_MITIGATION_TYPES: frozenset[str] = frozenset({
    "fr", "api", "nfr", "invariant", "fixture", "doc", "capability",
})

# Deferred validation: checks are performed once on first call to
# validate_step_11(), not at import time, to avoid noisy warnings when
# the module is simply imported.
_TRACE_TYPE_VALIDATED: bool = False


def _validate_trace_types_once() -> None:
    """Validate business-rule trace-type sets once per process."""
    global _TRACE_TYPE_VALIDATED
    if _TRACE_TYPE_VALIDATED:
        return
    _TRACE_TYPE_VALIDATED = True

    invalid_targets = {t for t in _ALLOWED_THREAT_TARGET_TYPES if not is_valid_trace_type(t)}
    if invalid_targets:
        warnings.warn(
            f"step_11: _ALLOWED_THREAT_TARGET_TYPES contains unknown canon trace types: {invalid_targets}",
            stacklevel=2,
        )

    invalid_mitigations = {t for t in _ALLOWED_MITIGATION_TYPES if not is_valid_trace_type(t)}
    if invalid_mitigations:
        warnings.warn(
            f"step_11: _ALLOWED_MITIGATION_TYPES contains unknown canon trace types: {invalid_mitigations}",
            stacklevel=2,
        )


def validate_step_11(instance: dict[str, Any], toolkit_root: str) -> list[SpecError]:
    """Validate Step 11 (Red Team / Threat Modeling) logic.

    Checks threat_id uniqueness, target ID cross-references against steps 02/05,
    and mitigation constraints.
    """
    _validate_trace_types_once()
    errors: list[SpecError] = []

    check_no_duplicates(instance.get("threats", []), "threat_id", "threat_id", errors)

    # Load cross-reference data for target validation
    component_ids = _load_component_ids(toolkit_root)
    api_ids = _load_api_ids(toolkit_root)

    for threat in instance.get("threats", []):
        threat_id = threat.get("threat_id")

        # Target validation
        if not threat.get("target_ids"):
            errors.append(make_error("E520", f"Threat '{threat_id}' has no target_ids"))
        for target in threat.get("target_ids", []):
            t = normalize_trace_type(target.get("type", ""))
            if t and t not in _ALLOWED_THREAT_TARGET_TYPES:
                errors.append(make_error("E530", f"Threat '{threat_id}' has invalid target type '{t}'"))

            # Cross-ref validation against steps 02 (components) and 05 (APIs).
            # NOTE: these individual comparisons route to different validation
            # pools and must stay in sync with _ALLOWED_THREAT_TARGET_TYPES.
            target_id = target.get("id", "")
            if t == "component" and component_ids is not None and target_id:
                if target_id not in component_ids:
                    errors.append(
                        make_error("E590", f"Threat '{threat_id}' references unknown component '{target_id}' "
                        "(not in 02_system_sketch.json)")
                    )
            elif t == "api" and api_ids is not None and target_id:
                if target_id not in api_ids:
                    errors.append(
                        make_error("E590", f"Threat '{threat_id}' references unknown API '{target_id}' "
                        "(not in 05_interface_contracts.json)")
                    )

        # Mitigation validation
        mitigations = threat.get("mitigations", [])
        if not mitigations:
            errors.append(make_error("E520", f"Threat '{threat_id}' has no mitigations"))
        for mitigation in mitigations:
            if not isinstance(mitigation, dict):
                errors.append(make_error("E520", f"Threat '{threat_id}' has non-object mitigation: {mitigation!r}"))
                continue
            t = normalize_trace_type(mitigation.get("type", ""))
            if t and t not in _ALLOWED_MITIGATION_TYPES:
                errors.append(make_error("E530", f"Threat '{threat_id}' has invalid mitigation type '{t}'"))

            # Evidence field: mitigations should have a description or ref
            if not mitigation.get("description") and not mitigation.get("ref"):
                errors.append(
                    make_error("E520", f"Threat '{threat_id}' has mitigation without description or ref")
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
                ids: set[str] = {
                    c["component_id"]
                    for c in data.get("components", [])
                    if isinstance(c, dict) and isinstance(c.get("component_id"), str)
                }
                return ids
            except (OSError, json.JSONDecodeError):
                pass
    return None


def _load_api_ids(toolkit_root: str) -> set[str] | None:
    """Load API IDs from step 05 if available.

    This loader is intentionally NOT migrated to the shared ``load_upstream_ids()``
    helper (AUDIT-003).  Step 05 artifacts historically use two different schema
    shapes — ``apis[].api_id`` (current) and ``endpoints[].endpoint_id`` (legacy) —
    and this function falls back across both array keys AND both id fields.  The
    shared ``load_upstream_ids()`` supports ``fallback_keys`` for alternate array
    names but always extracts the same ``id_field``, so it cannot express the
    ``api_id`` → ``endpoint_id`` field fallback needed here.
    """
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
