"""The migration maps: reviewable tables the migration scripts read (data, not code).

``legacy_ref_fields.yaml`` names, per step, the legacy fields that hold the id of another node and the kind that id
points at; ``legacy_ref_fields()`` loads it.  ``v1_2_0.yaml`` is the shape migration map: one row per row of
``tools/schema_changes.json`` with what the migration does with it; ``shape_map()`` loads it.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Any

import yaml

LEGACY_REF_FIELDS_FILE = "legacy_ref_fields.yaml"
SHAPE_MAP_FILE = "v1_2_0.yaml"


@lru_cache(maxsize=None)
def _load(name: str) -> dict[str, Any]:
    with (resources.files("specdev_tools.migration.maps") / name).open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"{name}: not a mapping")
    return loaded


def legacy_ref_fields() -> dict[str, Any]:
    """The parsed ``legacy_ref_fields.yaml``: ``fields`` (per step), ``typed_types`` and ``collisions``.  Do not edit the result."""
    return _load(LEGACY_REF_FIELDS_FILE)


def shape_map() -> dict[str, Any]:
    """The parsed ``v1_2_0.yaml``: ``rows`` (one per checklist row), ``retired_files`` and ``host_canon``.  Do not edit the result."""
    return _load(SHAPE_MAP_FILE)


def shape_rows(script: str) -> list[dict[str, Any]]:
    """The rows of the shape map that *script* applies, in checklist order."""
    return [row for row in shape_map()["rows"] if row.get("script") == script]
