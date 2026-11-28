"""Item and plan builders shared by the tests of the open-item reader, the open-item check and the upstream backlog."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def unified_item(item_id: str, **extra: object) -> dict[str, Any]:
    """A unified-shape ambiguity item (``about``, no ``severity``) with *extra* fields."""
    return {"id": item_id, "description": "what is unclear", "about": ["fr-login"], **extra}


def plan_doc(plan_items: Sequence[dict[str, Any]] = (), emergent: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
    """A milestone plan document with *plan_items* in ``plan.ambiguities`` and *emergent* in ``execution.emergent_ambiguities``."""
    return {"plan": {"ambiguities": list(plan_items)}, "execution": {"emergent_ambiguities": list(emergent)}}
