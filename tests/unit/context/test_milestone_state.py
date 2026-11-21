"""Unit tests for tools/specdev_tools/context/milestone_state.py.

Covers:
- Per-group state derivation: pending, code_converged, blocked, deferred, wont_do
- ``deferred`` / ``wont_do`` read from the ``disposition`` of the tasks a plan item realises, ``blocked`` from an open
  item about a node on the item's chain, ``closed`` from the anchor row (the spec graph is the worked example)
- Derived phase position transitions: pending, impl_in_progress, impl_complete,
  review_pending, review_complete, operator_pending, closed
- Findings-file logic: per-reviewer, round-output and halt-archive shapes; a non-dict file is skipped
- The module reads neither ``checklist_status`` nor ``implementation.status``

Findings probes use pytest ``tmp_path`` folders with a synthetic ``.specdev/findings/``; the spec side is a copy of
the worked example under ``tmp_path``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from specdev_tools.context import milestone_state
from specdev_tools.context.milestone_state import (
    ItemView,
    SpecView,
    compute_milestone_state,
    derive_group_state,
    derive_phase_position,
    load_spec_view,
)
from unit.graph._synth import run_cli
from unit.lifecycle._support import ANCHOR, edit_row, example_spec, load, toolkit_root

ITEM = "PWRESET_CONFIRM_EXPIRED_01"
PLAN = "impl_context/ms_account_recovery_plan.json"
ROADMAP = "14_roadmap.json"
EXPIRED_CRITERION = "tc-confirm-expired-token"
REUSED_CRITERION = "tc-confirm-reused-token"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _findings_dir(tmp_path: Path) -> Path:
    path = tmp_path / ".specdev" / "findings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_findings(findings_dir: Path, filename: str, findings: list) -> Path:
    """Write a synthetic findings file and return its path."""
    path = findings_dir / filename
    path.write_text(
        json.dumps({"round": 1, "scope": "test-scope", "generated_at": 1700000000, "findings": findings}), encoding="utf-8"
    )
    return path


def _group(group_id: str = "G1") -> dict:
    return {"id": group_id, "realises": ["tc-x"]}


def _converge(findings_dir: Path, group_id: str) -> None:
    _write_findings(findings_dir, f"findings_{group_id}_1.json", [])


def _state_of(group: dict, findings_dir: Path, ambiguities: list[dict] | None = None, view: ItemView = ItemView()) -> dict:
    return derive_group_state(group, str(findings_dir), ambiguities or [], view)


def _group_state(group_id: str, state: str, blocking: list[str] | None = None) -> dict:
    return {
        "group_id": group_id,
        "state": state,
        "implementation_converged_at": None,
        "reviewer_rounds": 0,
        "findings_resolved_path": None,
        "blocking_amb_ids": blocking or [],
    }


def _plan(spec: Path) -> dict:
    return load(spec, PLAN)


def _edit_plan(spec: Path, edit) -> None:
    document = load(spec, PLAN)
    edit(document)
    (spec / PLAN).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _set_disposition(spec: Path, value: str) -> None:
    document = load(spec, ROADMAP)
    document["milestones"][0]["tasks"][0]["disposition"] = {"value": value, "reason": "Set aside for the test."}
    (spec / ROADMAP).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _state_from_spec(spec: Path, tmp_path: Path) -> dict:
    """The one group of the example plan, derived through ``compute_milestone_state`` with the view of *spec*."""
    plan = _plan(spec)
    view = load_spec_view(plan, str(spec), toolkit_root())
    return compute_milestone_state(plan, str(_findings_dir(tmp_path)), "account_recovery", view)


# ---------------------------------------------------------------------------
# Per-group state from findings
# ---------------------------------------------------------------------------

class TestGroupStateFromFindings:
    def test_no_findings_dir(self, tmp_path: Path) -> None:
        state = derive_group_state(_group(), str(tmp_path / "missing"), [])
        assert state["state"] == "pending"
        assert state["findings_resolved_path"] is None

    def test_only_reviewer_files_not_empty(self, tmp_path: Path) -> None:
        findings_dir = _findings_dir(tmp_path)
        _write_findings(findings_dir, "findings_G1_1_r1.json", [{"kind": "gap"}])
        state = _state_of(_group(), findings_dir)
        assert (state["state"], state["reviewer_rounds"]) == ("pending", 1)

    def test_round_output_with_findings_is_pending(self, tmp_path: Path) -> None:
        findings_dir = _findings_dir(tmp_path)
        _write_findings(findings_dir, "findings_G1_1.json", [{"kind": "gap"}])
        assert _state_of(_group(), findings_dir)["state"] == "pending"

    def test_empty_round_output_is_code_converged(self, tmp_path: Path) -> None:
        findings_dir = _findings_dir(tmp_path)
        path = _write_findings(findings_dir, "findings_G1_1.json", [])
        state = _state_of(_group(), findings_dir)
        assert state["state"] == "code_converged"
        assert state["findings_resolved_path"] == str(path)
        assert state["implementation_converged_at"] is not None

    @pytest.mark.parametrize("name", ["findings_G1_2_r1.json", "findings_G1_2_rr3.json"])
    def test_empty_reviewer_file_is_code_converged(self, tmp_path: Path, name: str) -> None:
        findings_dir = _findings_dir(tmp_path)
        _write_findings(findings_dir, name, [])
        state = _state_of(_group(), findings_dir)
        assert (state["state"], state["reviewer_rounds"]) == ("code_converged", 1)

    def test_findings_file_logic_is_unchanged(self, tmp_path: Path) -> None:
        """Halt archives and fixer files never converge a group; a non-dict file is skipped; only the group's own files count."""
        findings_dir = _findings_dir(tmp_path)
        _write_findings(findings_dir, "findings_G1_5_1700000000.json", [])
        _write_findings(findings_dir, "findings_G1_1_r1_fixer-discovered.json", [])
        _write_findings(findings_dir, "findings_G2_1.json", [])
        (findings_dir / "findings_G1_2.json").write_text("[]", encoding="utf-8")
        assert _state_of(_group(), findings_dir)["state"] == "pending"
        _write_findings(findings_dir, "findings_G1_3.json", [])
        assert _state_of(_group(), findings_dir)["state"] == "code_converged"


