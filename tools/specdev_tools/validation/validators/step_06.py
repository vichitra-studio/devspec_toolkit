from __future__ import annotations

import re
from typing import Any

from ...core.errors import make_error, SpecError
from ...core.loaders import load_upstream_ids
from ...validation.linter_utils import check_no_duplicates

INV_ID_PATTERN = re.compile(r"^inv-[a-z0-9]+(?:-[a-z0-9]+)*$")
TRACE_TARGET_PATTERN = re.compile(r"^(fr|api|nfr|inv)-[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_06(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    errors: list[SpecError] = []
    check_no_duplicates(instance.get("rules", []), "inv_id", "inv_id", errors)
    for i, rule in enumerate(instance.get("rules", [])):
        inv_id = rule.get("inv_id")
        if isinstance(inv_id, str) and not INV_ID_PATTERN.match(inv_id):
            errors.append(make_error("E530", f"Invariant at index {i} has inv_id '{inv_id}' that does not follow 'inv-<kebab>' convention"))
        trace = rule.get("trace")
        if not trace:
            errors.append(make_error("E520", f"Invariant '{inv_id}' missing trace"))
        elif isinstance(trace, list):
            for t in trace:
                if isinstance(t, dict):
                    tid = t.get("id", "")
                    if tid and not TRACE_TARGET_PATTERN.match(tid):
                        errors.append(make_error("E530", f"Invariant '{inv_id}' has trace target '{tid}' that does not match (fr|api|nfr|inv)-* pattern"))
                elif isinstance(t, str) and not TRACE_TARGET_PATTERN.match(t):
                    errors.append(make_error("E530", f"Invariant '{inv_id}' has trace target '{t}' that does not match (fr|api|nfr|inv)-* pattern"))

    # Cross-step ID validation for trace targets
    fr_ids = load_upstream_ids(toolkit_root, "04", "functional_requirements", "fr_id", spec_root=spec_root)
    api_ids = load_upstream_ids(toolkit_root, "05", "apis", "api_id", spec_root=spec_root)

    # Collect inv IDs from this artifact for self-referential validation
    inv_ids = {
        rule.get("inv_id")
        for rule in instance.get("rules", [])
        if isinstance(rule, dict) and rule.get("inv_id")
    }

    # Track which upstream warnings have been emitted (once per missing file)
    warned_fr = False
    warned_api = False

    for rule in instance.get("rules", []):
        inv_id = rule.get("inv_id", "<unknown>")
        trace = rule.get("trace")
        if not isinstance(trace, list):
            continue
        for entry in trace:
            # Extract target ID from both dict (traceRef) and string formats
            if isinstance(entry, dict):
                target = entry.get("id", "")
            elif isinstance(entry, str):
                target = entry
            else:
                continue
            if not target:
                continue
            if target.startswith("fr-"):
                if fr_ids is None:
                    if not warned_fr:
                        errors.append(
                            make_error("W590", "CROSS_STEP_UPSTREAM_MISSING 04_fr_list.json not found; skipping FR reference validation")
                        )
                        warned_fr = True
                elif target not in fr_ids:
                    errors.append(
                        make_error("E590", f"CROSS_STEP_ID_NOT_FOUND invariant '{inv_id}' trace target '{target}' not found in 04_fr_list.json")
                    )
            elif target.startswith("api-"):
                if api_ids is None:
                    if not warned_api:
                        errors.append(
                            make_error("W590", "CROSS_STEP_UPSTREAM_MISSING 05_interface_contracts.json not found; skipping API reference validation")
                        )
                        warned_api = True
                elif target not in api_ids:
                    errors.append(
                        make_error("E590", f"CROSS_STEP_ID_NOT_FOUND invariant '{inv_id}' trace target '{target}' not found in 05_interface_contracts.json")
                    )
            elif target.startswith("inv-"):
                if target not in inv_ids:
                    errors.append(
                        make_error("E590", f"CROSS_STEP_ID_NOT_FOUND invariant '{inv_id}' trace target '{target}' not found in current artifact's rules")
                    )

    # Cross-step validation for scope.apis references
    for rule in instance.get("rules", []):
        inv_id = rule.get("inv_id", "<unknown>")
        scope = rule.get("scope")
        if not isinstance(scope, dict):
            continue
        scope_apis = scope.get("apis", [])
        if isinstance(scope_apis, list):
            for api_ref in scope_apis:
                if not isinstance(api_ref, str):
                    continue
                if api_ids is None:
                    if not warned_api:
                        errors.append(
                            make_error("W590", "CROSS_STEP_UPSTREAM_MISSING 05_interface_contracts.json not found; skipping API reference validation")
                        )
                        warned_api = True
                elif api_ref not in api_ids:
                    errors.append(
                        make_error("E590", f"CROSS_STEP_ID_NOT_FOUND invariant '{inv_id}' scope.apis reference '{api_ref}' not found in 05_interface_contracts.json")
                    )

    return errors
