from __future__ import annotations

import re
from typing import Any

from ...core.errors import make_error, SpecError
from ...core.trace_types import is_valid_trace_type


def validate_step_10(instance: dict[str, Any], toolkit_root: str) -> list[SpecError]:
    """Validate Step 10 (Governance) logic.

    Checks owners, enums, regex patterns, trace/link structure,
    commit pattern compilation, trace type canonical check, and link target validation.
    """
    errors: list[SpecError] = []

    # Validate owner
    allowed_owners = {"api", "ui", "system", "ops", "data", "product", "business", "engineering"}
    owner = instance.get("owner")
    if owner and owner not in allowed_owners:
        errors.append(make_error("E530", f"Invalid owner '{owner}'. Must be one of {sorted(allowed_owners)}"))

    # Validate commit_message_rules
    if "commit_message_rules" in instance:
        rules = instance["commit_message_rules"]
        if "pattern" in rules:
            try:
                re.compile(rules["pattern"])
            except re.error as e:
                errors.append(make_error("E520", f"Invalid regex pattern in commit_message_rules: {e}"))

        # Validate allowed_types if present
        allowed_types = rules.get("allowed_types", [])
        if isinstance(allowed_types, list):
            for t in allowed_types:
                if not isinstance(t, str) or not t.strip():
                    errors.append(make_error("E530", f"commit_message_rules.allowed_types contains invalid entry: {t!r}"))

    # Validate pr_rules
    if "pr_rules" in instance:
        allowed_rules = {
            "validate", "validate-all", "matrix", "fixtures-lint",
            "invariants-check", "governance-check", "seed-lint", "docs-lint", "test", "build",
            "lint", "format", "audit", "security"
        }
        for i, rule in enumerate(instance["pr_rules"]):
            if rule not in allowed_rules:
                errors.append(make_error("E530", f"Invalid pr_rule '{rule}' at index {i}. Must be one of {sorted(allowed_rules)}"))

    # Validate trace types against canonical registry
    if "trace" in instance:
        for i, item in enumerate(instance["trace"]):
            t_type = item.get("type")
            if t_type and not is_valid_trace_type(t_type):
                errors.append(make_error("E530", f"Invalid trace type '{t_type}' at index {i}."))

            # Link target validation: targets should reference existing spec artifacts
            targets = item.get("targets", [])
            if isinstance(targets, list):
                for target in targets:
                    if isinstance(target, str) and not _is_valid_link_target(target):
                        errors.append(
                            make_error("E530", f"Trace item at index {i} has invalid link target '{target}'. "
                            "Expected format: step_NN, fr-*, api-*, nfr-*, inv-*")
                        )

    return errors


def _is_valid_link_target(target: str) -> bool:
    """Check if a link target follows expected ID conventions."""
    if not target:
        return False
    # Accept step references, kebab-case IDs, or file paths
    if re.match(r"^(step_)?\d{2}[a-z]?$", target):
        return True
    if re.match(r"^[a-z]+-[a-z0-9-]+$", target):
        return True
    if "/" in target or target.endswith(".json") or target.endswith(".md"):
        return True
    return False
