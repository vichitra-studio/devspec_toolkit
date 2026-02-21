from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def lint_canon_dir(repo_root: str, canon_dir: str = "canon") -> list[str]:
    root = Path(os.path.abspath(repo_root))
    manifest_path = root / canon_dir / "manifest.json"
    if not manifest_path.exists():
        return [f"E520 UNRESOLVED_INPUT missing {manifest_path}"]
    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"E520 UNRESOLVED_INPUT invalid_manifest {manifest_path} {exc}"]
    return lint_manifest(manifest)


def lint_manifest(manifest: dict[str, Any]) -> list[str]:
    if not isinstance(manifest, dict):
        return ["E520 UNRESOLVED_INPUT manifest root must be an object"]
    errs: list[str] = []
    seen_ids: set[str] = set()
    seen_aliases: set[tuple[str, str]] = set()
    known_ids: set[str] = set()
    entry_alias_targets: dict[tuple[str, str], set[str]] = {}

    entries = manifest.get("entries", [])
    if not isinstance(entries, list):
        return ["E520 UNRESOLVED_INPUT manifest.entries must be an array"]
    aliases = manifest.get("aliases", [])
    if not isinstance(aliases, list):
        return ["E520 UNRESOLVED_INPUT manifest.aliases must be an array"]

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errs.append(f"E520 UNRESOLVED_INPUT manifest.entries[{i}] must be an object")
            continue
        cid = entry.get("id")
        if cid in seen_ids:
            errs.append(f"E410 CANONICAL_ALIAS_COLLISION duplicate id={cid}")
        seen_ids.add(cid)
        known_ids.add(cid)
        errs.extend(_validate_lifecycle(entry))
        raw_aliases = entry.get("aliases", [])
        if raw_aliases is None:
            raw_aliases = []
        if not isinstance(raw_aliases, list):
            errs.append(f"E520 UNRESOLVED_INPUT entry {cid} aliases must be an array")
            raw_aliases = []
        for alias in raw_aliases:
            if not isinstance(alias, str):
                errs.append(f"E520 UNRESOLVED_INPUT entry {cid} alias values must be strings")
                continue
            key = (entry.get("kind", ""), _norm(alias))
            entry_alias_targets.setdefault(key, set()).add(cid)

    for i, alias in enumerate(aliases):
        if not isinstance(alias, dict):
            errs.append(f"E520 UNRESOLVED_INPUT manifest.aliases[{i}] must be an object")
            continue
        kind = alias.get("kind", "")
        normalized = _norm(alias.get("normalized", ""))
        key = (kind, normalized)
        if alias.get("status") == "active":
            if key in seen_aliases:
                errs.append(f"E410 CANONICAL_ALIAS_COLLISION kind={kind} alias={normalized}")
            seen_aliases.add(key)
            entry_alias_targets.setdefault(key, set()).add(alias.get("target_id"))
        target = alias.get("target_id")
        if target and target not in known_ids:
            errs.append(f"E110 UNKNOWN_CANONICAL_ID alias target={target}")
        if alias.get("status") == "deprecated" and not alias.get("deprecated_since"):
            errs.append(f"E420 INVALID_DEPRECATION_LIFECYCLE alias={normalized} missing deprecated_since")

    for key, targets in entry_alias_targets.items():
        clean_targets = {t for t in targets if t}
        if len(clean_targets) > 1:
            errs.append(f"E410 CANONICAL_ALIAS_COLLISION kind={key[0]} alias={key[1]} targets={sorted(clean_targets)}")

    return errs


def _validate_lifecycle(entry: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    status = entry.get("status")
    lifecycle = entry.get("lifecycle", {}) or {}
    if not lifecycle.get("introduced_at"):
        errs.append(f"E420 INVALID_DEPRECATION_LIFECYCLE id={entry.get('id')} missing introduced_at")
    if status in {"deprecated", "sunset"} and not lifecycle.get("deprecated_since"):
        errs.append(f"E420 INVALID_DEPRECATION_LIFECYCLE id={entry.get('id')} missing deprecated_since")
    if status == "sunset" and not lifecycle.get("sunset_after"):
        errs.append(f"E420 INVALID_DEPRECATION_LIFECYCLE id={entry.get('id')} missing sunset_after")
    if status == "retired" and not lifecycle.get("retired_at"):
        errs.append(f"E420 INVALID_DEPRECATION_LIFECYCLE id={entry.get('id')} missing retired_at")
    return errs


def _norm(value: str) -> str:
    return " ".join((value or "").strip().lower().split())
