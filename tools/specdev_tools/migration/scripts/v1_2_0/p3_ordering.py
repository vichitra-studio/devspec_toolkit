"""``p3_ordering``: which 09 milestone orderings the stored links already imply (the ``implied`` report, CD-17 / CD-17m).

1.2.0 stores no milestone order: ``milestones[].depends_on`` (09) is removed and the order follows from what each milestone
schedules (FR to FR and API to API ``depends_on``).  For every captured pair "A after B" (``capture.json``,
``milestone_ordering.pairs``; the ids are mapped through the capture's ``renames``) this script reports ``implied: true`` when an
obligation A schedules reaches, over those ``depends_on`` links, an obligation B schedules, else ``implied: false``.  What A
schedules is the ``schedules`` of the milestone once someone confirmed it, else the proposal of ``p3_convert.schedule_proposals``.

It edits no spec file and adds no check or command.  The report is the script's residue (one line per pair); each pair that
is NOT implied is a worklist item for the step that authors the missing link (04 for an FR pair, 05 for an API pair, 09 when
nothing is known yet).  A pair that is implied needs no item.  Run again in the step-04/05 pass it reports the new links.
"""

from __future__ import annotations

from dataclasses import dataclass

from specdev_tools.migration.context import CAPTURE_REL
from specdev_tools.graph.build import build_graph
from specdev_tools.migration.registry import PHASE_SHAPES, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import capture_renames
from specdev_tools.migration.scripts.v1_2_0.p3_convert import schedule_proposals
from specdev_tools.migration.worklist import WORKLIST_FILE, WorklistItem, add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p3_ordering", phase=PHASE_SHAPES, requires=("p2_id_collisions", "p3_convert"), touches=("extras",))

KIND_ORDER = "milestone-order"
_STEP_OF_KIND = {"fr": "04", "api": "05"}
_WORKLIST_REL = WORKLIST_FILE.replace("\\", "/")


@dataclass(frozen=True)
class Pair:
    """``later`` came after ``earlier`` in 1.1.1; ``implied`` is true when the stored links give the same order."""

    later: str
    earlier: str
    implied: bool
    step: str
    evidence: str


def _reaches(adjacency: dict[str, list[str]], start: str, goals: set[str]) -> bool:
    seen: set[str] = set()
    stack = list(adjacency.get(start, ()))
    while stack:
        current = stack.pop()
        if current in goals:
            return True
        if current not in seen:
            seen.add(current)
            stack.extend(adjacency.get(current, ()))
    return False


def ordering_pairs(ctx) -> list[Pair]:
    """The captured 09 pairs with the ``implied`` verdict, in capture order."""
    capture = ctx.documents.load(CAPTURE_REL).data
    captured = (capture.get("milestone_ordering") or {}).get("pairs") or []
    renames = capture_renames(ctx).get("design-milestone", {})
    graph = build_graph(ctx.spec_root, ctx.toolkit_root)
    kind_of = {n.id: n.kind for n in graph.nodes}
    adjacency = {n.id: [link.target for link in n.links if link.field == "depends_on"] for n in graph.nodes if n.kind in _STEP_OF_KIND}
    confirmed = {n.id: [link.target for link in n.links if link.field == "schedules"] for n in graph.nodes if n.kind == "design-milestone"}
    proposed = schedule_proposals(ctx, graph, kind_of)
    pairs: list[Pair] = []
    for row in captured:
        old_later = str(row["milestone"])
        later = renames.get(old_later, old_later)
        for old in map(str, row.get("legacy_depends_on") or []):
            earlier = renames.get(old, old)
            a = confirmed.get(later) or proposed.get(later, [])
            b = set(confirmed.get(earlier) or proposed.get(earlier, []))
            implied = any(_reaches(adjacency, obligation, b) for obligation in a)
            kinds = [kind_of[i] for i in (*a, *b) if i in kind_of and kind_of[i] in _STEP_OF_KIND]
            step = _STEP_OF_KIND[kinds[0]] if kinds else "09"
            evidence = f"09 milestone {later} came after {earlier} (depends_on, now removed); it schedules {sorted(a) or 'nothing known'}, the other {sorted(b) or 'nothing known'}"
            pairs.append(Pair(later, earlier, implied, step, evidence))
    return pairs


def _items(pairs: list[Pair]) -> list[WorklistItem]:
    return [
        make_item(p.step, KIND_ORDER, f"{p.later}-after-{p.earlier}", audience="agent", blocking=False, evidence=p.evidence + "; no FR or API depends_on connects them",
                  proposal="add the missing depends_on between what they schedule, or drop the pair (the milestone order is stored nowhere)")
        for p in pairs
        if not p.implied
    ]


def detect(ctx) -> int:
    """Pairs whose item is not listed yet."""
    return len(missing_items(ctx, _items(ordering_pairs(ctx))))


def apply(ctx) -> ScriptResult:
    """List one item per pair the links do not imply; print one line per pair (nothing else is written)."""
    pairs = ordering_pairs(ctx)
    listed = add_items(ctx, _items(pairs))
    residue = tuple(f"implied: {str(p.implied).lower()}  {p.later} after {p.earlier}" for p in pairs)
    return ScriptResult(edits=listed, worklist_items=listed, residue=residue)


def verify(before, after) -> list[Problem]:
    """No file changed but the worklist."""
    return [
        Problem(f"{rel}: changed, and this script writes only the worklist", rel)
        for rel in sorted(set(before.files) | set(after.files))
        if before.files.get(rel) != after.files.get(rel) and rel != _WORKLIST_REL
    ]
