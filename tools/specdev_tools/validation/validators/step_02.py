import warnings
from typing import Optional, Set
from ...core.errors import make_error, SpecError
from ...core.trace_types import is_valid_trace_type, normalize_trace_type

def check_component_ids(components: list[dict]) -> list[SpecError]:
    errors: list[SpecError] = []
    seen = set()
    for comp in components:
        comp_id = comp.get("component_id")
        if not comp_id:
            continue
        if comp_id in seen:
            errors.append(make_error("E520", f"Duplicate component_id: {comp_id}"))
        seen.add(comp_id)
    return errors

def check_connection_integrity(connections: list[dict], component_ids: set[str]) -> list[SpecError]:
    errors: list[SpecError] = []
    for idx, conn in enumerate(connections):
        source = conn.get("from")
        target = conn.get("to")
        if source and source not in component_ids:
            errors.append(make_error("E590", f"Connection[{idx}] from '{source}' not found in components"))
        if target and target not in component_ids:
            errors.append(make_error("E590", f"Connection[{idx}] to '{target}' not found in components"))
    return errors

def check_rate_limits(connections: list[dict]) -> list[SpecError]:
    errors: list[SpecError] = []
    for idx, conn in enumerate(connections):
        rate_limit = conn.get("rate_limit")
        if not isinstance(rate_limit, dict):
            continue
        rps = rate_limit.get("rps")
        burst = rate_limit.get("burst")
        if burst is not None and rps is not None and burst < rps:
            errors.append(
                make_error("E520", f"Connection[{idx}] rate_limit burst {burst} is less than rps {rps}")
            )
    return errors

def check_external_trust_boundaries(components: list[dict], connections: list[dict]) -> list[SpecError]:
    errors: list[SpecError] = []
    external_ids = {
        comp.get("component_id")
        for comp in components
        if comp.get("component_id") and comp.get("type") == "external"
    }
    if not external_ids:
        return errors
    for idx, conn in enumerate(connections):
        source = conn.get("from")
        target = conn.get("to")
        if source not in external_ids and target not in external_ids:
            continue
        trust_boundary = conn.get("trust_boundary")
        if trust_boundary == "internal":
            errors.append(
                make_error("E520", f"Connection[{idx}] touches external component but trust_boundary is internal")
            )
    return errors

# ---------------------------------------------------------------------------
# Business-rule trace-type constant
# ---------------------------------------------------------------------------

# Business rule: component capability coverage accepts "doc" and "capability"
# trace types.
# Rationale: when a system-sketch component (Step 02) traces to a capability
# ID (from Step 01), it may use type "doc" (legacy convention: the component
# *documents* the capability) or type "capability" (explicit trace).  Both
# are accepted for backwards compatibility.  Mirrors the identical constant
# in cross_artifact_checks.py so the per-file validator and the matrix check
# agree on what is valid.
_CAPABILITY_COVERAGE_TYPES: frozenset[str] = frozenset({"doc", "capability"})

_invalid_capability_types = {t for t in _CAPABILITY_COVERAGE_TYPES if not is_valid_trace_type(t)}
if _invalid_capability_types:
    warnings.warn(
        f"step_02: _CAPABILITY_COVERAGE_TYPES contains unknown canon trace types: "
        f"{_invalid_capability_types}",
        stacklevel=1,
    )


def check_capability_coverage(components: list[dict], capability_ids: set[str]) -> list[SpecError]:
    if not capability_ids:
        return []
    traced = set()
    errors: list[SpecError] = []
    accepted = sorted(_CAPABILITY_COVERAGE_TYPES)
    for comp in components:
        traces = (comp.get("trace") or []) + (comp.get("trace_refs") or [])
        for trace in traces:
            trace_id = trace.get("id")
            trace_type = normalize_trace_type(trace.get("type", ""))
            if not trace_id:
                continue
            if trace_type in _CAPABILITY_COVERAGE_TYPES:
                traced.add(trace_id)
            elif trace_id in capability_ids:
                errors.append(
                    make_error("E530", f"Capability trace must use one of {accepted}: {trace_id}")
                )
    missing = sorted(capability_ids - traced)
    if missing:
        errors.append(make_error("E590", f"Missing capability coverage: {', '.join(missing)}"))
    return errors

def validate_step_02(
    instance: dict,
    repo_root: str,
    capability_ids: Optional[Set[str]] = None
) -> list[SpecError]:
    """
    Deep validation logic for Step 02 (System Sketch).

    Schema validation is handled by the orchestrator (validate.py) before
    this function is called.  This function performs deep logic checks.
    """
    errors: list[SpecError] = []

    components = instance.get("components", [])
    connections = instance.get("connections", [])
    comp_ids = {comp.get("component_id") for comp in components if comp.get("component_id")}

    errors.extend(check_component_ids(components))
    errors.extend(check_connection_integrity(connections, comp_ids))
    errors.extend(check_rate_limits(connections))
    errors.extend(check_external_trust_boundaries(components, connections))

    if capability_ids:
        errors.extend(check_capability_coverage(components, capability_ids))

    return errors
