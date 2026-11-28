"""The proof of an extension obligation (DEVSPEC-245, piece B, decision 1): what its own ``verified_by`` names proves it.

The verifiers of an obligation include the targets of its own ``verified_by``.  A run of such a verifier is a run for the
obligation: the binding may name it, the evidence rests on it, and it goes stale when the obligation changes.  An
obligation that names no verifier is told where to name one.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import apply_delta
from specdev_tools.core.errors import FindingError
from specdev_tools.proof.proof import NO_VERIFIER, NOT_REQUIRED, PENDING_STAGE, PROVEN, UNBOUND, UNPROVEN, proof_errors
from specdev_tools.proof.validity import NO_EVIDENCE, STALE_HASH
from specdev_tools.verify.bind import BindRequest, plan_bind, proved_ids, targets_of
from specdev_tools.verify.run import milestone_binding_ids
from unit.graph._extension import (
    CRITERION, DATA_PLACE, DATASTORE, DECLARE, DELTAS, ENTRY, EXTENSION, FIXTURE, PARKED_TABLE, REFINE, ROADMAP, SCHEMA_PLACE, STEP_13, TABLE, criterion,
    table, table_fields,
)

from unit.lifecycle._milestone_support import cli_run

from ._support import (
    GUARD, INVARIANT, NFR, OTHER_FIXTURE, PASSING, add_fixture, binding, binding_item, commit_all, context, edit_doc, graph_of, host_with, prove, run,
)

assert FIXTURE == OTHER_FIXTURE  # the fixture the table names is the example's reused-token fixture, which verifies the invariant
EXPIRED_FIXTURE = "fix-password-reset-expired-token"
JOB = "job-contract-tests"
REUSED, EXPIRED = "ver-reused", "ver-expired"
OLD_ADVICE = "add a fixture or a job that verifies it"
"""The advice of E348 for a node nothing verifies: right for a node a fixture or a job can verify."""
VERIFIED_BY = "verified_by"


def _host(tmp_path: Path, *bindings: dict[str, Any], name: str = "host") -> Path:
    """The worked example as a git host with code, the extension, its entry, the criterion that refines its table, and *bindings*."""
    host = host_with(tmp_path, *bindings, name=name)
    shutil.copytree(EXTENSION / "spec" / "extensions", host / "spec" / "extensions")
    for delta in (DECLARE, REFINE):
        apply_delta(host, delta, folder=DELTAS)
    commit_all(host)
    return host


def _reused(**given: Any) -> dict[str, Any]:
    """A binding of the fixture the table names; it states no ``proves`` unless given."""
    return binding_item(REUSED, verifier=FIXTURE, **{"proves": (), **given})


def _table(host: Path, change: Any, node_id: str = TABLE) -> None:
    edit_doc(host, DATA_PLACE, lambda document: change(table(document, node_id)))


def _errors(host: Path, *scope: str, cap: str = "dev") -> list[tuple[str, str | None, str | None, str | None]]:
    return [(error.code, error.subcode, error.node_id, error.owner) for error in proof_errors(graph_of(host), context(host), list(scope), cap)]


def _status(host: Path, node_id: str, cap: str) -> str:
    """The status of the proof of *node_id*, or the code of the refusal (a stage that cannot be told)."""
    try:
        return prove(host, node_id, cap).status
    except FindingError as refused:
        return refused.error.code


def _message(host: Path, node_id: str, cap: str = "dev") -> str:
    [error] = proof_errors(graph_of(host), context(host), [node_id], cap)
    return error.message


# --- the verifiers of the obligation -------------------------------------------------------------------------------------


def test_the_verifier_the_table_names_is_asked_for_a_binding(tmp_path: Path) -> None:
    host = _host(tmp_path)
    result = prove(host, TABLE)
    assert (result.status, [(shortfall.verifier, shortfall.reason) for shortfall in result.shortfalls]) == (UNBOUND, [(FIXTURE, "UNBOUND")])
    assert _errors(host, TABLE) == [("E348", "UNBOUND", TABLE, STEP_13)]
    assert f"specdev verify bind {FIXTURE}" in _message(host, TABLE)


def test_a_passing_run_of_the_verifier_the_table_names_proves_the_table(tmp_path: Path) -> None:
    host = _host(tmp_path, _reused())
    result = prove(host, TABLE)
    assert (result.status, [(shortfall.binding, shortfall.reason) for shortfall in result.shortfalls]) == (UNPROVEN, [(REUSED, NO_EVIDENCE)])
    run(host, [REUSED])
    assert prove(host, TABLE).status == PROVEN
    assert prove(host, INVARIANT).status == PROVEN  # the same run proves what the fixture verifies
    assert _errors(host, TABLE, INVARIANT) == []


def test_the_criterion_that_refines_the_table_is_proven_by_the_same_run(tmp_path: Path) -> None:
    host = _host(tmp_path, _reused())
    assert prove(host, CRITERION).status == UNPROVEN
    run(host, [REUSED])
    assert prove(host, CRITERION).status == PROVEN
    assert milestone_binding_ids(graph_of(host), "ms-account-recovery").count(REUSED) == 1  # `verify run --milestone` takes it


def test_every_verifier_the_table_names_must_be_satisfied(tmp_path: Path) -> None:
    host = _host(tmp_path, _reused())
    run(host, [REUSED])
    assert prove(host, TABLE).status == PROVEN
    _table(host, lambda item: item.update(verified_by=[FIXTURE, EXPIRED_FIXTURE]))
    assert prove(host, TABLE).status != PROVEN
    run(host, [REUSED])  # the ids a node links to are part of its content (trace.hashing): the earlier run was of another table
    result = prove(host, TABLE)
    assert (result.status, [(shortfall.verifier, shortfall.reason) for shortfall in result.shortfalls]) == (UNBOUND, [(EXPIRED_FIXTURE, "UNBOUND")])


def test_a_verifier_that_another_table_names_is_not_a_verifier_of_this_one(tmp_path: Path) -> None:
    host = _host(tmp_path, _reused())
    run(host, [REUSED])
    _table(host, lambda item: item.pop(VERIFIED_BY))
    _table(host, lambda item: item.update(verified_by=[FIXTURE]), PARKED_TABLE)
    assert prove(host, TABLE).status == NO_VERIFIER


def test_a_job_the_table_names_is_a_verifier_of_the_table(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _table(host, lambda item: item.update(verified_by=[JOB]))
    assert targets_of(graph_of(host).by_id[JOB], graph_of(host))[-1] == TABLE
    result = prove(host, TABLE, "ci")
    assert (result.status, [(shortfall.verifier, shortfall.reason) for shortfall in result.shortfalls]) == (UNBOUND, [(JOB, "UNBOUND")])


def test_a_verifier_out_of_play_is_not_asked(tmp_path: Path) -> None:
    host = _host(tmp_path)
    edit_doc(host, "08_fixtures.json", lambda document: next(item for item in document["fixtures"] if item["fixture_id"] == FIXTURE).update(lifecycle="not_applicable"))
    assert prove(host, TABLE).status == NO_VERIFIER  # as for the invariant, whose only fixture it is
    assert prove(host, INVARIANT).status == NO_VERIFIER


def test_a_parked_table_is_proven_like_any_node_asked_about(tmp_path: Path) -> None:
    """``proof`` answers for the node it is asked about; the gates leave a parked node out of their scope."""
    host = _host(tmp_path)
    assert prove(host, PARKED_TABLE).status == NO_VERIFIER


# --- the binding names the table and the evidence rests on it ------------------------------------------------------------


def test_the_table_is_a_node_the_verifier_can_prove_and_a_binding_may_name_it(tmp_path: Path) -> None:
    host = _host(tmp_path)
    graph = graph_of(host)
    assert targets_of(graph.by_id[FIXTURE], graph) == (INVARIANT, TABLE)
    assert targets_of(graph.by_id[EXPIRED_FIXTURE], graph) == tuple(link.target for link in graph.by_id[EXPIRED_FIXTURE].links if link.field == "verifies")
    plan = plan_bind(graph, BindRequest(FIXTURE, (PASSING,), GUARD, proves=(TABLE,)))
    assert (plan.proves, plan.stage) == ((TABLE,), "dev")
    assert plan_bind(graph, BindRequest(FIXTURE, (PASSING,), GUARD)).proves == (INVARIANT, TABLE)


@pytest.mark.parametrize("stranger", [PARKED_TABLE, DATASTORE, ENTRY, CRITERION])
def test_a_binding_may_not_name_a_node_that_does_not_name_the_verifier(tmp_path: Path, stranger: str) -> None:
    """The parked table names no verifier; a datastore and the entry are no obligations; the criterion lists the fixture, but a criterion is proven through what it refines."""
    host = _host(tmp_path)
    with pytest.raises(FindingError) as refused:
        plan_bind(graph_of(host), BindRequest(FIXTURE, (PASSING,), GUARD, proves=(stranger,)))
    assert refused.value.error.code == "E331"


def test_a_binding_that_states_only_the_invariant_is_no_binding_for_the_table(tmp_path: Path) -> None:
    host = _host(tmp_path, _reused(proves=(INVARIANT,)))
    run(host, [REUSED])
    assert proved_ids(binding(host, REUSED), graph_of(host)) == (INVARIANT,)
    assert prove(host, INVARIANT).status == PROVEN
    assert prove(host, TABLE).status == UNBOUND


def test_a_binding_that_states_the_table_proves_the_table_and_not_the_invariant(tmp_path: Path) -> None:
    host = _host(tmp_path, _reused(proves=(TABLE,)))
    run(host, [REUSED])
    assert (prove(host, TABLE).status, prove(host, INVARIANT).status) == (PROVEN, UNBOUND)


def test_an_edit_of_the_table_makes_the_run_stale(tmp_path: Path) -> None:
    host = _host(tmp_path, _reused())
    run(host, [REUSED])
    assert prove(host, TABLE).status == PROVEN
    _table(host, lambda item: item["columns"].append({"name": "requested_at", "type": "timestamptz"}))
    result = prove(host, TABLE)
    assert (result.status, [(shortfall.binding, shortfall.reason) for shortfall in result.shortfalls]) == (UNPROVEN, [(REUSED, STALE_HASH)])
    assert _errors(host, TABLE) == [("E347", STALE_HASH, TABLE, STEP_13)]
    run(host, [REUSED])
    assert prove(host, TABLE).status == PROVEN


def test_an_edit_of_a_field_outside_the_contract_of_the_table_leaves_the_run_valid(tmp_path: Path) -> None:
    host = _host(tmp_path, _reused())
    run(host, [REUSED])
    _table(host, lambda item: item.pop("term_ref"))
    assert prove(host, TABLE).status == PROVEN


def test_a_run_made_before_the_table_named_the_fixture_is_not_a_run_for_the_table(tmp_path: Path) -> None:
    host = _host(tmp_path, _reused())
    _table(host, lambda item: item.pop(VERIFIED_BY))
    run(host, [REUSED])
    assert prove(host, INVARIANT).status == PROVEN
    _table(host, lambda item: item.update(verified_by=[FIXTURE]))
    result = prove(host, TABLE)
    assert (result.status, [(shortfall.binding, shortfall.reason) for shortfall in result.shortfalls]) == (UNPROVEN, [(REUSED, STALE_HASH)])


# --- the advice of the finding for an obligation with no verifier --------------------------------------------------------


def test_a_table_that_names_no_verifier_is_told_to_name_one_in_its_verified_by(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _table(host, lambda item: item.pop(VERIFIED_BY))
    assert prove(host, TABLE).status == NO_VERIFIER
    assert _errors(host, TABLE) == [("E348", "NO_VERIFIER", TABLE, STEP_13)]
    message = _message(host, TABLE)
    assert message.startswith(f"table {TABLE} has no verifier to prove it: ")
    advice = message.split(": ", 1)[1]
    assert OLD_ADVICE not in message and "that verifies it" not in advice
    assert f"{VERIFIED_BY} of {TABLE}" in advice
    _table(host, lambda item: item.update(verified_by=[]))  # an empty list names no verifier either
    assert _message(host, TABLE) == message


def test_a_table_of_a_kind_with_no_verified_by_is_told_to_declare_the_link_in_the_schema(tmp_path: Path) -> None:
    host = _host(tmp_path)
    edit_doc(host, SCHEMA_PLACE, lambda schema: table_fields(schema).pop(VERIFIED_BY))
    _table(host, lambda item: item.pop(VERIFIED_BY))
    message = _message(host, TABLE)
    advice = message.split(": ", 1)[1]
    assert OLD_ADVICE not in message and "that verifies it" not in advice
    assert VERIFIED_BY in advice and "schema" in advice and "table" in advice


def test_the_advice_for_a_toolkit_obligation_is_as_before(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plain = host_with(tmp_path, name="plain")
    assert prove(plain, NFR, "prod").status == NO_VERIFIER
    assert _message(host, NFR, "prod") == _message(plain, NFR, "prod")
    assert _message(plain, NFR, "prod").endswith(f": {OLD_ADVICE}")
    edit_doc(host, ROADMAP, lambda roadmap: criterion(roadmap).pop(VERIFIED_BY))  # a task criterion: its own advice, unchanged
    edit_doc(plain, ROADMAP, lambda roadmap: criterion(roadmap, "tc-confirm-reused-token").pop(VERIFIED_BY))
    assert _message(host, CRITERION).split(": ", 1)[1] == _message(plain, "tc-confirm-reused-token").split(": ", 1)[1] == OLD_ADVICE


# --- nothing else of the worked example moves ----------------------------------------------------------------------------


def test_the_proof_of_every_node_of_the_plain_example_is_the_same_with_the_extension(tmp_path: Path) -> None:
    host = _host(tmp_path, _reused(), binding_item(EXPIRED, verifier=EXPIRED_FIXTURE, proves=()))
    plain = host_with(tmp_path, _reused(), binding_item(EXPIRED, verifier=EXPIRED_FIXTURE, proves=()), name="plain")
    for folder in (host, plain):
        run(folder, [REUSED, EXPIRED])
    names = [node.id for node in graph_of(plain).nodes if node.role in ("obligation-system", "obligation-delivery", "verifier") or node.kind == "task-criterion"]
    assert {INVARIANT, NFR, FIXTURE, "tc-confirm-reused-token"} <= set(names) and TABLE not in names
    for cap in ("dev", "prod"):
        assert {name: _status(host, name, cap) for name in names} == {name: _status(plain, name, cap) for name in names}
    statuses = {_status(plain, name, "prod") for name in names}
    assert {PROVEN, NO_VERIFIER} <= statuses and statuses <= {PROVEN, NO_VERIFIER, UNBOUND, UNPROVEN, PENDING_STAGE, NOT_REQUIRED, "E334"}


# --- fix round 1, F10: the two advices are told apart, and each is carried out --------------------------------------------------


def test_the_two_advices_for_a_table_with_no_verifier_differ_and_each_way_out_works(tmp_path: Path) -> None:
    """One table names none although its kind has the link; the other is of a kind that has no such link: the first is told to name one, the second to declare the link first."""
    named = _host(tmp_path, _reused(), name="named")
    link = table_fields(json.loads((named / "spec" / SCHEMA_PLACE).read_text(encoding="utf-8")))[VERIFIED_BY]
    assert "x-link" in link
    _table(named, lambda item: item.pop(VERIFIED_BY))
    name_one = _message(named, TABLE).split(": ", 1)[1]

    undeclared = _host(tmp_path, _reused(), name="undeclared")
    edit_doc(undeclared, SCHEMA_PLACE, lambda schema: table_fields(schema).pop(VERIFIED_BY))
    _table(undeclared, lambda item: item.pop(VERIFIED_BY))
    declare_first = _message(undeclared, TABLE).split(": ", 1)[1]

    assert name_one != declare_first
    assert "schema" not in name_one and "declares no" not in name_one and f"in {VERIFIED_BY} of {TABLE}" in name_one
    assert "declares no" in declare_first and "schema" in declare_first and declare_first.index("declare") < declare_first.index(f"{VERIFIED_BY} of {TABLE}")

    _table(named, lambda item: item.update(verified_by=[FIXTURE]))  # the first advice, carried out
    assert prove(named, TABLE).status != NO_VERIFIER
    run(named, [REUSED])
    assert prove(named, TABLE).status == PROVEN

    edit_doc(undeclared, SCHEMA_PLACE, lambda schema: table_fields(schema).update({VERIFIED_BY: link}))  # the second: declare the link ...
    assert prove(undeclared, TABLE).status == NO_VERIFIER and _message(undeclared, TABLE).split(": ", 1)[1] == name_one  # ... and now it is the first case
    _table(undeclared, lambda item: item.update(verified_by=[FIXTURE]))  # ... then name the verifier
    run(undeclared, [REUSED])
    assert prove(undeclared, TABLE).status == PROVEN


TABLE_ONLY, TABLE_ONLY_BINDING = "fix-table-only", "ver-table-only"
MILESTONE = "ms-account-recovery"


def test_the_run_of_the_milestone_proves_its_criterion_and_release_prep_runs_the_verifier_only_the_table_names(tmp_path: Path) -> None:
    """A fixture no criterion names, in ``verified_by`` of the table: the close of the milestone does not wait for it; the release does, and ``release prep`` runs it."""
    host = _host(tmp_path, _reused(), binding_item(TABLE_ONLY_BINDING, verifier=TABLE_ONLY, proves=()))
    add_fixture(host, fixture_id=TABLE_ONLY)
    _table(host, lambda item: item[VERIFIED_BY].append(TABLE_ONLY))
    commit_all(host)
    named_by = sorted(node.id for node in graph_of(host).nodes if any(link.field == VERIFIED_BY and link.target == TABLE_ONLY for link in node.links))
    assert named_by == [TABLE]  # only the table names it
    result = prove(host, TABLE)
    assert (result.status, sorted((shortfall.binding, shortfall.reason) for shortfall in result.shortfalls)) == (UNPROVEN, sorted([(REUSED, NO_EVIDENCE), (TABLE_ONLY_BINDING, NO_EVIDENCE)]))

    code, out, err = cli_run(host, "verify", "run", "--milestone", MILESTONE)
    assert code == 0, out + err
    assert prove(host, CRITERION).status == PROVEN  # what the close of the milestone asks of the criterion that refines the table
    result = prove(host, TABLE)
    assert (result.status, [(shortfall.binding, shortfall.reason) for shortfall in result.shortfalls]) == (UNPROVEN, [(TABLE_ONLY_BINDING, NO_EVIDENCE)])

    code, out, err = cli_run(host, "release", "prep", "--json")
    document = json.loads(out)
    assert (document["run"], document["already_proven"], document["passed"], document["failed"]) == ([TABLE_ONLY_BINDING], [REUSED], [TABLE_ONLY_BINDING], []), out + err
    assert code == 0 and prove(host, TABLE).status == PROVEN
