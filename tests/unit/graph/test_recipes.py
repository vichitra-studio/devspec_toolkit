"""Tests for the context packs of ``specdev trace --recipe`` (WI-M4-09): the recipe table, the engine, the packs of the
worked example, the two reports and the findings (E706, E707, E520)."""
from __future__ import annotations

import copy
import json
import shutil
from collections import deque
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.contract import item_at
from specdev_tools.graph.gitview import PREVIOUS_COMMIT, Snapshot, default_base_ref
from specdev_tools.graph.model import LIFECYCLES, NOT_APPLICABLE, Graph
from specdev_tools.graph.recipes import (
    DEPENDENCY,
    DependencyReport,
    GitContext,
    Hop,
    Pack,
    RecipeError,
    RecipeTable,
    _apply,
    build_pack,
    compare_dependencies,
    load_recipes,
    pack_to_dict,
    parse_recipes,
    render_text,
)

from ._synth import EXAMPLE_SPEC, ROOT
from ._synth import git as _git
from ._builders import _raw, _section, _set, _core_16b

START_16B = "PWRESET_CONFIRM_EXPIRED_01"
START_16A = "task-implement-password-reset-confirm"
START_16C = "ms-account-recovery"
STARTS = {"16a": START_16A, "16b": START_16B, "16c": START_16C}
PLAN_FILE = "impl_context/ms_account_recovery_plan.json"
VERIFICATION_RECORD = "ver-password-reset-expired-token"
EVIDENCE_FILE = "extras/verification/evd-attest-expired-token.json"
EVIDENCE_RECORD = "evd-attest-expired-token"
SKETCH_FILE = "02_system_sketch.json"
WRONG_VALUES = [None, 5, True, [], {}, ["x"]]


@pytest.fixture(scope="module")
def table() -> RecipeTable:
    return load_recipes(str(ROOT))


@pytest.fixture(scope="module")
def example() -> Graph:
    return build_graph(str(EXAMPLE_SPEC), str(ROOT))


def _sections(pack: Pack) -> dict[str, set[str]]:
    return {name: {entry.id for entry in entries} for name, entries in pack.sections.items()}


def _rebuilt(graph: Graph, edits: Mapping[str, Callable[[dict[str, Any]], None]]) -> Graph:
    """The example graph with each node of *edits* (id -> mutation of its item) changed in a copy of its document."""
    docs: dict[str, Any] = {}
    for node_id, mutate in edits.items():
        node = graph.by_id[node_id]
        document = docs.setdefault(node.file, copy.deepcopy(graph.documents[node.file]))
        item = item_at(document, node.jq_path)
        assert item is not None
        mutate(item)
    return build_graph(str(EXAMPLE_SPEC), str(ROOT), overrides=docs)


def _with_docs(graph: Graph, edits: Mapping[str, Callable[[dict[str, Any]], None]]) -> Graph:
    """The example graph with each document of *edits* (file -> mutation of the whole document) changed in a copy."""
    docs = {}
    for file, mutate in edits.items():
        docs[file] = copy.deepcopy(graph.documents.get(file, {}))
        mutate(docs[file])
    return build_graph(str(EXAMPLE_SPEC), str(ROOT), overrides=docs)


# --- the packs of the worked example --------------------------------------------------------------------------------

def test_pack_16a_adds_needs_and_assumptions(example: Graph, table: RecipeTable) -> None:
    sections = _sections(build_pack(example, table, "16a", START_16A))
    assert sections["needs"] == {"need-fewer-reset-tickets"}
    assert sections["assumptions"] == {"asm-member-controls-email"}
    assert {"need-fewer-reset-tickets", "sh-support-lead", "seg-registered-member", "risk-reset-link-takeover"} <= sections["lineage"]
    assert sections["core criteria"] == {"tc-confirm-expired-token", "tc-confirm-reused-token", "ms-account-recovery"}
    assert sections["obligations"] == {"ac-password-reset-3", "fr-password-reset", "inv-reset-token-single-use"}
    assert {"identity-service", "contract-tests", "ci"} <= sections["delivery"]
    assert sections["verifiers"] == {"fix-password-reset-expired-token", "fix-password-reset-reused-token", VERIFICATION_RECORD}


