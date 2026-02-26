from __future__ import annotations

from typing import Any


def validate_step_02a(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    ci_gates = instance.get("ci_gates", [])
    if isinstance(ci_gates, list):
        seen: set[str] = set()
        for i, gate in enumerate(ci_gates):
            if not isinstance(gate, str):
                continue
            if gate in seen:
                errors.append(f"Duplicate ci_gates entry '{gate}' at index {i}")
            seen.add(gate)
    return errors
