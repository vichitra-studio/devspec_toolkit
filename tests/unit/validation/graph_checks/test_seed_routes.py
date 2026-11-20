"""The seed route checks (E747, E748, E749, WI-M6b-09): small manifests under ``tests/fixtures/graph_checks/seed_routes/`` on copies of the worked example."""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import run_split, step_gate_host
from specdev_tools.core.errors import SpecError
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.validation.graph_checks.codes import SEED_LINK_NOT_ROUTED, SEED_NOT_ROUTED, SEED_ROUTE_UNUSED
from specdev_tools.validation.graph_checks.context import SEED_MANIFEST_PATH, GraphCheckContext
from specdev_tools.validation.graph_checks.seed_routes import _routes, check_seed_routes
from specdev_tools.validation.seed_lint import lint_seeds
from unit.graph._synth import HASH_SEEDS, ROOT
from unit.trace._lock_support import EXAMPLE_HOST

from ._example_support import Edit, context_of_spec, edit_documents
from ._order_support import seeded

FIXTURES = ROOT / "tests" / "fixtures" / "graph_checks" / "seed_routes"
SEED, EXTRA = "seed-accounts", "seed-extra"
CODES = (SEED_NOT_ROUTED, SEED_ROUTE_UNUSED, SEED_LINK_NOT_ROUTED)


def _host(tmp_path: Path, manifest: str | None = None, **edits: Edit) -> Path:
    """A copy of the worked example (spec and seed documents); with *manifest* the fixture of that name replaces the seed manifest; each edit changes the parsed spec file of its name."""
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    if manifest is not None:
        shutil.copy(FIXTURES / f"{manifest}.json", host / "spec" / SEED_MANIFEST_PATH)
    edit_documents(host / "spec", **edits)
    return host


def _context(host: Path) -> GraphCheckContext:
    return context_of_spec(host / "spec")


def _found(host: Path) -> list[SpecError]:
    return check_seed_routes(_context(host), "merge")


def _rows(findings: list[SpecError]) -> list[tuple[str, str | None, str | None]]:
    return [(error.code, error.node_id, error.owner) for error in findings]


def _derive_from_seed(file_edit: Callable[[dict[str, Any]], dict[str, Any]]) -> Edit:
    """Edit that adds the seed to ``derives_from`` of the item *file_edit* picks."""
    return lambda document: file_edit(document).setdefault("derives_from", []).append(SEED)


def _first_fr(document: dict[str, Any]) -> dict[str, Any]:
    return document["functional_requirements"][0]


def test_the_worked_example_has_no_seed_route_finding(tmp_path: Path) -> None:
    assert _found(_host(tmp_path)) == []


def test_unrouted_seed_gives_e747_owner_step_00(tmp_path: Path) -> None:
    (found,) = _found(_host(tmp_path, "unrouted_seed"))
    assert (found.code, found.node_id, found.owner, found.file) == (SEED_NOT_ROUTED, EXTRA, "step:00", SEED_MANIFEST_PATH)
    assert found.jq_path == ".seeds[1]" and found.route is None and found.target is None


def test_global_seed_order_only_seed_is_still_e747(tmp_path: Path) -> None:
    assert _rows(_found(_host(tmp_path, "global_order_only"))) == [(SEED_NOT_ROUTED, EXTRA, "step:00")]


def test_unused_route_gives_e748_owned_by_its_step(tmp_path: Path) -> None:
    (found,) = _found(_host(tmp_path, "unused_route"))
    assert (found.code, found.node_id, found.owner, found.file) == (SEED_ROUTE_UNUSED, SEED, "step:02a", SEED_MANIFEST_PATH)
    assert found.jq_path == '.step_requirements["02a"]'
    assert "step 02a" in found.message and SEED in found.message and "derives_from" in found.message


def test_used_route_gives_no_e748(tmp_path: Path) -> None:
    """The example routes the seed to 00 and 02, and a node of each links it; the same route unused once the links are gone."""
    assert _found(_host(tmp_path / "used")) == []
    only_00 = _host(tmp_path / "only-00", **{"02_system_sketch.json": lambda doc: [tp.pop("derives_from") for tp in doc["third_parties"]]})
    assert _rows(_found(only_00)) == [(SEED_ROUTE_UNUSED, SEED, "step:02")]


