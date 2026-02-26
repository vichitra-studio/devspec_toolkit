from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CanonicalEntry:
    id: str
    kind: str
    version: str
    status: str
    payload: dict[str, Any]


class CanonicalRegistry:
    def __init__(
        self,
        entries: dict[str, CanonicalEntry],
        aliases: dict[tuple[str, str], set[str]],
        alias_status: dict[tuple[str, str], str],
        load_errors: list[str] | None = None,
    ):
        self.entries = entries
        self.aliases = aliases
        self.alias_status = alias_status
        self.load_errors = load_errors or []

    @classmethod
    def load(cls, repo_root: str, canon_dir: str = "canon") -> "CanonicalRegistry":
        root = Path(os.path.abspath(repo_root))
        manifest, load_errors = _load_merged_manifest(root, canon_dir=canon_dir)
        if manifest is None:
            return cls(entries={}, aliases={}, alias_status={}, load_errors=load_errors)
        return cls.from_manifest(manifest, load_errors=load_errors)

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any], load_errors: list[str] | None = None) -> "CanonicalRegistry":
        entries: dict[str, CanonicalEntry] = {}
        aliases: dict[tuple[str, str], set[str]] = {}
        alias_status: dict[tuple[str, str], str] = {}

        def register_alias(kind: str, alias_value: str, target_id: str, status: str = "active") -> None:
            if not isinstance(kind, str) or not isinstance(alias_value, str) or not isinstance(target_id, str):
                return
            normalized = _norm(alias_value)
            if not normalized:
                return
            key = (kind, normalized)
            aliases.setdefault(key, set()).add(target_id)
            current = alias_status.get(key)
            if current is None or status == "active":
                alias_status[key] = status

        for raw in manifest.get("entries", []):
            if not isinstance(raw, dict):
                continue
            entry_id = raw.get("id")
            kind = raw.get("kind")
            if not isinstance(entry_id, str) or not isinstance(kind, str):
                continue
            entry = CanonicalEntry(
                id=entry_id,
                kind=kind,
                version=raw.get("version", "0.0.0"),
                status=raw.get("status", "active"),
                payload=raw,
            )
            entries[entry.id] = entry
            preferred_label = raw.get("preferred_label")
            if isinstance(preferred_label, str):
                register_alias(entry.kind, preferred_label, entry.id, status="active")
            for alias in (raw.get("aliases", []) or []):
                if not isinstance(alias, str):
                    continue
                register_alias(entry.kind, alias, entry.id, status="active")

        for alias in manifest.get("aliases", []):
            if not isinstance(alias, dict):
                continue
            kind = alias.get("kind")
            normalized = alias.get("normalized")
            target_id = alias.get("target_id")
            if not isinstance(kind, str) or not isinstance(normalized, str) or not isinstance(target_id, str):
                continue
            register_alias(kind, normalized, target_id, status=alias.get("status", "active"))

        return cls(entries=entries, aliases=aliases, alias_status=alias_status, load_errors=load_errors)

    def get(self, canonical_id: str) -> CanonicalEntry | None:
        return self.entries.get(canonical_id)

    def resolve_alias(self, kind: str, value: str) -> str | None:
        key = (kind, _norm(value))
        targets = self.aliases.get(key, set())
        if len(targets) == 1:
            return next(iter(targets))
        return None

    def alias_candidates(self, kind: str, value: str) -> list[str]:
        return sorted(self.aliases.get((kind, _norm(value)), set()))

    def alias_is_deprecated(self, kind: str, value: str) -> bool:
        return self.alias_status.get((kind, _norm(value))) == "deprecated"

    def validate_ref(self, ref: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        cid = ref.get("id")
        kind = ref.get("kind")
        version = ref.get("version")
        alias_used = ref.get("alias_used")
        if not cid:
            return errs
        entry = self.get(cid)
        if not entry:
            errs.append(f"E110 UNKNOWN_CANONICAL_ID {cid}")
            return errs
        if kind and entry.kind != kind:
            errs.append(f"E120 CANONICAL_KIND_MISMATCH {cid} expected={entry.kind} got={kind}")
        if version and not _version_matches(entry.version, version):
            errs.append(f"E130 CANONICAL_VERSION_MISMATCH {cid} expected={version} got={entry.version}")
        if not version:
            errs.append(f"W130 CANONICAL_REF_VERSION_OMITTED {cid}")
        if entry.status == "deprecated":
            errs.append(f"W110 DEPRECATED_CANONICAL_USED {cid}")
        if kind and alias_used:
            candidates = self.alias_candidates(kind, alias_used)
            if len(candidates) > 1:
                errs.append(f"E140 AMBIGUOUS_ALIAS kind={kind} alias={alias_used} candidates={candidates}")
            elif self.alias_is_deprecated(kind, alias_used):
                errs.append(f"W120 ALIAS_DEPRECATED kind={kind} alias={alias_used}")
        return errs


def _norm(value: str) -> str:
    # Treat whitespace, underscores, and hyphens as equivalent separators.
    tokens = [part for part in re.split(r"[\s_-]+", (value or "").lower().strip()) if part]
    return " ".join(tokens)


def _version_matches(actual: str, expected: str) -> bool:
    if expected == actual:
        return True
    if expected.startswith("^"):
        prefix = expected[1:].split(".", 1)[0]
        return actual.startswith(prefix + ".")
    return False


def _load_merged_manifest(root: Path, canon_dir: str) -> tuple[dict[str, Any] | None, list[str]]:
    load_errors: list[str] = []
    manifest_path = root / canon_dir / "manifest.json"
    manifest = _read_json_file(manifest_path, load_errors, "invalid_manifest") if manifest_path.exists() else None
    modular = _load_modular_manifest(root / canon_dir, load_errors)
    if manifest is None and modular is None:
        return None, load_errors
    if manifest is None:
        return modular, load_errors
    if modular is None:
        return manifest, load_errors
    return _merge_manifest_data(manifest, modular), load_errors


def _load_modular_manifest(canon_root: Path, load_errors: list[str]) -> dict[str, Any] | None:
    aliases_path = canon_root / "aliases.json"
    aliases_doc = _read_json_file(aliases_path, load_errors, "invalid_aliases") if aliases_path.exists() else None

    kinds_dir = canon_root / "kinds"
    kind_docs: list[tuple[Path, dict[str, Any]]] = []
    if kinds_dir.exists() and kinds_dir.is_dir():
        for kind_file in sorted(kinds_dir.glob("*.json")):
            kind_doc = _read_json_file(kind_file, load_errors, "invalid_kind_file")
            if isinstance(kind_doc, dict):
                kind_docs.append((kind_file, kind_doc))

    if aliases_doc is None and not kind_docs:
        return None

    entries: list[dict[str, Any]] = []
    registry_version: str | None = None
    for kind_file, kind_doc in kind_docs:
        if registry_version is None and isinstance(kind_doc.get("registry_version"), str):
            registry_version = kind_doc["registry_version"]
        kind = kind_doc.get("kind")
        if not isinstance(kind, str) or not kind:
            load_errors.append(f"E520 UNRESOLVED_INPUT invalid_kind_file {kind_file} missing kind")
            continue
        raw_entries = kind_doc.get("entries")
        if not isinstance(raw_entries, list):
            load_errors.append(f"E520 UNRESOLVED_INPUT invalid_kind_file {kind_file} entries must be an array")
            continue
        for idx, raw in enumerate(raw_entries):
            if not isinstance(raw, dict):
                load_errors.append(f"E520 UNRESOLVED_INPUT invalid_kind_file {kind_file} entries[{idx}] must be an object")
                continue
            entry = dict(raw)
            entry_kind = entry.get("kind")
            if entry_kind is None:
                entry["kind"] = kind
            elif not isinstance(entry_kind, str) or entry_kind != kind:
                load_errors.append(
                    f"E520 UNRESOLVED_INPUT invalid_kind_file {kind_file} entries[{idx}] kind mismatch expected={kind} got={entry_kind}"
                )
                continue
            entries.append(entry)

    aliases: list[dict[str, Any]] = []
    if isinstance(aliases_doc, dict):
        if registry_version is None and isinstance(aliases_doc.get("registry_version"), str):
            registry_version = aliases_doc["registry_version"]
        raw_aliases = aliases_doc.get("aliases")
        if not isinstance(raw_aliases, list):
            load_errors.append(f"E520 UNRESOLVED_INPUT invalid_aliases {aliases_path} aliases must be an array")
            raw_aliases = []
        for idx, raw_alias in enumerate(raw_aliases):
            if not isinstance(raw_alias, dict):
                load_errors.append(f"E520 UNRESOLVED_INPUT invalid_aliases {aliases_path} aliases[{idx}] must be an object")
                continue
            aliases.append(raw_alias)

    return {
        "registry_version": registry_version or "1.0.0",
        "entries": entries,
        "aliases": aliases,
    }


def _merge_manifest_data(manifest: dict[str, Any], modular: dict[str, Any]) -> dict[str, Any]:
    entries_by_id: dict[str, dict[str, Any]] = {}
    for raw in _iter_dicts(manifest.get("entries", [])):
        entry_id = raw.get("id")
        if isinstance(entry_id, str) and entry_id:
            entries_by_id[entry_id] = dict(raw)
    for raw in _iter_dicts(modular.get("entries", [])):
        entry_id = raw.get("id")
        if isinstance(entry_id, str) and entry_id:
            entries_by_id[entry_id] = dict(raw)

    aliases_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for raw in _iter_dicts(manifest.get("aliases", [])):
        key = _alias_key(raw)
        if key is not None:
            aliases_by_key[key] = dict(raw)
    for raw in _iter_dicts(modular.get("aliases", [])):
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


def _read_json_file(path: Path, load_errors: list[str], error_kind: str) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        load_errors.append(f"E520 UNRESOLVED_INPUT {error_kind} {path} {exc}")
        return None
    if not isinstance(data, dict):
        load_errors.append(f"E520 UNRESOLVED_INPUT {error_kind} {path} root must be an object")
        return None
    return data


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
