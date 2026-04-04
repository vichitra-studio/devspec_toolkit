from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.errors import SpecError, make_error


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
        load_errors: list[SpecError] | None = None,
        alias_lifecycle: dict[tuple[str, str], dict] | None = None,
    ):
        self.entries = entries
        self.aliases = aliases
        self.alias_status = alias_status
        self.load_errors: list[SpecError] = load_errors or []
        self.alias_lifecycle = alias_lifecycle or {}

    @classmethod
    def load(
        cls,
        repo_root: str,
        canon_dir: str = "canon",
        project_canon_dir: str | None = None,
    ) -> "CanonicalRegistry":
        root = Path(os.path.abspath(repo_root))
        manifest, load_errors = _load_merged_manifest(root, canon_dir=canon_dir)

        if project_canon_dir is not None:
            project_path = Path(os.path.abspath(project_canon_dir))
            if project_path.is_dir():
                project_manifest, project_errors = _load_merged_manifest(
                    project_path.parent, canon_dir=project_path.name,
                )
                load_errors.extend(project_errors)
                if project_manifest is not None:
                    if manifest is None:
                        manifest = project_manifest
                    else:
                        # Detect collisions before merging (project wins)
                        core_ids = {
                            e.get("id")
                            for e in manifest.get("entries", [])
                            if isinstance(e, dict) and isinstance(e.get("id"), str)
                        }
                        for entry in project_manifest.get("entries", []):
                            if isinstance(entry, dict):
                                eid = entry.get("id")
                                if isinstance(eid, str) and eid in core_ids:
                                    load_errors.append(
                                        make_error(
                                            "W421",
                                            f"CANON_ID_COLLISION_PROJECT_WINS id={eid} (project entry overrides core)",
                                        )
                                    )
                        manifest = _merge_manifest_data(manifest, project_manifest)

        if manifest is None:
            return cls(entries={}, aliases={}, alias_status={}, load_errors=load_errors)
        return cls.from_manifest(manifest, load_errors=load_errors)

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any], load_errors: list[SpecError] | None = None) -> "CanonicalRegistry":
        entries: dict[str, CanonicalEntry] = {}
        aliases: dict[tuple[str, str], set[str]] = {}
        alias_status: dict[tuple[str, str], str] = {}
        alias_lifecycle: dict[tuple[str, str], dict] = {}

        def register_alias(kind: str, alias_value: str, target_id: str, status: str = "active") -> None:
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
            lc = alias.get("lifecycle")
            if isinstance(lc, dict):
                alias_lifecycle[(kind, _norm(normalized))] = lc

        return cls(entries=entries, aliases=aliases, alias_status=alias_status, load_errors=load_errors, alias_lifecycle=alias_lifecycle)

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

    def alias_is_sunset(self, kind: str, value: str) -> bool:
        key = (kind, _norm(value))
        lc = self.alias_lifecycle.get(key)
        if not isinstance(lc, dict):
            return False
        sd = lc.get("sunset_date")
        if not isinstance(sd, str):
            return False
        try:
            sunset = datetime.fromisoformat(sd.replace("Z", "+00:00"))
            if sunset.tzinfo is None:
                sunset = sunset.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) >= sunset
        except (ValueError, TypeError):
            return False

    def validate_ref(self, ref: dict[str, Any]) -> list[SpecError]:
        errs: list[SpecError] = []
        cid = ref.get("id")
        kind = ref.get("kind")
        version = ref.get("version")
        alias_used = ref.get("alias_used")
        if not cid:
            return errs
        entry = self.get(cid)
        if not entry:
            errs.append(make_error("E110", f"UNKNOWN_CANONICAL_ID {cid}"))
            return errs
        if kind and entry.kind != kind:
            errs.append(make_error("E120", f"CANONICAL_KIND_MISMATCH {cid} expected={entry.kind} got={kind}"))
        if version and not _version_matches(entry.version, version):
            errs.append(make_error("E130", f"CANONICAL_VERSION_MISMATCH {cid} expected={version} got={entry.version}"))
        if not version:
            errs.append(make_error("W130", f"CANONICAL_REF_VERSION_OMITTED {cid}"))
        if entry.status == "deprecated":
            errs.append(make_error("W110", f"DEPRECATED_CANONICAL_USED {cid}"))
        if kind and alias_used:
            candidates = self.alias_candidates(kind, alias_used)
            if len(candidates) > 1:
                errs.append(make_error("E140", f"AMBIGUOUS_ALIAS kind={kind} alias={alias_used} candidates={candidates}"))
            elif self.alias_is_deprecated(kind, alias_used):
                lc = self.alias_lifecycle.get((kind, _norm(alias_used)), {})
                replaced_by = lc.get("replaced_by", "")
                if self.alias_is_sunset(kind, alias_used):
                    errs.append(make_error("E125", f"ALIAS_SUNSET_EXPIRED kind={kind} alias={alias_used} replaced_by={replaced_by}"))
                else:
                    errs.append(make_error("W120", f"ALIAS_DEPRECATED kind={kind} alias={alias_used} replaced_by={replaced_by}"))
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


