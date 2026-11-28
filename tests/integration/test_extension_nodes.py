"""The items of an extension data file as nodes of the spec graph, end to end (DEVSPEC-245, piece B).

The worked example is copied as a git repository with the database extension of ``tests/fixtures/extension_example``:
its two files, its manifest entry and the task criterion that refines its table, every link accepted and all of it
committed.  The commands run in this process with the three root flags, from another folder than the host.

That the whole check says what the plain example says, and that step 13 is not blocked, is in
``test_extension_schema_validates.py`` (the tests of piece A, on the same host).
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import apply_delta, attest, commit_all, run_split, start_branch, step_gate_host
from specdev_tools.context.canon_extractor import extract_canon
from specdev_tools.context.reviewer import review_artifact
from specdev_tools.context.structure import get_step_structure
from specdev_tools.core.ambiguity_items import read_ambiguity_items
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.gitview import GitViewError
from specdev_tools.release.tag_state import tag_state
from specdev_tools.trace.history import NOTE_NO_EARLIER
from specdev_tools.trace.lockfile import read_lock
from specdev_tools.validation.open_items import check_open_items
from unit.graph._extension import (
    CRITERION, DATA_PLACE, DATASTORE, DECLARE, DELTAS, ENTRY, EXTENSION, FIXTURE, MANIFEST, PARKED_TABLE, REFINE, ROADMAP, SCHEMA_PLACE, STEP_13, TABLE,
    criterion, table,
)
from unit.graph._synth import git
from unit.trace._lock_support import ROOT

FR = "fr-password-reset"
"""The functional requirement both tables derive from and the manifest entry is justified by."""
OTHER_FIXTURE = "fix-password-reset-expired-token"


def _host(destination: Path, *, committed: bool = True) -> Path:
    host = step_gate_host(destination, attested=False)
    shutil.copytree(EXTENSION / "spec" / "extensions", host / "spec" / "extensions")
    for delta in (DECLARE, REFINE):
        apply_delta(host, delta, folder=DELTAS)
    attest(host)
    if committed:
        commit_all(host, "the extension")
    return host


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(exist_ok=True)
    monkeypatch.chdir(elsewhere)  # a path relative to the spec folder finds nothing from here
    return _host(tmp_path / "host")


def _flags(host: Path) -> list[str]:
    return ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]


def _run(capsys: pytest.CaptureFixture[str], host: Path, *argv: str) -> tuple[int, str, str]:
    return run_split(capsys, *argv, *_flags(host))


def _read(host: Path, place: str) -> dict[str, Any]:
    return json.loads((host / "spec" / place).read_text(encoding="utf-8"))


def _text(host: Path, place: str) -> str:
    return (host / "spec" / place).read_text(encoding="utf-8")


def _findings(capsys: pytest.CaptureFixture[str], host: Path, *flags: str) -> list[dict[str, Any]]:
    _code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--json", *flags)
    return json.loads(out)["errors"]


def _about(findings: list[dict[str, Any]], *node_ids: str) -> list[tuple[str, str | None, str | None]]:
    """``(code, node, link)`` of the findings about *node_ids*; the link is ``field->target`` when the text names a link of the node (the JSON carries no target)."""
    return sorted((finding["code"], finding.get("node_id"), _link_named(finding)) for finding in findings if finding.get("node_id") in node_ids)


LINK_IN_TEXT = re.compile(r"field (\w+), target '([^']+)'")


def _link_named(finding: dict[str, Any]) -> str | None:
    found = LINK_IN_TEXT.search(finding["message"])
    return f"{found[1]}->{found[2]}" if found else None


def _entries(host: Path, holder: str) -> list[tuple[str, str]]:
    return sorted((entry.field, entry.target) for entry in read_lock(str(host / "spec")).entries if entry.source == holder)


# --- the nodes are read ------------------------------------------------------------------------------------------------


def test_node_show_reads_a_table_of_the_extension(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    code, out, err = _run(capsys, host, "node", "show", TABLE, "--json")
    assert code == 0, err
    shown = json.loads(out)
    node = shown["nodes"][0] if isinstance(shown, dict) and "nodes" in shown else (shown[0] if isinstance(shown, list) else shown)
    text = json.dumps(node)
    assert node["id"] == TABLE and node["kind"] == "table" and node["step"] == "13"
    assert DATA_PLACE in text and "reset_token" in text  # where it is defined and what it says
    for linked in (FR, DATASTORE, FIXTURE):  # its links out
        assert linked in text, linked
    assert {"verb": "refines", "kind": "task-criterion", "count": 1} in node["incoming"]  # and the criterion that refines it
    code, out, _err = _run(capsys, host, "node", "show", ENTRY, DATASTORE, "--json")
    assert code == 0 and '"extension"' in out and '"datastore"' in out


def test_the_committed_host_has_no_finding_about_a_node_of_the_extension(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    assert _about(_findings(capsys, host), TABLE, PARKED_TABLE, DATASTORE, ENTRY, CRITERION) == []
    code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--step", "13", "--json")
    gate = json.loads(out)["step_gate"]
    assert (code, gate["result"], gate["blocking"]) == (0, "clear", [])


# --- an edit upstream makes the links of the extension suspect, and attest clears them -----------------------------------


def test_an_edit_of_the_fr_makes_the_links_of_the_table_and_of_the_entry_suspect_and_attest_clears_them(
    capsys: pytest.CaptureFixture[str], host: Path,
) -> None:
    def reword(document: dict[str, Any]) -> None:
        requirement = next(found for found in document["functional_requirements"] if found["fr_id"] == FR)
        requirement["statement"] = requirement["statement"] + " The link is sent once."

    path = host / "spec" / "04_fr_list.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    reword(document)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    suspect = _about(_findings(capsys, host), TABLE, PARKED_TABLE, ENTRY)
    assert ("E763", TABLE, f"derives_from->{FR}") in suspect and ("E763", ENTRY, f"justified_by->{FR}") in suspect
    assert ("E763", PARKED_TABLE, f"derives_from->{FR}") in suspect  # a parked node's link is a link too
    assert {code for code, _node, _target in suspect} == {"E763"}
    code, out, err = _run(capsys, host, "stale", "--json")
    assert TABLE in out and ENTRY in out, err
    code, _out, err = _run(capsys, host, "attest", TABLE, "--yes")
    assert code == 1 and "E764" in err and FIXTURE in err, err  # top down: the fixture the table names is read again first
    graph = build_graph(str(host / "spec"), str(ROOT))
    holders = {finding["node_id"] for finding in _findings(capsys, host) if finding["code"] == "E763"}
    for node_id in sorted(holders, key=lambda name: graph.shape.order_key(graph.by_id[name])):
        code, _out, err = _run(capsys, host, "attest", node_id, "--yes")
        assert code == 0, (node_id, err)
    assert {TABLE, PARKED_TABLE, ENTRY, FIXTURE} <= holders
    assert [finding for finding in _findings(capsys, host) if finding["code"] == "E763"] == []


# --- written by node id ------------------------------------------------------------------------------------------------


def test_patch_by_id_writes_the_extension_file(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    before = _read(host, DATA_PLACE)
    code, out, err = _run(capsys, host, "json", "patch", "--id", TABLE, ".name", '"reset_tokens"')
    assert code == 0, out + err
    after = _read(host, DATA_PLACE)
    assert table(after)["name"] == "reset_tokens"
    table(after)["name"] = table(before)["name"]
    assert after == before  # and nothing else of the file
    # the table says something else now: the link that refines it is to be read again, and its own links stay accepted
    found = _about(_findings(capsys, host), TABLE, CRITERION)
    assert found == [("E763", CRITERION, f"refines->{TABLE}")]


def test_a_patch_by_id_that_breaks_the_schema_of_the_extension_is_refused_and_writes_nothing(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    before, lock_before = _text(host, DATA_PLACE), _text(host, "extras/trace.lock.json")
    code, out, err = _run(capsys, host, "json", "patch", "--id", TABLE, ".columns", '"x"')
    assert code == 1 and "E767" in out + err, out + err
    assert "columns" in out + err and "array" in out + err  # the violation is the extension schema's own
    assert (_text(host, DATA_PLACE), _text(host, "extras/trace.lock.json")) == (before, lock_before)
    code, out, err = _run(capsys, host, "json", "patch", "--id", TABLE, ".scope", '"sometime"')  # an enum of a toolkit core schema the extension refers to
    assert code == 1 and (_text(host, DATA_PLACE), _text(host, "extras/trace.lock.json")) == (before, lock_before), out + err


def test_insert_by_id_creates_a_declared_array_and_the_lock_entry_of_the_new_link(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    assert "verified_by" not in table(_read(host, DATA_PLACE), PARKED_TABLE)
    assert ("verified_by", OTHER_FIXTURE) not in _entries(host, PARKED_TABLE)
    code, out, err = _run(capsys, host, "json", "insert", "--id", PARKED_TABLE, ".verified_by", f'"{OTHER_FIXTURE}"')
    assert code == 0, out + err
    assert table(_read(host, DATA_PLACE), PARKED_TABLE)["verified_by"] == [OTHER_FIXTURE]
    assert ("verified_by", OTHER_FIXTURE) in _entries(host, PARKED_TABLE)
    assert _about(_findings(capsys, host), PARKED_TABLE) == []  # no E761: the write accepted the link it made


def test_insert_by_id_into_a_field_the_schema_does_not_declare_is_refused(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    before = _text(host, DATA_PLACE)
    code, out, err = _run(capsys, host, "json", "insert", "--id", PARKED_TABLE, ".indexes", '"ix-member"')
    assert code == 1 and "indexes" in out + err and _text(host, DATA_PLACE) == before, out + err


def test_a_link_by_id_to_a_node_of_a_kind_the_field_does_not_take_is_refused(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    before = _text(host, DATA_PLACE)
    code, out, err = _run(capsys, host, "json", "insert", "--id", TABLE, ".verified_by", '"inv-reset-token-single-use"')
    assert code == 1 and "E701" in out + err, out + err
    assert _text(host, DATA_PLACE) == before


def test_delete_by_id_removes_the_node_and_the_lock_entries_of_its_links(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    assert _entries(host, PARKED_TABLE) != []
    code, out, err = _run(capsys, host, "json", "delete", "--id", PARKED_TABLE)
    assert code == 0, out + err
    assert [item["table_id"] for item in _read(host, DATA_PLACE)["tables"]] == [TABLE]
    assert _entries(host, PARKED_TABLE) == []
    assert [finding for finding in _findings(capsys, host) if PARKED_TABLE in finding["message"]] == []  # no orphan entry (E762) is left


def test_a_delete_by_id_of_a_node_something_refines_names_the_criterion_it_breaks(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    """As for any node: a delete is written and says which holders now name no node (first written as a refusal: see the report)."""
    code, out, err = _run(capsys, host, "json", "delete", "--id", TABLE)
    assert code == 0 and CRITERION in out + err, out + err
    assert [item["table_id"] for item in _read(host, DATA_PLACE)["tables"]] == [PARKED_TABLE]
    assert _about(_findings(capsys, host), CRITERION) == [("E700", CRITERION, f"refines->{TABLE}")]


def test_rename_rewrites_the_extension_file_and_the_criterion_that_refines_the_table(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    before = _about(_findings(capsys, host), TABLE, CRITERION)
    code, out, err = _run(capsys, host, "node", "rename", TABLE, "tbl-reset-tokens")
    assert code == 0, out + err
    renamed = table(_read(host, DATA_PLACE), "tbl-reset-tokens")
    assert renamed["aliases"] == [TABLE] and renamed["name"] == "reset_token"
    assert criterion(_read(host, ROADMAP))["refines"] == ["tbl-reset-tokens"]
    assert ("refines", "tbl-reset-tokens") in _entries(host, CRITERION) and _entries(host, TABLE) == []
    assert sorted(_entries(host, "tbl-reset-tokens")) == [("derives_from", FR), ("part_of", DATASTORE), ("verified_by", FIXTURE)]
    assert _about(_findings(capsys, host), TABLE, "tbl-reset-tokens", CRITERION) == before == []


# --- the context commands know the extension schemas of the spec folder --------------------------------------------------


def test_the_review_compares_a_data_file_of_the_extension_with_its_own_schema(host: Path) -> None:
    spec = host / "spec"

    def missing(place: str) -> list[str]:
        result = review_artifact(str(spec / place), "13", str(spec), str(ROOT), git_root=str(host))
        return [pair.description for pair in result.semantic_pairs if pair.check_type == "scope_completeness"]

    assert missing(DATA_PLACE) == []  # not the manifest's extension_decision and extensions
    required = json.loads((spec / SCHEMA_PLACE).read_text(encoding="utf-8"))["required"]
    document = _read(host, DATA_PLACE)
    dropped = next(name for name in required if name in document and name not in ("id", "owner", "created_at", "$schema", "canonical_refs_used"))
    document.pop(dropped)
    (spec / DATA_PLACE).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    [description] = missing(DATA_PLACE)
    assert f"'{dropped}'" in description
    assert missing(MANIFEST) == []
    manifest = _read(host, MANIFEST)
    manifest.pop("extension_decision")
    (spec / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    assert [text for text in missing(MANIFEST) if "'extension_decision'" in text] != []  # the manifest is still compared with the step's schema


def test_no_change_guard_the_structure_and_the_canon_of_a_step_are_those_of_the_plain_example(tmp_path: Path, host: Path) -> None:
    """A guard, not the test of a fix: these two readers find the schema of a step by the needle ``vc:<NN>-`` and an extension ``$id`` is ``vc:ext-NN-<topic>``, so no extension schema can be taken for the schema of a step, and neither reader is handed the spec folder's schemas."""
    plain = step_gate_host(tmp_path / "plain")
    for step in ("13", "14"):
        with_extension = get_step_structure(step, str(host / "spec"), str(ROOT))
        without = get_step_structure(step, str(plain / "spec"), str(ROOT))
        assert with_extension["output_schema_keys"] == without["output_schema_keys"] != []
        assert extract_canon(step, str(ROOT), str(host / "spec")) == extract_canon(step, str(ROOT), str(plain / "spec"))


