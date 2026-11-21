"""``verify bind``: the stage of a binding, what it proves, and what is refused."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.graph.model import Graph
from specdev_tools.verify.bind import EMPTY_GUARD_NOTE, BindRequest, BindResult, apply_bind
from specdev_tools.verify.records import records_folder
from unit.graph._synth import ROOT

from ._support import edit_doc, example_host, graph_of

FIXTURE = "fix-password-reset-expired-token"
EXAMPLE_RECORD = "ver-password-reset-expired-token"
NFR = "nfr-latency-reset-email"
CRITERION = "ac-password-reset-3"
API = "api-password-reset-confirm"


def _bind(host: Path, verifier: str = FIXTURE, *, guard: str | None = "passed", commands: tuple[str, ...] = ("run-tests",), **given: Any) -> BindResult:
    """Bind *verifier* on *host* the way the command does: plan against the graph, write the record."""
    request = BindRequest(verifier, commands, guard, tuple(given.get("proves", ())), given.get("stage"), given.get("record_id"))
    return apply_bind(graph_of(host), str(host / "spec"), str(ROOT), request)


def _refusal(host: Path, verifier: str = FIXTURE, **given: Any) -> FindingError:
    with pytest.raises(FindingError) as caught:
        _bind(host, verifier, **given)
    return caught.value


def _record_files(host: Path) -> dict[str, str]:
    folder = Path(records_folder(str(host / "spec")))
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(folder.glob("*.json"))}


def _add_fixture(host: Path, **fixture: Any) -> None:
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"].append({"mode": "contract", **fixture}))


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return example_host(tmp_path)


def test_first_binding_of_the_worked_example_is_dev_with_both_proves(host: Path) -> None:
    stored = json.loads((host / "spec" / "extras" / "verification" / f"{EXAMPLE_RECORD}.json").read_text())["records"][0]
    result = _bind(host, guard=stored["output_guard"], commands=tuple(stored["commands"]))
    written = json.loads((host / "spec" / "extras" / "verification" / f"{EXAMPLE_RECORD}.json").read_text())["records"][0]
    assert result.plan.record_id == EXAMPLE_RECORD and result.plan.stage == "dev"
    assert written.pop("proves") == [CRITERION, API]
    assert written == stored


def test_nfr_staging_binding_defaults_to_staging(host: Path) -> None:
    _add_fixture(host, fixture_id="fix-reset-email-delivery-time", verifies=[NFR])
    result = _bind(host, "fix-reset-email-delivery-time")
    assert (result.plan.stage, result.plan.proves, result.plan.record_id) == ("staging", (NFR,), "ver-reset-email-delivery-time")


def test_explicit_dev_stage_on_a_prod_nfr_is_e330_and_writes_nothing(host: Path) -> None:
    _add_fixture(host, fixture_id="fix-reset-email-delivery-time", verifies=[NFR])
    before = _record_files(host)
    error = _refusal(host, "fix-reset-email-delivery-time", stage="dev")
    assert error.error.code == "E330" and "staging" in error.error.message
    assert _record_files(host) == before


def test_mixed_stage_fixture_without_proves_lists_the_two_groups(host: Path) -> None:
    _add_fixture(host, fixture_id="fix-mixed", verifies=[CRITERION, NFR])
    before = _record_files(host)
    message = _refusal(host, "fix-mixed").error.message
    assert f"dev: {CRITERION}" in message and f"staging: {NFR}" in message and "--proves" in message
    assert _record_files(host) == before


def test_two_binds_on_one_fixture_yield_two_records(host: Path) -> None:
    _add_fixture(host, fixture_id="fix-mixed", verifies=[CRITERION, NFR])
    first = _bind(host, "fix-mixed", proves=(CRITERION,))
    second = _bind(host, "fix-mixed", proves=(NFR,))
    assert [(first.plan.record_id, first.plan.stage), (second.plan.record_id, second.plan.stage)] == [("ver-mixed", "dev"), ("ver-mixed-staging", "staging")]
    assert {"ver-mixed.json", "ver-mixed-staging.json"} <= set(_record_files(host))


def test_a_rebind_after_the_stage_of_a_proved_node_changed_replaces_the_record_without_id(host: Path) -> None:
    """E330 on the stored record says its stage is not the one its nodes need: the same bind again is the way out, and it keeps the id."""
    _add_fixture(host, fixture_id="fix-reset-email-delivery-time", verifies=[NFR])
    first = _bind(host, "fix-reset-email-delivery-time")
    edit_doc(host, "07_nfrs.json", lambda doc: doc["nfrs"][0].update(stage="prod"))
    second = _bind(host, "fix-reset-email-delivery-time")
    assert (first.plan.stage, second.plan.stage) == ("staging", "prod")
    assert (second.plan.record_id, second.plan.replaced) == (first.plan.record_id, True)
    assert not [name for name in _record_files(host) if name.startswith("ver-reset-email-delivery-time-")]


def test_a_rebind_replaces_the_binding_whose_proved_nodes_are_the_requests_whatever_its_id(host: Path) -> None:
    """The second binding of a verifier is ``ver-mixed-staging``; when its node moves to ``prod`` the plain re-bind updates that record and keeps its id."""
    _add_fixture(host, fixture_id="fix-mixed", verifies=[CRITERION, NFR])
    _bind(host, "fix-mixed", proves=(CRITERION,))
    second = _bind(host, "fix-mixed", proves=(NFR,))
    edit_doc(host, "07_nfrs.json", lambda doc: doc["nfrs"][0].update(stage="prod"))
    again = _bind(host, "fix-mixed", proves=(NFR,))
    assert (second.plan.record_id, second.plan.stage) == ("ver-mixed-staging", "staging")
    assert (again.plan.record_id, again.plan.stage, again.plan.replaced) == ("ver-mixed-staging", "prod", True)
    assert not [name for name in _record_files(host) if name.startswith("ver-mixed-prod")]


def test_a_rebind_replaces_a_binding_with_an_explicit_id_the_same_way(host: Path) -> None:
    _add_fixture(host, fixture_id="fix-mixed", verifies=[CRITERION, NFR])
    _bind(host, "fix-mixed", proves=(CRITERION,))
    _bind(host, "fix-mixed", proves=(NFR,), record_id="ver-latency-only")
    edit_doc(host, "07_nfrs.json", lambda doc: doc["nfrs"][0].update(stage="prod"))
    again = _bind(host, "fix-mixed", proves=(NFR,))
    assert (again.plan.record_id, again.plan.replaced) == ("ver-latency-only", True)


def test_a_rebind_with_proved_nodes_that_overlap_a_binding_without_being_its_nodes_is_still_e333(host: Path) -> None:
    _add_fixture(host, fixture_id="fix-mixed", verifies=[CRITERION, NFR])
    _bind(host, "fix-mixed", proves=(CRITERION,))
    _bind(host, "fix-mixed", proves=(NFR,))
    error = _refusal(host, "fix-mixed", proves=(CRITERION, NFR), record_id="ver-both")
    assert error.error.code == "E333" and "ver-mixed" in error.error.message


RULE = "rule-spec-check-on-every-pr"


def test_a_plain_rebind_of_a_rule_replaces_the_default_id_binding_not_the_other_one(host: Path) -> None:
    """A rule's bindings prove nothing countable, so the nodes of the request say nothing about which binding is meant: the default id is."""
    first = _bind(host, RULE, commands=("echo ran",), guard="ran")
    _bind(host, RULE, commands=("echo ran",), guard="ran", record_id="ver-rule-two")
    again = _bind(host, RULE, commands=("echo changed",), guard="changed")
    assert (first.plan.record_id, again.plan.record_id, again.plan.replaced) == ("ver-spec-check-on-every-pr", "ver-spec-check-on-every-pr", True)
    files = _record_files(host)
    assert '"changed"' in files["ver-spec-check-on-every-pr.json"] and '"ran"' in files["ver-rule-two.json"]


