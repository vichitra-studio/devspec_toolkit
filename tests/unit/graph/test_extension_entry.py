"""The manifest entry of an extension is a node (DEVSPEC-245, piece B, decision 4).

Kind ``extension``, role ``plan``, a ``lifecycle`` and a required ``justified_by`` (at least one id) to a component, a
third party, a capability, an FR or an NFR.  The link resolves and is lock-tracked like any other; it is not a use of
its target, so the E740 of a node that only an entry names is the E740 the host saw before.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.gitview import read_seed_texts
from specdev_tools.graph.host_kinds import load_kind_registry
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.trace.lockfile import Lock
from specdev_tools.trace.suspects import check_lock, missing_entry_errors
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.no_dangling import check_no_dangling
from specdev_tools.validation.graph_checks.use_table import EXCLUDED_VERBS, furthest_steps, use_pairs
from specdev_tools.validation.validate import validate_file

from ..trace._lock_support import lock_for
from ._extension import CRITERION, ENTRY, MANIFEST, ROADMAP, STEP_13, TABLE, criterion, edit, extension_host, graph_of, spec_of
from ._synth import EXAMPLE_SPEC, ROOT, copy_example

JUSTIFIED_BY = "justified_by"
ACCEPTED = {
    "component": "identity-service", "third-party": "tp-mailrelay", "capability": "cap-account-recovery",
    "fr": "fr-password-reset", "nfr": "nfr-latency-reset-email",
}
"""The five kinds decision 4 names, each with a node of the worked example."""
REFUSED = {
    "criterion": "ac-password-reset-1", "connection": "conn-identity-to-mailrelay", "metric": "metric-recovery-time",
    "invariant": "inv-reset-token-single-use", "fixture": "fix-password-reset-reused-token", "threat": "threat-reset-token-replay",
    "table": TABLE, "task": "task-implement-password-reset-confirm",
}
"""Kinds next to the five (a criterion beside its FR, a connection beside its component), a host kind of the same step, and a node of a later step."""
UNUSED_NFR, UNUSED_FR = "nfr-latency-reset-email", "fr-password-reset-request"
"""Two nodes of the worked example that nothing uses (E740 in the plain example)."""
VALID_MANIFEST = ROOT / "tests" / "fixtures" / "step_13" / "valid_manifest.json"


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return extension_host(tmp_path / "host")


def _entry(manifest: dict[str, Any], entry_id: str = ENTRY) -> dict[str, Any]:
    return next(found for found in manifest["extensions"] if found["extension_id"] == entry_id)


def _justify(host: Path, *targets: str) -> None:
    edit(host, MANIFEST, lambda manifest: _entry(manifest).update(justified_by=list(targets)))


def _extension_decl(registry: Any) -> Any:
    return next(decl for file in registry.files for decl in file.kinds if decl.kind == "extension")


# --- the declaration ----------------------------------------------------------------------------------------------------


def test_the_kind_extension_is_a_plan_kind_with_one_required_link_to_the_five_kinds() -> None:
    registry = load_kind_registry(str(ROOT))
    decl = _extension_decl(registry)
    file = next(file for file in registry.files if decl in file.kinds)
    assert (file.pattern, file.step, decl.role, decl.id_field, decl.host) == (MANIFEST, "13", "plan", "extension_id", False)
    assert [link.field for link in decl.links] == [JUSTIFIED_BY]
    link = decl.links[0]
    assert set(link.kinds) == set(ACCEPTED) and len(link.kinds) == 5
    assert (link.required, link.same_step_kinds) == (True, ())


def test_the_schema_of_an_entry_has_a_lifecycle_and_requires_justified_by_with_one_id_at_least() -> None:
    schema = json.loads((ROOT / "schema" / "13_extension_manifest.schema.json").read_text(encoding="utf-8"))
    items = schema["properties"]["extensions"]["items"]
    assert JUSTIFIED_BY in items["required"]
    assert (items["properties"][JUSTIFIED_BY]["type"], items["properties"][JUSTIFIED_BY]["minItems"]) == ("array", 1)
    assert items["properties"]["lifecycle"]["$ref"] == "vc:core:graph#lifecycle"
    assert "lifecycle" not in items["required"]


def _schema_errors(tmp_path: Path, change: Any) -> list[str]:
    manifest = json.loads(VALID_MANIFEST.read_text(encoding="utf-8"))
    change(manifest["extensions"][0])
    path = tmp_path / MANIFEST
    path.write_text(json.dumps(manifest), encoding="utf-8")
    errors = validate_file(str(ROOT), str(path), include_quality_lint=False, include_canonical_integrity=False)
    return [error.render() for error in errors if error.code == "E520"]


def test_an_entry_that_names_one_node_is_valid_and_one_that_names_none_is_e520(tmp_path: Path) -> None:
    assert _schema_errors(tmp_path, lambda entry: None) == []
    assert _schema_errors(tmp_path, lambda entry: entry.update(justified_by=["fr-order-history"])) == []
    missing = _schema_errors(tmp_path, lambda entry: entry.pop(JUSTIFIED_BY))
    assert len(missing) == 1 and JUSTIFIED_BY in missing[0] and "required" in missing[0]
    empty = _schema_errors(tmp_path, lambda entry: entry.update(justified_by=[]))
    assert len(empty) == 1 and JUSTIFIED_BY in empty[0]
    not_a_list = _schema_errors(tmp_path, lambda entry: entry.update(justified_by="fr-order-history"))
    assert len(not_a_list) == 1 and JUSTIFIED_BY in not_a_list[0]


@pytest.mark.parametrize(("lifecycle", "valid"), [("active", True), ("deprecated", True), ("not_applicable", True), ("retired", False), ("", False)])
def test_an_entry_takes_the_three_lifecycle_states_and_no_other(tmp_path: Path, lifecycle: str, valid: bool) -> None:
    errors = _schema_errors(tmp_path, lambda entry: entry.update(lifecycle=lifecycle))
    assert (errors == []) is valid, errors
    if not valid:
        assert len(errors) == 1 and "lifecycle" in errors[0]


def test_a_manifest_with_no_entry_is_valid_as_before(tmp_path: Path) -> None:
    plain = EXAMPLE_SPEC / MANIFEST
    assert json.loads(plain.read_text(encoding="utf-8"))["extensions"] == []
    errors = validate_file(str(ROOT), str(plain), include_quality_lint=False, include_canonical_integrity=False)
    assert [error.render() for error in errors] == []


# --- the node and its links ---------------------------------------------------------------------------------------------


def test_the_entry_is_a_plan_node_of_step_13_with_its_links(host: Path) -> None:
    node = graph_of(host).by_id[ENTRY]
    assert (node.kind, node.role, node.step, node.file, node.jq_path, node.lifecycle, node.scope) == (
        "extension", "plan", "13", MANIFEST, ".extensions[0]", "active", None,
    )
    assert [(link.field, link.target) for link in node.links] == [(JUSTIFIED_BY, "fr-password-reset"), (JUSTIFIED_BY, "identity-service")]
    assert [error.render() for error in resolve_graph(graph_of(host))] == []


def test_the_lifecycle_of_an_entry_is_read(host: Path) -> None:
    edit(host, MANIFEST, lambda manifest: _entry(manifest).update(lifecycle="deprecated"))
    assert graph_of(host).by_id[ENTRY].lifecycle == "deprecated"


def test_justified_by_accepts_each_of_the_five_kinds(host: Path) -> None:
    graph = graph_of(host)
    assert {kind: graph.by_id[node_id].kind for kind, node_id in ACCEPTED.items()} == {kind: kind for kind in ACCEPTED}
    _justify(host, *ACCEPTED.values())
    assert [error.render() for error in resolve_graph(graph_of(host))] == []
    for node_id in ACCEPTED.values():  # and each alone
        _justify(host, node_id)
        assert [error.render() for error in resolve_graph(graph_of(host))] == [], node_id


@pytest.mark.parametrize("kind", sorted(REFUSED))
def test_justified_by_refuses_any_other_kind(host: Path, kind: str) -> None:
    target = REFUSED[kind]
    assert graph_of(host).by_id[target].kind == kind
    _justify(host, "fr-password-reset", target)
    errors = resolve_graph(graph_of(host))
    assert [(error.code, error.node_id, error.owner, error.target) for error in errors] == [("E701", ENTRY, STEP_13, f"{JUSTIFIED_BY}->{target}")]
    assert f"target '{target}' is a" in errors[0].message and "the field accepts: " in errors[0].message
    assert set(errors[0].message.split("the field accepts: ")[1].split(", ")) == set(ACCEPTED)


def test_justified_by_to_no_node_is_e700_and_a_link_listed_twice_is_two_links(host: Path) -> None:
    _justify(host, "fr-password-reset", "fr-password-reset")
    graph = graph_of(host)
    assert [link.target for link in graph.by_id[ENTRY].links] == ["fr-password-reset", "fr-password-reset"]
    assert [error.render() for error in resolve_graph(graph)] == []
    _justify(host, "fr-password-reset", "fr-never-written")
    errors = resolve_graph(graph_of(host))
    assert [(error.code, error.node_id, error.owner, error.target) for error in errors] == [("E700", ENTRY, STEP_13, f"{JUSTIFIED_BY}->fr-never-written")]
    assert "no node has that id" in errors[0].message


def test_an_entry_with_no_data_file_and_no_schema_is_still_a_node(tmp_path: Path) -> None:
    host = extension_host(tmp_path / "host", refined=False)
    for path in (spec_of(host) / "extensions").iterdir():
        path.unlink()
    graph = graph_of(host)
    assert graph.by_id[ENTRY].kind == "extension" and TABLE not in graph.by_id
    assert [error.render() for error in resolve_graph(graph)] == []


# --- the link is lock-tracked -------------------------------------------------------------------------------------------


def _lock_findings(host: Path, lock: Lock) -> list[tuple[str, str | None, str | None]]:
    graph = graph_of(host)
    found = [*missing_entry_errors(graph, lock), *check_lock(graph, lock, read_seed_texts(graph, str(host)))]
    return [(error.code, error.node_id, error.target) for error in found if error.node_id == ENTRY]


def test_justified_by_is_unaccepted_until_attested_and_suspect_after_an_edit_of_its_target(host: Path) -> None:
    assert _lock_findings(host, Lock(())) == [
        ("E761", ENTRY, f"{JUSTIFIED_BY}->fr-password-reset"), ("E761", ENTRY, f"{JUSTIFIED_BY}->identity-service"),
    ]
    accepted = lock_for(graph_of(host), host)
    assert _lock_findings(host, accepted) == []
    edit(host, "04_fr_list.json", lambda frs: frs["functional_requirements"][0].update(priority="should-have"))
    assert json.loads((spec_of(host) / "04_fr_list.json").read_text(encoding="utf-8"))["functional_requirements"][0]["fr_id"] == "fr-password-reset"
    assert _lock_findings(host, accepted) == [("E763", ENTRY, f"{JUSTIFIED_BY}->fr-password-reset")]  # not the link to the component
    assert _lock_findings(host, lock_for(graph_of(host), host)) == []  # read again and accepted


# --- justified_by is not a use ------------------------------------------------------------------------------------------


def _dangling(spec: Path) -> dict[str, tuple[str | None, str]]:
    """``{node id: (owner, message)}`` of the E740 findings of the spec folder *spec*."""
    context = GraphCheckContext.from_graph(build_graph(str(spec), str(ROOT)), None)
    return {error.node_id: (error.owner, error.message) for error in check_no_dangling(context, "merge") if error.node_id}


def test_justified_by_is_among_the_verbs_that_are_never_a_use(host: Path) -> None:
    assert JUSTIFIED_BY in EXCLUDED_VERBS
    plain, with_extension = build_graph(str(EXAMPLE_SPEC), str(ROOT)), graph_of(host)
    for graph in (plain, with_extension):
        assert JUSTIFIED_BY in [link.field for link in graph.decls["extension"].links]  # the link is declared, and still no use
        for kind in ACCEPTED:
            assert [use for use in use_pairs(kind, graph.decls) if use.verb == JUSTIFIED_BY or use.holder_kind == "extension"] == [], kind
    # the owner step of an unused node of the three kinds with no row of their own is the step it was
    before, after = furthest_steps(plain.decls, plain.shape), furthest_steps(with_extension.decls, with_extension.shape)
    assert {kind: after[kind] for kind in ("capability", "fr", "nfr")} == {kind: before[kind] for kind in ("capability", "fr", "nfr")}
    assert {before[kind] for kind in ("capability", "fr", "nfr")} == {"14"}  # a task criterion refines them: later than step 13


def test_the_e740_of_an_unused_nfr_is_the_one_of_the_plain_example_also_when_an_entry_names_it(tmp_path: Path, host: Path) -> None:
    plain = _dangling(copy_example(tmp_path / "plain"))
    assert UNUSED_NFR in plain and plain[UNUSED_NFR][0] == "step:14"
    assert JUSTIFIED_BY not in plain[UNUSED_NFR][1] and "extension" not in plain[UNUSED_NFR][1]
    assert _dangling(spec_of(host))[UNUSED_NFR] == plain[UNUSED_NFR]  # the entry names the FR and the component
    _justify(host, UNUSED_NFR)
    assert [link.source for link in graph_of(host).incoming[UNUSED_NFR] if link.field == JUSTIFIED_BY] == [ENTRY]
    assert _dangling(spec_of(host))[UNUSED_NFR] == plain[UNUSED_NFR]  # named by the entry: still unused, same owner, same text


def test_an_fr_that_only_an_entry_names_is_unused(tmp_path: Path, host: Path) -> None:
    plain = _dangling(copy_example(tmp_path / "plain"))
    assert UNUSED_FR in plain
    _justify(host, UNUSED_FR)
    found = _dangling(spec_of(host))
    assert UNUSED_FR in found and found[UNUSED_FR][0] == plain[UNUSED_FR][0]
    assert JUSTIFIED_BY not in found[UNUSED_FR][1]


def test_a_link_that_is_a_use_ends_the_e740_where_justified_by_did_not(host: Path) -> None:
    _justify(host, UNUSED_NFR)
    assert UNUSED_NFR in _dangling(spec_of(host))
    edit(host, ROADMAP, lambda roadmap: criterion(roadmap).update(refines=[UNUSED_NFR]))
    assert graph_of(host).by_id[CRITERION].links[0].target == UNUSED_NFR
    assert UNUSED_NFR not in _dangling(spec_of(host))


def test_an_entry_is_not_itself_checked_for_use(host: Path) -> None:
    """Nothing can link to an entry; a plan node is outside the no-dangling rule (the plan's reason for the role)."""
    graph = graph_of(host)
    assert graph.incoming.get(ENTRY, []) == []
    assert ENTRY not in _dangling(spec_of(host))
