"""Stored computed fields (WI-M5-13): E768 for a node that stores a field the toolkit computes."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.contract import item_at
from specdev_tools.graph.model import Graph
from specdev_tools.trace.computed_fields import COMPUTED_VIEWS, check_stored_computed
from specdev_tools.validation.spec_check import run_spec_check_json

from ..graph._synth import ROOT, accept_links, copy_example, load_doc, write_json

# The "Computed, never stored" rows of DOC section 4.6 (L554-581), as written there.
DOC_COMPUTED_VIEWS = (
    "a link target's kind",
    "impact, coverage, suspects, replay list",
    "built, proven, realisation status, release status",
    "a plan item's task, milestone, fixture and NFRs",
    "task progress",
    "a 14 milestone's 09 milestones",
    "09 capability placement",
    "14 milestone fr_refs and capability_refs; task fr_refs and invariant_refs",
    "a component's reliance on a third party",
    "glossary use",
    "step order",
    "context packs",
)

# The object of each node kind a view scopes, in its schema: (schema file, property path; ``[]`` is an array's items).
SCHEMA_OBJECT = {
    "plan-item": ("16_impl_context.schema.json", ("plan", "spec_alignment", "checklist", "[]")),
    "roadmap-milestone": ("14_roadmap.schema.json", ("milestones", "[]")),
    "task": ("14_roadmap.schema.json", ("milestones", "[]", "tasks", "[]")),
    "anchor-row": ("16_anchor.schema.json", ("plan", "milestone_index", "[]")),
}


def _stored(spec: Path, graph: Graph, kind: str, name: str) -> str:
    """Write ``name`` into the first node of *kind* in its spec file; the node id."""
    node = graph.by_kind[kind][0]
    document = load_doc(spec, node.file)
    item = item_at(document, node.jq_path)
    assert item is not None
    item[name] = "stored"
    write_json(spec, node.file, document)
    return node.id


def _findings(spec: Path) -> list[SpecError]:
    return check_stored_computed(build_graph(str(spec), str(ROOT)))


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    return copy_example(tmp_path / "spec")


@pytest.fixture
def graph(spec: Path) -> Graph:
    return build_graph(str(spec), str(ROOT))


def test_the_worked_example_stores_no_computed_field(graph: Graph) -> None:
    assert check_stored_computed(graph) == []


@pytest.mark.parametrize(
    ("kind", "name", "step"),
    [
        ("task", "fr_refs", "14"),
        ("roadmap-milestone", "deliverables", "14"),
        ("plan-item", "nfr_refs", "16a"),
        ("fr", "content_hash", "04"),
        ("anchor-row", "fr_refs", "16"),
    ],
)
def test_stored_suspects_impact_fr_refs_rejected(spec: Path, graph: Graph, kind: str, name: str, step: str) -> None:
    node_id = _stored(spec, graph, kind, name)

    (finding,) = _findings(spec)

    assert (finding.code, finding.node_id, finding.owner) == ("E768", node_id, f"step:{step}")
    assert f"'{name}'" in finding.message and finding.message.startswith(node_id)
    if name == "content_hash":  # review round 1: say it is computed and not stored; `specdev attest` does not write it
        assert "not stored in a spec file" in finding.message and "attest" not in finding.message
    else:
        assert "specdev" in finding.message
    assert finding.jq_path is not None and finding.jq_path.endswith(f".{name}")


def _property_names(schema: Any) -> Iterator[str]:
    """Every property name declared anywhere under *schema*."""
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key == "properties" and isinstance(value, dict):
                yield from value
            yield from _property_names(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from _property_names(value)


def _properties_of(schema: dict[str, Any]) -> dict[str, Any]:
    """The ``properties`` of *schema*, or of its ``allOf`` member that declares them."""
    if "properties" in schema:
        return schema["properties"]
    return next(member["properties"] for member in schema["allOf"] if "properties" in member)


def _object_schema(file: str, path: tuple[str, ...]) -> Any:
    current: Any = json.loads((ROOT / "schema" / file).read_text(encoding="utf-8"))
    for segment in path:
        current = current["items"] if segment == "[]" else _properties_of(current)[segment]
    return current


def _scoped_schemas(scope: tuple[str, ...] | None) -> list[tuple[str, Any]]:
    """The schemas a scope covers: the object of each scoped kind, or every step schema for every node."""
    if scope is None:
        return [(path.name, json.loads(path.read_text(encoding="utf-8"))) for path in sorted((ROOT / "schema").glob("[0-9]*.schema.json"))]
    return [(kind, _object_schema(*SCHEMA_OBJECT[kind])) for kind in scope]


def test_no_schema_declares_a_computed_field() -> None:
    declared = [
        (view.view, label, name)
        for view in COMPUTED_VIEWS
        for label, schema in _scoped_schemas(view.scope)
        for name in set(_property_names(schema)) & set(view.names)
    ]

    assert declared == []


def test_authored_fields_with_computed_looking_names_are_not_rejected(spec: Path, graph: Graph) -> None:
    metric_id = _stored(spec, graph, "metric", "baseline")
    charter = load_doc(spec, "00_charter.json")
    charter["ambiguities"] = [{"id": "amb-metric-unit", "about": metric_id, "impact": "the target is unclear"}]
    write_json(spec, "00_charter.json", charter)

    assert _findings(spec) == []


def test_extension_artifact_stored_field_rejected(spec: Path) -> None:
    manifest = load_doc(spec, "13_extension_manifest.json")
    manifest["extensions"] = [{"extension_id": "ext-01-database", "title": "Database", "chain_stamp": "sha256:0"}]
    write_json(spec, "13_extension_manifest.json", manifest)

    (finding,) = _findings(spec)

    assert (finding.code, finding.node_id, finding.owner) == ("E768", "ext-01-database", "step:13")


def test_every_doc_computed_view_has_a_row_or_an_exemption_reason() -> None:
    rows = {view.view: view for view in COMPUTED_VIEWS}

    assert [doc for doc in DOC_COMPUTED_VIEWS if doc not in rows] == []
    assert [view.view for view in COMPUTED_VIEWS if bool(view.names) == bool(view.reason)] == []


def test_computed_fields_check_in_spec_check_reports_e768_with_owner_and_node_id(spec: Path, graph: Graph) -> None:
    node_id = _stored(spec, graph, "task", "invariant_refs")
    accept_links(spec)

    _errors, context = run_spec_check_json(str(ROOT), str(spec))

    findings = context["checks"]["computed-fields"]["findings"]
    assert [(f["code"], f["node_id"], f["owner"]) for f in findings] == [("E768", node_id, "step:14")]
