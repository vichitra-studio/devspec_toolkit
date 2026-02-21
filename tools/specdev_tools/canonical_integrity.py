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
        rel = os.path.relpath(path, repo_root)
        errors.extend(_validate_document_integrity(registry, data, rel))
        _collect_observed_semantics(data, observed)

    for (kind, value), ids in observed.items():
        if len(ids) > 1:
            errors.append(
                f"E210 CROSS_ARTIFACT_DRIFT kind={kind} value='{value}' canonical_ids={sorted(ids)}"
            )
    return errors


def validate_canonical_integrity_file(repo_root: str, path: str, canon_dir: str = "canon") -> list[str]:
    registry = CanonicalRegistry.load(repo_root, canon_dir=canon_dir)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"E520 UNRESOLVED_INPUT {path} invalid_json {exc}"]

    errors = _validate_document_integrity(registry, data, path)
    observed: dict[tuple[str, str], set[str]] = {}
    _collect_observed_semantics(data, observed)
    for (kind, value), ids in observed.items():
        if len(ids) > 1:
            errors.append(
                f"E210 CROSS_ARTIFACT_DRIFT kind={kind} value='{value}' canonical_ids={sorted(ids)} {path}"
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


def _validate_document_integrity(
    registry: CanonicalRegistry,
    data: Any,
    rel: str,
) -> list[str]:
    errors: list[str] = []
    for ref_path, ref in _collect_canonical_refs(data):
        ref_errors = registry.validate_ref(ref)
        for err in ref_errors:
            errors.append(f"{err} {rel}:{ref_path}")

    declared_ids = _collect_declared_canonical_refs(data)
    observed_ids = _collect_used_canonical_ref_ids(data)
    missing_ids = sorted(observed_ids - declared_ids)
    extra_ids = sorted(declared_ids - observed_ids)
    if missing_ids:
        errors.append(
            f"E210 CROSS_ARTIFACT_DRIFT canonical_refs_used_missing {rel} ids={missing_ids}"
        )
    if extra_ids:
        errors.append(
            f"E210 CROSS_ARTIFACT_DRIFT canonical_refs_used_extra {rel} ids={extra_ids}"
        )
    return errors


def _collect_declared_canonical_refs(data: Any) -> set[str]:
    if not isinstance(data, dict):
        return set()
    values = data.get("canonical_refs_used")
    if not isinstance(values, list):
        return set()
    refs: set[str] = set()
    for item in values:
        if isinstance(item, dict):
            cid = item.get("id")
            if isinstance(cid, str) and cid.startswith("cn:"):
                refs.add(cid)
    return refs


def _collect_used_canonical_ref_ids(obj: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.endswith("_ref") and isinstance(value, dict):
                cid = value.get("id")
                if isinstance(cid, str) and cid.startswith("cn:"):
                    refs.add(cid)
            refs.update(_collect_used_canonical_ref_ids(value))
    elif isinstance(obj, list):
        for value in obj:
            refs.update(_collect_used_canonical_ref_ids(value))
    return refs


def _collect_observed_semantics(obj: Any, observed: dict[tuple[str, str], set[str]]) -> None:
    if isinstance(obj, dict):
        alias_value_fields: dict[str, tuple[str, ...]] = {
            "stage_ref": ("stage", "environment"),
            "environment_ref": ("environment", "stage"),
            "status_ref": ("status",),
        }
        for key, ref in obj.items():
            if not key.endswith("_ref") or not isinstance(ref, dict):
                continue
            cid = ref.get("id")
            if not isinstance(cid, str) or not cid.startswith("cn:"):
                continue
            kind = ref.get("kind")
            if not isinstance(kind, str) or not kind:
                kind = key[:-4]
            base_field = key[:-4]
            candidates = (base_field,) + alias_value_fields.get(key, ())
            for value_field in candidates:
                value = obj.get(value_field)
                if isinstance(value, str):
                    normalized = " ".join(value.strip().lower().split())
                    observed.setdefault((kind, normalized), set()).add(cid)
                    break
        for v in obj.values():
            _collect_observed_semantics(v, observed)
    elif isinstance(obj, list):
        for v in obj:
            _collect_observed_semantics(v, observed)
