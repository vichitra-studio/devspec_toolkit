"""``specdev verify attest`` and ``review_rule_attested``, on git copies of the worked example."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.core.schema_validate import schema_violations
from specdev_tools.lifecycle.executed import at_deploy_recorded
from specdev_tools.lifecycle.attest import attest, attestation_id, plan_attest, review_rule_attested
from specdev_tools.proof.proof import PROVEN, UNPROVEN, proof, proof_errors, verifier_proof
from specdev_tools.verify.records import attestations_about, evidence_id, install_check_id, records_folder, write_evidence
from unit.graph._synth import ROOT
from unit.lifecycle._record_support import AUTHOR, ITEM, action, author, plan_host, roots
from unit.proof._support import CRITERION, FIXTURE, INVARIANT, NFR, OTHER_FIXTURE, add_fixture, binding_item, context, edit_code, host_with, run
from unit.trace._lock_support import run_on_example
from unit.verify._support import commit_all, edit_doc, graph_of

pytestmark = pytest.mark.usefixtures("author")
REVIEW_RULE = "rule-security-review-of-token-handling"
MANUAL_NFR_FIXTURE = "fix-manual-latency"
EVIDENCE_FILES = "extras/verification"


def _manual(host: Path, fixture: str = OTHER_FIXTURE) -> None:
    """Make *fixture* of the example a manual fixture, as a person reviews it."""
    def edit(document: dict[str, Any]) -> None:
        for entry in document["fixtures"]:
            if entry["fixture_id"] == fixture:
                entry.update(mode="manual", manual_reason="a person replays the token by hand")

    edit_doc(host, "08_fixtures.json", edit)


def _host(tmp_path: Path, *bindings: dict[str, Any]) -> Path:
    """The example with code, ``fix-password-reset-reused-token`` manual, and the given bindings."""
    host = host_with(tmp_path, *bindings)
    _manual(host)
    commit_all(host, "manual fixture")
    return host


def _nfr_host(tmp_path: Path) -> Path:
    """A host whose manual fixture verifies the NFR that needs ``staging``."""
    host = host_with(tmp_path)
    add_fixture(host, fixture_id=MANUAL_NFR_FIXTURE, mode="manual", manual_reason="measured by hand", verifies=[NFR], description="A person measures the latency.")
    commit_all(host, "manual nfr fixture")
    return host


def _attest(host: Path, *argv: str) -> tuple[int, str]:
    return run_on_example(host, "verify", "attest", *argv)


def _evidence_names(host: Path) -> list[str]:
    return sorted(path.name for path in (host / "spec" / EVIDENCE_FILES).glob("evd-*.json"))


def _record(host: Path, node_id: str) -> dict[str, Any]:
    return json.loads((host / "spec" / EVIDENCE_FILES / f"{attestation_id(node_id)}.json").read_text(encoding="utf-8"))["records"][0]


def _review_findings(host: Path) -> list[Any]:
    return review_rule_attested(REVIEW_RULE, graph_of(host), context(host))


def test_review_rule_attested_is_empty_after_attest(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    code, _ = _attest(host, REVIEW_RULE)
    assert code == 0 and _review_findings(host) == []


def test_review_rule_unattested_is_e830_before_attest(tmp_path: Path) -> None:
    (finding,) = _review_findings(host_with(tmp_path))
    assert (finding.code, finding.subcode, finding.node_id, finding.owner) == ("E830", "NO_ATTESTATION", REVIEW_RULE, "release-gate")
    assert f"specdev verify attest {REVIEW_RULE}" in finding.message


@pytest.mark.parametrize(("change", "subcode"), [("rule", "STALE_HASH"), ("tree", "STALE_TREE")])
def test_review_rule_attestation_goes_stale_after_a_rule_or_tree_change(tmp_path: Path, change: str, subcode: str) -> None:
    host = host_with(tmp_path)
    _attest(host, REVIEW_RULE)
    if change == "rule":
        edit_doc(host, "10_governance.json", lambda doc: doc["rules"][2].update(text="A person reviews every change to reset-token handling and mail templates."))
    else:
        edit_code(host)
    (finding,) = _review_findings(host)
    assert finding.code == "E830" and finding.subcode == subcode
    _attest(host, REVIEW_RULE)
    assert _review_findings(host) == []


def test_review_rule_attested_takes_a_review_rule_only(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    with pytest.raises(ValueError, match="not a rule enforced by review"):
        review_rule_attested("rule-contract-tests-on-every-pr", graph_of(host), context(host))
    with pytest.raises(KeyError):
        review_rule_attested("rule-nothing", graph_of(host), context(host))


def test_manual_fixture_attested(tmp_path: Path) -> None:
    host = _host(tmp_path)
    assert verifier_proof(graph_of(host), context(host), OTHER_FIXTURE, "prod").status == UNPROVEN
    assert proof(graph_of(host), context(host), INVARIANT, "dev").status == UNPROVEN
    code, output = _attest(host, OTHER_FIXTURE)
    assert code == 0, output
    assert verifier_proof(graph_of(host), context(host), OTHER_FIXTURE, "prod").status == PROVEN
    assert proof(graph_of(host), context(host), INVARIANT, "dev").status == PROVEN


def test_the_unproven_manual_fixture_finding_names_the_command(tmp_path: Path) -> None:
    host = _host(tmp_path)
    (finding,) = proof_errors(graph_of(host), context(host), [INVARIANT], "dev")
    assert (finding.code, finding.subcode) == ("E347", "NO_EVIDENCE")
    assert f"run `specdev verify attest {OTHER_FIXTURE}`" in finding.message


def test_an_attestation_of_a_manual_fixture_goes_stale_when_the_fixture_changes(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _attest(host, OTHER_FIXTURE)
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][1].update(description="The confirm endpoint rejects a token that was redeemed already."))
    assert [error.subcode for error in proof_errors(graph_of(host), context(host), [INVARIANT], "dev")] == ["STALE_HASH"]


def test_non_attestable_id_is_e824_and_nothing_is_written(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _evidence_names(host)
    for bad in (FIXTURE, "rule-contract-tests-on-every-pr", CRITERION, "fix-no-such-fixture"):
        code, output = _attest(host, OTHER_FIXTURE, REVIEW_RULE, bad)
        assert code == 1 and output.startswith("E824"), output
        assert _evidence_names(host) == before


def test_the_e824_message_names_the_way_out(tmp_path: Path) -> None:
    host = _host(tmp_path)
    assert f"specdev verify bind {FIXTURE}" in _attest(host, FIXTURE)[1]
    assert "enforced by a job or a command" in _attest(host, "rule-contract-tests-on-every-pr")[1]
    assert "nearest: fix-password-reset-reused-token" in _attest(host, "fix-password-reset-reusd-token")[1]


def test_record_fields_match_m7_and_validate(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _attest(host, OTHER_FIXTURE)
    record = _record(host, OTHER_FIXTURE)
    repo = str(ROOT)
    document = json.loads((host / "spec" / EVIDENCE_FILES / "evd-fix-password-reset-reused-token-attested.json").read_text(encoding="utf-8"))
    assert schema_violations(repo, document) == []
    assert set(record) == {"evidence_id", "about", "type", "stage", "tested_tree", "recorded_hashes", "git_author"}
    assert (record["evidence_id"], record["about"], record["type"], record["git_author"]) == ("evd-fix-password-reset-reused-token-attested", [OTHER_FIXTURE], "attestation", AUTHOR)
    assert record["tested_tree"] == context(host).code_tree
    assert record["recorded_hashes"] == {OTHER_FIXTURE: context(host).content_hashes(graph_of(host))[OTHER_FIXTURE]}
    (read,) = attestations_about(graph_of(host), OTHER_FIXTURE)
    assert (read.evidence_id, read.stage, read.tested_tree) == (record["evidence_id"], record["stage"], record["tested_tree"])


def test_one_record_per_id(tmp_path: Path) -> None:
    host = _host(tmp_path)
    code, output = _attest(host, OTHER_FIXTURE, REVIEW_RULE, OTHER_FIXTURE)
    assert code == 0, output
    assert _evidence_names(host) == [f"{attestation_id(OTHER_FIXTURE)}.json", f"{attestation_id(REVIEW_RULE)}.json"]


def test_a_second_attestation_replaces_the_first(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _attest(host, OTHER_FIXTURE)
    _attest(host, OTHER_FIXTURE, "--stage", "staging")
    assert _evidence_names(host) == [f"{attestation_id(OTHER_FIXTURE)}.json"]
    assert _record(host, OTHER_FIXTURE)["stage"] == "staging"


def test_an_attestation_and_a_run_or_an_install_check_never_share_a_file(tmp_path: Path) -> None:
    """A run's evidence ends in a stage and an install check in ``-install``: an attestation ends in neither, so none replaces another."""
    host = host_with(tmp_path, binding_item("ver-attested-rule", verifier=REVIEW_RULE, proves=(), stage="ci"))
    run(host, ["ver-attested-rule"], stage="ci")
    write_evidence(records_folder(str(host / "spec")), str(ROOT), {
        "evidence_id": install_check_id("tp-argon2", "prod"), "about": ["tp-argon2"], "type": "install-check", "env": "prod", "tested_tree": "t", "installed_versions": {"tp-argon2": "1.0.0"},
    })
    before = _evidence_names(host)
    assert _attest(host, REVIEW_RULE)[0] == 0
    assert _evidence_names(host) == sorted([*before, f"{attestation_id(REVIEW_RULE)}.json"])
    assert evidence_id("ver-attested-rule", "ci") + ".json" in before and f"{attestation_id(REVIEW_RULE)}.json" not in before


