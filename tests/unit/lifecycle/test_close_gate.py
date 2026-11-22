"""The close gate: each check failing alone on a milestone that otherwise passes, the paused and out-of-play work, the chain filter and the close record check."""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.graph.gitview import read_seed_texts
from specdev_tools.lifecycle import anchor_store, chain, close_gate, frozen
from specdev_tools.lifecycle.close_gate import GateReport, PausedTask, check_close_gate, verify_close_record
from specdev_tools.lifecycle.executed import lock_if_present
from specdev_tools.lifecycle.plan_records import Address, record_action
from specdev_tools.proof.built_evidence import bind_proof_seams
from specdev_tools.trace.lockfile import Lock, read_lock, write_lock
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.scaffold import ScaffoldScan, scaffold_scan
from specdev_tools.validation.open_items import check_open_items
from unit.graph._synth import ROOT
from unit.lifecycle._milestone_support import attest_nodes
from unit.lifecycle._record_support import ITEM, action, alpha_binding, author, closed_row, plan_host, roots
from unit.lifecycle._support import MILESTONE, PLAN, closed_record
from unit.proof._closed import add_milestone, criterion
from unit.proof._support import API, CRITERION, FIXTURE, INVARIANT, OTHER_FIXTURE, REUSED_BINDING, add_fixture, attest, binding_item, context, edit_code, run
from unit.verify._support import commit_all, edit_doc, graph_of, write, write_json

pytestmark = pytest.mark.usefixtures("author")

SECOND_ITEM = "PWRESET_CONFIRM_REUSED_01"
SECOND_CRITERION = "tc-confirm-reused-token"
SCAFFOLD_FILE = "src/routes/password-resets/confirm.ts"
SIGNOFF_DIR = Path("spec") / "extras" / "signoff"
ROADMAP = "14_roadmap.json"
FIXTURES = Path(__file__).parents[2] / "fixtures" / "m8_legacy_rows" / "spec"
REVIEW = {"verdict": "verified", "recorded_at": "2026-11-21T10:00:00Z"}


def _second_item() -> dict[str, Any]:
    return {
        "id": SECOND_ITEM, "realises": [SECOND_CRITERION], "description": "A second redemption of a token is refused.", "type": "behavior", "layer": "api",
        "implementation": {"actions": []},
    }


def _signoff(host: Path, number: int = 1, milestone: str = MILESTONE) -> None:
    """A sign-off record of the milestone, as ``milestone sign-off`` writes one."""
    record_id = f"so-{milestone}-{number:04d}"
    record = {
        "signoff_id": record_id, "about": [milestone], "tree": "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
        "git_author": {"name": "Ada Lovelace", "email": "ada@example.invalid"}, "recorded_at": "2026-11-21T10:00:00Z",
        "listed": {"manual_fixtures": [], "attested": [], "deferred_tasks": [], "wont_do_tasks": [], "open_items": 0, "staging_prod_proof_owed": []},
    }
    write_json(host / SIGNOFF_DIR / f"{record_id}.json", {"records": [record]})


def ready(tmp_path: Path, *extra_actions: dict[str, Any], alpha: dict[str, Any] | None = None, tracked: bool = True) -> Path:
    """The worked example with both criteria realised, bound, run and proven, the item executed, a verified review, a sign-off and a tracked scaffold file."""
    bindings = (alpha or alpha_binding(), binding_item(REUSED_BINDING, verifier=OTHER_FIXTURE, proves=(INVARIANT,)))
    host = plan_host(tmp_path, *extra_actions, bindings=bindings)

    def edit_plan(document: dict[str, Any]) -> None:
        document["plan"]["spec_alignment"]["checklist"].append(_second_item())
        document["review"] = dict(REVIEW)

    edit_doc(host, PLAN, edit_plan)
    attest_nodes(host, SECOND_ITEM)
    if tracked:
        write(host / SCAFFOLD_FILE, "export {};\n")
    _signoff(host)
    commit_all(host, "ready")
    spec, repo, git = roots(host)
    record_action(spec, repo, git, Address(ITEM, "a01"), "done")
    run(host, [binding["verification_id"] for binding in bindings if binding["stage"] == "dev"])
    return host


