from __future__ import annotations

import json
import os
from collections import defaultdict
from glob import glob

from ..canonical.registry import CanonicalRegistry
from ..core.errors import SpecError, make_error


# Declarative enum↔canon pairings: (schema_rel_path, json_path_segments, canon_kind)
# Add a new line whenever a schema enum should track a canon kind.
_ENUM_CANON_PAIRINGS = [
    ("core/collections.schema.json", ["$defs", "environmentName", "enum"], "environment"),
    ("core/collections.schema.json", ["$defs", "stageName", "enum"], "stage"),
    ("07_nfrs.schema.json", ["properties", "nfrs", "items", "properties", "category", "enum"], "nfr_category"),
]


def lint_canon_schema_alignment(repo_root: str) -> list[SpecError]:
    """Check alignment between canon kinds and JSON Schema enum constraints."""
    errors: list[SpecError] = []
    schema_dir = os.path.join(repo_root, "schema")

    # Load canon kinds → {kind: set_of_preferred_labels}
    registry = CanonicalRegistry.load(repo_root)
    canon_kinds: dict[str, set[str]] = defaultdict(set)
    for entry in registry.entries.values():
        label = entry.payload.get("preferred_label", "")
        if label:
            canon_kinds[entry.kind].add(label)

    # Phase 1: Check explicit pairings
    registered_keys: set[tuple[str, str]] = set()
    for schema_rel, json_path, kind in _ENUM_CANON_PAIRINGS:
        path_str = "/".join(json_path)
        registered_keys.add((schema_rel, path_str))

        schema_path = os.path.join(schema_dir, schema_rel)
        if not os.path.exists(schema_path):
            errors.append(make_error("E552", f"MISSING_PAIRED_SCHEMA {schema_rel}"))
            continue

        with open(schema_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        enum_values = _resolve_json_path(data, json_path)
        if enum_values is None:
            errors.append(make_error("E553", f"MISSING_ENUM_PATH {schema_rel}:{path_str}"))
            continue

        enum_set = set(enum_values)
        canon_labels = canon_kinds.get(kind, set())

        missing = sorted(canon_labels - enum_set)
        extra = sorted(enum_set - canon_labels)

        if missing:
            errors.append(make_error(
                "E554",
                f"CANON_ENUM_DRIFT {schema_rel}:{path_str} "
                f"missing canon {kind} entries: {missing}",
            ))
        if extra:
            errors.append(make_error(
                "E551",
                f"SCHEMA_ENUM_EXTRA {schema_rel}:{path_str} "
                f"has values not in canon {kind}: {extra}",
            ))

    # Category B exclusions: enums that are intentional subsets of a canon kind
    _EXCLUDED_DISCOVERY_ENUMS = {
        ("11_redteam.schema.json", "properties/threats/items/properties/mitigations/items/properties/type/enum"),
        ("16_impl_context.schema.json", "$defs/specRef/properties/type/enum"),
    }

    # Phase 2: Discovery scan (advisory)
    for schema_path in sorted(glob(os.path.join(schema_dir, "**", "*.json"), recursive=True)):
        rel = os.path.relpath(schema_path, schema_dir)
        with open(schema_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for path_str, values in _extract_enums(data):
            if (rel, path_str) in registered_keys:
                continue
            if (rel, path_str) in _EXCLUDED_DISCOVERY_ENUMS:
                continue
            enum_set = set(values)
            if len(enum_set) < 3:
                continue
            for kind, labels in canon_kinds.items():
                overlap = len(enum_set & labels)
                if overlap >= 3 and overlap / len(enum_set) >= 0.8:
                    errors.append(make_error(
                        "W552",
                        f"POTENTIAL_UNREGISTERED_PAIRING {rel}:{path_str} "
                        f"overlaps {overlap}/{len(enum_set)} with canon kind '{kind}'",
                    ))
    return errors


def _resolve_json_path(data: dict, path: list[str]):
    """Walk a JSON object by path segments, return the final value or None."""
    current = data
    for segment in path:
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return None
    return current if isinstance(current, list) else None


def _extract_enums(schema: dict, path: str = "") -> list[tuple[str, list[str]]]:
    """Recursively extract all enum arrays from a JSON Schema."""
    results: list[tuple[str, list[str]]] = []
    if not isinstance(schema, dict):
        return results
    if "enum" in schema and isinstance(schema["enum"], list):
        values = [v for v in schema["enum"] if isinstance(v, str)]
        if values:
            results.append((path + "/enum" if path else "enum", values))
    for key, value in schema.items():
        if key.startswith("$") and key != "$defs":
            continue
        child_path = f"{path}/{key}" if path else key
        if isinstance(value, dict):
            results.extend(_extract_enums(value, child_path))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    results.extend(_extract_enums(item, f"{child_path}/{i}"))
    return results
