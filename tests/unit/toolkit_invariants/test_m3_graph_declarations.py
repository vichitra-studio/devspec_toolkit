"""M3 graph declarations: every ``x-node`` / ``x-link`` the step 06-16 schemas carry.

The model is ``test_m2_graph_declarations.py`` for steps 00-05; the helpers and fixtures are imported from it.
Tests are parametrised over the M3 schema files that carry ``x-node`` today. A step item adds its schema to the
tables below (``_EXPECTED_KINDS``, ``_EXPECTED_LINK_KINDS``) and one ``test_step_NN_...`` test with its link
fields; the generic tests then cover it with no further edit.
"""
from __future__ import annotations

from typing import Any

import pytest

from specdev_tools.registry.annotations import LinkDecl, lint_annotations

from .test_m2_graph_declarations import (  # noqa: F401  (decls and reader are pytest fixtures)
    _EXCLUDED_FROM_CONTRACT,
    _GRAPH,
    _OBLIGATION_ROLES,
    _ROLE_TABLE,
    _SCHEMA_DIR,
    _is_step_schema,
    _item,
    _link_fields,
    _links,
    _node_arrays,
    _nodes,
    _props,
    _step_of,
    declared_link_kinds,
    decls,
    reader,
)

_M3_STEPS = frozenset({"06", "07", "08", "09", "10", "11", "12", "14", "15", "16"})

# Kind -> id field, by step (PD-1 of the M3 plan).
_EXPECTED_KINDS: dict[str, dict[str, str]] = {
    "06": {"invariant": "inv_id"},
    "07": {"nfr": "nfr_id"},
    "08": {"fixture": "fixture_id"},
    "09": {"design-milestone": "milestone_id"},
    "10": {"rule": "rule_id"},
    "11": {"threat": "threat_id", "edge-case": "id"},
    "12": {"job": "job_id"},
    "14": {"roadmap-milestone": "milestone_id", "task": "task_id", "task-criterion": "criterion_id"},
}

# The kinds a threat or an edge case may be ``mitigated_by``: every obligation kind except capability, and fixtures.
_MITIGATION_KINDS = ["api", "api-error", "constraint", "criterion", "environment", "fixture", "fr", "gate", "invariant", "nfr", "rule", "secret"]

# Link fields that count toward the built computation (link table of the M3 plan, section 3.2): ``realises`` on a job
# (step 12) and ``refines`` on a task criterion (step 14) join the first two.
_BUILT_LINK_FIELDS = frozenset({"derives_from", "mitigated_by", "realises", "refines"})

# A task's ``disposition`` is stored outside the hash (design L194), so it is not part of the node's contract.
_EXCLUDED_FROM_M3_CONTRACT = _EXCLUDED_FROM_CONTRACT | {"disposition"}

# Every obligation kind with ids: what a task criterion may refine.
_REFINABLE_KINDS = [
    "api", "api-error", "capability", "constraint", "criterion", "edge-case", "environment", "fr", "gate",
    "invariant", "nfr", "risk", "rule", "scope-item", "secret", "threat",
]

