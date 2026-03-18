from __future__ import annotations

import warnings
from typing import Optional, Set
from ...core.errors import make_error, SpecError
from ...core.trace_types import is_valid_trace_type, normalize_trace_type

# ---------------------------------------------------------------------------
# Business-rule trace-type constant
# ---------------------------------------------------------------------------

# Business rule: capability-to-component traceability.
# Capabilities (Step 01) trace to system-sketch components (Step 02) to show
# which runtime component(s) realise a given capability.  Only the "component"
# trace type is valid here because capabilities are mapped to architectural
# building blocks, not to requirements or test artefacts.
_CAPABILITY_COMPONENT_TRACE_TYPE: str = "component"

# Deferred trace-type validation: performed once on first validate call,
# not at import time, to avoid noisy warnings during simple imports.
_TRACE_TYPE_VALIDATED: bool = False


def validate_trace_integrity(instance: dict, component_ids: Optional[Set[str]]) -> list[SpecError]:
    """
    Validates that capabilities trace to known components in the System Sketch.
    """
    errors: list[SpecError] = []
    if component_ids is None:
        return errors

    for cap in instance.get("capabilities", []):
        for trace in cap.get("trace", []):
            if normalize_trace_type(trace.get("type", "")) == _CAPABILITY_COMPONENT_TRACE_TYPE:
                target_id = trace.get("id")
                if target_id not in component_ids:
                    errors.append(make_error("E590", f"Capability '{cap.get('capability_id')}' traces to unknown component '{target_id}'"))
    return errors

def validate_step_01(
    instance: dict,
    repo_root: str,
    component_ids: Optional[Set[str]] = None
) -> list[SpecError]:
    """
    Deep validation logic for Step 01 (Capabilities).

    Schema validation is handled by the orchestrator (validate.py) before
    this function is called.  This function performs trace integrity checks.
    """
    global _TRACE_TYPE_VALIDATED
    if not _TRACE_TYPE_VALIDATED:
        _TRACE_TYPE_VALIDATED = True
        if not is_valid_trace_type(_CAPABILITY_COMPONENT_TRACE_TYPE):
            warnings.warn(
                f"step_01: _CAPABILITY_COMPONENT_TRACE_TYPE '{_CAPABILITY_COMPONENT_TRACE_TYPE}' "
                f"is not a valid canon trace type",
                stacklevel=2,
            )

    errors: list[SpecError] = []

    # Trace Integrity (if component_ids provided)
    if component_ids:
        custom_errors = validate_trace_integrity(instance, component_ids)
        errors.extend(custom_errors)

    return errors