def _attestation_about(node_id: str) -> dict[str, Any]:
    return {
        "$schema": "vc:extras:evidence-record",
        "records": [{"evidence_id": EVIDENCE_RECORD, "type": "attestation", "about": [node_id], "tested_tree": "9a41c7e2"}],
    }


def test_verifier_section_places_the_verification_and_evidence_kinds(example: Graph, table: RecipeTable) -> None:
    placed = {
        role: {kind for section in table.sections if section.name == "verifiers" and role in section.roles for kind in section.emitted_kinds}
        for role in ("16a", "16b", "16c")
    }
    assert placed == {
        "16a": {"fixture", "job", "verification-record"},
        "16b": {"fixture", "job", "verification-record"},
        "16c": {"fixture", "job", "verification-record", "evidence-record"},
    }
    graph = _with_docs(example, {EVIDENCE_FILE: lambda document: document.update(_attestation_about("fix-password-reset-expired-token"))})
    assert graph.by_id[EVIDENCE_RECORD].kind == "evidence-record"
    verifiers = {role: _sections(build_pack(graph, table, role, STARTS[role]))["verifiers"] for role in STARTS}
    assert VERIFICATION_RECORD in verifiers["16a"] and VERIFICATION_RECORD in verifiers["16b"]
    assert EVIDENCE_RECORD not in verifiers["16a"] | verifiers["16b"]
    assert {VERIFICATION_RECORD, EVIDENCE_RECORD} <= verifiers["16c"]


def _binding_evidence(binding_id: str) -> dict[str, Any]:
    return {
        "$schema": "vc:extras:evidence-record",
        "records": [{"evidence_id": EVIDENCE_RECORD, "type": "attestation", "about": [binding_id], "tested_tree": "9a41c7e2"}],
    }


def test_apply_expands_a_record_node_for_a_record_kind_hop(example: Graph, table: RecipeTable) -> None:
    graph = _with_docs(example, {EVIDENCE_FILE: lambda document: document.update(_binding_evidence(VERIFICATION_RECORD))})
    binding = graph.by_id[VERIFICATION_RECORD]
    hop = Hop("about", "in", frozenset({"evidence-record"}))
    known = {binding.id: binding}
    reached: dict[str, Any] = {}
    added = _apply(graph, hop, [binding], known, reached)
    assert [node.id for node in added] == [EVIDENCE_RECORD]
    assert reached[EVIDENCE_RECORD].source_id == VERIFICATION_RECORD
    assert EVIDENCE_RECORD in _sections(build_pack(graph, table, "16c", START_16C))["verifiers"]


@pytest.mark.parametrize("kinds", [frozenset({"fixture"}), frozenset()], ids=["non-record kind", "any kind"])
def test_apply_does_not_expand_a_record_node_for_other_hops(example: Graph, kinds: frozenset[str]) -> None:
    graph = _with_docs(example, {EVIDENCE_FILE: lambda document: document.update(_binding_evidence(VERIFICATION_RECORD))})
    binding = graph.by_id[VERIFICATION_RECORD]
    known = {binding.id: binding}
    assert _apply(graph, Hop("about", "in", kinds), [binding], known, {}) == []
    assert list(known) == [VERIFICATION_RECORD]


def test_pack_16b_has_neither_needs_nor_segments(example: Graph, table: RecipeTable) -> None:
    pack = build_pack(example, table, "16b", START_16B)
    assert "needs" not in pack.sections
    assert _sections(pack)["lineage"] == {"fr-password-reset", "cap-account-recovery", "scope-password-reset"}


def test_pack_16c_milestone_scope(example: Graph, table: RecipeTable) -> None:
    sections = _sections(build_pack(example, table, "16c", START_16C))
    assert sections["core criteria"] == {
        "task-implement-password-reset-confirm",
        "tc-confirm-expired-token",
        "tc-confirm-reused-token",
        "PWRESET_CONFIRM_EXPIRED_01",
        "anchor-ms-account-recovery",
        "milestone-account-recovery",
    }
    assert {"identity-service", "contract-tests"} <= sections["delivery"]
    assert sections["verifiers"] == {"fix-password-reset-expired-token", "fix-password-reset-reused-token", VERIFICATION_RECORD}
    assert "assumptions" not in sections and "needs" not in sections