def gate(host: Path, milestone: str = MILESTONE, *, with_lock: bool = True) -> GateReport:
    """The close gate on *host* as it is now, with the real open-item and scaffold checks."""
    bind_proof_seams()
    spec = str(host / "spec")
    graph = graph_of(host)
    held = lock_if_present(spec) if with_lock else None
    scan_context = GraphCheckContext.from_graph(graph, held, str(ROOT), git_root=str(host), spec_root=spec)
    return check_close_gate(
        graph, context(host), held, milestone,
        open_items=lambda plan: check_open_items(spec, gate="close", plan_path=plan),
        scaffold=lambda apis: scaffold_scan(scan_context, apis, "close"),
    )


def codes(report: GateReport) -> list[str]:
    return [error.code for error in report.errors]


def edit_roadmap(host: Path, edit: Any) -> None:
    edit_doc(host, ROADMAP, lambda document: edit(document["milestones"][0]["tasks"][0]))


def change_stamp(host: Path, holder: str, target: str) -> None:
    """Make the lock entry of the link *holder* to *target* carry a chain stamp the target no longer has: the link is suspect."""
    lock = read_lock(str(host / "spec"))
    stamped = [entry.__class__(**{**entry.__dict__, "chain_stamp": "sha256:" + "0" * 64}) if (entry.source, entry.target) == (holder, target) else entry for entry in lock.entries]
    write_lock(str(host / "spec"), Lock(tuple(stamped)))


# --- the milestone that passes ----------------------------------------------------------------------------------------


def test_all_checks_pass(tmp_path: Path) -> None:
    report = gate(ready(tmp_path))
    assert (report.errors, report.warnings, report.paused, report.notes) == ((), (), (), ())
    assert report.passed


# --- each check failing alone -----------------------------------------------------------------------------------------


def test_e810_criterion_with_no_plan_item(tmp_path: Path) -> None:
    host = ready(tmp_path)
    edit_doc(host, PLAN, lambda document: document["plan"]["spec_alignment"]["checklist"].pop())
    report = gate(host)
    assert [(error.code, error.node_id, error.owner) for error in report.errors] == [("E810", SECOND_CRITERION, "close-gate")]
    assert "realises" in report.errors[0].message and PLAN.split("/")[1] in report.errors[0].message


def test_e811_criterion_unproven(tmp_path: Path) -> None:
    host = ready(tmp_path)
    edit_code(host)
    report = gate(host)
    assert [(error.code, error.node_id) for error in report.errors] == [("E811", "tc-confirm-expired-token"), ("E811", SECOND_CRITERION)]
    assert "STALE_TREE" in report.errors[0].message and "specdev verify run ver-alpha --stage dev" in report.errors[0].message


def test_e812_item_not_executed(tmp_path: Path) -> None:
    host = ready(tmp_path)
    spec, repo, git = roots(host)
    record_action(spec, repo, git, Address(ITEM, "a01"), "failed")
    report = gate(host)
    assert [(error.code, error.node_id, error.owner) for error in report.errors] == [("E812", ITEM, "close-gate")]
    assert "a01" in report.errors[0].message


@pytest.mark.parametrize("review", [None, {**REVIEW, "verdict": "needs_work"}, {**REVIEW, "verdict": "blocked"}])
def test_e813_review_not_verified(tmp_path: Path, review: dict[str, Any] | None) -> None:
    host = ready(tmp_path)
    edit_doc(host, PLAN, lambda document: document.pop("review") if review is None else document.update(review=review))
    report = gate(host)
    assert [(error.code, error.node_id, error.owner) for error in report.errors] == [("E813", MILESTONE, "close-gate")]
    assert "specdev review record ms-account-recovery --verdict verified" in report.errors[0].message


def test_a_verified_review_with_a_blocking_finding_or_red_security_is_not_judged_here(tmp_path: Path) -> None:
    """The review record accepts them and the pack gives the gate one rule about the block: the verdict."""
    host = ready(tmp_path)
    edit_doc(host, PLAN, lambda document: document["review"].update(security_status="red"))
    assert gate(host).passed


def test_e814_no_signoff_record(tmp_path: Path) -> None:
    host = ready(tmp_path)
    (host / SIGNOFF_DIR / f"so-{MILESTONE}-0001.json").unlink()
    report = gate(host)
    assert [(error.code, error.node_id, error.owner) for error in report.errors] == [("E814", MILESTONE, "close-gate")]
    assert "specdev milestone sign-off" in report.errors[0].message


