from __future__ import annotations

import re
from typing import Any

FIXTURE_ID_PATTERN = re.compile(r"^fix-[a-z0-9]+(?:-[a-z0-9]+)*$")
TARGET_ID_PATTERN = re.compile(r"^(fr|api|nfr|inv)-[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_08(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, fixture in enumerate(instance.get("fixtures", [])):
        fixture_id = fixture.get("fixture_id")
        if isinstance(fixture_id, str) and not FIXTURE_ID_PATTERN.match(fixture_id):
            errors.append(f"Fixture at index {i} has fixture_id '{fixture_id}' that does not follow 'fix-<kebab>' convention")
        if fixture_id in seen_ids:
            errors.append(f"Duplicate fixture_id '{fixture_id}' at index {i}")
        seen_ids.add(fixture_id)
        targets = fixture.get("targets")
        if not targets:
            errors.append(f"Fixture '{fixture_id}' missing targets")
        elif isinstance(targets, list):
            for t in targets:
                if isinstance(t, str) and not TARGET_ID_PATTERN.match(t):
                    errors.append(f"Fixture '{fixture_id}' has target '{t}' that does not match (fr|api|nfr|inv)-* pattern")
    return errors
