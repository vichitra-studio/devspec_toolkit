"""Bindings and evidence: read a binding from the graph, build and write the record files of ``verify bind`` and ``verify run``.

A binding is a verification record (``ver-<id>.json``); the evidence of a run is an evidence record (``evd-<id>.json``).
Both live in ``extras/verification/`` as ``{"$schema": ..., "records": [<one record>]}`` and the file name is the record id
(``trace/records.py`` checks that).  A record has no lock entry, so a write needs no lock file: it is one atomic replace of
one file.  The functions that write take no write lock; the caller holds it (``with_write_lock``) for as short a time as it
can, because the lock fails at once when another write runs.
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from specdev_tools.core.errors import FindingError, make_error
from specdev_tools.core.json_utils import JQ_INDENT
from specdev_tools.core.schema_validate import schema_violations, violation_text
from specdev_tools.graph.contract import item_of
from specdev_tools.graph.model import Graph, Node
from specdev_tools.proof.stages import binding_stage
from specdev_tools.trace.lockfile import replace_file_atomically
from specdev_tools.trace.records import RECORD_FILE_SUFFIX, RECORDS_DIR

BINDING_KIND = "verification-record"
VERIFICATION_SCHEMA = "vc:extras:verification-record"
EVIDENCE_SCHEMA = "vc:extras:evidence-record"
BINDING_PREFIX = "ver-"
EVIDENCE_PREFIX = "evd-"
_VERIFIES = "verifies"


def refusal(code: str, message: str) -> FindingError:
    """The finding a command prints before it exits 1: *code* with *message*, no owner, no node."""
    return FindingError(make_error(code, message))


@dataclass(frozen=True)
class Binding:
    """A verification record as the graph holds it: the verifier it covers, what it proves, its stage, its commands and its guard."""

    id: str
    verifier: str
    commands: tuple[str, ...]
    guard: str
    stage: str
    proves: tuple[str, ...]


def binding_of(node: Node, graph: Graph) -> Binding:
    """The binding the verification record *node* declares; ``proves`` ids are resolved to current ids (a rename leaves the old id in the file)."""
    item = item_of(graph, node) or {}
    targets = [graph.canonical_id(link.target) for link in node.links if link.field == _VERIFIES]
    return Binding(
        id=node.id,
        verifier=targets[0] if targets else "",
        commands=tuple(item.get("commands", ())),
        guard=item.get("output_guard", ""),
        stage=binding_stage(node, graph),
        proves=tuple(graph.canonical_id(target) for target in item.get("proves", ())),
    )


def all_bindings(graph: Graph) -> list[Binding]:
    """Every binding of *graph*, in graph order."""
    return [binding_of(node, graph) for node in graph.by_kind.get(BINDING_KIND, ())]


@dataclass(frozen=True)
class Evidence:
    """The evidence of one run: what ``verify run`` writes as an evidence record, or returns in memory with ``--no-record``.

    ``notes`` are the warning lines the run produced for this binding; they are not part of the record.
    """

    evidence_id: str
    about: tuple[str, ...]
    stage: str
    tested_tree: str
    exit_code: int
    guard_matched: bool
    output_hash: str
    installed_versions: Mapping[str, str] = field(default_factory=dict)
    recorded_hashes: Mapping[str, str] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """A run passes when the commands exited 0 and the output matched the guard."""
        return self.exit_code == 0 and self.guard_matched

    def to_item(self) -> dict[str, Any]:
        """The record of the evidence, as the evidence schema states it (``recorded_hashes`` only when there are any)."""
        item: dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "about": list(self.about),
            "type": "run",
            "stage": self.stage,
            "tested_tree": self.tested_tree,
            "exit_code": self.exit_code,
            "guard_matched": self.guard_matched,
            "output_hash": self.output_hash,
            "installed_versions": dict(self.installed_versions),
        }
        if self.recorded_hashes:
            item["recorded_hashes"] = dict(self.recorded_hashes)
        return item


def records_folder(spec_root: str) -> str:
    """The folder that holds the record files of the spec folder *spec_root*."""
    return os.path.join(spec_root, RECORDS_DIR)


def record_file(record_id: str) -> str:
    """The name of the record file of *record_id*."""
    return f"{record_id}{RECORD_FILE_SUFFIX}"


def _write_record(folder: str, repo_root: str, schema: str, record_id: str, item: Mapping[str, Any]) -> str:
    name = record_file(record_id)
    document = {"$schema": schema, "records": [dict(item)]}
    problems = sorted(f"{'/'.join(str(part) for part in v.path) or 'file'}: {violation_text(v)}" for v in schema_violations(repo_root, document))
    if problems:
        raise refusal("E774", f"{name}: the record would not satisfy its schema ({problems[0]})")
    os.makedirs(folder, exist_ok=True)
    replace_file_atomically(os.path.join(folder, name), json.dumps(document, indent=JQ_INDENT, ensure_ascii=False) + "\n")
    return name


def write_binding(folder: str, repo_root: str, item: Mapping[str, Any]) -> str:
    """Write (or replace) the verification record *item* as ``<id>.json`` in *folder* (``records_folder``); returns the file name.

    The caller holds the write lock.  Raises ``FindingError`` (E774) when *item* breaks the record schema; nothing is written then.
    """
    return _write_record(folder, repo_root, VERIFICATION_SCHEMA, item["verification_id"], item)


def write_evidence(folder: str, repo_root: str, item: Mapping[str, Any]) -> str:
    """Write (or replace) the evidence record *item* as ``<id>.json`` in *folder* (``records_folder``); returns the file name.

    The caller holds the write lock.  Raises ``FindingError`` (E774) when *item* breaks the record schema; nothing is written then.
    """
    return _write_record(folder, repo_root, EVIDENCE_SCHEMA, item["evidence_id"], item)
