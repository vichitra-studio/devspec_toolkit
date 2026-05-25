"""Step 16b (Execute phase) validator.

Validates the execution phase of the Trinity Loop: execution results,
code artifacts, and evidence fields on top of the base step_16 checks.
"""
from __future__ import annotations

from typing import Any, Optional

from ...core.errors import make_error, SpecError
from .step_16a import validate_step_16a


# Mirrors the ``executionStatus`` atom in ``schema/16_impl_context.schema.json``
# (``$defs.executionStatus.enum``). Any drift between this set and the schema
# enum silently flips which statuses the deep validator accepts vs what the
# schema rejects — keep them synchronized.
_EXECUTION_STATUSES = frozenset({"passed", "failed", "blocked", "partial"})


def validate_step_16b(data: dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None, spec_root: Optional[str] = None) -> list[SpecError]:
    """Deep validation for Step 16b (Execute phase).

    A 16b artifact is a 16a plan augmented with an ``execution`` section.
    It must satisfy every 16a-phase constraint in addition to the 16b-specific
    execution-result checks below.  Chains up through ``validate_step_16a``,
    which itself chains through ``validate_step_16`` (base).
    """
    errors = validate_step_16a(data, toolkit_root, spec_path, spec_root)

    execution = data.get("execution", {})
    if not isinstance(execution, dict):
        # Execution section is expected in 16b
        errors.append(make_error("E520", "Step 16b expects an 'execution' object"))
        return errors

    # Execution results should be present
    results = execution.get("execution_results", [])
    if not isinstance(results, list):
        errors.append(make_error("E520", "Step 16b execution.execution_results must be an array"))
    else:
        seen_commands: set[str] = set()
        for i, result in enumerate(results):
            if not isinstance(result, dict):
                continue
            cmd = result.get("command")
            if isinstance(cmd, str):
                cmd_stripped = cmd.strip()
                if cmd_stripped in seen_commands:
                    errors.append(make_error("E520", f"Step 16b: duplicate execution_result command '{cmd_stripped}' at index {i}"))
                seen_commands.add(cmd_stripped)

            status = result.get("status")
            if status and status not in _EXECUTION_STATUSES:
                errors.append(
                    make_error(
                        "E520",
                        f"Step 16b: execution_result at index {i} has invalid status "
                        f"'{status}'. Must be one of: {', '.join(sorted(_EXECUTION_STATUSES))}",
                    )
                )

    return errors