# --- step create 13 <extension-id>: the data file of a declared extension ------------------------------------------------

DATA_FILE = EXTENSION / "spec" / DATA_PLACE
LOCK = "extras/trace.lock.json"


@pytest.fixture
def declared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The example with the entry and the schema of the extension, and no data file yet (so no criterion refines its table)."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(exist_ok=True)
    monkeypatch.chdir(elsewhere)
    host = step_gate_host(tmp_path / "declared", attested=False)
    (host / "spec" / "extensions").mkdir()
    shutil.copy(EXTENSION / "spec" / SCHEMA_PLACE, host / "spec" / SCHEMA_PLACE)
    apply_delta(host, DECLARE, folder=DELTAS)
    attest(host)
    commit_all(host, "the extension is declared")
    return host


def _draft(folder: Path, change: Any = None, name: str = "draft.json") -> str:
    document = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if change is not None:
        change(document)
    path = folder / name
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _create(capsys: pytest.CaptureFixture[str], host: Path, *words: str) -> tuple[int, str]:
    code, out, err = _run(capsys, host, "step", "create", *words)
    return code, out + err


def _nothing_written(host: Path, lock_before: str) -> bool:
    return not (host / "spec" / DATA_PLACE).exists() and _text(host, LOCK) == lock_before


def test_step_create_13_writes_the_data_file_of_a_declared_extension_and_accepts_its_links(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, declared: Path,
) -> None:
    code, said = _create(capsys, declared, "13", ENTRY, "--from", _draft(tmp_path))
    assert code == 0, said
    assert DATA_PLACE in said
    assert _read(declared, DATA_PLACE) == json.loads(DATA_FILE.read_text(encoding="utf-8"))
    assert _entries(declared, TABLE) == [("derives_from", FR), ("part_of", DATASTORE), ("verified_by", FIXTURE)]
    assert _entries(declared, PARKED_TABLE) == [("derives_from", FR), ("part_of", DATASTORE)]
    # the links are accepted (no E761); the table is an obligation nothing refines yet, which is the one thing said of the new nodes
    assert _about(_findings(capsys, declared), TABLE, PARKED_TABLE, DATASTORE, ENTRY) == [("E740", TABLE, None)]


def test_step_create_13_dry_run_reports_and_writes_nothing(capsys: pytest.CaptureFixture[str], tmp_path: Path, declared: Path) -> None:
    lock_before = _text(declared, LOCK)
    code, said = _create(capsys, declared, "13", ENTRY, "--from", _draft(tmp_path), "--dry-run")
    assert code == 0 and DATA_PLACE in said, said
    assert _nothing_written(declared, lock_before)


