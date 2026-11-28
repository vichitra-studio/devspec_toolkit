"""``p4_assumptions``: assumptions that bundle several claims or are really decisions are flagged (DOC "Assumptions", DEVSPEC-290).

``p2_id_mint`` already gave every charter assumption an id (that is the mechanical part).  Two things the old charter prompt
did to the list are judgement, so this script only proposes, one worklist item per case (``audience: agent``, step 00):

- ``assumption-bundle``: one assumption string that holds more than one claim (more than one sentence, a semicolon, ", and",
  "as well as", "and also"); the split is made in the step-00 pass;
- ``assumption-decision``: an assumption that names a technology the host's own ``tech_stack`` or external components named
  (old ``prompt_00`` told agents to file dependency risks as assumptions and technology constraints as risks); the move to
  the step-00 ``constraints`` list is made in the step-00 pass with the operator asked where it is unclear.

Both are heuristics with an unmeasured precision and write nothing.  The terms come from the capture (``third_party``) and
the third parties already in the tree; the seeds routed to step 00 are not parsed.  The task-level ``assumptions`` of step 14
went with phase 3 and are only counted in the report (the capture keeps them).
"""

from __future__ import annotations

import re

from specdev_tools.migration.context import CAPTURE_REL
from specdev_tools.migration.registry import PHASE_CONTENT, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import LEGACY, step_data
from specdev_tools.migration.worklist import WorklistItem, add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p4_assumptions", phase=PHASE_CONTENT, requires=("p2_id_mint",), touches=("extras",))

CHARTER_STEP = "00"
KIND_BUNDLE = "assumption-bundle"
KIND_DECISION = "assumption-decision"
_SENTENCES = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_CONJUNCTION = re.compile(r";|, and |\bas well as\b|\band also\b", re.IGNORECASE)
_MIN_TERM = 4


def _claims(text: str) -> str | None:
    """Why *text* looks like several claims, or ``None``."""
    sentences = [s for s in _SENTENCES.split(text.strip()) if s]
    if len(sentences) > 1:
        return f"{len(sentences)} sentences"
    found = _CONJUNCTION.search(text)
    return f"the conjunction {found.group().strip()!r}" if found else None


def _terms(ctx) -> list[str]:
    """The technology names of the host: the ``tech_stack`` names and external component ids of the capture, and the names of the third parties in step 02."""
    captured = ctx.documents.load(CAPTURE_REL).data.get("third_party") or {}
    names: list[str] = []
    for row in captured.get("tech_stacks") or []:
        for entries in (row.get(LEGACY + "tech_stack") or {}).values():
            names.extend(str(e["name"]) for e in entries if isinstance(e, dict) and e.get("name"))
    names.extend(str(row["component"]).replace("-", " ") for row in captured.get("external_components") or [])
    names.extend(str(tp["name"]) for tp in step_data(ctx, "02").get("third_parties", []) if isinstance(tp, dict) and tp.get("name"))
    return sorted({n for n in names if len(n) >= _MIN_TERM}, key=str.lower)


def _technology(text: str, terms: list[str]) -> list[str]:
    return [t for t in terms if re.search(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", text, re.IGNORECASE)]


def _items(ctx) -> list[WorklistItem]:
    terms = _terms(ctx)
    items = []
    for entry in step_data(ctx, CHARTER_STEP).get("assumptions", []):
        text = entry.get("text") if isinstance(entry, dict) else None
        if not (isinstance(text, str) and isinstance(entry.get("assumption_id"), str)):
            continue
        asm = entry["assumption_id"]
        if (why := _claims(text)) is not None:
            items.append(make_item(CHARTER_STEP, KIND_BUNDLE, asm, audience="agent", blocking=False,
                                   evidence=f"{asm} may hold more than one claim ({why}): {text!r}",
                                   proposal="split it into one assumption per claim in the step-00 pass; nothing was split here"))
        if names := _technology(text, terms):
            items.append(make_item(CHARTER_STEP, KIND_DECISION, asm, audience="agent", blocking=False,
                                   evidence=f"{asm} names {', '.join(names)}, which the host lists as technology: {text!r}",
                                   proposal="if it is a choice already made, move it to the step-00 `constraints` list in the step-00 pass (ask the operator when unclear); nothing was moved here"))
    return items


def _task_assumptions(ctx) -> int:
    return sum(len(row.get(LEGACY + "assumptions") or []) for row in ctx.documents.load(CAPTURE_REL).data.get("task_assumptions") or [])


def detect(ctx) -> int:
    """Flags not listed yet."""
    return len(missing_items(ctx, _items(ctx)))


def apply(ctx) -> ScriptResult:
    """List the flags; step 00 is not changed."""
    listed = add_items(ctx, _items(ctx))
    count = len(step_data(ctx, CHARTER_STEP).get("assumptions", []))
    return ScriptResult(edits=listed, worklist_items=listed, residue=(f"charter assumptions: {count}; flagged: {listed}; task-level assumptions kept in the capture only: {_task_assumptions(ctx)}",))


def verify(before, after) -> list[Problem]:
    """Step 00 is exactly as it was."""
    return [Problem(f"{rel} changed; the script only proposes", rel) for rel in sorted(after.documents) if rel.startswith("00_") and after.documents[rel] != before.documents.get(rel)]
