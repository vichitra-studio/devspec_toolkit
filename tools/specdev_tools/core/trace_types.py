from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _load_from_canon(project_canon_dir: str | None = None) -> tuple[tuple[str, ...], dict[str, str]]:
    """Load trace types from canon/kinds/trace_type.json via CanonicalRegistry."""
    try:
        from ..canonical.registry import CanonicalRegistry

        toolkit_root = str(Path(__file__).resolve().parents[3])
        registry = CanonicalRegistry.load(toolkit_root, project_canon_dir=project_canon_dir)
        types: set[str] = set()
        aliases: dict[str, str] = {}
        for entry in registry.entries.values():
            if entry.kind != "trace_type":
                continue
            label = entry.payload.get("preferred_label", "")
            if label:
                types.add(label)
            for alias in entry.payload.get("aliases", []) or []:
                if isinstance(alias, str) and alias != label:
                    aliases[alias] = label
        if types:
            return tuple(sorted(types)), aliases
    except Exception:
        pass
    return _FALLBACK_TYPES, _FALLBACK_ALIASES


_FALLBACK_TYPES: tuple[str, ...] = (
    "api", "capability", "charter-goal", "component", "doc", "fixture",
    "fr", "glossary", "invariant", "nfr", "threat",
)
_FALLBACK_ALIASES: dict[str, str] = {"inv": "invariant"}

TRACE_TYPES, CANONICAL_TRACE_TYPE = _load_from_canon()


def normalize_trace_type(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return normalized
    return CANONICAL_TRACE_TYPE.get(normalized, normalized)


def is_valid_trace_type(value: str) -> bool:
    return normalize_trace_type(value) in TRACE_TYPES


def normalize_trace_types(values: Iterable[str]) -> list[str]:
    return [normalize_trace_type(v) for v in values]
