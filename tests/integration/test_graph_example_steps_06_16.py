"""The worked example (password reset) for steps 06-16 on the spec-graph shape.

Continues ``test_graph_example_steps_00_05.py`` on the same folder, ``tests/fixtures/graph_example/``: the eleven
files of steps 06-16 and the one plan file of ``spec/impl_context/``.  These tests pin that they are valid against
the real schemas, validators, registry and ``spec-check`` with a known set of warnings, that every link of the whole
folder (00-16) names an existing id of an allowed kind, and that the readers meant to stay silent on the new shape
(milestone state, upstream backlog, scope resolver, reviewer) do.

Two consumers are not run on the folder because they read no 1.1.1 field of a spec artifact: ``extraction-intent-check``
reads the prompts and ``tools/step_order.json`` only, and seed-lint reads the seed manifest and the seed
folder, never a field of an artifact.
"""
from __future__ import annotations

import fnmatch
import json
import shutil
from collections import Counter
from pathlib import Path

import _graph_example as shared
import pytest

from specdev_tools.analysis.upstream_backlog import run as run_upstream_backlog
from specdev_tools.context.reviewer import _run_structural_pass
from specdev_tools.context.scope_resolver import resolve_scope
from specdev_tools.core.changelog_parser import get_toolkit_version
from specdev_tools.core.schema_validate import validate_data_against_schema
from specdev_tools.validation.spec_check import run_spec_check_json
from specdev_tools.validation.validate import DEEP_VALIDATORS
from specdev_tools.validation.graph_checks.codes import GRAPH_CHECK_CODES
from unit.graph._synth import run_cli as _run_cli

_ROOT = shared.ROOT
_SPEC = shared.SPEC
_PLAN = "impl_context/ms_account_recovery_plan.json"
_BATCH_ID = "account_recovery"
_FILES_00_05 = (
    "00_charter.json",
    "01_capabilities.json",
    "02_system_sketch.json",
    "02a_delivery_baseline.json",
    "03_glossary.json",
    "04_fr_list.json",
    "05_interface_contracts.json",
)
_FILES_06_16 = (
    "06_invariants.json",
    "07_nfrs.json",
    "08_fixtures.json",
    "09_impl_plan.json",
    "10_governance.json",
    "11_redteam.json",
    "12_ci_gates.json",
    "13_extension_manifest.json",
    "14_roadmap.json",
    "15_scaffold.json",
    "16_impl_context.json",
    _PLAN,
)
_ALL_FILES = _FILES_00_05 + _FILES_06_16
_DEEP_STEPS = {
    "06_invariants.json": "06",
    "07_nfrs.json": "07",
    "08_fixtures.json": "08",
    "09_impl_plan.json": "09",
    "10_governance.json": "10",
    "11_redteam.json": "11",
    "12_ci_gates.json": "12",
    "13_extension_manifest.json": "13",
    "14_roadmap.json": "14",
    "15_scaffold.json": "15",
    "16_impl_context.json": "16",
    _PLAN: "16a",
}

_EXPECTED_KINDS: dict[str, dict[str, str]] = {
    "06_invariants.json": {"inv-reset-token-single-use": "invariant"},
    "07_nfrs.json": {"nfr-latency-reset-email": "nfr"},
    "08_fixtures.json": {
        "fix-password-reset-expired-token": "fixture",
        "fix-password-reset-reused-token": "fixture",
    },
    "09_impl_plan.json": {"milestone-account-recovery": "design-milestone"},
    "10_governance.json": {
        "rule-contract-tests-on-every-pr": "rule",
        "rule-spec-check-on-every-pr": "rule",
        "rule-security-review-of-token-handling": "rule",
    },
    "11_redteam.json": {"threat-reset-token-replay": "threat", "ec-token-at-expiry-second": "edge-case"},
    "12_ci_gates.json": {"job-contract-tests": "job"},
    "13_extension_manifest.json": {},  # extension_decision none-required: the manifest holds no node
    "14_roadmap.json": {
        "ms-account-recovery": "roadmap-milestone",
        "task-implement-password-reset-confirm": "task",
        "tc-confirm-expired-token": "task-criterion",
        "tc-confirm-reused-token": "task-criterion",
    },
    "15_scaffold.json": {"scaffold-password-reset-confirm": "scaffold-row"},
    "16_impl_context.json": {"anchor-ms-account-recovery": "anchor-row"},
    _PLAN: {"PWRESET_CONFIRM_EXPIRED_01": "plan-item"},
}

