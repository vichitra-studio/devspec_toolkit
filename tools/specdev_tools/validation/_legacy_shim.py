"""Guards for readers of 1.1.1 fields that the spec graph retires (M6c deletes this module).

A guarded reader runs only when the artifacts that reader itself reads still carry a field that
reader itself reads (one constant per reader or group of readers; never "any loaded artifact").
There is no old-to-new translation: new-shape data skips the reader and yields no finding.
Deleting this module means deleting every use of ``has_legacy_fields`` and the ``LEGACY_*`` names.
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from typing import Any

# 1.1.1 `trace` links: read by the W564/E535 (05 apis), W568 (04 frs), matrix FR-to-API (05 apis)
# and step-04 integrity (04 frs) readers. M4's node/trace links replace them.
LEGACY_TRACE_FIELDS: frozenset[str] = frozenset({"trace"})

# Charter -> capabilities chain (E560): charter `goal_id`, capability `trace` and `success_metric_refs`.
LEGACY_CHARTER_CHAIN_FIELDS: frozenset[str] = frozenset({"goal_id", "trace", "success_metric_refs"})

# Step-02 connection reader only (`from`/`to` are generic keys: give it the connections, nothing else).
LEGACY_CONNECTION_FIELDS: frozenset[str] = frozenset({"from", "to", "schema_ref"})

# Step-02 capability-coverage reader (component `trace` / `trace_refs`).
LEGACY_COMPONENT_TRACE_FIELDS: frozenset[str] = frozenset({"trace", "trace_refs"})


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
