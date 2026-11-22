from __future__ import annotations

import re
from typing import Any

from ...core.cli_commands import known_cli_commands
from ...core.errors import make_error, SpecError

_ALLOWED_OWNERS: frozenset[str] = frozenset(
    {"api", "ui", "system", "ops", "data", "product", "business", "engineering"}
)


def validate_step_10(instance: dict[str, Any], toolkit_root: str) -> list[SpecError]:
    """Validate Step 10 (Governance) logic.

    Checks the owner value, the ``commit_message_rules`` pattern (it must compile), the
    ``commit_message_rules.allowed_types`` entries and the ``cli_command`` of each rule (it must be on the command list
    that ``registry-generate`` writes). A wrong-typed value is left to the schema and never raises here.
    """
    errors: list[SpecError] = []

    owner = instance.get("owner")
    if isinstance(owner, str) and owner and owner not in _ALLOWED_OWNERS:
        errors.append(make_error("E530", f"Invalid owner '{owner}'. Must be one of {sorted(_ALLOWED_OWNERS)}"))

    commit_rules = instance.get("commit_message_rules")
    if isinstance(commit_rules, dict):
        errors.extend(_commit_rule_errors(commit_rules))
    errors.extend(_rule_command_errors(instance.get("rules"), toolkit_root))
    return errors


def _rule_command_errors(rules: object, toolkit_root: str) -> list[SpecError]:
    """E530 for each rule whose ``cli_command`` is not a command of the toolkit's command list.

    Nothing is reported when the list cannot be read: there is then nothing to compare with.
    """
    if not isinstance(rules, list):
        return []
    named = [(rule, rule["cli_command"]) for rule in rules if isinstance(rule, dict) and isinstance(rule.get("cli_command"), str)]
    if not named:
        return []
    try:
        commands = known_cli_commands(toolkit_root)
    except (OSError, ValueError, KeyError, TypeError):
        return []
    return [
        make_error(
            "E530",
            f"the cli_command '{command}' of rule '{rule.get('rule_id')}' is not a specdev command; "
            f"give a command as you type it after specdev, for example spec-check or third-party check",
            node_id=rule["rule_id"] if isinstance(rule.get("rule_id"), str) else None,
        )
        for rule, command in named
        if command not in commands
    ]


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