# ---------------------------------------------------------------------------
# Per-group state from the item view (no graph needed)
# ---------------------------------------------------------------------------

class TestGroupStateFromView:
    def test_set_aside_outranks_converged_findings(self, tmp_path: Path) -> None:
        findings_dir = _findings_dir(tmp_path)
        _converge(findings_dir, "G1")
        for set_aside in ("deferred", "wont_do"):
            assert _state_of(_group(), findings_dir, view=ItemView(set_aside=set_aside))["state"] == set_aside

    def test_open_item_on_the_chain_blocks_a_converged_group(self, tmp_path: Path) -> None:
        findings_dir = _findings_dir(tmp_path)
        _converge(findings_dir, "G1")
        ambiguities = [{"id": "amb-one", "description": "d", "about": ["node-a", "node-b"]}]
        state = _state_of(_group(), findings_dir, ambiguities, ItemView(chain=frozenset({"node-b"})))
        assert (state["state"], state["blocking_amb_ids"]) == ("blocked", ["amb-one"])

    def test_open_item_on_the_chain_does_not_block_an_unconverged_group(self, tmp_path: Path) -> None:
        state = _state_of(_group(), _findings_dir(tmp_path), [{"id": "amb-one", "about": ["node-a"]}], ItemView(chain=frozenset({"node-a"})))
        assert (state["state"], state["blocking_amb_ids"]) == ("pending", ["amb-one"])

    def test_items_that_are_not_objects_or_have_no_id_are_skipped(self, tmp_path: Path) -> None:
        findings_dir = _findings_dir(tmp_path)
        _converge(findings_dir, "G1")
        state = _state_of(_group(), findings_dir, ["x", {"about": ["node-a"]}, {"id": 3, "about": ["node-a"]}], ItemView(chain=frozenset({"node-a"})))
        assert (state["state"], state["blocking_amb_ids"]) == ("code_converged", [])


