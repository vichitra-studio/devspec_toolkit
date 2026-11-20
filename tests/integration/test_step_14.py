import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

from specdev_tools.validation.validate import validate_file
from unit.graph._synth import accept_links, graph_check

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "step_14"

# The worked example of the spec-graph design (roadmap milestone, task and task criteria, "New" form).
_DOC_EXAMPLE_MILESTONE: dict[str, Any] = {
    "milestone_id": "ms-account-recovery",
    "name": "Account Recovery",
    "target_date": "2026-12-15",
    "user_story": "As a registered member, I want to reset a forgotten password so that I can get back in without support.",
    "tasks": [
        {
            "task_id": "task-implement-password-reset-confirm",
            "description": "Implement the confirm endpoint that redeems a reset token and sets the new password.",
            "acceptance_criteria": [
                {
                    "criterion_id": "tc-confirm-expired-token",
                    "text": (
                        "POST /v1/password-resets/{token} with a token issued 31 minutes earlier returns HTTP 410 "
                        "with error token-expired and leaves the password hash unchanged."
                    ),
                    "refines": ["ac-password-reset-3"],
                    "verified_by": ["fix-password-reset-expired-token"],
                },
                {
                    "criterion_id": "tc-confirm-reused-token",
                    "text": "A second redemption of a token that already changed the password returns HTTP 410, even within 30 minutes.",
                    "refines": ["inv-reset-token-single-use"],
                    "verified_by": ["fix-password-reset-reused-token"],
                },
            ],
        }
    ],
}

_TEMP_NAME = "14_tmp_roadmap.json"