@pytest.mark.parametrize(
    ("role", "start_id", "code", "words"),
    [
        ("16b", START_16A, "E707", ("plan-item", "task")),
        ("16a", START_16B, "E707", ("task", "plan-item")),
        ("16c", START_16A, "E707", ("roadmap-milestone", "task")),
        ("17z", START_16B, "E706", ("16a", "16b", "16c")),
        ("16b", "PWRESET_NO_SUCH_01", "E706", ("PWRESET_NO_SUCH_01",)),
    ],
    ids=["16b-from-task", "16a-from-plan-item", "16c-from-task", "unknown-role", "unknown-id"],
)
def test_wrong_start_kind_e707(
    example: Graph, table: RecipeTable, role: str, start_id: str, code: str, words: tuple[str, ...]
) -> None:
    with pytest.raises(RecipeError) as raised:
        build_pack(example, table, role, start_id)
    assert raised.value.error.code == code
    assert all(word in raised.value.error.message for word in words)


def test_expand_includes_content(example: Graph, table: RecipeTable) -> None:
    ids_only = build_pack(example, table, "16b", START_16B)
    expanded = build_pack(example, table, "16b", START_16B, expand=True)
    assert {entry.content for rows in ids_only.sections.values() for entry in rows} == {None}
    fr = next(entry for entry in expanded.sections["obligations"] if entry.id == "fr-password-reset")
    assert fr.content is not None and "single-use reset token" in fr.content["statement"]
    assert expanded.sections["third parties"][0].content is not None
    assert all(entry.content is None for entry in expanded.sections["universal"] if entry.kind == "pointer")
    document = pack_to_dict(expanded)
    assert document["sections"]["obligations"][1]["content"]["fr_id"] == "fr-password-reset"
    assert "single-use reset token" in render_text(expanded)
    assert "content" not in json.dumps(pack_to_dict(ids_only))


def test_pack_rows_carry_the_pin_of_a_third_party(example: Graph, table: RecipeTable) -> None:
    pack = build_pack(example, table, "16b", START_16B)
    rows = {entry.id: entry for entry in pack.sections["third parties"]}
    assert (rows["tp-argon2"].suffix, rows["tp-mailrelay"].suffix) == ("0.41.1", "api-v3")
    assert rows["tp-argon2"].label.endswith("0.41.1")
    assert "tp-argon2 0.41.1, tp-mailrelay api-v3" in render_text(pack)
    entries = {entry["id"]: entry for entry in pack_to_dict(pack)["sections"]["third parties"]}
    assert entries["tp-argon2"]["pin"] == "0.41.1" and entries["tp-mailrelay"]["pin"] == "api-v3"


def test_json_form_has_the_documented_keys(example: Graph, table: RecipeTable) -> None:
    document = pack_to_dict(build_pack(example, table, "16b", START_16B))
    assert set(document) == {"role", "start", "sections", "counts", "ambiguity_report"}
    assert document["start"]["id"] == START_16B
    assert set(document["sections"]["delivery"][0]) == {"id", "kind", "step", "label", "via"}
    assert document["counts"]["nodes"] == len({row["id"] for rows in document["sections"].values() for row in rows if row["kind"] != "pointer"})
    assert document["counts"]["sections"]["dependencies"] == 0


@pytest.mark.parametrize("role", sorted(STARTS))
def test_threat_and_constraint_sections_present(example: Graph, table: RecipeTable, role: str) -> None:
    sections = _sections(build_pack(example, table, role, STARTS[role]))
    assert sections["threats"] == {"threat-reset-token-replay", "ec-token-at-expiry-second"}
    assert sections["constraints"] == {"inv-reset-token-single-use", "nfr-latency-reset-email"}


