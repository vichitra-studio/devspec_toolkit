"""The mini host `tests/fixtures/migration/mini_host_1_1_1/`: every shape its README claims is present.

One assertion per claimed shape (`F01` to `F36` of the README table), looked up by key or value, plus the
README's own file table and the file styles it names.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "migration" / "mini_host_1_1_1"
README = FIXTURE / "README.md"

STEP_FILES = {
    "00": ["00_charter"],
    "01": ["01_capabilities"],
    "02": ["02_system_sketch"],
    "02a": ["02a_delivery_baseline"],
    "04": ["04_fr_list"],
    "05": ["05_interface_contracts"],
    "06": ["06_invariants"],
    "07": ["07_nfrs"],
    "08": ["08_fixtures"],
    "09": ["09_impl_plan"],
    "10": ["10_governance"],
    "11": ["11_redteam"],
    "12": ["12_ci_gates"],
    "13a": ["13a_completeness_assessment"],
    "14": ["14_roadmap"],
    "15": ["15_scaffold"],
    "16_anchor": ["16_impl_context"],
    "16_impl_context": ["impl_context/ms_catalog_plan", "impl_context/ms_reservations_plan", "impl_context/ms_late_fees_plan"],
}

# Kind `remove` rows of tools/schema_changes.json that a 1.1.1 host can carry and this fixture carries (step, path).
COVERED_PATHS = [
    ("00", "in_scope"),
    ("00", "out_of_scope"),
    ("00", "links"),
    ("00", "seed_refs_ingested"),
    ("01", "capabilities[].goal_id"),
    ("01", "capabilities[].success_metric_refs"),
    ("01", "capabilities[].trace"),
    ("02", "components[].trace"),
    ("02", "connections[].from"),
    ("02", "connections[].to"),
    ("02", "connections[].schema_ref"),
    ("02", "connections[].interface_ref"),
    ("02", "connections[].trace"),
    ("02", "tech_stack"),
    ("02", "spec_refs_ingested"),
    ("02a", "trace"),
    ("04", "functional_requirements[].trace"),
    ("04", "spec_refs_ingested"),
    ("04", "seed_refs_ingested"),
    ("05", "apis[].example_refs"),
    ("05", "apis[].trace"),
    ("05", "out_of_scope"),
    ("14", "spec_refs_ingested"),
    ("14", "seed_refs_ingested"),
    ("14", "trace"),
    ("14", "tech_stack"),
    ("14", "tech_stack_ref"),
    ("14", "dependencies"),
    ("14", "dependency_ref"),
    ("14", "milestones[].status"),
    ("14", "milestones[].milestone_status_reason"),
    ("14", "milestones[].source_milestones"),
    ("14", "milestones[].fr_refs"),
    ("14", "milestones[].capability_refs"),
    ("14", "milestones[].deliverables"),
    ("14", "milestones[].tasks[].status"),
    ("14", "milestones[].tasks[].status_reason"),
    ("14", "milestones[].tasks[].assumptions"),
    ("14", "milestones[].tasks[].exit_conditions"),
    ("14", "milestones[].tasks[].fr_refs"),
    ("14", "milestones[].tasks[].invariant_refs"),
    ("14", "milestones[].tasks[].acceptance_criteria[].fixture_ref"),
    ("06", "rules[].trace"),
    ("07", "nfrs[].trace"),
    ("08", "fixtures[].targets"),
    ("08", "out_of_scope"),
    ("09", "tech_stack"),
    ("09", "tech_stack_ref"),
    ("09", "trace"),
    ("09", "dependencies"),
    ("09", "dependency_ref"),
    ("09", "milestones[].status"),
    ("09", "milestones[].deliverables"),
    ("09", "milestones[].depends_on"),
    ("10", "pr_rules"),
    ("10", "spec_first_policy"),
    ("10", "review_policy"),
    ("10", "reviewers"),
    ("10", "trace"),
    ("10", "links"),
    ("11", "trace"),
    ("11", "threats[].target_ids"),
    ("11", "threats[].mitigations"),
    ("12", "trace"),
    ("12", "jobs[].requires"),
    ("12", "jobs[].steps[].id"),
    ("15", "trace"),
    ("15", "links"),
    ("15", "interface_map[].interface_ref"),
    ("15", "interface_map[].method"),
    ("16_anchor", "plan.milestone_index[].milestone_id"),
    ("16_anchor", "plan.milestone_index[].context_path"),
    ("16_anchor", "plan.milestone_index[].fr_refs"),
    ("16_impl_context", "plan.status"),
    ("16_impl_context", "plan.coverage_status"),
    ("16_impl_context", "plan.spec_alignment.checklist[].spec_ref"),
    ("16_impl_context", "plan.spec_alignment.checklist[].milestone_ref"),
    ("16_impl_context", "plan.spec_alignment.checklist[].nfr_refs"),
    ("16_impl_context", "plan.spec_alignment.checklist[].fixture_ref"),
    ("16_impl_context", "plan.spec_alignment.checklist[].checklist_status"),
    ("16_impl_context", "plan.spec_alignment.checklist[].deferred_reason"),
    ("16_impl_context", "plan.spec_alignment.checklist[].wont_do_reason"),
    ("16_impl_context", "plan.spec_alignment.checklist[].linked_test_expectation"),
    ("16_impl_context", "plan.spec_alignment.checklist[].implementation.status"),
    ("16_impl_context", "plan.spec_alignment.requirements_summary[].spec_refs"),
    ("16_impl_context", "plan.security.new_fixtures"),
    ("16_impl_context", "plan.security.spec_mutations"),
    ("16_impl_context", "execution.execution_results"),
    ("16_impl_context", "execution.critical_evidence"),
    ("16_impl_context", "review.fixture_status"),
    ("16_impl_context", "review.semantic_review.fr_coverage"),
    ("16_impl_context", "extensions.review_state"),
    ("16_impl_context", "review.findings[].spec_ref.line_range"),
    ("16_impl_context", "review.findings[].spec_ref.commit_hash"),
    ("16_impl_context", "execution.final_status"),
    ("16_impl_context", "plan.spec_alignment.checklist[].implementation.actions[].evidence"),
]


def _json(rel: str):
    return json.loads((FIXTURE / rel).read_text(encoding="utf-8"))


def _spec(name: str):
    return _json(f"spec/{name}.json")


def _plan(name: str):
    return _json(f"spec/impl_context/ms_{name}_plan.json")


def _has(node, path: str) -> bool:
    """True when the key path (`a[].b.c`, `[]` walks every list item) exists below `node`."""
    head, _, rest = path.partition(".")
    is_list = head.endswith("[]")
    key = head[:-2] if is_list else head
    if not isinstance(node, dict) or key not in node:
        return False
    value = node[key]
    if is_list:
        if not isinstance(value, list):
            return False
        return any(_has(item, rest) for item in value) if rest else bool(value)
    return _has(value, rest) if rest else True


def _walk(node):
    """Every dict below `node`, `node` first."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _checklist(plan: dict) -> list[dict]:
    return plan["plan"]["spec_alignment"]["checklist"]


