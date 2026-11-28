"""The worked example of the design (section 12: a member resets a forgotten password) through the migration (plan 7.3).

``tests/fixtures/migration/worked_example_1_1_1/`` is the 1.1.1 host the "Today" blocks of 12.2 to 12.19 describe.  The migration
runs on a git copy of it (the harness's mechanical stage), and the result is compared with the "New" blocks of the same
section by STRUCTURE and ids: the link-field names are the toolkit's own (``graph.names``), the list and id names are checked
against the 1.2.0 schemas (the design says its key names are illustrative), and the ids the runner mints are compared by their
prefix, not by the slug the design happened to choose.

What the design marks as mechanical must be there: string lists became nodes with ids, ``fixture_ref`` became ``verified_by``,
the removed fields are gone, the link fields a script can derive from a 1.1.1 field are written (``trace`` -> ``derives_from`` /
``provided_by``, ``scope`` + ``trace`` of an invariant -> ``constrains``, ``targets`` -> ``verifies``, ``target_ids`` ->
``threatens``, ``mitigations`` -> ``mitigated_by``, ``interface_ref`` of a scaffold row -> ``realises``), the ``pr_rules`` became
rules with the enforcer mapping.  What it marks as judgement (``derives_from`` of a rule, a charter node, a third party; ``refines``;
the pin of a third party; ``realises`` of a plan item; the risks a milestone schedules beyond its typed deliverables) is NOT invented: the field is absent and a worklist item or a
proposal names it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from specdev_tools.graph import names

from .host_migration.harness import Cli, make_git_copy, run_mechanical_stage

REAL_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REAL_ROOT / "tests" / "fixtures" / "migration" / "worked_example_1_1_1"
SCHEMA = REAL_ROOT / "schema"

# The list and id names the comparison reads: (step schema file, list name, id name).  Each is checked against the schema text.
SCHEMA_NAMES = [
    ("00_charter", "scope_items", "scope_id"),
    ("00_charter", "assumptions", "assumption_id"),
    ("00_charter", "risks", "risk_id"),
    ("00_charter", "stakeholders", "stakeholder_id"),
    ("00_charter", "needs", "need_id"),
    ("02_system_sketch", "third_parties", "third_party_id"),
    ("02_system_sketch", "connections", "connection_id"),
    ("02a_delivery_baseline", "ci_gates", "gate_id"),
    ("02a_delivery_baseline", "secrets", "secret_id"),
    ("05_interface_contracts", "errors", "error_id"),
    ("10_governance", "rules", "rule_id"),
    ("15_scaffold", "interface_map", "row_id"),
    ("16_anchor", "milestone_index", "anchor_id"),
]


def load(host: Path, name: str):
    return json.loads((host / "spec" / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def migrated(tmp_path_factory, toolkit_1_2_0):
    """``(host, report, worklist items)``: the worked-example host after the mechanical stage."""
    host = make_git_copy(FIXTURE, tmp_path_factory.mktemp("worked") / "host")
    report = run_mechanical_stage(host, toolkit_1_2_0, "mini")
    items = json.loads((host / "spec" / "extras" / "migration" / "worklist.json").read_text(encoding="utf-8"))["items"]
    return host, report, items


def worklist_about(items, kind: str) -> set[str]:
    return {item["about"] for item in items if item["kind"] == kind}


def keys_anywhere(value, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(keys_anywhere(v, key) for v in value.values())
    return isinstance(value, list) and any(keys_anywhere(v, key) for v in value)


def test_the_names_the_comparison_reads_exist_in_the_schemas():
    for step, list_name, id_name in SCHEMA_NAMES:
        text = (SCHEMA / f"{step}.schema.json").read_text(encoding="utf-8")
        assert f'"{list_name}"' in text and f'"{id_name}"' in text, (step, list_name, id_name)


def test_the_fixture_is_a_1_1_1_host_with_every_today_block_of_the_example():
    assert (FIXTURE / "spec" / "specdev_version").read_text(encoding="utf-8").count("toolkit_version: 1.1.1") == 1
    assert len(list((FIXTURE / "spec").glob("[0-1][0-9]*_*.json"))) == 18  # 00 to 16 (02a and 13 included) without 13a
    charter = load(FIXTURE, "00_charter.json")
    assert charter["in_scope"] and charter["stakeholders"][0]["needs"] == ["Fewer password-reset tickets"]  # string lists of 12.2
    assert load(FIXTURE, "09_impl_plan.json")["milestones"][0]["deliverables"][0]["id"] == "fr-password-reset"


def test_the_runner_accepts_the_example_and_the_harness_checklist_passes(migrated):
    _host, report, items = migrated
    assert report.ok, report.render()
    assert items  # the judgement is listed, not done


def test_charter_string_lists_became_nodes_and_the_judgement_links_are_not_invented(migrated):
    host, _report, items = migrated
    charter = load(host, "00_charter.json")
    assert {k for k in ("in_scope", "out_of_scope") if k in charter} == set()  # merged into scope_items
    scope = {s["scope_id"]: s["scope"] for s in charter["scope_items"]}
    assert sorted(scope.values()) == ["in", "out"] and all(i.startswith("scope-") for i in scope)
    assert [a["assumption_id"][:4] for a in charter["assumptions"]] == ["asm-"]
    assert [r["risk_id"][:5] for r in charter["risks"]] == ["risk-"] and charter["risks"][0]["scope"] == "in"
    stakeholder = charter["stakeholders"][0]
    assert stakeholder["stakeholder_id"] == "sh-support-lead" and stakeholder["needs"][0]["need_id"].startswith("need-")
    assert not keys_anywhere(charter, names.DERIVES_FROM)  # the seed or need a charter node derives from is a person's answer
    assert "scope-password-reset-by-sms" in worklist_about(items, "scope-reason")  # the out item needs its reason: listed, not invented
    assert "scope_reason" not in charter["scope_items"][1]


def test_capability_charter_goal_trace_became_derives_from_the_one_node_with_that_id(migrated):
    host, _report, items = migrated
    capability = load(host, "01_capabilities.json")["capabilities"][0]
    assert "trace" not in capability and capability[names.DERIVES_FROM] == ["seg-registered-member"]  # 12.3: a borrowed type, a bare id
    assert "cap-account-recovery" not in worklist_about(items, "trace-link")


def test_the_external_component_became_a_third_party_without_a_pin_and_tech_stack_went(migrated):
    host, _report, items = migrated
    sketch = load(host, "02_system_sketch.json")
    assert [c["component_id"] for c in sketch["components"]] == ["identity-service"]  # the external one left the components
    assert sketch["components"][0][names.DERIVES_FROM] == ["cap-account-recovery"]  # trace of a component is mechanical
    assert [t["third_party_id"] for t in sketch["third_parties"]] == ["email-provider"]
    assert "pin" not in sketch["third_parties"][0] and names.DERIVES_FROM not in sketch["third_parties"][0]
    assert "tech_stack" not in sketch and "tech_stack" not in load(host, "09_impl_plan.json") and "tech_stack" not in load(host, "14_roadmap.json")
    connection = sketch["connections"][0]
    assert connection["connection_id"].startswith("conn-") and connection[names.DERIVES_FROM] == ["identity-service"]
    assert names.CONNECTS_TO not in connection and {"from", "to", "trace"}.isdisjoint(connection)
    assert {"email-provider"} <= worklist_about(items, "external-component") and connection["connection_id"] in worklist_about(items, "connection-external")
    assert "email-provider" in worklist_about(items, "host-pin-source")  # where the pin is stated: the operator's answer


def test_delivery_baseline_gates_secrets_and_environments_became_nodes(migrated):
    host, _report, _items = migrated
    baseline = load(host, "02a_delivery_baseline.json")
    assert {name: env["scope"] for name, env in baseline["environments"].items()} == {"dev": "in", "ci": "in", "staging": "in", "prod": "in"}
    assert [g["gate_id"] for g in baseline["ci_gates"]] == ["contract-tests"]  # a gate keeps its kebab name as id (12.5)
    assert [s["secret_id"] for s in baseline["secrets"]] == ["secret-reset-token-signing-key", "secret-mailrelay-api-key"]  # minted, as in 12.5
    assert [s["name"] for s in baseline["secrets"]] == ["RESET_TOKEN_SIGNING_KEY", "MAILRELAY_API_KEY"]  # the env-var name stays as content
    assert all(g["scope"] == "in" for g in baseline["ci_gates"] + baseline["secrets"])


def test_fr_api_invariant_and_nfr_links_are_written_where_a_1_1_1_field_gives_them(migrated):
    host, _report, items = migrated
    fr = load(host, "04_fr_list.json")["functional_requirements"][0]
    assert fr[names.DERIVES_FROM] == ["cap-account-recovery"] and fr["scope"] == "in" and "trace" not in fr
    assert [c["scope"] for c in fr["acceptance_criteria"]] == ["in"] and fr["acceptance_criteria"][0]["criterion_id"] == "ac-password-reset-3"
    api = load(host, "05_interface_contracts.json")["apis"][0]
    assert api[names.DERIVES_FROM] == ["fr-password-reset"] and api[names.PROVIDED_BY] == ["identity-service"]  # one trace, two relations (12.8)
    assert api["scope"] == "in" and "trace" not in api and "example_refs" not in api and names.RELIES_ON not in api
    error = api["errors"][0]
    assert error["error_id"].startswith("err-") and error["scope"] == "in" and error["code"] == "token-expired"
    assert names.DERIVES_FROM not in error  # the criterion an error serves is a person's answer (12.8, Ruled)
    invariant = load(host, "06_invariants.json")["rules"][0]
    assert set(invariant[names.CONSTRAINS]) == {"fr-password-reset", "api-password-reset-confirm", "identity-service"}  # scope + trace -> one field (12.9)
    assert "trace" not in invariant and invariant["scope"] == "in"
    nfr = load(host, "07_nfrs.json")["nfrs"][0]
    assert nfr[names.CONSTRAINS] == ["fr-password-reset"] and nfr["scope"] == "in" and nfr["stage"] == "staging"  # `stage` stays (12.10)
    assert nfr[names.DERIVES_FROM] == ["metric-recovery-time"] and names.RELIES_ON not in nfr  # 12.10: the borrowed charter-goal type
    assert "nfr-latency-reset-email" not in worklist_about(items, "trace-link")


def test_fixture_targets_became_verifies_and_nothing_was_added(migrated):
    host, _report, _items = migrated
    fixtures = {f["fixture_id"]: f for f in load(host, "08_fixtures.json")["fixtures"]}
    assert fixtures["fix-password-reset-expired-token"][names.VERIFIES] == ["api-password-reset-confirm"]  # the criterion is a person's addition (12.11)
    assert fixtures["fix-password-reset-reused-token"][names.VERIFIES] == ["inv-reset-token-single-use"]
    assert all("targets" not in f for f in fixtures.values())


def test_design_milestone_lost_status_and_deliverables_and_the_typed_deliverable_became_schedules(migrated):
    host, _report, items = migrated
    milestone = load(host, "09_impl_plan.json")["milestones"][0]
    assert {"status", "deliverables", "depends_on"}.isdisjoint(milestone)
    assert milestone[names.SCHEDULES] == ["fr-password-reset"]  # 12.12: the typed deliverable is written
    assert worklist_about(items, "schedules") == set()  # every deliverable converted: nothing for a person


def test_governance_pr_rules_became_rules_with_the_enforcer_mapping(migrated):
    host, _report, items = migrated
    governance = load(host, "10_governance.json")
    assert {"pr_rules", "reviewers", "review_policy"}.isdisjoint(governance)  # `reviewers` is removed (12.13)
    rules = {r["rule_id"]: r for r in governance["rules"]}
    assert rules["rule-validate-all"]["cli_command"] == "spec-check"  # a retired command maps to its replacement (D10)
    assert rules["rule-governance-check"]["cli_command"] == "governance-check"
    assert all(r["scope"] == "in" and names.DERIVES_FROM not in r for r in rules.values())  # the upstream reason is a person's answer
    assert worklist_about(items, "rule-reason") == set(rules)
    assert governance["commit_message_rules"] == {"require_spec_ids": False}  # artifact content stays (12.13)


def test_threat_links_and_the_ci_job_steps(migrated):
    host, _report, _items = migrated
    redteam = load(host, "11_redteam.json")
    threat = redteam["threats"][0]
    assert threat["threatens"] == ["api-password-reset-confirm"]
    assert threat[names.MITIGATED_BY] == ["inv-reset-token-single-use", "fix-password-reset-expired-token"]
    assert {"target_ids", "mitigations"}.isdisjoint(threat) and names.DERIVES_FROM not in threat and threat["scope"] == "in"
    assert redteam["edge_cases"][0]["scope"] == "in"
    job = load(host, "12_ci_gates.json")["jobs"][0]
    assert job["steps"] == [{"name": "Run Contract Suite", "command": "npm run test:contract"}]  # steps are content: ids dropped (12.15)
    assert names.REALISES not in job  # the gate and rule a job realises are a person's answer


def test_roadmap_fixture_ref_became_verified_by_and_refines_is_a_proposal_not_a_value(migrated, toolkit_1_2_0):
    host, _report, _items = migrated
    milestone = load(host, "14_roadmap.json")["milestones"][0]
    assert {"status", "fr_refs", "capability_refs", "source_milestones", "deliverables"}.isdisjoint(milestone)
    task = milestone["tasks"][0]
    assert {"status", "fr_refs", "invariant_refs", "assumptions", "exit_conditions"}.isdisjoint(task)
    criterion = task["acceptance_criteria"][0]
    assert criterion[names.VERIFIED_BY] == ["fix-password-reset-expired-token"] and "fixture_ref" not in criterion
    assert names.REFINES not in criterion  # 12.17: the obligation a criterion narrows is judged, never guessed by a script
    proposed = Cli(host, toolkit_1_2_0).align("propose", "--kind", "refines", "--dry-run")
    assert proposed.code == 0 and "ac-implement-password-reset-confirm-1" in proposed.out
    assert names.REFINES not in load(host, "14_roadmap.json")["milestones"][0]["tasks"][0]["acceptance_criteria"][0]  # a dry run wrote nothing


def test_scaffold_row_anchor_row_and_plan_item(migrated):
    host, _report, items = migrated
    row = load(host, "15_scaffold.json")["interface_map"][0]
    assert row["row_id"].startswith("scaffold-") and row[names.REALISES] == ["api-password-reset-confirm"]  # interface_ref -> realises (12.18)
    assert {"interface_ref", "method", "trace"}.isdisjoint(row) and row["path"] == "src/routes/password-resets/confirm.ts"
    anchor = load(host, "16_impl_context.json")["plan"]["milestone_index"][0]
    assert anchor["anchor_id"] == "anchor-ms-account-recovery" and anchor[names.ABOUT] == ["ms-account-recovery"] and anchor["status"] == "in_progress"
    assert {"milestone_id", "context_path", "fr_refs"}.isdisjoint(anchor)  # 12.19
    assert anchor["checklist_id_prefix"] == "PWRESET"
    plan = load(host, "impl_context/ms_account_recovery_plan.json")
    assert plan["milestone"] == "ms-account-recovery"  # file-level key, not a link field (12.19)
    item = plan["plan"]["spec_alignment"]["checklist"][0]
    assert {"milestone_ref", "fixture_ref", "nfr_refs", "linked_test_expectation", "checklist_status"}.isdisjoint(item)  # the computed and removed fields
    assert "status" not in item["implementation"] and item["implementation"]["actions"][0]["id"] == "a01"  # an open plan's actions get ids
    assert names.REALISES not in item  # a task is not a task criterion: `realises` is the judgement 16a completes
    listed = [i for i in items if i["kind"] == "spec-ref-realises" and i["about"] == "PWRESET_CONFIRM_EXPIRED_01"]
    assert listed and "ac-implement-password-reset-confirm-1" in listed[0]["proposal"]
    # the item still holds spec_ref (with its pins) until `realises` replaces it: the worklist item is what names the task
    assert item["spec_ref"]["id"] == "task-implement-password-reset-confirm"


def test_every_mint_the_example_needed_is_stable_by_prefix(migrated):
    host, _report, _items = migrated
    text = "".join(path.read_text(encoding="utf-8") for path in (host / "spec").glob("*.json"))
    for prefix in ("scope-", "asm-", "risk-", "sh-", "need-", "conn-", "secret-", "err-", "scaffold-", "anchor-"):
        assert re.search(rf'"{prefix}[a-z0-9-]+"', text), prefix
