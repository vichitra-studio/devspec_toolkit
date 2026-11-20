"""The stage model: required stage of a node, binding stage, retired bindings."""
from __future__ import annotations

import json
from typing import Any

import pytest

from specdev_tools.graph.model import Graph
from specdev_tools.proof.proof import CLOSE_IGNORED_STAGES
from specdev_tools.graph.stages import (
    STAGES,
    UnknownStageForEnvironment,
    binding_required_stage,
    bindings_of,
    is_retired_binding,
    is_retired_verifier,
    required_stage,
    retired_binding_ids,
    stage_at_least,
    stage_rank,
)

from ._synth import ROOT, docs_graph


def _envs(**scopes: str) -> dict[str, Any]:
    names = {"dev": "in", "ci": "in", "staging": "in", "prod": "in", **scopes}
    return {"environments": {name: {"scope": scope} for name, scope in names.items()}}


def _record(record_id: str, verifies: list[str], stage: str | None = None) -> tuple[str, dict[str, Any]]:
    item: dict[str, Any] = {"verification_id": record_id, "verifies": verifies, "commands": ["t"], "output_guard": "ok"}
    if stage is not None:
        item["stage"] = stage
    return f"extras/verification/{record_id}.json", {"records": [item]}


def _graph(*, environments: dict[str, Any] | None = None, records: list[tuple[str, dict[str, Any]]] = (),
           jobs: list[dict[str, Any]] = ()) -> Graph:
    docs: dict[str, Any] = {
        "02a_delivery_baseline.json": environments or _envs(),
        "04_fr_list.json": {"functional_requirements": [{
            "fr_id": "fr-a", "statement": "A",
            "acceptance_criteria": [{"criterion_id": "ac-a-1", "text": "one"}]}]},
        "05_interface_contracts.json": {"apis": [{"api_id": "api-a", "name": "A", "errors": [{"error_id": "err-a"}]}]},
        "07_nfrs.json": {"nfrs": [{"nfr_id": "nfr-prod", "stage": "prod"}, {"nfr_id": "nfr-ci", "stage": "ci"}]},
        "08_fixtures.json": {"fixtures": [
            {"fixture_id": "fix-a", "verifies": ["ac-a-1", "api-a"]},
            {"fixture_id": "fix-mixed", "verifies": ["api-a", "nfr-prod"]},
            {"fixture_id": "fix-removal", "removes": ["api-a"]},
        ]},
        "10_governance.json": {"rules": [{"rule_id": "rule-a", "text": "R"}]},
        "12_ci_gates.json": {"jobs": list(jobs)},
    }
    docs.update(dict(records))
    return docs_graph(docs)


def _job(job_id: str, *realises: str) -> dict[str, Any]:
    return {"job_id": job_id, "name": job_id, "realises": list(realises)}


def _node(graph: Graph, node_id: str):
    node = graph.by_id[node_id]
    return node


def test_stage_names_are_the_schema_enum_in_order() -> None:
    schema = json.loads((ROOT / "schema" / "core" / "collections.schema.json").read_text(encoding="utf-8"))
    enum = schema["$defs"]["stageName"]["enum"]
    assert list(STAGES) == enum
    assert [stage_rank(s) for s in STAGES] == [0, 1, 2, 3]


def test_nfr_prod_needs_prod() -> None:
    graph = _graph()
    assert required_stage(_node(graph, "nfr-prod"), graph) == "prod"
    assert required_stage(_node(graph, "nfr-ci"), graph) == "ci"
    assert required_stage(_node(graph, "ac-a-1"), graph) == "dev"
    assert required_stage(_node(graph, "api-a"), graph) == "dev"
    assert required_stage(_node(graph, "err-a"), graph) == "dev"


def test_mixed_api_dev_and_nfr_prod_targets_give_prod() -> None:
    graph = _graph()
    assert binding_required_stage(["api-a", "nfr-prod"], graph) == "prod"
    assert binding_required_stage(["api-a", "ac-a-1"], graph) == "dev"


def test_scope_out_staging_retires_staging_bindings() -> None:
    graph = _graph(environments=_envs(staging="out"),
                   records=[_record("ver-s", ["fix-a"], "staging"), _record("ver-d", ["fix-a"], "dev")])
    assert is_retired_binding(_node(graph, "ver-s"), graph)
    assert not is_retired_binding(_node(graph, "ver-d"), graph)
    live = _graph(records=[_record("ver-s", ["fix-a"], "staging")])  # staging still in scope
    assert not is_retired_binding(_node(live, "ver-s"), live)


def test_verifier_with_all_bindings_retired_is_out_of_play() -> None:
    graph = _graph(environments=_envs(staging="out"), records=[_record("ver-s", ["fix-a"], "staging")])
    fixture = _node(graph, "fix-a")
    assert is_retired_verifier(fixture, graph)
    assert retired_binding_ids(fixture, graph) == {"ver-s"}
    assert not is_retired_verifier(_node(graph, "fix-mixed"), graph)  # no bindings at all: not retired


def test_verifier_with_one_live_binding_is_not_retired() -> None:
    graph = _graph(environments=_envs(staging="out"),
                   records=[_record("ver-s", ["fix-a"], "staging"), _record("ver-d", ["fix-a"])])
    fixture = _node(graph, "fix-a")
    assert sorted(b.id for b in bindings_of(fixture, graph)) == ["ver-d", "ver-s"]
    assert not is_retired_verifier(fixture, graph)
    assert retired_binding_ids(fixture, graph) == set()


def test_job_stage_is_the_stage_of_the_realised_environment() -> None:
    graph = _graph(jobs=[_job("job-ci", "ci"), _job("job-prod", "prod", "gate-x")])
    assert required_stage(_node(graph, "job-ci"), graph) == "ci"
    assert required_stage(_node(graph, "job-prod"), graph) == "prod"
    assert required_stage(_node(graph, "prod"), graph) == "prod"
    # a rule enforced by a job takes the job's stage
    assert required_stage(_node(graph, "rule-a"), graph, via_job=_node(graph, "job-prod")) == "prod"
    assert binding_required_stage(["rule-a"], graph, via_job=_node(graph, "job-ci")) == "ci"


def test_command_rule_binding_is_ci() -> None:
    graph = _graph()
    assert required_stage(_node(graph, "rule-a"), graph) == "ci"
    assert binding_required_stage(["rule-a"], graph) == "ci"


def test_removal_fixture_is_dev() -> None:
    graph = _graph()
    assert required_stage(_node(graph, "fix-removal"), graph) == "dev"


def test_empty_proves_is_dev() -> None:
    assert binding_required_stage([], _graph()) == "dev"
    assert binding_required_stage(["no-such-node"], _graph()) == "dev"


def test_non_canonical_environment_key_is_e334() -> None:
    graph = _graph(environments=_envs(qa="in"), jobs=[_job("job-qa", "qa")])
    with pytest.raises(UnknownStageForEnvironment) as caught:
        required_stage(_node(graph, "qa"), graph)
    assert caught.value.environment == "qa"
    with pytest.raises(UnknownStageForEnvironment):
        required_stage(_node(graph, "job-qa"), graph)


def test_stage_at_least_reads_the_order_of_the_stages() -> None:
    assert [stage_at_least(stage, "ci") for stage in STAGES] == [False, True, True, True]
    with pytest.raises(ValueError):
        stage_at_least("qa", "dev")


def test_the_stages_the_close_gate_ignores_are_those_above_ci() -> None:
    assert CLOSE_IGNORED_STAGES == tuple(stage for stage in STAGES if stage_rank(stage) > stage_rank("ci"))