def _tasks() -> list[dict]:
    return [t for m in _spec("14_roadmap")["milestones"] for t in m["tasks"]]


def _amb_ids(plan: dict) -> tuple[set[str], set[str]]:
    plan_ids = {a["id"] for a in plan["plan"].get("ambiguities", [])}
    emergent_ids = {a["id"] for a in plan["execution"].get("emergent_ambiguities", [])}
    return plan_ids, emergent_ids


def _style(rel: str) -> tuple[int, bool]:
    text = (FIXTURE / rel).read_text(encoding="utf-8")
    first_indent = next(len(line) - len(line.lstrip()) for line in text.splitlines() if line.startswith(" "))
    return first_indent, text.endswith("\n")


# ----- the shape checks: one function per README id -----


def f01():
    assert len(COVERED_PATHS) == 96


def f02():
    for plan in (_plan("catalog"), _plan("reservations"), _plan("late_fees")):
        for item in _checklist(plan):
            assert {"milestone_ref", "nfr_refs", "fixture_ref"} <= item.keys()
    roadmap = _spec("14_roadmap")
    for milestone in roadmap["milestones"]:
        assert {"fr_refs", "capability_refs", "deliverables", "source_milestones"} <= milestone.keys()
    assert any("invariant_refs" in t for t in _tasks())
    assert all("fr_refs" in t for t in _tasks())
    assert all("fr_refs" in row for row in _spec("16_impl_context")["plan"]["milestone_index"])