def _load_merged_manifest(root: Path, canon_dir: str) -> tuple[dict[str, Any] | None, list[SpecError]]:
    load_errors: list[SpecError] = []
    manifest_path = root / canon_dir / "manifest.json"
    manifest = _read_json_file(manifest_path, load_errors, "invalid_manifest") if manifest_path.exists() else None
    modular = _load_modular_manifest(root / canon_dir, load_errors)
    if manifest is None and modular is None:
        combined = None
    elif manifest is None:
        combined = modular
    elif modular is None:
        combined = manifest
    else:
        combined = _merge_manifest_data(manifest, modular)

    examples = _load_examples_manifests(root / canon_dir, load_errors)
    if examples is None:
        return combined, load_errors
    if combined is None:
        return examples, load_errors
    # Manifest/modular entries take precedence over examples entries.
    return _merge_manifest_data(examples, combined), load_errors


def _load_examples_manifests(canon_root: Path, load_errors: list[SpecError]) -> dict[str, Any] | None:
    examples_dir = canon_root / "examples"
    if not examples_dir.exists() or not examples_dir.is_dir():
        return None

    all_entries: list[dict[str, Any]] = []
    all_aliases: list[dict[str, Any]] = []
    found_any = False

    for example_file in sorted(examples_dir.glob("*.json")):
        doc = _read_json_file(example_file, load_errors, "invalid_examples_file")
        if not isinstance(doc, dict):
            continue
        raw_entries = doc.get("entries")
        if isinstance(raw_entries, list):
            for item in raw_entries:
                if isinstance(item, dict):
                    all_entries.append(item)
            found_any = True
        raw_aliases = doc.get("aliases")
        if isinstance(raw_aliases, list):
            for item in raw_aliases:
                if isinstance(item, dict):
                    all_aliases.append(item)

    if not found_any:
        return None

    return {
        "registry_version": "1.0.0",
        "entries": all_entries,
        "aliases": all_aliases,
    }


def _load_modular_manifest(canon_root: Path, load_errors: list[SpecError]) -> dict[str, Any] | None:
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
            load_errors.append(make_error("E520", f"UNRESOLVED_INPUT invalid_kind_file {kind_file} missing kind"))
            continue
        raw_entries = kind_doc.get("entries")
        if not isinstance(raw_entries, list):
            load_errors.append(make_error("E520", f"UNRESOLVED_INPUT invalid_kind_file {kind_file} entries must be an array"))
            continue
        for idx, raw in enumerate(raw_entries):
            if not isinstance(raw, dict):
                load_errors.append(make_error("E520", f"UNRESOLVED_INPUT invalid_kind_file {kind_file} entries[{idx}] must be an object"))
                continue
            entry = dict(raw)
            entry_kind = entry.get("kind")
            if entry_kind is None:
                entry["kind"] = kind
            elif not isinstance(entry_kind, str) or entry_kind != kind:
                load_errors.append(
                    make_error("E520", f"UNRESOLVED_INPUT invalid_kind_file {kind_file} entries[{idx}] kind mismatch expected={kind} got={entry_kind}")
                )
                continue
            entries.append(entry)

    aliases: list[dict[str, Any]] = []
    if isinstance(aliases_doc, dict):
        if registry_version is None and isinstance(aliases_doc.get("registry_version"), str):
            registry_version = aliases_doc["registry_version"]
        raw_aliases = aliases_doc.get("aliases")
        if not isinstance(raw_aliases, list):
            load_errors.append(make_error("E520", f"UNRESOLVED_INPUT invalid_aliases {aliases_path} aliases must be an array"))
            raw_aliases = []
        for idx, raw_alias in enumerate(raw_aliases):
            if not isinstance(raw_alias, dict):
                load_errors.append(make_error("E520", f"UNRESOLVED_INPUT invalid_aliases {aliases_path} aliases[{idx}] must be an object"))
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


def _read_json_file(path: Path, load_errors: list[SpecError], error_kind: str) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        load_errors.append(make_error("E520", f"UNRESOLVED_INPUT {error_kind} {path} {exc}"))
        return None
    if not isinstance(data, dict):
        load_errors.append(make_error("E520", f"UNRESOLVED_INPUT {error_kind} {path} root must be an object"))
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