class Step14IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = _REPO_ROOT
        self.fixtures_dir = _FIXTURES

    def _errors(self, mutate: Callable[[dict], None]) -> list[Any]:
        """Validation errors for the valid fixture with the design-doc milestone, after ``mutate`` edits the copy."""
        spec = json.loads((self.fixtures_dir / "valid_roadmap.json").read_text(encoding="utf-8"))
        spec["milestones"] = [copy.deepcopy(_DOC_EXAMPLE_MILESTONE)]
        mutate(spec)
        tmp_path = self.fixtures_dir / _TEMP_NAME
        try:
            tmp_path.write_text(json.dumps(spec), encoding="utf-8")
            return validate_file(str(self.repo_root), str(tmp_path))
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def _assert_fails_naming(self, mutate: Callable[[dict], None], needle: str) -> None:
        rendered = [e.render() for e in self._errors(mutate)]
        self.assertTrue(any(needle in msg for msg in rendered), rendered)

    def test_doc_example_validates(self):
        self.assertEqual([], [e.render() for e in self._errors(lambda spec: None) if e.code == "E520"])

    def test_task_criterion_without_refines_or_removes_rejected(self):
        def drop_refines(spec: dict) -> None:
            spec["milestones"][0]["tasks"][0]["acceptance_criteria"][0].pop("refines")

        self._assert_fails_naming(drop_refines, "acceptance_criteria/0")

    def test_removes_criterion_without_refines_accepted(self):
        def removes_only(spec: dict) -> None:
            criterion = spec["milestones"][0]["tasks"][0]["acceptance_criteria"][0]
            criterion.pop("refines")
            criterion["removes"] = ["api-legacy-password-reset"]

        self.assertEqual([], [e for e in self._errors(removes_only) if e.code == "E520"])

    def test_task_deferred_without_reason_rejected(self):
        def deferred_no_reason(spec: dict) -> None:
            spec["milestones"][0]["tasks"][0]["disposition"] = {"value": "deferred"}

        self._assert_fails_naming(deferred_no_reason, "reason")

    def test_task_deferred_with_reason_accepted(self):
        def deferred(spec: dict) -> None:
            spec["milestones"][0]["tasks"][0]["disposition"] = {
                "value": "deferred",
                "reason": "Blocked on vendor API access; resume once sandbox credentials are granted.",
            }

        self.assertEqual([], [e for e in self._errors(deferred) if e.code == "E520"])

    def test_no_status_property_on_milestone_or_task(self):
        self._assert_fails_naming(lambda spec: spec["milestones"][0].update(status="pending"), "status")
        self._assert_fails_naming(lambda spec: spec["milestones"][0]["tasks"][0].update(status="pending"), "status")
        self._assert_fails_naming(lambda spec: spec["milestones"][0]["tasks"][0].update(status_reason="r"), "status_reason")

    def test_removed_fields_are_rejected(self):
        for field, value in (("tech_stack", {}), ("dependencies", []), ("trace", [])):
            with self.subTest(field=field):
                self._assert_fails_naming(lambda spec, f=field, v=value: spec.update({f: v}), field)
        for field in ("fr_refs", "capability_refs", "source_milestones", "deliverables"):
            with self.subTest(field=field):
                self._assert_fails_naming(lambda spec, f=field: spec["milestones"][0].update({f: []}), field)
        for field in ("assumptions", "exit_conditions", "fr_refs", "invariant_refs"):
            with self.subTest(field=field):
                self._assert_fails_naming(lambda spec, f=field: spec["milestones"][0]["tasks"][0].update({f: []}), field)

    def test_fixture_ref_is_replaced_by_verified_by(self):
        def old_name(spec: dict) -> None:
            spec["milestones"][0]["tasks"][0]["acceptance_criteria"][0]["fixture_ref"] = "fix-x"

        self._assert_fails_naming(old_name, "fixture_ref")

    def test_valid_roadmap_fixtures_pass_schema_validation(self):
        for name in (
            "valid_roadmap.json",
            "valid_roadmap_migration.json",
            "valid_roadmap_with_refs.json",
            "valid_refines_invariant.json",
        ):
            errors = validate_file(str(self.repo_root), str(self.fixtures_dir / name))
            self.assertEqual([], errors, msg=f"{name} failed validation: {errors}")

    def test_invalid_roadmap_fixtures_fail_validation(self):
        for name in (
            "invalid_date_order.json",
            "invalid_missing_target_date.json",
            "invalid_missing_refines.json",
            "invalid_disposition_value.json",
            "invalid_disposition_without_reason.json",
            "invalid_risk_status_enum.json",
            "invalid_task_acceptance_criteria.json",
        ):
            errors = validate_file(str(self.repo_root), str(self.fixtures_dir / name))
            self.assertTrue(errors, msg=f"{name} unexpectedly passed validation")

    def test_milestones_are_in_chronological_order_for_valid_fixture(self):
        data = json.loads((self.fixtures_dir / "valid_roadmap.json").read_text(encoding="utf-8"))
        dates = [m.get("target_date") for m in data.get("milestones", [])]
        self.assertEqual(sorted(dates), dates, msg="Milestones are not in chronological order")

    def _as_step_14_file(self, fixture: str, folder: str) -> Path:
        """Copy *fixture* to ``<folder>/14_roadmap.json``, the name the registry knows."""
        target = Path(folder) / "14_roadmap.json"
        shutil.copyfile(self.fixtures_dir / fixture, target)
        return target

    def test_invalid_depends_on_cycle(self):
        """A task cycle is E703 from ``spec-check``, owned by step 14; the single-file validator no longer reports it."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._as_step_14_file("invalid_depends_on_cycle.json", tmp)
            self.assertEqual([], validate_file(str(self.repo_root), str(path)))
            graph = graph_check(accept_links(Path(tmp)))
        self.assertEqual("FAIL", graph["status"])
        self.assertEqual([("E703", "step:14")], [(f["code"], f["owner"]) for f in graph["findings"]])
        for task in ("task-a", "task-b", "task-c"):
            self.assertIn(task, graph["findings"][0]["message"])

    def test_invalid_task_format_duplicate_task_id_is_e704(self):
        """The fixture repeats a task id: the one-file id check of ``validate`` reports it as E704."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._as_step_14_file("invalid_task_format.json", tmp)
            errors = validate_file(str(self.repo_root), str(path))
        self.assertEqual([("E704", "step:14", "setup-health-check")], [(e.code, e.owner, e.node_id) for e in errors])

    def test_valid_roadmap_with_refs(self):
        errors = validate_file(str(self.repo_root), str(self.fixtures_dir / "valid_roadmap_with_refs.json"))
        self.assertEqual([], errors, f"valid_roadmap_with_refs.json should pass validation. Errors: {errors}")

    def test_no_cross_step_check_on_upstream_ids(self):
        """No sibling artifact is read: a roadmap whose criteria refine unknown ids and sit beside no 09/04/01 passes."""
        errors = validate_file(str(self.repo_root), str(self.fixtures_dir / "valid_roadmap.json"))
        self.assertEqual([], [e for e in errors if e.code in {"E590", "W590", "E142"}])