def f03():
    anchor_text = (FIXTURE / "spec/16_impl_context.json").read_text(encoding="utf-8")
    assert "status_ref" in anchor_text
    assert not any("status_ref" in node for step in STEP_FILES.values() for rel in step for node in _walk(_json(f"spec/{rel}.json")))
    variant = _json("variants/status_ref_1_0_x/04_fr_list.json")
    assert any("status_ref" in fr for fr in variant["functional_requirements"])


def _criteria(doc_frs: list[dict]) -> dict[str, str]:
    return {c["criterion_id"]: c["text"] for fr in doc_frs for c in fr["acceptance_criteria"]}


def _task_criteria() -> dict[str, str]:
    return {c["criterion_id"]: c["text"] for t in _tasks() for c in t["acceptance_criteria"]}


def _criterion_collision(criterion_id: str):
    in_04 = _criteria(_spec("04_fr_list")["functional_requirements"])
    in_14 = _task_criteria()
    assert criterion_id in in_04 and criterion_id in in_14
    assert in_04[criterion_id] != in_14[criterion_id]


def f04():
    _criterion_collision("ac-catalog-search-1")


def f05():
    _criterion_collision("ac-reserve-tool-1")


def f06():
    in_09 = {m["milestone_id"] for m in _spec("09_impl_plan")["milestones"]}
    in_14 = {m["milestone_id"] for m in _spec("14_roadmap")["milestones"]}
    assert "ms-late-fees" in in_09 & in_14


def f07():
    assert any(item["milestone_ref"] == "ms-late-fees" for item in _checklist(_plan("late_fees")))
    assert any(row["milestone_id"] == "ms-late-fees" for row in _spec("16_impl_context")["plan"]["milestone_index"])


def f08():
    descriptions = " ".join(item["description"] for plan in (_plan("catalog"), _plan("reservations")) for item in _checklist(plan))
    assert "`ac-catalog-search-1`" in descriptions
    assert "`ac-reserve-tool-1`" in descriptions


def f09():
    charter = _spec("00_charter")
    assert all(isinstance(x, str) for key in ("in_scope", "out_of_scope", "assumptions", "risks") for x in charter[key])
    assert all("id" not in s and "stakeholder_id" not in s for s in charter["stakeholders"])
    baseline = _spec("02a_delivery_baseline")
    assert all(isinstance(x, str) for x in baseline["ci_gates"] + baseline["secrets"])
    assert all("error_id" not in e for api in _spec("05_interface_contracts")["apis"] for e in api["errors"])
    assert all(isinstance(x, str) for x in _spec("10_governance")["pr_rules"])


def f10():
    tasks = _tasks()
    assert any("fr_refs" in t for t in tasks)
    assert any("invariant_refs" in t for t in tasks)
    assert any(t.get("depends_on") for t in tasks)
    assert any(t.get("status_reason") for t in tasks)


def f11():
    plan = _plan("reservations")
    for items in (plan["plan"]["ambiguities"], plan["execution"]["emergent_ambiguities"]):
        assert {"resolved", "tracking", "deferred"} <= {a["status"] for a in items}


def f12():
    plan_ids, emergent_ids = _amb_ids(_plan("reservations"))
    assert "amb-sms-retry" in plan_ids & emergent_ids
    anchor_ids = {a["id"] for a in _spec("16_impl_context")["plan"]["ambiguities"]}
    assert "amb-fee-rounding" in anchor_ids & plan_ids
    assert "amb-pickup-hours" in emergent_ids & _amb_ids(_plan("late_fees"))[1]


