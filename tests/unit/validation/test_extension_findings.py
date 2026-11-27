"""The findings of a host extension (DEVSPEC-245, piece A): each row of the table, with the words that identify it.

Two layers report them.  The step-13 validator compares the manifest's entries with the files of the spec folder's
``extensions`` folder (only when it is told the spec folder).  The file validator reports a data file whose schema is
not loaded or that breaks its schema.  Every finding is E520 or E320, and belongs to step 13.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.canonical.autofix import canonical_autofix
from specdev_tools.canonical.integrity import validate_canonical_integrity, validate_canonical_integrity_file
from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.core.registry import get_shared_registry
from specdev_tools.core.step_order import load_step_order
from specdev_tools.graph.model import Graph
from specdev_tools.validation.touched_steps import steps_for_paths, steps_without_artifact
from specdev_tools.validation import spec_check
from specdev_tools.validation.check_registry import CheckContext
from specdev_tools.validation.spec_quality_lint import lint_spec_quality
from specdev_tools.validation.validate import validate_dir, validate_file
from specdev_tools.validation.validators.step_13 import folder_without_manifest_errors, validate_step_13

from ..trace._lock_support import EXAMPLE_HOST

ROOT = Path(__file__).resolve().parents[3]
EXTENSION_FILES = ROOT / "tests" / "fixtures" / "extension_example" / "spec" / "extensions"
DECLARE_DELTA = ROOT / "tests" / "fixtures" / "extension_example" / "deltas" / "declare_extension.json"
STEP_ORDER = tuple(load_step_order(str(ROOT))["steps"])
URI = "vc:ext-01-database"
SCHEMA_NAME = "ext_01_database.schema.json"
DATA_NAME = "ext_01_database.json"
SCHEMA_PLACE = f"extensions/{SCHEMA_NAME}"
DATA_PLACE = f"extensions/{DATA_NAME}"
CANON = str(EXAMPLE_HOST / "spec" / "canon")
"""The project canon of the worked example: the example data file carries one of its terms."""
TERM = "cn:project:term:reset-token"
STEP_13 = "step:13"
LABEL = {"id": "cn:core:governance_label:mandatory", "kind": "governance_label", "version": "^1.0.0"}


def _entry(extension_id: str = "ext-01-database", sections: tuple[str, ...] = ("datastores", "tables", "validation_rules")) -> dict[str, Any]:
    return {
        "extension_id": extension_id,
        "justification": "The reset token and the credential are rows of tables no toolkit step describes.",
        "required_schema_sections": list(sections),
        "governance_label_ref": dict(LABEL),
    }


def _manifest(*entries: dict[str, Any]) -> dict[str, Any]:
    return {"extensions": list(entries)}


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    """A spec folder that holds the example extension's schema and data file."""
    folder = tmp_path / "spec"
    shutil.copytree(EXTENSION_FILES, folder / "extensions")
    return folder


def _edit(path: Path, change: Any) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def _found(errors: list[SpecError]) -> list[tuple[str, str]]:
    return [(error.code, error.message) for error in errors]


def _holds(errors: list[SpecError], *expected: tuple[str, tuple[str, ...]]) -> None:
    """*errors* are exactly the *expected* findings, in any order: each ``(code, words)`` matches one finding that no other took."""
    left = list(errors)
    for code, words in expected:
        match = next((error for error in left if error.code == code and all(word in error.message for word in words)), None)
        assert match is not None, (code, words, _found(left))
        left.remove(match)
    assert left == [], _found(left)


def _one(errors: list[SpecError], code: str, *words: str) -> None:
    """*errors* is one finding of *code* whose text holds each of *words*."""
    assert [error.code for error in errors] == [code], _found(errors)
    assert [word for word in words if word not in errors[0].message] == [], errors[0].message


# --- the manifest against the folder (validators/step_13.py) --------------------------------------------------------


def test_a_declared_extension_has_no_finding_with_both_files_and_one_without_its_data_file(spec: Path) -> None:
    manifest = _manifest(_entry())
    assert validate_step_13(manifest, str(ROOT), str(spec)) == []
    (spec / "extensions" / DATA_NAME).unlink()
    _one(validate_step_13(manifest, str(ROOT), str(spec)), "E520", "Extension 'ext-01-database' has no file")


def test_a_manifest_is_checked_for_files_only_when_its_spec_folder_is_known(spec: Path, tmp_path: Path) -> None:
    """A manifest validated alone is not checked for files; the same manifest with its spec folder is."""
    declared = _manifest(_entry("ext-07-nowhere"))
    assert validate_step_13(declared, str(ROOT)) == [] and validate_step_13(declared, str(ROOT), None) == []
    _holds(
        validate_step_13(declared, str(ROOT), str(tmp_path / "empty")),
        ("E520", ("'ext-07-nowhere' has no schema",)), ("E520", ("'ext-07-nowhere' has no file",)),
    )
    manifest = tmp_path / "alone" / "13_extension_manifest.json"
    manifest.parent.mkdir()
    shutil.copy(EXAMPLE_HOST / "spec" / "13_extension_manifest.json", manifest)
    _edit(manifest, lambda document: document.update(extensions=[_entry("ext-07-nowhere")]))
    flags = {"include_quality_lint": False, "include_canonical_integrity": False}
    alone = validate_file(str(ROOT), str(manifest), **flags)
    assert [error.message for error in alone if "ext-07-nowhere' has no" in error.message] == []
    known = validate_file(str(ROOT), str(manifest), schema_spec_root=str(manifest.parent), **flags)
    assert len([error for error in known if "ext-07-nowhere' has no" in error.message]) == 2


def test_an_entry_with_no_schema_file_is_e520(spec: Path) -> None:
    (spec / "extensions" / SCHEMA_NAME).unlink()
    _one(
        validate_step_13(_manifest(_entry()), str(ROOT), str(spec)),
        "E520", "Extension 'ext-01-database' has no schema", f"expected {SCHEMA_PLACE}", f'"$id" is "{URI}"',
    )


def test_an_entry_with_no_data_file_is_e520(spec: Path) -> None:
    (spec / "extensions" / DATA_NAME).unlink()
    _one(
        validate_step_13(_manifest(_entry()), str(ROOT), str(spec)),
        "E520", "Extension 'ext-01-database' has no file", f"expected {DATA_PLACE}", f'"$schema" is "{URI}"',
    )


def test_an_entry_with_neither_file_has_both_findings(tmp_path: Path) -> None:
    (tmp_path / "extensions").mkdir()
    errors = validate_step_13(_manifest(_entry()), str(ROOT), str(tmp_path))
    assert [error.code for error in errors] == ["E520", "E520"]
    assert "has no schema" in errors[0].message and "has no file" in errors[1].message


def test_an_entry_in_a_spec_with_no_extensions_folder_has_both_findings(tmp_path: Path) -> None:
    errors = validate_step_13(_manifest(_entry()), str(ROOT), str(tmp_path))
    assert ["has no schema" in errors[0].message, "has no file" in errors[1].message, len(errors)] == [True, True, 2]


def test_files_no_entry_declares_are_e520_each(spec: Path) -> None:
    _holds(
        validate_step_13(_manifest(), str(ROOT), str(spec)),
        ("E520", (f"{SCHEMA_PLACE}: no entry of 13_extension_manifest.json declares it",)),
        ("E520", (f"{DATA_PLACE}: no entry of 13_extension_manifest.json declares it",)),
    )


def test_only_a_json_file_of_the_folder_must_be_declared_and_the_text_gives_the_naming(spec: Path) -> None:
    (spec / "extensions" / "README.md").write_text("notes", encoding="utf-8")
    assert validate_step_13(_manifest(_entry()), str(ROOT), str(spec)) == []
    (spec / "extensions" / "notes.json").write_text("{}", encoding="utf-8")
    _one(
        validate_step_13(_manifest(_entry()), str(ROOT), str(spec)),
        "E520", "extensions/notes.json: no entry of 13_extension_manifest.json declares it",
        "ext_NN_<topic>.schema.json", "ext_NN_<topic>.json",
    )