def test_step_create_13_for_an_extension_the_manifest_does_not_declare_is_refused(capsys: pytest.CaptureFixture[str], tmp_path: Path, declared: Path) -> None:
    lock_before = _text(declared, LOCK)
    code, said = _create(capsys, declared, "13", "ext-02-cache", "--from", _draft(tmp_path))
    assert code == 1 and "E767" in said and "ext-02-cache" in said and MANIFEST in said, said
    assert ENTRY in said  # the entries there are
    assert not (declared / "spec" / "extensions" / "ext_02_cache.json").exists() and _nothing_written(declared, lock_before)


def test_step_create_13_for_an_entry_with_no_schema_file_is_refused(capsys: pytest.CaptureFixture[str], tmp_path: Path, declared: Path) -> None:
    (declared / "spec" / SCHEMA_PLACE).unlink()
    lock_before = _text(declared, LOCK)
    code, said = _create(capsys, declared, "13", ENTRY, "--from", _draft(tmp_path))
    assert code == 1 and "E767" in said and SCHEMA_PLACE in said, said
    assert _nothing_written(declared, lock_before)


def test_step_create_13_for_an_extension_that_has_its_data_file_is_refused(capsys: pytest.CaptureFixture[str], tmp_path: Path, host: Path) -> None:
    before = _text(host, DATA_PLACE)
    code, said = _create(capsys, host, "13", ENTRY, "--from", _draft(tmp_path, lambda document: document.update(owner="ops")))
    assert code == 1 and "E767" in said and DATA_PLACE in said and "--id" in said, said
    assert _text(host, DATA_PLACE) == before


@pytest.mark.parametrize("case", ["breaks the schema", "names another schema", "a link to no node", "a link to a wrong kind"])
def test_step_create_13_refuses_a_draft_that(capsys: pytest.CaptureFixture[str], tmp_path: Path, declared: Path, case: str) -> None:
    changes = {
        "breaks the schema": (lambda document: document["tables"][0].update(columns="x"), ["columns"]),
        "names another schema": (lambda document: document.update({"$schema": "vc:13-extension-manifest"}), ["vc:ext-01-database"]),
        "a link to no node": (lambda document: document["tables"][0].update(derives_from=["fr-never-written"]), ["fr-never-written"]),
        "a link to a wrong kind": (lambda document: document["tables"][0].update(verified_by=["inv-reset-token-single-use"]), ["E701"]),
    }
    change, words = changes[case]
    lock_before = _text(declared, LOCK)
    code, said = _create(capsys, declared, "13", ENTRY, "--from", _draft(tmp_path, change))
    assert code == 1 and all(word in said for word in words), said
    assert _nothing_written(declared, lock_before)


def test_step_create_13_mints_the_id_a_draft_leaves_out(capsys: pytest.CaptureFixture[str], tmp_path: Path, declared: Path) -> None:
    code, said = _create(capsys, declared, "13", ENTRY, "--from", _draft(tmp_path, lambda document: document["tables"][1].pop("table_id")))
    assert code == 0, said
    first, second = _read(declared, DATA_PLACE)["tables"]
    assert first["table_id"] == TABLE and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", second["table_id"]) and second["table_id"] != TABLE
    assert second["table_id"] in said


def test_step_create_13_with_no_extension_id_is_the_manifest_as_before(capsys: pytest.CaptureFixture[str], tmp_path: Path, declared: Path, host: Path) -> None:
    manifest_draft = tmp_path / "manifest.json"
    shutil.copy(host / "spec" / MANIFEST, manifest_draft)
    for folder in (declared, host):  # the manifest is there: refused, and the files of the extensions folder are not what is in the way
        code, said = _create(capsys, folder, "13", "--from", str(manifest_draft))
        assert code == 1 and "E767" in said and MANIFEST in said and DATA_PLACE not in said, said
    (host / "spec" / MANIFEST).unlink()  # an extensions folder with its two files and no manifest: the manifest can be created
    code, said = _create(capsys, host, "13", "--from", str(manifest_draft))
    assert code == 0 and (host / "spec" / MANIFEST).exists(), said


def test_a_second_word_after_another_step_is_refused_as_before(capsys: pytest.CaptureFixture[str], tmp_path: Path, declared: Path) -> None:
    code, said = _create(capsys, declared, "04", ENTRY, "--from", _draft(tmp_path))
    assert code == 1 and "E767" in said and "takes no batch" in said, said


# --- the manifest stays the file of step 13 ------------------------------------------------------------------------------


