from __future__ import annotations

import re
from typing import Any

from ...core.errors import make_error, SpecError

_ALLOWED_OWNERS: frozenset[str] = frozenset(
    {"api", "ui", "system", "ops", "data", "product", "business", "engineering"}
)


def validate_step_10(instance: dict[str, Any], toolkit_root: str) -> list[SpecError]:
    """Validate Step 10 (Governance) logic.

    Checks the owner value, the ``commit_message_rules`` pattern (it must compile) and the
    ``commit_message_rules.allowed_types`` entries. A wrong-typed value is left to the schema
    and never raises here.
    """
    errors: list[SpecError] = []

    owner = instance.get("owner")
    if isinstance(owner, str) and owner and owner not in _ALLOWED_OWNERS:
        errors.append(make_error("E530", f"Invalid owner '{owner}'. Must be one of {sorted(_ALLOWED_OWNERS)}"))

    commit_rules = instance.get("commit_message_rules")
    if isinstance(commit_rules, dict):
        errors.extend(_commit_rule_errors(commit_rules))
    return errors


def _commit_rule_errors(commit_rules: dict[str, Any]) -> list[SpecError]:
    """Errors for one ``commit_message_rules`` object: an uncompilable pattern, a blank ``allowed_types`` entry."""
    errors: list[SpecError] = []
    pattern = commit_rules.get("pattern")
    if isinstance(pattern, str):
        try:
            re.compile(pattern)
        except re.error as e:
            errors.append(make_error("E520", f"Invalid regex pattern in commit_message_rules: {e}"))

    allowed_types = commit_rules.get("allowed_types", [])
    if isinstance(allowed_types, list):
        for t in allowed_types:
            if not isinstance(t, str) or not t.strip():
                errors.append(make_error("E530", f"commit_message_rules.allowed_types contains invalid entry: {t!r}"))
    return errors
