from __future__ import annotations

import json
import os
from typing import Any

from ...core.errors import make_error, SpecError
from ...core.scope_helpers import is_parked

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

def check_external_trust_boundaries(connections: list[dict], third_party_ids: set[str]) -> list[SpecError]:
    """A connection to a third party declared in this file must not be ``internal``."""
    errors: list[SpecError] = []
    for idx, conn in enumerate(connections):
        targets = conn.get("connects_to") or []
        if conn.get("trust_boundary") == "internal" and third_party_ids.intersection(targets):
            errors.append(
                make_error("E520", f"Connection[{idx}] connects to a third party but trust_boundary is internal")
            )
    return errors


def check_capability_coverage(components: list[dict], capabilities: dict[str, dict]) -> list[SpecError]:
    """Every capability that is not parked must be named in some component's ``derives_from``."""
    covered = {ref for comp in components for ref in comp.get("derives_from") or []}
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


def _load_capabilities(repo_root: str, spec_root: str | None) -> dict[str, dict]:
    """Read the Step 01 artifact and return its capabilities keyed by ``capability_id``.

    Searches *spec_root* (when given), then ``<repo_root>/spec``. A missing or
    unreadable file yields an empty mapping: no coverage data, no error.
    """
    search_dirs = [d for d in (spec_root, os.path.join(repo_root, "spec")) if d]
    for directory in search_dirs:
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if name.startswith("01_") and name.endswith(".json"):
                return _read_capabilities(os.path.join(directory, name))
    return {}


def _read_capabilities(path: str) -> dict[str, dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            data: Any = json.load(fh)
    except (OSError, ValueError):
        return {}
    items = data.get("capabilities") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return {}
    return {c["capability_id"]: c for c in items if isinstance(c, dict) and isinstance(c.get("capability_id"), str)}


def validate_step_02(instance: dict, repo_root: str, spec_root: str | None = None) -> list[SpecError]:
    """
    Deep validation logic for Step 02 (System Sketch).

    Schema validation is handled by the orchestrator (validate.py) before
    this function is called.  This function performs deep logic checks.
    Capability coverage reads the Step 01 artifact from *spec_root* or
    ``<repo_root>/spec``; without it the coverage check is skipped.
    """
    errors: list[SpecError] = []

    components = instance.get("components", [])
    connections = instance.get("connections", [])
    third_party_ids = {tp["third_party_id"] for tp in instance.get("third_parties", []) if tp.get("third_party_id")}

    errors.extend(check_component_ids(components))
    errors.extend(check_rate_limits(connections))
    errors.extend(check_partner_public_rate_limit(connections))
    errors.extend(check_external_trust_boundaries(connections, third_party_ids))

    capabilities = _load_capabilities(repo_root, spec_root)
    if capabilities:
        errors.extend(check_capability_coverage(components, capabilities))

    return errors