REFUSED = {
    "not a JSON Schema": (
        lambda document: document["properties"]["tables"].update(type="arrray"),
        ["is not a valid JSON Schema", "'arrray'", "/properties/tables/type"],
    ),
    "a wrong $id": (
        lambda document: document.update({"$id": "vc:ext-01-db"}),
        ['has the "$id" "vc:ext-01-db"', f'its file name gives "$id": "{URI}"'],
    ),
    "a toolkit $id": (
        lambda document: document.update({"$id": "vc:core:atoms"}),
        ['has the "$id" of a toolkit schema ("vc:core:atoms")', f'its file name gives "$id": "{URI}"'],
    ),
    "no $id": (lambda document: document.pop("$id"), ['has no "$id"', f'its file name gives "$id": "{URI}"']),
}


@pytest.mark.parametrize("case", sorted(REFUSED))
def test_a_refused_schema_is_e520_with_the_reason(spec: Path, case: str) -> None:
    change, words = REFUSED[case]
    _edit(spec / "extensions" / SCHEMA_NAME, change)
    _one(validate_step_13(_manifest(_entry()), str(ROOT), str(spec)), "E520", f"Extension schema {SCHEMA_PLACE}", *words)


def test_a_schema_file_that_is_not_json_is_e520(spec: Path) -> None:
    (spec / "extensions" / SCHEMA_NAME).write_text("{not json", encoding="utf-8")
    _one(validate_step_13(_manifest(_entry()), str(ROOT), str(spec)), "E520", f"Extension schema {SCHEMA_PLACE} is not JSON")


def test_a_required_section_the_schema_does_not_declare_is_e320(spec: Path) -> None:
    entry = _entry(sections=("datastores", "tables", "validation_rules", "migrations"))
    _one(
        validate_step_13(_manifest(entry), str(ROOT), str(spec)),
        "E320", "Extension 'ext-01-database' required_schema_sections[3] 'migrations'", f"is not a property of its schema {SCHEMA_PLACE}",
    )


def test_a_property_the_schema_takes_from_a_core_schema_counts_as_declared_and_an_unknown_name_does_not(spec: Path) -> None:
    """``canonical_refs_used`` is a property of ``vc:core:step-base``, which the schema's ``allOf`` names; ``no_such_section`` is nobody's."""
    assert validate_step_13(_manifest(_entry(sections=("tables", "canonical_refs_used"))), str(ROOT), str(spec)) == []
    _one(
        validate_step_13(_manifest(_entry(sections=("tables", "canonical_refs_used", "no_such_section"))), str(ROOT), str(spec)),
        "E320", "'no_such_section'", "is not a property of its schema",
    )


def test_a_section_the_schema_declares_only_under_then_counts_as_declared(spec: Path) -> None:
    """X7: a conditional branch declares it; a name declared by no branch is still E320."""
    (spec / "extensions" / "ext_02_cache.schema.json").write_text(json.dumps({
        "$id": "vc:ext-02-cache",
        "type": "object",
        "properties": {"engine": {"type": "string"}},
        "if": {"properties": {"engine": {"const": "redis"}}},
        "then": {"properties": {"eviction": {"type": "object"}}},
    }), encoding="utf-8")
    (spec / "extensions" / "ext_02_cache.json").write_text(json.dumps({"$schema": "vc:ext-02-cache", "engine": "redis"}), encoding="utf-8")
    assert validate_step_13(_manifest(_entry(), _entry("ext-02-cache", ("engine", "eviction"))), str(ROOT), str(spec)) == []
    _one(
        validate_step_13(_manifest(_entry(), _entry("ext-02-cache", ("engine", "eviction", "shards"))), str(ROOT), str(spec)),
        "E320", "'shards'", "extensions/ext_02_cache.schema.json",
    )


def test_with_a_toolkit_root_that_does_not_exist_no_file_is_checked_and_nothing_is_raised(spec: Path, tmp_path: Path) -> None:
    """X7, from the pack: the validator never raises, and without the toolkit's registry it makes no file check (the older checks stay)."""
    (spec / "extensions" / DATA_NAME).unlink()
    declared = _manifest({**_entry(), "justification": " "})
    here = validate_step_13(declared, str(ROOT), str(spec))
    assert sorted(error.code for error in here) == ["E320", "E520"]  # the empty justification, and the missing data file
    nowhere = validate_step_13(declared, str(tmp_path / "no" / "such" / "toolkit"), str(spec))
    assert [error.code for error in nowhere] == ["E320"] and nowhere[0].message == next(e.message for e in here if e.code == "E320")


def test_the_sections_of_a_refused_schema_are_not_judged(spec: Path) -> None:
    _edit(spec / "extensions" / SCHEMA_NAME, lambda document: document.update({"$id": "vc:ext-01-db"}))
    errors = validate_step_13(_manifest(_entry(sections=("migrations",))), str(ROOT), str(spec))
    assert [error.code for error in errors] == ["E520"]


def test_the_older_checks_of_the_manifest_are_unchanged_with_a_spec_folder_and_the_file_check_is_added(spec: Path) -> None:
    entry = {**_entry(sections=("bad name",)), "justification": " "}
    without = _found(validate_step_13(_manifest(entry), str(ROOT)))
    assert sorted(code for code, _text in without) == ["E320", "E320"]  # the section name and the empty justification
    assert sorted(_found(validate_step_13(_manifest(entry), str(ROOT), str(spec)))) == sorted(without)  # 'bad name' is not judged twice
    (spec / "extensions" / DATA_NAME).unlink()
    added = [found for found in _found(validate_step_13(_manifest(entry), str(ROOT), str(spec))) if found not in without]
    assert [code for code, _text in added] == ["E520"] and "has no file" in added[0][1]


def test_an_entry_whose_id_is_not_an_extension_id_names_no_file(spec: Path) -> None:
    """The manifest's schema reports the id; the folder's files are then declared by no entry."""
    errors = validate_step_13(_manifest(_entry("database")), str(ROOT), str(spec))
    assert [error.code for error in errors] == ["E520", "E520"]
    assert all("no entry of 13_extension_manifest.json declares it" in error.message for error in errors)


def test_two_extensions_are_judged_each_on_its_own_files(spec: Path) -> None:
    second = spec / "extensions" / "ext_02_search.schema.json"
    second.write_text(json.dumps({"$id": "vc:ext-02-search", "type": "object", "properties": {"indexes": {"type": "array"}}}), encoding="utf-8")
    entries = _manifest(_entry(), _entry("ext-02-search", ("indexes", "shards")))
    _holds(
        validate_step_13(entries, str(ROOT), str(spec)),
        ("E320", ("'shards' is not a property of its schema extensions/ext_02_search.schema.json",)),
        ("E520", ("Extension 'ext-02-search' has no file: expected extensions/ext_02_search.json",)),
    )


def test_an_entry_finding_carries_the_place_of_its_entry_and_a_folder_finding_its_file(spec: Path) -> None:
    """X6: the step gate tells one manifest finding from another by these."""
    (spec / "extensions" / "notes.json").write_text("{}", encoding="utf-8")
    (spec / "extensions" / "ext_03_queue.schema.json").write_text(json.dumps({"$id": "vc:ext-03-wrong"}), encoding="utf-8")
    entries = _manifest("not an entry", _entry("ext-05-first", ("a",)), _entry(sections=("datastores", "migrations")), _entry("ext-03-queue", ("a",)))
    errors = validate_step_13(entries, str(ROOT), str(spec))

    def the(*words: str) -> SpecError:
        (match,) = [error for error in errors if all(word in error.message for word in words)]
        return match

    assert the("'ext-05-first' has no schema").jq_path == ".extensions[1]"
    assert the("'ext-05-first' has no file").jq_path == ".extensions[1]"
    assert the("'migrations' is not a property").jq_path == ".extensions[2]"
    assert the("'ext-03-queue' has no file").jq_path == ".extensions[3]"
    for name in ("notes.json", "ext_03_queue.schema.json"):
        folder_finding = the(f"extensions/{name}")
        assert folder_finding.path is not None and folder_finding.path.endswith(f"extensions/{name}"), folder_finding
    assert len({(error.jq_path, error.path, error.node_id) for error in errors}) >= 5  # five different places, not one identity


