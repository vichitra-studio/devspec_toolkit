"""Record files (E774): the verification, evidence and at-deploy records under ``<spec>/extras/verification/`` and the sign-off records under ``<spec>/extras/signoff/``.

A record file is ``{"$schema": <the record schema>, "records": [<one record>]}``; the file name without ``.json`` is the
record id.  Each kind owns the files whose name starts with its id prefix (``ver-``, ``evd-``, ``dep-``, ``so-``): the
registry gives one glob per kind, so the builder reads a file as exactly one kind.  ``check_records`` finds a file that is not a record of
the kind its name declares, and a file that holds more than one record.  The links of a record are resolved by the
``graph`` check (E700 to E702), not here.  No command here writes a record (``prune_orphan_records`` deletes the records whose node is gone); the stage and ``proves`` lint of the bindings is ``verify/lint.py``.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.core.loaders import read_json_object
from specdev_tools.core.schema_validate import SchemaValidationError, schema_violations, violation_text
from specdev_tools.graph.kinds import RECORD_ROLE
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.names import ABOUT, EXECUTION_RECORD, VERIFIES
from specdev_tools.trace.lockfile import MERGE_CHECK_OWNER

RECORDS_DIR = "extras/verification"
SIGNOFF_DIR = "extras/signoff"
RECORD_FOLDERS = (RECORDS_DIR, SIGNOFF_DIR)
RECORD_FILE_SUFFIX = ".json"


def record_files(spec_dir: str) -> list[str]:
    """Paths, relative to *spec_dir* and ``/``-separated, of the JSON files under ``extras/verification/`` and ``extras/signoff/``, sorted.

    Empty when neither folder exists.
    """
    root = Path(spec_dir)
    return sorted(
        path.relative_to(root).as_posix()
        for folder in RECORD_FOLDERS
        if (root / folder).is_dir()
        for path in (root / folder).glob(f"*{RECORD_FILE_SUFFIX}")
        if path.is_file()
    )


def _finding(rel: str, message: str, node_id: str | None = None) -> SpecError:
    return make_error("E774", f"{rel}: {message}", file=rel, owner=MERGE_CHECK_OWNER, node_id=node_id)


def _schema_findings(rel: str, document: dict, repo_root: str) -> list[SpecError]:
    """One finding for each violation of the schema the file names in ``$schema``, or one for a schema that cannot be applied."""
    try:
        violations = schema_violations(repo_root, document)
    except SchemaValidationError as exc:
        return [_finding(rel, f"the schema of the record cannot be applied: {exc}")]
    ordered = sorted(violations, key=lambda item: (tuple(str(part) for part in item.path), item.message))
    return [_finding(rel, f"{'/'.join(str(part) for part in item.path) or 'file'}: {violation_text(item)}") for item in ordered]


def _node_findings(rel: str, nodes: list[Node]) -> list[SpecError]:
    """Findings for a schema-valid file: it must hold one record of the kind its name declares, named as the file."""
    if not nodes:
        return [_finding(rel, "no record found: the file is not a record of the kind its name prefix declares (ver-, evd-, dep- or so-)")]
    stem = Path(rel).stem
    return [_finding(rel, f"the file name '{stem}' is not the record id '{node.id}'", node.id) for node in nodes if node.id != stem]


def check_records(spec_dir: str, repo_root: str, graph: Graph) -> list[SpecError]:
    """E774 for every problem in the record files of *spec_dir*; owner ``merge-check``.

    *graph* is the graph built from *spec_dir*.  A file is reported when it is not a JSON object, violates the schema
    its ``$schema`` names (a second record, a wrong id prefix, a missing output guard), holds no record of the kind its
    name declares, or has a file name other than its record id.  A file that violates its schema is reported for that
    only.  Unresolved links are not reported here: the resolver reports them (E700).
    """
    nodes_by_file: dict[str, list[Node]] = defaultdict(list)
    for node in graph.nodes:
        nodes_by_file[node.file].append(node)
    findings: list[SpecError] = []
    for rel in record_files(spec_dir):
        document = read_json_object(Path(spec_dir) / rel)
        if document is None:
            findings.append(_finding(rel, "unreadable or not a JSON object"))
            continue
        problems = _schema_findings(rel, document, repo_root)
        findings.extend(problems or _node_findings(rel, nodes_by_file.get(rel, [])))
    return findings


_RECORD_LINKS = (VERIFIES, ABOUT)


def _dangling(node: Node, graph: Graph, gone: set[str]) -> bool:
    """Whether every target of the ``verifies`` or ``about`` links of the record *node* is no node of *graph* or is in *gone*."""
    targets = [graph.canonical_id(link.target) for link in node.links if link.field in _RECORD_LINKS]
    return bool(targets) and all(graph.find(target) is None or target in gone for target in targets)


def orphan_records(graph: Graph) -> list[Node]:
    """The record nodes whose every ``verifies``/``about`` target is gone, in graph order.

    A record about an orphan record is an orphan too: the rule is applied again until no record is added.
    """
    records = [node for node in graph.nodes if node.role == RECORD_ROLE]
    gone: set[str] = set()
    while added := [node.id for node in records if node.id not in gone and _dangling(node, graph, gone)]:
        gone.update(added)
    return [node for node in records if node.id in gone]


def prune_orphan_records(spec_dir: str, graph: Graph, dry_run: bool = False) -> list[Path]:
    """Delete the orphan record FILES of *graph* from *spec_dir* and return their paths in graph order; with *dry_run*, delete nothing.

    An execution record is not a file of its own: it is an item of a plan file, which this never deletes
    (``specdev plan record --prune`` removes such a record from its plan).  The caller holds the write lock and built
    *graph* under it.
    """
    paths = [Path(spec_dir) / node.file for node in orphan_records(graph) if node.kind != EXECUTION_RECORD]
    if not dry_run:
        for path in paths:
            path.unlink()
    return paths
