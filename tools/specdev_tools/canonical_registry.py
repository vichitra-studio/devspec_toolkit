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
    ):
        self.entries = entries
        self.aliases = aliases
        self.alias_status = alias_status

    @classmethod
    def load(cls, repo_root: str, canon_dir: str = "canon") -> "CanonicalRegistry":
        root = Path(os.path.abspath(repo_root))
        manifest_path = root / canon_dir / "manifest.json"
        if not manifest_path.exists():
            return cls(entries={}, aliases={}, alias_status={})
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_manifest(data)

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> "CanonicalRegistry":
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

        return cls(entries=entries, aliases=aliases, alias_status=alias_status)

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
