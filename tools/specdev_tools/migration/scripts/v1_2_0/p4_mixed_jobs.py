"""``p4_mixed_jobs``: step-12 jobs that mix a one-time action with a re-runnable check are listed, never split (DOC "Mixed jobs").

A job is a candidate when one of its steps looks like a one-time action (a teardown, a deletion, a data migration, a
restore, a go-live) and another step does not: the action belongs in a plan execution, the check stays a verifier.  The split
changes what a job proves, so the script edits nothing: each candidate is a worklist item for the step-12 pass.  The words
are a heuristic and the report says so; a job whose steps are all actions is not mixed, and a candidate may be a false alarm.
"""

from __future__ import annotations

import re
from typing import Any

from specdev_tools.migration.registry import PHASE_CONTENT, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import step_data
from specdev_tools.migration.worklist import WorklistItem, add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p4_mixed_jobs", phase=PHASE_CONTENT, requires=("p3_remove",), touches=("extras",))

KIND = "mixed-job"
CI_STEP = "12"
_ACTION = re.compile(r"(?<![a-z])(teardown|tear[-_ ]down|delete|migrat(?:e|es|ion|ions)|restore|go[-_ ]live)(?![a-z])", re.IGNORECASE)


def _text(step: Any) -> str:
    return " ".join(str(step.get(key, "")) for key in ("name", "command")) if isinstance(step, dict) else str(step)


def _label(step: Any) -> str:
    return (step.get("name") or step.get("command") or "?") if isinstance(step, dict) else str(step)


def _items(ctx) -> list[WorklistItem]:
    items = []
    for job in step_data(ctx, CI_STEP).get("jobs", []):
        steps = job.get("steps") if isinstance(job, dict) else None
        if not isinstance(steps, list) or not isinstance(job.get("job_id"), str):
            continue
        actions = [_label(s) for s in steps if _ACTION.search(_text(s))]
        checks = [_label(s) for s in steps if not _ACTION.search(_text(s))]
        if actions and checks:
            items.append(make_item(
                CI_STEP, KIND, job["job_id"], audience="agent", blocking=False,
                evidence=f"job {job['job_id']} has one-time action steps ({', '.join(actions)}) next to re-runnable checks ({', '.join(checks)}); the words are a heuristic",
                proposal="the action becomes a plan execution in the milestone that needs it and the check stays a verifier; split the job in the step-12 pass (one-time actions at closed milestones go into the frozen plan as history)",
            ))
    return items


def detect(ctx) -> int:
    """Candidates not listed yet."""
    return len(missing_items(ctx, _items(ctx)))


def apply(ctx) -> ScriptResult:
    """List one item per candidate job; no job is changed."""
    listed = add_items(ctx, _items(ctx))
    return ScriptResult(edits=listed, worklist_items=listed, residue=(f"mixed-job candidates listed: {listed}",))


def verify(before, after) -> list[Problem]:
    """Step 12 is exactly as it was."""
    return [Problem(f"{rel} changed; the script only lists candidates", rel) for rel in sorted(after.documents) if rel.startswith("12_") and after.documents[rel] != before.documents.get(rel)]
