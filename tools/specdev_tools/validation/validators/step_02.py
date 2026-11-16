from __future__ import annotations

from ...core.errors import make_error, SpecError
from ...core.loaders import load_sibling_json
from ...core.scope_helpers import dict_items, is_parked

def check_component_ids(components: list[dict]) -> list[SpecError]:
    errors: list[SpecError] = []
    seen = set()
    for comp in components:
        comp_id = comp.get("component_id")
        if not isinstance(comp_id, str) or not comp_id:
            continue
        if comp_id in seen:
            errors.append(make_error("E520", f"Duplicate component_id: {comp_id}"))
        seen.add(comp_id)
    return errors

def check_rate_limits(connections: list[dict]) -> list[SpecError]:
    errors: list[SpecError] = []
    for idx, conn in enumerate(connections):
        rate_limit = conn.get("rate_limit")
        if not isinstance(rate_limit, dict):
            continue
        rps = rate_limit.get("rps")
        burst = rate_limit.get("burst")
        if isinstance(burst, (int, float)) and isinstance(rps, (int, float)) and burst < rps:
            errors.append(
                make_error("E520", f"Connection[{idx}] rate_limit burst {burst} is less than rps {rps}")
            )
    return errors

def check_external_trust_boundaries(connections: list[dict], third_party_ids: set[str]) -> list[SpecError]:
    """A connection to a third party declared in this file must not be ``internal``."""
    errors: list[SpecError] = []
    for idx, conn in enumerate(connections):
        targets = conn.get("connects_to")
        if not isinstance(targets, list):
            targets = []
        if conn.get("trust_boundary") == "internal" and any(
            t in third_party_ids for t in targets if isinstance(t, str)
        ):
            errors.append(
                make_error("E520", f"Connection[{idx}] connects to a third party but trust_boundary is internal")
            )
    return errors


def check_capability_coverage(components: list[dict], capabilities: dict[str, dict]) -> list[SpecError]:
    """Every capability that is not parked must be named in some component's ``derives_from``."""
    covered: set[str] = set()
    for comp in components:
        refs = comp.get("derives_from")
        if isinstance(refs, list):
            covered.update(ref for ref in refs if isinstance(ref, str))
    missing = sorted(cap_id for cap_id, cap in capabilities.items() if cap_id not in covered and not is_parked(cap))
    if missing:
        return [make_error("E590", f"Missing capability coverage: {', '.join(missing)}")]
    return []


def check_partner_public_rate_limit(connections: list[dict]) -> list[SpecError]:
    """Check that partner/public trust boundary connections have a rate_limit defined."""
    errors: list[SpecError] = []
    for idx, conn in enumerate(connections):
        if conn.get("trust_boundary") in ("partner", "public") and "rate_limit" not in conn:
            errors.append(
                make_error("E520", f"Connection[{idx}] trust_boundary is '{conn['trust_boundary']}' but rate_limit is missing")
            )
    return errors


def _load_capabilities(repo_root: str, spec_root: str | None, artifact_path: str | None = None) -> dict[str, dict]:
    """Read the Step 01 artifact and return its capabilities keyed by ``capability_id``.

    The lookup is ``core.loaders.load_sibling_json`` (artifact directory, then
    *spec_root*, then ``<repo_root>/spec``; first candidate that parses as an
    object). No such file yields an empty mapping: no coverage data, no error.
    """
    data = load_sibling_json(artifact_path, "01", spec_root=spec_root, fallback_root=repo_root)
    return _capabilities_of(data) if data is not None else {}


def _capabilities_of(data: dict) -> dict[str, dict]:
    items = data.get("capabilities")
    if not isinstance(items, list):
        return {}
    return {c["capability_id"]: c for c in items if isinstance(c, dict) and isinstance(c.get("capability_id"), str)}


def validate_step_02(
    instance: dict, repo_root: str, spec_root: str | None = None, artifact_path: str | None = None
) -> list[SpecError]:
    """
    Deep validation logic for Step 02 (System Sketch).

    Schema validation is handled by the orchestrator (validate.py) before
    this function is called.  This function performs deep logic checks.
    Capability coverage reads the Step 01 artifact from the artifact's own
    directory, *spec_root* or ``<repo_root>/spec``; without it the coverage check is skipped.
    """
    errors: list[SpecError] = []

    components = dict_items(instance.get("components"))
    connections = dict_items(instance.get("connections"))
    third_parties = instance.get("third_parties")
    third_party_ids = {
        tp["third_party_id"]
        for tp in (third_parties if isinstance(third_parties, list) else [])
        if isinstance(tp, dict) and isinstance(tp.get("third_party_id"), str) and tp["third_party_id"]
    }

    errors.extend(check_component_ids(components))
    errors.extend(check_rate_limits(connections))
    errors.extend(check_partner_public_rate_limit(connections))
    errors.extend(check_external_trust_boundaries(connections, third_party_ids))

    capabilities = _load_capabilities(repo_root, spec_root, artifact_path)
    if capabilities:
        errors.extend(check_capability_coverage(components, capabilities))

    return errors
