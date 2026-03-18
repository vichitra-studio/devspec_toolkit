"""Cross-artifact integrity checks extracted from validate_trace_integrity().

Each function accepts the full ``artifacts`` dict (path -> loaded JSON) and
returns a list of error strings.  These are called by
``matrix.validate_trace_integrity()`` after the generic broken-reference
scan, replacing inline step-specific logic that was previously embedded
directly in that function.
"""
from __future__ import annotations

import os
import re
import warnings
from typing import Any

from ..core.errors import SpecError, make_error
from ..core.trace_types import is_valid_trace_type, normalize_trace_type

# ---------------------------------------------------------------------------
# Business-rule trace-type constants for cross-artifact checks
# ---------------------------------------------------------------------------

# Business rule: component capability coverage accepts "doc" and "capability"
# trace types.
# Rationale: when a system-sketch component (Step 02) traces to a capability
# ID (from Step 01), it may use type "doc" (legacy convention: the component
# *documents* the capability) or type "capability" (explicit trace).  Both
# are accepted for backwards compatibility.
_CAPABILITY_COVERAGE_TYPES: frozenset[str] = frozenset({"doc", "capability"})

# Business rule: FR-to-glossary trace type.
# Rationale: an FR may reference glossary terms (Step 03) via type "glossary"
# or by ID prefix "term-".  "glossary" is a domain-specific trace type for
# vocabulary references.
# NOTE: "glossary" was added to canon as cn:core:trace_type:glossary.
_GLOSSARY_TRACE_TYPE: str = "glossary"

# Business rule: FR-to-capability trace type.
# Rationale: FRs (Step 04) reference capabilities (Step 01) to prove they
# are grounded in a user-facing capability.
_CAPABILITY_TRACE_TYPE: str = "capability"

# Validate at definition time
_all_cross_check_types = _CAPABILITY_COVERAGE_TYPES | {_GLOSSARY_TRACE_TYPE, _CAPABILITY_TRACE_TYPE}
_invalid_cross_check_types = {t for t in _all_cross_check_types if not is_valid_trace_type(t)}
if _invalid_cross_check_types:
    warnings.warn(
        f"cross_artifact_checks: business-rule sets contain unknown canon trace types: "
        f"{_invalid_cross_check_types}",
        stacklevel=1,
    )


# ---------------------------------------------------------------------------
# Step 01 helpers -- collect capability IDs for downstream checks
# ---------------------------------------------------------------------------

def collect_capability_ids(artifacts: dict[str, Any]) -> set[str]:
    """Index capability IDs across all Step 01 artifacts."""
    capability_ids: set[str] = set()
    for data in artifacts.values():
        schema = data.get("$schema", "")
        if "01_capabilities" in schema:
            for cap in data.get("capabilities", []):
                if cap.get("capability_id"):
                    capability_ids.add(cap["capability_id"])
    return capability_ids


# ---------------------------------------------------------------------------
# Step 02 -- system sketch integrity
# ---------------------------------------------------------------------------

_SCHEMA_REF_RE = re.compile(r"^(?:-tbd|(file://|https://|glossary:|api:).+)$")


def check_step_02_integrity(
    artifacts: dict[str, Any],
    capability_ids: set[str],
) -> list[SpecError]:
    """Validate system-sketch cross-artifact integrity.

    Checks:
    - Duplicate component IDs
    - Connection endpoint references
    - schema_ref format on connections
    - External component trust-boundary constraints
    - Capability coverage across components
    - External-dependency tag requirement
    """
    errors: list[SpecError] = []

    for path, data in artifacts.items():
        schema = data.get("$schema", "")
        if "02_system_sketch" not in schema:
            continue

        components = data.get("components", [])
        connections = data.get("connections", [])
        basename = os.path.basename(path)

        # Index component IDs and types
        component_ids: list[str] = []
        component_types: dict[str, str | None] = {}
        for comp in components:
            comp_id = comp.get("component_id")
            if comp_id:
                component_ids.append(comp_id)
                component_types[comp_id] = comp.get("type")

        # Duplicate component check
        seen: set[str] = set()
        for comp_id in component_ids:
            if comp_id in seen:
                errors.append(make_error(
                    "E520",
                    f"Step 02 Integrity in {basename}: Duplicate component_id '{comp_id}'.",
                ))
            seen.add(comp_id)

        # Connection endpoint validation
        component_id_set = set(component_ids)
        for idx, conn in enumerate(connections):
            source = conn.get("from")
            target = conn.get("to")
            if source and source not in component_id_set:
                errors.append(make_error(
                    "E590",
                    f"Step 02 Integrity in {basename}: connection[{idx}] from '{source}' not found.",
                ))
            if target and target not in component_id_set:
                errors.append(make_error(
                    "E590",
                    f"Step 02 Integrity in {basename}: connection[{idx}] to '{target}' not found.",
                ))

            # schema_ref format
            schema_ref = conn.get("schema_ref")
            if schema_ref and not _SCHEMA_REF_RE.match(schema_ref):
                errors.append(make_error(
                    "E520",
                    f"Step 02 Integrity in {basename}: connection[{idx}] schema_ref '{schema_ref}' is invalid.",
                ))

            # Trust boundary vs external component
            if (
                (source and component_types.get(source) == "external")
                or (target and component_types.get(target) == "external")
            ):
                trust_boundary = conn.get("trust_boundary")
                if trust_boundary == "internal":
                    errors.append(make_error(
                        "E520",
                        f"Step 02 Integrity in {basename}: connection[{idx}] uses internal trust_boundary with external component.",
                    ))

        # Capability coverage
        if capability_ids:
            traced: set[str] = set()
            for comp in components:
                traces = (comp.get("trace") or []) + (comp.get("trace_refs") or [])
                for trace in traces:
                    trace_id = trace.get("id")
                    trace_type = normalize_trace_type(trace.get("type") or "")
                    if not trace_id:
                        continue
                    if trace_type in _CAPABILITY_COVERAGE_TYPES:
                        traced.add(trace_id)
                    elif trace_id in capability_ids:
                        errors.append(make_error(
                            "E520",
                            f"Step 02 Integrity in {basename}: Capability trace_refs must use type 'doc' or 'capability' for '{trace_id}'.",
                        ))
            missing = sorted(capability_ids - traced)
            if missing:
                errors.append(make_error(
                    "E590",
                    f"Step 02 Integrity in {basename}: Missing capability coverage {', '.join(missing)}.",
                ))

        # External-dependency tag
        for comp in components:
            if comp.get("type") != "external":
                continue
            tags = comp.get("tags", []) or []
            if "external-dependency" not in tags:
                errors.append(make_error(
                    "E520",
                    f"Step 02 Integrity in {basename}: external component '{comp.get('component_id')}' lacks external-dependency tag.",
                ))

    return errors