def test_a_signoff_of_another_milestone_is_not_one(tmp_path: Path) -> None:
    host = ready(tmp_path)
    (host / SIGNOFF_DIR / f"so-{MILESTONE}-0001.json").rename(host / SIGNOFF_DIR / "so-ms-other-0001.json")
    document = json.loads((host / SIGNOFF_DIR / "so-ms-other-0001.json").read_text(encoding="utf-8"))
    document["records"][0].update(signoff_id="so-ms-other-0001", about=["ms-other"])
    write_json(host / SIGNOFF_DIR / "so-ms-other-0001.json", document)
    assert codes(gate(host)) == ["E814"]


def test_open_item_blocks_close(tmp_path: Path) -> None:
    host = ready(tmp_path)
    item = {"id": "amb-where-to-store", "description": "Where does the token live?", "about": [ITEM]}
    edit_doc(host, PLAN, lambda document: document.update(execution={**document.get("execution", {}), "emergent_ambiguities": [item]}))
    report = gate(host)
    assert [(error.code, error.owner) for error in report.errors] == [("E632", "close-gate")]


def test_suspect_on_the_chain_blocks_close(tmp_path: Path) -> None:
    host = ready(tmp_path)
    change_stamp(host, "tc-confirm-expired-token", CRITERION)
    report = gate(host)
    assert [(error.code, error.node_id, error.owner) for error in report.errors] == [("E763", "tc-confirm-expired-token", "close-gate")]
    assert "suspect link" in report.errors[0].message


def test_a_link_with_no_lock_entry_on_the_chain_blocks_close(tmp_path: Path) -> None:
    """A plan item added by a file edit and never attested has no entry; after the close its link is historical and can no longer be attested."""
    host = ready(tmp_path)
    lock = read_lock(str(host / "spec"))
    kept = tuple(entry for entry in lock.entries if (entry.source, entry.field) != (SECOND_ITEM, "realises"))
    assert len(kept) == len(lock.entries) - 1
    write_lock(str(host / "spec"), Lock(kept))
    report = gate(host)
    assert [(error.code, error.node_id, error.owner) for error in report.errors] == [("E761", SECOND_ITEM, "close-gate")]
    assert "no entry for this link" in report.errors[0].message and f"specdev attest {SECOND_ITEM}" in report.errors[0].message


def test_a_link_with_no_lock_entry_off_the_chain_does_not_block_close(tmp_path: Path) -> None:
    host = ready(tmp_path)
    lock = read_lock(str(host / "spec"))
    kept = tuple(entry for entry in lock.entries if (entry.source, entry.target) != ("nfr-latency-reset-email", "tp-mailrelay"))
    write_lock(str(host / "spec"), Lock(kept))
    assert gate(host).passed


def test_a_suspect_off_the_chain_does_not_block_close(tmp_path: Path) -> None:
    host = ready(tmp_path)
    change_stamp(host, "nfr-latency-reset-email", "tp-mailrelay")
    assert gate(host).passed


def test_without_a_trace_lock_the_suspect_check_is_skipped_and_the_report_says_so(tmp_path: Path) -> None:
    report = gate(ready(tmp_path), with_lock=False)
    assert report.passed and report.notes == ("no trace lock: the suspect-link check was skipped",)


def test_scaffold_row_untracked_blocks_close(tmp_path: Path) -> None:
    report = gate(ready(tmp_path, tracked=False))
    assert [(error.code, error.node_id, error.owner) for error in report.errors] == [("E746", "scaffold-password-reset-confirm", "close-gate")]
    assert SCAFFOLD_FILE in report.errors[0].message


def test_a_scaffold_scan_that_could_not_run_is_a_note_not_a_pass_without_a_word(tmp_path: Path) -> None:
    host = ready(tmp_path)
    graph, spec = graph_of(host), str(host / "spec")

    report = check_close_gate(graph, context(host), lock_if_present(spec), MILESTONE, open_items=lambda plan: [], scaffold=lambda apis: ScaffoldScan(skip_reason="git does not answer"))
    assert report.passed and report.notes == ("scaffold rows were not checked: git does not answer",)


def test_the_gate_reports_every_check_that_fails_in_the_order_of_the_checks(tmp_path: Path) -> None:
    host = ready(tmp_path, tracked=False)
    edit_code(host)
    edit_doc(host, PLAN, lambda document: document.pop("review"))
    (host / SIGNOFF_DIR / f"so-{MILESTONE}-0001.json").unlink()
    assert codes(gate(host)) == ["E811", "E811", "E813", "E746", "E814"]


