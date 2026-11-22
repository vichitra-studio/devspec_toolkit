"""The prose-id inventory (WI-M10-09, DEVSPEC-158): ``specdev align propose --kind prose-ids``.

Built on a copy of the invented gold set (``refines_gold``) with ids written into its prose by the tests.  The resolved
mentions are the ones the id-in-prose check (E752) reports on the same tree; the unresolved classes are the inventory's own.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.migration import proposers
from specdev_tools.migration.proposers import prose_ids
from specdev_tools.migration.worklist import WORKLIST_FILE, WORKLIST_SCHEMA, make_item
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.prose_ids import check_prose_ids

from ._proposer_support import copy_gold, edit, task_criterion, tree_of
from .test_runner_core import REAL_ROOT, tree_digest

CRITERION_1, CRITERION_2, CRITERION_3 = "tc-borrow-packet-1", "tc-borrow-packet-2", "tc-borrow-packet-3"


def _say(host: Path, criterion_id: str, text: str) -> None:
    edit(host, "14_roadmap.json", lambda data: task_criterion(data, criterion_id).update(text=text))


@pytest.fixture
def host(tmp_path) -> Path:
    """The gold copy with ids in prose: two resolved mentions in one node, one in another, one in a fixed leaf, and one of each unresolved class."""
    host = copy_gold(tmp_path)
    _say(host, CRITERION_1, "Closing the loan frees ac-borrow-packet-1 and fr-borrow-packet, and fr-borrow-wishlist is not in the spec")
    _say(host, CRITERION_2, "See ac-3 above; the label is fr-xxx; the slip is ac-borrow-pakcet-1; the old name fr-borrow-old; the word latency is no id")
    _say(host, CRITERION_3, "A member never breaks inv-six-packet-limit")
    edit(host, "05_interface_contracts.json", lambda data: data["apis"][0]["errors"][0].update(severity="ac-borrow-packet-1"))
    edit(host, "extras/migration/capture.json", lambda data: data.update(renames=[{"old": "fr-borrow-old", "new": "fr-borrow-packet", "kind": "fr", "file": "04_fr_list.json"}]))
    edit(host, "07_nfrs.json", lambda data: data["nfrs"].append({"nfr_id": "latency", "name": "Latency", "category": "latency", "metric": "m", "target": 1, "unit": "s", "stage": "prod"}))
    return host


def run(host: Path):
    return prose_ids.propose(tree_of(host))


def by_about(result) -> dict:
    return {proposal.data["about"]: proposal for proposal in result.proposals}


def mentions_of(proposal) -> dict[str, dict]:
    return {m["token"]: m for m in proposal.data["mentions"]}


def test_resolved_mentions_equal_the_e752_findings_of_the_same_tree(host):
    tree = tree_of(host)
    findings = check_prose_ids(GraphCheckContext.from_graph(tree.graph, None, str(REAL_ROOT), spec_root=str(host / "spec")), "merge")
    result = prose_ids.propose(tree)
    assert len(findings) == result.counts[prose_ids.RESOLVED] == 3
    inventory = {(p.data["about"], m["token"]) for p in result.proposals for m in p.data["mentions"] if m["class"] == prose_ids.RESOLVED}
    assert inventory == {(f.node_id, (f.target or "").split("->")[1]) for f in findings}
    assert "err-borrow-limit-reached" not in by_about(result), "an id in an enum leaf (the error's severity) is not prose"


def test_one_worklist_item_per_node(host):
    result = run(host)
    assert sorted(by_about(result)) == [CRITERION_1, CRITERION_2, CRITERION_3]
    assert len({p.item.id for p in result.proposals}) == len(result.proposals) == result.counts["nodes"]
    assert len(mentions_of(by_about(result)[CRITERION_1])) == 3, "two leaves' worth of tokens of one node are one item"


def test_each_unresolved_class_is_listed_with_its_class(host):
    mentions = mentions_of(by_about(run(host))[CRITERION_2])
    assert {token: m["class"] for token, m in mentions.items()} == {
        "ac-3": prose_ids.RELATIVE_NOTATION,
        "fr-xxx": prose_ids.PLACEHOLDER,
        "ac-borrow-pakcet-1": prose_ids.NEAR_MISS,
        "fr-borrow-old": prose_ids.RETIRED,
    }
    assert "ac-borrow-packet-1" in mentions["ac-borrow-pakcet-1"]["proposal"]
    assert "fr-borrow-packet" in mentions["fr-borrow-old"]["proposal"]
    never = mentions_of(by_about(run(host))[CRITERION_1])["fr-borrow-wishlist"]
    assert never["class"] == prose_ids.NEVER_DEFINED and never["target"] is None
    item = by_about(run(host))[CRITERION_2].item
    assert "ac-3 (unresolved: relative)" in item.evidence and item.blocking is False


def test_a_mention_that_states_a_relation_is_proposed_as_the_one_declared_field_that_fits(host):
    states = mentions_of(by_about(run(host))[CRITERION_3])["inv-six-packet-limit"]
    assert states["class"] == prose_ids.RESOLVED and states["target"] == "inv-six-packet-limit"
    assert "the declared field refines of task-criterion accepts the kind invariant" in states["proposal"]
    assert "removes" not in states["proposal"] and "replaces" not in states["proposal"]


def test_a_mention_of_a_node_the_holder_already_links_is_proposed_as_a_reword(host):
    edit(host, "05_interface_contracts.json", lambda data: data["apis"][0].update(name="the borrow endpoint of fr-borrow-packet"))
    proposal = mentions_of(by_about(run(host))["api-borrow-packet"])["fr-borrow-packet"]
    assert "already links fr-borrow-packet through derives_from: reword out" in proposal["proposal"]


def test_a_mention_the_collision_script_already_listed_is_left_to_its_item(host):
    item = make_item("14", prose_ids.CITATION_KIND, CRITERION_1, audience="agent", blocking=False, key="ac-borrow-packet-1-text",
                     evidence="14_roadmap.json names `ac-borrow-packet-1`; 2 nodes defined it")
    path = host / "spec" / WORKLIST_FILE
    path.write_text(json.dumps({"$schema": WORKLIST_SCHEMA, "items": [item.to_json()]}, indent=4) + "\n", encoding="utf-8")
    mentions = mentions_of(by_about(run(host))[CRITERION_1])
    assert f"decide worklist item {item.id} first" in mentions["ac-borrow-packet-1"]["proposal"]
    assert item.id not in mentions["fr-borrow-packet"]["proposal"]
    assert mentions["ac-borrow-packet-1"]["class"] == prose_ids.RESOLVED, "it still counts: E752 reports it"


def test_name_like_ids_without_a_hyphen_are_not_tokens(host):
    tree = tree_of(host)
    assert "latency" in tree.graph.by_id and "latency" not in prose_ids.id_tokens(tree.graph)
    assert "latency" not in mentions_of(by_about(prose_ids.propose(tree))[CRITERION_2])


def test_the_inventory_writes_no_spec_file(host):
    before = tree_digest(host)
    outcome = proposers.propose(host / "spec", kind=proposers.KIND_PROSE_IDS, toolkit_root=REAL_ROOT, git_root=host, dry_run=False)
    after = tree_digest(host)
    assert {rel for rel in after if before.get(rel) != after[rel]} == {f"spec/{WORKLIST_FILE}"}
    assert outcome.added == len(outcome.result.proposals) == 3
    assert proposers.propose(host / "spec", kind=proposers.KIND_PROSE_IDS, toolkit_root=REAL_ROOT, git_root=host, dry_run=False).added == 0


def test_a_blocking_item_is_one_with_a_resolved_mention(host):
    result = run(host)
    assert {p.item.about: p.item.blocking for p in result.proposals} == {CRITERION_1: True, CRITERION_2: False, CRITERION_3: True}
    _say(host, CRITERION_3, "no id here, only fr-borrow-wishlist")
    assert by_about(run(host))[CRITERION_3].item.blocking is False


def test_two_nodes_that_share_an_id_get_two_items(host):
    edit(host, "14_roadmap.json", lambda data: task_criterion(data, CRITERION_3).update(criterion_id=CRITERION_1))
    result = run(host)
    items = [p.item for p in result.proposals if p.item.about == CRITERION_1]
    assert len(items) == 2 and len({item.id for item in items}) == 2