# --- the data file (validation/validate.py, canonical/integrity.py) -------------------------------------------------


def _validate_data_file(spec: Path, **flags: Any) -> list[SpecError]:
    return validate_file(
        str(ROOT), str(spec / "extensions" / DATA_NAME), include_quality_lint=False, include_canonical_integrity=False, **flags,
    )


def test_the_data_file_validates_against_the_schema_beside_it(spec: Path) -> None:
    assert _validate_data_file(spec, schema_spec_root=str(spec)) == []
    assert _validate_data_file(spec, spec_root=str(spec)) == []
    assert _validate_data_file(spec) == []  # a file validated alone: the folder above ``extensions`` is its spec folder


def test_a_data_file_that_breaks_its_schema_is_e520_at_the_value(spec: Path) -> None:
    _edit(spec / "extensions" / DATA_NAME, lambda document: document["tables"][0].update(columns="x"))
    _one(_validate_data_file(spec, schema_spec_root=str(spec)), "E520", "tables/0/columns", "'x' is not of type 'array'")


TOOLKIT_SCHEMAS = {
    "the toolkit's step 04 schema": "schema/04_fr_list.schema.json",
    "the toolkit's manifest schema": "schema/13_extension_manifest.schema.json",
    "a core schema of the toolkit": "schema/core/atoms.schema.json",
}


def _toolkit_uri(schema_file: str) -> str:
    """The URI under which the toolkit's own registry holds its schema file *schema_file* (Z4: a URI the toolkit does hold)."""
    (uri,) = [uri for uri, place in get_shared_registry(str(ROOT)).map.items() if place == schema_file]
    return uri


WRONG_SCHEMAS = {
    "a typo": "vc:ext-1-database",
    "an extension no file is named for": "vc:ext-09-nowhere",
    "the accepted uri of another extension": "vc:ext-02-cache",
    "a uri no schema has": "vc:04-functional-requirements",
    **{name: _toolkit_uri(schema_file) for name, schema_file in TOOLKIT_SCHEMAS.items()},
    "no $schema at all": None,
}


@pytest.mark.parametrize("case", sorted(WRONG_SCHEMAS))
def test_the_schema_of_a_data_file_is_the_uri_its_file_name_gives(spec: Path, case: str) -> None:
    """X2: E520 that names the file's place, the value found and the right URI; the file is validated against no other schema."""
    value = WRONG_SCHEMAS[case]
    (spec / "extensions" / "ext_02_cache.schema.json").write_text(
        json.dumps({"$id": "vc:ext-02-cache", "type": "object", "required": ["caches"]}), encoding="utf-8",
    )
    data_file = spec / "extensions" / DATA_NAME
    assert _validate_data_file(spec, schema_spec_root=str(spec)) == []
    assert validate_canonical_integrity_file(str(ROOT), str(data_file), spec_root=str(spec), project_canon_dir=CANON) == []
    _edit(data_file, lambda document: document.pop("$schema") if value is None else document.update({"$schema": value}))
    autofix = canonical_autofix(str(ROOT), str(spec), project_canon_dir=CANON)
    assert all(isinstance(change, SpecError) for change in autofix[str(data_file)]), autofix[str(data_file)]  # no change is proposed
    by_layer = {
        "schema validation": _validate_data_file(spec, schema_spec_root=str(spec)),
        "canonical integrity": validate_canonical_integrity_file(str(ROOT), str(data_file), spec_root=str(spec), project_canon_dir=CANON),
        "canonical integrity of the folder": _about_the_data_file(validate_canonical_integrity(str(ROOT), str(spec), project_canon_dir=CANON)),
        "canonical autofix": [change for change in autofix[str(data_file)] if isinstance(change, SpecError)],
    }
    for layer, errors in by_layer.items():
        assert errors, layer
        for error in errors:
            assert error.code == "E520", (layer, error)
            assert DATA_PLACE in error.message and URI in error.message and "$schema" in error.message, (layer, error.message)
            assert value is None or value in error.message, (layer, error.message)
            assert "tools/schema_registry.json" not in error.message and "--repo-root" not in error.message, (layer, error.message)
            # judged by no other schema: nothing of the shape a schema asks for, whichever schema the file names
            assert not any(word in error.message for word in ("required property", "nevaluated", "is not of type")), (layer, error.message)
    assert all(len(errors) == 1 for errors in by_layer.values()), by_layer  # the one mismatch of each layer and no other finding
    assert all(error.owner == STEP_13 for layer in ("canonical integrity", "canonical integrity of the folder") for error in by_layer[layer])


def test_a_data_file_whose_schema_is_refused_is_the_same_e520(spec: Path) -> None:
    _edit(spec / "extensions" / SCHEMA_NAME, lambda document: document.update({"$id": "vc:ext-01-db"}))
    _one(_validate_data_file(spec, schema_spec_root=str(spec)), "E520", f"schema_not_found uri={URI}", f"{SCHEMA_PLACE} in the spec folder")


def test_the_integrity_finding_of_an_extension_file_names_the_folder_and_belongs_to_step_13(spec: Path) -> None:
    """The second of the two E520 of a file whose schema is not loaded: ``UNRESOLVED_INPUT`` of canonical integrity."""
    data_file = spec / "extensions" / DATA_NAME
    assert validate_canonical_integrity_file(str(ROOT), str(data_file), spec_root=str(spec), project_canon_dir=CANON) == []
    assert validate_canonical_integrity_file(str(ROOT), str(data_file), project_canon_dir=CANON) == []
    (spec / "extensions" / SCHEMA_NAME).unlink()
    errors = validate_canonical_integrity_file(str(ROOT), str(data_file), spec_root=str(spec), project_canon_dir=CANON)
    _one(errors, "E520", "UNRESOLVED_INPUT", f"schema_not_found uri={URI}", f"{SCHEMA_PLACE} in the spec folder")
    assert errors[0].owner == "step:13"


def test_the_integrity_finding_of_any_other_file_keeps_its_owner(tmp_path: Path) -> None:
    other = tmp_path / "spec" / "04_fr_list.json"
    other.parent.mkdir()
    other.write_text(json.dumps({"$schema": "vc:no-such-schema"}), encoding="utf-8")
    errors = validate_canonical_integrity_file(str(ROOT), str(other), spec_root=str(tmp_path / "spec"))
    _one(errors, "E520", "UNRESOLVED_INPUT", "schema_not_found uri=vc:no-such-schema")
    assert errors[0].owner is None and "extensions/" not in errors[0].message


def test_the_place_of_a_manifest_finding_is_kept_by_validate_file_and_that_of_another_step_is_not(spec: Path, tmp_path: Path) -> None:
    """X6 through ``validate_file``, and zero change beside it: the deep finding of step 10 carries no node id, as before."""
    manifest = spec / "13_extension_manifest.json"
    shutil.copy(EXAMPLE_HOST / "spec" / "13_extension_manifest.json", manifest)
    _edit(manifest, lambda document: document.update(extensions=[_entry("ext-07-nowhere")]))
    flags = {"include_quality_lint": False, "include_canonical_integrity": False}
    found = [error for error in validate_file(str(ROOT), str(manifest), schema_spec_root=str(spec), **flags) if "'ext-07-nowhere' has no" in error.message]
    assert len(found) == 2 and {(error.jq_path, error.node_id) for error in found} == {(".extensions[0]", "ext-07-nowhere")}

    governance = tmp_path / "other" / "10_governance.json"
    governance.parent.mkdir()
    shutil.copy(EXAMPLE_HOST / "spec" / "10_governance.json", governance)
    _edit(governance, lambda document: next(rule for rule in document["rules"] if "cli_command" in rule).update(cli_command="no-such-command"))
    (unknown,) = [error for error in validate_file(str(ROOT), str(governance), **flags) if "'no-such-command'" in error.message]
    assert (unknown.code, unknown.node_id, unknown.jq_path, unknown.path) == ("E530", None, None, None)