def f13():
    values = [item["linked_test_expectation"] for plan in (_plan("catalog"), _plan("reservations"), _plan("late_fees")) for item in _checklist(plan)]
    assert any(isinstance(v, list) for v in values)
    strings = [v for v in values if isinstance(v, str)]
    assert any(v.startswith(("npm ", "npx ", "bash ")) for v in strings)
    assert any(not v.startswith(("npm ", "npx ", "bash ", "pytest ")) and " " in v for v in strings)


def f14():
    actions = [a for plan in (_plan("catalog"), _plan("reservations"), _plan("late_fees")) for item in _checklist(plan)
               for a in item.get("implementation", {}).get("actions", [])]
    assert actions and all("id" not in a for a in actions)


def f15():
    statuses = {m["milestone_id"]: m["status"] for m in _spec("14_roadmap")["milestones"]}
    rows = {r["milestone_id"]: r["status"] for r in _spec("16_impl_context")["plan"]["milestone_index"]}
    design = {m["milestone_id"]: m["status"] for m in _spec("09_impl_plan")["milestones"]}
    assert statuses["ms-late-fees"] == "done" and rows["ms-late-fees"] == "pending" and design["ms-late-fees"] == "pending"
    by_milestone = {m["milestone_id"]: {t["task_id"]: t["status"] for t in m["tasks"]} for m in _spec("14_roadmap")["milestones"]}
    assert by_milestone["ms-reservations"]["task-checkout-return-flow"] == "done" and statuses["ms-reservations"] == "pending"
    assert by_milestone["ms-catalog-basics"]["task-catalog-import"] == "pending" and statuses["ms-catalog-basics"] == "done"
    assert _spec("16_impl_context")["plan"]["ambiguities"]


def f16():
    assert {n["stage"] for n in _spec("07_nfrs")["nfrs"]} == {"dev", "staging", "prod"}


def f17():
    sketch = _spec("02_system_sketch")
    external = [c for c in sketch["components"] if c["type"] == "external"]
    assert external and "external-dependency" in external[0]["tags"]
    for name in ("02_system_sketch", "09_impl_plan", "14_roadmap"):
        assert "tech_stack" in _spec(name)
    versions = {e["name"]: e["version"] for group in sketch["tech_stack"].values() for e in group}
    later = {e["name"]: e["version"] for group in _spec("09_impl_plan")["tech_stack"].values() for e in group}
    assert versions["TypeScript"] != later["TypeScript"]
    assert later["ESLint"] == "Built-in"
    for name in ("09_impl_plan", "14_roadmap"):
        assert any(d["type"] == "external" for d in _spec(name)["dependencies"])


def f18():
    assert _spec("00_charter")["assumptions"]
    assert any(t.get("assumptions") for t in _tasks())


def f19():
    ids = set(re.findall(r"`([a-z]+-[a-z0-9-]+)`", " ".join(item["description"] for item in _checklist(_plan("catalog")))))
    defined = {fr["fr_id"] for fr in _spec("04_fr_list")["functional_requirements"]}
    assert "fr-catalog-search" in ids & defined
    assert "fr-catalog-wishlist" in ids - defined


def f20():
    names = sorted(p.relative_to(FIXTURE).as_posix() for p in (FIXTURE / "spec").rglob("*.json") if "canon" not in p.parts)
    styles = {n: _style(n) for n in names}
    assert sum(1 for s in styles.values() if s == (4, True)) >= len(styles) - 3
    assert styles["spec/08_fixtures.json"] == (2, True)
    assert styles["spec/15_scaffold.json"][1] is False
    governance = (FIXTURE / "spec/10_governance.json").read_text(encoding="utf-8")
    assert re.search(r'"pr_rules": \["[^\]\n]+"\]', governance)
    assert any(ord(ch) > 127 for ch in (FIXTURE / "spec/00_charter.json").read_text(encoding="utf-8"))
    assert '\\u' not in (FIXTURE / "spec/00_charter.json").read_text(encoding="utf-8")


def f21():
    manifest = _json("spec/common/seed_manifest.json")
    assert all((FIXTURE / seed["path"]).is_file() for seed in manifest["seeds"])
    assert not any((FIXTURE / "spec" / seed["path"]).exists() for seed in manifest["seeds"])
    ids = {s["seed_id"] for s in manifest["seeds"]}
    assert "seed-decision-clarifications" in ids
    routed = {s for seeds in manifest["step_requirements"].values() for s in seeds}
    assert ids - routed


