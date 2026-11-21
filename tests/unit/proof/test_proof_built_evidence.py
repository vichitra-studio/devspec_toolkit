"""The evidence branches of "built" and the proof implementations of the context seams (WI-M7-08)."""
from __future__ import annotations

import shutil
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.graph.model import Node
from specdev_tools.proof import validity
from specdev_tools.proof.built_evidence import built_at_cap, built_state, pin_matches, record_users, relieved_nodes, retired_bindings
from specdev_tools.proof.proof import NO_VERIFIER, PENDING_STAGE, PROVEN, UNBOUND, UNPROVEN
from specdev_tools.trace.lockfile import read_lock
from specdev_tools.validation.graph_checks.built import BuiltResult, BuiltState, compute_built, register_built_provider
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.verify.records import records_folder, write_binding
from unit.graph._synth import ROOT
from unit.validation.graph_checks._built_support import built_context, node

from ._closed import add_milestone, closed_example, criterion
from ._support import (
    EXAMPLE_BINDING, FIXTURE, INVARIANT, NFR, PASSING, add_fixture, attest, binding_item, ci_host, commit_all, edit_code, edit_doc, graph_of, host_with, prove, run,
)
from unit.verify._support import write, write_json

BUILT, NOT_BUILT, PENDING, RELIEVED = BuiltState.BUILT, BuiltState.NOT_BUILT, BuiltState.PENDING_EVIDENCE, BuiltState.RELIEVED
JOB, ENVIRONMENT, GATE = "job-contract-tests", "ci", "contract-tests"
JOB_RULE, COMMAND_RULE, REVIEW_RULE = "rule-contract-tests-on-every-pr", "rule-spec-check-on-every-pr", "rule-security-review-of-token-handling"
THREAT, EDGE_CASE = "threat-reset-token-replay", "ec-token-at-expiry-second"
CI_BINDING, LATENCY_FIXTURE, LATENCY_BINDING = "ver-ci-job", "fix-latency", "ver-latency"
_ci_host = partial(ci_host, binding_id=CI_BINDING, verifier=JOB, proves=())
"""The example whose job ``job-contract-tests`` (it realises environment ci, the gate and a rule) has a ci binding, run once unless ``ran=False``."""
FAILING = "echo expected line; exit 3"
CONSTRAINT, TP, CLIENT = "con-pinned", "tp-mailrelay", "src/mail/client.ts"
CLIENT_TEXT = 'export const MAILRELAY_API_VERSION = "{}";\n'
DECLARATIONS = {"pin_sources": {TP: [{"type": "regex", "file": CLIENT, "pattern": 'MAILRELAY_API_VERSION = "(api-v[0-9]+)"'}]}}


def _ctx(host: Path) -> GraphCheckContext:
    spec = str(host / "spec")
    return GraphCheckContext.from_graph(graph_of(host), read_lock(spec), str(ROOT), git_root=str(host), spec_root=spec)


def _built(host: Path, cap: str = "ci") -> dict[str, BuiltResult]:
    return built_at_cap(_ctx(host), cap)


def _state(host: Path, node_id: str, cap: str = "ci") -> BuiltState:
    return _built(host, cap)[node_id].state


def _closed_host(tmp_path: Path, *bindings: dict[str, Any]) -> Path:
    """The example with its milestone closed, code, and *bindings* (the example's own record, which runs npx, is dropped)."""
    host = closed_example(tmp_path)
    (host / "spec" / "extras" / "verification" / f"{EXAMPLE_BINDING}.json").unlink()
    write(host / "src" / "hello.txt", "hello\n")
    for item in bindings:
        write_binding(records_folder(str(host / "spec")), str(ROOT), item)
    commit_all(host)
    return host


def _latency_host(tmp_path: Path, *, run_it: bool = False) -> Path:
    """A closed example in which a task criterion refines the NFR (staging) and a fixture verifies it with a staging binding."""
    host = _closed_host(tmp_path, binding_item(LATENCY_BINDING, verifier=LATENCY_FIXTURE, proves=(NFR,), stage="staging"))
    add_fixture(host, fixture_id=LATENCY_FIXTURE, verifies=[NFR])
    add_milestone(host, "ms-latency", [criterion("tc-latency-check", refines=[NFR])], done=True)
    commit_all(host)
    if run_it:
        run(host, [LATENCY_BINDING], stage="staging")
    return host


