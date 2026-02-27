from __future__ import annotations

import re
from typing import Any

INV_ID_PATTERN = re.compile(r"^inv-[a-z0-9]+(?:-[a-z0-9]+)*$")
TRACE_TARGET_PATTERN = re.compile(r"^(fr|api|nfr|inv)-[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_06(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, rule in enumerate(instance.get("rules", [])):
        inv_id = rule.get("inv_id")
        if isinstance(inv_id, str) and not INV_ID_PATTERN.match(inv_id):
            errors.append(f"Invariant at index {i} has inv_id '{inv_id}' that does not follow 'inv-<kebab>' convention")
        if inv_id in seen_ids:
            errors.append(f"Duplicate inv_id '{inv_id}' at index {i}")
        seen_ids.add(inv_id)
        trace = rule.get("trace")
        if not trace:
            errors.append(f"Invariant '{inv_id}' missing trace")
        elif isinstance(trace, list):
            for t in trace:
                if isinstance(t, str) and not TRACE_TARGET_PATTERN.match(t):
                    errors.append(f"Invariant '{inv_id}' has trace target '{t}' that does not match (fr|api|nfr|inv)-* pattern")
    return errors