def test_default_stage_follows_the_obligation(tmp_path: Path) -> None:
    host = _nfr_host(tmp_path)
    code, output = _attest(host, MANUAL_NFR_FIXTURE)
    assert code == 0 and f"{MANUAL_NFR_FIXTURE} (fixture) at stage staging (the stage it needs; --stage overrides it)" in output, output
    assert _record(host, MANUAL_NFR_FIXTURE)["stage"] == "staging"
    assert proof(graph_of(host), context(host), NFR, "prod").status == PROVEN


def test_a_stage_the_node_does_not_need_is_printed_as_given_and_the_proof_judges_it(tmp_path: Path) -> None:
    host = _nfr_host(tmp_path)
    code, output = _attest(host, MANUAL_NFR_FIXTURE, "--stage", "dev")
    assert code == 0 and "at stage dev (given by --stage)" in output, output
    result = proof(graph_of(host), context(host), NFR, "prod")
    assert (result.status, result.shortfalls[0].reason) == (UNPROVEN, "STAGE_TOO_LOW")


def test_a_review_rule_defaults_to_the_stage_of_a_rule(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    assert "at stage ci (the stage it needs" in _attest(host, REVIEW_RULE)[1]


def test_a_stage_that_cannot_be_told_is_e334_unless_given(tmp_path: Path) -> None:
    host = _nfr_host(tmp_path)
    edit_doc(host, "07_nfrs.json", lambda doc: doc["nfrs"][0].update(stage="weekly"))
    code, output = _attest(host, MANUAL_NFR_FIXTURE)
    assert code == 1 and output.startswith("E334") and "--stage" in output, output
    assert _attest(host, MANUAL_NFR_FIXTURE, "--stage", "staging")[0] == 0


def test_the_plan_is_printed_before_the_records_are_written(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _, output = _attest(host, OTHER_FIXTURE, REVIEW_RULE)
    lines = output.splitlines()
    assert lines[0] == "attesting 2 target(s):"
    assert OTHER_FIXTURE in lines[1] and "The confirm endpoint rejects a token" in lines[1] and "A person reviews every change" in lines[2]
    assert lines[3:] == [f"attested {name}: {EVIDENCE_FILES}/{attestation_id(name)}.json" for name in (OTHER_FIXTURE, REVIEW_RULE)]


def test_json_output_lists_targets_and_records(tmp_path: Path) -> None:
    host = _host(tmp_path)
    code, output = _attest(host, OTHER_FIXTURE, "--json")
    document = json.loads(output)
    assert code == 0 and document["command"] == "verify attest"
    assert document["targets"] == [{"id": OTHER_FIXTURE, "kind": "fixture", "stage": "dev", "stage_given": False, "text": document["targets"][0]["text"]}]
    assert document["records"][0]["file"] == f"{EVIDENCE_FILES}/{attestation_id(OTHER_FIXTURE)}.json"


def test_no_git_author_refuses_before_anything_is_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = _host(tmp_path)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "none"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "user.useConfigOnly")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "EMAIL"):
        monkeypatch.delenv(name, raising=False)
    code, output = _attest(host, OTHER_FIXTURE)
    assert code == 1 and output.startswith("E767") and "git cannot name an author" in output, output
    assert _evidence_names(host) == []