def test_threat_via_refining_task_criterion(example: Graph, table: RecipeTable) -> None:
    detached = {
        "threat-reset-token-replay": lambda item: item.update(threatens=[]),
        "ec-token-at-expiry-second": lambda item: item.update(threatens=[]),
    }
    alone = _rebuilt(example, detached)
    assert _sections(build_pack(alone, table, "16b", START_16B))["threats"] == set()
    refined = _rebuilt(
        example, {**detached, "tc-confirm-expired-token": lambda item: item["refines"].append("threat-reset-token-replay")}
    )
    assert _sections(build_pack(refined, table, "16b", START_16B))["threats"] == {"threat-reset-token-replay"}


@pytest.mark.parametrize("lifecycle", LIFECYCLES)
def test_recipe_honours_lifecycle(example: Graph, table: RecipeTable, lifecycle: str) -> None:
    graph = _rebuilt(example, {"fr-password-reset": lambda item: item.update(lifecycle=lifecycle)})
    pack = build_pack(graph, table, "16b", START_16B)
    seen = {entry.id: entry for rows in pack.sections.values() for entry in rows}
    assert ("fr-password-reset" in seen) is (lifecycle != NOT_APPLICABLE)
    if lifecycle == "deprecated":
        assert seen["fr-password-reset"].lifecycle == "deprecated"
        assert "(deprecated)" in render_text(pack)
        flagged = [row for rows in pack_to_dict(pack)["sections"].values() for row in rows if row.get("deprecated")]
        assert {row["id"] for row in flagged} == {"fr-password-reset"}


def test_not_applicable_excluded(example: Graph, table: RecipeTable) -> None:
    graph = _rebuilt(example, {"api-password-reset-confirm": lambda item: item.update(lifecycle=NOT_APPLICABLE)})
    sections = _sections(build_pack(graph, table, "16b", START_16B))
    everything = set().union(*sections.values())
    assert not everything & {"api-password-reset-confirm", "scaffold-password-reset-confirm", "tp-argon2", "identity-service"}
    assert sections["delivery"] == set()
    assert sections["obligations"] == {"ac-password-reset-3", "fr-password-reset"}


def test_the_start_node_may_be_in_any_lifecycle(example: Graph, table: RecipeTable) -> None:
    graph = _rebuilt(example, {START_16B: lambda item: item.update(lifecycle=NOT_APPLICABLE)})
    assert build_pack(graph, table, "16b", START_16B).sections["core criteria"]


def test_universal_matches_terms_by_the_text_of_the_pack(example: Graph, table: RecipeTable) -> None:
    universal = _sections(build_pack(example, table, "16b", START_16B))["universal"]
    assert "term-reset-token" in universal
    assert "term-reset-email-delivery-time-p95" not in universal
    assert "15_scaffold.json" in universal


# --- the ambiguity report -------------------------------------------------------------------------------------------

def _ambiguity(ambiguity_id: str, *about: str) -> dict[str, Any]:
    return {"id": ambiguity_id, "description": "An open question.", "about": list(about)}


def test_ambiguity_report_outside_pack(example: Graph, table: RecipeTable) -> None:
    def in_plan_file(document: dict[str, Any]) -> None:
        document["plan"]["ambiguities"] = [
            _ambiguity("amb-in-pack", "ac-password-reset-3"),
            _ambiguity("amb-outside", "fr-password-reset-request", "ac-password-reset-3"),
        ]
        document["execution"] = {"emergent_ambiguities": [_ambiguity("amb-emergent", "api-not-in-pack")]}

    def other_milestone(document: dict[str, Any]) -> None:
        document.update({"milestone": "ms-other", "plan": {"ambiguities": [_ambiguity("amb-other", "fr-password-reset-request")]}})

    graph = _with_docs(example, {PLAN_FILE: in_plan_file, "impl_context/ms_other_plan.json": other_milestone})
    for role in STARTS:
        pack = build_pack(graph, table, role, STARTS[role])
        assert pack.ambiguities is not None
        assert {row.id: row.about for row in pack.ambiguities} == {
            "amb-outside": ("fr-password-reset-request",),
            "amb-emergent": ("api-not-in-pack",),
        }
    document = pack_to_dict(build_pack(graph, table, "16b", START_16B))
    assert sorted(row["id"] for row in document["ambiguity_report"]) == ["amb-emergent", "amb-outside"]
    assert "amb-outside about fr-password-reset-request" in render_text(build_pack(graph, table, "16b", START_16B))