def test_the_integrity_finding_of_any_file_of_the_folder_belongs_to_step_13(spec: Path) -> None:
    """X4: also of a file that is not named for an extension."""
    for name in ("notes.json", "ext-01-database.json"):
        other = spec / "extensions" / name
        other.write_text(json.dumps({"$schema": "vc:no-such-schema"}), encoding="utf-8")
        errors = validate_canonical_integrity_file(str(ROOT), str(other), spec_root=str(spec), project_canon_dir=CANON)
        assert [error.owner for error in errors if "schema_not_found" in error.message] == [STEP_13], (name, _found(errors))


def test_the_deep_checks_of_step_13_do_not_run_on_a_data_file(spec: Path) -> None:
    """A data file is a step-13 file by its path, but the deep checks of the step read the manifest."""
    entries = [{"extension_id": "ext-05-x"}]
    assert [error for error in validate_step_13({"extensions": entries}, str(ROOT)) if "ext-05-x" in error.message] != []
    _edit(spec / "extensions" / DATA_NAME, lambda document: document.update(extensions=entries))
    assert [error.message for error in _validate_data_file(spec, schema_spec_root=str(spec)) if "'ext-05-x'" in error.message] == []


# --- a folder (validate_dir) ----------------------------------------------------------------------------------------


def _host_spec(tmp_path: Path) -> Path:
    """A copy of the worked example's spec folder with the extension's files and the manifest entry of the fixture's delta."""
    folder = tmp_path / "host" / "spec"
    shutil.copytree(EXAMPLE_HOST / "spec", folder)
    shutil.copytree(EXTENSION_FILES, folder / "extensions")
    ops = json.loads(DECLARE_DELTA.read_text(encoding="utf-8"))["ops"]
    assert {op["file"] for op in ops} == {"spec/13_extension_manifest.json"} and {op["op"] for op in ops} == {"set", "append"}

    def declare(document: dict[str, Any]) -> None:
        for op in ops:
            (key,) = op["path"]
            if op["op"] == "set":
                document[key] = op["value"]
            else:
                document[key].append(op["value"])

    _edit(folder / "13_extension_manifest.json", declare)
    return folder


def _folder_findings(spec_dir: Path) -> list[tuple[str, str]]:
    """``validate_dir`` of *spec_dir* as ``(code, text)``, the folder written ``S`` in both forms a text has it: absolute, and relative to the toolkit."""
    relative = os.path.relpath(spec_dir, ROOT)
    return sorted(
        (error.code, error.message.replace(str(spec_dir), "S").replace(relative, "S"))
        for error in validate_dir(str(ROOT), str(spec_dir), project_canon_dir=str(spec_dir / "canon"))
    )


def test_a_folder_with_the_extension_has_the_findings_of_the_folder_without_it(tmp_path: Path) -> None:
    """The schema file is not scanned as an artifact, the data file validates, the manifest finds both files."""
    plain = tmp_path / "plain" / "spec"
    shutil.copytree(EXAMPLE_HOST / "spec", plain)
    assert _folder_findings(_host_spec(tmp_path)) == _folder_findings(plain)


def test_a_folder_whose_extension_lost_its_schema_has_three_more_findings(tmp_path: Path) -> None:
    """One of the manifest (the entry has no schema) and the two of the data file (schema validation, canonical integrity)."""
    host = _host_spec(tmp_path)
    before = _folder_findings(host)
    (host / "extensions" / SCHEMA_NAME).unlink()
    added = [make for make in _folder_findings(host) if make not in before]
    assert [code for code, _text in added] == ["E520", "E520", "E520"]
    texts = [text for _code, text in added]
    (no_schema,) = [text for text in texts if "Extension 'ext-01-database' has no schema" in text]
    not_found = [text for text in texts if f"schema_not_found uri={URI}" in text]
    assert len(not_found) == 2 and no_schema not in not_found
    assert all(f"{SCHEMA_PLACE} in the spec folder" in text for text in not_found)


def test_a_folder_with_extension_files_and_no_manifest_is_one_e520_for_each_file(tmp_path: Path) -> None:
    """X5: nothing declares the files.  The control is the same folder without the files."""
    host = _host_spec(tmp_path)
    (host / "13_extension_manifest.json").unlink()
    with_files = validate_dir(str(ROOT), str(host), project_canon_dir=str(host / "canon"))
    undeclared = [error for error in with_files if "extensions/" in error.message and "13_extension_manifest.json" in error.message]
    assert sorted(error.code for error in undeclared) == ["E520", "E520"]
    assert sorted(place for place in (SCHEMA_PLACE, DATA_PLACE) for error in undeclared if place in error.message) == sorted([SCHEMA_PLACE, DATA_PLACE])
    assert all(error.owner == STEP_13 and "declare" in error.message for error in undeclared), undeclared
    shutil.rmtree(host / "extensions")
    without_files = validate_dir(str(ROOT), str(host), project_canon_dir=str(host / "canon"))
    assert [error.message for error in without_files if "extensions/" in error.message] == []


@pytest.mark.parametrize(("removed", "kept"), [(DATA_NAME, SCHEMA_PLACE), (SCHEMA_NAME, DATA_PLACE)])
def test_one_extension_file_alone_in_a_spec_with_no_manifest_is_its_own_e520(tmp_path: Path, removed: str, kept: str) -> None:
    """X5 says "for each schema file and each data file": a schema with no data file, and a data file with no schema, is undeclared too."""
    host = _host_spec(tmp_path)
    (host / "13_extension_manifest.json").unlink()
    (host / "extensions" / removed).unlink()
    errors = validate_dir(str(ROOT), str(host), project_canon_dir=str(host / "canon"))
    undeclared = [error for error in errors if "13_extension_manifest.json" in error.message and "declare" in error.message]
    assert [(error.code, error.owner) for error in undeclared] == [("E520", STEP_13)], undeclared
    assert kept in undeclared[0].message


def _about_the_data_file(errors: Any) -> list[SpecError]:
    return [error for error in errors if isinstance(error, SpecError) and DATA_NAME in f"{error.path} {error.file} {error.message}"]


def _is_told_the_way_out(error: Any) -> None:
    """Y1's E520 for the data file at the top of a folder called ``extensions``, with the sentence that names the way out."""
    assert isinstance(error, SpecError) and error.code == "E520", error
    assert "schema_uri_mismatch" in error.message and URI in error.message and "--spec-root" in error.message, error.message


def test_a_folder_command_on_the_extensions_folder_works_on_the_spec_folder_it_is_told(tmp_path: Path) -> None:
    """S1 (was X1): named the spec folder, the file is judged as on the spec folder; with none named, the folder handed is the spec folder.

    The data file carries a canonical ref its ``canonical_refs_used`` does not list, so there is something to find (E210).
    """
    host = _host_spec(tmp_path)
    _edit(host / "extensions" / DATA_NAME, lambda document: document.update(canonical_refs_used=[]))
    folder, canon = str(host / "extensions"), str(host / "canon")
    on_spec = _about_the_data_file(validate_canonical_integrity(str(ROOT), str(host), project_canon_dir=canon))
    assert [error.code for error in on_spec] == ["E210"] and TERM in on_spec[0].message
    named = {"project_canon_dir": canon, "spec_root": str(host)}
    on_folder = _about_the_data_file(validate_canonical_integrity(str(ROOT), folder, **named))
    assert [(error.code, error.value, error.message) for error in on_folder] == [("E210", on_spec[0].value, on_spec[0].message)], _found(on_folder)
    checked = _about_the_data_file(validate_dir(str(ROOT), folder, **named))
    assert {error.code for error in checked} == {"E210"}, _found(checked)
    for place, flags in ((str(host), {"project_canon_dir": canon}), (folder, named)):
        changes = canonical_autofix(str(ROOT), place, **flags)
        (for_the_file,) = [found for path, found in changes.items() if path.endswith(DATA_PLACE)]
        assert all(isinstance(change, str) for change in for_the_file), for_the_file
        assert any(TERM in change for change in for_the_file), for_the_file
    # No spec folder named: the folder handed is the spec folder, and the data file lies at its top, where no extension schema judges it.
    told = {
        "validate_dir": _about_the_data_file(validate_dir(str(ROOT), folder, project_canon_dir=canon)),
        "canonical integrity": _about_the_data_file(validate_canonical_integrity(str(ROOT), folder, project_canon_dir=canon)),
        "canonical autofix": canonical_autofix(str(ROOT), folder, project_canon_dir=canon).get(str(host / "extensions" / DATA_NAME), []),
    }
    for layer, errors in told.items():
        refused = [error for error in errors if error.code != "E210"]  # the ref this test took off the list is still found (integrity reads on)
        assert refused, (layer, errors)
        for error in refused:
            _is_told_the_way_out(error)
    assert len([error for error in told["validate_dir"] if error.code == "E520"]) == 2  # schema validation and integrity, as for any Y1 file


