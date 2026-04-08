from __future__ import annotations

import warnings
from typing import Any

from ...core.errors import make_error, SpecError
from ...core.loaders import load_sibling_artifact
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


def validate_step_11(
    instance: dict[str, Any],
    toolkit_root: str,
    artifact_path: str | None = None,
) -> list[SpecError]:
    """Validate Step 11 (Red Team / Threat Modeling) logic.

    Checks threat_id uniqueness, target ID cross-references against steps 02/05,
    mitigation constraints, and API-to-threat coverage (W583).
    """
    _validate_trace_types_once()
    errors: list[SpecError] = []

    check_no_duplicates(instance.get("threats", []), "threat_id", "threat_id", errors)

    # Load cross-reference data for target validation
    component_ids = _load_component_ids(toolkit_root, artifact_path)
    api_ids = _load_api_ids(toolkit_root, artifact_path)

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

            # Schema guarantees `type` and `id` are present.  Keep a safety
            # net for the `id` field so fixtures that bypass schema checks
            # still surface a clear error.
            if not mitigation.get("id"):
                errors.append(
                    make_error("E520", f"Threat '{threat_id}' has mitigation missing required 'id'")
                )

    # W583: API-to-threat coverage — each public API should be targeted by at
    # least one threat.  Only fires when step 05 is present (api_ids is not None).
    if api_ids is not None:
        threatened_api_ids: set[str] = set()
        for threat in instance.get("threats", []):
            for target in threat.get("target_ids", []):
                t = normalize_trace_type(target.get("type", ""))
                if t == "api":
                    tid = target.get("id", "")
                    if tid:
                        threatened_api_ids.add(tid)
        for api_id in sorted(api_ids):
            if api_id not in threatened_api_ids:
                errors.append(
                    make_error("W583", f"API_UNCOVERED_BY_THREAT {api_id} has no corresponding threat in Step 11")
                )

    return errors


def _load_component_ids(toolkit_root: str, artifact_path: str | None = None) -> set[str] | None:
    """Load component IDs from step 02 if available.

    Delegates to the shared ``load_sibling_artifact`` helper, which searches
    ``artifact_path``'s sibling directory first and falls back to
    ``<toolkit_root>/spec``.  Returns ``None`` (not an empty set) when no
    upstream file is found — callers use ``None`` as "upstream absent, skip
    cross-ref check" (see the ``component_ids is not None`` guard above).
    """
    return load_sibling_artifact(
        artifact_path or "",
        "02",
        "components",
        "component_id",
        fallback_root=toolkit_root,
    )


def _load_api_ids(toolkit_root: str, artifact_path: str | None = None) -> set[str] | None:
    """Load API IDs from step 05 if available.

    Delegates to ``load_sibling_artifact``, matching ``_load_component_ids``.
    Step 05 schema uses ``apis[].api_id`` exclusively; the legacy
    ``endpoints[].endpoint_id`` shape no longer appears in schema or fixtures.
    """
    return load_sibling_artifact(
        artifact_path or "",
        "05",
        "apis",
        "api_id",
        fallback_root=toolkit_root,
    )