# Every ``x-link`` of the M3 schemas: (schema file, JSON pointer of the link field, sorted ``kinds`` or "*").
# Written out by hand on purpose: a change of one link's ``kinds`` list must be a deliberate change of this table.
_EXPECTED_LINK_KINDS: list[tuple[str, str, Any]] = [
    ("06_invariants.schema.json", "/allOf/1/properties/rules/items/properties/constrains", ["api", "component", "connection", "fr"]),
    ("06_invariants.schema.json", "/allOf/1/properties/rules/items/properties/assumes", ["assumption"]),
    ("06_invariants.schema.json", "/allOf/1/properties/rules/items/properties/replaces", "*"),
    ("07_nfrs.schema.json", "/allOf/1/properties/nfrs/items/properties/constrains", ["api", "component", "connection", "fr"]),
    ("07_nfrs.schema.json", "/allOf/1/properties/nfrs/items/properties/relies_on", ["third-party"]),
    ("07_nfrs.schema.json", "/allOf/1/properties/nfrs/items/properties/derives_from", ["metric"]),
    ("07_nfrs.schema.json", "/allOf/1/properties/nfrs/items/properties/assumes", ["assumption"]),
    ("07_nfrs.schema.json", "/allOf/1/properties/nfrs/items/properties/replaces", "*"),
    ("08_fixtures.schema.json", "/properties/fixtures/items/properties/verifies", ["api", "criterion", "invariant", "nfr"]),
    ("08_fixtures.schema.json", "/properties/fixtures/items/properties/removes", "*"),
    ("08_fixtures.schema.json", "/properties/fixtures/items/properties/replaces", "*"),
    ("09_impl_plan.schema.json", "/properties/milestones/items/properties/schedules", ["api", "component", "criterion", "environment", "fr", "invariant", "nfr", "risk"]),
    ("09_impl_plan.schema.json", "/properties/milestones/items/properties/replaces", "*"),
    ("10_governance.schema.json", "/allOf/1/properties/rules/items/properties/derives_from", ["constraint", "environment", "gate", "risk", "scope-item", "stakeholder"]),
    ("10_governance.schema.json", "/allOf/1/properties/rules/items/properties/assumes", ["assumption"]),
    ("10_governance.schema.json", "/allOf/1/properties/rules/items/properties/replaces", "*"),
    ("11_redteam.schema.json", "/allOf/1/properties/threats/items/properties/derives_from", ["risk"]),
    ("11_redteam.schema.json", "/allOf/1/properties/threats/items/properties/threatens", ["api", "component", "connection", "third-party"]),
    ("11_redteam.schema.json", "/allOf/1/properties/threats/items/properties/mitigated_by", _MITIGATION_KINDS),
    ("11_redteam.schema.json", "/allOf/1/properties/threats/items/properties/assumes", ["assumption"]),
    ("11_redteam.schema.json", "/allOf/1/properties/threats/items/properties/replaces", "*"),
    ("11_redteam.schema.json", "/allOf/1/properties/edge_cases/items/properties/threatens", ["api", "component", "fr"]),
    ("11_redteam.schema.json", "/allOf/1/properties/edge_cases/items/properties/mitigated_by", _MITIGATION_KINDS),
    ("11_redteam.schema.json", "/allOf/1/properties/edge_cases/items/properties/assumes", ["assumption"]),
    ("11_redteam.schema.json", "/allOf/1/properties/edge_cases/items/properties/replaces", "*"),
    ("12_ci_gates.schema.json", "/allOf/1/properties/jobs/items/properties/realises", ["environment", "gate", "rule", "secret"]),
    ("12_ci_gates.schema.json", "/allOf/1/properties/jobs/items/properties/verifies", ["nfr"]),
    ("12_ci_gates.schema.json", "/allOf/1/properties/jobs/items/properties/depends_on", ["job"]),
    ("12_ci_gates.schema.json", "/allOf/1/properties/jobs/items/properties/replaces", "*"),
    ("14_roadmap.schema.json", "/allOf/1/properties/milestones/items/properties/replaces", "*"),
    ("14_roadmap.schema.json", "/allOf/1/properties/milestones/items/properties/tasks/items/properties/depends_on", ["task"]),
    ("14_roadmap.schema.json", "/allOf/1/properties/milestones/items/properties/tasks/items/properties/replaces", "*"),
    ("14_roadmap.schema.json", "/allOf/1/properties/milestones/items/properties/tasks/items/properties/acceptance_criteria/items/properties/refines", _REFINABLE_KINDS),
    ("14_roadmap.schema.json", "/allOf/1/properties/milestones/items/properties/tasks/items/properties/acceptance_criteria/items/properties/removes", "*"),
    ("14_roadmap.schema.json", "/allOf/1/properties/milestones/items/properties/tasks/items/properties/acceptance_criteria/items/properties/verified_by", ["fixture", "job", "rule"]),
    ("14_roadmap.schema.json", "/allOf/1/properties/milestones/items/properties/tasks/items/properties/acceptance_criteria/items/properties/replaces", "*"),
]


