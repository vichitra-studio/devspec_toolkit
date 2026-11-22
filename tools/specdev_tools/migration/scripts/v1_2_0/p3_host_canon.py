"""``p3_host_canon``: the host's own canon (``spec/canon``) follows the toolkit's kinds.

``migration/maps/v1_2_0.yaml`` (``host_canon``) lists the canon kinds the toolkit no longer has (``retired_kinds``) and the
kinds it renamed (``renamed_kinds``, ``inv`` to ``invariant``).  A host kind file of a retired kind is deleted and its
entries leave ``canon/manifest.json``; a renamed kind's file is rewritten under its new name (kind, entry ids
``cn:<tier>:inv:x`` to ``cn:<tier>:invariant:x``) and the same rewrite is applied to the manifest, ``canon/aliases.json`` when
the host has one, and every ``cn:`` reference in the step files.  Kinds the toolkit still has (``interface``,
``dependency``) are left alone whatever the host's age.  The report names each file and the number of entries.
"""

from __future__ import annotations

import copy
import os
import re
from typing import Any

from specdev_tools.core.step_paths import STEP_JSON_RE
from specdev_tools.migration.maps import shape_map
from specdev_tools.migration.registry import PHASE_SHAPES, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.scripts.v1_2_0.p2_plan_milestone_key import plan_rels
from specdev_tools.migration.scripts.v1_2_0.p3_remove import STEPS

SCRIPT = ScriptSpec(id="p3_host_canon", phase=PHASE_SHAPES, requires=("p2_id_collisions",), touches=("canon", *STEPS))

KINDS_DIR = "canon/kinds"
MANIFEST = "canon/manifest.json"
ALIASES = "canon/aliases.json"


def _rewrite(value: Any, renamed: dict[str, str]) -> int:
    """Rename kinds in place inside *value*: ``cn:<tier>:<old>:x`` ids and the ``kind`` of an entry that carries such an id; returns the count."""
    count = 0
    slots = list(value.items()) if isinstance(value, dict) else list(enumerate(value)) if isinstance(value, list) else []
    for slot, held in slots:
        new = _rename_id(held, renamed) if isinstance(held, str) else held
        if new != held:
            value[slot] = new
            count += 1
        elif not isinstance(held, str):
            count += _rewrite(held, renamed)
    if isinstance(value, dict) and value.get("kind") in renamed and isinstance(value.get("id"), str) and value["id"].startswith("cn:"):
        value["kind"] = renamed[value["kind"]]
        count += 1
    return count


def _rename_id(text: str, renamed: dict[str, str]) -> str:
    match = re.match(r"^(cn:[a-z0-9_-]+:)([a-z0-9_-]+)(:.*)$", text)
    return f"{match.group(1)}{renamed[match.group(2)]}{match.group(3)}" if match and match.group(2) in renamed else text