# --- what is out of play ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["deferred", "wont_do"])
def test_deferred_task_is_excluded_with_its_reason(tmp_path: Path, value: str) -> None:
    host = ready(tmp_path)
    edit_code(host)
    edit_roadmap(host, lambda task: task.update(disposition={"value": value, "reason": "Waiting for the vendor sandbox."}))
    report = gate(host)
    assert report.paused == (PausedTask("task-implement-password-reset-confirm", value, "Waiting for the vendor sandbox."),)
    assert report.errors == ()
    assert sorted(error.node_id or "" for error in report.warnings) == [ITEM, SECOND_ITEM] and {error.code for error in report.warnings} == {"W826"}


def test_a_w826_of_an_item_outside_the_milestone_is_not_in_its_warnings(tmp_path: Path) -> None:
    host = ready(tmp_path)
    edit_code(host)
    edit_roadmap(host, lambda task: task.update(disposition={"value": "deferred", "reason": "Waiting for the vendor sandbox."}))
    graph = graph_of(host)
    both = [graph.find(ITEM), graph.find(SECOND_ITEM)]
    assert all(node is not None for node in both)
    spec = str(host / "spec")
    warnings = close_gate._paused_items_warnings(graph, lock_if_present(spec), spec, [both[1]])
    assert [error.node_id for error in warnings] == [SECOND_ITEM]


def test_an_item_that_realises_a_paused_and_a_live_criterion_is_still_held_to_execution(tmp_path: Path) -> None:
    host = ready(tmp_path)
    spec, repo, git = roots(host)
    record_action(spec, repo, git, Address(ITEM, "a01"), "failed")
    edit_doc(host, PLAN, lambda document: document["plan"]["spec_alignment"]["checklist"][0]["realises"].append(SECOND_CRITERION))
    attest_nodes(host, ITEM)
    assert codes(gate(host)) == ["E812"]


def test_a_not_applicable_criterion_is_out_of_play(tmp_path: Path) -> None:
    host = ready(tmp_path)
    edit_code(host)
    edit_roadmap(host, lambda task: task["acceptance_criteria"].__setitem__(1, {**task["acceptance_criteria"][1], "lifecycle": "not_applicable"}))
    report = gate(host)
    assert [error.node_id for error in report.errors] == ["tc-confirm-expired-token"] and codes(report) == ["E811"]


def test_staging_only_binding_does_not_block(tmp_path: Path) -> None:
    host = ready(tmp_path, alpha=alpha_binding(stage="staging"))
    assert gate(host).passed


def test_at_deploy_action_does_not_block(tmp_path: Path) -> None:
    host = ready(tmp_path, action("a02", at_deploy=["staging"]))
    assert gate(host).passed


def test_removes_criterion_is_proven_by_its_fixture(tmp_path: Path) -> None:
    host = ready(tmp_path)
    edit_roadmap(host, lambda task: task["acceptance_criteria"].__setitem__(1, {"criterion_id": SECOND_CRITERION, "text": "The reuse rule is retired.", "removes": ["fr-password-reset-request"], "verified_by": [OTHER_FIXTURE]}))
    attest_nodes(host, SECOND_CRITERION, SECOND_ITEM)
    assert gate(host).passed


def test_unattested_manual_fixture_fails_e811(tmp_path: Path) -> None:
    host = ready(tmp_path)
    add_fixture(host, fixture_id="fix-reuse-manual", verifies=[INVARIANT], mode="manual", manual_reason="A person redeems a token twice.")
    edit_roadmap(host, lambda task: task["acceptance_criteria"][1].update(verified_by=["fix-reuse-manual"]))
    attest_nodes(host, "fix-reuse-manual", SECOND_CRITERION, SECOND_ITEM)
    report = gate(host)
    assert [(error.code, error.node_id) for error in report.errors] == [("E811", SECOND_CRITERION)]
    attest(host, "fix-reuse-manual")
    assert gate(host).passed


# --- how proof is asked ----------------------------------------------------------------------------------------------


def test_close_call_passes_cap_dev_and_treat_ci_as_dev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = ready(tmp_path)
    seen: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
    real = close_gate.proof

    def spy(graph: Any, ctx: Any, obligation: str, *args: Any, **keywords: Any) -> Any:
        seen.append((obligation, args, keywords))
        return real(graph, ctx, obligation, *args, **keywords)

    monkeypatch.setattr(close_gate, "proof", spy)
    assert gate(host).passed
    assert seen == [("tc-confirm-expired-token", ("dev",), {"treat_ci_as_dev": True}), (SECOND_CRITERION, ("dev",), {"treat_ci_as_dev": True})]