def test_the_e210_text_of_an_extension_file_names_the_spec_folder_and_that_of_a_step_file_is_unchanged(tmp_path: Path) -> None:
    """S1: the command of the text works as written: its folder is the spec folder, never ``<spec>/extensions``."""
    host = _host_spec(tmp_path)
    canon = str(host / "canon")
    for place in (DATA_PLACE, "04_fr_list.json"):
        _edit(host / place, lambda document: document.update(canonical_refs_used=[]))
    spec_folder = os.path.relpath(host, ROOT)  # the folder form names its files from the toolkit's folder
    errors = validate_canonical_integrity(str(ROOT), str(host), project_canon_dir=canon)
    drift = {error.file: error.message for error in errors if error.code == "E210" and "canonical_refs_used_missing" in error.message}
    assert set(drift) == {f"{spec_folder}/{DATA_PLACE}", f"{spec_folder}/04_fr_list.json"}, drift
    for text in drift.values():
        assert f"canonical-autofix {spec_folder} --write" in text, text
    for flags in ({}, {"spec_root": str(host)}):  # the file alone: by its path, and with the spec folder known
        alone = validate_canonical_integrity_file(str(ROOT), str(host / DATA_PLACE), project_canon_dir=canon, **flags)
        assert [f"canonical-autofix {host} --write" in error.message for error in alone if error.code == "E210"] == [True], _found(alone)
    stray = host / "common" / "extensions" / "x.json"  # no file of the extensions folder: the text keeps the folder of the file
    stray.parent.mkdir()
    shutil.copy(host / "04_fr_list.json", stray)
    errors = validate_canonical_integrity(str(ROOT), str(host), project_canon_dir=canon)
    assert [f"canonical-autofix {spec_folder}/common/extensions --write" in error.message for error in _about(errors, "common/extensions/x.json") if error.code == "E210"] == [True]


def test_the_plain_example_in_a_folder_called_extensions_is_the_spec_folder_whatever_lies_above_it(tmp_path: Path) -> None:
    """S1 (H1, H2), zero change by construction: the folder handed is the spec folder; nothing above it and nothing of its name is read."""
    answers, fixes = {}, {}
    for name in ("extensions", "specs"):
        host = tmp_path / f"host of {name}"
        shutil.copytree(EXAMPLE_HOST / "spec", host / name)
        (host / "00_index.json").write_text("{}", encoding="utf-8")
        answers[name] = _folder_findings(host / name)
        changes = canonical_autofix(str(ROOT), str(host / name), project_canon_dir=str(host / name / "canon"))
        fixes[name] = {path.replace(str(host / name), "S"): [str(change) for change in found] for path, found in changes.items()}
    assert answers["extensions"] == answers["specs"] and fixes["extensions"] == fixes["specs"]
    assert not any("to declare it" in text or "schema_uri_mismatch" in text for _code, text in answers["extensions"])
    # the quality checks of a step file are not lost there (H1): an empty critical array is found
    spec_dir = tmp_path / "host of extensions" / "extensions"
    _edit(spec_dir / "04_fr_list.json", lambda document: document.update(functional_requirements=[]))
    wanted = "04_fr_list.json empty critical array 'functional_requirements'"
    assert [error.code for error in lint_spec_quality(str(spec_dir)) if wanted in error.message] == ["E520"]
    assert [error.code for error in validate_dir(str(ROOT), str(spec_dir), project_canon_dir=str(spec_dir / "canon")) if wanted in error.message] == ["E520"]


# --- the step of a touched path (validation/touched_steps.py) -------------------------------------------------------


def _no_graph() -> Graph:
    raise AssertionError("the graph must not be loaded")


@pytest.mark.parametrize("path", [f"spec/{DATA_PLACE}", f"spec/{SCHEMA_PLACE}", "spec/extensions/notes.json"])
def test_a_touched_path_under_the_extensions_folder_is_step_13(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    monkeypatch.chdir(tmp_path)
    touched = steps_for_paths([path], str(host / "spec"), {}, _no_graph, step_order=STEP_ORDER, git_root=str(host))
    assert touched.steps == ("13",)
    both = steps_for_paths([path, "spec/04_fr_list.json"], str(host / "spec"), {}, _no_graph, step_order=STEP_ORDER, git_root=str(host))
    assert both.steps == ("04", "13")


@pytest.mark.parametrize("path", ["spec/extensions/sub/x.json", "spec/impl_context/extensions/ext_01_x.json", "spec/ext_01_x.json"])
def test_a_touched_path_that_is_not_directly_in_the_extensions_folder_is_not_step_13(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str,
) -> None:
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    monkeypatch.chdir(tmp_path)
    touched = steps_for_paths([path], str(host / "spec"), {}, _no_graph, step_order=STEP_ORDER, git_root=str(host))
    assert "13" not in touched.steps
    known = steps_for_paths([f"spec/{DATA_PLACE}"], str(host / "spec"), {}, _no_graph, step_order=STEP_ORDER, git_root=str(host))
    assert known.steps == ("13",)  # the same call with a path of the folder


def test_a_touched_extension_path_gates_step_13_also_in_a_spec_with_no_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """X5 with X4: the files of the folder are what step 13 has there; with neither a manifest nor a file there is nothing to gate."""
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    shutil.copytree(EXTENSION_FILES, host / "spec" / "extensions")
    (host / "spec" / "13_extension_manifest.json").unlink()
    monkeypatch.chdir(tmp_path)

    def touched(path: str) -> tuple[str, ...]:
        return steps_for_paths([path], str(host / "spec"), {}, _no_graph, step_order=STEP_ORDER, git_root=str(host)).steps

    assert touched(f"spec/{DATA_PLACE}") == ("13",) and touched(f"spec/{SCHEMA_PLACE}") == ("13",)
    shutil.rmtree(host / "spec" / "extensions")
    assert touched(f"spec/{DATA_PLACE}") == ()


def test_a_file_of_the_extensions_folder_that_is_not_json_is_no_file_of_step_13(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """S4 (H7): step 13 owns the JSON files of the folder; a README there neither makes the step present nor gates it."""
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    spec_dir = host / "spec"
    (spec_dir / "13_extension_manifest.json").unlink()
    monkeypatch.chdir(tmp_path)

    def touched(path: str) -> tuple[str, ...]:
        return steps_for_paths([path], str(spec_dir), {}, _no_graph, step_order=STEP_ORDER, git_root=str(host)).steps

    def absent() -> tuple[str, ...]:
        return steps_without_artifact(["04", "13"], str(spec_dir))

    assert absent() == ("13",) and touched("spec/extensions/README.md") == ()  # no folder: as at 673b5fa
    (spec_dir / "extensions").mkdir()
    (spec_dir / "extensions" / "README.md").write_text("notes", encoding="utf-8")
    assert absent() == ("13",) and touched("spec/extensions/README.md") == ()
    (spec_dir / "extensions" / "sub.json").mkdir()
    (spec_dir / "extensions" / "sub.json" / "x.json").write_text("{}", encoding="utf-8")
    assert absent() == ("13",)  # a folder named like a JSON file, and a JSON file below the folder, are no file of it
    (spec_dir / "extensions" / "notes.json").write_text("{}", encoding="utf-8")
    assert absent() == () and touched("spec/extensions/notes.json") == ("13",)  # X4, X5: one JSON file and the step is there
    assert touched("spec/extensions/README.md") == ()  # the README is still no step's


# --- Y1: an extension schema judges the data file of its name and no other file ------------------------------------

MISPLACED = {
    "a file at the top of the spec": "notes.json",
    "the 1.1.1 place of the data file": DATA_NAME,
    "a file of the folder that is not named for the extension": "extensions/notes.json",
    "a file under impl_context": "impl_context/x.json",
}
Y1_RUNS = [(case, True) for case in sorted(MISPLACED)] + [
    (case, False) for case in sorted(MISPLACED) if not MISPLACED[case].startswith("extensions/")
]
"""Each case with the schema file present and accepted, and once more with no ``extensions`` folder at all."""
SHAPE_WORDS = ("datastores", "not a list")
"""What a finding of the example schema's shape would name for ``_misplaced``: a required section, the value that is no array."""


def _misplaced(spec: Path, relative: str, uri: str = URI) -> Path:
    """A file at *relative* in *spec* that names the schema *uri* and has nothing of the shape the example's schema asks for."""
    path = spec / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"$schema": uri, "tables": "not a list"}), encoding="utf-8")
    return path


