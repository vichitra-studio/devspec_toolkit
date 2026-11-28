"""``specdev node rename`` end to end on the worked example with its committed lock (WI-M5-12)."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.graph.check import run_graph_check
from specdev_tools.graph.ids import mint_slug
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.trace import rename as rename_module
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.trace.label_rename import label_users, own_leaves, rename_label
from specdev_tools.trace.lockfile import Lock, LockEntry, lock_path
from specdev_tools.trace.rename import RenameRefusedError, rename_node
from specdev_tools.trace.suspects import orphan_entries
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.term_use import check_term_use
from specdev_tools.validation.spec_check import run_spec_check_json

from unit.graph._synth import ROOT, load_doc, run_cli, write_json
from unit.validation.graph_checks._term_support import label_matches
from unit.trace._lock_support import EXAMPLE_HOST, gap_providers  # noqa: F401  (a fixture)
from unit.trace._suspects_support import CRITERION, Example

NEW = "ac-password-reset-3b"
FR = "fr-password-reset"
CAPABILITY = "cap-account-recovery"
ANCHOR_FILE = "16_impl_context.json"
FR_FILE = "04_fr_list.json"
HISTORICAL_HOLDER = ("tc-confirm-expired-token", "refines")
LIVE_HOLDERS = {
    ("err-password-reset-confirm-token-expired", "derives_from"),
    ("fix-password-reset-expired-token", "verifies"),
    ("ec-token-at-expiry-second", "mitigated_by"),
}
FILES_OF_LIVE_HOLDERS = {FR_FILE, "05_interface_contracts.json", "08_fixtures.json", "11_redteam.json"}
OLD_LABEL, NEW_LABEL, TERM = "reset token", "recovery code", "term-reset-token"
LABEL_USERS = [
    "ac-password-reset-2", "ac-password-reset-3", FR, "err-password-reset-confirm-token-expired",
    "inv-reset-token-single-use", "task-implement-password-reset-confirm",
]


@pytest.fixture
def host(tmp_path: Path, gap_providers: Any) -> Example:
    """The worked example in a copy, with no coverage-gap provider registered (the role gaps of the partial example are not the subject here)."""
    root = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, root)
    return Example(root)


def _flags(host: Example) -> list[str]:
    return ["--repo-root", str(ROOT), "--spec-root", str(host.spec), "--git-root", str(host.host)]


def _rename(host: Example, *args: str) -> tuple[int, str]:
    return run_cli("node", "rename", *args, *_flags(host))


def _snapshot(host: Example) -> dict[str, bytes]:
    return {str(path.relative_to(host.host)): path.read_bytes() for path in host.host.rglob("*") if path.is_file()}


def _checks(host: Example) -> dict[str, Any]:
    _errors, context = run_spec_check_json(str(ROOT), str(host.spec), git_root=str(host.host))
    return context["checks"]


def _finding_codes(host: Example, *names: str) -> list[str]:
    checks = _checks(host)
    return [finding["code"] for name in names for finding in checks[name]["findings"]]


def _link_targets(host: Example, holder: str, field: str) -> list[str]:
    return [link.target for link in host.graph().by_id[holder].links if link.field == field]


def _entry_targets(host: Example, holder: str, field: str) -> list[str]:
    return [entry.target for entry in host.lock().entries if (entry.source, entry.field) == (holder, field)]


# --- the rename --------------------------------------------------------------------------------------------------------

def test_rename_rewrites_inbound_links_lock_entries_and_aliases_in_one_change(host: Example) -> None:
    host.close_milestone()
    before, lock_before = _snapshot(host), host.lock()
    code, out = _rename(host, CRITERION, NEW)
    assert code == 0 and out.startswith(f"renamed {CRITERION} -> {NEW} ({FR_FILE} ") and "links rewritten (3):" in out
    graph = host.graph()
    assert CRITERION not in graph.by_id and graph.by_id[NEW].aliases == (CRITERION,)
    for holder, field in LIVE_HOLDERS:
        for targets in (_link_targets(host, holder, field), _entry_targets(host, holder, field)):
            assert NEW in targets and CRITERION not in targets
    holder, field = HISTORICAL_HOLDER
    assert CRITERION in _link_targets(host, holder, field) and CRITERION in _entry_targets(host, holder, field)
    assert NEW not in _link_targets(host, holder, field) + _entry_targets(host, holder, field)
    changed = {path for path, content in _snapshot(host).items() if before.get(path) != content}
    assert changed == {f"spec/{name}" for name in FILES_OF_LIVE_HOLDERS} | {"spec/extras/trace.lock.json"}
    assert {entry.key for entry in lock_before.entries} - {entry.key for entry in host.lock().entries} == {
        (*pair, CRITERION) for pair in LIVE_HOLDERS
    }
    assert {(e.content_hash, e.chain_stamp) for e in host.lock().entries} == {(e.content_hash, e.chain_stamp) for e in lock_before.entries}


@pytest.mark.parametrize("old", [CRITERION, FR, CAPABILITY])
def test_rename_changes_no_hash_and_no_suspects(host: Example, old: str) -> None:
    host.close_milestone()
    graph = host.graph()
    before = compute_all(graph, host.seed_texts(graph))
    assert host.suspect_keys() == set()
    new = f"{old}-v2"
    assert _rename(host, old, new)[0] == 0
    after_graph = host.graph()
    assert compute_all(after_graph, host.seed_texts(after_graph)) == {new if key == old else key: value for key, value in before.items()}
    assert host.suspect_keys() == set()
    third = f"{old}-v3"
    assert _rename(host, new, third)[0] == 0
    assert host.suspect_keys() == set() and host.graph().by_id[third].aliases == (old, new)


@pytest.mark.parametrize("old", [CRITERION, FR, CAPABILITY])
def test_rename_leaves_no_suspect_link(host: Example, old: str) -> None:
    assert _rename(host, old, f"{old}-v2")[0] == 0
    checks = _checks(host)
    codes = [finding["code"] for name in ("graph", "trace-lock") for finding in checks[name]["findings"]]
    assert not {"E761", "E762", "E763", "E778"} & set(codes) and codes == []
    code, out = run_cli("stale", *_flags(host))
    assert code == 0 and "no pending replay" in out


def test_historical_and_record_links_resolve_through_alias(host: Example) -> None:
    host.close_milestone()
    code, out = _rename(host, "ms-account-recovery", "ms-account-recovery-v2")
    assert code == 1 and "E767" in out and "is closed" in out, "a closed milestone's step-14 node is not renamed outside a migration"
    (host.spec / "specdev_version").write_text("toolkit_version: 1.2.0\nmigration_status: in_progress\n", encoding="utf-8")
    assert _rename(host, "ms-account-recovery", "ms-account-recovery-v2")[0] == 0
    assert _rename(host, CRITERION, NEW)[0] == 0
    graph = host.graph()
    assert resolve_graph(graph) == [] and orphan_entries(graph, host.lock()) == []
    record = graph.by_id["anchor-ms-account-recovery"]
    assert [link.target for link in record.links] == ["ms-account-recovery"]
    assert graph.find("ms-account-recovery") is graph.by_id["ms-account-recovery-v2"]
    assert [link.source for link in graph.incoming[NEW] if link.source == HISTORICAL_HOLDER[0]] == [HISTORICAL_HOLDER[0]]
    assert "E778" not in _finding_codes(host, "graph")
    code, out = run_cli("node", "show", CRITERION, *_flags(host))
    assert code == 0 and out.startswith(NEW) and f"aliases: {CRITERION}" in out
    assert historical_node_ids(graph) >= {HISTORICAL_HOLDER[0], "tc-confirm-reused-token", "PWRESET_CONFIRM_EXPIRED_01"}


def test_live_holder_using_alias_is_e778_historical_holder_is_not(host: Example) -> None:
    host.close_milestone()
    assert _rename(host, CRITERION, NEW)[0] == 0
    assert _finding_codes(host, "graph") == []
    host.edit_item("fix-password-reset-expired-token", lambda item: item.update(verifies=[CRITERION, "api-password-reset-confirm"]))
    findings = _checks(host)["graph"]["findings"]
    assert [(f["code"], f["node_id"], f["owner"]) for f in findings] == [("E778", "fix-password-reset-expired-token", "step:08")]
    assert f"use the current id '{NEW}'" in findings[0]["message"]
    graph = host.graph()
    assert [e.code for e in run_graph_check(str(host.spec), str(ROOT), graph=graph, lock=host.lock())] == ["E778"]
    assert [e.code for e in run_graph_check(str(host.spec), str(ROOT), graph=graph)] == []


def test_alias_id_space_collisions(host: Example) -> None:
    host.edit_item("cap-account-recovery", lambda item: item.update(aliases=[FR]))
    host.edit_item("fr-password-reset-request", lambda item: item.update(aliases=["old-request"]))
    host.edit_item(FR, lambda item: item.update(aliases=["old-request"]))
    findings = _checks(host)["graph"]["findings"]
    assert [(f["code"], f["node_id"], f["owner"]) for f in findings] == [
        ("E771", CAPABILITY, "step:01"), ("E771", "fr-password-reset-request", "step:04"),
    ]
    assert "is the id of a fr" in findings[0]["message"] and "also an alias of 'fr-password-reset'" in findings[1]["message"]


def test_minting_never_reuses_a_live_alias_and_an_explicit_id_equal_to_an_alias_is_refused(host: Example) -> None:
    assert _rename(host, FR, "fr-password-reset-v2")[0] == 0
    flags = _flags(host)
    new_fr = {
        "statement": "The system shall let an admin revoke an outstanding reset token before it expires.", "scope": "in", "priority": "must-have",
        "capability_ref": {"id": "cn:project:capability:account-recovery", "kind": "capability", "version": "1.0.0"},
        "derives_from": [CAPABILITY],
        "acceptance_criteria": [{"text": "Given a revoked token, when it is redeemed, then no password changes.", "scope": "in"}] * 2,
    }
    code, out = run_cli("json", "insert", "--step", "04", ".functional_requirements", json.dumps({**new_fr, "fr_id": FR}), *flags)
    assert code == 1 and out.startswith("E767") and "E771" in out and "is the id of a fr" in out
    assert FR not in host.graph().by_id
    slug = mint_slug(new_fr["statement"], set(), prefix="fr-")
    host.edit_item("fr-password-reset-request", lambda item: item.update(aliases=[slug]))
    code, out = run_cli("json", "insert", "--step", "04", ".functional_requirements", json.dumps(new_fr), *flags, "--dry-run", "--json")
    assert code == 0, out
    minted = json.loads(out)["minted"]
    assert slug not in minted and f"{slug}-2" in minted


def test_rename_to_retired_unaliased_id_allowed(host: Example) -> None:
    retired = "ec-token-at-expiry-second"
    code, out = run_cli("json", "delete", "--id", retired, *_flags(host))
    assert code == 0, out
    assert retired not in host.graph().by_id and host.graph().alias_index == {}
    code, out = _rename(host, "fr-password-reset-request", retired)
    assert code == 0, out
    graph = host.graph()
    assert graph.by_id[retired].kind == "fr" and graph.by_id[retired].aliases == ("fr-password-reset-request",)
    assert _checks(host)["graph"]["findings"] == [] and host.suspect_keys() == set()


def test_replaces_naming_live_node_is_error(host: Example) -> None:
    host.edit_item("fr-password-reset-request", lambda item: item.update(replaces=[FR]))
    findings = _checks(host)["graph"]["findings"]
    assert [(f["code"], f["node_id"], f["owner"]) for f in findings] == [("E772", "fr-password-reset-request", "step:04")]
    host.edit_item("fr-password-reset-request", lambda item: item.update(replaces=["fr-deleted-long-ago"]))
    assert _checks(host)["graph"]["findings"] == []
    assert _rename(host, FR, "fr-password-reset-v2")[0] == 0
    host.edit_item("fr-password-reset-request", lambda item: item.update(replaces=[FR]))
    assert [f["code"] for f in _checks(host)["graph"]["findings"]] == ["E772"]


# --- refusals ----------------------------------------------------------------------------------------------------------

def _duplicate_an_fr(host: Example) -> None:
    document = load_doc(host.spec, FR_FILE)
    document["functional_requirements"].append({"fr_id": "fr-twin", "statement": "One."})
    document["functional_requirements"].append({"fr_id": "fr-twin", "statement": "Two."})
    write_json(host.spec, FR_FILE, document)


_REFUSALS = {
    "seed": ("seed-accounts", "seed-renamed", "is a seed"),
    "duplicate": ("fr-twin", "fr-twin-renamed", "is defined more than once (E704); fix the duplicate first"),
    "record": ("anchor-ms-account-recovery", "anchor-renamed", "which is a record"),
    "map key": ("dev", "dev-renamed", "is the key of a map"),
    "same id": (CRITERION, CRITERION, "the old and the new id are the same"),
    "live id": (CRITERION, "ac-password-reset-2", "is already the id of a criterion"),
    "not an id": (CRITERION, "has space", "is not an id"),
}


@pytest.mark.parametrize(("old", "new", "message"), list(_REFUSALS.values()), ids=list(_REFUSALS))
def test_rename_refuses_seed_duplicate_record_and_same_id_under_e770(host: Example, old: str, new: str, message: str) -> None:
    _duplicate_an_fr(host)
    before = _snapshot(host)
    code, out = _rename(host, old, new)
    assert code == 1 and out.startswith("E770") and message in out
    assert len(out.strip().splitlines()) == 1 and _snapshot(host) == before


def test_rename_refuses_an_alias_that_a_node_holds_and_a_lock_that_has_entries_under_the_new_id(host: Example) -> None:
    assert _rename(host, CRITERION, NEW)[0] == 0
    code, out = _rename(host, NEW, CRITERION)
    assert code == 1 and out.startswith("E770") and f"is an alias of '{NEW}'" in out
    stray = LockEntry("fix-expired-token-v2", "verifies", "api-password-reset-confirm", "sha256:" + "0" * 64, "sha256:" + "0" * 64)
    host.write_lock(Lock((*host.lock().entries, stray)))
    before = _snapshot(host)
    code, out = _rename(host, "fix-password-reset-expired-token", "fix-expired-token-v2")
    assert code == 1 and out.startswith("E770") and "already has entries under the id" in out and _snapshot(host) == before


def test_rename_unknown_id_is_e706_with_nearest_ids_exit_1(host: Example) -> None:
    before = _snapshot(host)
    code, out = _rename(host, "ac-password-reset-33", NEW)
    assert code == 1 and out.startswith("E706") and "ac-password-reset-3" in out and "nearest" in out
    code, out = _rename(host, "ac-password-reset-33", NEW, "--json")
    assert code == 1 and json.loads(out)["errors"][0]["code"] == "E706"
    assert _snapshot(host) == before


def test_rename_refuses_an_unknown_id(host: Example) -> None:
    with pytest.raises(FindingError) as raised:
        rename_node(str(host.spec), str(ROOT), "ac-nobody", NEW, apply=True)
    assert raised.value.error.code == "E706" and raised.value.unknown_id
    with pytest.raises(RenameRefusedError):
        rename_node(str(host.spec), str(ROOT), CRITERION, CRITERION)


# --- dry run and all or nothing ----------------------------------------------------------------------------------------

def test_rename_dry_run_writes_nothing(host: Example) -> None:
    before = _snapshot(host)
    code, out = _rename(host, CRITERION, NEW, "--dry-run")
    assert code == 0 and out.startswith(f"[dry-run] would rename {CRITERION} -> {NEW}") and "links rewritten (4):" in out
    code, out = _rename(host, CRITERION, NEW, "--dry-run", "--json")
    document = json.loads(out)
    assert code == 0 and document["written"] is False and document["new_id"] == NEW and len(document["lock_entries"]) == 4
    assert _snapshot(host) == before


def test_rename_is_all_or_nothing_when_a_write_fails(host: Example, monkeypatch: pytest.MonkeyPatch) -> None:
    before = _snapshot(host)
    real, calls = rename_module.json_write_atomic, []

    def fail_on_the_third(path: str, text: str) -> None:
        calls.append(path)
        if len(calls) == 3:
            raise OSError("disk full")
        real(path, text)

    monkeypatch.setattr(rename_module, "json_write_atomic", fail_on_the_third)
    with pytest.raises(OSError, match="disk full"):
        rename_node(str(host.spec), str(ROOT), CRITERION, NEW, apply=True)
    assert len(calls) == 3 and _snapshot(host) == before
    monkeypatch.setattr(rename_module, "json_write_atomic", real)
    assert rename_node(str(host.spec), str(ROOT), CRITERION, NEW, apply=True).written


def test_rename_writes_nothing_when_an_edit_adds_a_schema_violation(host: Example) -> None:
    before = _snapshot(host)
    code, out = _rename(host, CRITERION, "Not Valid")
    assert code == 1 and out.startswith("E770") and _snapshot(host) == before
    assert Path(lock_path(str(host.spec))).read_bytes() == before["spec/extras/trace.lock.json"]


# --- the label ---------------------------------------------------------------------------------------------------------

def _label_leaves(host: Example) -> dict[str, str]:
    """Every string of the files of steps 04 to 14 that holds the old label as whole words, by node id and path."""
    graph = host.graph()
    pattern = re.compile(rf"(?<!\w){re.escape(OLD_LABEL)}(?!\w)")
    found: dict[str, str] = {}
    for rel, document in graph.documents.items():
        if rel.split("_")[0] in {"04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15"}:
            found.update({f"{rel}:{index}": text for index, text in enumerate(_strings(document)) if pattern.search(text)})
    return found


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    items = value.values() if isinstance(value, dict) else value if isinstance(value, list) else []
    return [text for item in items for text in _strings(item)]


def test_label_rename_rewrites_exact_uses_and_lists_each(host: Example) -> None:
    before = _snapshot(host)
    code, out = _rename(host, "--label", TERM, NEW_LABEL)
    assert code == 0 and out.startswith(f"relabelled {TERM}: '{OLD_LABEL}' -> '{NEW_LABEL}'") and "uses rewritten (6):" in out
    graph = host.graph()
    assert load_doc(host.spec, "03_glossary.json")["terms"][0]["term"] == NEW_LABEL
    assert "redeeming a single-use recovery code emailed" in graph.documents[FR_FILE]["functional_requirements"][0]["statement"]
    assert graph.by_id[TERM].aliases == () and not _label_leaves(host)
    changed = {path for path, content in _snapshot(host).items() if before.get(path) != content}
    assert changed == {f"spec/{name}" for name in ("03_glossary.json", FR_FILE, "05_interface_contracts.json", "06_invariants.json", "14_roadmap.json")}
    assert before["spec/extras/trace.lock.json"] == _snapshot(host)["spec/extras/trace.lock.json"]
    # The new label is a contract change of the term and of each use: the links into them are suspect until attested.
    assert len(host.suspect_keys()) == 24 and ("err-password-reset-confirm-token-expired", "derives_from", CRITERION) in host.suspect_keys()


def _rename_json(host: Example, *args: str) -> str:
    code, out = _rename(host, *args, "--json")
    assert code == 0, out
    return out


def test_label_rename_lists_each_use_with_node_field_and_texts(host: Example) -> None:
    document = json.loads(_rename_json(host, "--label", TERM, NEW_LABEL, "--dry-run"))
    assert [use["node_id"] for use in document["uses"]] == LABEL_USERS
    first = document["uses"][0]
    assert (first["field_path"], first["old_text"].count(OLD_LABEL), first["new_text"].count(NEW_LABEL)) == (".text", 1, 1)
    assert first["new_text"] == first["old_text"].replace(OLD_LABEL, NEW_LABEL)
    assert document["old_label"] == OLD_LABEL and document["written"] is False


def test_label_rename_is_one_change_and_leaves_no_old_label_match(host: Example, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _label_leaves(host)
    before = _snapshot(host)
    real, calls = rename_module.json_write_atomic, []

    def fail_on_the_third(path: str, text: str) -> None:
        calls.append(path)
        if len(calls) == 3:
            raise OSError("disk full")
        real(path, text)

    monkeypatch.setattr(rename_module, "json_write_atomic", fail_on_the_third)
    with pytest.raises(OSError, match="disk full"):
        rename_label(str(host.spec), str(ROOT), TERM, NEW_LABEL, apply=True)
    assert _snapshot(host) == before and _label_leaves(host)
    monkeypatch.setattr(rename_module, "json_write_atomic", real)
    assert rename_label(str(host.spec), str(ROOT), TERM, NEW_LABEL, apply=True).written
    assert _label_leaves(host) == {}


def test_label_rename_dry_run_writes_nothing(host: Example) -> None:
    before = _snapshot(host)
    code, out = _rename(host, "--label", TERM, NEW_LABEL, "--dry-run")
    assert code == 0 and out.startswith(f"[dry-run] would relabel {TERM}") and "uses rewritten (6):" in out
    assert _snapshot(host) == before


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((FR, NEW_LABEL), "is a fr, not a glossary term"),
        ((TERM, OLD_LABEL), "already has the label"),
        ((TERM, " padded "), "is not a label"),
        ((TERM, ""), "is not a label"),
    ],
)
def test_label_rename_refusals_are_e770_and_write_nothing(host: Example, args: tuple[str, str], message: str) -> None:
    before = _snapshot(host)
    code, out = _rename(host, "--label", *args)
    assert code == 1 and out.startswith("E770") and message in out and _snapshot(host) == before
    code, out = _rename(host, "--label", "term-nobody", NEW_LABEL)
    assert code == 1 and out.startswith("E706")


# --- review round 1 (C-03, C-07): a node of every kind can be renamed to an id valid for that kind -----------------------

#: Kinds the design refuses to rename: the seed (id is its manifest key), records (written by the toolkit), map-keyed nodes.
_REFUSED_KINDS = {"seed", "evidence-record", "verification-record", "ambiguity-item", "anchor-row", "environment"}


def _kinds_of_the_example() -> list[str]:
    from specdev_tools.graph.build import build_graph

    graph = build_graph(str(EXAMPLE_HOST / "spec"), str(ROOT))
    return sorted({node.kind for node in graph.by_id.values()})


def _new_id_for(node_id: str) -> str:
    """An id in the same spelling as *node_id* that no node has: lower-case kebab gets a suffix, upper-case a suffix too."""
    if re.fullmatch(r"[A-Z0-9_]+", node_id):
        return f"{node_id}_RENAMED"
    return f"{node_id}-renamed"


@pytest.mark.parametrize("kind", _kinds_of_the_example())
def test_one_node_of_every_kind_renames_to_an_id_valid_for_its_kind(host: Example, kind: str) -> None:
    from specdev_tools.graph.build import build_graph

    graph = build_graph(str(host.spec), str(ROOT))
    old = next(node.id for node in graph.by_id.values() if node.kind == kind)
    status, out = _rename(host, old, _new_id_for(old), "--dry-run")
    if kind in _REFUSED_KINDS:
        assert status == 1 and out.startswith("E770"), (kind, out)
    else:
        assert status == 0, (kind, old, out)


def test_label_rename_does_not_rewrite_a_closed_milestone_and_lists_what_it_skipped(host: Example) -> None:
    host.close_milestone()
    path = host.spec / "14_roadmap.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    criterion = document["milestones"][0]["tasks"][0]["acceptance_criteria"][0]
    assert criterion["criterion_id"] == "tc-confirm-expired-token"
    criterion["text"] = f"A {OLD_LABEL} issued 31 minutes earlier is refused."
    path.write_text(json.dumps(document, indent=4) + "\n", encoding="utf-8")
    code, out = _rename(host, "--label", TERM, NEW_LABEL, "--dry-run")
    assert code == 0 and "not rewritten (closed milestone) (2):" in out and "    tc-confirm-expired-token .text" in out and "    task-implement-password-reset-confirm .description" in out, out
    result = json.loads(_rename_json(host, "--label", TERM, NEW_LABEL, "--dry-run"))
    assert {(item["node_id"], item["field_path"]) for item in result["skipped"]} == {
        ("tc-confirm-expired-token", ".text"), ("task-implement-password-reset-confirm", ".description")
    }
    assert not {"tc-confirm-expired-token", "task-implement-password-reset-confirm"} & {use["node_id"] for use in result["uses"]}
    assert _rename(host, "--label", TERM, NEW_LABEL)[0] == 0
    assert json.loads(path.read_text(encoding="utf-8"))["milestones"][0]["tasks"][0]["acceptance_criteria"][0]["text"] == criterion["text"]


def test_label_rename_and_e741_share_one_user_set(host: Example) -> None:
    """The nodes the rename rewrites are users of ``label_users`` and the matcher of E741 finds the new label in exactly them."""
    graph = host.graph()
    reading = {node.id for node in label_users(graph)}
    dry = rename_label(str(host.spec), str(ROOT), TERM, NEW_LABEL, graph=graph)
    assert [use.node_id for use in dry.uses] == LABEL_USERS and set(LABEL_USERS) <= reading
    assert all(use.field_path in dict(own_leaves(graph, graph.by_id[use.node_id])) for use in dry.uses)
    assert [e for e in check_term_use(GraphCheckContext.from_graph(graph, None, str(ROOT)), "merge") if e.node_id == TERM] == []
    assert rename_label(str(host.spec), str(ROOT), TERM, NEW_LABEL, apply=True).written
    after = host.graph()
    holders = {
        node.id for node in label_users(after)
        if any(label_matches(NEW_LABEL, text) for _path, text in own_leaves(after, node))
    }
    assert holders == set(LABEL_USERS)
    assert [e for e in check_term_use(GraphCheckContext.from_graph(after, None, str(ROOT)), "merge") if e.node_id == TERM] == []