def test_a_node_whose_stage_cannot_be_told_is_one_finding_and_the_others_are_still_answered(tmp_path: Path) -> None:
    host = ready(tmp_path)
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"].update(qa={"scope": "in"}))
    edit_doc(host, "12_ci_gates.json", lambda doc: doc["jobs"].append({"job_id": "job-qa-smoke", "name": "QA smoke", "realises": ["qa"]}))
    edit_roadmap(host, lambda task: task["acceptance_criteria"][1].update(refines=[INVARIANT, "qa"]))
    attest_nodes(host, "job-qa-smoke", SECOND_CRITERION, SECOND_ITEM)
    edit_code(host)
    report = gate(host)
    assert [(error.code, error.node_id) for error in report.errors] == [("E811", "tc-confirm-expired-token"), ("E334", SECOND_CRITERION)]
    assert "environment 'qa' is not a stage" in report.errors[1].message


def test_unreadable_host_declarations_stop_the_gate_with_one_error(tmp_path: Path) -> None:
    host = ready(tmp_path)
    write(host / "spec" / "common" / "host_declarations.json", "{ not json")
    with pytest.raises(FindingError) as caught:
        gate(host)
    assert caught.value.error.code == "E520"


# --- the plan after the close, and a legacy close -------------------------------------------------------------------


def test_frozen_plan_drift_after_close(tmp_path: Path) -> None:
    host = ready(tmp_path)
    spec = str(host / "spec")
    assert frozen.frozen_plan_drift(spec, MILESTONE) is None
    closed_row(host)
    assert frozen.frozen_plan_drift(spec, MILESTONE) is None and frozen.check_frozen_plans(spec).errors == ()
    edit_doc(host, PLAN, lambda document: document["plan"]["summary"].update(functional_summary="Changed by hand after the close."))
    [finding] = frozen.check_frozen_plans(spec).errors
    assert (finding.code, finding.node_id) == ("E827", MILESTONE)
    assert frozen.frozen_plan_drift(FIXTURES, "ms-done") is None


