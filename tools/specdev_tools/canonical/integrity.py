"""Canonical integrity checker — cross-artifact drift detection.

Scans spec artifacts for canonical references (``cn:`` IDs, ``*_ref``
objects) and verifies they resolve against the canonical registry.  Also
detects unresolved semantic candidates that should have a ``*_ref``
companion and flags partial-drift when the same semantic value maps to
different canonical IDs across files.

Coupling with ``lint.py``: this module calls ``lint_canon_dir`` as a
preflight step.  If the canonical directory itself is structurally invalid
the integrity check short-circuits with those errors.  Once the registry
passes structural lint, ``integrity.py`` loads it via
``CanonicalRegistry`` and walks every spec JSON file.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin

from .lint import lint_canon_dir
from .registry import CanonicalRegistry
from ..core.errors import SpecError, make_error
from ..core.registry import SchemaRegistry


def validate_canonical_integrity(
    repo_root: str,
    spec_dir: str,
    canon_dir: str = "canon",
    enforce_unresolved_semantics: bool = True,
    require_manifest_schema_registration: bool = True,
) -> list[SpecError]:
    spec_dir_abs = os.path.abspath(spec_dir)
    if not os.path.isdir(spec_dir_abs):
        return [make_error("E520", f"UNRESOLVED_INPUT missing_spec_dir {spec_dir_abs}")]
    preflight_errors = lint_canon_dir(
        repo_root,
        canon_dir=canon_dir,
        require_manifest_schema_registration=require_manifest_schema_registration,
    )
    if preflight_errors:
        return _uniq(preflight_errors)
    registry = CanonicalRegistry.load(repo_root, canon_dir=canon_dir)
    errors: list[SpecError] = list(registry.load_errors)
    schema_registry, schema_registry_error = _try_load_schema_registry(repo_root)
    observed: dict[tuple[str, str], dict[str, list[str]]] = {}
    for path in _iter_json_files(spec_dir_abs):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            rel = os.path.relpath(path, repo_root)
            errors.append(make_error("E520", f"UNRESOLVED_INPUT {rel} invalid_json {exc}"))
            continue
        rel = os.path.relpath(path, repo_root)
        schema, schema_uri, schema_error = _load_document_schema(schema_registry, data, rel, schema_registry_error)
        if schema_error:
            errors.append(schema_error)
        enforce_unresolved_for_doc = enforce_unresolved_semantics and schema_error is None
        errors.extend(
            _validate_document_integrity(
                registry,
                data,
                rel,
                schema=schema,
                schema_uri=schema_uri,
                schema_registry=schema_registry,
                enforce_unresolved_semantics=enforce_unresolved_for_doc,
            )
        )
        _collect_observed_semantics(data, observed, rel)

    for (kind, value), cid_paths in observed.items():
        if len(cid_paths) > 1:
            detail = " | ".join(f"{cid}@[{','.join(paths)}]" for cid, paths in sorted(cid_paths.items()))
            errors.append(
                make_error("E211", f"PARTIAL_DRIFT kind={kind} value='{value}' {detail}")
            )
    return errors


def validate_canonical_integrity_file(
    repo_root: str,
    path: str,
    canon_dir: str = "canon",
    enforce_unresolved_semantics: bool = True,
    require_manifest_schema_registration: bool = True,
) -> list[SpecError]:
    preflight_errors = lint_canon_dir(
        repo_root,
        canon_dir=canon_dir,
        require_manifest_schema_registration=require_manifest_schema_registration,
    )
    if preflight_errors:
        return _uniq(preflight_errors)
    registry = CanonicalRegistry.load(repo_root, canon_dir=canon_dir)
    errors: list[SpecError] = list(registry.load_errors)
    schema_registry, schema_registry_error = _try_load_schema_registry(repo_root)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return [make_error("E520", f"UNRESOLVED_INPUT {path} invalid_json {exc}")]

    schema, schema_uri, schema_error = _load_document_schema(schema_registry, data, path, schema_registry_error)
    if schema_error:
        errors.append(schema_error)
    enforce_unresolved_for_doc = enforce_unresolved_semantics and schema_error is None
    errors.extend(
        _validate_document_integrity(
            registry,
            data,
            path,
            schema=schema,
            schema_uri=schema_uri,
            schema_registry=schema_registry,
            enforce_unresolved_semantics=enforce_unresolved_for_doc,
        )
    )
    observed: dict[tuple[str, str], dict[str, list[str]]] = {}
    _collect_observed_semantics(data, observed, path)
    for (kind, value), cid_paths in observed.items():
        if len(cid_paths) > 1:
            detail = " | ".join(f"{cid}@[{','.join(paths)}]" for cid, paths in sorted(cid_paths.items()))
            errors.append(
                make_error("E211", f"PARTIAL_DRIFT kind={kind} value='{value}' {detail}")
            )
    return errors


def _iter_json_files(spec_dir: str):
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                yield os.path.join(root, fn)


def _uniq(messages: list[SpecError]) -> list[SpecError]:
    return list(dict.fromkeys(messages))


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
    schema: dict[str, Any] | None = None,
    schema_uri: str | None = None,
    schema_registry: SchemaRegistry | None = None,
    enforce_unresolved_semantics: bool = True,
) -> list[SpecError]:
    errors: list[SpecError] = []
    for ref_path, ref in _collect_canonical_refs(data):
        ref_errors = registry.validate_ref(ref)
        for err in ref_errors:
            errors.append(SpecError(code=err.code, message=f"{err.message} {rel}:{ref_path}"))

    declared_ids = _collect_declared_canonical_refs(data)
    observed_ids = _collect_used_canonical_ref_ids(data)
    missing_ids = sorted(observed_ids - declared_ids)
    extra_ids = sorted(declared_ids - observed_ids)
    if missing_ids:
        errors.append(
            make_error("E210", f"CROSS_ARTIFACT_DRIFT canonical_refs_used_missing {rel} ids={missing_ids}")
        )
    if extra_ids:
        errors.append(
            make_error("E210", f"CROSS_ARTIFACT_DRIFT canonical_refs_used_extra {rel} ids={extra_ids}")
        )
    if enforce_unresolved_semantics:
        errors.extend(
            _validate_unresolved_candidates(
                data,
                rel,
                schema=schema,
                schema_uri=schema_uri,
                schema_registry=schema_registry,
            )
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


def _collect_observed_semantics(obj: Any, observed: dict[tuple[str, str], dict[str, list[str]]], rel: str = "") -> None:
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
                    observed.setdefault((kind, normalized), {}).setdefault(cid, []).append(rel)
                    break
        for v in obj.values():
            _collect_observed_semantics(v, observed, rel)
    elif isinstance(obj, list):
        for v in obj:
            _collect_observed_semantics(v, observed, rel)


_ALIASED_SOURCE_FIELDS: dict[str, str] = {
    "category": "risk_category_ref",
}

_FALLBACK_DIRECT_FIELDS: set[str] = {
    "stage",
    "environment",
    "status",
    "term",
    "acronym",
    "capability",
    "action",
    "entity",
    "event",
    "interface",
    "metric",
    "unit",
    "role",
    "policy",
    "command",
    "tag",
    "risk_category",
    "governance_label",
    "id_pattern",
    "completeness_dimension",
}


def _validate_unresolved_candidates(
    data: Any,
    rel: str,
    schema: dict[str, Any] | None = None,
    schema_uri: str | None = None,
    schema_registry: SchemaRegistry | None = None,
) -> list[SpecError]:
    if not isinstance(data, dict):
        return []
    proposals = _proposal_index(data.get("canonical_proposals"))
    conflicts = _conflict_index(data.get("canonical_conflicts"))
    errors: list[SpecError] = []
    for field_path, kind, value in _collect_unresolved_candidates(
        data,
        schema=schema,
        schema_root=schema,
        current_schema_uri=schema_uri,
        schema_registry=schema_registry,
        allow_fallback=schema is None,
    ):
        label = _norm_semantic(value)
        if (field_path, label) in conflicts:
            continue
        if (field_path, kind, label) in proposals:
            continue
        errors.append(
            make_error("E210", f"CROSS_ARTIFACT_DRIFT unresolved_canonical_semantic {rel} field={field_path} kind={kind} value={value!r}")
        )
    return errors


def _collect_unresolved_candidates(
    obj: Any,
    schema: Any = None,
    path: str = "",
    schema_root: dict[str, Any] | None = None,
    current_schema_uri: str | None = None,
    schema_registry: SchemaRegistry | None = None,
    allow_fallback: bool = True,
) -> list[tuple[str, str, str]]:
    unresolved: list[tuple[str, str, str]] = []
    schema_node, schema_root_ctx, schema_uri_ctx = _resolve_schema_node(
        schema,
        schema_root,
        schema_registry=schema_registry,
        current_schema_uri=current_schema_uri,
    )
    if isinstance(obj, dict):
        schema_props = _schema_properties(
            schema_node,
            schema_root_ctx,
            schema_registry=schema_registry,
            current_schema_uri=schema_uri_ctx,
        )
        for key, value in obj.items():
            if key.endswith("_ref"):
                continue
            next_path = f"{path}.{key}" if path else key
            if isinstance(value, str):
                ref_key = _expected_ref_key(key, schema_props, allow_fallback=allow_fallback)
                if ref_key:
                    ref_value = obj.get(ref_key)
                    if not _is_resolved_ref(ref_value):
                        kind = _kind_for_ref_key(ref_key)
                        if kind and value.strip():
                            unresolved.append((next_path, kind, value))
            child_schema = _schema_property(
                schema_node,
                key,
                schema_root_ctx,
                schema_registry=schema_registry,
                current_schema_uri=schema_uri_ctx,
            )
            child_schema_node: Any = None
            child_schema_root: dict[str, Any] | None = schema_root_ctx
            child_schema_uri: str | None = schema_uri_ctx
            if child_schema is not None:
                child_schema_node, child_schema_root, child_schema_uri = child_schema
            unresolved.extend(
                _collect_unresolved_candidates(
                    value,
                    child_schema_node,
                    next_path,
                    child_schema_root,
                    current_schema_uri=child_schema_uri,
                    schema_registry=schema_registry,
                    allow_fallback=allow_fallback,
                )
            )
    elif isinstance(obj, list):
        item_schema = _schema_items(
            schema_node,
            schema_root_ctx,
            schema_registry=schema_registry,
            current_schema_uri=schema_uri_ctx,
        )
        item_schema_node: Any = None
        item_schema_root: dict[str, Any] | None = schema_root_ctx
        item_schema_uri: str | None = schema_uri_ctx
        if item_schema is not None:
            item_schema_node, item_schema_root, item_schema_uri = item_schema
        for idx, value in enumerate(obj):
            next_path = f"{path}[{idx}]"
            unresolved.extend(
                _collect_unresolved_candidates(
                    value,
                    item_schema_node,
                    next_path,
                    item_schema_root,
                    current_schema_uri=item_schema_uri,
                    schema_registry=schema_registry,
                    allow_fallback=allow_fallback,
                )
            )
    return unresolved


def _expected_ref_key(key: str, schema_props: dict[str, Any], allow_fallback: bool) -> str | None:
    if not schema_props:
        if not allow_fallback:
            return None
        if key in _FALLBACK_DIRECT_FIELDS:
            return f"{key}_ref"
        return None
    direct = f"{key}_ref"
    if direct in schema_props:
        return direct
    mapped = _ALIASED_SOURCE_FIELDS.get(key)
    if mapped and mapped in schema_props:
        return mapped
    return None


def _is_resolved_ref(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    cid = value.get("id")
    return isinstance(cid, str) and cid.startswith("cn:")


def _kind_for_ref_key(ref_key: str) -> str | None:
    if ref_key.endswith("_ref"):
        return ref_key[: -len("_ref")]
    return None


def _proposal_index(value: Any) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    if not isinstance(value, list):
        return out
    for item in value:
        if not isinstance(item, dict):
            continue
        field = item.get("source_field")
        kind = item.get("kind")
        label = item.get("proposed_label")
        if isinstance(field, str) and isinstance(kind, str) and isinstance(label, str):
            out.add((field, kind, _norm_semantic(label)))
    return out


def _conflict_index(value: Any) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    if not isinstance(value, list):
        return out
    for item in value:
        if not isinstance(item, dict):
            continue
        field = item.get("field_path")
        label = item.get("input_value")
        if isinstance(field, str) and isinstance(label, str):
            out.add((field, _norm_semantic(label)))
    return out


def _norm_semantic(value: str) -> str:
    tokens = [part for part in re.split(r"[\s_-]+", value.strip().lower()) if part]
    return " ".join(tokens)


def _try_load_schema_registry(repo_root: str) -> tuple[SchemaRegistry | None, str | None]:
    try:
        return SchemaRegistry(repo_root), None
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        return None, f"schema_registry_bootstrap_failed detail={exc}"


def _load_document_schema(
    schema_registry: SchemaRegistry | None,
    data: Any,
    rel: str,
    schema_registry_error: str | None,
) -> tuple[dict[str, Any] | None, str | None, SpecError | None]:
    if not isinstance(data, dict):
        return None, None, None
    schema_uri = data.get("$schema")
    if schema_uri is None:
        return None, None, None
    if not isinstance(schema_uri, str) or not schema_uri.strip():
        return None, None, make_error("E520", f"UNRESOLVED_INPUT {rel} invalid_schema_uri")
    normalized_schema_uri = schema_uri.strip()
    if schema_registry is None:
        detail = schema_registry_error or "unknown"
        return None, normalized_schema_uri, make_error("E520", f"UNRESOLVED_INPUT {rel} schema_registry_bootstrap_failed uri={normalized_schema_uri} detail={detail}")
    try:
        schema = schema_registry.load(normalized_schema_uri)
    except FileNotFoundError as exc:
        return None, normalized_schema_uri, make_error("E520", f"UNRESOLVED_INPUT {rel} schema_not_found uri={normalized_schema_uri} detail={exc}")
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        return None, normalized_schema_uri, make_error("E520", f"UNRESOLVED_INPUT {rel} schema_load_failed uri={normalized_schema_uri} detail={exc}")
    if not isinstance(schema, dict):
        return None, normalized_schema_uri, make_error("E520", f"UNRESOLVED_INPUT {rel} schema_invalid_root uri={normalized_schema_uri}")
    return schema, normalized_schema_uri, None


def _resolve_schema_node(
    schema_node: Any,
    schema_root: dict[str, Any] | None,
    schema_registry: SchemaRegistry | None = None,
    current_schema_uri: str | None = None,
) -> tuple[Any, dict[str, Any] | None, str | None]:
    if not isinstance(schema_node, dict):
        return schema_node, schema_root, current_schema_uri
    ref = schema_node.get("$ref")
    if not isinstance(ref, str):
        return schema_node, schema_root, current_schema_uri
    if ref.startswith("#/") and isinstance(schema_root, dict):
        resolved = _resolve_json_pointer(schema_root, ref[1:])
        if resolved is not None:
            return resolved, schema_root, current_schema_uri
    resolved_uri, resolved_pointer = _resolve_ref_uri(ref, current_schema_uri)
    if schema_registry is not None and resolved_uri:
        resolved_schema = _load_schema_by_uri(schema_registry, resolved_uri)
        if isinstance(resolved_schema, dict):
            if not resolved_pointer:
                return resolved_schema, resolved_schema, resolved_uri
            if resolved_pointer.startswith("/"):
                resolved = _resolve_json_pointer(resolved_schema, resolved_pointer)
                if resolved is not None:
                    return resolved, resolved_schema, resolved_uri
    return schema_node, schema_root, current_schema_uri


def _resolve_json_pointer(doc: dict[str, Any], pointer: str) -> Any | None:
    node: Any = doc
    parts = [p for p in pointer.split("/") if p]
    for raw in parts:
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and key in node:
            node = node[key]
            continue
        if isinstance(node, list):
            try:
                idx = int(key)
            except ValueError:
                return None
            if 0 <= idx < len(node):
                node = node[idx]
                continue
        return None
    return node


def _schema_properties(
    schema_node: Any,
    schema_root: dict[str, Any] | None,
    schema_registry: SchemaRegistry | None = None,
    current_schema_uri: str | None = None,
) -> dict[str, Any]:
    props: dict[str, Any] = {}
    for candidate, _, _ in _schema_candidates(
        schema_node,
        schema_root,
        schema_registry=schema_registry,
        current_schema_uri=current_schema_uri,
    ):
        cand_props = candidate.get("properties")
        if isinstance(cand_props, dict):
            props.update(cand_props)
    return props


def _schema_property(
    schema_node: Any,
    key: str,
    schema_root: dict[str, Any] | None,
    schema_registry: SchemaRegistry | None = None,
    current_schema_uri: str | None = None,
) -> tuple[Any, dict[str, Any] | None, str | None] | None:
    for candidate, candidate_root, candidate_uri in _schema_candidates(
        schema_node,
        schema_root,
        schema_registry=schema_registry,
        current_schema_uri=current_schema_uri,
    ):
        cand_props = candidate.get("properties")
        if isinstance(cand_props, dict) and key in cand_props:
            return cand_props[key], candidate_root, candidate_uri
    return None


def _schema_items(
    schema_node: Any,
    schema_root: dict[str, Any] | None,
    schema_registry: SchemaRegistry | None = None,
    current_schema_uri: str | None = None,
) -> tuple[Any, dict[str, Any] | None, str | None] | None:
    for candidate, candidate_root, candidate_uri in _schema_candidates(
        schema_node,
        schema_root,
        schema_registry=schema_registry,
        current_schema_uri=current_schema_uri,
    ):
        if "items" in candidate:
            return candidate.get("items"), candidate_root, candidate_uri
    return None


def _schema_candidates(
    schema_node: Any,
    schema_root: dict[str, Any] | None,
    schema_registry: SchemaRegistry | None = None,
    current_schema_uri: str | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any] | None, str | None]]:
    resolved, resolved_root, resolved_uri = _resolve_schema_node(
        schema_node,
        schema_root,
        schema_registry=schema_registry,
        current_schema_uri=current_schema_uri,
    )
    if not isinstance(resolved, dict):
        return []
    out = [(resolved, resolved_root, resolved_uri)]
    for key in ("allOf", "anyOf", "oneOf"):
        values = resolved.get(key)
        if isinstance(values, list):
            for value in values:
                out.extend(
                    _schema_candidates(
                        value,
                        resolved_root,
                        schema_registry=schema_registry,
                        current_schema_uri=resolved_uri,
                    )
                )
    return out


def _resolve_ref_uri(ref: str, current_schema_uri: str | None) -> tuple[str | None, str]:
    if not isinstance(ref, str) or not ref:
        return None, ""
    if ref.startswith("#"):
        return current_schema_uri, ref[1:]
    absolute_ref = urljoin(current_schema_uri or "", ref)
    base_uri, fragment = urldefrag(absolute_ref)
    return (base_uri or None), f"/{fragment}" if fragment and not fragment.startswith("/") else fragment


def _load_schema_by_uri(schema_registry: SchemaRegistry, schema_uri: str) -> dict[str, Any] | None:
    try:
        schema = schema_registry.load(schema_uri)
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError, TypeError):
        return None
    if isinstance(schema, dict):
        return schema
    return None