def test_ambiguity_report_is_empty_without_open_items(example: Graph, table: RecipeTable) -> None:
    assert build_pack(example, table, "16b", START_16B).ambiguities == ()


def test_ambiguity_report_leaves_out_an_item_about_the_pack_and_lists_an_item_about_the_outside(example: Graph, table: RecipeTable) -> None:
    """The filter is seen: an item exists in the plan file in both runs, and only the one about a node outside the pack is reported."""
    def only_inside(document: dict[str, Any]) -> None:
        document["plan"]["ambiguities"] = [_ambiguity("amb-in-pack", "ac-password-reset-3")]

    def inside_and_outside(document: dict[str, Any]) -> None:
        document["plan"]["ambiguities"] = [_ambiguity("amb-in-pack", "ac-password-reset-3"), _ambiguity("amb-open", "fr-password-reset-request")]

    closed = _with_docs(example, {PLAN_FILE: only_inside})
    assert "amb-in-pack" in closed.by_id
    assert build_pack(closed, table, "16b", START_16B).ambiguities == ()
    mixed = _with_docs(example, {PLAN_FILE: inside_and_outside})
    report = build_pack(mixed, table, "16b", START_16B).ambiguities
    assert report is not None and [(row.id, row.about) for row in report] == [("amb-open", ("fr-password-reset-request",))]


# --- the dependency report ------------------------------------------------------------------------------------------

def _older_sketch(document: dict[str, Any]) -> None:
    """The sketch as it was before: another pin for MailRelay, no connection to it, and a connection since removed."""
    for party in document["third_parties"]:
        if party["third_party_id"] == "tp-mailrelay":
            party["pin"] = "api-v2"
    document["connections"] = [{"connection_id": "conn-legacy", "derives_from": ["identity-service"]}]


def _older_fr(document: dict[str, Any]) -> None:
    document["functional_requirements"][1]["statement"] = "An older statement of an FR outside the pack."


def test_dependency_report_changed_and_unavailable_cases(example: Graph, table: RecipeTable) -> None:
    spec = table.reports[DEPENDENCY]
    old = _with_docs(example, {SKETCH_FILE: _older_sketch, "04_fr_list.json": _older_fr})
    seeds = ["fr-password-reset", "api-password-reset-confirm", "ac-password-reset-3"]
    report = compare_dependencies(Snapshot(old, {}), Snapshot(example, {}), spec, seeds, "v1")
    assert {change.id: change.changes for change in report.changes} == {
        "tp-mailrelay": ("changed",),
        "conn-identity-to-mailrelay": ("added",),
        "conn-legacy": ("removed",),
    }
    assert report.unavailable is None and report.base == "v1"
    unchanged = compare_dependencies(Snapshot(example, {}), Snapshot(example, {}), spec, seeds, "v2")
    assert unchanged.changes == ()
    assert compare_dependencies(Snapshot(old, {}), Snapshot(example, {}), spec, [], "v1").changes == ()


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _host(tmp_path: Path, branch: str) -> tuple[Path, Path]:
    """A repository on *branch* whose ``spec`` folder is the worked example, committed once."""
    repo = tmp_path / "host"
    spec = repo / "spec"
    spec.parent.mkdir()
    _git(spec.parent, "init", "-q", "-b", branch)
    shutil.copytree(EXAMPLE_SPEC, spec)
    _commit(repo, "example")
    return repo, spec


def _repin(spec: Path, pin: str) -> None:
    sketch = json.loads((spec / SKETCH_FILE).read_text(encoding="utf-8"))
    sketch["third_parties"][1]["pin"] = pin
    (spec / SKETCH_FILE).write_text(json.dumps(sketch, indent=2) + "\n", encoding="utf-8")


