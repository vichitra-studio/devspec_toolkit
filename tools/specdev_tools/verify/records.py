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
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from specdev_tools.core.errors import refusal
from specdev_tools.core.json_utils import JQ_INDENT
from specdev_tools.core.loaders import read_json_object
from specdev_tools.core.schema_validate import schema_violations, violation_text
from specdev_tools.graph.contract import item_of
from specdev_tools.graph.ids import mint_slug, suggest_prefix
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.names import BINDING_KIND, THIRD_PARTY, VERIFIES
from specdev_tools.graph.stages import DEFAULT_STAGE, STAGES, binding_stage
from specdev_tools.trace.lockfile import replace_file_atomically
from specdev_tools.trace.records import RECORD_FILE_SUFFIX, RECORDS_DIR

EVIDENCE_KIND = "evidence-record"
ATTESTATION_TYPE = "attestation"
RUN_TYPE = "run"
VERIFICATION_SCHEMA = "vc:extras:verification-record"
EVIDENCE_SCHEMA = "vc:extras:evidence-record"
AT_DEPLOY_SCHEMA = "vc:extras:at-deploy-record"
SIGNOFF_SCHEMA = "vc:extras:signoff-record"
BINDING_PREFIX = "ver-"
EVIDENCE_PREFIX = "evd-"
INSTALL_CHECK_SUFFIX = "-install"
BINDING_ID = re.compile(rf"^{re.escape(BINDING_PREFIX)}[a-z0-9]+(?:-[a-z0-9]+)*$")
"""The form of a binding id: ``ver-`` and a kebab-case name."""


def id_suffix(kind: str, node_id: str) -> str:
    """*node_id* without the prefix ``graph.ids`` suggests for *kind* (the whole id when it does not start with it).

    A verifier that wears the prefix of another kind (a fixture named ``job-x``) keeps it in the binding id (``ver-job-x``); a binding that exists keeps its id on a re-bind, so no stored id changes.
    """
    prefix = suggest_prefix(kind)
    return node_id.removeprefix(prefix) if prefix else node_id


def evidence_id(binding_id: str, stage: str) -> str:
    """The id of the run evidence of *binding_id* at *stage*: ``evd-``, the binding id without ``ver-``, then the stage."""
    return f"{EVIDENCE_PREFIX}{binding_id.removeprefix(BINDING_PREFIX)}-{stage}"


def install_check_id(third_party_id: str, env: str) -> str:
    """The id of the install-check record of *third_party_id* for *env*: ``evd-``, the id without its prefix, the environment, then ``-install``.

    A run's evidence id ends in a stage and ``install`` is not a stage, so the two kinds of record never share a file.

    Raises:
        FindingError: E767 when *env* has no letter or digit to make an id from.
    """
    try:
        slug = mint_slug(env, ())
    except ValueError as exc:
        raise refusal("E767", f"the environment '{env}' has no letter or digit to name the install-check record from; give --env a name such as prod") from exc
    return f"{EVIDENCE_PREFIX}{id_suffix(THIRD_PARTY, third_party_id)}-{slug}{INSTALL_CHECK_SUFFIX}"


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
    targets = [graph.canonical_id(link.target) for link in node.links if link.field == VERIFIES]
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
            "type": RUN_TYPE,
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


def _hash_map(value: object) -> dict[str, str]:
    return {key: text for key, text in value.items() if isinstance(key, str) and isinstance(text, str)} if isinstance(value, Mapping) else {}


def _about(item: Mapping[str, Any]) -> tuple[str, ...] | None:
    about = item.get("about")
    return tuple(about) if isinstance(about, list) and about and all(isinstance(name, str) for name in about) else None


def evidence_from_item(item: Mapping[str, Any]) -> Evidence | None:
    """The run evidence a stored evidence record *item* states; ``None`` when it is another type or is not shaped as the evidence schema says (the record check reports that)."""
    about, stage, tree = _about(item), item.get("stage", DEFAULT_STAGE), item.get("tested_tree")
    code, matched, digest = item.get("exit_code"), item.get("guard_matched"), item.get("output_hash")
    if item.get("type", RUN_TYPE) != RUN_TYPE or about is None or stage not in STAGES or not isinstance(tree, str):
        return None
    if not (isinstance(code, int) and isinstance(matched, bool) and isinstance(digest, str) and isinstance(item.get("evidence_id"), str)):
        return None
    return Evidence(
        evidence_id=item["evidence_id"], about=about, stage=stage, tested_tree=tree, exit_code=code, guard_matched=matched,
        output_hash=digest, installed_versions=_hash_map(item.get("installed_versions")), recorded_hashes=_hash_map(item.get("recorded_hashes")),
    )


def _only_record(path: str) -> Mapping[str, Any] | None:
    """The one record of the record file at *path*; ``None`` when there is no file, it is unreadable, or it does not hold exactly one record: the one reading of "the record" of an evidence file."""
    document = read_json_object(path)
    records = document.get("records") if document is not None else None
    return records[0] if isinstance(records, list) and len(records) == 1 and isinstance(records[0], dict) else None


def read_evidence(folder: str, evidence_id: str) -> Evidence | None:
    """The run evidence stored as ``<evidence_id>.json`` in *folder*; ``None`` when there is no such file, it is unreadable or it is not a run record."""
    item = _only_record(os.path.join(folder, record_file(evidence_id)))
    return evidence_from_item(item) if item is not None else None


@dataclass(frozen=True)
class Attestation:
    """An attestation record as the graph holds it: a person states that the nodes in ``about`` hold, on the code tree ``tested_tree``.

    ``recorded_hashes`` maps each attested node to its content hash when the attestation was made.
    """

    evidence_id: str
    about: tuple[str, ...]
    stage: str
    tested_tree: str
    recorded_hashes: Mapping[str, str]


def attestations_about(graph: Graph, node_id: str) -> list[Attestation]:
    """The attestation records of *graph* that are about *node_id* (by its id or an old id), in graph order."""
    wanted = graph.canonical_id(node_id)
    found: list[Attestation] = []
    for node in graph.by_kind.get(EVIDENCE_KIND, ()):
        item = item_of(graph, node) or {}
        about, stage, tree = _about(item), item.get("stage", DEFAULT_STAGE), item.get("tested_tree")
        if item.get("type") != ATTESTATION_TYPE or about is None or stage not in STAGES or not isinstance(tree, str):
            continue
        if wanted in (graph.canonical_id(name) for name in about):
            found.append(Attestation(node.id, tuple(graph.canonical_id(name) for name in about), stage, tree, _hash_map(item.get("recorded_hashes"))))
    return found


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


def write_at_deploy(folder: str, repo_root: str, item: Mapping[str, Any]) -> str:
    """Write the at-deploy record *item* as ``<deploy_id>.json`` in *folder* (``records_folder``); returns the file name.

    The caller holds the write lock.  Raises ``FindingError`` (E774) when *item* breaks the record schema; nothing is written then.
    """
    return _write_record(folder, repo_root, AT_DEPLOY_SCHEMA, item["deploy_id"], item)


def write_signoff(folder: str, repo_root: str, item: Mapping[str, Any]) -> str:
    """Write the sign-off record *item* as ``<signoff_id>.json`` in *folder* (the sign-off folder of the spec); returns the file name.

    The caller holds the write lock.  Raises ``FindingError`` (E774) when *item* breaks the record schema; nothing is written then.
    """
    return _write_record(folder, repo_root, SIGNOFF_SCHEMA, item["signoff_id"], item)