def _deploy_host(tmp_path: Path) -> Path:
    return plan_host(tmp_path, action("a02", at_deploy=["staging"]))


def _dep_files(host: Path) -> list[str]:
    return sorted(path.name for path in (host / "spec" / EVIDENCE_FILES).glob("dep-*.json"))


def test_at_deploy_action_writes_a_dep_record_and_no_evidence(tmp_path: Path) -> None:
    host = _deploy_host(tmp_path)
    code, output = _attest(host, f"{ITEM}/a02", "--env", "staging")
    assert code == 0, output
    assert _dep_files(host) == ["dep-0001.json"] and _evidence_names(host) == []
    (record,) = json.loads((host / "spec" / EVIDENCE_FILES / "dep-0001.json").read_text(encoding="utf-8"))["records"]
    assert (record["about"], record["action"], record["env"], record["outcome"], record["git_author"]) == ([ITEM], "a02", "staging", "done", AUTHOR)
    assert f"{ITEM}/a02 (plan action) done at staging" in output


def test_an_at_deploy_attestation_reads_as_the_deploy_job_record_does(tmp_path: Path) -> None:
    host = _deploy_host(tmp_path)
    assert not at_deploy_recorded(str(host / "spec"), ITEM, "a02", "staging")
    _attest(host, f"{ITEM}/a02", "--env", "staging")
    assert at_deploy_recorded(str(host / "spec"), ITEM, "a02", "staging")


