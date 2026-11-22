"""``p4_exit_conditions``: a task's ``exit_conditions`` become task criteria (DOC "Folded into task criteria").

1.1.1 step 14 gave a task a list of ``exit_conditions`` strings next to its ``acceptance_criteria``; 1.2.0 has one list.
``p3_remove`` took the field out of the tree after ``p1_capture`` kept the values (section ``task_exit_conditions``); this
script reads the capture and appends one task criterion (``criterion_id`` minted with the prefix ``tc-``, the text as
``text``) to the task's ``acceptance_criteria`` for each non-empty entry, in a closed milestone too (a recorded mechanical
edit on frozen nodes).  Each new criterion has a worklist item of kind ``legacy-exit-condition`` so the criterion is not
mistaken for a second list; the ``refines`` proposer (``align propose --kind refines``) offers its candidates like any task
criterion.  Nothing is written to ``refines`` here.
"""

from __future__ import annotations

from typing import Any

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.ids import mint_slug, suggest_prefix
from specdev_tools.graph.names import TASK_CRITERION
from specdev_tools.migration.registry import PHASE_CONTENT, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.scripts.v1_2_0.p1_capture import CAPTURE_REL, LEGACY
from specdev_tools.migration.scripts.v1_2_0.p2_plan_milestone_key import ROADMAP_STEP, step_data
from specdev_tools.migration.worklist import WorklistItem, add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p4_exit_conditions", phase=PHASE_CONTENT, requires=("p3_remove",), touches=("14", "extras"))

KIND = "legacy-exit-condition"
_CRITERIA = "acceptance_criteria"


def _conditions(ctx) -> list[tuple[str, int, str]]:
    """``(task id, position, text)`` of every non-empty captured exit condition, in capture order."""
    found = []
    for row in ctx.documents.load(CAPTURE_REL).data.get("task_exit_conditions") or []:
        entries = [e.strip() for e in row.get(LEGACY + "exit_conditions") or [] if isinstance(e, str) and e.strip()]
        found.extend((row["task"], position, text) for position, text in enumerate(entries, start=1))
    return found


def _tasks(ctx) -> dict[str, dict[str, Any]]:
    return {
        task["task_id"]: task
        for milestone in step_data(ctx, ROADMAP_STEP).get("milestones", [])
        if isinstance(milestone, dict)
        for task in milestone.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("task_id"), str)
    }


def _item(task: str, position: int, text: str, criterion: str | None, *, found: bool) -> WorklistItem:
    if found:
        evidence = f"exit condition {position} of task {task}, now the task criterion {criterion or '(to be minted)'}: {text}"
        proposal = "name what the criterion refines (`specdev align propose --kind refines` offers candidates); the criterion is the old exit condition, not a second list"
    else:
        evidence = f"exit condition {position} of task {task}: {text}; the task is not in step 14, so no criterion was made"
        proposal = "add it as a task criterion of the right task, or drop it"
    return make_item(ROADMAP_STEP, KIND, task, audience="agent" if found else "operator", blocking=not found, key=str(position), evidence=evidence, proposal=proposal)


def _items(ctx, minted: dict[tuple[str, int], str] | None = None) -> list[WorklistItem]:
    tasks = _tasks(ctx)
    return [_item(task, position, text, (minted or {}).get((task, position)), found=task in tasks) for task, position, text in _conditions(ctx)]


def detect(ctx) -> int:
    """Items (and with them criteria) not made yet."""
    return len(missing_items(ctx, _items(ctx)))


def apply(ctx) -> ScriptResult:
    """Append a task criterion for each exit condition that has no item yet and list it."""
    tasks = _tasks(ctx)
    todo = {item.id for item in missing_items(ctx, _items(ctx))}
    taken = set(build_graph(ctx.spec_root, ctx.toolkit_root).by_id)
    prefix = suggest_prefix(TASK_CRITERION)
    minted: dict[tuple[str, int], str] = {}
    for task, position, text in _conditions(ctx):
        if _item(task, position, text, None, found=True).id not in todo or task not in tasks:
            continue
        new_id = mint_slug(text, taken, prefix=prefix)
        taken.add(new_id)
        tasks[task].setdefault(_CRITERIA, []).append({"criterion_id": new_id, "text": text})
        minted[(task, position)] = new_id
    listed = add_items(ctx, _items(ctx, minted))
    return ScriptResult(edits=listed, worklist_items=listed, residue=(f"exit conditions turned into task criteria: {len(minted)}; not matched to a task: {listed - len(minted)}",))


def _has_key(data: Any, name: str) -> bool:
    if isinstance(data, dict):
        return name in data or any(_has_key(value, name) for value in data.values())
    return isinstance(data, list) and any(_has_key(value, name) for value in data)


def verify(before, after) -> list[Problem]:
    """No task gained a field named ``exit_conditions`` (a key; a text that mentions the word is not one)."""
    return [Problem(f"{rel}: exit_conditions is back", rel) for rel, doc in sorted(after.documents.items()) if rel[:2] == ROADMAP_STEP and _has_key(doc, "exit_conditions")]