def _m3_schema_files() -> list[str]:
    return sorted(
        p.name
        for p in _SCHEMA_DIR.glob("[0-9][0-9]*_*.schema.json")
        if _step_of(p.name) in _M3_STEPS and "x-node" in p.read_text()
    )


_FILES = _m3_schema_files()


def _link(decls_, fname: str, field: str) -> LinkDecl:
    """The one link declared under the field name *field* in schema *fname* (links named *field* in one node only)."""
    found = [lk for lk in _links(decls_, fname) if lk.field_name == field]
    assert len(found) == 1, (fname, field, found)
    return found[0]


def _assert_links(decls_, fname: str, expected: dict[str, tuple[Any, bool]]) -> None:
    """Assert the link fields of *fname* are exactly *expected*: ``{field: (kinds, required)}``."""
    actual = {lk.field_name: (lk.value["kinds"], lk.value["required"]) for lk in _links(decls_, fname)}
    normalised = {k: (v if v == "*" else sorted(v), r) for k, (v, r) in actual.items()}
    assert normalised == expected


def test_m3_schema_files_are_found() -> None:
    assert set(_FILES) == {
        "06_invariants.schema.json", "07_nfrs.schema.json", "08_fixtures.schema.json",
        "09_impl_plan.schema.json", "10_governance.schema.json", "11_redteam.schema.json",
        "12_ci_gates.schema.json", "14_roadmap.schema.json",
    }


@pytest.mark.parametrize("fname", _FILES)
def test_every_kind_declares_id_role_and_contract(decls, fname: str) -> None:
    declared = {n.kind: n.value for n in _nodes(decls, fname)}
    assert set(declared) == set(_EXPECTED_KINDS[_step_of(fname)])
    for kind, value in declared.items():
        assert value.get("id") == _EXPECTED_KINDS[_step_of(fname)][kind], kind
        assert value.get("role"), kind
        assert value.get("contract"), kind


@pytest.mark.parametrize("fname", _FILES)
def test_roles_match_kind_role_table(decls, fname: str) -> None:
    for node in _nodes(decls, fname):
        row = _ROLE_TABLE[node.kind]
        assert node.value["role"] == row["role"], node.kind
        assert node.value.get("coarse", False) == row.get("coarse", False), node.kind
        assert _step_of(fname) == row["step"], node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_obligation_kinds_carry_scope_with_default_and_reason_rule(decls, reader, fname: str) -> None:
    for node in _nodes(decls, fname):
        if node.value["role"] not in _OBLIGATION_ROLES:
            continue
        item, uri = _item(reader, node)
        props = reader.properties(item, uri)
        assert props["scope"][0]["$ref"] == f"{_GRAPH}#scope", node.kind
        assert props["scope"][0]["default"] == "in", node.kind
        assert "scope" not in (reader.get(item, uri, "required")[0] or []), node.kind
        assert props["scope_reason"][0]["$ref"] == f"{_GRAPH}#scopeReason", node.kind
        assert f"{_GRAPH}#scopeReasonRule" in reader.all_of_refs(item, uri), node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_verifier_kinds_carry_no_scope(decls, reader, fname: str) -> None:
    for node in _nodes(decls, fname):
        if node.value["role"] != "verifier":
            continue
        props = _props(reader, node)
        assert "scope" not in props and "scope_reason" not in props, node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_every_non_record_kind_carries_lifecycle_aliases_and_replaces(decls, reader, fname: str) -> None:
    for node in _nodes(decls, fname):
        item, uri = _item(reader, node)
        props = reader.properties(item, uri)
        required = reader.get(item, uri, "required")[0] or []
        assert props["lifecycle"][0]["$ref"] == f"{_GRAPH}#lifecycle", node.kind
        assert props["aliases"][0]["items"]["$ref"] == "vc:core:atoms#kebabId", node.kind
        assert "x-link" not in props["aliases"][0], node.kind
        assert props["replaces"][0]["items"]["$ref"] == f"{_GRAPH}#nodeId", node.kind
        assert not {"lifecycle", "aliases", "replaces"} & set(required), node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_every_link_kind_is_declared_or_seed(decls, fname: str) -> None:
    known = {n.kind for n in decls.nodes} | {"seed"}
    for link in _links(decls, fname):
        kinds = link.value["kinds"]
        if kinds != "*":
            assert set(kinds) <= known, (link.field_name, kinds)