def test_route_to_step_whose_kinds_cannot_link_a_seed_is_e748(tmp_path: Path) -> None:
    (found,) = _found(_host(tmp_path, "non_linkable_route"))
    assert (found.code, found.node_id, found.owner, found.jq_path) == (SEED_ROUTE_UNUSED, SEED, "step:04", '.step_requirements["04"]')
    assert "step 04" in found.message and "link a seed" in found.message


def test_trinity_key_gives_e748_naming_the_trinity_case(tmp_path: Path) -> None:
    (found,) = _found(_host(tmp_path, "trinity_route"))
    assert (found.code, found.node_id, found.owner, found.jq_path) == (SEED_ROUTE_UNUSED, SEED, "step:16", '.step_requirements["16"]')
    assert "trinity" in found.message and "remove the route" in found.message


def test_link_to_unrouted_seed_gives_e749_owned_by_holder_step(tmp_path: Path) -> None:
    findings = _found(_host(tmp_path, "unrouted_link"))
    assert {error.code for error in findings} == {SEED_LINK_NOT_ROUTED}
    assert _rows(findings) == [(SEED_LINK_NOT_ROUTED, "tp-argon2", "step:02"), (SEED_LINK_NOT_ROUTED, "tp-mailrelay", "step:02")]
    assert {error.target for error in findings} == {f"derives_from->{SEED}"}
    assert all(error.file == "02_system_sketch.json" for error in findings)


def test_record_link_about_is_ignored(tmp_path: Path) -> None:
    """An open item ``about`` the seed in step 05, which does not route the seed, raises no E749 (a record link is no use of a route)."""
    item = {"id": "amb-about-seed", "description": "Which flow?", "about": [SEED]}
    host = _host(tmp_path, "unrouted_link", **{"05_interface_contracts.json": lambda doc: doc.setdefault("ambiguities", []).append(item)})
    holders = {error.node_id for error in _found(host) if error.code == SEED_LINK_NOT_ROUTED}
    assert holders == {"tp-argon2", "tp-mailrelay"}


def test_derives_from_seed_on_a_04_node_is_the_resolver_error_not_e749(tmp_path: Path) -> None:
    """A requirement (step 04) cannot link a seed through ``derives_from``: the resolver reports the wrong kind (E701) and the route check stays silent."""
    context = _context(_host(tmp_path, "unrouted_link", **{"04_fr_list.json": _derive_from_seed(_first_fr)}))
    assert {error.node_id for error in check_seed_routes(context, "merge") if error.code == SEED_LINK_NOT_ROUTED} == {"tp-argon2", "tp-mailrelay"}
    wrong_kind = [error for error in resolve_graph(context.graph) if error.node_id == "fr-password-reset"]
    assert [error.code for error in wrong_kind] == ["E701"]


def test_e748_carries_route(tmp_path: Path) -> None:
    findings = _found(_host(tmp_path, "unused_route"))
    assert [error.route for error in findings] == [(SEED, "02a")]


def test_e749_carries_route(tmp_path: Path) -> None:
    findings = _found(_host(tmp_path, "unrouted_link"))
    assert [error.route for error in findings] == [(SEED, "02"), (SEED, "02")]


def test_e748_identity_differs_per_seed_and_step(tmp_path: Path) -> None:
    """Two unused routes differ in the step gate's key: ``node_id`` (seed) and ``jq_path`` (step) tell them apart."""
    host = _host(tmp_path, "unused_route")
    manifest = host / "spec" / SEED_MANIFEST_PATH
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["step_requirements"]["02a"] = [SEED]
    document["step_requirements"]["05"] = [SEED]
    manifest.write_text(json.dumps(document), encoding="utf-8")
    findings = _found(host)
    keys = [(error.code, error.owner, error.node_id, error.file, error.jq_path) for error in findings]
    assert len(set(keys)) == len(keys) == 2
    assert [error.jq_path for error in findings] == ['.step_requirements["02a"]', '.step_requirements["05"]']


