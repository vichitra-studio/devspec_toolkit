"""``strip_status_ref`` (DEVSPEC-249): delete every ``status_ref`` object and the status ids it leaves in ``canonical_refs_used``.

Toolkit 1.1.0 removed the optional ``status_ref`` field and retired the canon kind ``status``.  Every ``status_ref`` had
a sibling ``status`` string, so deleting it loses nothing; the ids ``cn:<namespace>:status:<value>`` of the retired kind
are then orphans in a file's ``canonical_refs_used[]`` and go too (the second step of the 1.1.0 changelog note).  The
script reads and writes the step files (``NN_*.json``) and the plan files of ``impl_context/``, through the migration's
writer, so the lines it did not touch keep their bytes.  A host already at 1.1.0 or later never runs it (the chain
starts above the host's version); on a tree without a ``status_ref`` its ``detect`` is 0.
"""

from __future__ import annotations

import os
import re
from typing import Any

from specdev_tools.core.plan_files import plan_files
from specdev_tools.core.step_paths import PLAN_DIR_NAME, STEP_JSON_RE
from specdev_tools.migration.registry import PHASE_SHAPES, Problem, ScriptResult, ScriptSpec

FIELD = "status_ref"
REFS_FIELD = "canonical_refs_used"
_STATUS_ID = re.compile(r"^cn:[^:]+:status:")

# Every step id a spec file can carry (``file_key`` of ``runner``): the script reads them all, edits the ones that have a ``status_ref``.
STEP_IDS = ("00", "01", "02", "02a", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "13a", "14", "15", "16")

SCRIPT = ScriptSpec(id="p3_strip_status_ref", phase=PHASE_SHAPES, touches=STEP_IDS)


def _is_status_ref_entry(entry: Any) -> bool:
    """True for a ``canonical_refs_used`` entry of the retired kind ``status``."""
    if isinstance(entry, dict):
        value = entry.get("id")
        return entry.get("kind") == "status" or (isinstance(value, str) and bool(_STATUS_ID.match(value)))
    return isinstance(entry, str) and bool(_STATUS_ID.match(entry))


def count(node: Any) -> int:
    """How many ``status_ref`` keys and ``canonical_refs_used`` status entries *node* holds, at any depth (read-only)."""
    total = 0
    if isinstance(node, dict):
        for key, value in node.items():
            if key == FIELD:
                total += 1
            elif key == REFS_FIELD and isinstance(value, list):
                total += sum(1 for entry in value if _is_status_ref_entry(entry))
                total += sum(count(entry) for entry in value if not _is_status_ref_entry(entry))
            else:
                total += count(value)
    elif isinstance(node, list):
        total += sum(count(item) for item in node)
    return total


def strip(node: Any) -> int:
    """Remove the ``status_ref`` keys and the status entries of ``canonical_refs_used`` from *node*; return how many."""
    removed = 0
    if isinstance(node, dict):
        if FIELD in node:
            del node[FIELD]
            removed += 1
        refs = node.get(REFS_FIELD)
        if isinstance(refs, list):
            kept = [entry for entry in refs if not _is_status_ref_entry(entry)]
            removed += len(refs) - len(kept)
            refs[:] = kept
        for value in list(node.values()):
            removed += strip(value)
    elif isinstance(node, list):
        removed += sum(strip(item) for item in node)
    return removed


def _spec_files(spec_root: str) -> list[str]:
    """The step files and the plan files of the spec folder, as paths relative to it, in path order."""
    names = [name for name in os.listdir(spec_root) if STEP_JSON_RE.match(name) and os.path.isfile(os.path.join(spec_root, name))]
    plans = [f"{PLAN_DIR_NAME}/{path.name}" for path in plan_files(spec_root)]
    return sorted(names) + sorted(plans)


def detect(ctx) -> int:
    """The number of edits ``apply`` would make; 0 when no file holds a ``status_ref`` or a retired status id."""
    return sum(count(ctx.documents.load(rel).data) for rel in _spec_files(ctx.spec_root))


def apply(ctx) -> ScriptResult:
    """Strip every file; the runner writes the changed ones."""
    edits = 0
    for rel in _spec_files(ctx.spec_root):
        edits += strip(ctx.documents.load(rel).data)
    return ScriptResult(edits=edits)


def verify(before, after) -> list[Problem]:
    """No step or plan file keeps a ``status_ref`` or a status id in ``canonical_refs_used``."""
    problems: list[Problem] = []
    for rel, document in sorted(after.documents.items()):
        head, _, tail = rel.partition("/")
        is_step = not tail and STEP_JSON_RE.match(head)
        is_plan = head == PLAN_DIR_NAME and tail.endswith(".json")
        if (is_step or is_plan) and count(document):
            problems.append(Problem(f"{rel} still holds {count(document)} status_ref key(s) or status id(s)", rel))
    return problems