# ---------------------------------------------------------------------------
# State read through the spec graph (the worked example)
# ---------------------------------------------------------------------------

class TestSpecView:
    def test_group_is_deferred_when_every_realised_criterion_is_deferred(self, tmp_path: Path) -> None:
        spec = example_spec(tmp_path)
        _set_disposition(spec, "deferred")
        assert _state_from_spec(spec, tmp_path)["groups"][0]["state"] == "deferred"

    def test_group_is_wont_do_when_every_realised_criterion_is_wont_do(self, tmp_path: Path) -> None:
        spec = example_spec(tmp_path)
        _set_disposition(spec, "wont_do")
        assert _state_from_spec(spec, tmp_path)["groups"][0]["state"] == "wont_do"

    def test_group_with_one_task_still_planned_is_not_set_aside(self, tmp_path: Path) -> None:
        """An item realising criteria of two tasks, only one of them deferred, stays active."""
        spec = example_spec(tmp_path)
        roadmap = load(spec, ROADMAP)
        task = roadmap["milestones"][0]["tasks"][0]
        second = {"task_id": "task-second", "description": "d", "acceptance_criteria": [{"criterion_id": "tc-second", "text": "t"}]}
        task["disposition"] = {"value": "deferred", "reason": "later"}
        roadmap["milestones"][0]["tasks"].append(second)
        (spec / ROADMAP).write_text(json.dumps(roadmap), encoding="utf-8")
        _edit_plan(spec, lambda plan: plan["plan"]["spec_alignment"]["checklist"][0]["realises"].append("tc-second"))
        assert _state_from_spec(spec, tmp_path)["groups"][0]["state"] == "pending"

    def test_deferred_and_wont_do_tasks_together_read_as_deferred(self, tmp_path: Path) -> None:
        spec = example_spec(tmp_path)
        roadmap = load(spec, ROADMAP)
        tasks = roadmap["milestones"][0]["tasks"]
        tasks[0]["disposition"] = {"value": "wont_do", "reason": "never"}
        tasks.append({
            "task_id": "task-second", "description": "d", "disposition": {"value": "deferred", "reason": "later"},
            "acceptance_criteria": [{"criterion_id": "tc-second", "text": "t"}],
        })
        (spec / ROADMAP).write_text(json.dumps(roadmap), encoding="utf-8")
        _edit_plan(spec, lambda plan: plan["plan"]["spec_alignment"]["checklist"][0]["realises"].append("tc-second"))
        assert _state_from_spec(spec, tmp_path)["groups"][0]["state"] == "deferred"

    def test_group_is_blocked_by_an_open_item_about_a_node_on_its_chain(self, tmp_path: Path) -> None:
        spec = example_spec(tmp_path)
        _edit_plan(spec, lambda plan: plan["plan"].update(
            ambiguities=[{"id": "amb-clock", "description": "Which clock decides expiry?", "about": [EXPIRED_CRITERION]}]
        ))
        _converge(_findings_dir(tmp_path), ITEM)
        result = _state_from_spec(spec, tmp_path)
        group = result["groups"][0]
        assert (group["state"], group["blocking_amb_ids"]) == ("blocked", ["amb-clock"])
        assert result["blockers"] == [{"kind": "ambiguity", "id": "amb-clock", "issue": f"open ambiguity about a node of group {ITEM}"}]
        assert result["derived_phase_position"] == "impl_complete"

    def test_open_item_in_the_execution_block_counts_too(self, tmp_path: Path) -> None:
        spec = example_spec(tmp_path)
        _edit_plan(spec, lambda plan: plan.update(
            execution={"emergent_ambiguities": [{"id": "amb-emergent", "description": "d", "about": ["fix-password-reset-expired-token"]}]}
        ))
        _converge(_findings_dir(tmp_path), ITEM)
        assert _state_from_spec(spec, tmp_path)["groups"][0]["blocking_amb_ids"] == ["amb-emergent"]

    def test_group_is_blocked_by_an_open_item_about_the_plan_item_itself(self, tmp_path: Path) -> None:
        spec = example_spec(tmp_path)
        _edit_plan(spec, lambda plan: plan["plan"].update(ambiguities=[{"id": "amb-self", "description": "d", "about": [ITEM]}]))
        assert _state_from_spec(spec, tmp_path)["groups"][0]["blocking_amb_ids"] == ["amb-self"]

    def test_open_item_about_an_unrelated_node_blocks_no_group(self, tmp_path: Path) -> None:
        """An item about the other criterion of the roadmap, which the plan item does not realise, blocks nothing."""
        spec = example_spec(tmp_path)
        _edit_plan(spec, lambda plan: plan["plan"].update(
            ambiguities=[{"id": "amb-other", "description": "d", "about": [REUSED_CRITERION]}]
        ))
        _converge(_findings_dir(tmp_path), ITEM)
        result = _state_from_spec(spec, tmp_path)
        assert (result["groups"][0]["state"], result["groups"][0]["blocking_amb_ids"], result["blockers"]) == ("code_converged", [], [])

    def test_open_item_blocks_only_the_group_whose_chain_it_is_on(self, tmp_path: Path) -> None:
        spec = example_spec(tmp_path)

        def second_item(plan: dict) -> None:
            checklist = plan["plan"]["spec_alignment"]["checklist"]
            checklist.append({**checklist[0], "id": "PWRESET_CONFIRM_REUSED_01", "realises": [REUSED_CRITERION]})
            plan["plan"]["ambiguities"] = [{"id": "amb-clock", "description": "d", "about": [EXPIRED_CRITERION]}]

        _edit_plan(spec, second_item)
        result = _state_from_spec(spec, tmp_path)
        assert {g["group_id"]: g["blocking_amb_ids"] for g in result["groups"]} == {ITEM: ["amb-clock"], "PWRESET_CONFIRM_REUSED_01": []}

    def test_closed_is_read_from_the_anchor_row(self, tmp_path: Path) -> None:
        spec = example_spec(tmp_path)
        assert _state_from_spec(spec, tmp_path)["derived_phase_position"] == "pending"
        edit_row(spec, lambda row: row.update(status="done", close={"signed_off_by": "someone@example.invalid"}))
        assert _state_from_spec(spec, tmp_path)["derived_phase_position"] == "closed"

    def test_closed_is_not_read_from_converged_groups(self, tmp_path: Path) -> None:
        """Every group converged and reviewed is not closed while the anchor row is not done."""
        spec = example_spec(tmp_path)
        findings_dir = _findings_dir(tmp_path)
        _converge(findings_dir, ITEM)
        _write_findings(findings_dir, "findings_account_recovery_review_1.json", [])
        assert _state_from_spec(spec, tmp_path)["derived_phase_position"] == "review_complete"

    def test_row_with_an_unknown_status_reads_as_not_closed(self, tmp_path: Path) -> None:
        spec = example_spec(tmp_path)
        edit_row(spec, lambda row: row.update(status="finished"))
        assert _state_from_spec(spec, tmp_path)["derived_phase_position"] == "pending"

    def test_no_graph_reports_no_blocked_group_and_does_not_crash(self, tmp_path: Path) -> None:
        spec = example_spec(tmp_path)
        _edit_plan(spec, lambda plan: plan["plan"].update(ambiguities=[{"id": "amb-clock", "description": "d", "about": [EXPIRED_CRITERION]}]))
        _set_disposition(spec, "deferred")
        _converge(_findings_dir(tmp_path), ITEM)
        view = load_spec_view(_plan(spec), str(spec), str(tmp_path / "no-toolkit"))
        assert view.items == {}
        result = compute_milestone_state(_plan(spec), str(_findings_dir(tmp_path)), "account_recovery", view)
        assert (result["groups"][0]["state"], result["groups"][0]["blocking_amb_ids"]) == ("code_converged", [])

    def test_plan_without_a_milestone_key_has_no_closed_view(self, tmp_path: Path) -> None:
        spec = example_spec(tmp_path)
        plan = _plan(spec)
        del plan["milestone"]
        assert load_spec_view(plan, str(spec), toolkit_root()).closed is False
        assert compute_milestone_state(plan, str(_findings_dir(tmp_path)), "account_recovery")["milestone"] is None


