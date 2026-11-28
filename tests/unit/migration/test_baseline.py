"""Phase 6, the lock baseline (WI-M10-07): ``p6_baseline``.

Two migrated copies of the mini host are shared by the module: ``migrated`` is the whole registered chain through
``run_migration`` (what a host gets), ``premigrated`` is the chain without ``p6_baseline`` (what the script starts from, so a
test can change the tree and run the script on it).  A test that changes a tree works on its own ``shutil`` copy.  The lock
is read and written with the lock's own library (``trace.lockfile``, ``trace.attest``, ``trace.suspects``): nothing here
parses the file by hand except to check the bytes.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.model import Graph
from specdev_tools.graph.resolve import HISTORY_FIELDS, resolve_graph
from specdev_tools.migration import registry, runner
from specdev_tools.migration.registry import PHASE_BASELINE
from specdev_tools.migration.report import STATUS_OK
from specdev_tools.migration.scripts.v1_2_0 import p6_baseline
from specdev_tools.trace import attest
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.history import containers_of, historical_node_ids
from specdev_tools.trace.lockfile import Lock, LockEntry, lock_path, read_lock, write_lock
from specdev_tools.trace.suspects import LockHook, check_lock, find_suspects, lock_links, missing_entries
from specdev_tools.trace.writing import seed_texts_for_write
from specdev_tools.validation.migration_mode import not_passed_owners

from ._support import context, items, make_host, make_toolkit, REAL_ROOT, tree_digest

EXAMPLE_HOST = REAL_ROOT / "tests" / "fixtures" / "graph_example"
LOCK_REL = "extras/trace.lock.json"
LIVE_HOLDER = "api-return-create"
LIVE_LINK = ("derives_from", "fr-return-tool")
STALE_HASH = "sha256:" + "0" * 64


# ---------------------------------------------------------------------------
# Support
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("p6")
    toolkit, host = make_toolkit(tmp), make_host(tmp)
    report = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host)
    assert report.status == STATUS_OK, report.errors
    return host, toolkit, report


@pytest.fixture(scope="module")
def premigrated(tmp_path_factory):
    """The mini host after every script of the chain but ``p6_baseline``: a tree with links and no lock."""
    tmp = tmp_path_factory.mktemp("p6-before")
    toolkit, host = make_toolkit(tmp), make_host(tmp)
    chain = [script for script in registry.discover_scripts() if script.id != p6_baseline.SCRIPT.id]
    report = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=chain)
    assert report.status == STATUS_OK, report.errors
    assert not (host / "spec" / LOCK_REL).exists()
    return host, toolkit


def copy_of(source: Path, tmp_path: Path) -> Path:
    destination = tmp_path / "host"
    shutil.copytree(source, destination)
    return destination


def graph_of(host: Path, toolkit: Path) -> Graph:
    return build_graph(str(host / "spec"), str(toolkit))


def seeds_of(graph: Graph, host: Path) -> dict[str, str]:
    return seed_texts_for_write(graph, str(host))


def lock_of(host: Path) -> Lock:
    return read_lock(str(host / "spec"))


def run_script(host: Path, toolkit: Path):
    """Detect and apply ``p6_baseline`` on *host* as the runner does (the documents it holds are written after ``apply``)."""
    ctx = context(host, toolkit)
    detected = p6_baseline.detect(ctx)
    result = p6_baseline.apply(ctx)
    ctx.documents.write()
    return detected, result


def holders_with_marker(lock: Lock, historical: set[str], *, live: bool) -> set[str]:
    return {entry.source for entry in lock.entries if entry.baseline and (entry.source in historical) is not live}


def rewrite_link(host: Path, graph: Graph, holder: str, field: str, new_target: str) -> None:
    """Point the *field* link of the node *holder* at *new_target* in its spec file (the file is rewritten at indent 4)."""
    path = host / "spec" / graph.by_id[holder].file
    document = json.loads(path.read_text(encoding="utf-8"))

    def walk(value: Any):
        if isinstance(value, dict):
            yield value
            for inner in value.values():
                yield from walk(inner)
        elif isinstance(value, list):
            for inner in value:
                yield from walk(inner)

    node = next(d for d in walk(document) if holder in d.values() and field in d)
    node[field] = [new_target] if isinstance(node[field], list) else new_target
    path.write_text(json.dumps(document, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


def edit_text(host: Path, graph: Graph, node_id: str, key: str) -> None:
    """Append a word to the string *key* of the node *node_id* in its spec file."""
    path = host / "spec" / graph.by_id[node_id].file
    document = json.loads(path.read_text(encoding="utf-8"))

    def walk(value: Any):
        if isinstance(value, dict):
            yield value
            for inner in value.values():
                yield from walk(inner)
        elif isinstance(value, list):
            for inner in value:
                yield from walk(inner)

    node = next(d for d in walk(document) if node_id in d.values() and key in d)
    node[key] = f"{node[key]} Changed after the baseline."
    path.write_text(json.dumps(document, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# The script is registered, and what its entries are
# ---------------------------------------------------------------------------


def test_the_script_is_discovered_in_phase_6_and_touches_extras_only():
    script = next(s for s in registry.discover_scripts() if s.id == "p6_baseline")
    assert script.spec.phase == PHASE_BASELINE and script.spec.touches == ("extras",)
    assert script.spec.requires == ()


def test_baseline_entries_carry_both_hashes_and_target_containers(migrated):
    host, toolkit, _report = migrated
    graph = graph_of(host, toolkit)
    hashes = compute_all(graph, seeds_of(graph, host))
    lock = lock_of(host)
    assert lock.entries
    for entry in lock.entries:
        target = graph.find(entry.target)
        assert target is not None
        assert (entry.content_hash, entry.chain_stamp) == hashes[target.id]
        assert entry.target_containers == containers_of(graph, target)
        assert entry.baseline is True
    assert any(entry.target_containers for entry in lock.entries)


def test_the_marker_is_on_every_entry_the_script_wrote_and_on_none_it_did_not(premigrated, tmp_path):
    host, toolkit = premigrated
    copy = copy_of(host, tmp_path)
    graph = graph_of(copy, toolkit)
    keep = next(item for item in lock_links(graph))
    own = LockEntry(keep.holder.id, keep.link.field, keep.link.target, STALE_HASH, STALE_HASH)
    write_lock(str(copy / "spec"), Lock((own,)))
    _detected, result = run_script(copy, toolkit)
    lock = lock_of(copy)
    assert lock.get(*own.key) == own and not own.baseline
    assert all(entry.baseline for entry in lock.entries if entry.key != own.key)
    assert result.edits == len(lock.entries) - 1


def test_entry_count_equals_resolver_link_count(migrated):
    host, toolkit, _report = migrated
    graph = graph_of(host, toolkit)
    refused = {(error.node_id, error.target) for error in resolve_graph(graph, historical=historical_node_ids(graph)) if error.code in {"E700", "E701", "E702"}}
    declared = {
        (holder.id, link.field, link.target)
        for holder in graph.gated_nodes()
        if holder.role != "record"
        for link in holder.links
        if link.field not in HISTORY_FIELDS and graph.find(link.target) is not None
    }
    resolved = {key for key in declared if (key[0], f"{key[1]}->{key[2]}") not in refused}
    assert len(lock_of(host).entries) == len(resolved) == len(lock_links(graph)) > 0


def test_no_link_lacks_an_entry_after_the_script_and_every_one_did_before(premigrated, migrated):
    before_host, before_toolkit = premigrated
    after_host, after_toolkit, _report = migrated
    before, after = graph_of(before_host, before_toolkit), graph_of(after_host, after_toolkit)
    missing_before = [e for e in resolve_graph(before, hooks=LockHook(before, Lock())) if e.code == "E761"]
    missing_after = [e for e in resolve_graph(after, hooks=LockHook(after, lock_of(after_host))) if e.code == "E761"]
    assert len(missing_before) == len(lock_of(after_host).entries) > 0
    assert missing_after == [] and missing_entries(after, lock_of(after_host)) == []


# ---------------------------------------------------------------------------
# Idempotency and the existing entry
# ---------------------------------------------------------------------------


def test_second_run_makes_zero_edits(migrated, tmp_path):
    host, toolkit, _report = migrated
    copy = copy_of(host, tmp_path)
    before = (copy / "spec" / LOCK_REL).read_bytes()
    detected, result = run_script(copy, toolkit)
    assert detected == 0 and result.edits == 0 and result.worklist_items == 0
    assert (copy / "spec" / LOCK_REL).read_bytes() == before
    digest = tree_digest(host / "spec")
    again = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host)
    assert again.status == STATUS_OK and not any(script.edits for script in again.scripts)
    assert tree_digest(host / "spec") == digest


def test_two_runs_with_the_same_input_write_the_same_bytes(migrated, tmp_path):
    host, _toolkit, _report = migrated
    toolkit, other = make_toolkit(tmp_path), make_host(tmp_path)
    assert runner.run_migration(other / "spec", toolkit_root=toolkit, git_root=other).status == STATUS_OK
    for rel in (LOCK_REL, "extras/migration/worklist.json"):
        assert (other / "spec" / rel).read_bytes() == (host / "spec" / rel).read_bytes()


def test_existing_entry_is_never_restamped(premigrated, tmp_path):
    host, toolkit = premigrated
    copy = copy_of(host, tmp_path)
    graph = graph_of(copy, toolkit)
    first, second = lock_links(graph)[:2]
    stale = LockEntry(first.holder.id, first.link.field, first.link.target, STALE_HASH, STALE_HASH, baseline=True)
    write_lock(str(copy / "spec"), Lock((stale,)))
    _detected, result = run_script(copy, toolkit)
    lock = lock_of(copy)
    assert lock.get(*stale.key) == stale
    assert lock.get(second.holder.id, second.link.field, second.link.target) is not None
    assert result.edits == len(lock_links(graph)) - 1 == len(lock.entries) - 1


def test_reattested_entry_keeps_no_marker_on_a_later_run(migrated, tmp_path):
    host, toolkit, _report = migrated
    copy = copy_of(host, tmp_path)
    graph = graph_of(copy, toolkit)
    plan = attest.plan_node_attest(graph, lock_of(copy), seeds_of(graph, copy), LIVE_HOLDER)
    write_lock(str(copy / "spec"), attest.apply_attest(lock_of(copy), plan))
    cleared = lock_of(copy)
    run_script(copy, toolkit)
    assert lock_of(copy) == cleared
    assert not any(entry.baseline for entry in cleared.entries if entry.source == LIVE_HOLDER)


# ---------------------------------------------------------------------------
# Which links get an entry
# ---------------------------------------------------------------------------


def test_record_links_and_replaces_removes_get_no_entry(tmp_path):
    host = copy_of(EXAMPLE_HOST, tmp_path)
    (host / "spec" / LOCK_REL).unlink()
    fr_file = host / "spec" / "04_fr_list.json"
    document = json.loads(fr_file.read_text(encoding="utf-8"))
    document["functional_requirements"][0]["replaces"] = ["fr-old-name"]
    fr_file.write_text(json.dumps(document, indent=4) + "\n", encoding="utf-8")
    graph = graph_of(host, REAL_ROOT)
    records = [node for node in graph.nodes if node.role == "record" and node.links]
    assert records and any(link.field in HISTORY_FIELDS for node in graph.nodes for link in node.links)
    run_script(host, REAL_ROOT)
    lock = lock_of(host)
    assert {entry.key for entry in lock.entries} == {item.key for item in lock_links(graph)} and lock.entries
    assert not {entry.source for entry in lock.entries} & {node.id for node in records}
    assert not {entry.field for entry in lock.entries} & HISTORY_FIELDS


def test_unresolvable_link_gets_worklist_item_not_entry(premigrated, tmp_path):
    host, toolkit = premigrated
    copy = copy_of(host, tmp_path)
    rewrite_link(copy, graph_of(copy, toolkit), LIVE_HOLDER, LIVE_LINK[0], "fr-not-there")
    total = len(lock_links(graph_of(copy, toolkit)))
    detected, result = run_script(copy, toolkit)
    assert result.worklist_items == 1 and detected == total + 1 == result.edits
    lock = lock_of(copy)
    assert len(lock.entries) == total
    assert not [entry for entry in lock.entries if (entry.source, entry.field) == (LIVE_HOLDER, LIVE_LINK[0])]
    [item] = items(copy, p6_baseline.KIND_UNRESOLVED_LINK)
    assert item["about"] == LIVE_HOLDER and item["step"] == "05" and item["audience"] == "operator" and item["blocking"] is False
    assert "E700" in item["evidence"] and "fr-not-there" in item["evidence"]
    assert any("fr-not-there" in line for line in result.residue)
    assert p6_baseline.detect(context(copy, toolkit)) == 0


# ---------------------------------------------------------------------------
# What a baselined entry means: attest, the check, migration mode
# ---------------------------------------------------------------------------


def test_attest_clears_marker_on_live_link(migrated, tmp_path):
    host, toolkit, _report = migrated
    copy = copy_of(host, tmp_path)
    graph = graph_of(copy, toolkit)
    lock = lock_of(copy)
    plan = attest.plan_node_attest(graph, lock, seeds_of(graph, copy), LIVE_HOLDER)
    assert plan.links and {link.reason for link in plan.links} == {attest.REASON_BASELINE}
    write_lock(str(copy / "spec"), attest.apply_attest(lock, plan))
    after = lock_of(copy)
    own = [entry for entry in after.entries if entry.source == LIVE_HOLDER]
    assert own and not any(entry.baseline for entry in own)
    assert all(entry.baseline for entry in after.entries if entry.source != LIVE_HOLDER)
    key = (LIVE_HOLDER, *LIVE_LINK)
    assert (after.get(*key).content_hash, after.get(*key).chain_stamp) == (lock.get(*key).content_hash, lock.get(*key).chain_stamp)


def test_attest_refuses_historical_link(migrated):
    host, toolkit, _report = migrated
    graph = graph_of(host, toolkit)
    lock = lock_of(host)
    historical = sorted(holders_with_marker(lock, historical_node_ids(graph), live=False))
    assert historical
    with pytest.raises(attest.AttestRefusedError) as refused:
        attest.plan_node_attest(graph, lock, seeds_of(graph, host), historical[0])
    assert refused.value.error.code == "E765"
    assert all(entry.baseline for entry in lock.entries if entry.source == historical[0])


def test_e882_fires_for_live_baseline_and_not_for_historical_after_runner(migrated):
    host, toolkit, _report = migrated
    graph = graph_of(host, toolkit)
    lock = lock_of(host)
    historical = historical_node_ids(graph)
    errors = [error for error in check_lock(graph, lock, seeds_of(graph, host)) if error.code == "E882"]
    live, frozen = holders_with_marker(lock, historical, live=True), holders_with_marker(lock, historical, live=False)
    assert live and frozen
    assert {error.node_id for error in errors} == live
    assert len(errors) == sum(entry.baseline and entry.source in live for entry in lock.entries)
    assert not {error.node_id for error in errors} & frozen
    assert not_passed_owners(errors) == {error.owner for error in errors} != frozenset()


def test_a_link_changed_after_the_baseline_is_stale_again(migrated, tmp_path):
    host, toolkit, _report = migrated
    copy = copy_of(host, tmp_path)
    graph = graph_of(copy, toolkit)
    assert find_suspects(graph, lock_of(copy), seeds_of(graph, copy)) == []
    edit_text(copy, graph, LIVE_LINK[1], "statement")
    changed = graph_of(copy, toolkit)
    stale = {suspect.key: suspect.cause for suspect in find_suspects(changed, lock_of(copy), seeds_of(changed, copy))}
    assert stale[(LIVE_HOLDER, *LIVE_LINK)] == "content_changed"
    assert any(error.code == "E763" for error in check_lock(changed, lock_of(copy), seeds_of(changed, copy)))


# ---------------------------------------------------------------------------
# The script's own refusals and its check
# ---------------------------------------------------------------------------


def test_an_unreadable_spec_file_refuses_the_script(premigrated, tmp_path):
    host, toolkit = premigrated
    copy = copy_of(host, tmp_path)
    (copy / "spec" / "04_fr_list.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(FindingError) as refused:
        p6_baseline.detect(context(copy, toolkit))
    assert refused.value.error.code == "E520"
    assert not Path(lock_path(str(copy / "spec"))).exists()


def snapshot(entries: list[dict], **other: str) -> SimpleNamespace:
    files = {LOCK_REL: json.dumps(entries), **other}
    return SimpleNamespace(files=files, documents={LOCK_REL: {"entries": entries}})


def entry(target: str, **extra: Any) -> dict[str, Any]:
    return {"source": "a", "field": "derives_from", "target": target, "content_hash": STALE_HASH, "chain_stamp": STALE_HASH, **extra}


def test_verify_accepts_new_marked_entries_and_refuses_the_rest():
    old = snapshot([entry("x")])
    assert p6_baseline.verify(old, snapshot([entry("x"), entry("y", baseline=True)])) == []
    unmarked = p6_baseline.verify(old, snapshot([entry("x"), entry("y")]))
    changed = p6_baseline.verify(old, snapshot([entry("x", baseline=True), entry("y", baseline=True)]))
    removed = p6_baseline.verify(old, snapshot([]))
    elsewhere = p6_baseline.verify(old, snapshot([entry("x")], **{"04_fr_list.json": "changed"}))
    assert ["without the baseline marker" in p.message for p in unmarked] == [True]
    assert ["never restamped" in p.message for p in changed] == [True] and len(removed) == 1
    assert [p.file for p in elsewhere] == ["04_fr_list.json"]
