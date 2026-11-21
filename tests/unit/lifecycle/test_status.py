"""``specdev status``: each section, the awaiting-sign-off row, the milestone view, the extension point and the exit code."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.lifecycle import status as status_module
from specdev_tools.lifecycle.executed import lock_if_present
from specdev_tools.lifecycle.signoff import sign_off
from specdev_tools.lifecycle.status import Section, build_status, register_status_section, status_context
from unit.lifecycle._milestone_support import change_stamp, cli_run, providers_of, ready_host, set_row
from unit.lifecycle._record_support import alpha_binding, author, closed_row, plan_host, roots
from unit.lifecycle._support import MILESTONE, PLAN
from unit.proof._closed import closed_example, reword_criterion
from unit.proof._support import CRITERION, FIXTURE, run
from unit.verify._support import commit_all, edit_doc
from unit._ambiguity_support import unified_item

pytestmark = pytest.mark.usefixtures("author")
SECTION_NAMES = ["pending_replay", "open_items", "awaiting_signoff", "realisations", "next_step", "gate_owned_errors", "merge_release_gates", "production_verification"]


def _sections(host: Path) -> dict[str, Section]:
    spec, repo, git = roots(host)
    context = status_context(spec, repo, git, lock_if_present(spec), build_graph(spec, repo), providers_of(host))
    return {section.name: section for section in build_status(context)}


def test_each_section_on_a_fixture(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    reword_criterion(host, CRITERION, "A reset email arrives within sixty seconds of the request.")
    change_stamp(host, "tc-confirm-expired-token", CRITERION)
    edit_doc(host, PLAN, lambda document: document["plan"].update(ambiguities=[unified_item("amb-token-length", about=["tc-confirm-expired-token"])]))
    sections = _sections(host)
    assert list(sections) == SECTION_NAMES
    assert any("suspect link" in line for line in sections["pending_replay"].lines)
    assert sections["open_items"].data == {}, "the plan is closed: its open item is a legacy item, as for spec-check"
    assert any(line.startswith("E343 outdated") for line in sections["realisations"].lines)
    assert sections["next_step"].lines == ("every step has a spec file",)
    assert sections["awaiting_signoff"].lines == ("none",)
    assert sections["merge_release_gates"].lines == ("release gate not installed",) == sections["production_verification"].lines


def test_awaiting_signoff_row_appears_after_a_verified_review_and_goes_after_signoff(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    assert _sections(host)["awaiting_signoff"].data == [MILESTONE]
    spec, repo, git = roots(host)
    sign_off(spec, repo, git, MILESTONE, providers_of(host))
    assert _sections(host)["awaiting_signoff"].data == []
    edit_doc(host, PLAN, lambda document: document["review"].update(verdict="needs_work"))
    assert _sections(host)["awaiting_signoff"].data == []


def _manual(document: dict[str, Any]) -> None:
    for fixture in document["fixtures"]:
        if fixture["fixture_id"] == FIXTURE:
            fixture.update(mode="manual", manual_reason="A person reads the mail relay log.")


def test_milestone_view_lists_the_manual_share(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    edit_doc(host, "08_fixtures.json", _manual)
    (host / "spec" / "extras" / "verification" / "ver-alpha.json").unlink()
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE)
    assert code == 0 and "manual share: 1 node(s) a person attests, 0 attested" in out
    assert f"{FIXTURE} (fixture): not attested; `specdev verify attest {FIXTURE}`" in out
    code, out, _ = cli_run(host, "verify", "attest", FIXTURE)
    assert code == 0, out
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE, "--json")
    assert json.loads(out)["manual"] == {"count": 1, "attested": 1, "nodes": [{"node": FIXTURE, "kind": "fixture", "attested": True}]}


def test_milestone_view_lists_paused_tasks_with_their_reasons(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    edit_doc(host, "14_roadmap.json", lambda document: document["milestones"][0]["tasks"][0].update(disposition={"value": "deferred", "reason": "waits for the mail relay"}))
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE)
    assert code == 0 and "task-implement-password-reset-confirm deferred: waits for the mail relay" in out
    assert "(W826)" in out


def test_gate_owned_errors_group_by_owner(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    section = _sections(host)["gate_owned_errors"]
    assert list(section.data["errors"]) == ["close-gate"]
    assert [line.split(": ")[1].split(" ")[0] for line in section.data["errors"]["close-gate"]] == ["E810", "E811", "E811", "E812", "E813", "E746", "E814"]
    assert section.lines[0] == "close-gate (7):"
    set_row(host, "pending")
    assert _sections(host)["gate_owned_errors"].data["errors"] == {}


def test_extension_point_accepts_a_stub_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = plan_host(tmp_path)
    monkeypatch.setattr(status_module, "SECTIONS", dict(status_module.SECTIONS))
    register_status_section("stub", lambda _sc: Section("stub", "A stub", ("hello",), {"n": 1}))
    register_status_section(status_module.PRODUCTION_SECTION, lambda _sc: Section(status_module.PRODUCTION_SECTION, "Production verification", ("installed",), None))
    sections = _sections(host)
    assert list(sections) == [*SECTION_NAMES, "stub"] and sections["production_verification"].lines == ("installed",)
    code, out, _ = cli_run(host, "status")
    assert code == 0 and "A stub\n  hello" in out


def test_status_exits_zero_beside_an_unreadable_file(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    (host / "spec" / "05_interface_contracts.json").write_text("{ not json", encoding="utf-8")
    code, out, err = cli_run(host, "status")
    assert code == 0 and "could not read" in err and "Gate-owned errors by owner" in out


def test_status_json_keys_are_stable(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    code, out, _ = cli_run(host, "status", "--json")
    document = json.loads(out)
    assert code == 0 and list(document) == ["command", "sections"] and list(document["sections"]) == SECTION_NAMES
    assert all(list(section) == ["title", "lines", "data"] for section in document["sections"].values())
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE, "--json")
    assert list(json.loads(out)) == ["command", "milestone", "status", "plan", "tree", "signoffs", "criteria", "manual", "paused_tasks", "paused_items", "open_items", "items_not_executed", "proof_owed_later", "warnings", "close_gate"]


def test_status_prints_w350(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = plan_host(tmp_path)
    monkeypatch.setattr(status_module, "submodule_warnings", lambda git_root: [status_module.SpecError(code="W350", message="submodule 'lib' has uncommitted content that the code tree does not see; commit it in the submodule and update the pointer here")])
    code, out, _ = cli_run(host, "status")
    assert code == 0 and "W350 submodule 'lib' has uncommitted content" in out
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE)
    assert "W350 submodule 'lib'" in out


def test_a_node_whose_stage_cannot_be_told_does_not_stop_the_report(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"].update(qa={"scope": "in"}))
    edit_doc(host, "12_ci_gates.json", lambda doc: doc["jobs"].append({"job_id": "job-qa-smoke", "name": "QA smoke", "realises": ["qa"]}))
    edit_doc(host, "14_roadmap.json", lambda doc: doc["milestones"][0]["tasks"][0]["acceptance_criteria"][1].update(refines=["inv-reset-token-single-use", "qa"]))
    code, out, err = cli_run(host, "status", "--milestone", MILESTONE)
    assert code == 0 and "tc-confirm-reused-token (task task-implement-password-reset-confirm): E334" in out
    assert "tc-confirm-expired-token (task task-implement-password-reset-confirm): proven" in out and "E334" in out.split("close gate (dry run)")[1]
    assert _owed_later(host) == [], "a stage that cannot be told (E334) is the gate's finding, not an owed proof"
    code, out, _ = cli_run(host, "status")
    assert code == 0 and "E334" in out


def test_status_on_a_batch_id_names_the_way_to_the_milestone(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    code, _, err = cli_run(host, "status", "--milestone", "account_recovery")
    assert code == 1 and "milestone-state --batch-id account_recovery" in err


def _stage_of_alpha(host: Path, stage: str) -> None:
    path = host / "spec" / "extras" / "verification" / "ver-alpha.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["records"][0]["stage"] = stage
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _owed_later(host: Path) -> list[str]:
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE, "--json")
    assert code == 0, out
    return json.loads(out)["proof_owed_later"]


def test_proof_owed_at_staging_or_prod_names_a_criterion_whose_staging_binding_has_no_evidence(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    assert _owed_later(host) == []  # everything is proven at dev, no later binding
    _stage_of_alpha(host, "staging")
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE)
    assert code == 0 and "proof owed at staging or prod: tc-confirm-expired-token" in out
    assert _owed_later(host) == ["tc-confirm-expired-token"]
    code, out, _ = cli_run(host, "milestone", "sign-off", MILESTONE)
    assert code == 0 and "proof owed at staging or prod: tc-confirm-expired-token" in out
    record = json.loads((host / "spec" / "extras" / "signoff" / "so-ms-account-recovery-0001.json").read_text(encoding="utf-8"))["records"][0]
    assert record["listed"]["staging_prod_proof_owed"] == ["tc-confirm-expired-token"]


def test_proof_owed_at_staging_or_prod_is_empty_when_the_staging_binding_has_staging_evidence(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    _stage_of_alpha(host, "staging")
    run(host, ["ver-alpha"], stage="staging")
    assert _owed_later(host) == []
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE)
    assert "proof owed at staging or prod: none" in out


def test_proof_owed_at_staging_or_prod_is_empty_for_a_criterion_unproven_at_dev_with_no_later_binding(tmp_path: Path) -> None:
    host = plan_host(tmp_path, bindings=(alpha_binding(),))  # bound at dev, never run: unproven at dev, nothing at staging or prod
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE)
    assert code == 0 and "tc-confirm-expired-token (task task-implement-password-reset-confirm): unproven" in out
    assert _owed_later(host) == []
    assert "proof owed at staging or prod: none" in out


def test_proof_owed_at_staging_or_prod_is_empty_for_a_criterion_with_no_binding(tmp_path: Path) -> None:
    host = plan_host(tmp_path)  # unbound: the gate says E811, nothing is owed LATER
    assert _owed_later(host) == []


def test_status_milestone_for_a_milestone_with_a_plan_and_no_anchor_row_is_e800(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    edit_doc(host, "16_impl_context.json", lambda document: document["plan"].update(milestone_index=[]))
    code, out, err = cli_run(host, "status", "--milestone", MILESTONE)
    assert code == 1 and out == "" and err.startswith("E800") and "pending" not in err
    start_code, _, start_err = cli_run(host, "milestone", "start", MILESTONE)
    assert start_code == 1 and start_err == err  # the same refusal as the commands that write
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE, "--json")
    assert code == 1 and "E800" in out and "pending" not in out


def test_milestone_view_does_not_count_an_item_of_only_paused_criteria_as_not_executed(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    edit_doc(host, PLAN, lambda document: document["plan"]["spec_alignment"]["checklist"][0]["implementation"]["actions"].append({"id": "a02", "type": "file_edit", "description": "More.", "target": "src/hello.txt"}))
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE)
    assert code == 0 and "plan items not executed: 1 (PWRESET_CONFIRM_EXPIRED_01)" in out
    edit_doc(host, "14_roadmap.json", lambda document: document["milestones"][0]["tasks"][0].update(disposition={"value": "deferred", "reason": "waits for the mail relay"}))
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE)
    assert code == 0 and "plan items not executed: 0" in out
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE, "--json")
    assert json.loads(out)["items_not_executed"] == []


def test_a_milestone_whose_review_says_needs_work_is_not_awaiting_sign_off(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    assert _sections(host)["awaiting_signoff"].data == [MILESTONE]
    for verdict in ("needs_work", "blocked", "deferred"):
        edit_doc(host, PLAN, lambda document, verdict=verdict: document["review"].update(verdict=verdict))
        assert _sections(host)["awaiting_signoff"].data == [] and _sections(host)["awaiting_signoff"].lines == ("none",)


def test_the_open_items_of_a_closed_plan_are_left_out_by_status_as_by_spec_check(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    edit_doc(host, PLAN, lambda document: document["plan"].update(ambiguities=[unified_item("amb-token-store", about=["tc-confirm-expired-token"])]))

    def listed() -> tuple[dict[str, Any], list[str]]:
        code, out, _ = cli_run(host, "status", "--milestone", MILESTONE, "--json")
        return _sections(host)["open_items"].data, json.loads(out)["open_items"]

    assert listed() == ({"step:16a": ["amb-token-store"]}, ["amb-token-store"])
    code, _, err = cli_run(host, "milestone", "close", MILESTONE, "--check")
    assert code != 0 and "E632" in err
    closed_row(host)
    assert listed() == ({}, [])
    assert _sections(host)["open_items"].lines == ("none",)


def test_status_milestone_of_a_done_row_runs_no_close_gate_and_says_nothing_of_the_code_of_now(tmp_path: Path) -> None:
    """Ruling L33: a closed milestone stays closed; the dry run of the gate is for a milestone that can still close."""
    host = ready_host(tmp_path)
    closed_row(host)
    edit_doc(host, PLAN, lambda document: document["plan"].update(ambiguities=[unified_item("amb-token-store", about=["tc-confirm-expired-token"])]))
    code, out, err = cli_run(host, "status", "--milestone", MILESTONE)
    assert code == 0, err
    assert f"milestone {MILESTONE}: done" in out and "open items: 0" in out and "close gate" not in out and "E632" not in out
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE, "--json")
    document = json.loads(out)
    assert code == 0 and document["status"] == "done" and document["close_gate"] is None and document["open_items"] == []
    (host / "src" / "after_the_close.py").write_text("# a later commit\n", encoding="utf-8")
    commit_all(host, "code after the close")
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE)
    assert code == 0 and "close gate" not in out and "E811" not in out and "STALE_TREE" not in out


@pytest.mark.parametrize("status", ["in_progress", "deferred"])
def test_status_milestone_of_a_row_that_can_still_close_keeps_the_dry_run(tmp_path: Path, status: str) -> None:
    host = ready_host(tmp_path)
    if status == "deferred":
        set_row(host, "deferred", deferral_reason="waits")
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE)
    assert code == 0 and f"milestone {MILESTONE}: {status}" in out and "close gate (dry run):" in out
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE, "--json")
    assert set(json.loads(out)["close_gate"]) == {"passes", "errors", "notes"}


def test_a_legacy_item_with_status_resolved_is_not_listed_by_status(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    legacy = {"id": "amb-old-open", "description": "an old question", "severity": "medium", "status": "open", "impact": "none"}
    edit_doc(host, PLAN, lambda document: document["plan"].update(ambiguities=[legacy, {**legacy, "id": "amb-old-resolved", "status": "resolved"}]))
    assert _sections(host)["open_items"].data == {"step:16a": ["amb-old-open"]}
    code, out, _ = cli_run(host, "status", "--milestone", MILESTONE, "--json")
    assert code == 0 and json.loads(out)["open_items"] == ["amb-old-open"]