def _is_the_y1_finding(error: Any, path: Path, uri: str = URI) -> None:
    """E520 that names the file, the URI found and the place of the data file of that URI, and sends nobody to the toolkit."""
    assert isinstance(error, SpecError) and error.code == "E520", error
    text = error.message
    assert f"{path.parent.name}/{path.name}" in text and uri in text and DATA_PLACE in text, text
    assert not any(word in text for word in SHAPE_WORDS), text
    assert "tools/schema_registry.json" not in text and "--repo-root" not in text and "write that file" not in text.lower(), text


@pytest.mark.parametrize(("case", "with_the_folder"), Y1_RUNS)
def test_a_file_that_names_an_extension_schema_and_is_not_its_data_file_is_e520_of_each_check(
    spec: Path, case: str, with_the_folder: bool,
) -> None:
    """Y1: such a file is validated against no host schema; schema validation and canonical integrity each say E520."""
    assert validate_canonical_integrity(str(ROOT), str(spec), project_canon_dir=CANON) == []  # the example alone is clean
    if not with_the_folder:
        shutil.rmtree(spec / "extensions")
    path = _misplaced(spec, MISPLACED[case])
    plain = {"include_quality_lint": False, "include_canonical_integrity": False}
    by_layer = {
        "schema validation of the file alone": validate_file(str(ROOT), str(path), **plain),
        "schema validation, the spec folder known": validate_file(str(ROOT), str(path), schema_spec_root=str(spec), **plain),
        "canonical integrity of the file alone": validate_canonical_integrity_file(str(ROOT), str(path), project_canon_dir=CANON),
        "canonical integrity, the spec folder known": validate_canonical_integrity_file(
            str(ROOT), str(path), spec_root=str(spec), project_canon_dir=CANON,
        ),
        # The folder holds nothing else that is wrong, so every finding of the folder is one of this file.
        "canonical integrity of the folder": validate_canonical_integrity(str(ROOT), str(spec), project_canon_dir=CANON),
        "canonical autofix": canonical_autofix(str(ROOT), str(spec), project_canon_dir=CANON)[str(path)],
    }
    for layer, errors in by_layer.items():
        assert errors, layer
        for error in errors:
            _is_the_y1_finding(error, path)
    if MISPLACED[case].startswith("extensions/"):  # X4: a file of the folder belongs to step 13
        for layer in ("canonical integrity of the file alone", "canonical integrity, the spec folder known", "canonical integrity of the folder"):
            assert all(error.owner == STEP_13 for error in by_layer[layer]), (layer, by_layer[layer])


@pytest.mark.parametrize("uri", ["vc:no-such", "vc:ext-1-database", "vc:ext-01"])
def test_a_file_whose_schema_is_not_of_the_extension_form_keeps_the_answer_of_the_base_commit(spec: Path, uri: str) -> None:
    """Next to Y1: ``vc:ext-NN-<topic>`` is the form; any other unknown URI is ``schema_not_found`` as at 673b5fa."""
    path = _misplaced(spec, "notes.json", uri)
    errors = validate_file(
        str(ROOT), str(path), include_quality_lint=False, include_canonical_integrity=False, schema_spec_root=str(spec),
    )
    assert [error.code for error in errors] == ["E520"], errors
    assert errors[0].message.startswith(f"{path}: schema_not_found uri={uri} detail="), errors[0].message
    assert DATA_PLACE not in errors[0].message


def test_with_the_spec_folder_known_a_file_of_a_nested_extensions_folder_is_not_the_data_file(spec: Path) -> None:
    """Y1 read with the spec folder known: ``sub/extensions/ext_01_database.json`` is not ``extensions/ext_01_database.json``.

    A file handed alone, with no spec folder known, is read by its path: the folder above its ``extensions`` folder
    is its spec folder (X4's limit), and the schema beside it judges it.
    """
    nested = spec / "sub" / "extensions"
    shutil.copytree(spec / "extensions", nested)
    path = nested / DATA_NAME
    plain = {"include_quality_lint": False, "include_canonical_integrity": False}
    known = {
        "schema validation": validate_file(str(ROOT), str(path), schema_spec_root=str(spec), **plain),
        "canonical integrity": validate_canonical_integrity_file(str(ROOT), str(path), spec_root=str(spec), project_canon_dir=CANON),
        "canonical integrity of the folder": validate_canonical_integrity(str(ROOT), str(spec), project_canon_dir=CANON),
        "canonical autofix": canonical_autofix(str(ROOT), str(spec), project_canon_dir=CANON)[str(path)],
    }
    for layer, errors in known.items():
        assert errors, layer
        for error in errors:
            _is_the_y1_finding(error, path)
    assert validate_file(str(ROOT), str(path), **plain) == []
    assert validate_file(str(ROOT), str(spec / "extensions" / DATA_NAME), schema_spec_root=str(spec), **plain) == []


# --- Y2: validate on a schema file of the folder ---------------------------------------------------------------------

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
Y2_REFUSED = {
    "a wrong $id": lambda path: _edit(path, lambda schema: schema.update({"$id": "vc:ext-01-databse"})),
    "draft-07": lambda path: _edit(path, lambda schema: schema.update({"$schema": "http://json-schema.org/draft-07/schema#"})),
    "not a JSON Schema": lambda path: _edit(path, lambda schema: schema.update({"type": "no-such-type"})),
    "not JSON": lambda path: path.write_text("{", encoding="utf-8"),
}


def _validate_alone(path: Path, **flags: Any) -> list[SpecError]:
    """What ``specdev validate <path>`` hands to ``validate_file`` (every check on)."""
    return validate_file(str(ROOT), str(path), project_canon_dir=CANON, **flags)


def _of_the_folder_check(spec: Path, place: str) -> list[SpecError]:
    """What the folder check (the manifest's validator, the spec folder known) says of the file *place*."""
    return [error for error in validate_step_13(_manifest(_entry()), str(ROOT), str(spec)) if error.path == place]


def test_validate_on_an_accepted_schema_file_of_the_folder_has_no_finding(spec: Path) -> None:
    assert _of_the_folder_check(spec, SCHEMA_PLACE) == []
    for flags in ({}, {"spec_root": str(spec)}):
        assert _validate_alone(spec / "extensions" / SCHEMA_NAME, **flags) == [], flags


@pytest.mark.parametrize("case", sorted(Y2_REFUSED))
def test_validate_on_a_refused_schema_file_gives_the_finding_of_the_folder_check_and_nothing_else(spec: Path, case: str) -> None:
    schema_file = spec / "extensions" / SCHEMA_NAME
    Y2_REFUSED[case](schema_file)
    of_the_folder = _of_the_folder_check(spec, SCHEMA_PLACE)
    assert [error.code for error in of_the_folder] == ["E520"], of_the_folder
    for flags in ({}, {"spec_root": str(spec)}):
        alone = _validate_alone(schema_file, **flags)
        assert [(error.code, error.owner, error.message) for error in alone] == [("E520", STEP_13, of_the_folder[0].message)], (flags, alone)
        assert "schema_not_found" not in alone[0].message and "tools/schema_registry.json" not in alone[0].message