def test_a_step_requirements_value_that_is_not_a_list_is_skipped(tmp_path: Path) -> None:
    """The route of step 00 is a string (the schema's finding): the check does not crash, reports no route for it and treats the seed as not routed to step 00."""
    found = _found(_host(tmp_path, "non_list_route"))
    assert {error.node_id for error in found if error.code == SEED_LINK_NOT_ROUTED} >= {"scope-password-reset", "risk-reset-link-takeover"}
    assert {error.code for error in found} == {SEED_LINK_NOT_ROUTED}
    assert {error.owner for error in found} == {"step:00"}


def test_route_of_makes_the_e748_of_its_step_wait_on_an_open_item_about_the_seed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """End to end through ``spec-check --step 05``: the E748 of step 05 waits on the open item about the seed (step 06 would not), and blocks without the item."""
    def route_to_05(host: Path) -> None:
        path = host / "spec" / SEED_MANIFEST_PATH
        document = json.loads(path.read_text(encoding="utf-8"))
        document["step_requirements"]["05"] = [SEED]
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    def gate(host: Path) -> dict[str, Any]:
        flags = ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host), "--step", "05", "--json"]
        _code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *flags)
        return json.loads(out)["step_gate"]

    with_item = step_gate_host(tmp_path / "with-item", ["open_items"])
    route_to_05(with_item)
    waiting = [entry for entry in gate(with_item)["waiting"] if entry["error"]["code"] == SEED_ROUTE_UNUSED]
    assert [(entry["error"]["node_id"], entry["waiting_on"]) for entry in waiting] == [(SEED, ["amb-reset-seed"])]
    assert not [error for error in gate(with_item)["blocking"] if error["code"] == SEED_ROUTE_UNUSED]

    without_item = step_gate_host(tmp_path / "without-item")
    route_to_05(without_item)
    blocking = [error for error in gate(without_item)["blocking"] if error["code"] == SEED_ROUTE_UNUSED]
    assert [error["node_id"] for error in blocking] == [SEED]


def test_seed_lint_w140_w551_and_route_checks_on_one_new_shape_manifest(tmp_path: Path) -> None:
    """The new-shape manifest (no key 16) with a declared seed routed to 02 that nothing links and an undeclared seed on disk.

    The older lint and the route checks run side by side and do not agree until M6c removes W140 and W551: W551 names the
    undeclared document, W140 may warn on the routes the new design keeps, and the route check reports the unused route.
    """
    host = _host(tmp_path, "new_shape")
    seed_dir = host / "docs" / "seed"
    (seed_dir / "seed_extra.md").write_text("# Extra\n\nBilling export cadence and invoice numbering.\n", encoding="utf-8")
    (seed_dir / "stray.md").write_text("# Stray\n\nNot declared anywhere.\n", encoding="utf-8")
    lint = lint_seeds(str(ROOT), str(host / "spec"), str(host))
    assert [error.message for error in lint if error.code == "W551"] == ["UNDECLARED_SEED on-disk seed 'stray.md' not declared in seed_manifest.json"]
    assert {error.code for error in lint} <= {"W140", "W551", "W555"}
    assert [(error.code, error.node_id, error.jq_path) for error in _found(host)] == [(SEED_ROUTE_UNUSED, EXTRA, '.step_requirements["02"]')]


def _only_user_of_the_route_in_02a(lifecycle: str) -> Edit:
    """Edit of step 02a: the environment ``dev`` derives from the seed, with *lifecycle*; it is then the one use of the route."""
    def edit(document: dict[str, Any]) -> None:
        dev = document["environments"]["dev"]
        dev["derives_from"].append(SEED)
        dev["lifecycle"] = lifecycle
    return edit