# ---------------------------------------------------------------------------
# Step 03 -- glossary integrity
# ---------------------------------------------------------------------------

def collect_glossary_term_ids(artifacts: dict[str, Any]) -> set[str]:
    """Index glossary term IDs (lowercased) across all Step 03 artifacts."""
    glossary_term_ids: set[str] = set()
    for data in artifacts.values():
        schema = data.get("$schema", "")
        if "03_glossary" not in schema:
            continue
        for term in data.get("terms", []):
            if term.get("term_id"):
                glossary_term_ids.add(term["term_id"].lower())
    return glossary_term_ids


def check_step_03_integrity(artifacts: dict[str, Any]) -> list[SpecError]:
    """Validate glossary-specific integrity within artifacts.

    Checks:
    - Empty terms array
    - Duplicate term_id (case-insensitive)
    - Duplicate term text (case-insensitive)
    - Empty optional string fields (domain, units)
    """
    errors: list[SpecError] = []

    for path, data in artifacts.items():
        schema = data.get("$schema", "")
        if "03_glossary" not in schema:
            continue

        basename = os.path.basename(path)
        terms = data.get("terms", [])

        if len(terms) == 0:
            errors.append(make_error(
                "E520",
                f"Step 03 Integrity in {basename}: Empty terms array",
            ))

        seen_term_ids: set[str] = set()
        seen_terms: set[str] = set()

        for i, term in enumerate(terms):
            term_id = term.get("term_id")
            if term_id:
                term_id_lower = term_id.lower()
                if term_id_lower in seen_term_ids:
                    errors.append(make_error(
                        "E520",
                        f"Step 03 Integrity in {basename}: Duplicate term_id '{term_id}' at index {i}",
                    ))
                seen_term_ids.add(term_id_lower)

            term_text = term.get("term")
            if term_text:
                term_text_lower = term_text.lower()
                if term_text_lower in seen_terms:
                    errors.append(make_error(
                        "E520",
                        f"Step 03 Integrity in {basename}: Duplicate term '{term_text}' at index {i}",
                    ))
                seen_terms.add(term_text_lower)

            domain = term.get("domain")
            if isinstance(domain, str) and domain == "":
                errors.append(make_error(
                    "E520",
                    f"Step 03 Integrity in {basename}: Empty domain string at term index {i}",
                ))

            units = term.get("units")
            if isinstance(units, str) and units == "":
                errors.append(make_error(
                    "E520",
                    f"Step 03 Integrity in {basename}: Empty units string at term index {i}",
                ))

    return errors


# ---------------------------------------------------------------------------
# Step 04 -- FR cross-artifact trace checks
# ---------------------------------------------------------------------------

def check_step_04_integrity(
    artifacts: dict[str, Any],
    glossary_term_ids: set[str],
    capability_ids: set[str],
) -> list[SpecError]:
    """Validate FR-to-glossary and FR-to-capability trace references.

    Checks:
    - FR traces referencing unknown glossary terms
    - FR traces referencing unknown capabilities
    """
    errors: list[SpecError] = []

    for path, data in artifacts.items():
        schema = data.get("$schema", "")
        if "04_fr_list" not in schema:
            continue

        basename = os.path.basename(path)
        for fr in data.get("functional_requirements", []):
            for trace in fr.get("trace", []) or []:
                trace_type = normalize_trace_type(trace.get("type") or "")
                trace_id = trace.get("id")

                if not trace_id:
                    continue

                # Glossary trace check
                if trace_type == _GLOSSARY_TRACE_TYPE or trace_id.startswith("term-"):
                    if trace_id.lower() not in glossary_term_ids:
                        errors.append(make_error(
                            "E590",
                            f"Step 04 Integrity in {basename}: FR '{fr.get('fr_id')}' references unknown glossary term '{trace_id}'.",
                        ))

                # Capability trace check
                if trace_type == _CAPABILITY_TRACE_TYPE:
                    if trace_id not in capability_ids:
                        errors.append(make_error(
                            "E590",
                            f"Step 04 Integrity in {basename}: FR '{fr.get('fr_id')}' references unknown capability '{trace_id}'.",
                        ))

    return errors
