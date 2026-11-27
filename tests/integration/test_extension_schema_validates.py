"""A host extension schema that validates, end to end (DEVSPEC-245, piece A).

The worked example (``tests/fixtures/graph_example``) is copied as a git repository: plain, and with the small
database extension of ``tests/fixtures/extension_example`` (its schema and data file under ``spec/extensions`` and the
manifest entry that declares them).  No number is pinned: the extension copy must report what the plain copy reports,
and each negative case must add the findings of its row of the table and nothing else, all owned by step 13.

The negative cases run in three layouts (the three root flags, no ``--spec-root``, the spec folder at ``sub/spec``), and
the gate cases run with the extension committed, so that a baseline tree holds an extension too.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import (
    NESTED_SPEC, apply_delta, attest, commit_all, nested_step_gate_host, run_split, start_branch, step_gate_host,
)
from specdev_tools.core.registry import get_shared_registry
from unit.graph._synth import git
from unit.trace._lock_support import EXAMPLE_HOST, ROOT

EXTENSION = ROOT / "tests" / "fixtures" / "extension_example"
DELTAS = EXTENSION / "deltas"
FOLDER = "spec/extensions"
SCHEMA_NAME = "ext_01_database.schema.json"
DATA_NAME = "ext_01_database.json"
SCHEMA_PLACE = f"extensions/{SCHEMA_NAME}"
DATA_PLACE = f"extensions/{DATA_NAME}"
URI = "vc:ext-01-database"
STEP_13 = "step:13"
MANIFEST = "13_extension_manifest.json"
TERM = "cn:project:term:reset-token"
"""The canonical ref the example's table ``tbl-reset-token`` carries (a term of the worked example's project canon)."""
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
RESTORED = (f"spec/{MANIFEST}", "spec/extras/trace.lock.json")

SECOND_URI = "vc:ext-02-cache"
SECOND_SCHEMA_PLACE = "extensions/ext_02_cache.schema.json"
SECOND_DATA_PLACE = "extensions/ext_02_cache.json"
SECOND_SCHEMA: dict[str, Any] = {
    "$schema": DRAFT_2020_12,
    "$id": SECOND_URI,
    "title": "ext_02_cache",
    "type": "object",
    "properties": {
        "caches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"cache_id": {"$ref": "vc:core:atoms#kebabId"}, "ttl_seconds": {"type": "integer", "minimum": 1}},
                "required": ["cache_id", "ttl_seconds"],
                "additionalProperties": False,
            },
        },
        "eviction_rules": {"type": "array", "items": {"type": "string"}},
        "validation_rules": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["caches", "eviction_rules", "validation_rules"],
    "allOf": [{"$ref": "vc:core:step-base"}],
    "unevaluatedProperties": False,
}
SECOND_DATA: dict[str, Any] = {
    "$schema": SECOND_URI,
    "id": "ext-cache-password-reset",
    "owner": "data",
    "created_at": "2026-11-15T00:00:00Z",
    "caches": [{"cache_id": "cache-reset-attempts", "ttl_seconds": 900}],
    "eviction_rules": ["An entry of cache-reset-attempts is dropped when its ttl_seconds have passed."],
    "validation_rules": ["A test reads cache-reset-attempts after ttl_seconds and finds no entry."],
    "canonical_refs_used": [],
}

Key = tuple[str, str | None, str | None]


def _prefix(host: Path) -> str:
    """Where the spec folder of *host* is: ``sub/spec`` in the nested layout."""
    return NESTED_SPEC if (host / NESTED_SPEC).is_dir() else "spec"


def _spec(host: Path) -> Path:
    return host / _prefix(host)


def _add_extension(host: Path, *deltas: str, declared: bool = True) -> None:
    """Put the extension's two files into *host*, declare it (unless not *declared*), apply *deltas* and accept every link."""
    shutil.copytree(EXTENSION / FOLDER, _spec(host) / "extensions")
    for name in (("declare_extension",) if declared else ()) + deltas:
        apply_delta(host, name, _prefix(host), folder=DELTAS)
    attest(host, _prefix(host))


def _extension_host(destination: Path, *deltas: str, declared: bool = True, nested: bool = False) -> Path:
    """The worked example with the extension (see ``_add_extension``), uncommitted: the one commit is the plain example."""
    host = nested_step_gate_host(destination) if nested else step_gate_host(destination, attested=False)
    _add_extension(host, *deltas, declared=declared)
    return host


def _edit_json(path: Path, change: Any) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _declare_second(host: Path, *, files: bool) -> None:
    """Declare ``ext-02-cache`` in the manifest of *host*, with its schema and data file when *files*; every link accepted."""
    first = next(op["value"] for op in json.loads((DELTAS / "declare_extension.json").read_text(encoding="utf-8"))["ops"] if op["op"] == "append")
    entry = {
        **first,
        "extension_id": "ext-02-cache",
        "title": "Cache Extension",
        "area_of_concern": "Performance",
        "justification": "The reset flow limits attempts per member with a short-lived counter; no core step describes a cache and its eviction.",
        "required_schema_sections": ["caches", "eviction_rules", "validation_rules"],
        "schema_design_guidelines": "Reuse vc:core:atoms#kebabId for cache ids (cache-{name}). Every cache states its ttl_seconds; include validation_rules that a test can verify.",
    }
    _edit_json(_spec(host) / MANIFEST, lambda manifest: manifest["extensions"].append(entry))
    if files:
        (_spec(host) / SECOND_SCHEMA_PLACE).write_text(json.dumps(SECOND_SCHEMA, indent=2) + "\n", encoding="utf-8")
        (_spec(host) / SECOND_DATA_PLACE).write_text(json.dumps(SECOND_DATA, indent=2) + "\n", encoding="utf-8")
    attest(host, _prefix(host))


def _flags(host: Path, *, spec_root: bool = True) -> list[str]:
    named = ["--spec-root", str(_spec(host))] if spec_root else []
    return ["--repo-root", str(ROOT), *named, "--git-root", str(host)]


def _output(capsys: pytest.CaptureFixture[str], host: Path, *flags: str, spec_root: bool = True) -> tuple[int, str]:
    """``spec-check <flags>`` on *host*: the exit code and stdout with the host's folder written ``<host>``."""
    code, out, _err = run_split(capsys, "spec-check", str(_spec(host)), *_flags(host, spec_root=spec_root), *flags)
    return code, out.replace(str(host), "<host>")


def _report(capsys: pytest.CaptureFixture[str], host: Path, *flags: str, spec_root: bool = True) -> dict[str, Any]:
    _code, out = _output(capsys, host, *flags, "--json", spec_root=spec_root)
    return json.loads(out)


def _key(finding: dict[str, Any]) -> Key:
    return finding["code"], finding.get("node_id"), finding.get("owner")


def _findings(capsys: pytest.CaptureFixture[str], host: Path, *, spec_root: bool = True) -> list[dict[str, Any]]:
    return _report(capsys, host, spec_root=spec_root)["errors"]


