from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .canonical_registry import CanonicalRegistry


def validate_canonical_integrity(repo_root: str, spec_dir: str, canon_dir: str = "canon") -> list[str]:
    registry = CanonicalRegistry.load(repo_root, canon_dir=canon_dir)
    errors: list[str] = []
    observed: dict[tuple[str, str], set[str]] = {}
    for path in _iter_json_files(spec_dir):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            rel = os.path.relpath(path, repo_root)
            errors.append(f"E520 UNRESOLVED_INPUT {rel} invalid_json {exc}")
            continue
        for ref_path, ref in _collect_canonical_refs(data):
            ref_errors = registry.validate_ref(ref)
            for err in ref_errors:
                errors.append(f"{err} {os.path.relpath(path, repo_root)}:{ref_path}")
        _collect_observed_semantics(data, observed)

    for (kind, value), ids in observed.items():
        if len(ids) > 1:
            errors.append(
                f"E210 CROSS_ARTIFACT_DRIFT kind={kind} value='{value}' canonical_ids={sorted(ids)}"
            )
    return errors


def _iter_json_files(spec_dir: str):
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                yield os.path.join(root, fn)


def _collect_canonical_refs(obj: Any, path: str = "") -> list[tuple[str, dict[str, Any]]]:
    refs: list[tuple[str, dict[str, Any]]] = []
    if isinstance(obj, dict):
        if {"id", "kind"} <= set(obj.keys()) and isinstance(obj.get("id"), str) and obj["id"].startswith("cn:"):
            refs.append((path or "$", obj))
        for key, value in obj.items():
            next_path = f"{path}.{key}" if path else key
            refs.extend(_collect_canonical_refs(value, next_path))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            next_path = f"{path}[{idx}]"
            refs.extend(_collect_canonical_refs(value, next_path))
    return refs


def _collect_observed_semantics(obj: Any, observed: dict[tuple[str, str], set[str]]) -> None:
    if isinstance(obj, dict):
        pairs = (
            ("metric", "metric_ref", "metric"),
            ("unit", "unit_ref", "unit"),
            ("stage", "stage_ref", "environment"),
            ("environment", "environment_ref", "environment"),
            ("status", "status_ref", "lifecycle_state"),
        )
        for value_field, ref_field, kind in pairs:
            value = obj.get(value_field)
            ref = obj.get(ref_field)
            if isinstance(value, str) and isinstance(ref, dict):
                cid = ref.get("id")
                if isinstance(cid, str) and cid.startswith("cn:"):
                    key = (kind, " ".join(value.strip().lower().split()))
                    observed.setdefault(key, set()).add(cid)
        for v in obj.values():
            _collect_observed_semantics(v, observed)
    elif isinstance(obj, list):
        for v in obj:
            _collect_observed_semantics(v, observed)
