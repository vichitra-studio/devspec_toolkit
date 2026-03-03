from __future__ import annotations

import json
import os
import re
from typing import Any, Optional, Set

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
                if isinstance(t, dict):
                    tid = t.get("id", "")
                    if tid and not TRACE_TARGET_PATTERN.match(tid):
                        errors.append(f"Invariant '{inv_id}' has trace target '{tid}' that does not match (fr|api|nfr|inv)-* pattern")
                elif isinstance(t, str) and not TRACE_TARGET_PATTERN.match(t):
                    errors.append(f"Invariant '{inv_id}' has trace target '{t}' that does not match (fr|api|nfr|inv)-* pattern")

    # Cross-step ID validation for trace targets
    fr_ids = _load_fr_ids(toolkit_root)
    api_ids = _load_api_ids(toolkit_root)

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
                            "W590 CROSS_STEP_UPSTREAM_MISSING 04_fr_list.json not found; skipping FR reference validation"
                        )
                        warned_fr = True
                elif target not in fr_ids:
                    errors.append(
                        f"E590 CROSS_STEP_ID_NOT_FOUND invariant '{inv_id}' trace target '{target}' not found in 04_fr_list.json"
                    )
            elif target.startswith("api-"):
                if api_ids is None:
                    if not warned_api:
                        errors.append(
                            "W590 CROSS_STEP_UPSTREAM_MISSING 05_interface_contracts.json not found; skipping API reference validation"
                        )
                        warned_api = True
                elif target not in api_ids:
                    errors.append(
                        f"E590 CROSS_STEP_ID_NOT_FOUND invariant '{inv_id}' trace target '{target}' not found in 05_interface_contracts.json"
                    )
            elif target.startswith("inv-"):
                if target not in inv_ids:
                    errors.append(
                        f"E590 CROSS_STEP_ID_NOT_FOUND invariant '{inv_id}' trace target '{target}' not found in current artifact's rules"
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
                            "W590 CROSS_STEP_UPSTREAM_MISSING 05_interface_contracts.json not found; skipping API reference validation"
                        )
                        warned_api = True
                elif api_ref not in api_ids:
                    errors.append(
                        f"E590 CROSS_STEP_ID_NOT_FOUND invariant '{inv_id}' scope.apis reference '{api_ref}' not found in 05_interface_contracts.json"
                    )

    return errors


def _load_fr_ids(toolkit_root: str) -> Optional[Set[str]]:
    """Load FR IDs from step 04 if available."""
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None
    for fn in os.listdir(spec_dir):
        if fn.startswith("04_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items = data.get("functional_requirements", [])
                return {
                    item.get("fr_id")
                    for item in items
                    if isinstance(item, dict) and item.get("fr_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None


def _load_api_ids(toolkit_root: str) -> Optional[Set[str]]:
    """Load API IDs from step 05 if available."""
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None
    for fn in os.listdir(spec_dir):
        if fn.startswith("05_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items = data.get("apis", [])
                return {
                    item.get("api_id")
                    for item in items
                    if isinstance(item, dict) and item.get("api_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None