def _pinned_host(tmp_path: Path, *, version: str | None = "api-v3", declared: bool = True) -> Path:
    """A closed example with a constraint that only the third party ``tp-mailrelay`` derives from, relied on by the NFR (built through a closed criterion)."""
    host = closed_example(tmp_path)
    edit_doc(host, "00_charter.json", lambda doc: doc["constraints"].append({"constraint_id": CONSTRAINT, "scope": "in", "text": "The mail relay is used at its pinned version.", "derives_from": ["seed-accounts"]}))
    edit_doc(host, "02_system_sketch.json", lambda doc: doc["third_parties"][1]["derives_from"].append(CONSTRAINT))
    add_milestone(host, "ms-pin", [criterion("tc-pin-nfr", refines=[NFR])], done=True)
    if version is not None:
        write(host / CLIENT, CLIENT_TEXT.format(version))
    if declared:
        write_json(host / "spec" / "common" / "host_declarations.json", DECLARATIONS)
    commit_all(host)
    return host


# --- the seams ----------------------------------------------------------------------------------------------------------


def test_constraint_is_built_through_a_third_party_when_the_pin_matches(tmp_path: Path) -> None:
    host = _pinned_host(tmp_path)
    result = compute_built(_ctx(host))[CONSTRAINT]
    assert (result.state, result.via) == (BUILT, (TP,))
    assert pin_matches(_ctx(host), graph_of(host).by_id[TP]) == "OK"


def test_constraint_not_built_when_the_pin_differs(tmp_path: Path) -> None:
    host = _pinned_host(tmp_path, version="api-v9")
    result = compute_built(_ctx(host))[CONSTRAINT]
    assert (result.state, result.via) == (NOT_BUILT, (TP,))
    assert pin_matches(_ctx(host), graph_of(host).by_id[TP]) == "MISMATCH"


def test_constraint_pending_when_the_third_party_has_no_source(tmp_path: Path) -> None:
    host = _pinned_host(tmp_path, declared=False)
    assert pin_matches(_ctx(host), graph_of(host).by_id[TP]) == "UNKNOWN"
    assert compute_built(_ctx(host))[CONSTRAINT].state is PENDING


def test_a_source_that_cannot_be_read_is_a_mismatch_and_an_unreadable_declarations_file_is_unknown(tmp_path: Path) -> None:
    host = _pinned_host(tmp_path, version=None)
    assert pin_matches(_ctx(host), graph_of(host).by_id[TP]) == "MISMATCH"
    write(host / "spec" / "common" / "host_declarations.json", "{not json")
    assert pin_matches(_ctx(host), graph_of(host).by_id[TP]) == "UNKNOWN"


def test_pin_matches_is_read_once_per_context_and_is_unknown_for_a_node_that_is_not_a_third_party(tmp_path: Path) -> None:
    host = _pinned_host(tmp_path)
    ctx = _ctx(host)
    assert pin_matches(ctx, graph_of(host).by_id[TP]) == "OK"
    (host / CLIENT).write_text(CLIENT_TEXT.format("api-v9"), encoding="utf-8")
    assert pin_matches(ctx, graph_of(host).by_id[TP]) == "OK", "the sources are read once for a context"
    assert pin_matches(_ctx(host), graph_of(host).by_id[TP]) == "MISMATCH"
    assert pin_matches(ctx, graph_of(host).by_id[NFR]) == "UNKNOWN"