def test_validate_on_a_schema_file_of_the_folder_that_is_not_named_for_an_extension_gives_the_finding_of_the_folder_check(spec: Path) -> None:
    """Not in the brief's lines (my reading): such a file is never loaded as a schema, and the folder check says so of it."""
    place = "extensions/notes.schema.json"
    shutil.copyfile(spec / "extensions" / SCHEMA_NAME, spec / place)
    of_the_folder = _of_the_folder_check(spec, place)
    assert [error.code for error in of_the_folder] == ["E520"] and "ext_NN_<topic>" in of_the_folder[0].message, of_the_folder
    alone = _validate_alone(spec / place)
    assert [(error.code, error.owner, error.message) for error in alone] == [("E520", STEP_13, of_the_folder[0].message)], alone


@pytest.mark.parametrize("relative", ["foo.schema.json", "impl_context/extensions/ext_01_database.schema.json", "extensions/sub/ext_01_database.schema.json"])
def test_validate_on_a_schema_file_outside_an_extensions_folder_keeps_the_answer_of_the_base_commit(spec: Path, relative: str) -> None:
    """673b5fa reads any JSON file as a spec artifact: its ``$schema`` is the dialect, which is no schema of the toolkit."""
    path = spec / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(spec / "extensions" / SCHEMA_NAME, path)
    assert json.loads(path.read_text(encoding="utf-8"))["$schema"] == DRAFT_2020_12
    errors = _validate_alone(path)
    assert [error.code for error in errors] == ["E520"], errors
    assert errors[0].message.startswith(f"{path}: schema_not_found uri={DRAFT_2020_12} detail="), errors[0].message


def test_validate_on_a_schema_file_that_does_not_exist_is_not_a_clean_answer(spec: Path) -> None:
    """The file is asked for by name: a name with nothing behind it may not read as "accepted"."""
    missing = spec / "extensions" / "ext_09_nothing.schema.json"
    errors = _validate_alone(missing)
    assert errors != [] and all(error.code.startswith("E") for error in errors), errors


def test_validate_with_the_spec_folder_known_reads_a_schema_file_of_a_nested_extensions_folder_as_any_other_file(spec: Path) -> None:
    """Y2 with the spec folder known: ``sub/extensions/*.schema.json`` is outside its ``extensions`` folder, so the answer
    is that of 673b5fa and not the folder's verdict on the file of the same name.  By its path alone it is a schema file."""
    nested = spec / "sub" / "extensions"
    shutil.copytree(spec / "extensions", nested)
    errors = _validate_alone(nested / SCHEMA_NAME, spec_root=str(spec))
    assert [error.code for error in errors] == ["E520"], errors
    assert errors[0].message.startswith(f"{nested / SCHEMA_NAME}: schema_not_found uri={DRAFT_2020_12} detail="), errors[0].message
    assert _validate_alone(nested / SCHEMA_NAME) == []


# --- fix round 3 ------------------------------------------------------------------------------------------------------

NOTE = '{"note": 1, "assumptions": ["TBD: who owns this note"]}'
"""No step document: read as a step file it lacks four top-level keys, and its assumption holds a marker (the lint's second pass)."""
QUIET = {"include_quality_lint": False, "include_canonical_integrity": False}


def _about(errors: list[SpecError], words: str) -> list[SpecError]:
    return [error for error in errors if words in f"{error.path} {error.file} {error.message}"]


def test_with_the_spec_folder_known_a_step_named_file_of_the_folder_is_read_as_no_step_file(tmp_path: Path) -> None:
    """Z2(a): the place decides.  The control is the same file at the top of the spec folder, which the name makes a step file."""
    host = _host_spec(tmp_path)
    in_folder, at_top = host / "extensions" / "04_notes.json", host / "04_notes.json"
    in_folder.write_text(NOTE, encoding="utf-8")
    at_top.write_text(NOTE, encoding="utf-8")
    for errors in (validate_dir(str(ROOT), str(host), project_canon_dir=str(host / "canon")), lint_spec_quality(str(host))):
        asks_top_level = [error.message for error in errors if "missing top-level" in error.message]
        assert [text for text in asks_top_level if "extensions/04_notes.json" in text] == [], asks_top_level
        assert len([text for text in asks_top_level if "04_notes.json" in text]) == 4, asks_top_level  # id, owner, created_at, canonical_refs_used
        markers = [error.message for error in errors if error.code == "E512"]
        assert len(markers) == 1 and " 04_notes.json:assumptions" in markers[0], markers  # the second pass: the file at the top only
    # the lint handed the extensions folder: named the spec folder, the file is a file of its folder; with none named,
    # the folder handed is the spec folder and the file a step file at its top (S1; this line asked for [] before)
    assert [error.message for error in lint_spec_quality(str(host / "extensions"), spec_root=str(host)) if "missing top-level" in error.message] == []
    assert len([error.message for error in lint_spec_quality(str(host / "extensions")) if "missing top-level" in error.message]) == 4
    # One file, a step 04 document with no id (a file with no "$schema" is not read further): with the spec folder
    # known the lint of a step file does not read it; by its path alone the name keeps its step, and the lint asks for the id.
    document = json.loads((host / "04_fr_list.json").read_text(encoding="utf-8"))
    del document["id"]
    in_folder.write_text(json.dumps(document), encoding="utf-8")
    known = validate_file(str(ROOT), str(in_folder), include_canonical_integrity=False, spec_root=str(host))
    alone = validate_file(str(ROOT), str(in_folder), include_canonical_integrity=False)
    assert [error.message for error in known if "missing top-level" in error.message] == []
    assert [error.message for error in alone if "missing top-level" in error.message] == ["UNRESOLVED_INPUT 04_notes.json missing top-level 'id'"]
    of_the_schema = [error.message for error in known if "'id' is a required property" in error.message]
    assert len(of_the_schema) == 1  # the schema it names still judges it, and the guidance is step 13's: the step that owns the file
    assert "prompts/prompt_13" in of_the_schema[0] and "prompts/prompt_04" not in of_the_schema[0], of_the_schema


def test_the_checks_of_the_manifest_read_the_manifest_and_no_other_file_of_the_folder(tmp_path: Path) -> None:
    """Z2(a): a file of the folder is step 13's by its place, and the deep checks of step 13 are the manifest's alone, whatever the file is named."""
    host = _host_spec(tmp_path)
    manifest = host / "13_extension_manifest.json"
    _edit(manifest, lambda document: document["extensions"].append({**document["extensions"][0], "extension_id": "ext-07-nowhere"}))
    copy = host / "extensions" / "04_notes.json"
    shutil.copy(manifest, copy)
    flags = {"include_canonical_integrity": False, "spec_root": str(host)}
    of_the_manifest = [error for error in validate_file(str(ROOT), str(manifest), **flags) if "'ext-07-nowhere' has no" in error.message]
    assert len(of_the_manifest) == 2
    assert [error.message for error in validate_file(str(ROOT), str(copy), **flags) if "'ext-07-nowhere' has no" in error.message] == []


def test_spec_check_gives_a_finding_the_owner_of_its_files_place(tmp_path: Path) -> None:
    """Z2(a) in the two owner stamps of ``spec-check``: the schema check, and a check that names its file and leaves the owner open."""
    host = _host_spec(tmp_path)
    (host / "extensions" / "04_notes.json").write_text(NOTE, encoding="utf-8")
    (host / "common" / "extensions").mkdir()
    (host / "common" / "extensions" / "x.json").write_text(NOTE, encoding="utf-8")
    found = spec_check._check_schema_validation(CheckContext(repo_root=str(ROOT), spec_dir=str(host)))["errors"]
    owners = {error.file: error.owner for error in found if "missing_schema_uri" in error.message}
    assert owners == {"extensions/04_notes.json": STEP_13, "common/extensions/x.json": None}
    named = [make_error("E530", "x", file=place) for place in ("extensions/04_notes.json", "common/extensions/x.json", "04_fr_list.json")]
    assert [error.owner for error in spec_check._owned_by_file(named, str(host), str(host))] == [STEP_13, None, "step:04"]


