from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
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
    mitigation ID cross-references against upstream spec steps (01/04/05/06/07/08),
    mitigation constraints, API-to-threat coverage (W583), and invariant coverage (W615).
    """
    _validate_trace_types_once()
    errors: list[SpecError] = []

    check_no_duplicates(instance.get("threats", []), "threat_id", "threat_id", errors)

    # Load cross-reference data for target validation (steps 02, 05)
    component_ids = _load_component_ids(toolkit_root, artifact_path)
    api_ids = _load_api_ids(toolkit_root, artifact_path)

    # Load cross-reference data for mitigation validation (steps 01, 04, 06, 07, 08)
    # Each loader returns None (upstream absent → skip check) or a set[str].
    invariant_ids = _load_invariant_ids(toolkit_root, artifact_path)
    fr_ids = _load_fr_ids(toolkit_root, artifact_path)
    nfr_ids = _load_nfr_ids(toolkit_root, artifact_path)
    fixture_ids = _load_fixture_ids(toolkit_root, artifact_path)
    capability_ids = _load_capability_ids(toolkit_root, artifact_path)

    # Mapping from normalised mitigation type to the loaded ID set.
    # "doc" is intentionally absent — there is no doc-ID registry in the toolkit,
    # so doc mitigations are exempt from cross-ref validation.
    # A .get() on a missing key returns None, which triggers the "skip" guard below.
    _mitigation_id_sets: dict[str, set[str] | None] = {
        "invariant": invariant_ids,
        "fr": fr_ids,
        "nfr": nfr_ids,
        "fixture": fixture_ids,
        "capability": capability_ids,
        "api": api_ids,
    }

    # Collect the invariant IDs that have a risk_category_ref (security-relevant)
    # for the W615 coverage check.  Derived from step-06 full objects, not just IDs.
    security_invariant_ids: set[str] = _load_security_invariant_ids(toolkit_root, artifact_path)

    for i, threat in enumerate(instance.get("threats", [])):
        if not isinstance(threat, dict):
            errors.append(make_error("E520", f"threats[{i}] is not an object: {threat!r}"))
            continue
        threat_id = threat.get("threat_id")

        # Target validation
        if not threat.get("target_ids"):
            errors.append(make_error("E520", f"Threat '{threat_id}' has no target_ids"))
        for j, target in enumerate(threat.get("target_ids", [])):
            if not isinstance(target, dict):
                errors.append(make_error("E520", f"Threat '{threat_id}' target_ids[{j}] is not an object: {target!r}"))
                continue
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
            mid = mitigation.get("id", "")
            if not mid:
                errors.append(
                    make_error("E520", f"Threat '{threat_id}' has mitigation missing required 'id'")
                )

            # Cross-ref validation: check the mitigation ID against its source spec.
            # Uses the same is-not-None guard as target cross-ref — absent upstream
            # file → skip silently (None), present but id not found → E590.
            # "doc" mitigations are exempt: there is no doc-ID registry in the toolkit.
            if t and mid:
                id_set = _mitigation_id_sets.get(t)
                if id_set is not None and mid not in id_set:
                    errors.append(
                        make_error(
                            "E590",
                            f"Threat '{threat_id}' mitigation type '{mitigation.get('type')}' "
                            f"references unknown id '{mid}' (not found in upstream step for type '{t}')",
                        )
                    )

    # W583: API-to-threat coverage — each public API should be targeted by at
    # least one threat.  Only fires when step 05 is present (api_ids is not None).
    if api_ids is not None:
        threatened_api_ids: set[str] = set()
        for threat in instance.get("threats", []):
            if not isinstance(threat, dict):
                continue
            for target in threat.get("target_ids", []):
                if not isinstance(target, dict):
                    continue
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

    # W615: Invariant coverage — each step-06 invariant with a risk_category_ref
    # should be referenced by at least one threat's mitigation of type 'inv'.
    # Only fires when step 06 is present (invariant_ids is not None).
    # Firing condition: invariant has risk_category_ref AND no threat mitigation
    # of normalised type 'invariant' references it.
    if invariant_ids is not None and security_invariant_ids:
        mitigated_invariant_ids: set[str] = set()
        for threat in instance.get("threats", []):
            if not isinstance(threat, dict):
                continue
            for mitigation in threat.get("mitigations", []):
                if not isinstance(mitigation, dict):
                    continue
                t = normalize_trace_type(mitigation.get("type", ""))
                if t == "invariant":
                    mid = mitigation.get("id", "")
                    if mid:
                        mitigated_invariant_ids.add(mid)
        for inv_id in sorted(security_invariant_ids):
            if inv_id not in mitigated_invariant_ids:
                errors.append(
                    make_error(
                        "W615",
                        f"INVARIANT_UNEXERCISED_BY_THREAT {inv_id} has a risk_category_ref "
                        "but no threat mitigation references it",
                    )
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


def _load_invariant_ids(toolkit_root: str, artifact_path: str | None = None) -> set[str] | None:
    """Load invariant IDs from step 06 if available.

    Returns None when the upstream file is absent (skip cross-ref check),
    or a set[str] of inv_id values (possibly empty when the file has no rules).
    """
    return load_sibling_artifact(
        artifact_path or "",
        "06",
        "rules",
        "inv_id",
        fallback_root=toolkit_root,
    )


def _load_fr_ids(toolkit_root: str, artifact_path: str | None = None) -> set[str] | None:
    """Load functional requirement IDs from step 04 if available."""
    return load_sibling_artifact(
        artifact_path or "",
        "04",
        "functional_requirements",
        "fr_id",
        fallback_root=toolkit_root,
    )


def _load_nfr_ids(toolkit_root: str, artifact_path: str | None = None) -> set[str] | None:
    """Load NFR IDs from step 07 if available."""
    return load_sibling_artifact(
        artifact_path or "",
        "07",
        "nfrs",
        "nfr_id",
        fallback_root=toolkit_root,
    )


def _load_fixture_ids(toolkit_root: str, artifact_path: str | None = None) -> set[str] | None:
    """Load fixture IDs from step 08 if available."""
    return load_sibling_artifact(
        artifact_path or "",
        "08",
        "fixtures",
        "fixture_id",
        fallback_root=toolkit_root,
    )


def _load_capability_ids(toolkit_root: str, artifact_path: str | None = None) -> set[str] | None:
    """Load capability IDs from step 01 if available."""
    return load_sibling_artifact(
        artifact_path or "",
        "01",
        "capabilities",
        "capability_id",
        fallback_root=toolkit_root,
    )


def _load_security_invariant_ids(
    toolkit_root: str, artifact_path: str | None = None
) -> set[str]:
    """Load the set of step-06 inv_ids that carry a non-empty risk_category_ref.

    These are the "security-relevant" invariants that W615 checks against.
    Shares the same sibling-first / fallback-to-toolkit resolution path as
    ``_load_invariant_ids`` so both sets are always derived from the same file.

    Returns an empty set when step 06 is absent or contains no such invariants.
    """
    candidates: list[Path] = []
    if artifact_path:
        artifact_dir = Path(artifact_path).resolve().parent
        for fn in _iter_step_files(artifact_dir, "06"):
            candidates.append(artifact_dir / fn)
    fallback_spec = Path(toolkit_root).resolve() / "spec"
    for fn in _iter_step_files(fallback_spec, "06"):
        candidates.append(fallback_spec / fn)

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            with candidate.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return set()
        result: set[str] = set()
        for rule in data.get("rules", []):
            if not isinstance(rule, dict):
                continue
            inv_id = rule.get("inv_id")
            if inv_id and rule.get("risk_category_ref"):
                result.add(str(inv_id))
        return result

    return set()


def _iter_step_files(directory: Path, prefix: str) -> list[str]:
    """Return filenames in *directory* matching ``<prefix>_*.json``."""
    if not directory.is_dir():
        return []
    return [
        fn for fn in os.listdir(str(directory))
        if fn.startswith(f"{prefix}_") and fn.endswith(".json")
    ]