# ---------------------------------------------------------------------------
# Phase position
# ---------------------------------------------------------------------------

class TestDerivePhasePosition:
    @pytest.fixture
    def findings_dir(self, tmp_path: Path) -> Path:
        return _findings_dir(tmp_path)

    def _position(self, findings_dir: Path, *states: str, closed: bool = False) -> str:
        groups = [_group_state(f"G{i}", state) for i, state in enumerate(states)]
        return derive_phase_position(groups, str(findings_dir), "batch1", closed)

    @pytest.mark.parametrize(
        "states",
        [("pending", "pending"), ("deferred", "deferred"), ("wont_do",), ("deferred", "wont_do")],
    )
    def test_pending_when_every_active_group_is_pending_or_none_is_active(self, findings_dir: Path, states: tuple[str, ...]) -> None:
        assert self._position(findings_dir, *states) == "pending"

    def test_impl_in_progress_mixed(self, findings_dir: Path) -> None:
        assert self._position(findings_dir, "code_converged", "pending") == "impl_in_progress"

    def test_set_aside_group_is_excluded_from_the_roll_up(self, findings_dir: Path) -> None:
        assert self._position(findings_dir, "code_converged", "wont_do") == "impl_complete"

    def test_impl_complete_all_advanced_no_review_file(self, findings_dir: Path) -> None:
        assert self._position(findings_dir, "code_converged", "blocked") == "impl_complete"

    def test_review_pending_has_review_file_not_empty(self, findings_dir: Path) -> None:
        _write_findings(findings_dir, "findings_batch1_review_1.json", [{"kind": "gap"}])
        assert self._position(findings_dir, "code_converged") == "review_pending"

    def test_review_complete_empty_review_file(self, findings_dir: Path) -> None:
        _write_findings(findings_dir, "findings_batch1_review_1.json", [])
        assert self._position(findings_dir, "code_converged") == "review_complete"

    def test_operator_pending_blocked_group(self, findings_dir: Path) -> None:
        _write_findings(findings_dir, "findings_batch1_review_1.json", [])
        assert self._position(findings_dir, "code_converged", "blocked") == "operator_pending"

    def test_operator_pending_open_item_on_a_group(self, findings_dir: Path) -> None:
        _write_findings(findings_dir, "findings_batch1_review_1.json", [])
        groups = [_group_state("G0", "code_converged", blocking=["amb-one"])]
        assert derive_phase_position(groups, str(findings_dir), "batch1") == "operator_pending"

    @pytest.mark.parametrize("states", [("pending",), ("deferred",), ("code_converged", "blocked")])
    def test_closed_is_decided_by_the_flag_alone(self, findings_dir: Path, states: tuple[str, ...]) -> None:
        assert self._position(findings_dir, *states, closed=True) == "closed"
        assert self._position(findings_dir, *states) != "closed"


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