def _report(table: RecipeTable, repo: Path, spec: Path, since: str | None) -> DependencyReport:
    graph = build_graph(str(spec), str(ROOT))
    pack = build_pack(graph, table, "16b", START_16B, git=GitContext(str(repo), str(spec), str(ROOT), since))
    assert pack.dependency_report is not None
    return pack.dependency_report


def test_dependency_report_default_base_is_the_fork_point(tmp_path: Path, table: RecipeTable) -> None:
    repo, spec = _host(tmp_path, "main")
    _git(repo, "checkout", "-q", "-b", "feature")
    _repin(spec, "api-v4")
    _commit(repo, "repin")
    _repin(spec, "api-v5")
    report = _report(table, repo, spec, None)
    assert report.unavailable is None
    assert report.base == _git(repo, "rev-parse", "main")
    assert [(change.id, change.changes) for change in report.changes] == [("tp-mailrelay", ("changed",))]


def test_the_default_base_tries_origin_main_before_main(tmp_path: Path) -> None:
    repo, spec = _host(tmp_path, "main")
    first = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/main", first)
    _repin(spec, "api-v4")
    _commit(repo, "repin")
    assert _git(repo, "rev-parse", "main") != first
    assert default_base_ref(str(repo)) == first


def test_dependency_report_without_a_default_branch_uses_the_previous_commit(tmp_path: Path, table: RecipeTable) -> None:
    repo, spec = _host(tmp_path, "trunk")
    _repin(spec, "api-v4")
    _commit(repo, "repin")
    assert default_base_ref(str(repo)) == PREVIOUS_COMMIT
    report = _report(table, repo, spec, None)
    assert (report.base, [change.id for change in report.changes]) == (PREVIOUS_COMMIT, ["tp-mailrelay"])
    assert _report(table, repo, spec, "HEAD").changes == ()


def test_a_seed_is_never_admitted_to_a_pack_by_a_hop() -> None:
    """A hop with no ``kinds`` filter walks ``derives_from`` up to the seed of the example; the seed does not enter the pack."""
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    open_table = parse_recipes(
        {
            "start_kinds": {"16b": "scope-item"},
            "sections": [
                {
                    "name": "upstream", "roles": ["16b"], "start_set": ["start"], "kinds": ["seed", "scope-item"],
                    "hops": [{"verb": "derives_from", "direction": "out", "kinds": [], "repeat": True}],
                }
            ],
        }
    )
    seed_ids = {node.id for node in graph.by_kind["seed"]}
    assert any(link.target in seed_ids for link in graph.by_id["scope-password-reset"].links)
    pack = build_pack(graph, open_table, "16b", "scope-password-reset")
    assert pack.sections["upstream"] == () and not pack.node_ids & seed_ids


def test_dependency_report_unavailable_for_an_unknown_ref(tmp_path: Path, table: RecipeTable) -> None:
    repo, spec = _host(tmp_path, "main")
    report = _report(table, repo, spec, "no-such-ref")
    assert report.changes == () and report.unavailable is not None and report.unavailable.code == "E708"
    assert "unavailable (E708)" in render_text(Pack("16b", build_pack(build_graph(str(spec), str(ROOT)), table, "16b", START_16B).start, {}, None, report))


def test_dependency_report_unavailable_for_a_tree_before_the_node_model(tmp_path: Path, table: RecipeTable) -> None:
    repo, spec = _host(tmp_path, "main")
    shutil.rmtree(spec)
    spec.mkdir()
    (spec / "04_fr_list.json").write_text('{"functional_requirements": []}\n', encoding="utf-8")
    _commit(repo, "before the model")
    _git(repo, "tag", "bare")
    shutil.rmtree(spec)
    shutil.copytree(EXAMPLE_SPEC, spec)
    report = _report(table, repo, spec, "bare")
    assert report.changes == () and report.unavailable is not None and report.unavailable.code == "E709"


def test_dependency_report_unavailable_outside_a_repository(tmp_path: Path, table: RecipeTable) -> None:
    spec = tmp_path / "spec"
    shutil.copytree(EXAMPLE_SPEC, spec)
    report = _report(table, tmp_path, spec, None)
    assert report.unavailable is not None and report.unavailable.code == "E708"


