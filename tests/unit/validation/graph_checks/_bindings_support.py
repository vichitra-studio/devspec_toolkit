"""Binding a proof-milestone seam or a built provider for the length of one test (the ``bindings`` fixture of ``conftest.py``)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from specdev_tools.validation.graph_checks.built import BuiltProvider, KindPredicate, register_built_provider
from specdev_tools.validation.graph_checks.context import bind_seams


class Bindings:
    """``seams(**seams)`` and ``provider(kind_predicate, fn)`` bind like ``bind_seams`` and ``register_built_provider`` and return their restore function; whatever is still bound when the test ends is removed."""

    def __init__(self) -> None:
        self._restores: list[Callable[[], None]] = []

    def seams(self, **seams: Callable[..., Any]) -> Callable[[], None]:
        restore = bind_seams(**seams)
        self._restores.append(restore)
        return restore

    def provider(self, kind_predicate: KindPredicate, fn: BuiltProvider) -> Callable[[], None]:
        restore = register_built_provider(kind_predicate, fn)
        self._restores.append(restore)
        return restore

    def release(self) -> None:
        for restore in reversed(self._restores):
            restore()
