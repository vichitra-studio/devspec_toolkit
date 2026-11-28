"""``p2_action_ids``: every action of an OPEN plan gets an id (``a01``, ``a02``, ... per plan item).

1.2.0 requires an ``id`` on each action of a plan item (``plan.spec_alignment.checklist[].implementation.actions[]``).
The id is minted by the one minter of the action ids, ``lifecycle.records.mint_action_id`` (one past the highest
number among the ids the item's actions already hold), so a rerun mints nothing and an id that exists is never
changed.  A legacy-closed plan (ruling P13) gets no action ids: it is history, the schema does not judge it and no
command records into it.  "Closed" is the rule of ``spec_reads.closed_milestones``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from specdev_tools.lifecycle.records import mint_action_id
from specdev_tools.migration.registry import PHASE_IDS, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import closed_milestones, insert_key, plan_milestones, plan_rels

SCRIPT = ScriptSpec(id="p2_action_ids", phase=PHASE_IDS, requires=("p2_plan_milestone_key",), touches=("16",))

ID_FIELD = "id"


def _action_lists(plan: dict[str, Any]) -> Iterator[list[Any]]:
    items = ((plan.get("plan") or {}).get("spec_alignment") or {}).get("checklist")
    for item in items if isinstance(items, list) else []:
        actions = (item.get("implementation") or {}).get("actions") if isinstance(item, dict) else None
        if isinstance(actions, list):
            yield actions


def open_plans(ctx) -> list[str]:
    """The plan files that are not legacy-closed (a plan whose milestone is unknown counts as open)."""
    closed, milestones = closed_milestones(ctx), plan_milestones(ctx)
    return [rel for rel in plan_rels(ctx) if milestones.get(rel) not in closed]


def mint_all(ctx, *, write: bool) -> int:
    """Mint the missing action ids of the open plans; return how many (on a copy when *write* is false)."""
    minted = 0
    for rel in open_plans(ctx):
        data = ctx.documents.load(rel).data
        for actions in _action_lists(data):
            known = [a[ID_FIELD] for a in actions if isinstance(a, dict) and isinstance(a.get(ID_FIELD), str)]
            for action in actions:
                if isinstance(action, dict) and not isinstance(action.get(ID_FIELD), str):
                    new_id = mint_action_id(known)
                    known.append(new_id)
                    minted += 1
                    if write:
                        insert_key(action, ID_FIELD, new_id)
    return minted


def detect(ctx) -> int:
    """How many actions of open plans have no id."""
    return mint_all(ctx, write=False)


def apply(ctx) -> ScriptResult:
    """Give every action of an open plan its id."""
    return ScriptResult(edits=mint_all(ctx, write=True))


def verify(before, after) -> list[Problem]:
    """No action that had an id lost or changed it."""
    problems: list[Problem] = []
    for rel, document in sorted(after.documents.items()):
        old = before.documents.get(rel)
        if rel.startswith("impl_context/") and isinstance(old, dict) and isinstance(document, dict):
            was = [a.get(ID_FIELD) for lst in _action_lists(old) for a in lst if isinstance(a, dict) and ID_FIELD in a]
            now = [a.get(ID_FIELD) for lst in _action_lists(document) for a in lst if isinstance(a, dict) and ID_FIELD in a]
            if not set(was) <= set(now):
                problems.append(Problem(f"{rel}: an action id changed or was removed", rel))
    return problems