# Findings of spec-check on the whole folder, as (code, subject).  The subject is a needle in the rendered message:
# a file name, or the code's own name when no file is named.  No error appears, and no other warning.
_PINNED_FINDINGS = Counter(
    {
        # The seed has no out-of-scope section (only a prose line): the lint counts 0 of the 3 it expects.
        ("W555", "STEP00_SEED_OUT_OF_SCOPE_THIN"): 1,
        # The example restates its upstream in few words, so the token overlap stays under the threshold of 5.
        ("W594", "01_capabilities.json"): 1,
        ("W594", "03_glossary.json"): 1,
        ("W594", "06_invariants.json"): 1,
        ("W594", "08_fixtures.json"): 1,
        ("W594", "12_ci_gates.json"): 1,
        ("W594", "13_extension_manifest.json"): 1,
    }
)


def _validated(name: str) -> list[tuple[tuple, str]]:
    return validate_data_against_schema(str(_ROOT), shared.load(name))


@pytest.fixture(scope="module")
def stamped_example(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A copy of the example with the toolkit version stamped, so it follows every version bump."""
    copied = tmp_path_factory.mktemp("graph_example") / "graph_example"
    shutil.copytree(shared.EXAMPLE, copied)
    version = get_toolkit_version(_ROOT)
    (copied / "spec" / "specdev_version").write_text(json.dumps({"toolkit_version": version}), encoding="utf-8")
    return copied


# --- the files ------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", _FILES_06_16)
def test_file_validates_against_its_schema(name: str) -> None:
    assert _validated(name) == []


@pytest.mark.parametrize("name", sorted(_DEEP_STEPS))
def test_deep_validators_return_no_error(name: str) -> None:
    context = {"spec_root": str(_SPEC)}
    errors = DEEP_VALIDATORS[_DEEP_STEPS[name]](shared.load(name), str(_ROOT), context)
    assert [e.render() for e in errors if not e.code.startswith("W")] == []


@pytest.mark.parametrize("name", _FILES_06_16)
def test_registry_lists_the_expected_kinds(name: str) -> None:
    found = {node.node_id: node.kind for node in shared.nodes_of((name,))}
    assert found == _EXPECTED_KINDS[name]


def test_plan_file_matches_the_registry_glob_of_plan_files() -> None:
    registry = json.loads((_ROOT / "tools" / "entry_key_registry.json").read_text(encoding="utf-8"))["registry"]
    assert any(fnmatch.fnmatchcase(_PLAN, pattern) for pattern in registry)


def test_every_registry_file_of_the_example_is_present() -> None:
    assert {name for name in _EXPECTED_KINDS} == set(_FILES_06_16)


# --- the links of the whole folder ----------------------------------------------------------------


def _folder_nodes() -> list[shared.Node]:
    return shared.nodes_of(_ALL_FILES)


def _stored_targets(node: shared.Node, field: str) -> list[str]:
    value = node.item.get(field, [])
    return value if isinstance(value, list) else [value]


def test_node_ids_are_unique_across_the_example() -> None:
    ids = [node.node_id for node in _folder_nodes()]
    assert [i for i, n in Counter(ids).items() if n > 1] == []


def test_every_link_value_names_an_existing_id_of_an_allowed_kind() -> None:
    nodes = _folder_nodes()
    kind_of = {node.node_id: node.kind for node in nodes} | {shared.SEED_ID: "seed"}
    checked = Counter[str]()
    for node in nodes:
        for link in node.links:
            for target in _stored_targets(node, link["field"]):
                assert target in kind_of, f"{node.node_id}.{link['field']} -> unknown id {target}"
                if link["kinds"] != "*":
                    assert kind_of[target] in link["kinds"], (
                        f"{node.node_id}.{link['field']} -> {target} is a {kind_of[target]}"
                    )
                checked[node.kind] += 1
    linked_kinds = {node.kind for node in nodes if any(_stored_targets(node, link["field"]) for link in node.links)}
    assert {"invariant", "nfr", "fixture", "design-milestone", "rule", "threat", "edge-case", "job",
            "task-criterion", "scaffold-row", "anchor-row", "plan-item"} <= linked_kinds
    assert sum(checked.values()) > 0


def test_every_required_link_of_steps_06_16_is_present() -> None:
    for node in shared.nodes_of(_FILES_06_16):
        for link in node.links:
            if link["required"]:
                assert node.item.get(link["field"]), f"{node.node_id} has no {link['field']}"


def test_plan_file_names_a_roadmap_milestone() -> None:
    kind_of = {node.node_id: node.kind for node in _folder_nodes()}
    assert kind_of[shared.load(_PLAN)["milestone"]] == "roadmap-milestone"


# --- spec-check on the whole folder ---------------------------------------------------------------


def test_spec_check_finding_set_is_pinned(stamped_example: Path) -> None:
    spec_dir = str(stamped_example / "spec")
    errors, context = run_spec_check_json(
        str(_ROOT), spec_dir, spec_root=spec_dir, project_canon_dir=str(stamped_example / "spec" / "canon")
    )
    other = [e.render() for e in errors if not e.code.startswith("W") and e.code not in GRAPH_CHECK_CODES | {"E566", "E567"}]
    assert other == []  # the graph checks' findings on the example are pinned in test_graph_roles_example.py
    # the milestone numbers (M6c): the example is a partial spec, one FR has no task criterion (ruling C15)
    assert [(e.code, e.node_id, e.owner) for e in errors if e.code in ("E566", "E567")] == [("E566", "fr-password-reset-request", "step:14")]
    needles = [subject for _code, subject in _PINNED_FINDINGS]
    found = Counter(
        (e.code, next((n for n in needles if n in e.render()), "?")) for e in errors if e.code not in GRAPH_CHECK_CODES | {"E566", "E567"}
    )
    assert found == _PINNED_FINDINGS, [e.render() for e in errors]
    assert context["checks"]["schema-validation"]["status"] == "PASS"
    assert context["checks"]["canonical-integrity"]["status"] == "PASS"


# --- readers meant to stay silent on the new shape ------------------------------------------------


def test_coverage_by_fr_lists_both_frs_of_the_example(tmp_path: Path) -> None:
    """The FR view that ``specdev matrix`` gave comes from ``coverage --by fr``: both FRs, with their linked nodes."""
    code, out = _run_cli(
        "coverage", "--by", "fr", "--repo-root", str(_ROOT), "--spec-root", str(_SPEC), "--git-root", str(tmp_path),
    )
    assert code == 0
    assert [line.split()[0] for line in out.splitlines() if line.startswith("fr-")] == ["fr-password-reset", "fr-password-reset-request"]
    assert "api-password-reset-confirm (derives_from)" in out


def test_milestone_state_reads_the_plan_file(tmp_path: Path) -> None:
    code, out = _run_cli(
        "milestone-state", "--batch-id", _BATCH_ID, "--repo-root", str(_ROOT), "--spec-root", str(_SPEC),
        "--git-root", str(tmp_path),
    )
    state = json.loads(out)
    assert code == 0
    assert state["milestone_id"] == _BATCH_ID
    assert [(g["group_id"], g["state"]) for g in state["groups"]] == [("PWRESET_CONFIRM_EXPIRED_01", "pending")]
    assert state["derived_phase_position"] == "pending"
    assert state["blockers"] == []


def test_upstream_backlog_is_empty() -> None:
    stdout, stderr_lines, exit_code = run_upstream_backlog(str(_SPEC), repo_root=str(_ROOT))
    assert exit_code == 0
    assert stdout == "Totals: 0 items / 0 with answer / 0 needing answer."
    assert stderr_lines == []


def test_scope_resolver_finds_the_fr_and_its_lineage_but_not_its_sibling(tmp_path: Path) -> None:
    # `resolve_scope` writes nothing: neither the fixture folder nor the copy gains a trace matrix.
    spec = tmp_path / "spec"
    shutil.copytree(_SPEC, spec)
    before = {path: path.read_bytes() for path in spec.rglob("*") if path.is_file()}
    scope = resolve_scope("fr-password-reset", str(spec), str(_ROOT))
    assert not (_SPEC / "extras" / "trace_matrix.json").exists()
    assert {path: path.read_bytes() for path in spec.rglob("*") if path.is_file()} == before
    assert not scope.get("errors")
    assert scope["resolved_ids"]["fr"] == ["fr-password-reset"]
    assert "cap-account-recovery" in scope["resolved_ids"]["capability"]
    assert "fr-password-reset-request" not in scope["source_files"]


def test_structural_reviewer_finds_nothing_to_report() -> None:
    review = _run_structural_pass(shared.load("05_interface_contracts.json"), "", [("", shared.load("04_fr_list.json"))])
    assert review.upstream_coverage == {"covered": [], "dropped": []}
    assert review.reverse_trace == {"unjustified": [], "scope_creep": []}