# --- the milestone numbers (E566, E567): the graph check ``milestone-numbers`` ---------------------------------------------


FR_REQUEST = "fr-password-reset-request"
AC_REQUEST = "ac-password-reset-request-1"
DESIGN_MILESTONE = "milestone-account-recovery"


def _milestone_numbers(spec: Path) -> list[Any]:
    from specdev_tools.validation.graph_checks.context import MERGE
    from specdev_tools.validation.validators.step_14_milestones import check_milestone_numbers
    from unit.validation.graph_checks._example_support import context_of_spec

    return check_milestone_numbers(context_of_spec(spec), MERGE)


def _found(findings: list[Any], code: str) -> list[str]:
    return [finding.node_id for finding in findings if finding.code == code]


def _example(tmp_path: Path, **edits: Any) -> Path:
    from unit.validation.graph_checks._example_support import edited_example

    return edited_example(tmp_path / "spec", **edits)


def _add_fr(document: dict[str, Any]) -> None:
    fr = copy.deepcopy(document["functional_requirements"][1])
    fr["fr_id"] = "fr-extra"
    fr["acceptance_criteria"] = [{"criterion_id": "ac-extra-1", "scope": "in", "text": "Given an extra requirement, then something is done."}]
    document["functional_requirements"].append(fr)


def _schedule_request(document: dict[str, Any]) -> None:
    document["milestones"][0]["schedules"].append(FR_REQUEST)


def _refine_request(document: dict[str, Any]) -> None:
    document["milestones"][0]["tasks"][0]["acceptance_criteria"].append(
        {"criterion_id": "tc-request-sends-link", "text": "A reset request sends one email.", "refines": [AC_REQUEST], "verified_by": ["fix-password-reset-expired-token"]}
    )


def test_in_scope_fr_without_a_reachable_criterion_gives_e566(tmp_path: Path) -> None:
    findings = _milestone_numbers(_example(tmp_path, **{"04_fr_list.json": _add_fr}))
    assert "fr-extra" in _found(findings, "E566")
    finding = next(f for f in findings if f.node_id == "fr-extra")
    assert (finding.owner, finding.file) == ("step:14", "04_fr_list.json")
    assert "fr-password-reset" not in _found(findings, "E566")  # refined through its acceptance criterion


def test_fr_covered_through_an_api_that_derives_from_it_gives_no_e566(tmp_path: Path) -> None:
    def derive(document: dict[str, Any]) -> None:
        api = next(a for a in document["apis"] if a.get("api_id") == "api-password-reset-confirm")
        api.setdefault("derives_from", []).append(FR_REQUEST)

    def refine_api(document: dict[str, Any]) -> None:
        document["milestones"][0]["tasks"][0]["acceptance_criteria"][0]["refines"].append("api-password-reset-confirm")

    spec = _example(tmp_path)
    assert FR_REQUEST in _found(_milestone_numbers(spec), "E566")
    from unit.validation.graph_checks._example_support import edit_documents

    edit_documents(spec, **{"05_interface_contracts.json": derive, "14_roadmap.json": refine_api})
    assert FR_REQUEST not in _found(_milestone_numbers(spec), "E566")


def _task_criterion_refining(target: str) -> Callable[[dict[str, Any]], None]:
    def refine(document: dict[str, Any]) -> None:
        document["milestones"][0]["tasks"][0]["acceptance_criteria"].append(
            {"criterion_id": "tc-extra", "text": "An extra thing is done.", "refines": [target], "verified_by": ["fix-password-reset-expired-token"]}
        )

    return refine