@pytest.mark.parametrize("fname", _FILES)
def test_no_forward_links(decls, fname: str) -> None:
    kind_step = {n.kind: _step_of(n.schema_file) for n in decls.nodes if n.kind != "seed" and _is_step_schema(n.schema_file)}
    holder_step = _step_of(fname)
    for link in _links(decls, fname):
        kinds = link.value["kinds"]
        same_step = set(link.value.get("same_step_kinds", []))
        for kind in [] if kinds == "*" else kinds:
            if kind == "seed":
                continue
            assert kind_step[kind] <= holder_step, (link.field_name, kind)
            assert kind_step[kind] != holder_step or kind in same_step, (link.field_name, kind)


@pytest.mark.parametrize("fname", _FILES)
def test_contract_equals_computed_content_set(decls, reader, fname: str) -> None:
    for node in _nodes(decls, fname):
        props = _props(reader, node)
        contract = node.value["contract"]
        id_field = node.value["id"]
        links = _link_fields(reader, props)
        assert id_field not in contract and not set(contract) & links, node.kind
        computed = set(props) - {id_field} - links - _node_arrays(reader, props) - _EXCLUDED_FROM_M3_CONTRACT
        assert set(contract) == computed, node.kind
        assert len(contract) == len(set(contract)), node.kind


@pytest.mark.parametrize("fname", _FILES)
def test_built_true_only_on_the_built_link_fields(decls, fname: str) -> None:
    for link in _links(decls, fname):
        assert link.value.get("built", False) is (link.field_name in _BUILT_LINK_FIELDS), link.field_name


@pytest.mark.parametrize("fname", _FILES)
def test_required_links_have_min_items_one(decls, reader, fname: str) -> None:
    for link in _links(decls, fname):
        min_items, _ = reader.get(link.container, link.uri, "minItems")
        if link.value["required"]:
            assert min_items is not None and min_items >= 1, (link.field_name, link.path)


def test_every_x_link_declares_the_pinned_kinds() -> None:
    declared = declared_link_kinds(_FILES)
    expected = [row for row in _EXPECTED_LINK_KINDS if row[0] in _FILES]
    assert [d[:2] for d in declared if d[:2] not in [e[:2] for e in expected]] == [], "x-link declared but not in the table"
    assert [e[:2] for e in expected if e[:2] not in [d[:2] for d in declared]] == [], "x-link in the table but not declared"
    assert sorted(declared, key=repr) == sorted(expected, key=repr)


def test_annotation_lints_are_clean_on_m3_schemas(decls) -> None:
    assert lint_annotations(decls) == []


def test_step_06_invariant_declares_constrains_and_assumes_links(decls) -> None:
    fname = "06_invariants.schema.json"
    _assert_links(
        decls, fname,
        {
            "constrains": (["api", "component", "connection", "fr"], False),
            "assumes": (["assumption"], False),
            "replaces": ("*", False),
        },
    )


def test_step_07_nfr_declares_constrains_relies_on_and_derives_from(decls) -> None:
    fname = "07_nfrs.schema.json"
    _assert_links(
        decls, fname,
        {
            "constrains": (["api", "component", "connection", "fr"], False),
            "relies_on": (["third-party"], False),
            "derives_from": (["metric"], False),
            "assumes": (["assumption"], False),
            "replaces": ("*", False),
        },
    )
    assert _link(decls, fname, "derives_from").value["built"] is True


def test_step_08_fixture_declares_verifies_and_removes_links(decls) -> None:
    fname = "08_fixtures.schema.json"
    _assert_links(
        decls, fname,
        {
            "verifies": (["api", "criterion", "invariant", "nfr"], False),
            "removes": ("*", False),
            "replaces": ("*", False),
        },
    )


