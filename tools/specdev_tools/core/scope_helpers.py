"""Shared definition of a parked spec node (one that is deliberately not built now)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PARKED_SCOPES: frozenset[str] = frozenset({"later", "out"})
_WONT_HAVE_PRIORITY = "wont-have"


def scope_in(node: Mapping[str, Any], scopes: frozenset[str]) -> bool:
    """Return True when *node*'s ``scope`` is a string in *scopes*; a missing or wrong-typed ``scope`` is False."""
    scope = node.get("scope")
    return isinstance(scope, str) and scope in scopes


def is_parked(node: Mapping[str, Any]) -> bool:
    """Return True when *node* is parked: ``scope`` is ``later`` or ``out``, or ``priority`` is ``wont-have``.

    Works for any node mapping; a missing ``scope`` or ``priority`` key (a capability has no
    ``priority``) counts as not parked on that criterion. Never raises on missing keys or on a
    wrong-typed value (a list or dict ``scope`` is not parked).
    The ``priority`` branch is the 1.1.1 spelling and goes away with the 04 ``priority`` field.
    """
    return scope_in(node, PARKED_SCOPES) or node.get("priority") == _WONT_HAVE_PRIORITY