def test_a_binding_without_stated_proves_under_another_id_is_not_taken_for_a_request_that_proves_a_node(host: Path) -> None:
    """The first binding of a fixture is ``ver-late`` (no ``proves`` stated): a request that proves one node of the fixture does not replace it, E333 says it already claims every target."""
    _add_fixture(host, fixture_id="fix-mixed", verifies=[CRITERION, NFR])
    _bind(host, "fix-mixed", proves=(CRITERION,), record_id="ver-late")
    edit_doc(host, "extras/verification/ver-late.json", lambda doc: doc["records"][0].pop("proves"))
    error = _refusal(host, "fix-mixed", proves=(NFR,))
    assert error.error.code == "E333" and "ver-late" in error.error.message


def test_a_narrower_request_does_not_take_over_the_wider_bindings_id(host: Path) -> None:
    _add_fixture(host, fixture_id="fix-mixed", verifies=[CRITERION, NFR])
    _bind(host, "fix-mixed", proves=(CRITERION,), record_id="ver-wide")
    edit_doc(host, "extras/verification/ver-wide.json", lambda doc: doc["records"][0].update(proves=[CRITERION, NFR]))
    error = _refusal(host, "fix-mixed", proves=(NFR,))
    assert error.error.code == "E333" and "ver-wide" in error.error.message


@pytest.mark.parametrize("guard", [None, ""])
def test_missing_guard_is_e332(host: Path, guard: str | None) -> None:
    assert _refusal(host, guard=guard).error.code == "E332"