@pytest.mark.parametrize(
    ("address", "env"),
    [(f"{ITEM}/a01", "staging"), (f"{ITEM}/a09", "staging"), ("NO_ITEM/a01", "staging"), (f"{ITEM}/a02", "prod"), ("PWRESET/", "staging")],
)
def test_an_action_that_is_not_marked_for_the_environment_is_e824_and_nothing_is_written(tmp_path: Path, address: str, env: str) -> None:
    host = _deploy_host(tmp_path)
    code, output = _attest(host, REVIEW_RULE, address, "--env", env)
    assert code == 1 and output.startswith("E824"), output
    assert _dep_files(host) == [] and _evidence_names(host) == []


def test_a_node_and_an_action_in_one_command_write_both(tmp_path: Path) -> None:
    host = _deploy_host(tmp_path)
    code, output = _attest(host, REVIEW_RULE, f"{ITEM}/a02", "--env", "staging")
    assert code == 0, output
    assert _evidence_names(host) == [f"{attestation_id(REVIEW_RULE)}.json"] and _dep_files(host) == ["dep-0001.json"]


@pytest.mark.parametrize("argv", [(f"{ITEM}/a02",), (REVIEW_RULE, "--env", "staging")])
def test_env_and_actions_go_together(tmp_path: Path, argv: tuple[str, ...]) -> None:
    host = _deploy_host(tmp_path)
    code, output = _attest(host, *argv)
    assert code == 2 and "--env" in output, output
    assert _dep_files(host) == [] and _evidence_names(host) == []


def test_plan_attest_is_pure(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = plan_attest(graph_of(host), [OTHER_FIXTURE, REVIEW_RULE], "ci")
    assert [(target.node.id, target.stage, target.stage_given) for target in plan.nodes] == [(OTHER_FIXTURE, "ci", True), (REVIEW_RULE, "ci", True)]
    assert _evidence_names(host) == []
    with pytest.raises(FindingError) as caught:
        plan_attest(graph_of(host), [OTHER_FIXTURE, FIXTURE])
    assert caught.value.error.code == "E824"


def test_attest_writes_through_the_library(tmp_path: Path) -> None:
    host = _host(tmp_path)
    spec, repo, git = roots(host)
    result = attest(spec, repo, git, lambda graph: plan_attest(graph, [OTHER_FIXTURE]))
    assert [(entry.about, entry.type) for entry in result.written] == [(OTHER_FIXTURE, "attestation")]
    assert _evidence_names(host) == [f"{attestation_id(OTHER_FIXTURE)}.json"]