def test_step_09_x_links_are_schedules_and_assumes_only(decls) -> None:
    """The design milestone declares ``schedules`` (required) and the shared ``replaces``: no order link, no same-step kinds."""
    fname = "09_impl_plan.schema.json"
    _assert_links(
        decls, fname,
        {
            "schedules": (["api", "component", "criterion", "environment", "fr", "invariant", "nfr", "risk"], True),
            "replaces": ("*", False),
        },
    )
    assert not [lk for lk in _links(decls, fname) if "same_step_kinds" in lk.value]


def test_step_10_rule_declares_derives_from_assumes_and_replaces_links(decls) -> None:
    fname = "10_governance.schema.json"
    _assert_links(
        decls, fname,
        {
            "derives_from": (["constraint", "environment", "gate", "risk", "scope-item", "stakeholder"], True),
            "assumes": (["assumption"], False),
            "replaces": ("*", False),
        },
    )
    assert _link(decls, fname, "derives_from").value["built"] is True


def test_step_11_threat_and_edge_case_declare_threatens_and_mitigated_by(decls) -> None:
    by_holder: dict[str, dict[str, tuple[Any, bool]]] = {}
    for link in _links(decls, "11_redteam.schema.json"):
        kinds = link.value["kinds"]
        for holder in link.holders:
            by_holder.setdefault(holder, {})[link.field_name] = (kinds if kinds == "*" else sorted(kinds), link.value["required"])
    assert by_holder == {
        "threat": {
            "derives_from": (["risk"], False),
            "threatens": (["api", "component", "connection", "third-party"], True),
            "mitigated_by": (sorted(_MITIGATION_KINDS), False),
            "assumes": (["assumption"], False),
            "replaces": ("*", False),
        },
        "edge-case": {
            "threatens": (["api", "component", "fr"], True),
            "mitigated_by": (sorted(_MITIGATION_KINDS), True),
            "assumes": (["assumption"], False),
            "replaces": ("*", False),
        },
    }
    for link in _links(decls, "11_redteam.schema.json"):
        assert link.field_name != "mitigated_by" or link.value["built"] is True


def test_step_12_job_verifies_link_is_nfr_only_and_not_built(decls) -> None:
    fname = "12_ci_gates.schema.json"
    _assert_links(
        decls, fname,
        {
            "realises": (["environment", "gate", "rule", "secret"], False),
            "verifies": (["nfr"], False),
            "depends_on": (["job"], False),
            "replaces": ("*", False),
        },
    )
    assert _link(decls, fname, "verifies").value.get("built", False) is False
    assert _link(decls, fname, "realises").value["built"] is True
    assert _link(decls, fname, "depends_on").value["same_step_kinds"] == ["job"]


def test_step_14_milestone_stores_no_link_task_depends_on_and_criterion_refines(decls) -> None:
    fname = "14_roadmap.schema.json"
    by_holder: dict[str, dict[str, tuple[Any, bool]]] = {}
    for link in _links(decls, fname):
        kinds = link.value["kinds"]
        for holder in link.holders:
            by_holder.setdefault(holder, {})[link.field_name] = (kinds if kinds == "*" else sorted(kinds), link.value["required"])
    assert by_holder == {
        "roadmap-milestone": {"replaces": ("*", False)},
        "task": {"depends_on": (["task"], False), "replaces": ("*", False)},
        "task-criterion": {
            "refines": (_REFINABLE_KINDS, False),
            "removes": ("*", False),
            "verified_by": (["fixture", "job", "rule"], False),
            "replaces": ("*", False),
        },
    }
    assert _link(decls, fname, "refines").value["built"] is True
    assert _link(decls, fname, "depends_on").value["same_step_kinds"] == ["task"]


def test_step_14_task_criterion_requires_refines_or_removes_and_task_disposition_is_outside_the_contract(decls, reader) -> None:
    fname = "14_roadmap.schema.json"
    nodes = {n.kind: n for n in _nodes(decls, fname)}
    criterion_item, uri = _item(reader, nodes["task-criterion"])
    assert reader.get(criterion_item, uri, "anyOf")[0] == [{"required": ["refines"]}, {"required": ["removes"]}]
    assert "disposition" in _props(reader, nodes["task"])
    assert "disposition" not in nodes["task"].value["contract"]
