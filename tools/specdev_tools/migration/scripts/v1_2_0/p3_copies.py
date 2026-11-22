"""``p3_copies``: the artifact-level ``trace`` of a step file is removed (DEVSPEC-218: FR copies).

A 1.1.1 file carries a top-level ``trace`` whose entries' ``note`` text often holds the statement of an FR word for word.
1.2.0 keeps a statement in one place (step 04) and a link as a link, so the artifact-level ``trace`` is not coverage
(DOC L1182) and is removed; the typed entries of a NODE's own ``trace`` are converted by ``p3_convert`` first.  Rows with
disposition ``copy-dropped`` of ``migration/maps/v1_2_0.yaml`` name the steps.  The report prints how many entries went and
how many of their notes were at least 50 characters long (the size of the text that was copied).
"""

from __future__ import annotations

from typing import Any

from specdev_tools.migration.maps import LEGACY_STEP_IDS, shape_rows
from specdev_tools.migration.registry import PHASE_SHAPES, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.spec_reads import last_key, row_step, step_file

SCRIPT = ScriptSpec(id="p3_copies", phase=PHASE_SHAPES, requires=("p3_convert", "p3_ordering"), touches=LEGACY_STEP_IDS)

_LONG_NOTE = 50


def _traced_files(ctx) -> list[tuple[str, str]]:
    """``(row id, file)`` of every step file that holds the artifact-level key of a ``copy-dropped`` row."""
    found = []
    for row in shape_rows(SCRIPT.id):
        name = step_file(ctx, row_step(row))
        if name and last_key(row["path"]) in ctx.documents.load(name).data:
            found.append((row["id"], name))
    return found


def _notes(entries: Any) -> list[str]:
    return [e["note"] for e in entries if isinstance(e, dict) and isinstance(e.get("note"), str)] if isinstance(entries, list) else []


def detect(ctx) -> int:
    """Files that still hold an artifact-level ``trace``."""
    return len(_traced_files(ctx))


def apply(ctx) -> ScriptResult:
    """Remove the artifact-level ``trace`` of each file the map names."""
    rows = {row["id"]: row for row in shape_rows(SCRIPT.id)}
    residue: list[str] = []
    done = _traced_files(ctx)
    for row_id, name in done:
        data = ctx.documents.load(name).data
        key = last_key(rows[row_id]["path"])
        notes = _notes(data[key])
        residue.append(f"{row_id}: {name} {key}: {len(data[key]) if isinstance(data[key], list) else 1} entries removed, {sum(len(n) >= _LONG_NOTE for n in notes)} long notes")
        del data[key]
    return ScriptResult(edits=len(done), residue=tuple(residue))


def verify(before, after) -> list[Problem]:
    """No file of the map holds its artifact-level ``trace`` any more."""
    keys = {last_key(row["path"]) for row in shape_rows(SCRIPT.id)}
    return [
        Problem(f"{rel}: the artifact-level {sorted(keys & set(document))} is still there", rel)
        for rel, document in sorted(after.documents.items())
        if isinstance(document, dict) and "/" not in rel and keys & set(document) and rel[:2] in {r["id"][3:5] for r in shape_rows(SCRIPT.id)}
    ]
