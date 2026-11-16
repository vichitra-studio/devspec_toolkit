"""Error ownership: which step, gate or check a finding belongs to.

The ownership table is the data file ``tools/error_ownership.json`` (one row per error class, each with an owner rule
and the registered codes that implement the class).  This module reads it, resolves a code to an owner string and
stamps the step of a file onto the schema errors found in that file.

Owner strings are ``step:<id>``, ``merge-check``, ``close-gate`` and ``release-gate``.  Command usage errors
(E705-E709) are not findings about the spec and have no row.
"""
from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from specdev_tools.core.errors import SpecError
from specdev_tools.core.loaders import read_json_object
from specdev_tools.core.scope_helpers import as_str, dict_items, str_items
from specdev_tools.graph.model import Node
from specdev_tools.validation.validate import _get_step_from_path, _refine_impl_context_substep

STEP_PREFIX = "step:"
FIXED_STEP_PREFIX = "fixed_step:"
GATE_OWNERS = frozenset({"merge-check", "close-gate", "release-gate"})
_NODE_STEP_RULES = frozenset({"holder_step", "node_step", "consumer_step", "binding_step"})
_FURTHEST_STEP_RULE = "furthest_usable_step"
_UNKNOWN_STEP = "unknown"
_TABLE_RELATIVE = os.path.join("tools", "error_ownership.json")


class OwnershipTableError(Exception):
    """``tools/error_ownership.json`` is missing, unreadable or not a JSON object."""


@dataclass(frozen=True)
class OwnershipRow:
    """One error class: its ``owner_rule`` and the registered ``codes`` that implement it."""

    class_name: str
    owner_rule: str
    codes: tuple[str, ...]
    authority: str


@dataclass(frozen=True)
class OwnerContext:
    """What an owner rule needs besides the node: the table, and the furthest step that can use each kind."""

    rows: tuple[OwnershipRow, ...]
    furthest_step: Mapping[str, str] = field(default_factory=dict)


def load_ownership_table(repo_root: str) -> tuple[OwnershipRow, ...]:
    """Read ``<repo_root>/tools/error_ownership.json`` into rows.

    Raises ``OwnershipTableError`` when the file is missing, unreadable or not a JSON object.  A row that is not an
    object is skipped; a wrong-typed field reads as empty.
    """
    path = os.path.join(repo_root, _TABLE_RELATIVE)
    data = read_json_object(path)
    if data is None:
        raise OwnershipTableError(f"{path}: unreadable or not a JSON object")
    return tuple(
        OwnershipRow(
            class_name=as_str(row.get("class")),
            owner_rule=as_str(row.get("owner")),
            codes=tuple(str_items(row.get("codes"))),
            authority=as_str(row.get("authority")),
        )
        for row in dict_items(data.get("rows"))
    )


def owner_for(code: str, node: Node | None, ctx: OwnerContext) -> str | None:
    """The owner string of *code* for *node*, or ``None`` when no row lists the code or the rule has no answer.

    The step rules (``holder_step``, ``node_step``, ``consumer_step``, ``binding_step``) give the step of *node*, the
    node the caller names as the owner; ``furthest_usable_step`` gives ``ctx.furthest_step`` for the kind of *node*;
    ``fixed_step:<id>`` gives that step; a gate rule gives the gate.
    """
    for row in ctx.rows:
        if code in row.codes:
            return _resolve_rule(row.owner_rule, node, ctx)
    return None


def _resolve_rule(rule: str, node: Node | None, ctx: OwnerContext) -> str | None:
    if rule in GATE_OWNERS:
        return rule
    if rule.startswith(FIXED_STEP_PREFIX):
        return STEP_PREFIX + rule[len(FIXED_STEP_PREFIX):]
    if node is None:
        return None
    if rule in _NODE_STEP_RULES:
        return STEP_PREFIX + node.step if node.step else None
    if rule == _FURTHEST_STEP_RULE:
        step = ctx.furthest_step.get(node.kind)
        return STEP_PREFIX + step if step else None
    return None


def step_for_file(path: str, data: object) -> str | None:
    """The step a spec file belongs to, or ``None`` for a file with no step (seed manifest, canon manifest).

    Uses the routing ``validate_file`` itself uses, so an ``impl_context/ms_*_plan.json`` is ``16a``, ``16b`` or
    ``16c`` by its content.  *data* is the parsed document; a non-object gives the path-only step.
    """
    step = _refine_impl_context_substep(_get_step_from_path(path), data)
    return None if step == _UNKNOWN_STEP else step


def stamp_file_owner(errors: Sequence[SpecError], step: str | None) -> list[SpecError]:
    """Copies of *errors* with ``owner`` set to ``step:<step>`` where it is still unset.

    ``node_id`` is left as it is (``None`` for a file-level error).  With ``step`` ``None`` the errors come back
    unchanged.
    """
    if step is None:
        return list(errors)
    owner = STEP_PREFIX + step
    return [err if err.owner is not None else replace(err, owner=owner) for err in errors]