def test_the_e566_message_says_how_to_clear_it(tmp_path: Path) -> None:
    finding = next(f for f in _milestone_numbers(_example(tmp_path)) if f.code == "E566" and f.node_id == FR_REQUEST)
    assert f"fr {FR_REQUEST} is in scope but no task criterion reaches it" in finding.message
    assert "add a task criterion that refines it, one of its acceptance criteria or a node derived from it" in finding.message
    assert "or set its scope to later or out with a scope_reason" in finding.message


def test_a_task_criterion_that_refines_an_out_of_play_criterion_of_an_fr_does_not_reach_it(tmp_path: Path) -> None:
    def park_criterion(document: dict[str, Any]) -> None:
        fr = next(f for f in document["functional_requirements"] if f["fr_id"] == FR_REQUEST)
        criterion = next(c for c in fr["acceptance_criteria"] if c["criterion_id"] == AC_REQUEST)
        criterion.update(scope="out", scope_reason="Dropped from this release.")

    spec = _example(tmp_path, **{"04_fr_list.json": park_criterion, "14_roadmap.json": _refine_request})
    assert FR_REQUEST in _found(_milestone_numbers(spec), "E566")


def test_fr_reached_through_a_node_linked_by_realises_gives_no_e566(tmp_path: Path) -> None:
    """FR <- api (derives_from) <- scaffold row (realises) <- task criterion (refines)."""
    def derive(document: dict[str, Any]) -> None:
        api = next(a for a in document["apis"] if a.get("api_id") == "api-password-reset-confirm")
        api.setdefault("derives_from", []).append(FR_REQUEST)

    spec = _example(tmp_path, **{"05_interface_contracts.json": derive})
    assert FR_REQUEST in _found(_milestone_numbers(spec), "E566")
    from unit.validation.graph_checks._example_support import edit_documents

    edit_documents(spec, **{"14_roadmap.json": _task_criterion_refining("scaffold-password-reset-confirm")})
    assert FR_REQUEST not in _found(_milestone_numbers(spec), "E566")


def test_fr_reached_through_a_node_linked_by_mitigated_by_gives_no_e566(tmp_path: Path) -> None:
    """FR <- threat (mitigated_by) <- task criterion (refines)."""
    def mitigate(document: dict[str, Any]) -> None:
        document["threats"][0]["mitigated_by"].append(FR_REQUEST)

    spec = _example(tmp_path, **{"11_redteam.json": mitigate})
    assert FR_REQUEST in _found(_milestone_numbers(spec), "E566")
    from unit.validation.graph_checks._example_support import edit_documents

    edit_documents(spec, **{"14_roadmap.json": _task_criterion_refining("threat-reset-token-replay")})
    assert FR_REQUEST not in _found(_milestone_numbers(spec), "E566")


def test_fr_with_scope_later_gives_no_e566(tmp_path: Path) -> None:
    def park(document: dict[str, Any]) -> None:
        _add_fr(document)
        document["functional_requirements"][-1].update(scope="later", scope_reason="Deferred to the next release.")

    findings = _milestone_numbers(_example(tmp_path, **{"04_fr_list.json": park}))
    assert "fr-extra" not in _found(findings, "E566")


def test_scheduled_obligation_no_criterion_refines_gives_e567(tmp_path: Path) -> None:
    findings = _milestone_numbers(_example(tmp_path, **{"09_impl_plan.json": _schedule_request}))
    e567 = [f for f in findings if f.code == "E567"]
    assert [(f.node_id, f.target, f.owner, f.file) for f in e567] == [(DESIGN_MILESTONE, FR_REQUEST, "step:14", "09_impl_plan.json")]
    assert "add a task criterion that refines it" in e567[0].message and f"remove it from the schedules of {DESIGN_MILESTONE}" in e567[0].message