def _added(findings: list[dict[str, Any]], plain: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The findings of *findings* beyond those of *plain*, compared by code, node and owner; fails if one of *plain* is gone."""
    left = Counter(_key(finding) for finding in plain)
    added = []
    for finding in findings:
        if left[_key(finding)] > 0:
            left[_key(finding)] -= 1
        else:
            added.append(finding)
    assert +left == Counter(), f"findings of the plain example that are gone: {+left}"
    return added


def _whole(findings: list[dict[str, Any]]) -> list[str]:
    """Each finding with every key it has (its file, its place and its text too), sorted: what ``_added`` does not compare."""
    return sorted(json.dumps(finding, sort_keys=True) for finding in findings)


def _texts(findings: list[dict[str, Any]]) -> list[str]:
    return [finding["message"] for finding in findings]


def _of_step_13(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [finding for finding in findings if finding.get("owner") == STEP_13]


def _gate(capsys: pytest.CaptureFixture[str], host: Path, step: str) -> dict[str, Any]:
    """The step gate of *step* on *host* (``--detail all``): new upstream errors are in ``blocking``, old ones in ``upstream_debt``."""
    return _report(capsys, host, "--step", step, "--detail", "all")["step_gate"]


def _has_each(texts: list[str], *wanted: str) -> bool:
    """Each of *wanted* is in a text of its own, and there is no text beyond them."""
    left = list(texts)
    for words in wanted:
        match = next((text for text in left if words in text), None)
        if match is None:
            return False
        left.remove(match)
    return left == []


@pytest.fixture
def plain(tmp_path: Path) -> Path:
    return step_gate_host(tmp_path / "plain")


# --- the extension validates ----------------------------------------------------------------------------------------


def test_the_example_with_the_extension_reports_what_the_plain_example_reports(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, plain: Path,
) -> None:
    host = _extension_host(tmp_path / "host")
    plain_report, report = _report(capsys, plain), _report(capsys, host)
    assert sorted(map(_key, report["errors"]), key=str) == sorted(map(_key, plain_report["errors"]), key=str)
    assert _added(report["errors"], plain_report["errors"]) == []
    assert (report["status"], report["error_count"], report["warning_count"]) == (
        plain_report["status"], plain_report["error_count"], plain_report["warning_count"],
    )
    assert [name for name in report["checks"] if report["checks"][name] != plain_report["checks"][name]] == []
    assert "extensions" not in json.dumps(report)  # neither file is named by any finding or note
    assert _output(capsys, host) == _output(capsys, plain)  # and the text a person reads is the same, to the byte


def test_the_extension_does_not_block_step_13(capsys: pytest.CaptureFixture[str], tmp_path: Path, plain: Path) -> None:
    host = _extension_host(tmp_path / "host")
    plain_code, plain_text = _output(capsys, plain, "--step", "13")
    code, text = _output(capsys, host, "--step", "13")
    plain_gate, gate = _report(capsys, plain, "--step", "13")["step_gate"], _report(capsys, host, "--step", "13")["step_gate"]
    assert gate["blocking"] == [] and [finding for finding in gate["own_warnings"] if "xtension" in finding["message"]] == []
    assert (code, gate["result"]) == (plain_code, plain_gate["result"])
    for part in ("blocking", "waiting", "own_warnings", "new_upstream_warnings", "upstream_debt", "gate_owned"):
        assert sorted(map(_key, gate[part]), key=str) == sorted(map(_key, plain_gate[part]), key=str), part
    assert gate["pending"] == plain_gate["pending"]
    assert [line for line in text.splitlines() if not line.startswith("step gate:")] == [
        line for line in plain_text.splitlines() if not line.startswith("step gate:")
    ]  # the header line names the base commit, which is each copy's own


# --- each row of the findings table is the one difference -----------------------------------------------------------

NOT_FOUND = [f"schema_not_found uri={URI}", f"{SCHEMA_PLACE} in the spec folder"]
TWO_NOT_FOUND = [("E520", [DATA_PLACE, *NOT_FOUND]), ("E520", ["UNRESOLVED_INPUT", DATA_PLACE, *NOT_FOUND])]
"""Today's two E520 of a file whose schema is not loaded: schema validation and canonical integrity."""
DRAFT_07 = "http://json-schema.org/draft-07/schema#"


def _remove(*places: str) -> Any:
    def change(host: Path) -> None:
        for place in places:
            (_spec(host) / place).unlink()
    return change


def _write(place: str, text: str) -> Any:
    return lambda host: (_spec(host) / place).write_text(text, encoding="utf-8")


def _dialect(value: Any) -> Any:
    return lambda host: _edit_json(_spec(host) / SCHEMA_PLACE, lambda schema: schema.update({"$schema": value}))


CASES: dict[str, tuple[tuple[str, ...], Any, bool, list[tuple[str, list[str]]]]] = {
    # name: (deltas, an edit of the files, the entry is declared, the findings added: (code, words))
    "the data file breaks its schema": (
        ("data_breaks_schema",), None, True, [("E520", [f"{DATA_PLACE}:tables/0/columns", "'x' is not of type 'array'"])],
    ),
    "the entry has no schema file": (
        (), _remove(SCHEMA_PLACE), True,
        [("E520", [MANIFEST, "Extension 'ext-01-database' has no schema", f"expected {SCHEMA_PLACE}"]), *TWO_NOT_FOUND],
    ),
    "the entry has no data file": (
        (), _remove(DATA_PLACE), True,
        [("E520", [MANIFEST, "Extension 'ext-01-database' has no file", f"expected {DATA_PLACE}"])],
    ),
    "no entry declares the two files": (
        (), None, False,
        [("E520", [f"{SCHEMA_PLACE}: no entry of {MANIFEST} declares it"]),
         ("E520", [f"{DATA_PLACE}: no entry of {MANIFEST} declares it"])],
    ),
    "a schema file no entry declares": (
        (), _write("extensions/ext_02_search.schema.json", json.dumps({"$id": "vc:ext-02-search", "type": "object"})), True,
        [("E520", [f"extensions/ext_02_search.schema.json: no entry of {MANIFEST} declares it"])],
    ),
    "the schema is not a JSON Schema": (
        ("schema_not_json_schema",), None, True,
        [("E520", [f"Extension schema {SCHEMA_PLACE} is not a valid JSON Schema", "'arrray'", "/properties/tables/type"]), *TWO_NOT_FOUND],
    ),
    "the schema has an $id that is not its file name's": (
        ("schema_wrong_id",), None, True,
        [("E520", [f"Extension schema {SCHEMA_PLACE}", 'has the "$id" "vc:ext-01-db"', f'its file name gives "$id": "{URI}"']), *TWO_NOT_FOUND],
    ),
    "the schema has the $id of a toolkit schema": (
        ("schema_toolkit_id",), None, True,
        [("E520", [f"Extension schema {SCHEMA_PLACE}", 'the "$id" of a toolkit schema ("vc:core:atoms")']), *TWO_NOT_FOUND],
    ),
    "the schema names a draft that is not 2020-12": (  # X3
        (), _dialect(DRAFT_07), True, [("E520", [SCHEMA_PLACE, DRAFT_07, DRAFT_2020_12]), *TWO_NOT_FOUND],
    ),
    "a required section is not a property of the schema": (
        ("section_not_in_schema",), None, True,
        [("E320", ["Extension 'ext-01-database' required_schema_sections[3] 'migrations'", f"is not a property of its schema {SCHEMA_PLACE}"])],
    ),
}

LAYOUTS: dict[str, tuple[bool, bool]] = {
    # name: (the spec folder is sub/spec, --spec-root is passed)
    "the three root flags": (False, True),
    "no --spec-root": (False, False),
    "the nested layout sub/spec": (True, True),
}
_PLAIN: dict[str, list[dict[str, Any]]] = {}
"""The findings of the plain example in each layout (compared by code, node and owner, so one run serves every case)."""


def _plain_findings(capsys: pytest.CaptureFixture[str], tmp_path: Path, layout: str) -> list[dict[str, Any]]:
    if layout not in _PLAIN:
        nested, spec_root = LAYOUTS[layout]
        destination = tmp_path / f"plain {layout}"
        host = nested_step_gate_host(destination) if nested else step_gate_host(destination)
        _PLAIN[layout] = _findings(capsys, host, spec_root=spec_root)
    return _PLAIN[layout]


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
@pytest.mark.parametrize("case", sorted(CASES))
def test_a_negative_case_adds_the_findings_of_its_row_and_nothing_else(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, case: str, layout: str,
) -> None:
    deltas, edit, declared, expected = CASES[case]
    nested, spec_root = LAYOUTS[layout]
    host = _extension_host(tmp_path / "host", *deltas, declared=declared, nested=nested)
    if edit is not None:
        edit(host)
    added = _added(_findings(capsys, host, spec_root=spec_root), _plain_findings(capsys, tmp_path, layout))
    if not spec_root:  # Z4: the same host with the flag says the same, to the file and the text (``_added`` sees neither)
        assert _whole(added) == _whole(_added(_findings(capsys, host), _plain_findings(capsys, tmp_path, "the three root flags")))
    assert {(finding["code"], finding.get("owner")) for finding in added} == {(code, STEP_13) for code, _words in expected}, added
    assert len(added) == len(expected), _texts(added)
    unmatched = [text.replace(str(host), "<host>") for text in _texts(added)]
    for code, words in expected:
        match = next((text for text in unmatched if all(word in text for word in words)), None)
        assert match is not None, (code, words, unmatched)
        unmatched.remove(match)


def test_a_finding_of_the_extension_blocks_step_13_as_its_own(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    host = _extension_host(tmp_path / "host", "data_breaks_schema")
    code, _text = _output(capsys, host, "--step", "13")
    gate = _report(capsys, host, "--step", "13")["step_gate"]
    assert (code, gate["result"]) == (1, "blocked")
    assert [_key(finding) for finding in gate["blocking"]] == [("E520", None, STEP_13)]
    assert "tables/0/columns: 'x' is not of type 'array'" in gate["blocking"][0]["message"]
    gate = _report(capsys, host, "--step", "12")["step_gate"]
    assert [finding for finding in gate["blocking"] if finding.get("owner") == STEP_13] == []  # a later step's: not step 12's block


# --- X2: the $schema of a data file is the URI its file name gives --------------------------------------------------

TOOLKIT_SCHEMAS = {
    "the toolkit's step 04 schema": "schema/04_fr_list.schema.json",
    "the toolkit's manifest schema": "schema/13_extension_manifest.schema.json",
    "a core schema of the toolkit": "schema/core/atoms.schema.json",
}


def _toolkit_uri(schema_file: str) -> str:
    """The URI under which the toolkit's own registry holds its schema file *schema_file* (Z4: a URI the toolkit does hold)."""
    (uri,) = [uri for uri, place in get_shared_registry(str(ROOT)).map.items() if place == schema_file]
    return uri


WRONG_SCHEMAS: dict[str, str | None] = {
    "a typo": "vc:ext-1-database",
    "the accepted uri of another extension": SECOND_URI,
    "a uri no schema has": "vc:04-functional-requirements",
    **{name: _toolkit_uri(schema_file) for name, schema_file in TOOLKIT_SCHEMAS.items()},
    "no $schema at all": None,
}


@pytest.mark.parametrize("case", sorted(WRONG_SCHEMAS))
def test_a_data_file_whose_schema_is_not_the_uri_of_its_file_name_is_e520_of_step_13(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, plain: Path, case: str,
) -> None:
    """Two declared extensions, both clean; then the first data file names *case*.  It is judged by no schema but its own."""
    value = WRONG_SCHEMAS[case]
    host = _extension_host(tmp_path / "host")
    _declare_second(host, files=True)
    plain_findings = _findings(capsys, plain)
    assert _texts(_added(_findings(capsys, host), plain_findings)) == []
    _edit_json(host / FOLDER / DATA_NAME, lambda data: data.pop("$schema") if value is None else data.update({"$schema": value}))
    added = _added(_findings(capsys, host), plain_findings)
    assert added != []
    for finding in added:
        text = finding["message"]
        assert (finding["code"], finding.get("owner")) == ("E520", STEP_13), finding
        assert DATA_PLACE in text and URI in text and "$schema" in text, text
        assert value is None or value in text, text
        assert "tools/schema_registry.json" not in text and "--repo-root" not in text, text
        # judged by no other schema: nothing of the shape a schema asks for, whichever schema the file names
        assert not any(word in text for word in ("required property", "nevaluated", "is not of type", "is not valid under")), text
    assert _whole(_added(_findings(capsys, host, spec_root=False), plain_findings)) == _whole(added)


# --- X5: files in the folder and no manifest ------------------------------------------------------------------------


def test_extension_files_in_a_spec_with_no_manifest_are_e520_each_and_their_path_gates_step_13(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    control = step_gate_host(tmp_path / "control", attested=False)
    (control / "spec" / MANIFEST).unlink()
    attest(control)
    host = _extension_host(tmp_path / "host", declared=False)
    (host / "spec" / MANIFEST).unlink()
    attest(host)
    added = _added(_findings(capsys, host), _findings(capsys, control))
    assert {(finding["code"], finding.get("owner")) for finding in added} == {("E520", STEP_13)}, added
    assert _has_each(_texts(added), SCHEMA_PLACE, DATA_PLACE), _texts(added)
    assert all(f"has no {MANIFEST} to declare it" in text for text in _texts(added)), _texts(added)
    monkeypatch.chdir(host)
    for name in (DATA_NAME, SCHEMA_NAME):
        gate = _report(capsys, host, "--paths", f"{FOLDER}/{name}")["step_gate"]
        assert gate["steps"] == ["13"] and gate["result"] == "blocked", name
        assert _has_each(_texts(_of_step_13(gate["blocking"])), SCHEMA_PLACE, DATA_PLACE), gate["blocking"]


def test_a_touched_file_of_the_extensions_folder_gates_step_13(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """X4: any name directly in the folder, whether the file is there or not; the gate of the clean extension is clear."""
    host = _extension_host(tmp_path / "host")
    monkeypatch.chdir(host)
    for name in (DATA_NAME, SCHEMA_NAME, "notes.json", "ext-01-database.json"):
        gate = _report(capsys, host, "--paths", f"{FOLDER}/{name}")["step_gate"]
        assert gate["steps"] == ["13"], name
        assert _of_step_13(gate["blocking"]) == [], name


# --- X6: each manifest finding has its own identity -----------------------------------------------------------------


def test_the_gate_tells_the_findings_of_one_entry_from_those_of_another(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """The baseline commit has "ext-01 has no file"; the head declares ``ext-02-cache`` with neither file."""
    host = _extension_host(tmp_path / "host")
    data_file = host / FOLDER / DATA_NAME
    kept = data_file.read_text(encoding="utf-8")
    data_file.unlink()
    attest(host)
    commit_all(host, "the extension, its data file missing")
    _declare_second(host, files=False)

    gate = _gate(capsys, host, "14")  # the baseline finding left in place in the head: debt 1 and new 2
    assert _has_each(_texts(_of_step_13(gate["upstream_debt"])), "Extension 'ext-01-database' has no file"), gate["upstream_debt"]
    assert _has_each(
        _texts(_of_step_13(gate["blocking"])), "Extension 'ext-02-cache' has no schema", "Extension 'ext-02-cache' has no file",
    ), gate["blocking"]

    data_file.write_text(kept, encoding="utf-8")  # the head restores the file: 2 new and no debt of step 13
    attest(host)
    gate = _gate(capsys, host, "14")
    assert _of_step_13(gate["upstream_debt"]) == [], gate["upstream_debt"]
    assert _has_each(
        _texts(_of_step_13(gate["blocking"])), "Extension 'ext-02-cache' has no schema", "Extension 'ext-02-cache' has no file",
    ), gate["blocking"]


def test_the_gate_tells_the_findings_of_one_file_of_the_folder_from_those_of_another(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    """The baseline commit has one file no entry declares; the head removes it and adds another: one new, no debt."""
    host = _extension_host(tmp_path / "host")
    (host / FOLDER / "notes.json").write_text("{}", encoding="utf-8")
    commit_all(host, "the extension and a file nothing declares")
    (host / FOLDER / "notes.json").unlink()
    (host / FOLDER / "other.schema.json").write_text("{}", encoding="utf-8")
    gate = _gate(capsys, host, "14")
    assert _of_step_13(gate["upstream_debt"]) == [], gate["upstream_debt"]
    assert _has_each(_texts(_of_step_13(gate["blocking"])), "extensions/other.schema.json"), gate["blocking"]


# --- X7: the extension committed (a baseline tree that holds an extension too) --------------------------------------


def test_a_committed_extension_is_clean_and_data_broken_in_the_head_is_new_then_debt(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, plain: Path,
) -> None:
    host = _extension_host(tmp_path / "host")
    commit_all(host, "the extension")
    assert _texts(_added(_findings(capsys, host), _findings(capsys, plain))) == []
    for step in ("13", "14"):
        gate, plain_gate = _gate(capsys, host, step), _gate(capsys, plain, step)
        assert gate["result"] == plain_gate["result"], step
        for part in ("blocking", "own_warnings", "new_upstream_warnings", "upstream_debt"):
            assert sorted(map(_key, gate[part]), key=str) == sorted(map(_key, plain_gate[part]), key=str), (step, part)

    apply_delta(host, "data_breaks_schema", folder=DELTAS)  # broken in the head only
    own = _gate(capsys, host, "13")
    assert own["result"] == "blocked" and _has_each(_texts(_of_step_13(own["blocking"])), "tables/0/columns"), own["blocking"]
    later = _gate(capsys, host, "14")
    assert _has_each(_texts(_of_step_13(later["blocking"])), "tables/0/columns"), later["blocking"]  # new upstream
    assert _of_step_13(later["upstream_debt"]) == []

    commit_all(host, "the broken data file")  # now the baseline has it too
    later = _gate(capsys, host, "14")
    assert _of_step_13(later["blocking"]) == [], later["blocking"]
    assert _has_each(_texts(_of_step_13(later["upstream_debt"])), "tables/0/columns"), later["upstream_debt"]
    assert _gate(capsys, host, "13")["result"] == "blocked"  # its own step never takes it as debt


def test_a_schema_changed_in_the_head_judges_the_head_and_the_baseline_keeps_its_own(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    """Head and baseline in one process: neither tree is judged by the other's schema."""
    host = _extension_host(tmp_path / "host")
    commit_all(host, "the extension")
    schema_file = host / FOLDER / SCHEMA_NAME
    _edit_json(schema_file, lambda schema: schema["required"].append("migrations"))  # stricter in the head
    gate = _gate(capsys, host, "14")
    new = _texts(_of_step_13(gate["blocking"]))
    assert new != [] and all(DATA_PLACE in text and "migrations" in text for text in new), new
    assert _of_step_13(gate["upstream_debt"]) == [], gate["upstream_debt"]  # the baseline's file is right by the baseline's schema

    commit_all(host, "a stricter schema")
    _edit_json(schema_file, lambda schema: schema["required"].remove("migrations"))  # the head takes it back
    gate = _gate(capsys, host, "14")
    assert _of_step_13(gate["blocking"]) == [], gate["blocking"]  # the head's file is right by the head's schema
    assert _of_step_13(gate["upstream_debt"]) == [], gate["upstream_debt"]


def test_an_extension_removed_in_the_head_leaves_the_plain_example(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, plain: Path,
) -> None:
    host = _extension_host(tmp_path / "host")
    commit_all(host, "the extension")
    shutil.rmtree(host / FOLDER)  # the folder goes and the entry stays: the entry has neither file
    gate = _gate(capsys, host, "14")
    assert _has_each(
        _texts(_of_step_13(gate["blocking"])), "Extension 'ext-01-database' has no schema", "Extension 'ext-01-database' has no file",
    ), gate["blocking"]
    assert _of_step_13(gate["upstream_debt"]) == []

    for place in RESTORED:  # the manifest entry and the lock that accepted it go with the folder
        shutil.copy(EXAMPLE_HOST / place, host / place)
    attest(host)
    assert get_shared_registry(str(ROOT), str(host / "spec")) is get_shared_registry(str(ROOT))
    assert _texts(_added(_findings(capsys, host), _findings(capsys, plain))) == []
    for step in ("13", "14"):
        gate = _gate(capsys, host, step)
        assert _of_step_13(gate["blocking"]) == [] and _of_step_13(gate["upstream_debt"]) == [], step


def test_an_extension_added_on_a_branch_passes_the_merge_gate_as_a_branch_without_it(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    control = step_gate_host(tmp_path / "control")
    start_branch(control)
    git(control, "commit", "-q", "--allow-empty", "-m", "nothing")
    host = step_gate_host(tmp_path / "host", attested=False)
    start_branch(host)
    _add_extension(host)
    commit_all(host, "the extension")

    def merge(repository: Path) -> dict[str, Any]:
        return _report(capsys, repository, "--merge", "--base-ref", "main")

    control_report, report = merge(control), merge(host)
    assert _texts(_added(report["errors"], control_report["errors"])) == []
    assert report["status"] == control_report["status"]

    apply_delta(host, "data_breaks_schema", folder=DELTAS)
    commit_all(host, "the broken data file")
    added = _added(merge(host)["errors"], control_report["errors"])
    assert [(finding["code"], finding.get("owner")) for finding in added] == [("E520", STEP_13)], added
    assert "tables/0/columns" in added[0]["message"]


# --- X1: the canonical commands on an extension file ----------------------------------------------------------------


def test_a_canonical_ref_the_data_file_does_not_list_is_e210_and_the_command_of_its_text_lists_the_id(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, plain: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _extension_host(tmp_path / "host", "ref_not_listed")
    _code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--json")  # the text as printed: its path is run below
    added = _added(json.loads(out)["errors"], _findings(capsys, plain))
    assert [finding["code"] for finding in added] == ["E210"], added
    text = added[0]["message"]
    assert DATA_NAME in text and TERM in text, text
    named = re.search(r"run '([^']+)'", text)
    assert named is not None, text
    words = shlex.split(named.group(1))
    assert words[0].endswith("run_specdev.sh") and words[1] == "canonical-autofix" and "--write" in words, words
    assert (ROOT / words[2]).resolve() == (host / "spec").resolve(), words  # S1: the folder of the text is the spec folder, not <spec>/extensions
    # As written, but for --write: the wrapper is `specdev`, and the path of the text is relative to the toolkit's folder.
    monkeypatch.chdir(ROOT)
    before = (host / FOLDER / DATA_NAME).read_text(encoding="utf-8")
    code, out, err = run_split(capsys, *("--dry-run" if word == "--write" else word for word in words[1:]))
    assert code == 0, out + err
    assert "schema_not_found" not in out + err
    assert [line for line in out.splitlines() if TERM in line and "add" in line] != [], out
    assert (host / FOLDER / DATA_NAME).read_text(encoding="utf-8") == before
    # And as written, with --write: the finding is gone and nothing takes its place.
    code, out, err = run_split(capsys, *words[1:])
    assert code == 0, out + err
    assert (host / FOLDER / DATA_NAME).read_text(encoding="utf-8") != before
    assert _texts(_added(_findings(capsys, host), _findings(capsys, plain))) == []


def _said_of_the_file(output: str) -> list[str]:
    """The lines of a command's output that name the data file, each with the indented lines below it (the changes of a file)."""
    kept, taking = [], False
    for line in output.splitlines():
        if DATA_NAME in line:
            taking = True
            kept.append(line)
        elif taking and line.startswith("  "):
            kept.append(line)
        else:
            taking = False
    return sorted(kept)


@pytest.mark.parametrize("command", [("canonical-autofix", "--dry-run"), ("validate-all",), ("canonical-integrity",)], ids=lambda words: words[0])
def test_a_folder_command_on_the_extensions_folder_with_the_spec_folder_named_says_of_the_file_what_it_says_on_the_spec_folder(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, command: tuple[str, ...],
) -> None:
    """S1 (was X1, which asked the same with no ``--spec-root``: that is now the test of the way out below).

    The data file carries a ref it does not list and a value its schema refuses, so each command has something to say.
    The flag and the folder handed differ here: a handler that drops the flag fails this.
    """
    host = _extension_host(tmp_path / "host", "ref_not_listed", "data_breaks_schema")
    name, *flags = command

    def said(folder: Path) -> list[str]:
        _code, out, err = run_split(capsys, name, str(folder), *_flags(host), *flags)
        return _said_of_the_file(out + err)

    on_spec = said(host / "spec")
    assert [line for line in on_spec if TERM in line] != [], on_spec
    assert "schema_not_found" not in "\n".join(on_spec) and "schema_uri_mismatch" not in "\n".join(on_spec)
    assert said(host / FOLDER) == on_spec


def _of_the_data_file(findings: list[dict[str, Any]]) -> list[tuple[str, str | None, str]]:
    return sorted((finding["code"], finding.get("owner"), finding["message"]) for finding in findings if DATA_NAME in finding["message"])


def test_spec_check_on_the_extensions_folder_with_the_spec_folder_named_says_of_the_file_what_it_says_on_the_spec_folder(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    """S1: the same for ``spec-check``, by code, owner and text; and a refused schema file has its own finding there too."""
    host = _extension_host(tmp_path / "host", "ref_not_listed", "data_breaks_schema")

    def findings(folder: Path) -> list[dict[str, Any]]:
        _code, out, _err = run_split(capsys, "spec-check", str(folder), *_flags(host), "--json")
        return json.loads(out)["errors"]

    on_spec = _of_the_data_file(findings(host / "spec"))
    assert {code for code, _owner, _text in on_spec} == {"E210", "E520"}, on_spec
    assert [text for _code, _owner, text in on_spec if "'x' is not of type 'array'" in text] != [], on_spec
    assert _of_the_data_file(findings(host / FOLDER)) == on_spec

    _edit_json(host / FOLDER / SCHEMA_NAME, lambda schema: schema.update({"$schema": DRAFT_07}))

    def refused(folder: Path) -> list[tuple[str, str | None, str]]:
        return sorted(
            (finding["code"], finding.get("owner"), finding["message"][finding["message"].index("Extension schema"):])
            for finding in findings(folder) if "Extension schema" in finding["message"]
        )

    on_spec = refused(host / "spec")
    assert len(on_spec) == 1 and on_spec[0][:2] == ("E520", STEP_13) and SCHEMA_PLACE in on_spec[0][2] and DRAFT_07 in on_spec[0][2], on_spec
    assert refused(host / FOLDER) == on_spec


def _strings(value: Any) -> list[str]:
    """Every string anywhere in the JSON value *value*."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    return [text for item in value for text in _strings(item)] if isinstance(value, list) else []


WAY_OUT_COMMANDS = [("spec-check",), ("validate-all",), ("canonical-integrity",), ("canonical-autofix", "--dry-run")]


def test_a_folder_command_on_the_extensions_folder_with_no_spec_root_tells_the_data_file_the_way_out(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    """S1 (H3): the folder handed is the spec folder the command was told, so the data file lies at its top: Y1's E520.

    Its text names the way out (the spec folder, ``--spec-root``); the four commands say the same of the file and none
    says OK.  Named the spec folder, none of them has that finding.
    """
    host = _extension_host(tmp_path / "host")
    told = {}
    for name, *flags in WAY_OUT_COMMANDS:
        code, out, _err = run_split(capsys, name, str(host / FOLDER), "--repo-root", str(ROOT), *flags, "--json")
        texts = [text[text.index("schema_uri_mismatch"):] for text in _strings(json.loads(out)) if "schema_uri_mismatch" in text]
        assert code == 1 and texts != [], (name, out)
        told[name] = set(texts)
        _code, text, err = run_split(capsys, name, str(host / FOLDER), "--repo-root", str(ROOT), *flags)
        assert _code == 1 and [line for line in (text + err).splitlines() if line.strip() == "OK" or line.startswith("OK ")] == [], (name, text + err)
        _code, out, _err = run_split(capsys, name, str(host / FOLDER), *_flags(host), *flags, "--json")
        assert [text for text in _strings(json.loads(out)) if "schema_uri_mismatch" in text] == [], (name, out)
    (text,) = set.union(*told.values())  # one text, the same from each command
    assert all(texts == {text} for texts in told.values()), told
    assert DATA_NAME in text and URI in text and DATA_PLACE in text and "--spec-root" in text, text


def test_spec_quality_lint_reads_a_step_named_file_of_the_extensions_folder_by_the_spec_folder_it_is_told(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    """S1 (H1), the handler: named the spec folder, ``extensions/04_fr_list.json`` is a file of the folder (Z2a); with none, a step file of the folder handed."""
    host = _extension_host(tmp_path / "host")
    copy = host / FOLDER / "04_fr_list.json"
    shutil.copy(host / "spec" / "04_fr_list.json", copy)
    _edit_json(copy, lambda document: document.update(functional_requirements=[]))

    def empty(*roots: str) -> tuple[int, list[str]]:
        code, out, err = run_split(capsys, "spec-quality-lint", str(host / FOLDER), "--repo-root", str(ROOT), *roots)
        return code, [line for line in (out + err).splitlines() if "empty critical array" in line]

    assert empty("--spec-root", str(host / "spec"), "--git-root", str(host)) == (0, [])
    code, lines = empty()
    assert code == 1 and len(lines) == 1 and lines[0].startswith("E520") and "04_fr_list.json" in lines[0], lines


# --- zero change without the folder ---------------------------------------------------------------------------------


def test_with_the_folder_removed_the_output_is_byte_equal_to_the_plain_examples(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    """One host, one process, three states: the plain example, the example with the extension, the example with the folder removed.

    The same folder and the same commit each time, so nothing of the output is rewritten before it is compared:
    exit code, stdout and stderr of the full check and of the step-13 gate, as text and as JSON.
    """
    host = step_gate_host(tmp_path / "host")
    toolkit_registry = get_shared_registry(str(ROOT))
    assert get_shared_registry(str(ROOT), str(host / "spec")) is toolkit_registry

    def run(*flags: str) -> tuple[int, str, str]:
        return run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), *flags)

    plain_runs = {flags: run(*flags) for flags in ((), ("--json",), ("--step", "13"), ("--step", "13", "--json"))}

    shutil.copytree(EXTENSION / FOLDER, host / FOLDER)
    apply_delta(host, "declare_extension", folder=DELTAS)
    attest(host)
    assert get_shared_registry(str(ROOT), str(host / "spec")) is not toolkit_registry
    assert run() == plain_runs[()] and run("--step", "13") == plain_runs[("--step", "13")]

    shutil.rmtree(host / FOLDER)
    for place in RESTORED:  # the manifest entry and the lock that accepted it go with the folder
        shutil.copy(EXAMPLE_HOST / place, host / place)
    attest(host)
    assert get_shared_registry(str(ROOT), str(host / "spec")) is toolkit_registry
    for flags, expected in plain_runs.items():
        assert run(*flags) == expected, flags


# --- Y1: an extension schema judges the data file of its name and no other file ------------------------------------

MISPLACED = {
    "a file at the top of the spec": "notes.json",
    "the 1.1.1 place of the data file": DATA_NAME,
    "a file of the folder that is not named for the extension": "extensions/notes.json",
    "a file under impl_context": "impl_context/x.json",
}


def _stray(host: Path, relative: str, uri: str) -> Path:
    """A file at *relative* in the spec of *host* that names the schema *uri* and has nothing of the example schema's shape."""
    path = _spec(host) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"$schema": uri, "tables": "not a list"}, indent=2) + "\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("case", sorted(MISPLACED))
def test_a_file_that_names_an_extension_schema_and_is_not_its_data_file_is_e520_and_no_host_schema_judges_it(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, plain: Path, case: str,
) -> None:
    """The control is the same file naming ``vc:no-such``: what is not about the schema is the same for both."""
    relative = MISPLACED[case]
    host = _extension_host(tmp_path / "host")
    plain_findings = _findings(capsys, plain)
    assert _texts(_added(_findings(capsys, host), plain_findings)) == []
    path = _stray(host, relative, "vc:no-such")
    control = [finding for finding in _added(_findings(capsys, host), plain_findings) if "vc:no-such" not in finding["message"]]
    _stray(host, relative, URI)
    by_run = {}
    for spec_root in (True, False):
        added = by_run[spec_root] = _added(_findings(capsys, host, spec_root=spec_root), plain_findings)
        named = [finding for finding in added if URI in finding["message"]]
        assert named != [], _texts(added)
        for finding in named:
            text = finding["message"]
            assert finding["code"] == "E520" and f"spec/{relative}" in text and DATA_PLACE in text, finding
            assert "tools/schema_registry.json" not in text and "--repo-root" not in text and "write that file" not in text.lower(), text
            assert not relative.startswith("extensions/") or finding.get("owner") == STEP_13, finding
        assert not any(word in text for text in _texts(added) for word in ("datastores", "not a list")), _texts(added)
        others = [finding for finding in added if URI not in finding["message"]]
        assert sorted(map(_key, others), key=str) == sorted(map(_key, control), key=str), (_texts(others), _texts(control))
    assert _whole(by_run[False]) == _whole(by_run[True])
    assert path.is_file()


def test_a_data_file_left_at_its_1_1_1_place_is_told_where_it_belongs_and_the_entry_has_no_file(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, plain: Path,
) -> None:
    """What a migrating host has: ``spec/ext_01_database.json``, valid for its schema, and nothing in ``extensions/`` but the schema."""
    host = _extension_host(tmp_path / "host")
    plain_findings = _findings(capsys, plain)
    shutil.move(str(host / FOLDER / DATA_NAME), str(host / "spec" / DATA_NAME))
    added = _added(_findings(capsys, host), plain_findings)
    texts = _texts(added)
    moved = [text for text in texts if f"spec/{DATA_NAME}" in text and URI in text]
    assert moved != [] and all(DATA_PLACE in text and "write that file" not in text.lower() for text in moved), texts
    assert not any("--spec-root" in text for text in moved), moved  # S1: that sentence is for a folder called extensions only
    no_file = [finding for finding in added if "ext-01-database" in finding["message"] and "has no file" in finding["message"]]
    assert [(finding["code"], finding.get("owner")) for finding in no_file] == [("E520", STEP_13)], texts
    assert DATA_PLACE in no_file[0]["message"]
    assert not any("schema_not_found" in text or "tools/schema_registry.json" in text for text in texts), texts


# --- Y2: validate on a schema file of the folder ---------------------------------------------------------------------


def _validate(capsys: pytest.CaptureFixture[str], path: Path, *flags: str) -> tuple[int, list[dict[str, Any]], str]:
    """``specdev validate <path> <flags>``: the exit code, the findings (``--json``) and the text a person reads."""
    code, out, _err = run_split(capsys, "validate", str(path), *flags, "--json")
    _code, text, err = run_split(capsys, "validate", str(path), *flags)
    assert _code == code
    return code, json.loads(out)["errors"], text + err


@pytest.mark.parametrize("layout", ["the three root flags", "only --repo-root"])
def test_validate_on_the_schema_file_of_an_extension_answers_as_the_folder_check_does(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, layout: str,
) -> None:
    host = _extension_host(tmp_path / "host")
    schema_file = host / FOLDER / SCHEMA_NAME
    flags = _flags(host) if layout == "the three root flags" else ["--repo-root", str(ROOT)]
    code, findings, text = _validate(capsys, schema_file, *flags)
    assert (code, findings) == (0, []), text
    assert "schema_not_found" not in text and "tools/schema_registry.json" not in text, text
    _edit_json(schema_file, lambda schema: schema.update({"$id": "vc:ext-01-databse"}))
    of_the_folder = [finding["message"] for finding in _findings(capsys, host) if SCHEMA_PLACE in finding["message"] and "Extension schema" in finding["message"]]
    assert len(of_the_folder) == 1, of_the_folder
    code, findings, text = _validate(capsys, schema_file, *flags)
    assert code == 1 and [(finding["code"], finding.get("owner")) for finding in findings] == [("E520", STEP_13)], text
    assert of_the_folder[0].endswith(findings[0]["message"]) and "vc:ext-01-databse" in findings[0]["message"], (of_the_folder, findings)
    assert "schema_not_found" not in text and "tools/schema_registry.json" not in text, text


# --- Z2(a): where the spec folder is known, the place of a file decides ---------------------------------------------

GATE_PARTS = ("blocking", "waiting", "own_warnings", "new_upstream_warnings", "upstream_debt")
NOTE = '{"note": 1}'


def _about(findings: list[dict[str, Any]], words: str) -> list[dict[str, Any]]:
    """The findings that name *words* in any of their keys."""
    return [finding for finding in findings if words in json.dumps(finding)]


def _renamed(findings: list[dict[str, Any]], old: str, new: str) -> list[str]:
    """Each finding whole, with *old* written *new*: what is said of two files, compared."""
    return sorted(json.dumps(finding, sort_keys=True).replace(old, new) for finding in findings)


def test_a_file_of_the_folder_named_like_a_step_file_is_step_13s_as_a_file_of_any_other_name_is(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Z2(a), G3: ``extensions/04_notes.json`` gets what ``extensions/notes.json`` gets, and steps 04 and 05 do not see it."""
    host = _extension_host(tmp_path / "host")
    before = {step: _gate(capsys, host, step)["result"] for step in ("04", "05")}
    control = host / FOLDER / "notes.json"
    control.write_text(NOTE, encoding="utf-8")
    expected = _renamed(_about(_findings(capsys, host), "notes.json"), "notes.json", "<the file>")
    control.unlink()
    (host / FOLDER / "04_notes.json").write_text(NOTE, encoding="utf-8")
    for spec_root in (True, False):
        about = _about(_findings(capsys, host, spec_root=spec_root), "04_notes.json")
        assert _renamed(about, "04_notes.json", "<the file>") == expected, spec_root
        of_a_step = [finding for finding in about if str(finding.get("owner")).startswith("step:")]
        assert {finding["owner"] for finding in of_a_step} == {STEP_13}, about
        assert [finding for finding in of_a_step if "no entry" in finding["message"] and "declares it" in finding["message"]] != [], about
        assert [finding for finding in of_a_step if "missing_schema_uri" in finding["message"]] != [], about
    for step in ("04", "05"):
        gate = _gate(capsys, host, step)
        seen = [finding for part in GATE_PARTS for finding in gate[part] if "04_notes.json" in json.dumps(finding)]
        assert seen == [] and gate["result"] == before[step], (step, seen)
    assert _about(_gate(capsys, host, "13")["blocking"], "04_notes.json") != []
    monkeypatch.chdir(host)
    assert _report(capsys, host, "--paths", f"{FOLDER}/04_notes.json")["step_gate"]["steps"] == ["13"]


def test_every_finding_about_a_file_of_the_folder_is_step_13s(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """Z2(a) to the letter: "its findings are step 13's (the folder finding and any other)"; no check reads the name as a step file's."""
    host = _extension_host(tmp_path / "host")
    (host / FOLDER / "04_notes.json").write_text('{"note": 1, "source_ref": "no-such-node"}', encoding="utf-8")
    about = _about(_findings(capsys, host), "04_notes.json")
    assert about != [] and {finding.get("owner") for finding in about} == {STEP_13}, about
    assert _about(about, "no-such-node") != [], about  # a check that names its file and leaves the owner to the place of the file


def test_a_folder_called_extensions_below_the_spec_folder_is_not_the_extensions_folder(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, plain: Path,
) -> None:
    """Z2(a), G4: on the plain example ``common/extensions/x.json`` gets what ``common/other/x.json`` gets (the answer of 673b5fa for both)."""

    def said(folder: str) -> tuple[list[str], int, str, list[str]]:
        place = plain / "spec" / "common" / folder / "x.json"
        place.parent.mkdir()
        place.write_text('{"a": 1}', encoding="utf-8")
        about = _about(_findings(capsys, plain), f"common/{folder}/x.json")
        code, _text = _output(capsys, plain, "--step", "13")
        gate = _report(capsys, plain, "--step", "13")["step_gate"]
        shutil.rmtree(place.parent)
        old, new = f"common/{folder}/", "common/<folder>/"
        return _renamed(about, old, new), code, gate["result"], _renamed([finding for part in GATE_PARTS for finding in gate[part]], old, new)

    other, here = said("other"), said("extensions")
    assert here == other
    assert here[0] != [] and here[1] == 0  # the file has a finding, and step 13 is not blocked by it
    assert [text for text in here[0] if "missing_schema_uri" in text] != [] and not any(STEP_13 in text for text in here[0]), here[0]


def test_the_name_of_the_data_file_in_a_folder_called_extensions_below_the_spec_folder_is_a_stray_file(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Z2(a), G4: ``sub/extensions/ext_01_database.json`` with its schema beside it gets what the same two files get in ``sub/other``."""
    host = _extension_host(tmp_path / "host")

    def said(folder: str) -> list[dict[str, Any]]:
        shutil.rmtree(host / "spec" / "sub", ignore_errors=True)
        shutil.copytree(EXTENSION / FOLDER, host / "spec" / "sub" / folder)
        return _about(_findings(capsys, host), f"sub/{folder}/")

    other, here = said("other"), said("extensions")
    assert _renamed(here, "sub/extensions/", "sub/<folder>/") == _renamed(other, "sub/other/", "sub/<folder>/")
    named = [finding for finding in here if URI in finding["message"]]
    assert named != [], here
    for finding in named:  # Y1, and not step 13's
        assert finding["code"] == "E520" and DATA_PLACE in finding["message"] and finding.get("owner") != STEP_13, finding
    monkeypatch.chdir(host)
    assert _report(capsys, host, "--paths", f"spec/sub/extensions/{DATA_NAME}")["step_gate"]["steps"] == []


# --- Z2(b): a spec folder that is itself called extensions ----------------------------------------------------------

NAMED = "extensions"


def _named_host(destination: Path, name: str, *deltas: str, extension: bool = False) -> Path:
    """The worked example as a git repository whose spec folder is called *name* (its one commit), with a ``00_index.json`` above it.

    With *extension* the extension is overlaid and declared and *deltas* are applied, uncommitted; every link is accepted.
    """
    shutil.copytree(EXAMPLE_HOST, destination)
    shutil.move(str(destination / "spec"), str(destination / name))
    (destination / "00_index.json").write_text("{}\n", encoding="utf-8")  # S6 (H1, H2): a numbered JSON file above the spec folder
    git(destination, "init", "-q", "-b", "main")
    commit_all(destination, "worked example")
    if extension:
        shutil.copytree(EXTENSION / FOLDER, destination / name / "extensions")
        for delta in ("declare_extension", *deltas):
            apply_delta(destination, delta, name, folder=DELTAS)
    attest(destination, name)
    return destination


def _named_flags(host: Path, name: str, *, spec_root: bool = True) -> list[str]:
    named = ["--spec-root", str(host / name)] if spec_root else []
    return ["--repo-root", str(ROOT), *named, "--git-root", str(host)]


def _named_report(
    capsys: pytest.CaptureFixture[str], host: Path, name: str, *flags: str, spec_root: bool = True,
) -> tuple[int, dict[str, Any]]:
    code, out, _err = run_split(capsys, "spec-check", str(host / name), *_named_flags(host, name, spec_root=spec_root), *flags, "--json")
    return code, json.loads(out)


@pytest.mark.parametrize("spec_root", [True, False], ids=["--spec-root", "no --spec-root"])
def test_a_spec_folder_called_extensions_holds_an_extension_as_any_spec_folder_does(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, spec_root: bool,
) -> None:
    """Z2(b): the extension overlaid adds no finding and removes none against the plain example there; a broken data file blocks step 13."""
    plain = _named_host(tmp_path / "plain", NAMED)
    host = _named_host(tmp_path / "host", NAMED, extension=True)
    _code, plain_report = _named_report(capsys, plain, NAMED, spec_root=spec_root)
    _code, report = _named_report(capsys, host, NAMED, spec_root=spec_root)
    assert _texts(_added(report["errors"], plain_report["errors"])) == []
    assert _renamed(report["errors"], str(host), "<host>") == _renamed(plain_report["errors"], str(plain), "<host>")
    plain_code, plain_gate = _named_report(capsys, plain, NAMED, "--step", "13", spec_root=spec_root)
    code, gate = _named_report(capsys, host, NAMED, "--step", "13", spec_root=spec_root)
    assert (code, gate["step_gate"]["result"], gate["step_gate"]["blocking"]) == (plain_code, plain_gate["step_gate"]["result"], [])
    apply_delta(host, "data_breaks_schema", NAMED, folder=DELTAS)
    code, broken = _named_report(capsys, host, NAMED, "--step", "13", spec_root=spec_root)
    assert (code, broken["step_gate"]["result"]) == (1, "blocked")
    assert [_key(finding) for finding in broken["step_gate"]["blocking"]] == [("E520", None, STEP_13)]
    assert "tables/0/columns: 'x' is not of type 'array'" in broken["step_gate"]["blocking"][0]["message"]


def test_in_a_spec_folder_called_extensions_validate_answers_on_the_schema_file_as_in_any_spec_folder(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    """Z2(b): Y2 there."""
    host = _named_host(tmp_path / "host", NAMED, extension=True)
    schema_file = host / NAMED / "extensions" / SCHEMA_NAME
    code, findings, text = _validate(capsys, schema_file, *_named_flags(host, NAMED))
    assert (code, findings) == (0, []), text
    _edit_json(schema_file, lambda schema: schema.update({"$id": "vc:ext-01-databse"}))
    code, findings, text = _validate(capsys, schema_file, *_named_flags(host, NAMED))
    assert code == 1 and [(finding["code"], finding.get("owner")) for finding in findings] == [("E520", STEP_13)], text
    assert SCHEMA_PLACE in findings[0]["message"] and "vc:ext-01-databse" in findings[0]["message"], findings
    assert "schema_not_found" not in text and "tools/schema_registry.json" not in text, text


NAMED_FOLDER_COMMANDS = [("validate-all",), ("canonical-integrity",), ("canonical-autofix", "--dry-run"), ("spec-check",), ("spec-quality-lint",)]
ZERO_CHANGE_ROOTS = ["the three root flags", "only --repo-root", "no flag, from the toolkit root"]


def _roots(monkeypatch: pytest.MonkeyPatch, host: Path, name: str, roots: str) -> list[str]:
    """The root flags of the row *roots* for the spec folder *name* of *host*; the current folder is the toolkit's where the row has no flag."""
    monkeypatch.chdir(ROOT if roots == "no flag, from the toolkit root" else host)
    return {"the three root flags": _named_flags(host, name), "only --repo-root": ["--repo-root", str(ROOT)]}.get(roots, [])


@pytest.mark.parametrize("roots", ZERO_CHANGE_ROOTS)
def test_in_a_spec_folder_called_extensions_the_commands_accept_the_right_data_file_and_read_it(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, roots: str,
) -> None:
    """Z2(b), S1 (H1): ``validate`` and the folder commands say nothing against the data file; broken, each that reads it has something to say of it.

    A numbered JSON file lies above the spec folder (``_named_host``): nothing above the folder handed is read.
    """
    plain = _named_host(tmp_path / "plain", NAMED)
    host = _named_host(tmp_path / "host", NAMED, extension=True)
    data_file = host / NAMED / "extensions" / DATA_NAME

    def run(of: Path, command: tuple[str, ...]) -> tuple[int, str]:
        code, out, err = run_split(capsys, command[0], str(of / NAMED), *_roots(monkeypatch, of, NAMED, roots), *command[1:])
        return code, out + err

    code, findings, text = _validate(capsys, data_file, *_roots(monkeypatch, host, NAMED, roots))
    assert (code, findings) == (0, []), text
    for command in NAMED_FOLDER_COMMANDS:
        plain_code, _text = run(plain, command)
        code, text = run(host, command)
        assert code == plain_code, (command, text)
        against = [line for line in text.splitlines() if DATA_NAME in line and (re.search(r"\b[EW]\d{3}\b", line) or "UNRESOLVED_INPUT" in line)]
        assert against == [], (command, against)
    for delta in ("ref_not_listed", "data_breaks_schema"):
        apply_delta(host, delta, NAMED, folder=DELTAS)
    code, findings, text = _validate(capsys, data_file, *_roots(monkeypatch, host, NAMED, roots))
    assert code == 1 and [finding for finding in findings if "'x' is not of type 'array'" in finding["message"]] != [], text
    for command in NAMED_FOLDER_COMMANDS[:3]:
        _code, text = run(host, command)
        said = _said_of_the_file(text)
        assert [line for line in said if TERM in line] != [], (command, said)
        assert "schema_not_found" not in "\n".join(said) and "move this file" not in "\n".join(said), (command, said)
    _code, out, _err = run_split(capsys, "spec-check", str(host / NAMED), *_roots(monkeypatch, host, NAMED, roots), "--json")
    of_the_file = _of_the_data_file(json.loads(out)["errors"])
    assert {code for code, _owner, _text in of_the_file} == {"E210", "E520"}, of_the_file
    assert not any("move this file" in text or "schema_not_found" in text for _code, _owner, text in of_the_file), of_the_file


@pytest.mark.parametrize("roots", ZERO_CHANGE_ROOTS)
def test_spec_quality_lint_on_a_spec_folder_called_extensions_finds_the_empty_critical_array_of_a_step_file(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, roots: str,
) -> None:
    """S1 (H1), the review's host: a numbered JSON file lies above the spec folder; the quality checks of a step file are not lost."""
    host = _named_host(tmp_path / "host", NAMED)
    _edit_json(host / NAMED / "04_fr_list.json", lambda document: document.update(functional_requirements=[]))
    code, out, err = run_split(capsys, "spec-quality-lint", str(host / NAMED), *_roots(monkeypatch, host, NAMED, roots))
    lines = [line for line in (out + err).splitlines() if "empty critical array 'functional_requirements'" in line]
    assert code == 1 and len(lines) == 1 and lines[0].startswith("E520") and "04_fr_list.json" in lines[0], out + err


@pytest.mark.xfail(strict=True, reason=(
    "Z2(b) names `json patch --id` on the right data file.  Until piece B an item of an extension file is no node, so no "
    "id names one; what the id-keyed write calls is tested instead (test_host_schemas: check_edit with the spec folder). "
    "Which id did the line mean?"
))
def test_in_a_spec_folder_called_extensions_an_item_of_the_data_file_is_written_by_its_id(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    host = _named_host(tmp_path / "host", NAMED, extension=True)
    code, out, err = run_split(capsys, "json", "patch", "--id", "tbl-reset-token", ".name", '"reset_tokens"', *_named_flags(host, NAMED))
    assert code == 0, out + err
    assert json.loads((host / NAMED / "extensions" / DATA_NAME).read_text(encoding="utf-8"))["tables"][0]["name"] == "reset_tokens"


ZERO_CHANGE_COMMANDS = [
    ("spec-check",), ("spec-check", "--step", "13"), ("validate-all",), ("canonical-integrity",), ("canonical-autofix", "--dry-run"),
    ("spec-quality-lint",),
]


def _folder_named(text: str, host: Path, name: str) -> str:
    """*text* with the spec folder of *host* written ``<spec>``: by its path, by its path from the toolkit folder, and by its own name before a slash."""
    for place, word in ((host / name, "<spec>"), (host, "<host>")):
        text = text.replace(str(place), word).replace(os.path.relpath(place, ROOT), word)
    return re.sub(rf"(?<![\w./<>-]){re.escape(name)}/", "<spec>/", text)


def _answers(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, host: Path, name: str, roots: str,
) -> dict[tuple[str, ...], tuple[int, Any]]:
    """Each command of ``ZERO_CHANGE_COMMANDS`` on the spec folder *name* of *host*: its exit code and its ``--json`` answer, the folder's name replaced."""
    flags = _roots(monkeypatch, host, name, roots)
    answers = {}
    for command in ZERO_CHANGE_COMMANDS:
        code, out, _err = run_split(capsys, command[0], str(host / name), *flags, *command[1:], "--json")
        answer = json.loads(_folder_named(out, host, name))
        if isinstance(answer, dict) and isinstance(answer.get("step_gate"), dict):
            answer["step_gate"]["baseline"].pop("commit", None)  # each copy has its own commit
        answers[command] = (code, answer)
    return answers


README = "extensions/README.md"
ZERO_CHANGE_HOSTS = {"the plain example": None, "with a file of no step at its top": "notes.json", "with a README in an empty extensions folder": README}


@pytest.mark.parametrize("extra", sorted(ZERO_CHANGE_HOSTS))
@pytest.mark.parametrize("roots", ZERO_CHANGE_ROOTS)
def test_the_plain_example_in_a_folder_called_extensions_says_what_it_says_in_a_folder_called_specs(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, roots: str, extra: str,
) -> None:
    """Z2(b), S6, zero change: no extension inside; the same findings by code, node, owner and text once the folder's name is replaced.

    Both hosts have a numbered JSON file above the spec folder (``_named_host``).  The second row is not the pack's: one
    JSON file that is no step file at the top of the spec folder (a host may have one).  The README of the third row is
    in the folder called ``extensions`` only: it must change nothing against the folder called ``specs`` that has none.
    """
    added = ZERO_CHANGE_HOSTS[extra]
    answers = {}
    for name in (NAMED, "specs"):
        host = _named_host(tmp_path / f"host of {name}", name)  # the host folder is not called as its spec folder is
        if added and (name == NAMED or added != README):
            (host / name / added).parent.mkdir(exist_ok=True)
            (host / name / added).write_text('{"a": 1}' if added.endswith(".json") else "notes", encoding="utf-8")
        answers[name] = _answers(capsys, monkeypatch, host, name, roots)
    for command in ZERO_CHANGE_COMMANDS:
        assert answers[NAMED][command] == answers["specs"][command], command
    assert STEP_13 not in json.dumps(answers[NAMED][("spec-check",)]) or added == "notes.json"  # the file at the top is no step's
    if added is None and roots == "only --repo-root":
        assert answers[NAMED][("validate-all",)][0] == 0  # H2: the review's host says OK, as at 673b5fa


# --- Z3: validate-all on the extensions folder, no --spec-root ------------------------------------------------------


def _validate_all_lines(capsys: pytest.CaptureFixture[str], folder: Path, words: str, *roots: str) -> list[str]:
    """The E520 lines of ``validate-all <folder>`` that hold *words*, each from *words* on (what is before them names the file that was read)."""
    _code, out, err = run_split(capsys, "validate-all", str(folder), "--repo-root", str(ROOT), *roots)
    return sorted(line[line.index(words):] for line in (out + err).splitlines() if line.startswith("E520") and words in line)


def test_validate_all_on_the_extensions_folder_says_of_a_spec_with_no_manifest_what_the_spec_folder_it_is_told_says(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    """S1 (was Z3, which asked the same with no ``--spec-root``): named the spec folder, each file has the E520 it has on the spec folder.

    With none named the folder handed is the spec folder: nothing there is undeclared, and the data file is told the way out.
    """
    host = _extension_host(tmp_path / "host", declared=False)
    (host / "spec" / MANIFEST).unlink()
    named = ("--spec-root", str(host / "spec"))
    on_spec = _validate_all_lines(capsys, host / "spec", "extensions/")
    undeclared = [line for line in on_spec if f"the spec has no {MANIFEST} to declare it" in line]
    assert _has_each(undeclared, SCHEMA_PLACE, DATA_PLACE), on_spec
    on_folder = _validate_all_lines(capsys, host / FOLDER, "extensions/", *named)
    assert [line for line in on_folder if "to declare it" in line] == undeclared, on_folder
    assert _validate_all_lines(capsys, host / FOLDER, "to declare it") == []
    told = _validate_all_lines(capsys, host / FOLDER, "schema_uri_mismatch")
    assert len(told) == 2 and all("--spec-root" in line for line in told), told
    for roots in ((), named):
        code, _out, _err = run_split(capsys, "validate-all", str(host / FOLDER), "--repo-root", str(ROOT), *roots)
        assert code == 1, roots


def test_validate_all_on_the_extensions_folder_gives_the_own_finding_of_a_refused_schema_when_the_spec_folder_is_named(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    """S1 (was Z3): with no ``--spec-root`` the schema file lies at the top of the folder handed, where it is no extension schema."""
    host = _extension_host(tmp_path / "host")
    _edit_json(host / FOLDER / SCHEMA_NAME, lambda schema: schema.update({"$schema": DRAFT_07}))
    on_spec = _validate_all_lines(capsys, host / "spec", "Extension schema")
    assert len(on_spec) == 1 and SCHEMA_PLACE in on_spec[0] and DRAFT_07 in on_spec[0], on_spec
    assert _validate_all_lines(capsys, host / FOLDER, "Extension schema", "--spec-root", str(host / "spec")) == on_spec
    assert _validate_all_lines(capsys, host / FOLDER, "Extension schema") == []


# --- S2 (H5): one file, one answer ----------------------------------------------------------------------------------


def _validated(capsys: pytest.CaptureFixture[str], host: Path, path: Path) -> tuple[int, list[tuple[str, str | None, str]]]:
    """``validate <path>`` with the three root flags: the exit code and each finding with the path as typed written ``<file>``."""
    code, findings, _text = _validate(capsys, path, *_flags(host))
    return code, sorted((finding["code"], finding.get("owner"), finding["message"].replace(str(path), "<file>")) for finding in findings)


def test_validate_judges_the_data_file_reached_through_a_link_to_the_extensions_folder_as_by_its_plain_path(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    host = _extension_host(tmp_path / "host", "data_breaks_schema")
    (tmp_path / "to_the_folder").symlink_to(host / FOLDER, target_is_directory=True)
    plain = _validated(capsys, host, host / FOLDER / DATA_NAME)
    assert plain[0] == 1 and [text for _code, _owner, text in plain[1] if "tables/0/columns: 'x' is not of type 'array'" in text] != [], plain
    assert not any("move this file" in text for _code, _owner, text in plain[1])
    assert _validated(capsys, host, tmp_path / "to_the_folder" / DATA_NAME) == plain


def test_validate_judges_the_data_file_typed_in_another_case_as_by_its_plain_path_where_the_file_system_ignores_case(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    host = _extension_host(tmp_path / "host", "data_breaks_schema")
    typed = host / "spec" / "Extensions" / DATA_NAME
    if not typed.is_file():
        pytest.skip("this file system keeps case: spec/Extensions is another folder")
    plain = _validated(capsys, host, host / FOLDER / DATA_NAME)
    assert plain[0] == 1 and _validated(capsys, host, typed) == plain


# --- S4 (H7): step 13 owns the JSON files of the folder -------------------------------------------------------------


def test_a_readme_alone_in_the_extensions_folder_changes_nothing_and_one_json_file_makes_step_13_present(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The plain example with no manifest: with the README, ``--step 13`` and ``--paths <the README>`` print what they print with no folder."""
    host = step_gate_host(tmp_path / "host")
    (host / "spec" / MANIFEST).unlink()
    monkeypatch.chdir(host)
    asked = (("--step", "13"), ("--paths", f"{FOLDER}/README.md"), ("--step", "13", "--json"))

    def runs() -> dict[tuple[str, ...], tuple[int, str, str]]:
        return {flags: run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), *flags) for flags in asked}

    with_no_folder = runs()
    assert "step 13 has no artifact" in "".join(with_no_folder[asked[0]][1:]), with_no_folder[asked[0]]
    assert "no step gated" in "".join(with_no_folder[asked[1]][1:]), with_no_folder[asked[1]]
    (host / FOLDER).mkdir()
    (host / FOLDER / "README.md").write_text("notes", encoding="utf-8")
    assert runs() == with_no_folder
    (host / FOLDER / "notes.json").write_text("{}", encoding="utf-8")  # X4, X5: one JSON file and step 13 is present and gated
    _code, out, err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--step", "13")
    assert "step 13 has no artifact" not in out + err, out + err
    assert _report(capsys, host, "--paths", f"{FOLDER}/notes.json")["step_gate"]["steps"] == ["13"]
    assert _report(capsys, host, "--paths", f"{FOLDER}/README.md")["step_gate"]["steps"] == []