def f22():
    text = (FIXTURE / "spec/specdev_version").read_text(encoding="utf-8")
    assert re.search(r"^toolkit_version: 1\.1\.1$", text, re.M)
    assert re.search(r"^migration_history: \[\]$", text, re.M)


def f23():
    for kind in ("interface", "dependency", "inv"):
        assert (FIXTURE / f"spec/canon/kinds/{kind}.json").is_file()
        entries = _json(f"spec/canon/kinds/{kind}.json")["entries"]
        assert all(e["kind"] == kind for e in entries)
    manifest_kinds = {e["kind"] for e in _json("spec/canon/manifest.json")["entries"]}
    assert {"interface", "dependency", "inv"} <= manifest_kinds


def f24():
    assert (FIXTURE / "spec/13a_completeness_assessment.json").is_file()
    assert (FIXTURE / "spec/extras/trace_matrix.json").is_file()


def f25():
    closed = _plan("catalog")
    assert closed["review"]["verdict"] == "verified"
    assert "review" not in _plan("late_fees")
    assert "review" not in _plan("reservations")
    assert all("milestone" not in _plan(n) for n in ("catalog", "reservations", "late_fees"))


def f26():
    jobs = {j["job_id"]: j for j in _spec("12_ci_gates")["jobs"]}
    commands = " ".join(s["command"] for s in jobs["gate-go-live-staging-teardown"]["steps"])
    assert "smoke" in commands and "delete_staging" in commands and "migrate" in commands


def f27():
    rules = _spec("10_governance")["pr_rules"]
    assert {"validate-all", "matrix", "governance-check", "fixtures-lint", "test", "lint"} <= set(rules)


def f28():
    plan = _plan("catalog")
    assert plan["execution"]["execution_results"][0]["evidence_binding"]
    assert {"critical_evidence", "final_status"} <= plan["execution"].keys()
    assert {"fixture_status", "semantic_review"} <= plan["review"].keys()
    assert plan["plan"]["security"]["spec_mutations"] and plan["plan"]["security"]["new_fixtures"]
    assert "review_state" in plan["extensions"]
    assert all({"line_range", "commit_hash"} <= item["spec_ref"].keys() for item in _checklist(plan))


def f29():
    for name in ("catalog", "reservations"):
        items = _checklist(_plan(name))
        deferred = [i for i in items if i.get("checklist_status") == "deferred"]
        wont_do = [i for i in items if i.get("checklist_status") == "wont_do"]
        assert deferred and all(i["deferred_reason"] for i in deferred)
        assert wont_do and all(i["wont_do_reason"] for i in wont_do)


def f30():
    environments = _spec("02a_delivery_baseline")["environments"]
    assert environments["staging"]["lifecycle"] == "decommissioned-at-production-go-live"
    assert "ghost_port" in environments["prod"]


def f31():
    assert any(api["method"] == "DELETE" for api in _spec("05_interface_contracts")["apis"])


def f32():
    workflow = (FIXTURE / ".github/workflows/spec_validation.yml").read_text(encoding="utf-8")
    assert "specdev validate-all" in workflow and "specdev matrix" in workflow
    assert "specdev spec-check" in (FIXTURE / ".pre-commit-config.yaml").read_text(encoding="utf-8")


def f33():
    fixtures = _spec("08_fixtures")["fixtures"]
    assert any(t["type"] == "fr" for f in fixtures for t in f["targets"])
    commands: dict[str, set[str]] = {}
    for plan in (_plan("catalog"), _plan("reservations"), _plan("late_fees")):
        for item in _checklist(plan):
            if isinstance(item["linked_test_expectation"], str):
                commands.setdefault(item["linked_test_expectation"], set()).add(item["fixture_ref"])
    assert any(len(refs) >= 2 for refs in commands.values())
    named = {item["fixture_ref"] for plan in (_plan("catalog"), _plan("reservations"), _plan("late_fees")) for item in _checklist(plan)}
    assert {f["fixture_id"] for f in fixtures} - named
    targeted = {t["id"] for f in fixtures for t in f["targets"] if t["type"] == "nfr"}
    nfrs = {n["nfr_id"] for n in _spec("07_nfrs")["nfrs"]}
    assert targeted and nfrs - targeted


