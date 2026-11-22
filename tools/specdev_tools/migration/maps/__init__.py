"""The migration maps: reviewable tables the migration scripts read (data, not code).

``legacy_ref_fields.yaml`` names, per step, the legacy fields that hold the id of another node and the kind that id
points at; ``legacy_ref_fields()`` loads it.  Later bundles add their own maps to this package.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_MAPS_DIR = Path(__file__).resolve().parent
LEGACY_REF_FIELDS_FILE = "legacy_ref_fields.yaml"


@lru_cache(maxsize=None)
def _load(name: str) -> dict[str, Any]:
    with open(_MAPS_DIR / name, encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"{name}: not a mapping")
    return loaded


def legacy_ref_fields() -> dict[str, Any]:
    """The parsed ``legacy_ref_fields.yaml``: ``fields`` (per step), ``typed_types`` and ``collisions``.  Do not edit the result."""
    return _load(LEGACY_REF_FIELDS_FILE)
