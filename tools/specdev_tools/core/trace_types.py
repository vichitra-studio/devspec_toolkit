from __future__ import annotations

from typing import Iterable


TRACE_TYPES = (
    "fr",
    "api",
    "nfr",
    "inv",
    "invariant",
    "fixture",
    "doc",
    "capability",
    "component",
)


CANONICAL_TRACE_TYPE = {
    "inv": "invariant"
}


def normalize_trace_type(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return normalized
    return CANONICAL_TRACE_TYPE.get(normalized, normalized)


def is_valid_trace_type(value: str) -> bool:
    return normalize_trace_type(value) in TRACE_TYPES


def normalize_trace_types(values: Iterable[str]) -> list[str]:
    return [normalize_trace_type(v) for v in values]