@pytest.mark.parametrize(("lifecycle", "expected"), [
    ("active", []), ("deprecated", []), ("not_applicable", [(SEED_ROUTE_UNUSED, SEED, "step:02a")]),
])
def test_seed_routes_do_not_read_a_not_applicable_node(tmp_path: Path, lifecycle: str, expected: list[tuple[str, str, str]]) -> None:
    """A not_applicable node is no use of a route; a deprecated one is read."""
    assert _rows(_found(_host(tmp_path, "unused_route", **{"02a_delivery_baseline.json": _only_user_of_the_route_in_02a(lifecycle)}))) == expected


def test_a_not_applicable_holder_holds_no_e749(tmp_path: Path) -> None:
    def retire(document: dict[str, Any]) -> None:
        for third_party in document["third_parties"]:
            third_party["lifecycle"] = "not_applicable"

    assert _found(_host(tmp_path, "unrouted_link", **{"02_system_sketch.json": retire})) == []


def _listed(host: str) -> list[list[str | None]]:
    """The seed-route findings of the host at *host* as ``[code, node, jq path, target]``."""
    context = context_of_spec(Path(host) / "spec")
    return [[e.code, e.node_id, e.jq_path, e.target] for e in check_seed_routes(context, "merge")]


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_seed_routes_report_in_the_same_order_whatever_the_hash_seed(seed: int, tmp_path: Path) -> None:
    def route_the_seed_to_four_steps(document: dict[str, Any]) -> None:
        document["step_requirements"].update({"02a": [SEED], "16": [SEED, EXTRA], "05": [SEED]})

    host = _host(tmp_path, "unrouted_seed", **{SEED_MANIFEST_PATH: route_the_seed_to_four_steps})
    listed = seeded(seed, __name__, "_listed", str(host))
    assert listed == _listed(str(host))
    assert [row[0] for row in listed] == [SEED_ROUTE_UNUSED] * 4
    assert [row[2] for row in listed] == ['.step_requirements["02a"]', '.step_requirements["05"]', '.step_requirements["16"]', '.step_requirements["16"]']
    assert [row[1] for row in listed] == [SEED, SEED, SEED, EXTRA]


@pytest.mark.parametrize("routes", ["absent", "empty"])
def test_a_seed_no_entry_routes_anywhere_is_one_e747_and_no_e749(tmp_path: Path, routes: str) -> None:
    """One fault, one finding: the links to a seed nothing routes are not E749 (that code is for a seed routed to another step)."""

    def unroute(document: dict[str, Any]) -> None:
        if routes == "absent":
            del document["step_requirements"]
        else:
            document["step_requirements"] = {}

    findings = _found(_host(tmp_path, **{SEED_MANIFEST_PATH: unroute}))
    assert [error.code for error in findings] == [SEED_NOT_ROUTED] and findings[0].node_id == SEED


def test_a_route_of_a_step_the_spec_does_not_have_is_not_e748(tmp_path: Path) -> None:
    """A key that is no step is the manifest lint's business (W553), not an unused route."""

    def add_unknown_step(document: dict[str, Any]) -> None:
        document["step_requirements"]["99"] = [SEED]

    assert _found(_host(tmp_path, **{SEED_MANIFEST_PATH: add_unknown_step})) == []


# --- the way out each message names (every one is followed to a clean spec-check in the report of the round) ------------------


def _extra_seed(routes: dict[str, list[str]]) -> Edit:
    """Manifest edit: a second seed ``seed-extra`` (no node links it) routed to each step of *routes*."""
    def edit(document: dict[str, Any]) -> None:
        document["seeds"].append({"seed_id": EXTRA, "path": "docs/seed/seed_extra.md", "description": "Extra.", "required": False, "source_type": "doc"})
        for step, seeds in routes.items():
            document["step_requirements"][step] = [*document["step_requirements"].get(step, []), *seeds]
    return edit


def _messages(host: Path, code: str) -> dict[str | None, str]:
    return {error.node_id: error.message for error in _found(host) if error.code == code}


