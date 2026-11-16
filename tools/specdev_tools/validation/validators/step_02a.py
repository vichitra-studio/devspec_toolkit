from __future__ import annotations

from typing import Any

from ...core.errors import SpecError


def validate_step_02a(instance: dict[str, Any], toolkit_root: str) -> list[SpecError]:
    """Deep checks of a step 02a artifact: none today; duplicate gate and secret ids are the graph's E704."""
    return []
