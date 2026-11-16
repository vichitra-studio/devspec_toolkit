"""Shared definition of a parked spec node, and the type helpers every reader of a spec value uses.

The type helpers (``as_dict``, ``as_list``, ``dict_items``, ``str_items``, ``str_in``) are how a validator or a
reader of steps 06-16 looks at a value it did not check yet: a wrong-typed value reads as empty, never raises.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PARKED_SCOPES: frozenset[str] = frozenset({"later", "out"})


def scope_in(node: Mapping[str, Any], scopes: frozenset[str]) -> bool:
    """Return True when *node*'s ``scope`` is a string in *scopes*; a missing or wrong-typed ``scope`` is False."""
    scope = node.get("scope")
    return isinstance(scope, str) and scope in scopes


def is_parked(node: Mapping[str, Any]) -> bool:
    """Return True when *node* is parked: its ``scope`` is ``later`` or ``out``.

    Works for any node mapping; a missing ``scope`` key counts as not parked. Never raises on
    missing keys or on a wrong-typed value (a list or dict ``scope`` is not parked).
    """
    return scope_in(node, PARKED_SCOPES)


def as_dict(value: Any) -> dict[str, Any]:
    """Return *value* when it is a dict, else an empty dict."""
    return value if isinstance(value, dict) else {}


def as_str(value: Any) -> str:
    """Return *value* when it is a string, else an empty string."""
    return value if isinstance(value, str) else ""


def as_list(value: Any) -> list[Any]:
    """Return *value* when it is a list, else an empty list."""
    return value if isinstance(value, list) else []


def dict_items(value: Any) -> list[dict[str, Any]]:
    """Return the members of *value* that are dicts; a value that is not a list gives an empty list."""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def str_items(value: Any) -> list[str]:
    """Return the members of *value* that are strings; a value that is not a list gives an empty list."""
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def str_in(value: Any, allowed: Any) -> bool:
    """Return True when *value* is a string found in *allowed*; a list or dict *value* (unhashable) is False."""
    return isinstance(value, str) and value in allowed