class TestComputeMilestoneState:
    def test_output_contract_shape(self, tmp_path: Path) -> None:
        plan = {"milestone": "ms-x", "plan": {"spec_alignment": {"checklist": [_group("G1")]}}}
        result = compute_milestone_state(plan, str(_findings_dir(tmp_path)), "batch1")
        assert list(result) == ["milestone_id", "milestone", "groups", "derived_phase_position", "blockers"]
        assert list(result["groups"][0]) == [
            "group_id", "state", "implementation_converged_at", "reviewer_rounds", "findings_resolved_path", "blocking_amb_ids",
        ]

    def test_milestone_id_echoes_the_batch_id_and_milestone_is_the_plan_key(self, tmp_path: Path) -> None:
        plan = {"id": "plan-x", "milestone": "ms-x", "plan": {"spec_alignment": {"checklist": []}}}
        result = compute_milestone_state(plan, str(_findings_dir(tmp_path)), "batch1")
        assert (result["milestone_id"], result["milestone"]) == ("batch1", "ms-x")

    def test_wrong_typed_levels_read_as_absent(self, tmp_path: Path) -> None:
        for plan in ({}, {"plan": []}, {"plan": {"spec_alignment": {"checklist": "x"}}, "execution": 3}, {"milestone": 4}):
            result = compute_milestone_state(plan, str(_findings_dir(tmp_path)), "batch1")
            assert (result["groups"], result["milestone"], result["derived_phase_position"]) == ([], None, "pending")

    def test_a_group_without_a_string_id_is_not_a_group(self, tmp_path: Path) -> None:
        plan = {"plan": {"spec_alignment": {"checklist": [{"realises": ["tc-x"]}, {"id": 4}, "x", _group("G1")]}}}
        result = compute_milestone_state(plan, str(_findings_dir(tmp_path)), "batch1")
        assert [g["group_id"] for g in result["groups"]] == ["G1"]

    def test_a_blocker_is_listed_once(self, tmp_path: Path) -> None:
        findings_dir = _findings_dir(tmp_path)
        for gid in ("G1", "G2"):
            _converge(findings_dir, gid)
        plan = {
            "plan": {"spec_alignment": {"checklist": [_group("G1"), _group("G2")]}, "ambiguities": [{"id": "amb-one", "about": ["node-a"]}]},
        }
        view = SpecView(items={gid: ItemView(chain=frozenset({"node-a"})) for gid in ("G1", "G2")})
        result = compute_milestone_state(plan, str(findings_dir), "batch1", view)
        assert [b["id"] for b in result["blockers"]] == ["amb-one"]
        assert [g["state"] for g in result["groups"]] == ["blocked", "blocked"]