def test_invalid_regex_guard_is_e332(host: Path) -> None:
    error = _refusal(host, guard="(unclosed")
    assert error.error.code == "E332" and "(unclosed" in error.error.message


def test_empty_matching_guard_is_accepted_with_a_note(host: Path) -> None:
    result = _bind(host, guard=".*")
    assert result.plan.notes == (EMPTY_GUARD_NOTE,)
    assert (host / "spec" / "extras" / "verification" / f"{result.plan.record_id}.json").is_file()


def test_manual_fixture_is_refused_with_the_attest_pointer(host: Path) -> None:
    _add_fixture(host, fixture_id="fix-manual-review", verifies=[CRITERION], mode="manual", manual_reason="a person looks")
    error = _refusal(host, "fix-manual-review")
    assert error.error.code == "E767" and "a person attests it" in error.error.message and "verify attest" not in error.error.message


def test_removal_fixture_is_accepted_at_dev_only(host: Path) -> None:
    _add_fixture(host, fixture_id="fix-removed-endpoint", removes=[API])
    assert _refusal(host, "fix-removed-endpoint", stage="ci").error.code == "E330"
    assert _refusal(host, "fix-removed-endpoint", proves=(API,)).error.code == "E331"
    result = _bind(host, "fix-removed-endpoint")
    stored = json.loads((host / "spec" / "extras" / "verification" / f"{result.plan.record_id}.json").read_text())["records"][0]
    assert (result.plan.stage, stored["stage"], "proves" in stored) == ("dev", "dev", False)


def test_bind_twice_is_idempotent(host: Path) -> None:
    first = _bind(host, guard="passed again")
    text = _record_files(host)[f"{first.plan.record_id}.json"]
    second = _bind(host, guard="passed again")
    assert (second.plan.replaced, second.plan.record_id) == (True, first.plan.record_id)
    assert _record_files(host)[f"{second.plan.record_id}.json"] == text
    assert sorted(_record_files(host)) == [f"{EXAMPLE_RECORD}.json"]


def test_proves_outside_the_verifier_targets_is_e331(host: Path) -> None:
    error = _refusal(host, proves=(NFR,))
    assert error.error.code == "E331" and NFR in error.error.message and API in error.error.message


def test_second_binding_id_for_a_claimed_pair_is_e333(host: Path) -> None:
    _bind(host, proves=(API,))  # the example's record, which stated no proves, now states the API only
    _bind(host, proves=(CRITERION,), record_id="ver-claims-the-criterion")
    error = _refusal(host, proves=(CRITERION,), record_id="ver-claims-it-too")
    assert error.error.code == "E333" and "ver-claims-the-criterion" in error.error.message


def test_a_record_that_states_no_proves_claims_every_target_of_its_verifier(host: Path) -> None:
    error = _refusal(host, proves=(CRITERION,), record_id="ver-claims-the-criterion")
    assert error.error.code == "E333" and EXAMPLE_RECORD in error.error.message


def test_unknown_environment_stage_is_e334(host: Path) -> None:
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"].update(qa={"scope": "in"}))
    edit_doc(host, "12_ci_gates.json", lambda doc: doc["jobs"].append({"job_id": "job-qa-smoke", "name": "QA smoke", "realises": ["qa"]}))
    error = _refusal(host, "job-qa-smoke")
    assert error.error.code == "E334" and "qa" in error.error.message


def test_a_not_applicable_verifier_takes_no_binding(host: Path) -> None:
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(lifecycle="not_applicable"))
    error = _refusal(host).error
    assert error.code == "E767" and "not_applicable" in error.message


def test_a_job_binds_what_it_realises_at_its_environment_stage(host: Path) -> None:
    result = _bind(host, "job-contract-tests")
    assert (result.plan.stage, result.plan.record_id) == ("ci", "ver-contract-tests")
    assert set(result.plan.proves) == {"ci", "contract-tests", "rule-contract-tests-on-every-pr"}


@pytest.mark.parametrize("verifier", ["fix-nothing-like-this", NFR, "tp-argon2"])
def test_an_unknown_or_unbindable_verifier_is_refused(host: Path, verifier: str) -> None:
    assert _refusal(host, verifier).error.code in {"E706", "E767"}


def test_an_id_that_names_another_node_is_refused(host: Path) -> None:
    assert _refusal(host, record_id=FIXTURE).error.code == "E767"


def test_the_graph_after_a_bind_resolves_the_record(host: Path) -> None:
    result = _bind(host, guard="passed again")
    graph: Graph = graph_of(host)
    assert graph.by_id[result.plan.record_id].kind == "verification-record" and not graph.load_errors
