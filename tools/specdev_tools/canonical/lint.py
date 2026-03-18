"""Canonical registry structural lint.

Validates the canonical registry directory (manifest.json, aliases.json,
kinds/*.json) for structural correctness: valid JSON, required fields,
duplicate IDs, alias collisions, and lifecycle consistency.

This module is concerned with the *internal* consistency of canonical
documents.  It does NOT check whether spec artifacts actually reference
canonical IDs correctly — that cross-artifact integrity check lives in
``integrity.py``, which calls ``lint_canon_dir`` as a preflight gate
before scanning spec files.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import _WrappedReferencingError  # type: ignore[attr-defined]
from referencing import Registry, Resource

from ..core.errors import SpecError, make_error
from ..core.registry import SchemaRegistry

CANON_ALIASES_SCHEMA_URI = "https://specdev.local/schema/canon/aliases/1"
CANON_KIND_SCHEMA_URI = "https://specdev.local/schema/canon/kind/1"
CANON_MANIFEST_SCHEMA_URI = "https://specdev.local/schema/core/canon/1"


def lint_canon_dir(
    repo_root: str,
    canon_dir: str = "canon",
    require_manifest_schema_registration: bool = True,
) -> list[SpecError]:
    root = Path(os.path.abspath(repo_root))
    canon_root = root / canon_dir
    manifest_path = root / canon_dir / "manifest.json"
    aliases_path = canon_root / "aliases.json"
    kinds_dir = canon_root / "kinds"
    registry_path = root / "tools" / "schema_registry.json"
    fallback_registry_path = root / "schema_registry.json"

    errs: list[SpecError] = []
    manifest = _load_json_object(manifest_path, "invalid_manifest", errs) if manifest_path.exists() else None
    aliases_doc = _load_json_object(aliases_path, "invalid_aliases", errs) if aliases_path.exists() else None
    kind_docs = _load_kind_docs(kinds_dir, errs) if kinds_dir.exists() else []
    canonical_docs_present = manifest is not None or aliases_doc is not None or bool(kind_docs)

    schema_registry = _load_schema_registry_if_available(root, errs)
    if (
        require_manifest_schema_registration
        and canonical_docs_present
        and schema_registry is None
        and not registry_path.exists()
        and not fallback_registry_path.exists()
    ):
        errs.append(
            make_error("E520", f"UNRESOLVED_INPUT missing_schema_registry checked={registry_path},{fallback_registry_path}")
        )
    if schema_registry is not None:
        if manifest is not None:
            if _schema_uri_registered(schema_registry, CANON_MANIFEST_SCHEMA_URI):
                errs.extend(_validate_doc_schema(schema_registry, manifest, manifest_path, CANON_MANIFEST_SCHEMA_URI))
            elif require_manifest_schema_registration:
                errs.append(
                    make_error("E520", f"UNRESOLVED_INPUT schema_uri_not_registered uri={CANON_MANIFEST_SCHEMA_URI} file={manifest_path}")
                )
        if aliases_doc is not None:
            errs.extend(_validate_doc_schema(schema_registry, aliases_doc, aliases_path, CANON_ALIASES_SCHEMA_URI))
        for kind_file, kind_doc in kind_docs:
            errs.extend(_validate_doc_schema(schema_registry, kind_doc, kind_file, CANON_KIND_SCHEMA_URI))

    modular_present = aliases_doc is not None or bool(kind_docs)
    if not manifest_path.exists() and not modular_present:
        if errs:
            return errs
        return [make_error("E520", f"UNRESOLVED_INPUT missing {manifest_path}")]
    if manifest is None and manifest_path.exists() and not modular_present:
        return errs

    modular_manifest = _compose_modular_manifest(aliases_doc, aliases_path, kind_docs, errs) if modular_present else None

    if manifest is not None and modular_manifest is not None:
        errs.extend(_detect_manifest_modular_drift(manifest, modular_manifest))
        merged = _merge_manifest_data(manifest, modular_manifest)
    elif manifest is not None:
        merged = manifest
    elif modular_manifest is not None:
        merged = modular_manifest
    else:
        merged = {"registry_version": "1.0.0", "entries": [], "aliases": []}

    errs.extend(lint_manifest(merged))
    return errs


def lint_manifest(manifest: dict[str, Any]) -> list[SpecError]:
    if not isinstance(manifest, dict):
        return [make_error("E520", "UNRESOLVED_INPUT manifest root must be an object")]
    errs: list[SpecError] = []
    seen_ids: set[str] = set()
    seen_aliases: set[tuple[str, str]] = set()
    known_ids: set[str] = set()
    entry_alias_targets: dict[tuple[str, str], set[str]] = {}

    entries = manifest.get("entries", [])
    if not isinstance(entries, list):
        return [make_error("E520", "UNRESOLVED_INPUT manifest.entries must be an array")]
    aliases = manifest.get("aliases", [])
    if not isinstance(aliases, list):
        return [make_error("E520", "UNRESOLVED_INPUT manifest.aliases must be an array")]

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errs.append(make_error("E520", f"UNRESOLVED_INPUT manifest.entries[{i}] must be an object"))
            continue
        cid_raw = entry.get("id")
        cid: str | None = None
        if not isinstance(cid_raw, str) or not cid_raw:
            errs.append(make_error("E520", f"UNRESOLVED_INPUT manifest.entries[{i}] missing id"))
        else:
            cid = cid_raw
            if cid in seen_ids:
                errs.append(make_error("E410", f"CANONICAL_ALIAS_COLLISION duplicate id={cid}"))
            seen_ids.add(cid)
            known_ids.add(cid)
        kind_raw = entry.get("kind")
        kind: str | None = None
        if not isinstance(kind_raw, str) or not kind_raw:
            errs.append(make_error("E520", f"UNRESOLVED_INPUT manifest.entries[{i}] missing kind"))
        else:
            kind = kind_raw
        errs.extend(_validate_lifecycle(entry))
        entry_label = cid if cid is not None else f"manifest.entries[{i}]"
        raw_aliases = entry.get("aliases", [])
        if raw_aliases is None:
            raw_aliases = []
        if not isinstance(raw_aliases, list):
            errs.append(make_error("E520", f"UNRESOLVED_INPUT entry {entry_label} aliases must be an array"))
            raw_aliases = []
        for alias in raw_aliases:
            if not isinstance(alias, str):
                errs.append(make_error("E520", f"UNRESOLVED_INPUT entry {entry_label} alias values must be strings"))
                continue
            if kind is None or cid is None:
                continue
            key = (kind, _norm(alias))
            entry_alias_targets.setdefault(key, set()).add(cid)

    for i, alias in enumerate(aliases):
        if not isinstance(alias, dict):
            errs.append(make_error("E520", f"UNRESOLVED_INPUT manifest.aliases[{i}] must be an object"))
            continue
        kind_raw = alias.get("kind")
        if not isinstance(kind_raw, str) or not kind_raw:
            errs.append(make_error("E520", f"UNRESOLVED_INPUT manifest.aliases[{i}] missing kind"))
            continue
        normalized_raw = alias.get("normalized")
        if not isinstance(normalized_raw, str) or not normalized_raw.strip():
            errs.append(make_error("E520", f"UNRESOLVED_INPUT manifest.aliases[{i}] missing normalized"))
            continue
        target = alias.get("target_id")
        if not isinstance(target, str) or not target:
            errs.append(make_error("E520", f"UNRESOLVED_INPUT manifest.aliases[{i}] missing target_id"))
            continue
        status = alias.get("status")
        if not isinstance(status, str) or not status:
            errs.append(make_error("E520", f"UNRESOLVED_INPUT manifest.aliases[{i}] missing status"))
            continue

        kind = kind_raw
        normalized = _norm(normalized_raw)
        key = (kind, normalized)
        if status == "active":
            if key in seen_aliases:
                errs.append(make_error("E410", f"CANONICAL_ALIAS_COLLISION kind={kind} alias={normalized}"))
            seen_aliases.add(key)
            entry_alias_targets.setdefault(key, set()).add(target)
        if target and target not in known_ids:
            errs.append(make_error("E110", f"UNKNOWN_CANONICAL_ID alias target={target}"))
        has_deprecated_since = alias.get("deprecated_since") or (
            isinstance(alias.get("lifecycle"), dict) and alias["lifecycle"].get("deprecated_since")
        )
        if status == "deprecated" and not has_deprecated_since:
            errs.append(make_error("E420", f"INVALID_DEPRECATION_LIFECYCLE alias={normalized} missing deprecated_since"))

    for key, targets in entry_alias_targets.items():
        clean_targets = {t for t in targets if t}
        if len(clean_targets) > 1:
            errs.append(make_error("E410", f"CANONICAL_ALIAS_COLLISION kind={key[0]} alias={key[1]} targets={sorted(clean_targets)}"))

    return errs


def _validate_lifecycle(entry: dict[str, Any]) -> list[SpecError]:
    errs: list[SpecError] = []
    status = entry.get("status")
    lifecycle = entry.get("lifecycle", {}) or {}
    if not lifecycle.get("introduced_at"):
        errs.append(make_error("E420", f"INVALID_DEPRECATION_LIFECYCLE id={entry.get('id')} missing introduced_at"))
    if status in {"deprecated", "sunset"} and not lifecycle.get("deprecated_since"):
        errs.append(make_error("E420", f"INVALID_DEPRECATION_LIFECYCLE id={entry.get('id')} missing deprecated_since"))
    if status == "sunset" and not lifecycle.get("sunset_after"):
        errs.append(make_error("E420", f"INVALID_DEPRECATION_LIFECYCLE id={entry.get('id')} missing sunset_after"))
    if status == "retired" and not lifecycle.get("retired_at"):
        errs.append(make_error("E420", f"INVALID_DEPRECATION_LIFECYCLE id={entry.get('id')} missing retired_at"))
    return errs


def _norm(value: str) -> str:
    tokens = [part for part in re.split(r"[\s_-]+", (value or "").strip().lower()) if part]
    return " ".join(tokens)


def _load_json_object(path: Path, error_kind: str, errs: list[SpecError]) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        errs.append(make_error("E520", f"UNRESOLVED_INPUT {error_kind} {path} {exc}"))
        return None
    if not isinstance(data, dict):
        errs.append(make_error("E520", f"UNRESOLVED_INPUT {error_kind} {path} root must be an object"))
        return None
    return data


def _load_kind_docs(kinds_dir: Path, errs: list[SpecError]) -> list[tuple[Path, dict[str, Any]]]:
    docs: list[tuple[Path, dict[str, Any]]] = []
    if not kinds_dir.is_dir():
        errs.append(make_error("E520", f"UNRESOLVED_INPUT invalid_kinds_dir {kinds_dir}"))
        return docs
    for kind_file in sorted(kinds_dir.glob("*.json")):
        doc = _load_json_object(kind_file, "invalid_kind_file", errs)
        if doc is None:
            continue
        docs.append((kind_file, doc))
    return docs


def _compose_modular_manifest(
    aliases_doc: dict[str, Any] | None,
    aliases_path: Path,
    kind_docs: list[tuple[Path, dict[str, Any]]],
    errs: list[SpecError],
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    registry_version: str | None = None

    for kind_file, doc in kind_docs:
        kind = doc.get("kind")
        if registry_version is None and isinstance(doc.get("registry_version"), str):
            registry_version = doc["registry_version"]
        if not isinstance(kind, str) or not kind:
            errs.append(make_error("E520", f"UNRESOLVED_INPUT invalid_kind_file {kind_file} missing kind"))
            continue
        raw_entries = doc.get("entries")
        if not isinstance(raw_entries, list):
            errs.append(make_error("E520", f"UNRESOLVED_INPUT invalid_kind_file {kind_file} entries must be an array"))
            continue
        for idx, raw in enumerate(raw_entries):
            if not isinstance(raw, dict):
                errs.append(make_error("E520", f"UNRESOLVED_INPUT invalid_kind_file {kind_file} entries[{idx}] must be an object"))
                continue
            entry = dict(raw)
            entry_kind = entry.get("kind")
            if entry_kind is None:
                entry["kind"] = kind
            elif entry_kind != kind:
                errs.append(
                    make_error("E520", f"UNRESOLVED_INPUT invalid_kind_file {kind_file} entries[{idx}] kind mismatch expected={kind} got={entry_kind}")
                )
                continue
            entries.append(entry)

    aliases: list[dict[str, Any]] = []
    if aliases_doc is not None:
        if registry_version is None and isinstance(aliases_doc.get("registry_version"), str):
            registry_version = aliases_doc["registry_version"]
        raw_aliases = aliases_doc.get("aliases")
        if not isinstance(raw_aliases, list):
            errs.append(make_error("E520", f"UNRESOLVED_INPUT invalid_aliases {aliases_path} aliases must be an array"))
            raw_aliases = []
        for idx, raw in enumerate(raw_aliases):
            if not isinstance(raw, dict):
                errs.append(make_error("E520", f"UNRESOLVED_INPUT invalid_aliases aliases[{idx}] must be an object"))
                continue
            aliases.append(dict(raw))

    return {
        "registry_version": registry_version or "1.0.0",
        "entries": entries,
        "aliases": aliases,
    }


def _merge_manifest_data(manifest: dict[str, Any], modular: dict[str, Any]) -> dict[str, Any]:
    entries_by_id: dict[str, dict[str, Any]] = {}
    for raw in _iter_dicts(manifest.get("entries")):
        entry_id = raw.get("id")
        if isinstance(entry_id, str) and entry_id:
            entries_by_id[entry_id] = dict(raw)
    for raw in _iter_dicts(modular.get("entries")):
        entry_id = raw.get("id")
        if isinstance(entry_id, str) and entry_id:
            entries_by_id[entry_id] = dict(raw)

    aliases_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for raw in _iter_dicts(manifest.get("aliases")):
        key = _alias_key(raw)
        if key is not None:
            aliases_by_key[key] = dict(raw)
    for raw in _iter_dicts(modular.get("aliases")):
        key = _alias_key(raw)
        if key is not None:
            aliases_by_key[key] = dict(raw)

    merged = dict(manifest)
    merged["registry_version"] = (
        modular.get("registry_version")
        if isinstance(modular.get("registry_version"), str)
        else manifest.get("registry_version", "1.0.0")
    )
    merged["entries"] = [entries_by_id[k] for k in sorted(entries_by_id.keys())]
    merged["aliases"] = [aliases_by_key[k] for k in sorted(aliases_by_key.keys())]
    return merged


def _detect_manifest_modular_drift(manifest: dict[str, Any], modular: dict[str, Any]) -> list[SpecError]:
    errs: list[SpecError] = []
    manifest_entries = _entries_by_id(manifest.get("entries"))
    modular_entries = _entries_by_id(modular.get("entries"))
    if set(manifest_entries.keys()) != set(modular_entries.keys()):
        only_manifest = sorted(set(manifest_entries.keys()) - set(modular_entries.keys()))
        only_modular = sorted(set(modular_entries.keys()) - set(manifest_entries.keys()))
        errs.append(
            make_error("E210", f"CROSS_ARTIFACT_DRIFT canonical_manifest_modular_mismatch entries only_manifest={only_manifest} only_modular={only_modular}")
        )
    for entry_id in sorted(set(manifest_entries.keys()) & set(modular_entries.keys())):
        if _json_sig(manifest_entries[entry_id]) != _json_sig(modular_entries[entry_id]):
            errs.append(
                make_error("E210", f"CROSS_ARTIFACT_DRIFT canonical_manifest_modular_mismatch entry={entry_id}")
            )

    manifest_aliases = _effective_alias_signatures(manifest)
    modular_aliases = _effective_alias_signatures(modular)
    if manifest_aliases != modular_aliases:
        errs.append(
            make_error("E210", "CROSS_ARTIFACT_DRIFT canonical_manifest_modular_mismatch aliases differ")
        )
    return errs


def _entries_by_id(entries: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for entry in _iter_dicts(entries):
        entry_id = entry.get("id")
        if isinstance(entry_id, str) and entry_id:
            out[entry_id] = entry
    return out


def _iter_dicts(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, dict)]


def _alias_key(alias: dict[str, Any]) -> tuple[str, str, str, str] | None:
    kind = alias.get("kind")
    normalized = alias.get("normalized")
    target_id = alias.get("target_id")
    status = alias.get("status", "active")
    if not isinstance(kind, str) or not isinstance(normalized, str) or not isinstance(target_id, str):
        return None
    return (kind, _norm(normalized), target_id, str(status))


def _alias_signature(alias: dict[str, Any]) -> str:
    normalized = dict(alias)
    if isinstance(normalized.get("normalized"), str):
        normalized["normalized"] = _norm(normalized["normalized"])
    return _json_sig(normalized)


def _json_sig(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _effective_alias_signatures(manifest: dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    for entry in _iter_dicts(manifest.get("entries")):
        kind = entry.get("kind")
        entry_id = entry.get("id")
        if not isinstance(kind, str) or not isinstance(entry_id, str):
            continue
        preferred_label = entry.get("preferred_label")
        if isinstance(preferred_label, str):
            aliases.add(
                _json_sig(
                    {
                        "kind": kind,
                        "normalized": _norm(preferred_label),
                        "target_id": entry_id,
                        "status": "active",
                    }
                )
            )
        raw_aliases = entry.get("aliases")
        if isinstance(raw_aliases, list):
            for alias in raw_aliases:
                if isinstance(alias, str):
                    aliases.add(
                        _json_sig(
                            {
                                "kind": kind,
                                "normalized": _norm(alias),
                                "target_id": entry_id,
                                "status": "active",
                            }
                        )
                    )
    for alias in _iter_dicts(manifest.get("aliases")):
        aliases.add(_alias_signature(alias))
    return aliases


def _load_schema_registry_if_available(root: Path, errs: list[SpecError]) -> SchemaRegistry | None:
    registry_path = root / "tools" / "schema_registry.json"
    fallback_path = root / "schema_registry.json"
    if not registry_path.exists() and not fallback_path.exists():
        return None
    try:
        return SchemaRegistry(str(root))
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        errs.append(make_error("E520", f"UNRESOLVED_INPUT schema_registry_bootstrap_failed detail={exc}"))
        return None


def _validate_doc_schema(
    schema_registry: SchemaRegistry,
    data: dict[str, Any],
    path: Path,
    schema_uri: str,
) -> list[SpecError]:
    errs: list[SpecError] = []
    try:
        schema = schema_registry.load(schema_uri)
    except FileNotFoundError as exc:
        return [make_error("E520", f"UNRESOLVED_INPUT schema_not_found uri={schema_uri} detail={exc}")]
    except json.JSONDecodeError as exc:
        return [make_error("E520", f"UNRESOLVED_INPUT schema_json_decode_failed uri={schema_uri} detail={exc}")]

    reg = _jsonschema_registry(schema_registry)
    validator = Draft202012Validator(
        schema,
        registry=reg,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    try:
        validation_errors = sorted(validator.iter_errors(data), key=lambda e: tuple(e.path))
    except _WrappedReferencingError as exc:
        return [make_error("E520", f"UNRESOLVED_INPUT schema_reference_resolution_failed uri={schema_uri} detail={exc}")]
    except Exception as exc:
        return [make_error("E521", f"VALIDATOR_RUNTIME {path}: schema_validation_runtime_error {type(exc).__name__}: {exc}")]

    for error in validation_errors:
        error_path = "/".join(str(p) for p in error.path)
        errs.append(
            make_error("E520", f"UNRESOLVED_INPUT schema_invalid {path} uri={schema_uri} path={error_path or '$'} detail={error.message}")
        )
    return errs


def _jsonschema_registry(schema_registry: SchemaRegistry) -> Registry:
    store = {uri: Resource.from_contents(schema) for uri, schema in schema_registry.store.items()}
    return Registry().with_resources(store.items())


def _schema_uri_registered(schema_registry: SchemaRegistry, schema_uri: str) -> bool:
    return schema_uri in schema_registry.map
