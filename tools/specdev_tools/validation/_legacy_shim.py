"""Guards for readers of 1.1.1 fields that the spec graph retires (M6c deletes this module).

A guarded reader runs only when the artifacts that reader itself reads still carry a field that
reader itself reads (one constant per reader or group of readers; never "any loaded artifact").
There is no old-to-new translation: new-shape data skips the reader and yields no finding.
Deleting this module means deleting every use of ``has_legacy_fields`` and the ``LEGACY_*`` names;
the callers of ``is_parked_any_shape`` go back to ``core.scope_helpers.is_parked``.
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from typing import Any

from ..core.scope_helpers import is_parked, scope_in

# 1.1.1 `trace` links, read by three live readers: W564/E535 (05 apis) and W568 (04 frs) in
# `traceability_closure.py`, and FR-to-API coverage (05 apis) in `matrix.py`.
LEGACY_TRACE_FIELDS: frozenset[str] = frozenset({"trace"})

# Charter -> capabilities chain: read by E560 in `traceability_closure.py` (charter `goal_id`,
# capability `trace` and `success_metric_refs`).
LEGACY_CHARTER_CHAIN_FIELDS: frozenset[str] = frozenset({"goal_id", "trace", "success_metric_refs"})

# Step-02 capability-coverage reader in `cross_artifact_checks.py` (component `trace` / `trace_refs`).
LEGACY_COMPONENT_TRACE_FIELDS: frozenset[str] = frozenset({"trace", "trace_refs"})

# The 1.1.1 spellings of a parked node: a capability with `scope: future` and an FR with
# `priority: wont-have`. Readers that can meet a legacy file (`matrix.py`, `traceability_closure.py`,
# `validators/step_11.py`, `cli.py`) call `is_parked_any_shape`.
LEGACY_PARKED_SCOPES: frozenset[str] = frozenset({"future"})
LEGACY_PARKED_PRIORITY = "wont-have"


def is_parked_any_shape(node: Mapping[str, Any]) -> bool:
    """Return True when *node* is parked in the current shape (``is_parked``) or the 1.1.1 one.

    The 1.1.1 forms are ``scope: future`` and ``priority: wont-have``. For readers that can meet
    a legacy file and a new-shape file in the same run. When this module is deleted its callers
    go back to ``is_parked``. Never raises on a wrong-typed value.
    """
    return (
        is_parked(node)
        or scope_in(node, LEGACY_PARKED_SCOPES)
        or node.get("priority") == LEGACY_PARKED_PRIORITY
    )


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
