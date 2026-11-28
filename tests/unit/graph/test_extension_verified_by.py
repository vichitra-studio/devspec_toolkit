"""An extension obligation names what proves it with ``verified_by`` (DEVSPEC-245, piece B, decision 1): the graph side.

Coverage (E745): a verifier covers an obligation that lists it in its own ``verified_by``.  A fixture or a job that only
an extension node names counts as used (E742).  The link of a live extension node resolves and is lock-tracked like any
link; an extension node is never history, whatever milestone closes.  The proof side is ``tests/unit/proof``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import apply_delta
from specdev_tools.context.milestone_state import _chain
from specdev_tools.graph.gitview import read_seed_texts
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.trace.lockfile import Lock
from specdev_tools.trace.suspects import check_lock, missing_entry_errors
from specdev_tools.validation.graph_checks.built import BuiltState, compute_built
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.refinement import check_refinement, covers
from specdev_tools.validation.graph_checks.removal_rules import check_removal_rules
from specdev_tools.validation.graph_checks.verifiers import check_verifier_rules

from ..trace._lock_support import ROOT, lock_for
from ._extension import (
    CRITERION, DATA_PLACE, DATASTORE, ENTRY, FIXTURE, PARKED_TABLE, ROADMAP, SCHEMA_PLACE, STEP_13, TABLE, criterion, edit, extension_host, graph_of,
    spec_of, table, table_fields,
)

VERIFIED_BY = "verified_by"
OTHER_FIXTURE = "fix-password-reset-expired-token"
JOB = "job-contract-tests"
INVARIANT = "inv-reset-token-single-use"
PLAIN_CRITERION = "tc-confirm-reused-token"
"""A criterion of the worked example that refines a toolkit obligation (the invariant) and lists ``FIXTURE``."""
NEW_FIXTURE = "fix-reset-token-table"
MILESTONE_DONE = ROOT / "tests" / "fixtures" / "graph_checks" / "deltas"
OLD_ADVICE = "add a verifier that does"
"""The end of every E745 before this piece: right for an obligation a fixture or a job can verify."""


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return extension_host(tmp_path / "host")


def _context(host: Path) -> GraphCheckContext:
    return GraphCheckContext.from_graph(graph_of(host), None, spec_root=str(spec_of(host)))


def _e745(host: Path) -> dict[tuple[str | None, str | None], str]:
    """``{(criterion, target): message}`` of the E745 findings of *host*; every one is owned by step 14."""
    found = check_refinement(_context(host), "merge")
    assert {error.code for error in found} <= {"E745"} and {error.owner for error in found} <= {"step:14"}
    return {(error.node_id, error.target): error.message for error in found}


def _verify_table_by(host: Path, *verifiers: str, node_id: str = TABLE) -> None:
    edit(host, DATA_PLACE, lambda document: table(document, node_id).update(verified_by=list(verifiers)))


def _verify_criterion_by(host: Path, *verifiers: str, node_id: str = CRITERION) -> None:
    edit(host, ROADMAP, lambda roadmap: criterion(roadmap, node_id).update(verified_by=list(verifiers)))


def _accept(host: Path, kinds: list[str]) -> None:
    """Let ``verified_by`` of the kind ``table`` accept *kinds* (an edit of the host's own schema)."""
    edit(host, SCHEMA_PLACE, lambda schema: table_fields(schema)[VERIFIED_BY]["x-link"].update(kinds=kinds))


# --- coverage (E745) ----------------------------------------------------------------------------------------------------


def test_a_verifier_the_obligation_lists_in_its_own_verified_by_covers_it(host: Path) -> None:
    graph = graph_of(host)
    assert [link.target for link in graph.by_id[TABLE].links if link.field == VERIFIED_BY] == [FIXTURE]
    assert [link.target for link in graph.by_id[CRITERION].links if link.field == VERIFIED_BY] == [FIXTURE]
    assert FIXTURE not in [link.source for link in graph.incoming[TABLE]]  # the fixture does not, and cannot, name the table
    context = _context(host)
    assert covers(context, graph.by_id[FIXTURE], graph.by_id[TABLE]) is True
    assert covers(context, graph.by_id[OTHER_FIXTURE], graph.by_id[TABLE]) is False
    assert [key for key in _e745(host) if key[0] == CRITERION] == []


def test_a_verifier_the_obligation_does_not_list_does_not_cover_it(host: Path) -> None:
    _verify_criterion_by(host, OTHER_FIXTURE)
    found = _e745(host)
    assert [key for key in found if key[0] == CRITERION] == [(CRITERION, f"refines->{TABLE}")]


def test_one_listed_verifier_among_those_of_the_criterion_is_enough(host: Path) -> None:
    _verify_criterion_by(host, OTHER_FIXTURE, FIXTURE)
    assert [key for key in _e745(host) if key[0] == CRITERION] == []
    _verify_table_by(host, OTHER_FIXTURE, FIXTURE)
    _verify_criterion_by(host, FIXTURE)
    assert [key for key in _e745(host) if key[0] == CRITERION] == []


def test_the_list_of_another_obligation_does_not_count(host: Path) -> None:
    _verify_table_by(host, OTHER_FIXTURE, node_id=PARKED_TABLE)
    _verify_criterion_by(host, OTHER_FIXTURE)
    assert (CRITERION, f"refines->{TABLE}") in _e745(host)


def test_the_rule_is_the_same_for_a_job(host: Path) -> None:
    """No test of a kind name: whatever verifier the obligation lists covers it."""
    _verify_table_by(host, JOB)
    _verify_criterion_by(host, JOB)
    assert graph_of(host).by_id[JOB].kind == "job" and resolve_graph(graph_of(host)) == []
    assert [key for key in _e745(host) if key[0] == CRITERION] == []
    _verify_criterion_by(host, FIXTURE)
    assert (CRITERION, f"refines->{TABLE}") in _e745(host)


def test_a_toolkit_obligation_is_covered_as_before(tmp_path: Path, host: Path) -> None:
    """The worked example's own criterion and its invariant: covered by the fixture that ``verifies`` it, in both hosts, and E745 with its old words when it does not."""
    plain = extension_host(tmp_path / "plain", declared=False, refined=False)
    for path in (spec_of(plain) / "extensions").iterdir():
        path.unlink()
    for folder in (plain, host):
        assert [key for key in _e745(folder) if key[0] == PLAIN_CRITERION] == []
        _verify_criterion_by(folder, OTHER_FIXTURE, node_id=PLAIN_CRITERION)
    key = (PLAIN_CRITERION, f"refines->{INVARIANT}")
    assert _e745(host)[key] == _e745(plain)[key]
    assert _e745(plain)[key].endswith(f"; {OLD_ADVICE}") and VERIFIED_BY not in _e745(plain)[key].split(";")[-1]


# --- the advice of E745 for an extension obligation ---------------------------------------------------------------------


def _advice(message: str) -> str:
    """What the finding tells the author to do: the text after its last ``;``."""
    return message.rsplit(";", 1)[1]


def test_the_advice_for_an_obligation_with_another_verifier_names_its_verified_by(host: Path) -> None:
    _verify_criterion_by(host, OTHER_FIXTURE)
    message = _e745(host)[(CRITERION, f"refines->{TABLE}")]
    assert message.startswith(f"task criterion {CRITERION} refines {TABLE} but none of its verifiers ({OTHER_FIXTURE}) ")
    advice = _advice(message)
    assert OLD_ADVICE not in message
    assert f"{VERIFIED_BY} of {TABLE}" in advice and FIXTURE in advice  # where the proof is named, and what is named there now
    assert "that verifies it" not in advice


def test_the_advice_for_an_obligation_that_lists_no_verifier_names_its_verified_by(host: Path) -> None:
    edit(host, DATA_PLACE, lambda document: table(document).pop(VERIFIED_BY))
    message = _e745(host)[(CRITERION, f"refines->{TABLE}")]
    advice = _advice(message)
    assert OLD_ADVICE not in message and f"{VERIFIED_BY} of {TABLE}" in advice
    edit(host, DATA_PLACE, lambda document: table(document).update(verified_by=[]))  # an empty list is no verifier either
    assert _advice(_e745(host)[(CRITERION, f"refines->{TABLE}")]) == advice


def test_the_advice_for_a_kind_that_declares_no_verified_by_names_the_schema_of_the_extension(host: Path) -> None:
    edit(host, SCHEMA_PLACE, lambda schema: table_fields(schema).pop(VERIFIED_BY))
    edit(host, DATA_PLACE, lambda document: table(document).pop(VERIFIED_BY))
    assert VERIFIED_BY not in [link.field for link in graph_of(host).decls["table"].links]
    message = _e745(host)[(CRITERION, f"refines->{TABLE}")]
    advice = _advice(message)
    assert OLD_ADVICE not in message and "that verifies it" not in advice
    assert VERIFIED_BY in advice and "schema" in advice and "table" in advice


# --- a verifier that only an extension node names is used (E742) --------------------------------------------------------


def _unused(host: Path) -> list[str | None]:
    return [error.node_id for error in check_verifier_rules(_context(host), "merge") if error.code == "E742"]


def _add_fixture(host: Path) -> None:
    fixture = {"fixture_id": NEW_FIXTURE, "mode": "contract", "description": "The table refuses a second redemption.", "verifies": [INVARIANT]}
    edit(host, "08_fixtures.json", lambda document: document["fixtures"].append(fixture))


def test_a_fixture_that_only_an_extension_node_names_is_used(host: Path) -> None:
    before = _unused(host)
    assert NEW_FIXTURE not in before
    _add_fixture(host)
    assert _unused(host) == [*before, NEW_FIXTURE]  # nothing lists it yet
    _verify_table_by(host, FIXTURE, NEW_FIXTURE)
    assert [link.source for link in graph_of(host).incoming[NEW_FIXTURE]] == [TABLE]
    assert _unused(host) == before


def test_a_fixture_that_only_a_parked_extension_node_names_is_not_used(host: Path) -> None:
    _add_fixture(host)
    _verify_table_by(host, NEW_FIXTURE, node_id=PARKED_TABLE)
    graph = graph_of(host)
    assert (graph.by_id[PARKED_TABLE].scope, [link.source for link in graph.incoming[NEW_FIXTURE]]) == ("later", [PARKED_TABLE])
    assert NEW_FIXTURE in _unused(host)


# --- the link of a live extension node resolves like any link -----------------------------------------------------------


def _resolved(host: Path, *, closed: bool = False) -> list[tuple[str, str | None, str | None, str | None]]:
    graph = graph_of(host)
    errors = resolve_graph(graph, historical=historical_node_ids(graph)) if closed else resolve_graph(graph)
    return [(error.code, error.node_id, error.owner, error.target) for error in errors]


def test_verified_by_to_no_node_is_e700(host: Path) -> None:
    _verify_table_by(host, FIXTURE, "fix-never-written")
    assert _resolved(host) == [("E700", TABLE, STEP_13, f"{VERIFIED_BY}->fix-never-written")]


@pytest.mark.parametrize("target", [INVARIANT, "rule-contract-tests-on-every-pr", DATASTORE, TABLE, "ac-password-reset-3"])
def test_verified_by_to_a_kind_the_field_does_not_accept_is_e701(host: Path, target: str) -> None:
    _verify_table_by(host, FIXTURE, target)
    assert _resolved(host) == [("E701", TABLE, STEP_13, f"{VERIFIED_BY}->{target}")]


def test_verified_by_to_a_later_step_is_e702(host: Path) -> None:
    _accept(host, ["fixture", "job", "task-criterion"])
    _verify_table_by(host, FIXTURE, "tc-confirm-expired-token")
    graph = graph_of(host)
    errors = resolve_graph(graph)
    assert [(error.code, error.node_id, error.owner, error.target) for error in errors] == [("E702", TABLE, STEP_13, f"{VERIFIED_BY}->tc-confirm-expired-token")]
    assert "later step" in errors[0].message


def test_verified_by_of_both_verifier_kinds_resolves(host: Path) -> None:
    _verify_table_by(host, FIXTURE, JOB)
    assert _resolved(host) == []


# --- and is lock-tracked ------------------------------------------------------------------------------------------------


def _lock_findings(host: Path, lock: Lock, holder: str = TABLE) -> list[tuple[str, str | None, str | None]]:
    graph = graph_of(host)
    found = [*missing_entry_errors(graph, lock), *check_lock(graph, lock, read_seed_texts(graph, str(host)))]
    return [(error.code, error.node_id, error.target) for error in found if error.node_id == holder and (error.target or "").startswith(VERIFIED_BY)]


def test_verified_by_is_unaccepted_until_attested_and_suspect_after_an_edit_of_the_fixture(host: Path) -> None:
    assert _lock_findings(host, Lock(())) == [("E761", TABLE, f"{VERIFIED_BY}->{FIXTURE}")]
    accepted = lock_for(graph_of(host), host)
    assert _lock_findings(host, accepted) == []

    def reword(document: dict[str, Any]) -> None:
        fixture = next(found for found in document["fixtures"] if found["fixture_id"] == FIXTURE)
        fixture["expected"] = {**fixture["expected"], "status": 409}

    edit(host, "08_fixtures.json", reword)
    assert _lock_findings(host, accepted) == [("E763", TABLE, f"{VERIFIED_BY}->{FIXTURE}")]
    assert _lock_findings(host, accepted, CRITERION) == [("E763", CRITERION, f"{VERIFIED_BY}->{FIXTURE}")]  # the criterion's own link too
    assert _lock_findings(host, lock_for(graph_of(host), host)) == []


# --- an extension node is never history ---------------------------------------------------------------------------------


def _close_the_milestone(host: Path) -> None:
    apply_delta(host, "milestone_done", folder=MILESTONE_DONE)


def test_an_extension_node_is_not_history_when_the_milestone_of_the_criterion_that_refines_it_closes(host: Path) -> None:
    assert historical_node_ids(graph_of(host)) == set()
    _close_the_milestone(host)
    historical = historical_node_ids(graph_of(host))
    assert {CRITERION, PLAIN_CRITERION, "ms-account-recovery", "task-implement-password-reset-confirm"} <= historical
    assert not {TABLE, PARKED_TABLE, DATASTORE, ENTRY} & historical
    assert [node_id for node_id in historical if graph_of(host).by_id[node_id].step == "13"] == []


def test_the_verified_by_of_an_extension_node_stays_live_after_the_close_and_that_of_the_closed_criterion_is_frozen(host: Path) -> None:
    _verify_table_by(host, FIXTURE, "fix-never-written")
    _verify_criterion_by(host, FIXTURE, "fix-never-written")
    open_findings = _resolved(host, closed=True)
    assert open_findings == [("E700", TABLE, STEP_13, f"{VERIFIED_BY}->fix-never-written"), ("E700", CRITERION, "step:14", f"{VERIFIED_BY}->fix-never-written")]
    _close_the_milestone(host)
    closed = _resolved(host, closed=True)
    assert ("E700", TABLE, STEP_13, f"{VERIFIED_BY}->fix-never-written") in closed  # the extension node is live: its link is still refused
    assert [found for found in closed if found[0] == "E700" and found[1] == CRITERION] == []  # the closed criterion's link is history, as before


# --- the chain of a plan item reaches what the obligation names ---------------------------------------------------------


def test_the_chain_through_a_criterion_reaches_the_extension_obligation_and_its_verifiers(host: Path) -> None:
    _verify_table_by(host, FIXTURE, OTHER_FIXTURE)
    chain = _chain(graph_of(host), CRITERION)
    assert {CRITERION, TABLE, FIXTURE, OTHER_FIXTURE} <= chain
    assert DATASTORE not in chain and ENTRY not in chain  # part_of and justified_by are not chain verbs


# --- a removal fixture is covered by a criterion that removes, not by an obligation that names it -----------------------


def test_a_removal_fixture_that_a_table_names_still_needs_a_criterion_that_removes(host: Path) -> None:
    """E341 reads the task criteria: a table has no ``removes``, so naming the fixture in its ``verified_by`` covers no removal."""
    removed = "api-password-reset-confirm"

    def as_removal(document: dict[str, Any]) -> None:
        next(found for found in document["fixtures"] if found["fixture_id"] == FIXTURE)["removes"] = [removed]

    def uncovered() -> list[tuple[str, str | None]]:
        found = check_removal_rules(_context(host), "merge")  # E342 too: the id the fixture removes is a node of the example, which is not the subject here
        return [(error.code, error.node_id) for error in found if error.node_id == FIXTURE and error.code == "E341"]

    assert uncovered() == []
    edit(host, "08_fixtures.json", as_removal)
    assert uncovered() == [("E341", FIXTURE)]  # the table and the criterion both list it; neither removes
    _verify_criterion_by(host, OTHER_FIXTURE)
    assert uncovered() == [("E341", FIXTURE)]  # now the table alone lists it: still no criterion removes


# --- built: a closed criterion that refines the table at its current content --------------------------------------------


def _built(folder: Path, node_id: str = TABLE) -> BuiltState:
    graph = graph_of(folder)
    context = GraphCheckContext.from_graph(graph, lock_for(graph, folder), spec_root=str(spec_of(folder)), git_root=str(folder))
    return compute_built(context, node_id)[node_id].state


def test_the_table_is_built_only_when_a_closed_criterion_refines_it(tmp_path: Path, host: Path) -> None:
    assert _built(host) is BuiltState.NOT_BUILT  # refined, and the milestone is open
    _close_the_milestone(host)
    assert _built(host) is BuiltState.BUILT
    unrefined = extension_host(tmp_path / "unrefined", refined=False)
    _close_the_milestone(unrefined)
    assert _built(unrefined) is BuiltState.NOT_BUILT  # the milestone is closed and no criterion refines the table
    assert _built(unrefined, INVARIANT) is BuiltState.BUILT and _built(host, INVARIANT) is BuiltState.BUILT  # the example's own obligation, either way


def test_the_table_is_not_built_once_it_changed_after_the_refinement_was_accepted(host: Path) -> None:
    _close_the_milestone(host)
    graph = graph_of(host)
    accepted = lock_for(graph, host)
    edit(host, DATA_PLACE, lambda document: table(document)["columns"].append({"name": "requested_at", "type": "timestamptz"}))
    changed = graph_of(host)
    context = GraphCheckContext.from_graph(changed, accepted, spec_root=str(spec_of(host)), git_root=str(host))
    assert compute_built(context, TABLE)[TABLE].state is BuiltState.NOT_BUILT
    assert compute_built(context, INVARIANT)[INVARIANT].state is BuiltState.BUILT


def test_a_parked_table_and_a_datastore_take_no_part_in_built(host: Path) -> None:
    _close_the_milestone(host)
    assert _built(host, PARKED_TABLE) is BuiltState.IGNORED  # scope later: out of play
    assert _built(host, DATASTORE) is BuiltState.IGNORED  # a context node is no obligation
    assert _built(host, ENTRY) is BuiltState.IGNORED  # nor is the manifest entry (a plan node)

