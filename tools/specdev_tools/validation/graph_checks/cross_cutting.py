"""Stub of the check built by WI-M6b-06: it skips and reports nothing until that work item replaces both functions (the names stay)."""
from __future__ import annotations

from typing import Any

from specdev_tools.core.errors import SpecError
from specdev_tools.validation import check_registry
from specdev_tools.validation.check_registry import CheckContext

from .context import GraphCheckContext, Mode


def run_cross_cutting(ctx: CheckContext) -> dict[str, Any]:
    """The registered function: skips until WI-M6b-06 builds the check."""
    return check_registry.skip("not built yet")


def check_cross_cutting(ctx: GraphCheckContext, mode: Mode) -> list[SpecError]:
    """The rule function: reports nothing until WI-M6b-06 builds the check."""
    return []
