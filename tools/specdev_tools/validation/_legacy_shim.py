"""Guards for readers of 1.1.1 fields that the spec graph retires (M6c deletes this module).

A guarded reader runs only when a loaded artifact still carries a field it reads. There is no
old-to-new translation: new-shape data skips the reader and yields no finding.
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from typing import Any

# Names removed from the 00-05 artifacts; M3 adds the names removed from 06-16.
LEGACY_FIELDS: frozenset[str] = frozenset({
    "trace", "goal_id", "success_metric_refs", "from", "to", "schema_ref",
})

LEGACY_TRACE_FIELDS: frozenset[str] = frozenset({"trace"})


def _carries(value: Any, names: Collection[str]) -> bool:
    if isinstance(value, Mapping):
        return any(key in names or _carries(item, names) for key, item in value.items())
    if isinstance(value, list):
        return any(_carries(item, names) for item in value)
    return False


def has_legacy_fields(artifacts: Iterable[Any], names: Collection[str]) -> bool:
    """Return True when any key in *names* appears at any depth of any artifact in *artifacts*.

    *artifacts* is an iterable of loaded artifact values (dicts); anything that is not a mapping
    or list is ignored. Never raises on malformed data.
    """
    return any(_carries(artifact, names) for artifact in artifacts)