class _Work:
    """One run's edits to the host canon; the live documents when *write*, else private copies."""

    def __init__(self, ctx, write: bool) -> None:
        self.ctx, self.write = ctx, write
        self.edits = 0
        self.residue: list[str] = []
        self.remove_files: list[str] = []
        self.create: list[tuple[str, Any]] = []
        self.docs: dict[str, Any] = {}
        self.config = shape_map()["host_canon"]

    def data(self, rel: str) -> Any:
        if rel not in self.docs:
            held = self.ctx.documents.load(rel).data
            self.docs[rel] = held if self.write else copy.deepcopy(held)
        return self.docs[rel]

    def exists(self, rel: str) -> bool:
        return os.path.isfile(os.path.join(self.ctx.spec_root, rel))

    def kind_files(self) -> list[str]:
        folder = os.path.join(self.ctx.spec_root, KINDS_DIR)
        return [f"{KINDS_DIR}/{n}" for n in sorted(os.listdir(folder)) if n.endswith(".json")] if os.path.isdir(folder) else []

    def run(self) -> None:
        retired, renamed = set(self.config["retired_kinds"]), dict(self.config["renamed_kinds"])
        for rel in self.kind_files():
            document = self.data(rel)
            kind = document.get("kind") if isinstance(document, dict) else None
            if kind in retired:
                self.remove_files.append(rel)
                self.residue.append(f"{rel}: kind {kind} is retired; file deleted ({len(document.get('entries') or [])} entries)")
            elif kind in renamed:
                self._rename_file(rel, document, renamed)
        if self.exists(MANIFEST):
            self._manifest(retired, renamed)
        if renamed:
            self._rewrite_files([ALIASES, *self._step_files()], renamed)

    def _rename_file(self, rel: str, document: dict[str, Any], renamed: dict[str, str]) -> None:
        target = f"{KINDS_DIR}/{renamed[document['kind']]}.json"
        if self.exists(target):
            self.residue.append(f"{rel}: kind {document['kind']} is renamed {renamed[document['kind']]}, but {target} exists; left as it is")
            return
        moved = copy.deepcopy(document)
        moved["kind"] = renamed[document["kind"]]
        self.edits += 1 + _rewrite(moved, renamed)
        self.create.append((target, moved))
        self.remove_files.append(rel)
        self.residue.append(f"{rel}: kind {document['kind']} renamed {moved['kind']}; written as {target}")

    def _manifest(self, retired: set[str], renamed: dict[str, str]) -> None:
        manifest = self.data(MANIFEST)
        entries = manifest.get("entries") if isinstance(manifest, dict) else None
        if not isinstance(entries, list):
            return
        kept = [e for e in entries if not (isinstance(e, dict) and e.get("kind") in retired)]
        if len(kept) != len(entries):
            self.edits += len(entries) - len(kept)
            self.residue.append(f"{MANIFEST}: {len(entries) - len(kept)} entries of retired kinds removed")
            entries[:] = kept
        count = _rewrite(manifest, renamed)
        self.edits += count
        if count:
            self.residue.append(f"{MANIFEST}: {count} renamed kind values and ids rewritten")

    def _step_files(self) -> list[str]:
        return [n for n in sorted(os.listdir(self.ctx.spec_root)) if STEP_JSON_RE.match(n)] + plan_rels(self.ctx)

    def _rewrite_files(self, rels: list[str], renamed: dict[str, str]) -> None:
        for rel in rels:
            if self.exists(rel):
                count = _rewrite(self.data(rel), renamed)
                self.edits += count
                if count:
                    self.residue.append(f"{rel}: {count} renamed canon ids rewritten")


def detect(ctx) -> int:
    """Files to delete or rename and values to rewrite."""
    work = _Work(ctx, write=False)
    work.run()
    return work.edits + len(work.remove_files)


def apply(ctx) -> ScriptResult:
    """Delete retired kind files, rename kinds, rewrite the manifest, aliases and references."""
    work = _Work(ctx, write=True)
    work.run()
    for rel, data in work.create:
        ctx.documents.create(rel, data)
    for rel in work.remove_files:
        os.remove(os.path.join(ctx.spec_root, rel))
    return ScriptResult(edits=work.edits + len(work.remove_files), residue=tuple(work.residue))


def verify(before, after) -> list[Problem]:
    """No kind file of a retired or renamed kind is left, and the manifest has no entry of a retired kind."""
    config = shape_map()["host_canon"]
    gone = set(config["retired_kinds"]) | set(config["renamed_kinds"])
    problems = [
        Problem(f"{rel}: a canon kind file of the kind {document.get('kind')} is left", rel)
        for rel, document in sorted(after.documents.items())
        if rel.startswith(KINDS_DIR + "/") and isinstance(document, dict) and document.get("kind") in gone
    ]
    manifest = after.documents.get(MANIFEST)
    for entry in (manifest or {}).get("entries", []) if isinstance(manifest, dict) else []:
        if isinstance(entry, dict) and entry.get("kind") in gone:
            problems.append(Problem(f"{MANIFEST}: the entry {entry.get('id')} has the retired or renamed kind {entry.get('kind')}", MANIFEST))
    return problems