def test_module_reads_neither_checklist_status_nor_implementation_status() -> None:
    source = Path(milestone_state.__file__).read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    assert not re.search(r"checklist_status|[\"']implementation[\"']\s*\)|\.get\(\s*[\"']status[\"']|impl_status", code)


def test_anchor_file_name_is_the_one_the_view_reads(tmp_path: Path) -> None:
    """The engine reads the closedness of the milestone from the anchor file of the spec folder, nowhere else."""
    spec = example_spec(tmp_path)
    (spec / ANCHOR).unlink()
    assert load_spec_view(_plan(spec), str(spec), toolkit_root()).closed is False


# ---------------------------------------------------------------------------
# Through the real command
# ---------------------------------------------------------------------------

def _run_command(spec: Path, host: Path) -> dict:
    code, out = run_cli("milestone-state", "--batch-id", "account_recovery", "--repo-root", toolkit_root(), "--spec-root", str(spec), "--git-root", str(host))
    assert code == 0, out
    return json.loads(out)


def test_command_reads_closed_blocked_and_deferred_from_the_spec(tmp_path: Path) -> None:
    """`specdev milestone-state` on a copy of the worked example: the anchor row gives `closed`, the roadmap `deferred`, an open item `blocked`."""
    spec = example_spec(tmp_path / "host")
    _converge(_findings_dir(tmp_path / "host"), ITEM)
    state = _run_command(spec, tmp_path / "host")
    assert (state["milestone"], state["groups"][0]["state"], state["derived_phase_position"]) == ("ms-account-recovery", "code_converged", "impl_complete")
    _edit_plan(spec, lambda plan: plan["plan"].update(ambiguities=[{"id": "amb-clock", "description": "d", "about": [EXPIRED_CRITERION]}]))
    assert _run_command(spec, tmp_path / "host")["groups"][0]["state"] == "blocked"
    edit_row(spec, lambda row: row.update(status="done", close={"signed_off_by": "someone@example.invalid"}))
    assert _run_command(spec, tmp_path / "host")["derived_phase_position"] == "closed"
    _set_disposition(spec, "deferred")
    assert _run_command(spec, tmp_path / "host")["groups"][0]["state"] == "deferred"