def test_e748_of_a_seeds_only_route_says_to_remove_the_seed_with_it(tmp_path: Path) -> None:
    """Removing the only route of a seed starts E747: the advice names what clears both."""
    message = _messages(_host(tmp_path, **{SEED_MANIFEST_PATH: _extra_seed({"02": [EXTRA]})}), SEED_ROUTE_UNUSED)[EXTRA]
    assert "distil the seed in that step (a node of step 02 lists seed-extra in derives_from)" in message
    assert message.endswith("remove the seed from the manifest (its seeds[] entry, this route and its document), as this is its only route and a seed with no route is E747")


def test_e748_of_a_route_that_is_not_the_seeds_only_one_says_to_remove_the_route(tmp_path: Path) -> None:
    message = _messages(_host(tmp_path, "unused_route"), SEED_ROUTE_UNUSED)[SEED]
    assert message.endswith("distil the seed in that step (a node of step 02a lists seed-accounts in derives_from), or remove the route")


@pytest.mark.parametrize("step", ["05", "16"])
def test_e748_of_a_step_that_cannot_link_a_seed_says_to_move_the_route_not_to_distil_there(tmp_path: Path, step: str) -> None:
    """A node of step 05, or of the trinity steps, cannot list a seed: "distil it in that step" cannot be followed."""
    message = _messages(_host(tmp_path, **{SEED_MANIFEST_PATH: _extra_seed({step: [EXTRA]})}), SEED_ROUTE_UNUSED)[EXTRA]
    assert "distil the seed in that step" not in message
    assert "move the route to a step whose nodes can link a seed (00, 02, 02a) and list seed-extra in derives_from of a node there, or remove the seed from the manifest" in message


def test_e747_of_a_seed_no_node_links_says_to_route_it_and_have_a_node_list_it(tmp_path: Path) -> None:
    message = _messages(_host(tmp_path, "unrouted_seed"), SEED_NOT_ROUTED)[EXTRA]
    assert message.endswith("route it to the step that distils it and list it in derives_from of a node of that step, or remove the seed (its seeds[] entry and its document)")


def test_e747_of_a_seed_a_node_links_names_the_step_of_that_node(tmp_path: Path) -> None:
    """The route clears it at once; removing the seed leaves the link, which the message says to remove and prune."""
    third_party = {"02_system_sketch.json": lambda doc: doc["third_parties"][0]["derives_from"].append(EXTRA)}
    message = _messages(_host(tmp_path, "unrouted_seed", **third_party), SEED_NOT_ROUTED)[EXTRA]
    assert "route it to step 02 (where a node lists it in derives_from), or remove the seed (its seeds[] entry and its document) and the derives_from links to it, then run specdev attest --prune" in message


def test_e749_says_to_prune_after_removing_the_link(tmp_path: Path) -> None:
    messages = _messages(_host(tmp_path, "unrouted_link"), SEED_LINK_NOT_ROUTED)
    assert messages["tp-argon2"].endswith('add seed-accounts to step_requirements["02"], or remove the link and run specdev attest --prune (a derives_from that would be left empty needs another entry)')


def test_a_seed_listed_twice_under_one_step_is_one_unused_route(tmp_path: Path) -> None:
    host = _host(tmp_path, **{SEED_MANIFEST_PATH: _extra_seed({"02a": [EXTRA, EXTRA]})})
    assert _rows(_found(host)) == [(SEED_ROUTE_UNUSED, EXTRA, "step:02a")]


def test_a_route_to_an_id_that_is_no_seed_is_not_reported_here(tmp_path: Path) -> None:
    """It is E520 of the seed lint; the route checks neither report it nor fail on it."""
    def route_unknown(document: dict[str, Any]) -> None:
        document["step_requirements"]["02a"] = ["seed-nope"]

    assert _found(_host(tmp_path, **{SEED_MANIFEST_PATH: route_unknown})) == []


def test_the_routes_of_the_manifest_leave_out_what_is_not_a_list_of_ids(tmp_path: Path) -> None:
    context = _context(_host(tmp_path))
    context.__dict__["manifest"] = {"step_requirements": {"00": "s", "02": [SEED, 7]}}
    assert _routes(context) == {"02": [SEED]}
