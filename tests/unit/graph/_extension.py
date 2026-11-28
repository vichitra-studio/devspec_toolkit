"""The worked example with the database extension of ``tests/fixtures/extension_example``, for the unit tests of extension kinds.

``extension_host`` copies the worked example (``spec`` and ``docs``, no git), puts the extension's two files under
``spec/extensions`` and applies the deltas that declare it and refine its table.  The helpers below edit the copy; none
of them clears a cache, so a test that edits a file and reads again also shows that the edit is seen.
"""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from integration._step_gate_support import apply_delta
from specdev_tools.core.errors import SpecError
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.kinds import KindRegistryError
from specdev_tools.graph.model import Graph
from specdev_tools.trace.lockfile import write_lock

from ..trace._lock_support import EXAMPLE_HOST, ROOT, lock_for

EXTENSION = ROOT / "tests" / "fixtures" / "extension_example"
DELTAS = EXTENSION / "deltas"
SCHEMA_PLACE = "extensions/ext_01_database.schema.json"
DATA_PLACE = "extensions/ext_01_database.json"
MANIFEST = "13_extension_manifest.json"
ROADMAP = "14_roadmap.json"
DECLARE, REFINE = "declare_extension", "refine_table"
"""The two deltas of the whole example: the manifest entry, and the task criterion that refines the table."""
TABLE, PARKED_TABLE, DATASTORE, ENTRY, CRITERION = "tbl-reset-token", "tbl-member-credential", "ds-identity", "ext-01-database", "tc-reset-token-table"
FIXTURE = "fix-password-reset-reused-token"
"""The fixture the table and the criterion that refines it both name in ``verified_by``."""
STEP_13 = "step:13"
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"

Change = Callable[[dict[str, Any]], Any]


def extension_host(destination: Path, *deltas: str, declared: bool = True, refined: bool = True) -> Path:
    """The worked example copied to *destination* with the extension's files, its entry (*declared*) and the criterion that refines its table (*refined*), then *deltas*."""
    shutil.copytree(EXAMPLE_HOST, destination)
    shutil.copytree(EXTENSION / "spec" / "extensions", destination / "spec" / "extensions")
    for name in (*((DECLARE,) if declared else ()), *((REFINE,) if refined else ()), *deltas):
        apply_delta(destination, name, folder=DELTAS)
    return destination


def spec_of(host: Path) -> Path:
    return host / "spec"


def read(host: Path, place: str) -> dict[str, Any]:
    return json.loads((spec_of(host) / place).read_text(encoding="utf-8"))


def edit(host: Path, place: str, change: Change) -> None:
    """Apply *change* to the parsed file *place* of the spec folder of *host* and write it back."""
    path = spec_of(host) / place
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def tables(schema: dict[str, Any]) -> dict[str, Any]:
    """The ``tables`` property of the example schema: the array that carries the ``x-node`` of kind ``table``."""
    return schema["properties"]["tables"]


def datastores(schema: dict[str, Any]) -> dict[str, Any]:
    return schema["properties"]["datastores"]


def table_fields(schema: dict[str, Any]) -> dict[str, Any]:
    """The properties of one table: where its link fields and their ``x-link`` are."""
    return tables(schema)["items"]["properties"]


def item(document: dict[str, Any], collection: str, id_field: str, node_id: str) -> dict[str, Any]:
    """The item of *collection* of a data file whose *id_field* is *node_id*."""
    return next(found for found in document[collection] if found.get(id_field) == node_id)


def table(document: dict[str, Any], node_id: str = TABLE) -> dict[str, Any]:
    return item(document, "tables", "table_id", node_id)


def criterion(roadmap: dict[str, Any], node_id: str = CRITERION) -> dict[str, Any]:
    """The task criterion *node_id* of the roadmap document."""
    return next(
        found for milestone in roadmap["milestones"] for task in milestone["tasks"] for found in task["acceptance_criteria"]
        if found.get("criterion_id") == node_id
    )


def graph_of(host: Path) -> Graph:
    return build_graph(str(spec_of(host)), str(ROOT))


def accept_links(host: Path) -> None:
    """Write the trace lock of *host* so that it accepts every link as the files have it now."""
    write_lock(str(spec_of(host)), lock_for(graph_of(host), host))


def refusal(host: Path) -> SpecError:
    """The finding with which the graph of *host* is refused; fails when it is built."""
    try:
        graph_of(host)
    except KindRegistryError as error:
        return error.error
    raise AssertionError("the graph was built: no extension schema was refused")


def lines(error: SpecError) -> list[str]:
    """The lines an E520 of the extension schemas lists (the text after its first line), each without its indent."""
    return [line.strip() for line in error.message.splitlines()[1:]]


SECOND_SCHEMA_PLACE = "extensions/ext_02_cache.schema.json"
SECOND_DATA_PLACE = "extensions/ext_02_cache.json"


def second_schema(kind: str = "cache", role: str = "context", **more: Any) -> dict[str, Any]:
    """The schema of a second extension ``ext-02-cache`` that declares one kind *kind* of role *role* with a ``derives_from`` to a component; *more* is merged into the item properties."""
    properties: dict[str, Any] = {
        "cache_id": {"$ref": "vc:core:atoms#kebabId"},
        "name": {"type": "string"},
        "lifecycle": {"$ref": "vc:core:graph#lifecycle"},
        "derives_from": {
            "type": "array",
            "items": {"$ref": "vc:core:atoms#kebabId"},
            "x-link": {"kinds": ["component"], "required": True, "built": True},
        },
        **more,
    }
    obligation = role.startswith("obligation")
    if obligation:
        properties.update({"scope": {"$ref": "vc:core:graph#scope"}, "scope_reason": {"$ref": "vc:core:graph#scopeReason"}})
    return {
        "$schema": DRAFT_2020_12,
        "$id": "vc:ext-02-cache",
        "type": "object",
        "properties": {
            "caches": {
                "type": "array",
                "x-node": {"kind": kind, "role": role, "contract": ["name"], "id": "cache_id"},
                "items": {
                    "type": "object",
                    "properties": properties,
                    "required": ["cache_id", "name"],
                    **({"allOf": [{"$ref": "vc:core:graph#scopeReasonRule"}]} if obligation else {}),
                },
            },
        },
        "allOf": [{"$ref": "vc:core:step-base"}],
    }


def second_data(*caches: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "vc:ext-02-cache", "id": "ext-cache-password-reset", "owner": "data", "created_at": "2026-11-15T00:00:00Z",
        "caches": list(caches), "canonical_refs_used": [],
    }


def add_second(host: Path, schema: dict[str, Any], *caches: dict[str, Any]) -> None:
    """Write the schema and the data file of ``ext-02-cache`` into *host* (no manifest entry: the graph reads the folder, not the manifest)."""
    (spec_of(host) / SECOND_SCHEMA_PLACE).write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    (spec_of(host) / SECOND_DATA_PLACE).write_text(json.dumps(second_data(*caches), indent=2) + "\n", encoding="utf-8")