def f34():
    assert any("exit_conditions" in t for t in _tasks())
    assert any("fixture_ref" in c for t in _tasks() for c in t["acceptance_criteria"])


def f35():
    rows = _spec("16_impl_context")["plan"]["milestone_index"]
    assert all({"milestone_id", "context_path"} <= row.keys() and "anchor_id" not in row for row in rows)
    stems = {Path(row["context_path"]).name: row["milestone_id"] for row in rows}
    assert stems["ms_catalog_plan.json"] == "ms-catalog-basics"
    assert all((FIXTURE / row["context_path"]).is_file() for row in rows)


def f36():
    threats = _spec("11_redteam")["threats"]
    assert any(m["type"] == "capability" for t in threats for m in t["mitigations"])


SHAPE_CHECKS = {f"F{i:02d}": fn for i, fn in enumerate(
    [f01, f02, f03, f04, f05, f06, f07, f08, f09, f10, f11, f12, f13, f14, f15, f16, f17, f18, f19, f20,
     f21, f22, f23, f24, f25, f26, f27, f28, f29, f30, f31, f32, f33, f34, f35, f36], start=1)}


# ----- the tests -----


def _readme_tables() -> tuple[list[str], list[str]]:
    text = README.read_text(encoding="utf-8")
    files_part = text.split("## Files", 1)[1].split("## Shapes", 1)[0]
    shapes_part = text.split("## Shapes", 1)[1].split("### Removed-field rows", 1)[0]
    return files_part.splitlines(), shapes_part.splitlines()


def _named_files() -> set[str]:
    named: set[str] = set()
    lines, _ = _readme_tables()
    for line in lines:
        if not line.startswith("| `"):
            continue
        cell = line.split("|")[1]
        paths = re.findall(r"`([^`]+)`", cell)
        base = paths[0].rsplit("/", 1)[0] + "/" if "/" in paths[0] else ""
        for path in paths:
            named.add(path if "/" in path or not base else base + path)
    return named


def test_every_json_file_loads():
    for path in FIXTURE.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))


def test_the_readme_table_names_every_file():
    on_disk = {p.relative_to(FIXTURE).as_posix() for p in FIXTURE.rglob("*") if p.is_file()} - {"README.md"}
    assert _named_files() == on_disk


def test_the_readme_shape_ids_are_the_asserted_ids():
    _, lines = _readme_tables()
    claimed = {m.group(1) for line in lines if (m := re.match(r"\| (F\d\d) \|", line))}
    assert claimed == set(SHAPE_CHECKS)


@pytest.mark.parametrize("shape_id", sorted(SHAPE_CHECKS))
def test_the_claimed_shape_is_present(shape_id):
    SHAPE_CHECKS[shape_id]()


@pytest.mark.parametrize(("step", "path"), COVERED_PATHS)
def test_the_removed_field_is_present(step, path):
    assert any(_has(_json(f"spec/{rel}.json"), path) for rel in STEP_FILES[step])


def test_a_copy_becomes_a_git_repository(tmp_path):
    copy = tmp_path / "host"
    shutil.copytree(FIXTURE, copy)
    (copy / "README.md").unlink()
    git = ["git", "-c", "user.email=fixture@example.org", "-c", "user.name=fixture"]
    subprocess.run([*git, "init", "-q", "-b", "main"], cwd=copy, check=True)
    subprocess.run([*git, "add", "-A"], cwd=copy, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "baseline"], cwd=copy, check=True)
    status = subprocess.run([*git, "status", "--porcelain"], cwd=copy, check=True, capture_output=True, text=True)
    assert status.stdout == ""
    assert (copy / "spec/15_scaffold.json").read_bytes() == (FIXTURE / "spec/15_scaffold.json").read_bytes()