def test_the_dependency_report_is_only_computed_with_a_git_context(example: Graph, table: RecipeTable) -> None:
    assert build_pack(example, table, "16b", START_16B).dependency_report is None
    assert build_pack(example, table, "16a", START_16A, git=GitContext(".", ".", ".")).dependency_report is None


# --- size -----------------------------------------------------------------------------------------------------------

def _component(graph: Graph, start_id: str) -> set[str]:
    """The ids connected to *start_id* through links and containment, in either direction."""
    seen = {start_id}
    queue = deque([start_id])
    while queue:
        node = graph.by_id[queue.popleft()]
        neighbours = [link.target for link in node.links] + [link.source for link in graph.incoming.get(node.id, ())]
        neighbours += list(node.children) + ([node.parent] if node.parent else [])
        for other in neighbours:
            if other in graph.by_id and other not in seen:
                seen.add(other)
                queue.append(other)
    return seen


def _bulk(graph: Graph, count: int) -> Graph:
    """The example with *count* more FRs: half under the example capability, half under a second capability."""
    def more_capabilities(document: dict[str, Any]) -> None:
        document["capabilities"].append({"capability_id": "cap-bulk", "title": "Bulk", "derives_from": ["scope-sms-reset"]})

    def more_frs(document: dict[str, Any]) -> None:
        for index in range(count):
            parent = "cap-account-recovery" if index % 2 else "cap-bulk"
            document["functional_requirements"].append(
                {
                    "fr_id": f"fr-bulk-{index}",
                    "statement": f"The system shall do bulk thing {index}.",
                    "derives_from": [parent],
                    "acceptance_criteria": [{"criterion_id": f"ac-bulk-{index}", "text": f"Bulk criterion {index}."}],
                }
            )

    return _with_docs(graph, {"01_capabilities.json": more_capabilities, "04_fr_list.json": more_frs})


def test_pack_size_w_scale(example: Graph, table: RecipeTable) -> None:
    graph = _bulk(example, 72)
    assert len(graph.by_kind["fr"]) == 74
    pack = build_pack(graph, table, "16b", START_16B)
    component = _component(graph, START_16B)
    assert len(pack.node_ids) <= len(component) < len(graph.nodes)
    assert len(pack.node_ids) == len(build_pack(example, table, "16b", START_16B).node_ids)


# --- the table and the documents never raise ------------------------------------------------------------------------







def _drop(path: Callable[[dict[str, Any]], dict[str, Any]], key: str) -> Callable[[dict[str, Any]], None]:
    return lambda raw: path(raw).pop(key)




def _hop(index: int) -> Callable[[dict[str, Any]], dict[str, Any]]:
    return lambda raw: _core_16b(raw)["hops"][index]


