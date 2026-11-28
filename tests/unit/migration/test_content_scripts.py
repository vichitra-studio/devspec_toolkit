"""Phase 4, the content migration (WI-M10-06): the nine ``p4_*`` scripts.

Every test runs the WHOLE registered chain through ``run_migration`` on a ``tmp_path`` git copy of the mini host with a temp
toolkit root that says 1.2.0 (ruling P1).  The module-scoped ``migrated`` run is the shared result; a test that needs another
1.1.1 shape edits its own copy first (the fixture folder is never rewritten).
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from specdev_tools.core.ambiguity_items import is_open, iter_ambiguity_items
from specdev_tools.migration import registry, runner
from specdev_tools.migration.report import STATUS_OK
from specdev_tools.migration.scripts.v1_2_0 import (
    p4_ambiguities,
    p4_assumptions,
    p4_exit_conditions,
    p4_mixed_jobs,
    p4_nfr_verifiers,
    p4_plan_dispositions,
    p4_plan_security_items,
    p4_step10_rules,
    p4_third_party,
)

from ._support import context, git, items, make_host, make_toolkit, migrate, MINI_HOST, read, REAL_ROOT, tree_digest

P4 = (p4_ambiguities, p4_assumptions, p4_exit_conditions, p4_mixed_jobs, p4_nfr_verifiers, p4_plan_dispositions, p4_plan_security_items, p4_step10_rules, p4_third_party)
P4_FILES = tuple(Path(module.__file__) for module in P4)
OPEN_PLAN = "impl_context/ms_reservations_plan.json"
CLOSED_PLAN = "impl_context/ms_catalog_plan.json"
FROZEN_BY_STATUS = "impl_context/ms_late_fees_plan.json"


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    host, toolkit, report = migrate(tmp_path_factory.mktemp("p4"))
    return host, toolkit, report


def residue_of(report, script_id: str) -> str:
    return "\n".join(next(s.residue for s in report.scripts if s.id == script_id))


def rules_of(host: Path) -> dict[str, dict]:
    return {rule["rule_id"]: rule for rule in read(host, "10_governance.json")["rules"]}


def by_text(rules: dict[str, dict]) -> dict[str, dict]:
    return {rule["text"]: rule for rule in rules.values()}


def original(rel: str):
    return json.loads((MINI_HOST / "spec" / rel).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------


def test_assumptions_become_nodes_with_ids(migrated):
    host, _toolkit, _report = migrated
    assumptions = read(host, "00_charter.json")["assumptions"]
    assert [a["text"] for a in assumptions] == original("00_charter.json")["assumptions"]
    assert all(a["assumption_id"].startswith("asm-") for a in assumptions)
    assert items(host, "assumption-bundle") == [] and items(host, "assumption-decision") == []


def test_bundled_assumption_is_flagged_not_split(tmp_path):
    bundled = "Members have a phone. The desk has a scanner."
    host, _toolkit, _report = migrate(tmp_path, ("00_charter.json", lambda d: d["assumptions"].append(bundled)))
    assumptions = read(host, "00_charter.json")["assumptions"]
    assert [a["text"] for a in assumptions].count(bundled) == 1 and len(assumptions) == 3
    [item] = items(host, "assumption-bundle")
    assert item["step"] == "00" and item["audience"] == "agent" and "2 sentences" in item["evidence"]
    assert item["about"] == next(a["assumption_id"] for a in assumptions if a["text"] == bundled)


def test_technology_assumption_is_flagged_as_decision(tmp_path):
    host, _toolkit, _report = migrate(tmp_path, ("00_charter.json", lambda d: d["assumptions"].append("PostgreSQL is available on the hosting plan")))
    [item] = items(host, "assumption-decision")
    assert item["step"] == "00" and "PostgreSQL" in item["evidence"] and "step-00 pass" in item["proposal"]
    assert "constraints" not in read(host, "00_charter.json")


# ---------------------------------------------------------------------------
# Step 10
# ---------------------------------------------------------------------------


def test_pr_rules_validate_all_and_matrix_map_to_spec_check_and_coverage(migrated, tmp_path):
    host, _toolkit, _report = migrated
    rules = by_text(rules_of(host))
    assert rules["validate-all"]["cli_command"] == "spec-check" and rules["matrix"]["cli_command"] == "coverage"
    pair, _t, _r = migrate(tmp_path, ("10_governance.json", lambda d: d.update(pr_rules=["validate-all", "governance-check"])))
    two = [r for r in read(pair, "10_governance.json")["rules"] if r["rule_id"] != "rule-a-reviewer-reads-every-changed-checklist-item"][:2]
    assert [(r["text"], r["cli_command"]) for r in two] == [("validate-all", "spec-check"), ("governance-check", "governance-check")]


def test_pr_rules_known_command_goes_to_cli_command(migrated):
    host, _toolkit, _report = migrated
    rules = by_text(rules_of(host))
    for name in ("governance-check", "fixtures-lint"):
        assert rules[name]["cli_command"] == name and "enforcer" not in rules[name]


def test_pr_rules_unknown_name_becomes_worklist_item(tmp_path):
    host, _toolkit, _report = migrate(tmp_path, ("10_governance.json", lambda d: d["pr_rules"].append("security")))
    rules = by_text(rules_of(host))
    assert all("cli_command" not in rules[name] for name in ("test", "lint", "security"))
    found = {i["about"]: i for i in items(host, "rule-job")}
    assert set(found) == {"rule-test", "rule-lint", "rule-security"}
    assert "gate-lint" in found["rule-lint"]["proposal"] and "gate-unit-tests" in found["rule-test"]["proposal"]
    assert "no step-12 job runs it" in found["rule-security"]["proposal"]


def test_review_policy_strings_become_review_rules(migrated):
    host, _toolkit, _report = migrated
    wanted = original("10_governance.json")["review_policy"]["verdict_requirements"]
    review = [r for r in rules_of(host).values() if r.get("enforcer") == "review"]
    assert [r["text"] for r in review] == wanted
    assert all(r["rule_id"].startswith("rule-") and r["scope"] == "in" and "cli_command" not in r and "derives_from" not in r for r in review)
    assert {i["about"] for i in items(host, "rule-reason")} >= {r["rule_id"] for r in review}


def test_reviewers_field_is_removed(migrated):
    host, _toolkit, _report = migrated
    data = read(host, "10_governance.json")
    assert not {"reviewers", "review_policy", "spec_first_policy", "pr_rules"} & set(data)


def test_commit_message_rules_and_versioning_untouched(migrated):
    host, _toolkit, _report = migrated
    data, before = read(host, "10_governance.json"), original("10_governance.json")
    assert data["commit_message_rules"] == before["commit_message_rules"] and data["versioning"] == before["versioning"]
    assert data["policy_ref"] == before["policy_ref"]


# ---------------------------------------------------------------------------
# Mixed jobs, third parties
# ---------------------------------------------------------------------------


def test_mixed_job_candidate_is_listed_not_split(migrated):
    host, _toolkit, _report = migrated
    [item] = items(host, "mixed-job")
    assert item["about"] == "gate-go-live-staging-teardown" and item["step"] == "12" and item["audience"] == "agent"
    jobs = {j["job_id"]: j for j in read(host, "12_ci_gates.json")["jobs"]}
    assert len(jobs["gate-go-live-staging-teardown"]["steps"]) == 3
    assert [s["name"] for s in jobs["gate-go-live-staging-teardown"]["steps"]] == [s["name"] for s in original("12_ci_gates.json")["jobs"][-1]["steps"]]


def test_tech_stack_entries_become_third_party_proposals(migrated):
    host, _toolkit, _report = migrated
    found = {i["about"]: i for i in items(host, "third-party-proposal")}
    assert set(found) == {"tp-typescript", "tp-express", "tp-postgresql", "tp-textline-sms-api", "tp-eslint"}
    assert all(i["step"] == "02" and i["audience"] == "agent" for i in found.values())
    assert "pin 16" in found["tp-postgresql"]["proposal"]
    system = read(host, "02_system_sketch.json")
    assert "tech_stack" not in system
    assert [t["third_party_id"] for t in system["third_parties"]] == ["textline-sms"]
    assert "derives_from" not in system["third_parties"][0] and "pin" not in system["third_parties"][0]
    assert "textline-sms" not in {c["component_id"] for c in system["components"]}


def test_external_dependency_entry_becomes_one_item(migrated):
    host, _toolkit, _report = migrated
    found = items(host, "external-dependency")
    assert sorted(i["id"].rsplit("-", 1)[1] for i in found) == ["09", "14"]
    assert all(i["about"] == "textline-sms" and "relies_on" in i["proposal"] and "connects_to" in i["proposal"] for i in found)
    [component] = items(host, "external-component")
    assert component["about"] == "textline-sms" and "E590" in component["evidence"]


def test_non_semver_version_is_flagged(tmp_path):
    def exact(document: dict) -> None:
        for group in document["tech_stack"].values():
            for entry in group:
                if entry["name"] == "ESLint":
                    entry["version"] = "9.1.0"

    host, _toolkit, _report = migrate(tmp_path, *((rel, exact) for rel in ("02_system_sketch.json", "09_impl_plan.json", "14_roadmap.json")))
    found = {i["about"]: i for i in items(host, "third-party-proposal")}
    assert "not semver" not in found["tp-eslint"]["evidence"] and "disagree" not in found["tp-eslint"]["evidence"]
    assert "version '16' is not semver" in found["tp-postgresql"]["evidence"] and "version '^4.19' is not semver" in found["tp-express"]["evidence"]
    assert "the steps disagree on the version" in found["tp-typescript"]["evidence"]


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


def checklist(host: Path, rel: str) -> list[dict]:
    return read(host, rel)["plan"]["spec_alignment"]["checklist"]


def test_plan_dispositions_removed_and_open_plan_item_becomes_open_item(migrated):
    host, _toolkit, _report = migrated
    plan = read(host, OPEN_PLAN)["plan"]
    assert "status" not in plan
    assert not {"checklist_status", "deferred_reason", "wont_do_reason"} & {key for item in checklist(host, OPEN_PLAN) for key in item}
    assert not [a for a in plan.get("ambiguities", []) if a["id"].startswith("amb-defer-")], "the script writes no open item into the plan"
    listed = {i["about"]: i for i in items(host, "plan-item-disposition")}
    assert set(listed) == {"RESERVE_SMS_01", "RESERVE_WAITLIST_01"}
    assert all(i["audience"] == "operator" and i["blocking"] is False for i in listed.values())
    assert "vendor contract is not signed" in listed["RESERVE_SMS_01"]["evidence"]
    assert "ambiguities" not in read(host, "14_roadmap.json")
    kept = [item for item in checklist(host, CLOSED_PLAN) if "checklist_status" in item]
    assert {item["id"] for item in kept} == {"CATALOG_IMPORT_01", "CATALOG_PRINT_01"}, "a closed plan keeps its history (P13)"


def test_exit_conditions_become_task_criteria_count_equal(migrated):
    host, _toolkit, _report = migrated
    legacy = [text for milestone in original("14_roadmap.json")["milestones"] for task in milestone["tasks"] for text in task.get("exit_conditions", []) if text]
    tasks = [task for milestone in read(host, "14_roadmap.json")["milestones"] for task in milestone["tasks"]]
    made = [c for task in tasks for c in task["acceptance_criteria"] if c["criterion_id"].startswith("tc-") and c["text"] in legacy]
    assert len(made) == len(legacy) == 3
    assert sorted(c["text"] for c in made) == sorted(legacy)
    assert all(set(c) == {"criterion_id", "text"} for c in made), "no refines, no verified_by is written"
    assert "exit_conditions" not in json.dumps(read(host, "14_roadmap.json"))
    assert len(items(host, "legacy-exit-condition")) == 3


def test_a_criterion_text_that_mentions_the_removed_field_does_not_fail_the_run(tmp_path):
    def mention(data: dict) -> None:
        data["milestones"][0]["tasks"][0]["acceptance_criteria"][0]["text"] += " (was listed under exit_conditions)"

    host, _toolkit, report = migrate(tmp_path, ("14_roadmap.json", mention))
    assert report.status == STATUS_OK
    assert "exit_conditions" in (host / "spec" / "14_roadmap.json").read_text(encoding="utf-8")


def test_a_dependency_written_as_a_sentence_becomes_one_item(tmp_path):
    def add_note(data: dict) -> None:
        data.setdefault("dependencies", []).append("The SMS vendor contract is signed before launch")

    host, _toolkit, report = migrate(tmp_path, ("09_impl_plan.json", add_note))
    assert report.status == STATUS_OK
    [note] = [i for i in items(host, "external-dependency") if i["about"].startswith("dependency-note-")]
    assert "The SMS vendor contract is signed before launch" in note["evidence"] and note["id"].endswith("-09")


def test_exit_conditions_script_runs_after_p3_from_capture(migrated, tmp_path):
    host, toolkit, _report = migrated
    spare = tmp_path / "spare"
    shutil.copytree(host, spare)
    roadmap = read(spare, "14_roadmap.json")
    for milestone in roadmap["milestones"]:
        for task in milestone["tasks"]:
            task["acceptance_criteria"] = [c for c in task["acceptance_criteria"] if c["text"] not in {
                "The migration runs on a fresh database without errors", "GET /tools answers 200 with a page of tools", "POST /reservations answers 201 and 409 as specified"}]
    worklist = read(spare, "extras/migration/worklist.json")
    worklist["items"] = [i for i in worklist["items"] if i["kind"] != "legacy-exit-condition"]
    for rel, data in (("14_roadmap.json", roadmap), ("extras/migration/worklist.json", worklist)):
        (spare / "spec" / rel).write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    ctx = context(spare, toolkit)
    assert p4_exit_conditions.detect(ctx) == 3
    assert p4_exit_conditions.apply(ctx).edits == 3
    ctx.documents.write()
    assert p4_exit_conditions.detect(context(spare, toolkit)) == 0
    assert len([c for m in read(spare, "14_roadmap.json")["milestones"] for t in m["tasks"] for c in t["acceptance_criteria"] if c["criterion_id"].startswith("tc-") and c["text"].startswith(("The migration runs", "GET /tools", "POST /reservations"))]) == 3


def test_plan_security_items_open_and_frozen(tmp_path):
    def add(document: dict) -> None:
        document["plan"]["security"] = {
            "status": "planned",
            "spec_mutations": [{"ref": {"type": "task", "id": "task-reserve-sms"}, "change": "Retry failed texts", "reason": "Found in the sandbox"}],
            "new_fixtures": ["fix-sms-retry"],
        }

    host, _toolkit, _report = migrate(tmp_path, (OPEN_PLAN, add))
    open_items = [a for a in read(host, OPEN_PLAN)["plan"]["ambiguities"] if a["description"].startswith(("Spec change the plan asked for", "Fixture the plan asked for"))]
    assert sorted(tuple(a["about"]) for a in open_items) == [("ms-reservations",), ("task-reserve-sms",)]
    frozen = items(host, "plan-security-item")
    assert len(frozen) == 2 and all(not i["blocking"] and "ms-catalog-basics" == i["about"] for i in frozen)
    # the item is about a fixture or a spec change, never an open item: no open-item rule and no `--id <item-id>` command
    assert all("E631" not in i["proposal"] and "<item-id>" not in i["proposal"] and "--step 08 .fixtures" in i["proposal"] for i in frozen)
    assert not any("asked for" in a["description"] for a in read(host, CLOSED_PLAN)["plan"].get("ambiguities", []))


# ---------------------------------------------------------------------------
# Ambiguities
# ---------------------------------------------------------------------------


def test_resolved_items_deleted_and_count_equals_probe(tmp_path):
    toolkit, host = make_toolkit(tmp_path), make_host(tmp_path)
    probe = sum(not is_open(item) for item in iter_ambiguity_items(str(host / "spec")))
    assert probe == 2
    report = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host)
    assert report.status == STATUS_OK
    assert f"resolved items deleted: {probe} in 1 file(s)" in residue_of(report, "p4_ambiguities")
    leftovers = [e for rel in (OPEN_PLAN, FROZEN_BY_STATUS, "16_impl_context.json") for e in (read(host, rel).get("plan", {}).get("ambiguities", []) + read(host, rel).get("execution", {}).get("emergent_ambiguities", [])) if e.get("status") == "resolved"]
    assert leftovers == []
    text = (host / "spec" / OPEN_PLAN).read_text(encoding="utf-8")
    assert "amb-pickup-cutoff" not in text and "amb-late-pickup" not in text


def test_resolved_deletion_keeps_the_indent_of_a_plan(tmp_path):
    toolkit, host = make_toolkit(tmp_path), make_host(tmp_path)
    path = host / "spec" / OPEN_PLAN
    path.write_text(json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "indent 2")
    assert runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host).status == STATUS_OK
    text = path.read_text(encoding="utf-8")
    assert text.startswith('{\n  "$schema"') and "amb-pickup-cutoff" not in text


def test_non_resolved_items_in_frozen_plan_become_informational(migrated):
    host, _toolkit, _report = migrated
    plan = read(host, FROZEN_BY_STATUS)
    assert plan["execution"]["emergent_ambiguities"] == []
    [item] = items(host, "legacy-open-item")
    assert item["about"] == "ms-late-fees" and item["blocking"] is False and item["audience"] == "operator"
    assert "amb-pickup-hours" in item["evidence"] and "fr-late-fee-calc" in item["evidence"], "the old impact is shown"


def test_anchor_items_convert_with_about_from_single_impact(migrated):
    host, _toolkit, _report = migrated
    anchor = {a["id"]: a for a in read(host, "16_impl_context.json")["plan"]["ambiguities"]}
    assert anchor["amb-fee-rounding"] == {"id": "amb-fee-rounding", "description": "It is not stated whether a part day owes a fee.", "about": ["fr-late-fee-calc"]}
    assert "impact" in anchor["amb-card-renewal"] and "about" not in anchor["amb-card-renewal"]
    [stuck] = [i for i in items(host, "ambiguity-about") if i["about"] == "amb-card-renewal"]
    assert stuck["audience"] == "operator" and stuck["blocking"] is True
    plan = read(host, OPEN_PLAN)
    ids = [a["id"] for a in plan["plan"]["ambiguities"] + plan["execution"]["emergent_ambiguities"]]
    assert len(ids) == len(set(ids)) and "amb-sms-retry-2" in ids, "a duplicate id inside one plan is renamed"
    assert {"id": "amb-sms-retry", "description": "How often a failed text is retried is not stated.", "about": ["task-reserve-sms"]} in plan["plan"]["ambiguities"]


# ---------------------------------------------------------------------------
# NFR verifiers
# ---------------------------------------------------------------------------


def test_nfr_without_fixture_yields_one_item(tmp_path):
    def mention(document: dict) -> None:
        document["jobs"][2]["name"] = "Unit tests and the nfr-search-latency timing"

    host, _toolkit, _report = migrate(tmp_path, ("12_ci_gates.json", mention))
    found = {i["about"]: i for i in items(host, "nfr-verifier")}
    assert set(found) == {"nfr-search-latency", "nfr-checkout-latency", "nfr-desk-availability"}
    assert len(items(host, "nfr-verifier")) == 3
    assert all(i["step"] == "12" and i["audience"] == "agent" for i in found.values())
    assert "gate-unit-tests" in found["nfr-search-latency"]["proposal"]
    assert "job" not in found["nfr-checkout-latency"]["proposal"].split("add a step-12 job")[0]


def test_nfr_with_fixture_yields_none_and_nothing_written(migrated):
    host, _toolkit, _report = migrated
    assert "nfr-fee-accuracy" not in {i["about"] for i in items(host, "nfr-verifier")}
    assert all("verifies" not in job for job in read(host, "12_ci_gates.json")["jobs"])


# ---------------------------------------------------------------------------
# What no script writes
# ---------------------------------------------------------------------------


def count_keys(value, names: tuple[str, ...]) -> int:
    if isinstance(value, dict):
        return sum(k in names for k in value) + sum(count_keys(v, names) for v in value.values())
    return sum(count_keys(v, names) for v in value) if isinstance(value, list) else 0


def test_no_script_writes_derives_from_or_verifies(tmp_path):
    toolkit, host = make_toolkit(tmp_path), make_host(tmp_path)
    upto_p3 = [s for s in registry.discover_scripts() if s.spec.phase <= registry.PHASE_SHAPES]
    assert runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=upto_p3).status == STATUS_OK
    names = ("derives_from", "verifies")

    def total() -> int:
        return sum(count_keys(json.loads(p.read_text(encoding="utf-8")), names) for p in (host / "spec").rglob("*.json"))

    before = total()
    for module in P4:
        ctx = context(host, toolkit)
        if module.detect(ctx):
            module.apply(ctx)
            ctx.documents.write()
    assert total() == before - 1, "the one key that goes is the derives_from of the external component that became a third party"
    assert all(module.detect(context(host, toolkit)) == 0 for module in P4)
    assert not [path.name for path in P4_FILES if re.search(r"\[\s*[\"'](derives_from|verifies)[\"']\s*\]\s*=", path.read_text(encoding="utf-8"))]


def test_the_scripts_are_discovered_with_their_ids():
    found = {script.id: script for script in registry.discover_scripts()}
    for module in P4:
        assert module.SCRIPT.id == Path(module.__file__).stem and found[module.SCRIPT.id].spec.phase == registry.PHASE_CONTENT


def test_a_second_run_changes_no_byte(tmp_path):
    host, toolkit, _report = migrate(tmp_path)
    before = tree_digest(host / "spec")
    again = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, allow_dirty=True)
    assert again.status in (STATUS_OK, "noop") and tree_digest(host / "spec") == before