def test_record_users_returns_a_verifier_that_has_a_binding_and_empty_without(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item("ver-reused", verifier="fix-password-reset-reused-token", proves=(INVARIANT,)), keep_example_binding=True)
    ctx, graph = _ctx(host), graph_of(host)
    assert record_users(ctx, graph.by_id[FIXTURE]) == {EXAMPLE_BINDING}
    assert record_users(ctx, graph.by_id["fix-password-reset-reused-token"]) == {"ver-reused"}
    assert record_users(ctx, graph.by_id[JOB]) == set()
    attest(host, FIXTURE)
    after = _ctx(host)
    assert record_users(after, graph_of(host).by_id[FIXTURE]) == {EXAMPLE_BINDING, "evd-attest-one"}
    assert after.record_users(graph_of(host).by_id[FIXTURE]) == {EXAMPLE_BINDING, "evd-attest-one"}


def test_retired_bindings_names_the_bindings_of_a_verifier_whose_bindings_are_all_retired(tmp_path: Path) -> None:
    host = host_with(tmp_path, keep_example_binding=True)
    assert retired_bindings(_ctx(host), graph_of(host).by_id[FIXTURE]) == set()
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"]["dev"].update(scope="out", scope_reason="not shipped"))
    graph = graph_of(host)
    assert retired_bindings(_ctx(host), graph.by_id[FIXTURE]) == {EXAMPLE_BINDING}
    assert not _ctx(host).in_play(graph.by_id[FIXTURE])


def test_nfr_with_only_a_job_verifier_is_proven_at_its_stage_pending_stage_below_and_unbound_without_binding(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item("ver-job-latency", verifier="job-latency", proves=(NFR,), stage="staging"))
    edit_doc(host, "12_ci_gates.json", lambda doc: doc["jobs"].append({
        "job_id": "job-latency", "name": "Latency", "steps": [{"name": "Measure", "command": "echo measure"}], "realises": ["staging"], "verifies": [NFR],
    }))
    assert prove(host, NFR, "staging").status == UNPROVEN
    run(host, ["ver-job-latency"], stage="staging")
    assert prove(host, NFR, "staging").status == PROVEN
    assert prove(host, NFR, "ci").status == PENDING_STAGE
    bare = host_with(tmp_path, name="bare")
    edit_doc(bare, "12_ci_gates.json", lambda doc: doc["jobs"].append({
        "job_id": "job-latency", "name": "Latency", "steps": [{"name": "Measure", "command": "echo measure"}], "realises": ["staging"], "verifies": [NFR],
    }))
    assert prove(bare, NFR, "staging").status == UNBOUND


