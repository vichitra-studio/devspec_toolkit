"""Verification and evidence records (E774): the files under ``<spec>/extras/verification/``.

A record file is ``{"$schema": <the record schema>, "records": [<one record>]}``; the file name without ``.json`` is the
record id.  Each kind owns the files whose name starts with its id prefix (``ver-``, ``evd-``): the registry gives one
glob per kind, so the builder reads a file as exactly one kind.  ``check_records`` finds a file that is not a record of
the kind its name declares, and a file that holds more than one record.  The links of a record are resolved by the
``graph`` check (E700 to E702), not here.  No command here writes a record.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.core.loaders import read_json_object
from specdev_tools.core.schema_validate import SchemaValidationError, schema_violations
from specdev_tools.graph.model import Graph, Node
from specdev_tools.trace.lockfile import MERGE_CHECK_OWNER

RECORDS_DIR = "extras/verification"
RECORD_FILE_SUFFIX = ".json"


def record_files(spec_dir: str) -> list[str]:
    """Paths, relative to *spec_dir* and ``/``-separated, of the JSON files under ``extras/verification/``, sorted.

    Empty when the folder does not exist.
    """
    folder = Path(spec_dir) / RECORDS_DIR
    if not folder.is_dir():
        return []
    return sorted(path.relative_to(spec_dir).as_posix() for path in folder.glob(f"*{RECORD_FILE_SUFFIX}") if path.is_file())


def _finding(rel: str, message: str, node_id: str | None = None) -> SpecError:
    return make_error("E774", f"{rel}: {message}", file=rel, owner=MERGE_CHECK_OWNER, node_id=node_id)


def _schema_findings(rel: str, document: dict, repo_root: str) -> list[SpecError]:
    """One finding for each violation of the schema the file names in ``$schema``, or one for a schema that cannot be applied."""
    try:
        violations = schema_violations(repo_root, document)
    except SchemaValidationError as exc:
        return [_finding(rel, f"the schema of the record cannot be applied: {exc}")]
    ordered = sorted(violations, key=lambda item: (tuple(str(part) for part in item.path), item.message))
    return [_finding(rel, f"{'/'.join(str(part) for part in item.path) or 'file'}: {item.message}") for item in ordered]


def _node_findings(rel: str, nodes: list[Node]) -> list[SpecError]:
    """Findings for a schema-valid file: it must hold one record of the kind its name declares, named as the file."""
    if not nodes:
        return [_finding(rel, "no record found: the file is not a record of the kind its name prefix declares (ver- or evd-)")]
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