def test_every_scheduled_obligation_refined_gives_no_e567(tmp_path: Path) -> None:
    """The unchanged example has none; a scheduled FR whose acceptance criterion a task criterion refines gives none either."""
    assert _found(_milestone_numbers(_example(tmp_path)), "E567") == []
    spec = _example(tmp_path / "refined", **{"09_impl_plan.json": _schedule_request, "14_roadmap.json": _refine_request})
    findings = _milestone_numbers(spec)
    assert _found(findings, "E567") == [] and FR_REQUEST not in _found(findings, "E566")


def test_design_milestone_without_a_matching_roadmap_milestone_gives_no_e567(tmp_path: Path) -> None:
    def second_milestone(document: dict[str, Any]) -> None:
        document["milestones"].append({"milestone_id": "milestone-nothing-built", "name": "Nothing built", "schedules": [FR_REQUEST]})

    findings = _milestone_numbers(_example(tmp_path, **{"09_impl_plan.json": second_milestone}))
    assert _found(findings, "E567") == []


def test_a_scheduled_node_with_scope_later_gives_no_e567(tmp_path: Path) -> None:
    def park(document: dict[str, Any]) -> None:
        fr = next(f for f in document["functional_requirements"] if f["fr_id"] == FR_REQUEST)
        fr.update(scope="later", scope_reason="Deferred to the next release.")

    findings = _milestone_numbers(_example(tmp_path, **{"04_fr_list.json": park, "09_impl_plan.json": _schedule_request}))
    assert _found(findings, "E567") == []


def test_milestone_with_no_tasks_gives_neither(tmp_path: Path) -> None:
    def empty_milestone(document: dict[str, Any]) -> None:
        document["milestones"].append({"milestone_id": "ms-empty", "name": "Empty", "target_date": "2027-01-15", "user_story": "As a member, nothing yet.", "tasks": []})

    before = [(f.code, f.node_id) for f in _milestone_numbers(_example(tmp_path / "a"))]
    after = [(f.code, f.node_id) for f in _milestone_numbers(_example(tmp_path / "b", **{"14_roadmap.json": empty_milestone}))]
    assert after == before


def test_milestone_checks_skip_without_graph() -> None:
    """``spec-check`` runs the check under its registered name and the check skips, with the reason of every graph check, when no graph could be built."""
    from types import SimpleNamespace

    from specdev_tools.validation.check_registry import CHECK_REGISTRY
    from specdev_tools.validation.graph_checks.context import GRAPH_NOT_BUILT
    from specdev_tools.validation.spec_check import run_spec_check_json  # noqa: F401  (importing it fills CHECK_REGISTRY)

    registered = {spec.name: spec.fn for spec in CHECK_REGISTRY}
    result = registered["milestone-numbers"](SimpleNamespace(check_graph=None))
    assert result["status"] == "SKIP" and GRAPH_NOT_BUILT in json.dumps(result)


def test_milestone_count_in_step_09_changes_the_result_and_in_another_step_does_not(tmp_path: Path) -> None:
    """Adding a step 09 milestone that a task criterion computes and that schedules something unrefined adds E567; adding a step 14 milestone without tasks changes nothing."""
    def unrefined_milestone(document: dict[str, Any]) -> None:
        document["milestones"].append({"milestone_id": "milestone-second", "name": "Second", "schedules": ["fr-password-reset", FR_REQUEST]})

    def empty_milestone(document: dict[str, Any]) -> None:
        document["milestones"].append({"milestone_id": "ms-empty", "name": "Empty", "target_date": "2027-01-15", "user_story": "As a member, nothing yet.", "tasks": []})

    base = [(f.code, f.node_id, f.target) for f in _milestone_numbers(_example(tmp_path / "base"))]
    in_09 = [(f.code, f.node_id, f.target) for f in _milestone_numbers(_example(tmp_path / "s09", **{"09_impl_plan.json": unrefined_milestone}))]
    in_14 = [(f.code, f.node_id, f.target) for f in _milestone_numbers(_example(tmp_path / "s14", **{"14_roadmap.json": empty_milestone}))]
    assert in_09 == [*base, ("E567", "milestone-second", FR_REQUEST)]
    assert in_14 == base


if __name__ == "__main__":
    unittest.main()