def test_extra_verifiers_is_empty_for_an_nfr(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    ctx, graph = _ctx(host), graph_of(host)
    assert ctx.extra_verifiers(graph.by_id[NFR]) == set() == ctx.extra_verifiers(graph.by_id[JOB])


def test_every_seam_receives_the_context_and_the_node(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    ctx, graph = _ctx(host), graph_of(host)
    asked: list[tuple[str, GraphCheckContext, Node]] = []
    seams = ctx.seams.__class__(
        retired_bindings=lambda given, found: asked.append(("retired", given, found)) or set(),
        record_users=lambda given, found: asked.append(("users", given, found)) or set(),
        extra_verifiers=lambda given, found: asked.append(("extra", given, found)) or set(),
        pin_matches=lambda given, found: asked.append(("pin", given, found)) or "UNKNOWN",
    )
    ctx.seams = seams
    fixture = graph.by_id[FIXTURE]
    ctx.retired_bindings(fixture), ctx.record_users(fixture), ctx.extra_verifiers(fixture), ctx.pin_matches(fixture)
    assert [(name, given is ctx, found) for name, given, found in asked] == [(name, True, fixture) for name in ("retired", "users", "extra", "pin")]


# --- environment, gate, secret, rule ------------------------------------------------------------------------------------


def test_environment_is_built_only_after_its_jobs_evidence_is_valid(tmp_path: Path) -> None:
    unrun = _ci_host(tmp_path, ran=False)
    assert (_state(unrun, ENVIRONMENT), _state(unrun, GATE)) == (NOT_BUILT, NOT_BUILT)
    assert "no valid evidence (NO_EVIDENCE)" in _built(unrun)[ENVIRONMENT].reason
    host = _ci_host(tmp_path / "ran")
    assert (_state(host, ENVIRONMENT), _state(host, GATE)) == (BUILT, BUILT)


def test_invalid_evidence_flips_the_environment_back(tmp_path: Path) -> None:
    host = _ci_host(tmp_path)
    assert _state(host, ENVIRONMENT) is BUILT
    edit_code(host)
    result = _built(host)[ENVIRONMENT]
    assert result.state is NOT_BUILT and "STALE_TREE" in result.reason
    run(host, [CI_BINDING], stage="ci")
    assert _state(host, ENVIRONMENT) is BUILT


def test_a_failing_run_leaves_the_environment_not_built(tmp_path: Path) -> None:
    host = _ci_host(tmp_path, commands=(FAILING,))
    assert "NONZERO_EXIT" in _built(host)[ENVIRONMENT].reason and _state(host, GATE) is NOT_BUILT


def test_an_environment_whose_job_binding_is_above_the_cap_is_relieved_and_waits_for_that_stage(tmp_path: Path) -> None:
    host = _ci_host(tmp_path)
    result = _built(host, "dev")[ENVIRONMENT]
    assert (result.state, result.waits_for) == (RELIEVED, "ci")


def test_rule_is_built_through_a_job_with_a_proven_binding(tmp_path: Path) -> None:
    unrun = _ci_host(tmp_path, ran=False)
    assert _state(unrun, JOB_RULE) is NOT_BUILT
    assert _state(_ci_host(tmp_path / "ran"), JOB_RULE) is BUILT


def test_rule_with_cli_command_in_the_list_is_built(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    assert (_state(host, COMMAND_RULE), prove(host, COMMAND_RULE).status) == (BUILT, PROVEN)


def test_rule_with_cli_command_absent_from_the_list_is_not_built(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    edit_doc(host, "10_governance.json", lambda doc: doc["rules"][1].update(cli_command="no-such-command"))
    assert (_state(host, COMMAND_RULE), prove(host, COMMAND_RULE).status) == (NOT_BUILT, NO_VERIFIER)


def test_review_enforced_rule_stays_pending_evidence(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    assert _state(host, REVIEW_RULE) is PENDING
    attest(host, REVIEW_RULE)
    assert _state(host, REVIEW_RULE) is PENDING, "an attestation is read at release by M8, not here"


def test_command_rule_without_a_binding_is_built_and_proven(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    result = built_state(_ctx(host), graph_of(host).by_id[COMMAND_RULE], "ci")
    assert result.state is BUILT and prove(host, COMMAND_RULE, "ci").status == PROVEN


def test_command_rule_with_a_failing_optional_binding_is_unproven(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item("ver-rule", verifier=COMMAND_RULE, proves=(), stage="ci", commands=(FAILING,)))
    run(host, ["ver-rule"], stage="ci")
    assert prove(host, COMMAND_RULE, "ci").status == UNPROVEN
    assert _state(host, COMMAND_RULE) is NOT_BUILT
    passing = host_with(tmp_path, binding_item("ver-rule", verifier=COMMAND_RULE, proves=(), stage="ci"), name="passing")
    run(passing, ["ver-rule"], stage="ci")
    assert (prove(passing, COMMAND_RULE, "ci").status, _state(passing, COMMAND_RULE)) == (PROVEN, BUILT)


# --- threats and edge cases ---------------------------------------------------------------------------------------------


def test_threat_with_a_fixture_mitigation_lacking_evidence_is_not_built(tmp_path: Path) -> None:
    host = _closed_host(tmp_path, binding_item("ver-alpha"))
    states = _built(host)
    assert states[INVARIANT].state is BUILT, "the obligation mitigation is built by the engine"
    assert states[THREAT].state is NOT_BUILT and states[THREAT].via == (FIXTURE,)
    run(host, ["ver-alpha"])
    assert _state(host, THREAT) is BUILT


def test_a_threat_whose_obligation_mitigation_is_not_built_is_not_built_even_with_proven_fixtures(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item("ver-alpha"))
    run(host, ["ver-alpha"])
    states = _built(host)
    assert states[INVARIANT].state is NOT_BUILT and states[THREAT].state is NOT_BUILT and states[THREAT].via == (INVARIANT,)


def test_zero_mitigation_threat_is_not_built(tmp_path: Path) -> None:
    host = _closed_host(tmp_path, binding_item("ver-alpha"))
    run(host, ["ver-alpha"])
    edit_doc(host, "11_redteam.json", lambda doc: doc["threats"][0].pop("mitigated_by"))
    result = _built(host)[THREAT]
    assert (result.state, result.reason) == (NOT_BUILT, "it has no mitigation in play")


# --- relieved ---------------------------------------------------------------------------------------------------------


def test_relieved_list_holds_an_nfr_with_only_a_staging_binding_at_cap_ci(tmp_path: Path) -> None:
    host = _latency_host(tmp_path)
    ctx = _ctx(host)
    assert [found.id for found in relieved_nodes(ctx, "ci")] == [NFR]
    result = built_state(ctx, graph_of(host).by_id[NFR], "ci")
    assert (result.state, result.waits_for) == (RELIEVED, "staging")


def test_a_retired_binding_does_not_set_the_stage_a_relieved_node_waits_for(tmp_path: Path) -> None:
    """At cap dev the NFR waits for the lowest stage of a live binding above the cap; a binding of a retired environment (ci is out) is not one."""
    host = _latency_host(tmp_path)
    write_binding(records_folder(str(host / "spec")), str(ROOT), binding_item("ver-latency-ci", verifier=LATENCY_FIXTURE, proves=(NFR,), stage="ci"))
    commit_all(host)
    assert built_state(_ctx(host), graph_of(host).by_id[NFR], "dev").waits_for == "ci"
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"]["ci"].update(scope="out"))
    assert built_state(_ctx(host), graph_of(host).by_id[NFR], "dev").waits_for == "staging"


def test_relieved_node_satisfies_its_ancestor_at_cap_ci(tmp_path: Path) -> None:
    """A threat mitigated by the relieved NFR is satisfied (it waits for the same stage); at cap staging nothing waits and it is built."""
    host = _latency_host(tmp_path)
    edit_doc(host, "11_redteam.json", lambda doc: doc["threats"][0].update(mitigated_by=[NFR]))
    states = _built(host)
    assert states[NFR].state is RELIEVED
    assert (states[THREAT].state, states[THREAT].via, states[THREAT].waits_for) == (RELIEVED, (NFR,), "staging")
    assert _state(host, THREAT, "staging") is BUILT


def test_at_cap_staging_the_node_is_no_longer_relieved(tmp_path: Path) -> None:
    host = _latency_host(tmp_path)
    assert _state(host, NFR, "staging") is BUILT and relieved_nodes(_ctx(host), "staging") == []
    run(host, [LATENCY_BINDING], stage="staging")
    assert _state(host, NFR, "staging") is BUILT


def test_a_node_that_is_not_built_by_its_own_branch_is_never_relieved(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(LATENCY_BINDING, verifier=LATENCY_FIXTURE, proves=(NFR,), stage="staging"))
    add_fixture(host, fixture_id=LATENCY_FIXTURE, verifies=[NFR])
    assert _state(host, NFR, "ci") is NOT_BUILT and relieved_nodes(_ctx(host), "ci") == []


def test_built_state_enum_readers_handle_relieved() -> None:
    """A relieved obligation counts as built for the parent and the constraint that read it."""
    nodes = [
        node("fr-1", "fr", children=["ac-1", "ac-2"]),
        node("ac-1", "criterion", parent="fr-1"),
        node("ac-2", "criterion", parent="fr-1"),
    ]
    ctx = built_context(nodes, {"tc-1": "ac-1"})
    answer = BuiltResult(RELIEVED, "waits for staging", waits_for="staging")
    restore = register_built_provider(lambda found: found.id == "ac-2", lambda _run, _found: answer)
    try:
        result = compute_built(ctx)
    finally:
        restore()
    assert result["ac-2"] == answer
    assert result["fr-1"].state is BUILT and result["fr-1"].via == ("ac-1", "ac-2")


# --- cost and a host without what the branches read ---------------------------------------------------------------------


def test_the_code_tree_is_computed_once_for_a_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = _ci_host(tmp_path)
    calls: list[str] = []
    real = validity.code_tree_for_host
    monkeypatch.setattr(validity, "code_tree_for_host", lambda *args, **kwargs: calls.append("tree") or real(*args, **kwargs))
    states = built_at_cap(_ctx(host), "ci")
    assert {states[name].state for name in (ENVIRONMENT, GATE, JOB_RULE)} == {BUILT}
    assert calls == ["tree"], "four nodes read the evidence of one binding: one code tree for the context, not one for each node"


def test_a_context_without_a_host_root_leaves_the_evidence_kinds_pending(tmp_path: Path) -> None:
    host = _ci_host(tmp_path)
    spec = str(host / "spec")
    ctx = GraphCheckContext.from_graph(graph_of(host), read_lock(spec), str(ROOT))
    states = built_at_cap(ctx, "ci")
    assert {states[name].state for name in (ENVIRONMENT, GATE, JOB_RULE, THREAT)} == {PENDING}
    assert states[ENVIRONMENT].reason == "no host repository to read evidence from"


def test_a_spec_outside_a_git_repository_leaves_the_evidence_kinds_pending(tmp_path: Path) -> None:
    host = _ci_host(tmp_path)
    shutil.rmtree(host / ".git")
    states = _built(host)
    assert {states[name].state for name in (ENVIRONMENT, GATE, JOB_RULE)} == {PENDING}
    assert states[ENVIRONMENT].reason.startswith("the code tree cannot be read")


def test_a_node_whose_stage_cannot_be_told_is_not_built_and_the_other_nodes_are_still_answered(tmp_path: Path) -> None:
    """The proof raises E334 for such a node; the built computation must report it on that node, not stop."""
    host = _ci_host(tmp_path)
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"].update(qa={"scope": "in"}))
    edit_doc(host, "12_ci_gates.json", lambda doc: doc["jobs"].append({"job_id": "job-qa-smoke", "name": "QA smoke", "realises": ["qa"]}))
    states = _built(host)
    assert states["qa"].state is BuiltState.NOT_BUILT
    assert "environment 'qa' is not a stage" in states["qa"].reason
    assert ENVIRONMENT in states


def test_unreadable_host_declarations_are_raised_once_by_built_at_cap_not_reported_for_every_node(tmp_path: Path) -> None:
    """Only the stage finding (E334) becomes a reason on one node; an E520 of the host declarations is raised, as ``proof_errors`` raises it."""
    host = _ci_host(tmp_path)
    write(host / "spec" / "common" / "host_declarations.json", "{ not json")
    with pytest.raises(FindingError) as caught:
        _built(host)
    assert caught.value.error.code == "E520"


def test_a_host_with_no_verification_folder_and_no_declarations_reports_what_the_branches_say(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    assert list((host / "spec" / "extras" / "verification").glob("*.json")) == []
    assert not (host / "spec" / "common" / "host_declarations.json").exists()
    states = _built(host)
    assert states[ENVIRONMENT].state is NOT_BUILT and "no binding" in states[ENVIRONMENT].reason
    assert states[COMMAND_RULE].state is BUILT and states[REVIEW_RULE].state is PENDING
    assert pin_matches(_ctx(host), graph_of(host).by_id[TP]) == "UNKNOWN"


def test_built_at_cap_removes_its_provider_and_refuses_a_cap_that_is_not_a_stage(tmp_path: Path) -> None:
    host = _ci_host(tmp_path)
    ctx = _ctx(host)
    assert built_at_cap(ctx, "ci")[ENVIRONMENT].state is BUILT
    assert compute_built(ctx)[ENVIRONMENT].state is PENDING, "the plain computation keeps the evidence kinds pending"
    with pytest.raises(ValueError):
        built_at_cap(ctx, "later")
    with pytest.raises(KeyError):
        built_at_cap(ctx, "ci", "no-such-node")
    assert compute_built(ctx)[ENVIRONMENT].state is PENDING