def test_json_insert_step_13_adds_an_entry_to_the_manifest_of_a_spec_with_an_extension_file(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    entry = {**_read(host, MANIFEST)["extensions"][0], "extension_id": "ext-02-cache", "title": "Cache Extension", "justified_by": [FR]}
    data_before = _text(host, DATA_PLACE)
    code, out, err = _run(capsys, host, "json", "insert", "--step", "13", ".extensions", json.dumps(entry))
    assert code == 0, out + err
    assert [item["extension_id"] for item in _read(host, MANIFEST)["extensions"]] == [ENTRY, "ext-02-cache"]
    assert _entries(host, "ext-02-cache") == [("justified_by", FR)] and _text(host, DATA_PLACE) == data_before


def test_json_insert_step_13_takes_no_collection_of_an_extension_file(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    before = _text(host, DATA_PLACE), _text(host, MANIFEST)
    new_table = {**table(_read(host, DATA_PLACE), PARKED_TABLE), "table_id": "tbl-audit"}
    code, out, err = _run(capsys, host, "json", "insert", "--step", "13", ".tables", json.dumps(new_table))
    assert code == 1 and "E767" in out + err and ".extensions" in out + err, out + err  # the collections of the step's file, the manifest
    assert (_text(host, DATA_PLACE), _text(host, MANIFEST)) == before


# --- the ambiguities of an extension data file are read like a step file's (decision 8) ----------------------------------

OPEN_ITEM = {"id": "amb-reset-token-retention", "description": "How long is a used row of reset_token kept?", "about": [FR]}
AMBIGUITY_LIST = {"$ref": "vc:core:collections#ambiguityList"}


def _write_json(path: Path, document: Any) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _ask(host: Path, *items: dict[str, Any]) -> None:
    """Let the schema of the extension take an ``ambiguities`` list, put *items* in the data file and accept the links."""
    schema = _read(host, SCHEMA_PLACE)
    schema["properties"]["ambiguities"] = AMBIGUITY_LIST
    _write_json(host / "spec" / SCHEMA_PLACE, schema)
    data = _read(host, DATA_PLACE)
    data["ambiguities"] = list(items)
    _write_json(host / "spec" / DATA_PLACE, data)
    attest(host)


def _open(host: Path, gate: str) -> list[tuple[str, str | None, str | None]]:
    return [(error.code, error.owner, error.file) for error in check_open_items(str(host / "spec"), gate=gate)]


def test_an_open_item_of_an_extension_data_file_is_counted_by_the_open_item_checks(host: Path) -> None:
    before = {gate: _open(host, gate) for gate in ("step", "merge")}
    _ask(host)  # the list is there and empty: nothing is open
    assert {gate: _open(host, gate) for gate in ("step", "merge")} == before
    _ask(host, OPEN_ITEM)
    assert _open(host, "merge") == [*before["merge"], ("E631", "merge-check", DATA_PLACE)]
    assert _open(host, "step") == [*before["step"], ("W630", STEP_13, DATA_PLACE)]
    [finding] = [error for error in check_open_items(str(host / "spec"), gate="merge") if error.file == DATA_PLACE]
    assert OPEN_ITEM["id"] in finding.message


def test_the_merge_gate_and_the_step_gate_say_it(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    _ask(host, OPEN_ITEM)
    manifest = _read(host, MANIFEST)
    manifest["ambiguities"] = [{"id": "amb-manifest", "description": "One extension or two?", "about": [FR]}]  # the same question in the step's own file
    _write_json(host / "spec" / MANIFEST, manifest)
    attest(host)
    commit_all(host, "an open question in the extension file and one in the manifest")
    merged = _findings(capsys, host, "--merge", "--base-ref", "HEAD~1")

    def said_of(item_id: str) -> list[tuple[str, str | None]]:
        return sorted((finding["code"], finding.get("owner")) for finding in merged if item_id in finding["message"])

    assert ("E631", "merge-check") in said_of(OPEN_ITEM["id"])
    assert said_of(OPEN_ITEM["id"]) == said_of("amb-manifest")  # read like a step file's: what the gate says of one it says of the other
    _code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--step", "13", "--json", "--detail", "all")
    own = [finding for finding in json.loads(out)["step_gate"]["own_warnings"] if OPEN_ITEM["id"] in finding["message"]]
    assert [(finding["code"], finding.get("owner")) for finding in own] == [("W630", STEP_13)]


def test_upstream_backlog_lists_the_item_as_an_item_of_step_13(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    _ask(host, OPEN_ITEM)
    code, out, err = run_split(capsys, "upstream-backlog", str(host / "spec"), "--repo-root", str(ROOT), "--json")
    assert code == 0, err
    records = [record for record in _records(json.loads(out)) if record.get("item_id") == OPEN_ITEM["id"]]
    assert [(record["step"], record["artifact"], record["group"]) for record in records] == [("13", DATA_PLACE, "04")]  # it lives in step 13 and is about a node of step 04
    code, text, _err = run_split(capsys, "upstream-backlog", str(host / "spec"), "--repo-root", str(ROOT))
    assert OPEN_ITEM["id"] in text and DATA_PLACE in text


def _records(report: Any) -> list[dict[str, Any]]:
    """Every object of the report that describes one item (it has an ``item_id``), wherever the report keeps them."""
    found: list[dict[str, Any]] = []
    if isinstance(report, dict):
        if "item_id" in report:
            found.append(report)
        for value in report.values():
            found.extend(_records(value))
    elif isinstance(report, list):
        for value in report:
            found.extend(_records(value))
    return found


def test_the_items_are_read_at_the_place_of_step_13_and_only_from_the_files_of_the_folder(host: Path) -> None:
    spec = host / "spec"
    _ask(host, OPEN_ITEM)
    roadmap = _read(host, ROADMAP)
    roadmap["ambiguities"] = [{"id": "amb-roadmap", "description": "Which milestone first?", "about": [FR]}]
    _write_json(spec / ROADMAP, roadmap)
    manifest = _read(host, MANIFEST)
    manifest["ambiguities"] = [{"id": "amb-manifest", "description": "One extension or two?", "about": [FR]}]
    _write_json(spec / MANIFEST, manifest)
    (spec / "extensions" / "deeper").mkdir()
    _write_json(spec / "extensions" / "deeper" / "ext_09_notes.json", {"ambiguities": [{"id": "amb-deeper", "description": "Not a file of the folder.", "about": [FR]}]})
    _write_json(spec / "extensions" / "04_notes.json", {"ambiguities": [{"id": "amb-notes", "description": "A file of the folder, whatever its name.", "about": [FR]}]})
    schema = _read(host, SCHEMA_PLACE)
    schema["ambiguities"] = [{"id": "amb-schema", "description": "A schema file is no data file.", "about": [FR]}]
    _write_json(spec / SCHEMA_PLACE, schema)
    read = read_ambiguity_items(str(spec))
    assert read.error is None
    ours = [(item.id, item.step, item.location) for item in read.items if item.id.startswith("amb-") and item.id != "amb-reset-seed"]
    named = [name for name, _step, _location in ours]
    assert named.index("amb-manifest") < named.index("amb-notes") < named.index(OPEN_ITEM["id"]) < named.index("amb-roadmap")  # step 13: the manifest, then the folder by name
    assert ("amb-notes", "13", ".ambiguities") in ours and (OPEN_ITEM["id"], "13", ".ambiguities") in ours
    assert "amb-deeper" not in named and "amb-schema" not in named


def _schema_errors(capsys: pytest.CaptureFixture[str], host: Path, place: str) -> list[dict[str, Any]]:
    """The E520 findings of step 13 that the merge gate has about the file *place*."""
    findings = _findings(capsys, host, "--merge", "--base-ref", "HEAD")
    return [finding for finding in findings if finding["code"] == "E520" and finding.get("owner") == STEP_13 and finding.get("file") == place]


def test_an_extension_data_file_that_cannot_be_read_stops_no_reader_of_items_and_the_gate_reports_the_file(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    """A file of the folder is the host's, judged by its own schema (piece A): the reader of items takes what it can read.

    First written as "an E520 of the reader, like a step file's"; that reader stopped the 1.1.1 migration of a host whose
    extension data file is no JSON (E881 from ``p1_capture``), and the gate reports such a file without it.
    """
    _ask(host, OPEN_ITEM)
    commit_all(host, "an open question in the extension file")
    before = _open(host, "merge")
    (host / "spec" / "extensions" / "04_notes.json").write_text("{ not json", encoding="utf-8")  # read before ext_01_database.json
    read = read_ambiguity_items(str(host / "spec"))
    assert read.error is None and OPEN_ITEM["id"] in [item.id for item in read.items]
    assert _open(host, "merge") == before and ("E631", "merge-check", DATA_PLACE) in before
    code, out, err = run_split(capsys, "upstream-backlog", str(host / "spec"), "--repo-root", str(ROOT))
    assert code == 0 and OPEN_ITEM["id"] in out, err
    assert _schema_errors(capsys, host, "extensions/04_notes.json") != []  # not silent: the check of the file says it cannot be read


# --- the context packs (decision 7) -------------------------------------------------------------------------------------------

PLAN_ITEM = "PWRESET_CONFIRM_EXPIRED_01"  # the start of tests/fixtures/graph/pack_16b_expected.json


def _pack_start(host: Path, role: str) -> str:
    """The task that holds the criterion which refines the table (16a) or its milestone (16c), read from the roadmap."""
    for milestone in _read(host, ROADMAP)["milestones"]:
        for task in milestone["tasks"]:
            if any(found["criterion_id"] == CRITERION for found in task["acceptance_criteria"]):
                return task["task_id"] if role == "16a" else milestone["milestone_id"]
    raise AssertionError(f"no task of the roadmap holds {CRITERION}")


def _pack(capsys: pytest.CaptureFixture[str], host: Path, role: str, start: str, *more: str) -> dict[str, Any]:
    code, out, err = _run(capsys, host, "trace", start, "--recipe", role, "--json", *more)
    assert code == 0, err
    return json.loads(out)


def _ids_of(pack: dict[str, Any]) -> dict[str, list[str]]:
    return {name: [row["id"] for row in rows] for name, rows in pack["sections"].items()}


@pytest.mark.parametrize("role", ["16a", "16c"])
def test_trace_with_the_recipe_of_a_planner_or_a_reviewer_shows_the_table_and_the_datastore(capsys: pytest.CaptureFixture[str], host: Path, tmp_path: Path, role: str) -> None:
    start = _pack_start(host, role)
    sections = _ids_of(_pack(capsys, host, role, start))
    plain = _ids_of(_pack(capsys, step_gate_host(tmp_path / "plain"), role, start))
    assert TABLE in sections["obligations"] and TABLE not in plain["obligations"]
    [added] = [name for name in sections if name not in plain]
    assert sections[added] == [DATASTORE]
    code, text, err = _run(capsys, host, "trace", start, "--recipe", role)
    assert code == 0, err
    assert TABLE in text and DATASTORE in text and added in text


def test_trace_with_the_recipe_of_the_implementer_holds_no_host_node_for_an_item_that_realises_another_criterion(capsys: pytest.CaptureFixture[str], host: Path, tmp_path: Path) -> None:
    """The lead's ruling after the pack: 16b shows the kinds of a host too; the item of the golden realises another criterion."""
    plain = step_gate_host(tmp_path / "plain")
    golden = json.loads((ROOT / "tests" / "fixtures" / "graph" / "pack_16b_expected.json").read_text(encoding="utf-8"))
    assert golden["start"] == PLAN_ITEM
    with_extension, without = (_pack(capsys, folder, "16b", PLAN_ITEM)["sections"] for folder in (host, plain))
    assert list(without) == list(golden["sections"])
    [added] = [name for name in with_extension if name not in without]
    assert with_extension[added] == [] and {name: rows for name, rows in with_extension.items() if name != added} == without
    said = [_run(capsys, folder, "trace", PLAN_ITEM, "--recipe", "16b", "--since", "HEAD")[1].splitlines() for folder in (host, plain)]
    assert [line for line in said[0] if not line.startswith(added)] == said[1] and said[1] != []
    assert not any(node in line for line in said[0] for node in (TABLE, DATASTORE))


def test_trace_with_the_recipe_of_the_implementer_shows_the_table_to_the_item_that_builds_it(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    plan = "impl_context/ms_account_recovery_plan.json"
    document = _read(host, plan)
    checklist = document["plan"]["spec_alignment"]["checklist"]
    checklist.append({**json.loads(json.dumps(checklist[0])), "id": "RESET_TOKEN_TABLE_01", "realises": [CRITERION], "description": "A migration creates the table reset_token."})
    _write_json(host / "spec" / plan, document)
    sections = _ids_of(_pack(capsys, host, "16b", "RESET_TOKEN_TABLE_01"))
    assert TABLE in sections["obligations"] and FIXTURE in sections["verifiers"]
    [holding] = [name for name, ids in sections.items() if DATASTORE in ids]
    assert sections[holding] == [DATASTORE] and holding not in ("obligations", "verifiers")
    code, text, err = _run(capsys, host, "trace", "RESET_TOKEN_TABLE_01", "--recipe", "16b", "--since", "HEAD")
    assert code == 0, err
    assert TABLE in text and DATASTORE in text and FIXTURE in text


# --- the ambiguities of an extension data file: the edges (decision 8) ------------------------------------------------------


def test_a_spec_folder_that_holds_only_an_extension_data_file_has_its_items(tmp_path: Path) -> None:
    """No root file of a later step follows the folder, and no schema is there: the items are read all the same."""
    spec = tmp_path / "spec"
    (spec / "extensions").mkdir(parents=True)
    _write_json(spec / "extensions" / "ext_01_database.json", {"ambiguities": [OPEN_ITEM]})
    read = read_ambiguity_items(str(spec))
    assert read.error is None and [(item.id, item.step, item.location) for item in read.items] == [(OPEN_ITEM["id"], "13", ".ambiguities")]
    assert [Path(item.artifact_path) for item in read.items] == [spec / "extensions" / "ext_01_database.json"]
    assert [(error.code, error.owner) for error in check_open_items(str(spec), gate="merge")] == [("E631", "merge-check")]


def test_a_spec_folder_with_no_extensions_folder_or_an_empty_one_has_no_item_more(tmp_path: Path) -> None:
    plain = step_gate_host(tmp_path / "plain")
    before = [(item.id, item.step, item.artifact_path) for item in read_ambiguity_items(str(plain / "spec")).items]
    (plain / "spec" / "extensions").mkdir()
    assert [(item.id, item.step, item.artifact_path) for item in read_ambiguity_items(str(plain / "spec")).items] == before
    _write_json(plain / "spec" / "extensions" / "ext_01_database.json", {"tables": []})  # a data file that asks nothing
    assert [(item.id, item.step, item.artifact_path) for item in read_ambiguity_items(str(plain / "spec")).items] == before


@pytest.mark.parametrize(
    "malformed, read",
    [("none yet", []), ({"amb-one": {}}, []), ([OPEN_ITEM, "amb-two"], [OPEN_ITEM["id"]])],
    ids=["a-text", "an-object", "an-entry-that-is-no-object"],
)
def test_a_malformed_list_is_reported_by_the_schema_of_the_file_and_the_reader_takes_the_items_it_can(
    capsys: pytest.CaptureFixture[str], host: Path, malformed: Any, read: list[str],
) -> None:
    """First written as "reported as the manifest's would be" (an E520 of the reader); see the test of the unreadable file."""
    _ask(host)  # the schema of the extension takes the toolkit's list
    commit_all(host, "the extension may ask")
    before = _open(host, "merge")
    document = _read(host, DATA_PLACE)
    document["ambiguities"] = malformed
    _write_json(host / "spec" / DATA_PLACE, document)
    found = read_ambiguity_items(str(host / "spec"))
    assert found.error is None
    assert [item.id for item in found.items if Path(item.artifact_path) == host / "spec" / DATA_PLACE] == read
    assert _open(host, "merge") == [*before, *(("E631", "merge-check", DATA_PLACE) for _id in read)]
    assert _schema_errors(capsys, host, DATA_PLACE) != []  # the schema of the file refuses the value


def test_an_ambiguities_field_of_the_hosts_own_shape_is_no_finding(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    """Next to the boundary: the schema of the extension gives the key another meaning, and the data file follows it."""
    before = _open(host, "merge")
    schema = _read(host, SCHEMA_PLACE)
    schema["properties"]["ambiguities"] = {"type": "string"}
    _write_json(host / "spec" / SCHEMA_PLACE, schema)
    document = _read(host, DATA_PLACE)
    document["ambiguities"] = "none yet"
    _write_json(host / "spec" / DATA_PLACE, document)
    assert read_ambiguity_items(str(host / "spec")).error is None and _open(host, "merge") == before
    assert _schema_errors(capsys, host, DATA_PLACE) == []
    code, _out, err = run_split(capsys, "upstream-backlog", str(host / "spec"), "--repo-root", str(ROOT))
    assert code == 0, err


# --- fix round 1, F1: an extension schema that refers to itself ---------------------------------------------------------------


def _tree_host(destination: Path, *, recursive: bool) -> Path:
    """The plain example with a declared extension whose schema has no annotation; with *recursive* a group holds groups by ``$ref`` to itself."""
    host = step_gate_host(destination, attested=False)
    (host / "spec" / "extensions").mkdir()
    apply_delta(host, DECLARE, folder=DELTAS)
    inner = {"$ref": "#/$defs/group"} if recursive else {"type": "object"}
    group = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}, "groups": {"type": "array", "items": inner}}}
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "vc:ext-01-database", "type": "object", "allOf": [{"$ref": "vc:core:step-base"}],
        "$defs": {"group": group}, "properties": {"groups": {"type": "array", "items": {"$ref": "#/$defs/group"}}}, "required": ["groups"],
    }
    data = {
        "$schema": "vc:ext-01-database", "id": "ext-groups", "owner": "data", "created_at": "2026-11-15T00:00:00Z", "canonical_refs_used": [],
        "groups": [{"name": "a", "groups": [{"name": "b", "groups": [{"name": "c", "groups": []}]}]}],
    }
    _write_json(host / "spec" / SCHEMA_PLACE, schema)
    _write_json(host / "spec" / DATA_PLACE, data)
    attest(host)
    commit_all(host, "a tree of groups")
    return host


def test_an_extension_schema_with_no_annotation_that_refers_to_itself_stops_no_command(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """As on 930879e, which never walked a host schema: the answers are those of the same schema with the inner ``$ref`` taken out."""
    tree, flat = _tree_host(tmp_path / "tree", recursive=True), _tree_host(tmp_path / "flat", recursive=False)
    code, out, err = run_split(capsys, "validate", str(tree / "spec" / DATA_PLACE), "--repo-root", str(ROOT), "--spec-root", str(tree / "spec"))
    assert code == 0 and "OK" in out + err, out + err
    code, out, err = _run(capsys, tree, "node", "show", FR)
    assert code == 0 and FR in out, err

    def said(host: Path, *argv: str) -> tuple[int, str, str]:
        code, out, err = _run(capsys, host, *argv)
        plain = [re.sub(r"\b[0-9a-f]{12}\b", "<commit>", text.replace(str(host), "<host>")) for text in (out, err)]  # each host has its own commits
        return code, plain[0], plain[1]

    for argv in (("spec-check", "<spec>", "--step", "13"), ("spec-check", "<spec>"), ("stale",), ("trace", "ms-account-recovery", "--recipe", "16c")):
        answers = [said(host, *(str(host / "spec") if word == "<spec>" else word for word in argv)) for host in (tree, flat)]
        assert answers[0] == answers[1], argv
        assert "recursion" not in answers[0][1] + answers[0][2]


# --- fix round 1, F2: an old commit whose extension schema the graph refuses ---------------------------------------------------

OLD_WORDS = table(json.loads((EXTENSION / "spec" / DATA_PLACE).read_text(encoding="utf-8")))["description"]
NEW_WORDS = "One row for each reset; a used row is kept for a year."
"""The description of the table as the example has it (accepted, committed), and the one a later commit gives it."""
HEAD_REFUSAL = "the extension schemas of the spec folder"
"""How the E520 of a refused schema of the working tree begins: said of the head only, never of an old commit."""
PLAN_ITEM = "PWRESET_CONFIRM_EXPIRED_01"


def _refuse_the_schema(host: Path) -> str:
    """Give the datastores a role the graph refuses; returns the text of the schema as it was."""
    path = host / "spec" / SCHEMA_PLACE
    good = path.read_text(encoding="utf-8")
    assert good.count('"role": "context"') == 1
    path.write_text(good.replace('"role": "context"', '"role": "verifier"'), encoding="utf-8")
    return good


def _describe_the_table(host: Path, words: str) -> None:
    document = _read(host, DATA_PLACE)
    table(document)["description"] = words
    _write_json(host / "spec" / DATA_PLACE, document)


def _commit_of(host: Path, ref: str = "HEAD") -> str:
    return git(host, "rev-parse", ref).strip()


@pytest.fixture
def corrected(host: Path) -> Path:
    """The review's first host: one commit edits the table and holds a refused schema, the next corrects the schema."""
    assert OLD_WORDS and OLD_WORDS != NEW_WORDS
    start_branch(host)
    good = _refuse_the_schema(host)
    _describe_the_table(host, NEW_WORDS)
    commit_all(host, "wip: the table text, and a role the graph refuses")
    (host / "spec" / SCHEMA_PLACE).write_text(good, encoding="utf-8")
    commit_all(host, "correct the role")
    return host


@pytest.fixture
def refused_base(host: Path) -> Path:
    """The review's second host: ``main`` holds a refused schema, the branch corrects it."""
    good = _refuse_the_schema(host)
    commit_all(host, "a refused schema on main")
    start_branch(host)
    (host / "spec" / SCHEMA_PLACE).write_text(good, encoding="utf-8")
    commit_all(host, "correct it")
    return host


def test_stale_and_attest_read_past_a_commit_whose_extension_schema_is_refused(capsys: pytest.CaptureFixture[str], corrected: Path) -> None:
    """The reader of old text (``trace/history.py``): the refused commit is skipped and the accepted text is found in the commit before it."""
    code, out, err = _run(capsys, corrected, "stale", "--diff")
    assert code == 0, out + err
    assert CRITERION in out and OLD_WORDS in out and NEW_WORDS in out
    assert "E520" not in out + err and HEAD_REFUSAL not in out + err
    code, out, err = _run(capsys, corrected, "attest", CRITERION)
    assert code == 0, out + err
    assert OLD_WORDS in out and NEW_WORDS in out and "E520" not in out + err
    code, out, err = _run(capsys, corrected, "attest", CRITERION, "--yes")
    assert code == 0, out + err
    code, out, err = _run(capsys, corrected, "stale")
    assert code == 0 and CRITERION not in out, out + err


ACCEPTED_WORDS = "A row for each reset that was asked for."


def _accepted_text_in_one_commit(host: Path, unreadable: str) -> Path:
    """The text of the table is accepted in the working tree and committed in a commit that cannot be read; the next commit can be read and holds another text."""
    start_branch(host)
    _describe_the_table(host, ACCEPTED_WORDS)
    attest(host)  # accepted while the tree can be read
    stamp = host / "spec" / "specdev_version"
    assert not stamp.exists()
    if unreadable == "its extension schema is refused":
        good = _refuse_the_schema(host)
    else:  # what makes a commit unreadable today: a spec stamped below the node model (E709)
        stamp.write_text('toolkit_version: "1.1.1"\n', encoding="utf-8")
    commit_all(host, "wip: accepted text, in a tree that cannot be read")
    if unreadable == "its extension schema is refused":
        (host / "spec" / SCHEMA_PLACE).write_text(good, encoding="utf-8")
    else:
        stamp.unlink()
    _describe_the_table(host, NEW_WORDS)
    commit_all(host, "a tree that can be read, and another text")
    return host


def test_text_accepted_only_in_the_refused_commit_is_unavailable_as_for_a_commit_that_cannot_be_read_today(capsys: pytest.CaptureFixture[str], tmp_path: Path, host: Path) -> None:
    """No readable commit holds the accepted text: ``stale --diff`` and ``attest`` say what they say of a commit stamped before the node model."""
    refused = _accepted_text_in_one_commit(host, "its extension schema is refused")
    stamped = _accepted_text_in_one_commit(_host(tmp_path / "stamped"), "its stamp is below the node model")
    for argv in (("stale", "--diff"), ("attest", CRITERION)):
        answers = []
        for one in (refused, stamped):
            code, out, err = _run(capsys, one, *argv)
            answers.append((code, out.replace(str(one), "<host>"), err.replace(str(one), "<host>")))
        assert answers[0] == answers[1], argv
        code, out, err = answers[0]
        assert code == 0 and CRITERION in out and NOTE_NO_EARLIER in out, out + err
        assert "E520" not in out + err and ACCEPTED_WORDS not in out


def test_the_pack_of_an_implementer_is_printed_when_the_base_holds_a_refused_extension_schema(capsys: pytest.CaptureFixture[str], refused_base: Path) -> None:
    """The reader of the base of a dependency report (``graph/recipes.py``)."""
    pack = _pack(capsys, refused_base, "16b", PLAN_ITEM, "--since", "main")
    assert PLAN_ITEM in json.dumps(pack["sections"])
    unavailable = pack["dependency_report"]["unavailable"]
    assert unavailable["code"] == "E708" and "'main'" in unavailable["message"] and "extension schema" in unavailable["message"]
    assert HEAD_REFUSAL not in unavailable["message"]
    code, text, err = _run(capsys, refused_base, "trace", PLAN_ITEM, "--recipe", "16b", "--since", "main")
    assert code == 0, err
    assert "unavailable (E708)" in text and "E520" not in text + err
    readable = _pack(capsys, refused_base, "16b", PLAN_ITEM, "--since", "HEAD")  # the boundary: a base that is read
    assert readable["dependency_report"].get("unavailable") is None


def test_the_step_gate_says_that_the_baseline_holds_a_refused_extension_schema(capsys: pytest.CaptureFixture[str], refused_base: Path) -> None:
    """The baseline of the step gate: as one that cannot be read, with the reason, and never the upstream debt counted as new without a word."""
    code, out, err = _run(capsys, refused_base, "spec-check", str(refused_base / "spec"), "--step", "13", "--base-ref", "main")
    assert "base: unavailable" in out, out
    [note] = [line for line in err.splitlines() if line.startswith("note:") and "extension schema" in line]
    assert "'main'" in note and HEAD_REFUSAL not in note
    assert "E520" not in out  # the head is right: nothing of it is refused
    readable = _commit_of(refused_base, "main~1")  # the boundary: the commit before, whose schema is right
    code, out, err = _run(capsys, refused_base, "spec-check", str(refused_base / "spec"), "--step", "13", "--base-ref", readable)
    assert "base: unavailable" not in out and "extension schema" not in err, out + err


def test_diff_names_the_ref_whose_extension_schema_is_refused(capsys: pytest.CaptureFixture[str], refused_base: Path) -> None:
    code, out, err = _run(capsys, refused_base, "diff", "main", "HEAD")
    said = out + err
    assert code == 1 and "E708" in said and "'main'" in said and "extension schema" in said, said
    assert "E520" not in said and HEAD_REFUSAL not in said
    code, out, err = _run(capsys, refused_base, "diff", "main~1", "HEAD")  # the boundary: two refs that are read
    assert code == 0, out + err
    code, out, err = _run(capsys, refused_base, "diff", "main~1", "main")  # the refused ref on the other side
    assert code == 1 and "E708" in out + err and "'main'" in out + err


def test_the_state_of_a_tag_names_the_commit_whose_extension_schema_is_refused(refused_base: Path) -> None:
    """A fifth reader of an old tree, found while looking for the four: the release reads the tree of a tag."""
    refused = _commit_of(refused_base, "main")
    with pytest.raises(GitViewError) as raised, tag_state(str(refused_base), str(refused_base / "spec"), str(ROOT), refused):
        pass
    assert raised.value.error.code == "E708" and refused in raised.value.error.message
    with tag_state(str(refused_base), str(refused_base / "spec"), str(ROOT), "HEAD") as state:  # the boundary
        assert TABLE in state.graph.by_id


def test_a_refused_extension_schema_of_the_working_tree_keeps_its_e520(capsys: pytest.CaptureFixture[str], refused_base: Path) -> None:
    """Next to the four readers: what is refused NOW is said of the head, with the lines to correct."""
    _refuse_the_schema(refused_base)
    for argv in (("stale", "--diff"), ("trace", PLAN_ITEM, "--recipe", "16b", "--since", "main~1"), ("diff", "main~1", "HEAD")):
        code, out, err = _run(capsys, refused_base, *argv)
        if argv[0] == "diff":  # two refs, and both are read: the working tree is not part of it
            assert code == 0, out + err
            continue
        assert code == 1 and "E520" in out + err and HEAD_REFUSAL in out + err and "may not take the role 'verifier'" in out + err, argv


# --- fix round 1, F3: context review of a data file, with no --spec-dir ----------------------------------------------------------


def _review(capsys: pytest.CaptureFixture[str], host: Path, place: str, *more: str, step: str = "13") -> dict[str, Any]:
    code, out, err = run_split(capsys, "context", "review", str(host / "spec" / place), "--step", step, "--repo-root", str(ROOT), "--git-root", str(host), *more)
    assert code == 0, err
    return json.loads(out)


def _missing(review: dict[str, Any]) -> list[tuple[str, str]]:
    """``(description, schema the pair comes from)`` of the fields a review says are missing."""
    return [(pair["description"], pair["source"]["id"]) for pair in review["semantic_pairs"] if pair["check_type"] == "scope_completeness"]


def test_context_review_of_a_data_file_with_no_spec_dir_reads_the_spec_folder_from_the_path(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    """The command is handed one file: the spec folder is the one above its ``extensions`` folder, as with ``--spec-dir``."""
    document = _read(host, DATA_PLACE)
    document.pop("validation_rules")
    _write_json(host / "spec" / DATA_PLACE, document)
    with_flag = _review(capsys, host, DATA_PLACE, "--spec-dir", str(host / "spec"))
    without = _review(capsys, host, DATA_PLACE)
    assert without == with_flag
    [(description, source)] = _missing(without)
    assert "'validation_rules'" in description and source == "vc:ext-01-database"


def test_context_review_of_a_step_file_with_no_spec_dir_takes_the_folder_of_the_file(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    """Unchanged: the folder of a step file is its spec folder, and the file is compared with the schema of its step."""
    manifest = _read(host, MANIFEST)
    manifest.pop("extension_decision")
    _write_json(host / "spec" / MANIFEST, manifest)
    without = _review(capsys, host, MANIFEST)
    assert without == _review(capsys, host, MANIFEST, "--spec-dir", str(host / "spec"))
    assert [source for description, source in _missing(without) if "'extension_decision'" in description] == ["vc:13-extension-manifest"]
    charter = _review(capsys, host, "00_charter.json", step="00")  # a review that reads the spec folder: the seed manifest lies in it
    assert charter == _review(capsys, host, "00_charter.json", "--spec-dir", str(host / "spec"), step="00")
    assert charter != _review(capsys, host, "00_charter.json", "--spec-dir", str(host), step="00")


def test_a_step_file_handed_with_its_spec_folder_is_compared_with_the_schema_of_its_step_whatever_its_own_schema_says(host: Path) -> None:
    """The file of step 13 that names the schema of the extension as its own is still the manifest: the extension's required lists are not asked of it."""
    spec = host / "spec"
    manifest = _read(host, MANIFEST)
    manifest["$schema"] = "vc:ext-01-database"
    manifest.pop("extension_decision")
    _write_json(spec / MANIFEST, manifest)
    result = review_artifact(str(spec / MANIFEST), "13", str(spec), str(ROOT), git_root=str(host))
    sources = {pair.source.id for pair in result.semantic_pairs if pair.check_type == "scope_completeness"}
    assert sources == {"vc:13-extension-manifest"}
    descriptions = [pair.description for pair in result.semantic_pairs if pair.check_type == "scope_completeness"]
    assert [text for text in descriptions if "'extension_decision'" in text] != [] and [text for text in descriptions if "'tables'" in text] == []


# --- fix round 1, F4: the entry of an extension is not renamed by id ---------------------------------------------------------------


@pytest.mark.parametrize("more", [(), ("--dry-run",)])
def test_the_rename_of_an_extension_entry_is_refused_in_words_and_writes_nothing(capsys: pytest.CaptureFixture[str], host: Path, more: tuple[str, ...]) -> None:
    """Its id names its two files and the ``$id`` of its schema: the refusal says what to do by hand, and never fails on a key the entry cannot hold."""
    before = {place: _text(host, place) for place in (MANIFEST, DATA_PLACE, SCHEMA_PLACE, LOCK)}
    code, out, err = _run(capsys, host, "node", "rename", ENTRY, "ext-01-db", *more)
    said = out + err
    assert code == 1 and "E770" in said, said
    assert "aliases" not in said and "schema violation" not in said
    for named in (DATA_PLACE, SCHEMA_PLACE, "$id", "$schema", "move"):
        assert named in said, named
    assert {place: _text(host, place) for place in before} == before
    assert not (host / "spec" / "extensions" / "ext_01_db.json").exists()


def test_a_node_of_an_extension_file_is_still_renamed_by_id(capsys: pytest.CaptureFixture[str], host: Path) -> None:
    """Next to the refusal: the datastore (a context kind of the same file) is renamed, and the table that names it follows."""
    code, out, err = _run(capsys, host, "node", "rename", DATASTORE, "ds-members")
    assert code == 0, out + err
    document = _read(host, DATA_PLACE)
    assert [store["datastore_id"] for store in document["datastores"]] == ["ds-members"]
    assert DATASTORE not in json.dumps(table(document)) and "ds-members" in json.dumps(table(document))


# --- fix round 1, F5: step create 13 <extension-id> advises a command that works -------------------------------------------------

INSERT_ADVICE, CREATE_ADVICE = "specdev json insert --step 13 .extensions", "specdev step create 13 --from"


def test_step_create_13_for_an_extension_when_step_13_has_no_file_advises_to_create_the_manifest(capsys: pytest.CaptureFixture[str], tmp_path: Path, declared: Path) -> None:
    """The entry cannot be inserted into a file that is not there: the advice names the command that makes the manifest, and that command is run here."""
    manifest_draft = tmp_path / "manifest.json"
    shutil.move(declared / "spec" / MANIFEST, manifest_draft)
    lock_before = _text(declared, LOCK)
    code, said = _create(capsys, declared, "13", ENTRY, "--from", _draft(tmp_path))
    assert code == 1 and "E767" in said and ENTRY in said, said
    assert CREATE_ADVICE in said and INSERT_ADVICE not in said
    assert _nothing_written(declared, lock_before)
    code, out, err = _run(capsys, declared, "json", "insert", "--step", "13", ".extensions", json.dumps(json.loads(manifest_draft.read_text(encoding="utf-8"))["extensions"][0]))
    assert code == 1, out + err  # why the other advice would be wrong here
    code, said = _create(capsys, declared, "13", "--from", str(manifest_draft))  # the advised command
    assert code == 0 and (declared / "spec" / MANIFEST).exists(), said
    code, said = _create(capsys, declared, "13", ENTRY, "--from", _draft(tmp_path))  # and what the person wanted now works
    assert code == 0 and (declared / "spec" / DATA_PLACE).exists(), said


def test_step_create_13_for_an_extension_the_manifest_lacks_still_advises_the_insert_and_the_insert_works(capsys: pytest.CaptureFixture[str], tmp_path: Path, declared: Path) -> None:
    """Unchanged: with a manifest, the entry is inserted into it; the advised command is run here."""
    code, said = _create(capsys, declared, "13", "ext-02-cache", "--from", _draft(tmp_path))
    assert code == 1 and INSERT_ADVICE in said and CREATE_ADVICE not in said, said
    entry = {**_read(declared, MANIFEST)["extensions"][0], "extension_id": "ext-02-cache", "title": "Cache"}
    code, out, err = _run(capsys, declared, "json", "insert", "--step", "13", ".extensions", json.dumps(entry))
    assert code == 0, out + err
    assert [found["extension_id"] for found in _read(declared, MANIFEST)["extensions"]] == [ENTRY, "ext-02-cache"]
    code, said = _create(capsys, declared, "13", "ext-02-cache", "--from", _draft(tmp_path))
    assert code == 1 and "declares no extension" not in said and "extensions/ext_02_cache.schema.json" in said, said  # the next thing in the way: its schema


# --- fix round 1, F10: tests the mutation runs asked for -----------------------------------------------------------------------


def test_a_review_pair_names_the_schema_file_its_field_comes_from(host: Path) -> None:
    """The schema file of the extension for its data file; a schema file of the toolkit's step for the manifest."""
    spec = host / "spec"

    def source_files(place: str, dropped: str) -> set[str]:
        document = _read(host, place)
        document.pop(dropped)
        _write_json(spec / place, document)
        result = review_artifact(str(spec / place), "13", str(spec), str(ROOT), git_root=str(host))
        return {pair.source.file for pair in result.semantic_pairs if pair.check_type == "scope_completeness" and f"'{dropped}'" in pair.description}

    assert source_files(DATA_PLACE, "validation_rules") == {SCHEMA_PLACE}
    [of_step] = source_files(MANIFEST, "extension_decision")
    assert of_step.startswith("schema/13_") and of_step.endswith(".schema.json")


def test_step_create_13_tells_a_missing_schema_file_from_one_that_is_refused(capsys: pytest.CaptureFixture[str], tmp_path: Path, declared: Path) -> None:
    """Two reasons, two ways out: write the file, or read what the check says of it (and the check does say it)."""
    path = declared / "spec" / SCHEMA_PLACE
    good = path.read_text(encoding="utf-8")
    assert good.count('"vc:ext-01-database"') == 1
    path.write_text(good.replace('"vc:ext-01-database"', '"vc:ext-01-db"'), encoding="utf-8")  # there, and not the schema its name says: refused
    code, refused = _create(capsys, declared, "13", ENTRY, "--from", _draft(tmp_path))
    assert code == 1 and "E767" in refused and SCHEMA_PLACE in refused, refused
    path.unlink()
    code, missing = _create(capsys, declared, "13", ENTRY, "--from", _draft(tmp_path))
    assert code == 1 and "E767" in missing and SCHEMA_PLACE in missing, missing
    assert "missing" in missing and "missing" not in refused
    assert "spec-check" in refused and "spec-check" not in missing
    path.write_text(good.replace('"vc:ext-01-database"', '"vc:ext-01-db"'), encoding="utf-8")
    said = [finding for finding in _findings(capsys, declared) if SCHEMA_PLACE in json.dumps(finding)]
    assert [finding["code"] for finding in said if "vc:ext-01-db" in finding["message"]] != []  # the advised command says why
    path.write_text(good, encoding="utf-8")  # the way out of both: the schema file, right
    code, said_now = _create(capsys, declared, "13", ENTRY, "--from", _draft(tmp_path))
    assert code == 0, said_now


def test_the_result_of_step_create_13_names_the_id_of_the_draft_or_the_file(capsys: pytest.CaptureFixture[str], tmp_path: Path, declared: Path) -> None:
    code, out, err = _run(capsys, declared, "step", "create", "13", ENTRY, "--from", _draft(tmp_path), "--json", "--dry-run")
    assert code == 0, err
    with_id = json.loads(out)
    assert with_id["id"] == json.loads(DATA_FILE.read_text(encoding="utf-8"))["id"]  # the key of the JSON report is "id"
    # an extension whose schema asks for no top-level id: the result names the file
    sections = ["notes", "regions", "limits"]  # an entry names at least three
    texts = {"type": "array", "items": {"type": "string"}}
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "vc:ext-02-cache", "type": "object", "properties": dict.fromkeys(sections, texts)}
    _write_json(declared / "spec" / "extensions" / "ext_02_cache.schema.json", schema)
    entry = {**_read(declared, MANIFEST)["extensions"][0], "extension_id": "ext-02-cache", "title": "Cache", "required_schema_sections": sections}
    code, out, err = _run(capsys, declared, "json", "insert", "--step", "13", ".extensions", json.dumps(entry))
    assert code == 0, out + err
    draft = tmp_path / "cache.json"
    _write_json(draft, {"$schema": "vc:ext-02-cache", "notes": ["none yet"]})
    code, out, err = _run(capsys, declared, "step", "create", "13", "ext-02-cache", "--from", str(draft), "--json", "--dry-run")
    assert code == 0, out + err
    without_id = json.loads(out)
    assert "ext_02_cache" in without_id["id"] and without_id["id"] != "None" and without_id["file"] == "extensions/ext_02_cache.json"


# --- fix round 1, F10: what review L found clean by probe and no test held ---------------------------------------------------------


def _item_in(tmp_path: Path, name: str, place: str | None) -> Path:
    """The extension host with ``OPEN_ITEM`` in the ``ambiguities`` of the file *place* (in no file for ``None``), its links accepted, committed."""
    host = _host(tmp_path / name, committed=False)
    if place == DATA_PLACE:
        _ask(host, OPEN_ITEM)
    elif place is not None:
        document = _read(host, place)
        document["ambiguities"] = [OPEN_ITEM]
        _write_json(host / "spec" / place, document)
        attest(host)
    commit_all(host, "the extension, and an open question" if place else "the extension")
    return host


def _reword_the_requirement(host: Path) -> None:
    """Edit the statement of the FR the open item is about: every link to it is to be read again."""
    [path] = (host / "spec").glob("04_*.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    [requirement] = [item for item in document["functional_requirements"] if item["fr_id"] == FR]
    requirement["statement"] += " The link in the mail is valid once."
    _write_json(path, document)


def test_status_and_step_ready_14_read_an_open_item_of_a_data_file_as_they_read_one_of_the_manifest(capsys: pytest.CaptureFixture[str], tmp_path: Path, host: Path) -> None:
    """Decision 8: read like a step file's, under step 13.  The manifest (the step's own file) with the same item is the measure."""
    in_data, in_manifest = _item_in(tmp_path, "data", DATA_PLACE), _item_in(tmp_path, "manifest", MANIFEST)

    def owners(of: Path) -> dict[str, list[str]]:
        code, out, err = _run(capsys, of, "status", "--json")
        assert code == 0, out + err
        return json.loads(out)["sections"]["open_items"]["data"]

    assert OPEN_ITEM["id"] in owners(in_data)[STEP_13]
    assert owners(in_data) == owners(in_manifest)
    assert OPEN_ITEM["id"] not in owners(host).get(STEP_13, [])  # the host with no such item: the comparison can fail

    def said(of: Path) -> list[str]:
        """The lines of ``status`` that name the item, with the manifest's name for the data file's."""
        _code, out, _err = _run(capsys, of, "status")
        return [line.replace(DATA_PLACE, MANIFEST) for line in out.splitlines() if OPEN_ITEM["id"] in line]

    count = len(owners(in_data)[STEP_13])
    assert [line.strip() for line in said(in_data) if line.strip().startswith(f"{STEP_13}: ")] == [f"{STEP_13}: {count} ({', '.join(owners(in_data)[STEP_13])})"]
    assert said(in_data) == said(in_manifest)  # what it says of one it says of the other, in every section
    assert said(host) == []

    def ready(of: Path) -> tuple[int, list[tuple[str, str, str, str, str]]]:
        code, out, _err = _run(capsys, of, "step", "ready", "14", "--json")
        return code, [(b["step"], b["reason"], b["node"], b["field"], b["target"]) for b in json.loads(out)["blockers"]]

    assert ready(in_data) == ready(in_manifest) == ready(host)  # accepted, nothing edited: the item keeps step 14 from nothing
    for each in (in_data, in_manifest, host):
        _reword_the_requirement(each)
    code, blockers = ready(in_data)
    assert code == 1 and ("13", "suspect", TABLE, "derives_from", FR) in blockers  # a node of the data file is read again before step 14 starts
    assert ready(in_manifest) == (code, blockers)  # and the open item changes that no more in the data file than in the manifest


def test_a_write_by_id_with_the_repo_root_flag_only_writes_what_the_three_flags_write(capsys: pytest.CaptureFixture[str], tmp_path: Path, host: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """From the root of the host, whose spec folder is ``spec``: the same file, the same lock entries, the same report."""
    twin = tmp_path / "twin"
    shutil.copytree(host, twin, symlinks=True)
    writes = [
        ("json", "patch", "--id", TABLE, ".description", '"One row for each reset a member asked for."'),
        ("json", "insert", "--id", PARKED_TABLE, ".verified_by", f'"{OTHER_FIXTURE}"'),
        ("json", "delete", "--id", PARKED_TABLE),
    ]
    places = (DATA_PLACE, "extras/trace.lock.json")
    before = {place: (host / "spec" / place).read_text(encoding="utf-8") for place in places}
    for write in writes:
        with_three = _run(capsys, host, *write)  # from another folder (the fixture), every root told
        monkeypatch.chdir(twin)
        with_one = run_split(capsys, *write, "--repo-root", str(ROOT))
        monkeypatch.chdir(tmp_path / "elsewhere")
        assert with_three[0] == 0, with_three
        assert with_one == with_three, write
        for place in places:
            assert (twin / "spec" / place).read_text(encoding="utf-8") == (host / "spec" / place).read_text(encoding="utf-8"), (write, place)
    assert all((host / "spec" / place).read_text(encoding="utf-8") != text for place, text in before.items())  # the writes did write, the file and the lock
    assert _read(twin, DATA_PLACE)["tables"][0]["description"] == "One row for each reset a member asked for."
    assert [item["table_id"] for item in _read(twin, DATA_PLACE)["tables"]] == [TABLE]