def test_legacy_close_is_not_rechecked(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    assert {"E813", "E814"} <= set(codes(gate(host)))
    anchor_store.write_legacy_close(host / "spec", MILESTONE, "1.1.1 migration", repo_root=str(ROOT))
    report = gate(host)
    assert (report.passed, report.errors, report.warnings, report.notes) == (True, (), (), ("legacy close: not re-checked",))


# --- verify_close_record ----------------------------------------------------------------------------------------------


def test_verify_close_record_signature() -> None:
    signature = inspect.signature(verify_close_record)
    assert list(signature.parameters) == ["row"]
    assert signature.return_annotation == "list[SpecError]"


def _state(status: str = "done", **close: Any) -> anchor_store.AnchorState:
    record = closed_record(**close)
    return anchor_store.state_of(status, {key: value for key, value in record.items() if value is not None})


def test_verify_close_record_accepts_a_good_record_a_legacy_close_and_the_rows_of_the_fixture() -> None:
    assert verify_close_record(_state()) == []
    assert verify_close_record(anchor_store.state_of("done", {"signed_off_by": "legacy-migration", "source": "1.1.1", "signoff": None})) == []
    done, pending = anchor_store.read_row(FIXTURES, "ms-done"), anchor_store.read_row(FIXTURES, "ms-pending")
    assert done is not None and pending is not None
    assert verify_close_record(done) == []
    [finding] = verify_close_record(pending)
    assert (finding.code, finding.node_id, finding.owner) == ("E814", "ms-pending", "close-gate")


def test_verify_close_record_names_the_milestone_of_a_row_and_works_on_the_statuses_of_a_ref(tmp_path: Path) -> None:
    host = ready(tmp_path)
    closed_row(host)
    states = anchor_store.read_statuses(host / "spec")
    assert verify_close_record(states[MILESTONE]) == []
    row = anchor_store.read_row(host / "spec", MILESTONE)
    assert row is not None and verify_close_record(row) == []


@pytest.mark.parametrize(
    "state",
    [
        _state(signoff=None),
        _state(signoff=""),
        _state(signed_off_by=""),
        _state("in_progress"),
        anchor_store.state_of("done", None),
        anchor_store.state_of("done", {"signoff": "so-ms-account-recovery-0001"}),
    ],
)
def test_verify_close_record_refuses_a_tampered_or_absent_record(state: anchor_store.AnchorState) -> None:
    [finding] = verify_close_record(state)
    assert (finding.code, finding.owner) == ("E814", "close-gate")


# --- the chain -------------------------------------------------------------------------------------------------------


def test_the_chain_holds_the_milestone_its_work_and_what_that_reaches_upward(tmp_path: Path) -> None:
    host = ready(tmp_path)
    reached = chain.milestone_chain(graph_of(host), MILESTONE)
    assert {MILESTONE, "task-implement-password-reset-confirm", "tc-confirm-expired-token", ITEM, SECOND_ITEM, CRITERION, API, "seed-accounts"} <= reached
    assert "nfr-latency-reset-email" not in reached and "tp-mailrelay" not in reached


def test_the_chain_of_a_milestone_that_shares_upstream_with_another_is_its_own(tmp_path: Path) -> None:
    host = ready(tmp_path)
    [other] = add_milestone(host, "ms-other", [criterion("tc-other", refines=[CRITERION], verified_by=[FIXTURE])], done=False)
    graph = graph_of(host)
    ours, theirs = chain.milestone_chain(graph, MILESTONE), chain.milestone_chain(graph, "ms-other")
    assert CRITERION in ours and CRITERION in theirs
    assert other not in ours and "tc-confirm-expired-token" not in theirs and "task-implement-password-reset-confirm" not in theirs
    assert chain.on_chain(ours, graph, other, CRITERION) and not chain.on_chain(theirs, graph, "tc-confirm-expired-token", "tp-mailrelay")


def test_a_suspect_link_of_another_milestone_is_on_our_chain_only_when_it_points_into_it(tmp_path: Path) -> None:
    host = ready(tmp_path)
    add_milestone(host, "ms-other", [criterion("tc-other", refines=[CRITERION], verified_by=[FIXTURE])], done=False)
    change_stamp(host, "tc-other", CRITERION)
    change_stamp(host, "nfr-latency-reset-email", "tp-mailrelay")
    graph, spec = graph_of(host), str(host / "spec")
    texts = read_seed_texts(graph, str(host))
    on_ours = chain.suspect_links_on_chain(graph, read_lock(spec), texts, chain.milestone_chain(graph, MILESTONE))
    assert [(error.node_id, error.target) for error in on_ours] == [("tc-other", f"refines->{CRITERION}")]
    assert all(error.code == "E763" for error in on_ours)


# --- the branches the gate rests on (round 1 survivors m13, m14, m15) ---------------------------------------------------


def test_a_not_applicable_task_is_out_of_play_with_its_criteria(tmp_path: Path) -> None:
    """The lifecycle of a task is not passed on to its criteria, so the gate reads the task's own lifecycle."""
    host = ready(tmp_path)
    edit_code(host)
    assert codes(gate(host)) == ["E811", "E811"]
    edit_roadmap(host, lambda task: task.update(lifecycle="not_applicable"))
    report = gate(host)
    assert report.errors == () and report.paused == ()


def test_an_item_that_realises_only_paused_criteria_is_not_held_to_execution(tmp_path: Path) -> None:
    host = ready(tmp_path)
    spec, repo, git = roots(host)
    record_action(spec, repo, git, Address(ITEM, "a01"), "failed")
    assert codes(gate(host)) == ["E812"]
    edit_roadmap(host, lambda task: task.update(disposition={"value": "deferred", "reason": "Waiting for the vendor sandbox."}))
    report = gate(host)
    assert report.errors == ()
    assert [error.node_id for error in report.warnings if error.node_id == ITEM] == [ITEM]


def test_a_plan_item_of_another_milestone_is_not_held_to_this_milestones_execution(tmp_path: Path) -> None:
    host = ready(tmp_path)
    add_milestone(host, "ms-other", [criterion("tc-other", refines=[CRITERION], verified_by=[FIXTURE])], done=False)
    plan = json.loads((host / "spec" / PLAN).read_text(encoding="utf-8"))
    foreign = {"id": "OTHER_REALISES_01", "realises": [SECOND_CRITERION], "description": "Realises a criterion of the first milestone.", "type": "behavior", "layer": "api",
               "implementation": {"actions": [action("a01")]}}
    write_json(host / "spec" / "impl_context" / "ms_other_plan.json", {"$schema": plan["$schema"], "milestone": "ms-other", "plan": {"spec_alignment": {"checklist": [foreign]}}})
    assert foreign["id"] in [node.id for node in graph_of(host).by_kind["plan-item"]]
    assert [node.id for node in close_gate.plan_items(graph_of(host), "ms-other")] == [foreign["id"]]
    assert gate(host).passed