BAD_TABLES: dict[str, Callable[[dict[str, Any]], None]] = {
    "sections-not-a-list": _set(lambda raw: raw, "sections", "x"),
    "section-not-an-object": lambda raw: raw["sections"].__setitem__(0, 5),
    "start-kinds-not-an-object": _set(lambda raw: raw, "start_kinds", []),
    "start-kind-not-a-string": _set(lambda raw: raw["start_kinds"], "16b", 5),
    "suffix-fields-wrong": _set(lambda raw: raw, "suffix_fields", [1]),
    "exempt-not-a-list": _set(lambda raw: raw, "exempt", {}),
    "exemption-without-authority": lambda raw: raw["exempt"].__setitem__(0, {"kind": "seed"}),
    "roles-not-a-list": _set(_core_16b, "roles", "16b"),
    "unknown-role": _set(_core_16b, "roles", ["17z"]),
    "no-roles": _set(_core_16b, "roles", []),
    "name-missing": _drop(_core_16b, "name"),
    "kinds-not-a-list": _set(_core_16b, "kinds", "task"),
    "emits-nothing": _set(_core_16b, "kinds", []),
    "flag-not-a-bool": _set(_core_16b, "include_start_set", "yes"),
    "hop-direction-unknown": _set(_hop(0), "direction", "sideways"),
    "hop-out-without-verb": _drop(_hop(0), "verb"),
    "hop-parent-with-verb": _set(_hop(1), "verb", "realises"),
    "hop-kinds-not-a-list": _set(_hop(0), "kinds", "task"),
    "hop-repeat-not-a-bool": _set(_hop(0), "repeat", 1),
    "hop-not-an-object": lambda raw: _core_16b(raw)["hops"].__setitem__(0, "x"),
    "start-set-names-nothing": _set(lambda raw: _section(raw, "obligations", "16b"), "start_set", ["nowhere"]),
    "start-set-loops": _set(lambda raw: _section(raw, "obligations", "16b"), "start_set", ["APIs and errors"]),
    "start-set-names-universal": _set(lambda raw: _section(raw, "obligations", "16b"), "start_set", ["universal"]),
    "duplicate-name": lambda raw: raw["sections"].append(copy.deepcopy(_core_16b(raw))),
    "universal-with-kinds": _set(lambda raw: _section(raw, "universal", "16b"), "kinds", ["rule"]),
    "matched-not-a-list": _set(lambda raw: _section(raw, "universal", "16b"), "matched", "term"),
    "pointer-not-an-object": _set(lambda raw: _section(raw, "universal", "16b"), "pointer", "x"),
    "unknown-report": _set(lambda raw: raw["reports"], "nope", {"roles": ["16b"]}),
    "report-hops-wrong": _set(lambda raw: raw["reports"]["dependency"], "hops", "x"),
}


def test_shipped_table_parses(table: RecipeTable) -> None:
    assert table.roles == ("16a", "16b", "16c")
    assert {section.name for section in table.sections_for("16b")} >= {"core criteria", "delivery", "universal"}
    assert parse_recipes(_raw()) == table


@pytest.mark.parametrize("name", BAD_TABLES)
def test_a_wrong_table_gives_e520_never_a_traceback(name: str) -> None:
    raw = _raw()
    BAD_TABLES[name](raw)
    with pytest.raises(RecipeError) as raised:
        parse_recipes(raw)
    assert raised.value.error.code == "E520"
    assert "graph_recipes.json" in raised.value.error.message


@pytest.mark.parametrize("content", [None, "not json", "[1, 2]"], ids=["missing", "not-json", "not-an-object"])
def test_an_unreadable_table_file_gives_e520(tmp_path: Path, content: str | None) -> None:
    (tmp_path / "tools").mkdir()
    if content is not None:
        (tmp_path / "tools" / "graph_recipes.json").write_text(content, encoding="utf-8")
    with pytest.raises(RecipeError) as raised:
        load_recipes(str(tmp_path))
    assert raised.value.error.code == "E520"


@pytest.mark.parametrize("wrong", WRONG_VALUES, ids=lambda value: type(value).__name__ + str(value)[:3])
@pytest.mark.parametrize(
    ("node_id", "field"),
    [
        ("tp-argon2", "pin"),
        ("tp-argon2", "name"),
        ("term-reset-token", "term"),
        (START_16B, "description"),
        ("tc-confirm-expired-token", "refines"),
        ("ci", "derives_from"),
    ],
)
def test_a_wrong_typed_value_in_a_document_does_not_raise(
    example: Graph, table: RecipeTable, node_id: str, field: str, wrong: Any
) -> None:
    graph = _rebuilt(example, {node_id: lambda item: item.update({field: wrong})})
    for role, start_id in STARTS.items():
        pack = build_pack(graph, table, role, start_id, expand=True)
        json.dumps(pack_to_dict(pack))
        assert render_text(pack)


@pytest.mark.parametrize("wrong", WRONG_VALUES, ids=lambda value: type(value).__name__ + str(value)[:3])
def test_a_wrong_typed_milestone_in_the_plan_file_does_not_raise(example: Graph, table: RecipeTable, wrong: Any) -> None:
    graph = _with_docs(example, {PLAN_FILE: lambda document: document.update(milestone=wrong)})
    assert build_pack(graph, table, "16b", START_16B).ambiguities is not None
