from __future__ import annotations

import json
import os
from typing import Any

from .canonical_registry import CanonicalRegistry


def canonical_autofix(repo_root: str, spec_dir: str, write: bool = False, canon_dir: str = "canon") -> dict[str, list[str]]:
    registry = CanonicalRegistry.load(repo_root, canon_dir=canon_dir)
    changes: dict[str, list[str]] = {}
    for path in _iter_json(spec_dir):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        file_changes: list[str] = []
        _autofix_node(data, registry, file_changes)
        if file_changes:
            changes[path] = file_changes
            if write:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.write("\n")
    return changes


def _autofix_node(node: Any, registry: CanonicalRegistry, file_changes: list[str], path: str = "") -> None:
    if isinstance(node, dict):
        for source_field, target_ref_field, kind in INFERENCE_RULES:
            _try_infer_ref(node, source_field, target_ref_field, kind, registry, file_changes, path)
        for key, value in node.items():
            next_path = f"{path}.{key}" if path else key
            _autofix_node(value, registry, file_changes, next_path)
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            next_path = f"{path}[{idx}]"
            _autofix_node(value, registry, file_changes, next_path)


def _try_infer_ref(
    obj: dict[str, Any],
    source_field: str,
    target_ref_field: str,
    kind: str,
    registry: CanonicalRegistry,
    file_changes: list[str],
    path: str,
) -> None:
    value = obj.get(source_field)
    if not isinstance(value, str):
        return
    if target_ref_field in obj and isinstance(obj[target_ref_field], dict):
        return
    resolved = registry.resolve_alias(kind, value)
    if not resolved:
        return
    obj[target_ref_field] = {"id": resolved, "kind": kind}
    file_changes.append(f"{path or '$'} add {target_ref_field} from {source_field}")


def _iter_json(spec_dir: str):
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                yield os.path.join(root, fn)


INFERENCE_RULES = (
    ("metric", "metric_ref", "metric"),
    ("unit", "unit_ref", "unit"),
    ("units", "unit_ref", "unit"),
    ("stage", "stage_ref", "environment"),
    ("environment", "environment_ref", "environment"),
    ("status", "status_ref", "lifecycle_state"),
    ("state", "state_ref", "lifecycle_state"),
    ("role", "role_ref", "role"),
    ("actor", "actor_ref", "role"),
    ("entity", "entity_ref", "entity"),
    ("resource", "resource_ref", "entity"),
    ("capability", "capability_ref", "capability"),
    ("action", "action_ref", "action"),
    ("command", "command_ref", "command"),
    ("policy", "policy_ref", "policy"),
    ("risk_category", "risk_category_ref", "risk_category"),
    ("tag", "tag_ref", "tag"),
)
