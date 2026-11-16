from __future__ import annotations

import re
from typing import Any

from ...core.errors import make_error, SpecError
from ...validation.linter_utils import check_no_duplicates

FIXTURE_ID_PATTERN = re.compile(r"^fix-[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_08(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    """Validate Step 08 (fixtures): duplicate ``fixture_id`` values and the ``fix-<kebab>`` id convention.

    What a fixture proves (``verifies`` / ``removes``) is required by the schema, and whether those ids
    exist is the resolver's job, so this validator reads no other field. Never raises on a wrong-typed value.
    """
    errors: list[SpecError] = []
    fixtures = instance.get("fixtures", [])
    if not isinstance(fixtures, list):
        return errors
    check_no_duplicates(fixtures, "fixture_id", "fixture_id", errors)
    for i, fixture in enumerate(fixtures):
        fixture_id = fixture.get("fixture_id") if isinstance(fixture, dict) else None
        if isinstance(fixture_id, str) and not FIXTURE_ID_PATTERN.match(fixture_id):
            errors.append(make_error("E530", f"Fixture at index {i} has fixture_id '{fixture_id}' that does not follow 'fix-<kebab>' convention"))
    return errors