def test_the_spec_folder_is_the_one_a_caller_names_and_else_the_folder_it_was_handed(tmp_path: Path) -> None:
    """S1: a folder called ``extensions`` below a folder that holds a numbered JSON file is the spec folder when it is handed; named, the spec folder decides."""
    spec_dir = tmp_path / "spec"
    folder = spec_dir / "extensions"
    folder.mkdir(parents=True)
    (folder / "04_notes.json").write_text(NOTE, encoding="utf-8")
    (spec_dir / "00_index.json").write_text("{}", encoding="utf-8")  # H1: nothing above the folder handed is read

    def asked(errors: Any) -> list[str]:
        return [error["message"] if isinstance(error, dict) else error.message for error in errors if "missing top-level" in str(error)]

    assert len(asked(lint_spec_quality(str(folder)))) == 4
    assert asked(lint_spec_quality(str(folder), spec_root=str(spec_dir))) == []
    assert asked(validate_dir(str(ROOT), str(folder), spec_root=str(spec_dir))) == []
    named = CheckContext(repo_root=str(ROOT), spec_dir=str(folder), spec_root=str(spec_dir))
    assert asked(spec_check._check_spec_quality_lint(named)["errors"]) == []
    assert len(asked(spec_check._check_spec_quality_lint(CheckContext(repo_root=str(ROOT), spec_dir=str(folder)))["errors"])) == 4


def test_a_folder_called_extensions_below_the_spec_folder_holds_no_file_of_step_13(tmp_path: Path) -> None:
    """Z2(a), G4: the integrity finding of ``sub/extensions/ext_01_database.json`` keeps the owner of a stray file of that place."""
    host = _host_spec(tmp_path)
    for folder in ("other", "extensions"):
        shutil.copytree(EXTENSION_FILES, host / "sub" / folder)
    errors = validate_canonical_integrity(str(ROOT), str(host), project_canon_dir=str(host / "canon"))
    by_folder = {folder: _about(errors, f"sub/{folder}/{DATA_NAME}") for folder in ("other", "extensions")}
    for folder, found in by_folder.items():
        assert [error.code for error in found] == ["E520"] and URI in found[0].message and DATA_PLACE in found[0].message, (folder, found)
    assert by_folder["extensions"][0].owner == by_folder["other"][0].owner and by_folder["extensions"][0].owner != STEP_13
    assert _about(errors, f"spec/{DATA_PLACE}") == []  # the right data file is still accepted


def test_the_folder_commands_on_a_spec_folder_called_extensions_work_on_that_folder(tmp_path: Path) -> None:
    """Z2(b): X1's reading does not fire for a folder that is a spec folder; its data file is accepted, and judged when it is broken."""
    spec_dir = tmp_path / "host" / "extensions"
    shutil.move(str(_host_spec(tmp_path)), str(spec_dir))
    (tmp_path / "host" / "00_index.json").write_text("{}", encoding="utf-8")  # H1, H2: nothing above the folder handed is read
    canon = str(spec_dir / "canon")
    data_file = spec_dir / "extensions" / DATA_NAME
    assert _about(validate_dir(str(ROOT), str(spec_dir), project_canon_dir=canon), DATA_NAME) == []
    assert _about(validate_canonical_integrity(str(ROOT), str(spec_dir), project_canon_dir=canon), DATA_NAME) == []
    assert canonical_autofix(str(ROOT), str(spec_dir), project_canon_dir=canon).get(str(data_file), []) == []
    _edit(data_file, lambda document: document["tables"][0].update(columns="x"))
    broken = _about(validate_dir(str(ROOT), str(spec_dir), project_canon_dir=canon), DATA_NAME)
    assert [error for error in broken if "'x' is not of type 'array'" in error.message and error.code == "E520"] != [], broken
    assert not any("move this file" in error.message or "schema_not_found" in error.message for error in broken), broken


def test_validate_dir_on_the_extensions_folder_gives_what_the_spec_folder_it_is_told_gives_of_its_files(tmp_path: Path) -> None:
    """S1 (was Z3): named the spec folder, a refused schema has its own finding and, with no manifest, each file its E520, as on the spec folder.

    With none named the folder handed is the spec folder: the data file is told the way out and nothing is said of a schema file or a manifest.
    """
    host = _host_spec(tmp_path)
    canon = str(host / "canon")
    named = {"spec_root": str(host)}
    draft_07 = "http://json-schema.org/draft-07/schema#"
    _edit(host / "extensions" / SCHEMA_NAME, lambda document: document.update({"$schema": draft_07}))

    def own(spec_dir: Path, **flags: Any) -> list[tuple[str, str | None, str]]:
        errors = validate_dir(str(ROOT), str(spec_dir), project_canon_dir=canon, **flags)
        return sorted((error.code, error.owner, error.message[error.message.index("Extension schema"):]) for error in errors if "Extension schema" in error.message)

    on_spec = own(host)
    assert len(on_spec) == 1 and on_spec[0][0] == "E520" and SCHEMA_PLACE in on_spec[0][2] and draft_07 in on_spec[0][2], on_spec
    on_folder = own(host / "extensions", **named)
    assert [(code, text) for code, _owner, text in on_folder] == [(code, text) for code, _owner, text in on_spec]
    assert on_folder[0][1] == STEP_13
    (tmp_path / "to_the_folder").symlink_to(host / "extensions", target_is_directory=True)
    assert own(tmp_path / "to_the_folder", **named) == on_folder  # S2: the folder walked is the extensions folder however it is reached
    assert own(host / "extensions") == []
    alone = _about_the_data_file(validate_dir(str(ROOT), str(host / "extensions"), project_canon_dir=canon))
    assert len(alone) == 2, _found(alone)
    for error in alone:
        _is_told_the_way_out(error)

    (host / "13_extension_manifest.json").unlink()

    def undeclared(spec_dir: Path, **flags: Any) -> list[tuple[str, str | None, str | None, str]]:
        errors = validate_dir(str(ROOT), str(spec_dir), project_canon_dir=canon, **flags)
        return sorted((error.code, error.owner, error.file, error.message) for error in errors if "to declare it" in error.message)

    on_spec = undeclared(host)
    assert [(code, owner, place) for code, owner, place, _text in on_spec] == [("E520", STEP_13, DATA_PLACE), ("E520", STEP_13, SCHEMA_PLACE)]
    assert undeclared(host / "extensions", **named) == on_spec and undeclared(host / "extensions") == []
    # with no manifest the answer is "nothing declares it" for each file, on the folder as on the spec: not also a second finding of the schema file
    assert own(host / "extensions", **named) == own(host) == []


def test_a_folder_finding_names_its_file_the_way_a_finding_of_a_spec_with_no_manifest_does(spec: Path) -> None:
    """Z6: ``file``, relative to the spec folder, from the validator and through ``validate_file`` of the manifest; an entry finding has none."""
    (spec / "extensions" / "notes.json").write_text("{}", encoding="utf-8")
    _edit(spec / "extensions" / SCHEMA_NAME, lambda document: document.update({"$id": "vc:ext-01-db"}))
    manifest = spec / "13_extension_manifest.json"
    shutil.copy(EXAMPLE_HOST / "spec" / "13_extension_manifest.json", manifest)
    _edit(manifest, lambda document: document.update(extensions=[_entry(), _entry("ext-07-nowhere")]))
    direct = validate_step_13(_manifest(_entry(), _entry("ext-07-nowhere")), str(ROOT), str(spec))
    through = [error for error in validate_file(str(ROOT), str(manifest), schema_spec_root=str(spec), **QUIET) if "xtension" in error.message]
    for errors in (direct, through):
        assert {error.file for error in errors if error.jq_path is None} == {"extensions/notes.json", SCHEMA_PLACE}, errors
        assert [error for error in errors if error.jq_path is not None] != [] and all(error.file is None for error in errors if error.jq_path is not None)
        assert all(error.file == error.path for error in errors if error.jq_path is None)
    manifest.unlink()
    assert {error.file for error in folder_without_manifest_errors(str(spec))} == {"extensions/notes.json", SCHEMA_PLACE, DATA_PLACE}
