"""Step 16b (Execute phase) validator.

Validates the execution phase of the Trinity Loop: execution results,
code artifacts, and evidence fields on top of the base step_16 checks.
"""
from __future__ import annotations

from typing import Any, Optional

from .step_16 import validate_step_16


def validate_step_16b(data: dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None) -> list[str]:
    """Deep validation for Step 16b (Execute phase)."""
    errors = validate_step_16(data, toolkit_root, spec_path)

    execution = data.get("execution", {})
    if not isinstance(execution, dict):
        # Execution section is expected in 16b
        errors.append("Step 16b expects an 'execution' object")
        return errors

    # Execution results should be present
    results = execution.get("execution_results", [])
    if not isinstance(results, list):
        errors.append("Step 16b execution.execution_results must be an array")
    else:
        seen_commands: set[str] = set()
        for i, result in enumerate(results):
            if not isinstance(result, dict):
                continue
            cmd = result.get("command")
            if isinstance(cmd, str):
                cmd_stripped = cmd.strip()
                if cmd_stripped in seen_commands:
                    errors.append(f"Step 16b: duplicate execution_result command '{cmd_stripped}' at index {i}")
                seen_commands.add(cmd_stripped)

            status = result.get("status")
            if status and status not in {"passed", "failed", "skipped", "error"}:
                errors.append(
                    f"Step 16b: execution_result at index {i} has invalid status '{status}'"
                )

    return errors
