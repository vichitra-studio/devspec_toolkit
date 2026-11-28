"""A host's extension schemas (``spec/extensions/*.schema.json``) in both schema resolvers (DEVSPEC-245, piece A).

The schema and the data file are the ones of ``tests/fixtures/extension_example``; each test copies them to a spec
folder of its own.  The zero-change claims are identities: a spec folder with no ``extensions`` folder gets the very
registry object a call without a spec root returns.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

import specdev_tools.core.registry as registry_module
from specdev_tools.core import host_schemas, json_utils
from specdev_tools.core.host_schemas import (
    NO_HOST_SCHEMAS,
    data_file_of,
    extension_id_of,
    find_host_schemas,
    missing_schema_text,
    schema_file_of,
    schema_place_of,
    schema_uri_problem,
    spec_root_for,
    spec_root_of,
    stem_of,
    uri_of,
)
from specdev_tools.core.json_utils import JsonUtilsError, build_id_index, check_edit, find_schema_dir, json_schema_discovery
from specdev_tools.core.loaders import iter_spec_artifacts
from specdev_tools.core.registry import get_shared_registry
from specdev_tools.core.schema_validate import SchemaNotFoundError, schema_violations, validate_data_against_schema
from specdev_tools.core.step_paths import get_step_from_path, is_extension_file, step_of_spec_file
from specdev_tools.migration import triage
from unit.graph._synth import git, run_cli

ROOT = Path(__file__).resolve().parents[3]
EXTENSION_FILES = ROOT / "tests" / "fixtures" / "extension_example" / "spec" / "extensions"
PLAIN_SPEC = ROOT / "tests" / "fixtures" / "graph_example" / "spec"
URI = "vc:ext-01-database"
SCHEMA_NAME = "ext_01_database.schema.json"
DATA_NAME = "ext_01_database.json"
SCHEMA_PLACE = f"extensions/{SCHEMA_NAME}"
DATA_PLACE = f"extensions/{DATA_NAME}"
TOOLKIT_SCHEMA_FILES = ("schema/04_fr_list.schema.json", "schema/13_extension_manifest.schema.json", "schema/core/atoms.schema.json")


def _spec(folder: Path) -> Path:
    """A spec folder at *folder* that holds the example extension's two files and nothing else."""
    shutil.copytree(EXTENSION_FILES, folder / "extensions")
    return folder


def _schema_path(spec: Path) -> Path:
    return spec / "extensions" / SCHEMA_NAME


def _data(spec: Path) -> dict[str, Any]:
    return json.loads((spec / "extensions" / DATA_NAME).read_text(encoding="utf-8"))


def _edit_schema(spec: Path, change: Any) -> None:
    """Rewrite the schema of *spec* after ``change(document)`` (the size changes with it, so the edit is seen)."""
    path = _schema_path(spec)
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(json.dumps(document), encoding="utf-8")


# --- names ----------------------------------------------------------------------------------------------------------


def test_the_names_of_an_extension_follow_from_its_id() -> None:
    assert stem_of("ext-01-database") == "ext_01_database"
    assert uri_of("ext-01-database") == URI
    assert schema_file_of("ext-01-database") == SCHEMA_PLACE
    assert data_file_of("ext-01-database") == f"extensions/{DATA_NAME}"
    assert extension_id_of(SCHEMA_NAME) == extension_id_of(DATA_NAME) == "ext-01-database"
    assert extension_id_of("ext_02_auth_provider.json") == "ext-02-auth-provider"
    assert schema_place_of(URI) == SCHEMA_PLACE
    text = missing_schema_text(URI)
    assert text is not None and text.startswith(f"Schema not found for {URI}") and SCHEMA_PLACE in text


@pytest.mark.parametrize("name", ["notes.json", "ext-01-database.json", "ext_1_database.json", "ext_01_Database.schema.json", "ext_01_database.yaml"])
def test_a_name_that_is_not_an_extensions_gives_no_id(name: str) -> None:
    assert extension_id_of(name) is None


@pytest.mark.parametrize(
    "uri",
    ["vc:13-extension-manifest", "vc:core:atoms", "vc:extras:trace-lock", "https://json-schema.org/draft/2020-12/schema"],
)
def test_only_the_extension_form_of_a_uri_has_a_place_in_the_spec_folder(uri: str) -> None:
    assert schema_place_of(uri) is None and missing_schema_text(uri) is None


def test_no_toolkit_uri_has_the_extension_form() -> None:
    assert [uri for uri in get_shared_registry(str(ROOT)).map if schema_place_of(uri)] == []


def test_the_spec_root_of_an_extension_file_is_the_folder_above_extensions(tmp_path: Path) -> None:
    assert spec_root_of(str(tmp_path / "spec" / "extensions" / DATA_NAME)) == str(tmp_path / "spec")
    assert spec_root_of(str(tmp_path / "spec" / "04_fr_list.json")) is None
    assert spec_root_of(str(tmp_path / "spec" / "impl_context" / "ms_a_plan.json")) is None


# --- discovery and the URI rule -------------------------------------------------------------------------------------


def test_a_spec_folder_with_no_extensions_folder_gives_the_one_empty_answer(tmp_path: Path) -> None:
    assert find_host_schemas(str(PLAIN_SPEC)) is NO_HOST_SCHEMAS
    assert find_host_schemas(str(tmp_path / "no-such-folder")) is NO_HOST_SCHEMAS
    assert find_host_schemas(None) is NO_HOST_SCHEMAS
    assert NO_HOST_SCHEMAS.accepted == {} and NO_HOST_SCHEMAS.paths == {}


def test_a_schema_named_for_its_id_is_accepted(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    found = find_host_schemas(str(spec), get_shared_registry(str(ROOT)).map)
    assert list(found.accepted) == [URI] and found.refused == {}
    assert found.paths == {URI: str(_schema_path(spec))}
    assert found.accepted[URI].schema["$id"] == URI
    assert found.schema_files == (SCHEMA_NAME,) and found.data_files == (DATA_NAME,)


def _not_json(path: Path) -> None:
    path.write_text("{not json", encoding="utf-8")


def _set(key_path: tuple[str, ...], value: Any) -> Any:
    def change(path: Path) -> None:
        document = json.loads(path.read_text(encoding="utf-8"))
        node = document
        for key in key_path[:-1]:
            node = node[key]
        node[key_path[-1]] = value
        path.write_text(json.dumps(document), encoding="utf-8")
    return change


def _drop_id(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    del document["$id"]
    path.write_text(json.dumps(document), encoding="utf-8")


REFUSALS = {
    "not JSON": (_not_json, ["is not JSON"]),
    "not a JSON Schema": (_set(("properties", "tables", "type"), "arrray"), ["is not a valid JSON Schema", "'arrray'", "/properties/tables/type"]),
    "no $id": (_drop_id, ['has no "$id"', f'"$id": "{URI}"']),
    "an $id that is not its file name's": (_set(("$id",), "vc:ext-01-db"), ['has the "$id" "vc:ext-01-db"', f'its file name gives "$id": "{URI}"']),
    "the $id of a toolkit schema": (_set(("$id",), "vc:core:atoms"), ['the "$id" of a toolkit schema ("vc:core:atoms")', f'"$id": "{URI}"']),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_a_schema_that_is_not_accepted_is_refused_with_the_reason(tmp_path: Path, case: str) -> None:
    change, words = REFUSALS[case]
    spec = _spec(tmp_path / "spec")
    change(_schema_path(spec))
    found = find_host_schemas(str(spec), get_shared_registry(str(ROOT)).map)
    assert found.accepted == {} and list(found.refused) == [SCHEMA_NAME]
    assert [word for word in words if word not in found.refused[SCHEMA_NAME]] == []
    assert found.schema_files == (SCHEMA_NAME,)
    assert get_shared_registry(str(ROOT), str(spec)) is get_shared_registry(str(ROOT))


def test_a_schema_file_not_named_for_an_extension_is_listed_and_never_loaded(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    shutil.copy(_schema_path(spec), spec / "extensions" / "notes.schema.json")
    (spec / "extensions" / "notes.json").write_text("{}", encoding="utf-8")
    (spec / "extensions" / "README.md").write_text("notes", encoding="utf-8")
    found = find_host_schemas(str(spec))
    assert list(found.accepted) == [URI] and found.refused == {}
    assert found.schema_files == (SCHEMA_NAME, "notes.schema.json") and found.data_files == (DATA_NAME, "notes.json")


def test_a_schema_is_read_once_and_again_when_its_file_changes(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    first = find_host_schemas(str(spec)).accepted[URI].schema
    assert find_host_schemas(str(spec)).accepted[URI].schema is first
    _edit_schema(spec, lambda document: document.update(title="changed"))
    second = find_host_schemas(str(spec)).accepted[URI].schema
    assert second is not first and second["title"] == "changed"


# --- the URI map: get_shared_registry -------------------------------------------------------------------------------


def test_without_an_extensions_folder_the_registry_is_the_very_object_of_today(tmp_path: Path) -> None:
    toolkit = get_shared_registry(str(ROOT))
    assert get_shared_registry(str(ROOT), str(PLAIN_SPEC)) is toolkit
    assert get_shared_registry(str(ROOT), None) is toolkit
    assert get_shared_registry(str(ROOT), str(tmp_path / "no-such-folder")) is toolkit
    (tmp_path / "extensions").mkdir()
    assert get_shared_registry(str(ROOT), str(tmp_path)) is toolkit  # an empty folder holds no schema
    assert toolkit.spec_root is None


def test_with_an_extension_the_registry_holds_both_and_the_toolkits_is_untouched(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    toolkit = get_shared_registry(str(ROOT))
    before = dict(toolkit.map)
    registry = get_shared_registry(str(ROOT), str(spec))
    assert registry is not toolkit and registry is get_shared_registry(str(ROOT), str(spec))
    assert registry.spec_root == os.path.realpath(spec)
    assert set(registry.map) == set(before) | {URI} and registry.resolve(URI) == str(_schema_path(spec))
    assert registry.uri_exists(URI) and registry.load(URI)["$id"] == URI
    assert registry.store["vc:core:atoms"] is toolkit.store["vc:core:atoms"]  # shared, not read again
    assert get_shared_registry(str(ROOT)) is toolkit and toolkit.map == before and not toolkit.uri_exists(URI)


def test_a_host_schema_that_refs_three_core_schemas_validates_its_file(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    text = _schema_path(spec).read_text(encoding="utf-8")
    assert all(ref in text for ref in ('"vc:core:atoms#kebabId"', '"vc:core:graph#scopeReasonRule"', '"vc:core:step-base"'))
    data = _data(spec)
    assert validate_data_against_schema(str(ROOT), data, str(spec)) == []
    data["tables"][0]["columns"] = "x"                      # the schema's own keyword
    data["tables"][0]["table_id"] = "Not Kebab"             # vc:core:atoms#kebabId
    data["tables"][1].pop("scope_reason")                   # vc:core:graph#scopeReasonRule (scope is later)
    data["owner"] = "nobody"                                # vc:core:step-base (owner enum)
    found = {path for path, _message in validate_data_against_schema(str(ROOT), data, str(spec))}
    # jsonschema may add findings of its own (the root's unevaluated properties when a branch fails): the four written here are held
    assert {("owner",), ("tables", 0, "columns"), ("tables", 0, "table_id"), ("tables", 1)} <= found


def test_without_the_spec_root_the_extension_schema_is_not_found_and_the_text_names_the_folder(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    with pytest.raises(SchemaNotFoundError) as refusal:
        validate_data_against_schema(str(ROOT), _data(spec))
    assert refusal.value.uri == URI and SCHEMA_PLACE in refusal.value.detail and "in the spec folder" in refusal.value.detail
    with pytest.raises(SchemaNotFoundError) as other:
        validate_data_against_schema(str(ROOT), {"$schema": "vc:no-such-schema"})
    assert "tools/schema_registry.json" in other.value.detail and "extensions/" not in other.value.detail


def test_the_registry_is_built_again_when_the_host_schema_changes(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    first = get_shared_registry(str(ROOT), str(spec))
    assert schema_violations(str(ROOT), _data(spec), str(spec)) == []
    _edit_schema(spec, lambda document: document["required"].append("migrations"))
    second = get_shared_registry(str(ROOT), str(spec))
    assert second is not first
    assert [violation.message for violation in schema_violations(str(ROOT), _data(spec), str(spec))] == ["'migrations' is a required property"]
    _schema_path(spec).unlink()
    assert get_shared_registry(str(ROOT), str(spec)) is get_shared_registry(str(ROOT))


def test_a_host_schema_without_the_dialect_keyword_does_not_stop_the_other_files(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    _edit_schema(spec, lambda document: document.pop("$schema"))
    assert validate_data_against_schema(str(ROOT), _data(spec), str(spec)) == []
    manifest = json.loads((PLAIN_SPEC / "13_extension_manifest.json").read_text(encoding="utf-8"))
    assert validate_data_against_schema(str(ROOT), manifest, str(spec)) == []


class _CountingCache(dict):  # type: ignore[type-arg]
    """Counts the validators stored: ``get_cached_validator`` stores one each time it has to build one."""

    built = 0

    def __setitem__(self, key: Any, value: Any) -> None:
        self.built += 1
        super().__setitem__(key, value)


def test_two_spec_roots_in_one_process_keep_their_own_validators(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Head and baseline of the step gate: after the first round no validator is built again, and each root keeps its own answer."""
    head, baseline = _spec(tmp_path / "head"), _spec(tmp_path / "baseline")
    _edit_schema(head, lambda document: document["required"].append("migrations"))
    cache = _CountingCache()
    monkeypatch.setattr(registry_module, "_VALIDATOR_CACHE", cache)
    manifest = json.loads((PLAIN_SPEC / "13_extension_manifest.json").read_text(encoding="utf-8"))

    def one_round() -> None:
        assert [path for path, _message in validate_data_against_schema(str(ROOT), _data(head), str(head))] == [()]  # 'migrations' is missing
        assert validate_data_against_schema(str(ROOT), _data(baseline), str(baseline)) == []
        for spec_root in (str(head), str(baseline), str(PLAIN_SPEC), None):
            assert validate_data_against_schema(str(ROOT), manifest, spec_root) == []

    one_round()
    after_first = cache.built
    assert after_first > 0
    one_round()
    one_round()
    assert cache.built == after_first  # head, baseline and the toolkit's own did not evict one another


def test_more_spec_roots_than_the_registry_remembers_still_get_their_own_answers(tmp_path: Path) -> None:
    """Each spec folder requires a key of its own; the answer of a folder never comes from another folder's schema."""
    count = registry_module._HOST_REGISTRY_LIMIT + 2
    specs = [_spec(tmp_path / f"spec{index}") for index in range(count)]
    for index, spec in enumerate(specs):
        _edit_schema(spec, lambda document, index=index: document["required"].append(f"key_{index}"))
    for order in (range(count), reversed(range(count)), range(count)):
        for index in order:
            messages = [message for _path, message in validate_data_against_schema(str(ROOT), _data(specs[index]), str(specs[index]))]
            assert len(messages) == 1 and f"'key_{index}'" in messages[0], (index, messages)
            assert len(registry_module._HOST_REGISTRIES) <= registry_module._HOST_REGISTRY_LIMIT  # "remembered at once"
            # A spec folder that is no longer remembered leaves no validator behind ("dropped with its validators").
            validators_of = {key[:2] for key in registry_module._VALIDATOR_CACHE if key[1] is not None}
            assert validators_of <= set(registry_module._HOST_REGISTRIES), validators_of - set(registry_module._HOST_REGISTRIES)


def test_more_folders_than_the_scan_remembers_still_give_their_own_schemas(tmp_path: Path) -> None:
    count = host_schemas._SCAN_LIMIT + 2
    specs = [_spec(tmp_path / f"spec{index}") for index in range(count)]
    for index, spec in enumerate(specs):
        _edit_schema(spec, lambda document, index=index: document.update(title=f"schema {index}"))
    for order in (range(count), reversed(range(count)), range(count)):
        for index in order:
            found = find_host_schemas(str(specs[index]))
            assert found.accepted[URI].schema["title"] == f"schema {index}" and found.accepted[URI].path == str(_schema_path(specs[index]))
            assert len(host_schemas._SCANS) <= host_schemas._SCAN_LIMIT  # "folders remembered at once"


# --- the $id index: json_utils --------------------------------------------------------------------------------------


def test_the_id_index_takes_the_host_schema_and_is_unchanged_without_a_folder(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    schema_dir = find_schema_dir(str(ROOT))
    assert schema_dir is not None
    toolkit = build_id_index(schema_dir)
    assert build_id_index(schema_dir, str(PLAIN_SPEC)) == toolkit and build_id_index(schema_dir, None) == toolkit
    assert build_id_index(schema_dir, str(spec)) == {**toolkit, URI: str(_schema_path(spec))}
    _edit_schema(spec, lambda document: document.update({"$id": "vc:core:atoms"}))
    assert build_id_index(schema_dir, str(spec)) == toolkit  # a host schema never takes a toolkit $id


def test_schema_discovery_answers_for_an_extension_file(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    data_file = str(spec / "extensions" / DATA_NAME)
    top = json.loads(json_schema_discovery(data_file, ".", str(ROOT)) or "{}")
    assert {"datastores", "tables", "validation_rules", "owner"} <= set(top)  # its own sections and step-base's
    columns = json.loads(json_schema_discovery(data_file, ".tables[0].columns", str(ROOT)) or "{}")
    assert columns["type"] == "array" and columns["minItems"] == 1
    table_id = json.loads(json_schema_discovery(data_file, ".tables[0].table_id", str(ROOT), spec_root=str(spec)) or "{}")
    assert table_id["type"] == "string" and "pattern" in table_id  # resolved through vc:core:atoms#kebabId
    assert json_utils.resolve_schema_path(data_file, str(ROOT)) == str(_schema_path(spec))


def test_the_json_schema_command_answers_on_the_path_of_an_extension_file(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    code, output = run_cli("json", "schema", str(spec / "extensions" / DATA_NAME), ".tables", "--repo-root", str(ROOT))
    assert code == 0, output
    assert json.loads(output)["type"] == "array"
    _schema_path(spec).unlink()
    code, output = run_cli("json", "schema", str(spec / "extensions" / DATA_NAME), ".tables", "--repo-root", str(ROOT))
    assert code == 1 and SCHEMA_PLACE in output  # X9: the text names the place of the missing schema
    assert "Traceback" not in output


def test_a_write_to_an_extension_file_is_checked_against_its_schema(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    data_file = spec / "extensions" / DATA_NAME
    with pytest.raises(JsonUtilsError, match=r"\.tables\[0\]\.columns: 'x' is not of type 'array'"):
        json_utils.json_patch(str(data_file), ".tables[0].columns", '"x"', repo_root=str(ROOT))
    assert "reset_tokens" not in data_file.read_text(encoding="utf-8")
    json_utils.json_patch(str(data_file), ".tables[0].name", '"reset_tokens"', repo_root=str(ROOT))
    assert _data(spec)["tables"][0]["name"] == "reset_tokens"


def test_check_edit_takes_the_spec_root_for_a_path_relative_to_it(tmp_path: Path) -> None:
    """The form of an id-keyed write: the file is named relative to the spec folder, so the folder is passed."""
    spec = _spec(tmp_path / "spec")
    relative = f"extensions/{DATA_NAME}"
    content = (spec / relative).read_text(encoding="utf-8")
    broken = _data(spec)
    broken["tables"][0]["columns"] = "x"
    check_edit(relative, content, content, str(ROOT), spec_root=str(spec))
    with pytest.raises(JsonUtilsError, match="'x' is not of type 'array'"):
        check_edit(relative, content, json.dumps(broken), str(ROOT), spec_root=str(spec))
    with pytest.raises(JsonUtilsError) as refusal:  # Y1: in no extensions folder, so not the data file of the URI it names
        check_edit(str(tmp_path / "elsewhere" / DATA_NAME), content, json.dumps(broken), str(ROOT))
    assert str(refusal.value).startswith("Could not ") and URI in str(refusal.value) and DATA_PLACE in str(refusal.value)
    assert "schema_registry.json" not in str(refusal.value) and "'x' is not of type" not in str(refusal.value)


# --- the scan and the step of a path --------------------------------------------------------------------------------


def test_the_artifact_scan_takes_the_data_file_and_skips_every_schema_file(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    (spec / "04_fr_list.json").write_text("{}", encoding="utf-8")
    (spec / "stray.schema.json").write_text("{}", encoding="utf-8")
    (spec / "impl_context").mkdir()
    (spec / "impl_context" / "deep.schema.json").write_text("{}", encoding="utf-8")
    found = sorted(os.path.relpath(path, spec) for path in iter_spec_artifacts(str(spec)))
    assert found == ["04_fr_list.json", f"extensions/{DATA_NAME}"]


def test_a_schema_file_added_to_a_spec_changes_nothing_in_the_scan_and_a_data_file_does(tmp_path: Path) -> None:
    spec = tmp_path / "spec"
    shutil.copytree(PLAIN_SPEC, spec)
    before = sorted(iter_spec_artifacts(str(spec)))
    assert str(spec / "13_extension_manifest.json") in before
    (spec / "extensions").mkdir()
    (spec / "extensions" / SCHEMA_NAME).write_text("{}", encoding="utf-8")
    (spec / "top.schema.json").write_text("{}", encoding="utf-8")
    assert sorted(iter_spec_artifacts(str(spec))) == before
    (spec / "extensions" / DATA_NAME).write_text("{}", encoding="utf-8")
    assert sorted(iter_spec_artifacts(str(spec))) == sorted([*before, str(spec / "extensions" / DATA_NAME)])


STEP_13_PATHS = [  # X4 with S4: exactly two parts, ``extensions/<any name>.json``
    f"extensions/{DATA_NAME}", f"extensions/{SCHEMA_NAME}", "extensions/notes.json", "extensions/ext-01-database.json",
]
NOT_JSON_PATHS = ["extensions/README.md", "extensions/ext_01_database.yaml", "extensions/json"]
"""S4 (H7): step 13 owns the JSON files of the folder; any other file there is no step's, as at 673b5fa."""
NOT_STEP_13_PATHS = ["extensions/sub/x.json", "impl_context/extensions/ext_01_x.json", "ext_01_x.json", *NOT_JSON_PATHS]
OTHER_STEPS = {"13_extension_manifest.json": "13", "04_fr_list.json": "04", "impl_context/ms_account_recovery_plan.json": "16a"}


def test_the_step_of_a_path(tmp_path: Path) -> None:
    """One test for the whole table, so the old rows cannot pass alone: a file directly in the spec's ``extensions`` folder is step 13.

    Each path is asked relative to the spec folder (the form of the rule) and as the absolute path of the same file.
    """
    spec = tmp_path / "host" / "spec"
    for prefix in ("", f"{spec}/"):
        assert {path: get_step_from_path(prefix + path) for path in STEP_13_PATHS} == {path: "13" for path in STEP_13_PATHS}
        assert [path for path in NOT_STEP_13_PATHS if get_step_from_path(prefix + path) == "13"] == []
        assert {path: get_step_from_path(prefix + path) for path in OTHER_STEPS} == OTHER_STEPS
        assert [path for path in STEP_13_PATHS if not is_extension_file(prefix + path)] == []
        assert [path for path in [*NOT_STEP_13_PATHS, *OTHER_STEPS] if is_extension_file(prefix + path)] == []


KNOWN_STEP_13_PATHS = [*STEP_13_PATHS, "extensions/04_notes.json", "extensions/16_impl_context.json", "extensions/13_extension_manifest.json"]
KNOWN_NOT_STEP_13_PATHS = {  # Z2(a): no file anywhere else is one; each keeps the step 673b5fa gives it
    "extensions/sub/x.json": "unknown", "ext_01_x.json": "unknown", "notes.json": "unknown",
    "common/extensions/x.json": "unknown", f"sub/extensions/{DATA_NAME}": "unknown", "impl_context/extensions/ext_01_x.json": "unknown",
    **{path: "unknown" for path in NOT_JSON_PATHS},
}


def test_the_step_of_a_path_with_the_spec_folder_known_is_decided_by_the_place_and_not_by_the_name(tmp_path: Path) -> None:
    """Z2(a): exactly ``extensions/<name>`` under the spec folder, whatever the name, and no file anywhere else."""
    spec = tmp_path / "host" / "spec"
    known = str(spec)
    assert {path: get_step_from_path(f"{spec}/{path}", known) for path in KNOWN_STEP_13_PATHS} == {path: "13" for path in KNOWN_STEP_13_PATHS}
    assert [path for path in KNOWN_STEP_13_PATHS if not is_extension_file(f"{spec}/{path}", known)] == []
    assert {path: get_step_from_path(f"{spec}/{path}", known) for path in KNOWN_NOT_STEP_13_PATHS} == KNOWN_NOT_STEP_13_PATHS
    assert {path: get_step_from_path(f"{spec}/{path}", known) for path in OTHER_STEPS} == OTHER_STEPS
    assert [path for path in [*KNOWN_NOT_STEP_13_PATHS, *OTHER_STEPS] if is_extension_file(f"{spec}/{path}", known)] == []
    assert not is_extension_file(str(tmp_path / "another" / "extensions" / DATA_NAME), known)  # a file of no folder of this spec
    # the spec folder is the same folder however it is named: by a link, with a slash at its end, from the current folder
    (spec / "extensions").mkdir(parents=True)
    (tmp_path / "link").symlink_to(spec, target_is_directory=True)
    assert is_extension_file(str(tmp_path / "link" / "extensions" / DATA_NAME), known)
    assert is_extension_file(f"{spec}/extensions/{DATA_NAME}", str(tmp_path / "link") + os.sep)
    assert not is_extension_file(str(tmp_path / "link" / "common" / "extensions" / "x.json"), known)


def test_the_step_that_owns_a_file_is_read_with_the_spec_folder_where_the_caller_knows_it(tmp_path: Path) -> None:
    """``step_of_spec_file``: what ``spec-check`` stamps on the finding of a file (Z2(a): owner by place)."""
    spec = tmp_path / "host" / "spec"
    known = str(spec)
    assert step_of_spec_file(f"{spec}/extensions/04_notes.json", {}, known) == "13"
    assert step_of_spec_file(f"{spec}/extensions/04_notes.json", {}) == "04"  # by the path alone the name keeps its step
    assert step_of_spec_file(f"{spec}/common/extensions/x.json", {}, known) is None  # a file of no step
    assert step_of_spec_file(f"{spec}/common/extensions/x.json", {}) == "13"  # the path alone: the folder above is taken for the spec folder
    assert step_of_spec_file(f"{spec}/04_fr_list.json", {}, known) == "04" and step_of_spec_file(f"{spec}/notes.json", {}, known) is None
    plan = f"{spec}/impl_context/ms_account_recovery_plan.json"
    assert step_of_spec_file(plan, {}, known) == "16a" and step_of_spec_file(plan, {"review": {"verdict": "PASS"}}, known) == "16c"


def test_a_spec_folder_that_is_itself_called_extensions_is_a_spec_folder_like_any_other(tmp_path: Path) -> None:
    """Z2(b) with the spec folder known, Z2(c) by the path alone."""
    spec = tmp_path / "host" / "extensions"
    known = str(spec)
    step_files = {"04_fr_list.json": "04", "13_extension_manifest.json": "13", "16_impl_context.json": "16"}
    # (b) the spec folder is known: its extension files are step 13, its step files keep their step, a file at its top is no extension file
    assert is_extension_file(str(spec / "extensions" / DATA_NAME), known)
    assert get_step_from_path(str(spec / "extensions" / DATA_NAME), known) == "13"
    assert {name: get_step_from_path(str(spec / name), known) for name in step_files} == step_files
    assert [name for name in (*step_files, "notes.json", DATA_NAME) if is_extension_file(str(spec / name), known)] == []
    assert get_step_from_path(str(spec / "notes.json"), known) == "unknown"
    assert get_step_from_path(str(spec / "impl_context" / "ms_account_recovery_plan.json"), known) == "16a"
    # (c) by the path alone the folder above a folder called extensions is taken for the spec folder, and a file
    # named like a step file keeps its step
    for prefix in ("extensions/", f"{spec}/"):
        assert {name: get_step_from_path(prefix + name) for name in step_files} == step_files
        assert [name for name in step_files if is_extension_file(prefix + name)] == []
    assert spec_root_of(str(spec / "04_fr_list.json")) is None
    assert get_step_from_path(str(spec / "impl_context" / "ms_account_recovery_plan.json")) == "16a"
    assert is_extension_file(str(spec / "extensions" / DATA_NAME)) and spec_root_of(str(spec / "extensions" / DATA_NAME)) == known


def test_by_its_path_alone_the_data_file_of_a_spec_folder_called_extensions_is_read_and_written(tmp_path: Path) -> None:
    """Z2(c): never "move this file there" for a file that is where it belongs."""
    spec = _spec(tmp_path / "host" / "extensions")
    data_file = spec / "extensions" / DATA_NAME
    assert json.loads(json_schema_discovery(str(data_file), ".tables", str(ROOT)))["type"] == "array"
    json_utils.json_patch(str(data_file), ".tables[0].name", '"reset_tokens"', repo_root=str(ROOT))
    assert json.loads(data_file.read_text(encoding="utf-8"))["tables"][0]["name"] == "reset_tokens"
    assert schema_violations(str(ROOT), _data(spec), str(spec)) == []


# --- X3: the draft of a host schema ---------------------------------------------------------------------------------

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"


def _set_dialect(spec: Path, value: Any) -> None:
    _edit_schema(spec, lambda document: document.update({"$schema": value}))


def test_a_host_schema_with_no_dialect_or_draft_2020_12_is_accepted_and_any_other_is_refused(tmp_path: Path) -> None:
    toolkit = get_shared_registry(str(ROOT)).map
    spec = _spec(tmp_path / "spec")
    _set_dialect(spec, DRAFT_2020_12)
    assert list(find_host_schemas(str(spec), toolkit).accepted) == [URI]
    _edit_schema(spec, lambda document: document.pop("$schema"))
    assert list(find_host_schemas(str(spec), toolkit).accepted) == [URI]
    for value, shown in (("http://json-schema.org/draft-07/schema#", "http://json-schema.org/draft-07/schema#"),
                         ("https://json-schema.org/draft/2020-12/shcema", "https://json-schema.org/draft/2020-12/shcema"), (7, "7")):
        _set_dialect(spec, value)
        found = find_host_schemas(str(spec), toolkit)
        assert found.accepted == {} and list(found.refused) == [SCHEMA_NAME], value
        assert shown in found.refused[SCHEMA_NAME] and DRAFT_2020_12 in found.refused[SCHEMA_NAME], found.refused


# --- X9, X7: what a schema file that cannot serve is told -----------------------------------------------------------


@pytest.mark.parametrize("text", ["true", "[]", "7", '"a string"'])
def test_a_schema_file_that_is_not_an_object_is_told_what_an_extension_schema_must_be(tmp_path: Path, text: str) -> None:
    """``true`` is a JSON Schema, so "not a JSON Schema" would be false: an extension schema must be a JSON object with an ``$id``."""
    spec = _spec(tmp_path / "spec")
    _schema_path(spec).write_text(text, encoding="utf-8")
    found = find_host_schemas(str(spec))
    assert found.accepted == {} and list(found.refused) == [SCHEMA_NAME]
    reason = found.refused[SCHEMA_NAME]
    assert "JSON object" in reason and "$id" in reason and "not a valid JSON Schema" not in reason, reason
    assert "is a JSON object" not in reason, reason  # the file is not one: the text may not say that it is


@pytest.mark.parametrize("value", ["", 5, None, [], {}])
def test_an_empty_or_non_string_id_is_no_id(tmp_path: Path, value: Any) -> None:
    spec = _spec(tmp_path / "spec")
    _edit_schema(spec, lambda document: document.update({"$id": value}))
    reason = find_host_schemas(str(spec), get_shared_registry(str(ROOT)).map).refused[SCHEMA_NAME]
    assert re.search(r'has no "?\$id"?', reason) and "has the" not in reason, reason
    assert URI in reason  # and the reason gives the one its file name asks for


def _unreadable(path: Path) -> None:
    path.chmod(0)


def _folder_in_its_place(path: Path) -> None:
    path.unlink()
    path.mkdir()


def _dangling_link_in_its_place(path: Path) -> None:
    path.unlink()
    path.symlink_to(path.parent / "no-such-file")


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a file of mode 000")
@pytest.mark.parametrize("damage", [_unreadable, _folder_in_its_place, _dangling_link_in_its_place])
def test_a_schema_file_that_cannot_be_read_is_refused_with_a_reason(tmp_path: Path, damage: Any) -> None:
    spec = _spec(tmp_path / "spec")
    damage(_schema_path(spec))
    try:
        found = find_host_schemas(str(spec), get_shared_registry(str(ROOT)).map)
        assert found.accepted == {} and list(found.refused) == [SCHEMA_NAME]
        assert isinstance(found.refused[SCHEMA_NAME], str) and found.refused[SCHEMA_NAME].strip()
        assert get_shared_registry(str(ROOT), str(spec)) is get_shared_registry(str(ROOT))
        with pytest.raises(SchemaNotFoundError):
            validate_data_against_schema(str(ROOT), _data(spec), str(spec))
    finally:
        if _schema_path(spec).is_file() and not _schema_path(spec).is_symlink():
            _schema_path(spec).chmod(0o644)


@pytest.mark.skipif(os.geteuid() == 0, reason="root lists a folder of mode 000")
def test_an_extensions_folder_that_cannot_be_listed_is_the_answer_of_no_folder(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    assert find_host_schemas(str(spec)) is not NO_HOST_SCHEMAS
    (spec / "extensions").chmod(0)
    try:
        assert find_host_schemas(str(spec)) is NO_HOST_SCHEMAS
        assert get_shared_registry(str(ROOT), str(spec)) is get_shared_registry(str(ROOT))
    finally:
        (spec / "extensions").chmod(0o755)


# --- X7: one host schema that refers to another ---------------------------------------------------------------------


def test_a_host_schema_may_ref_another_host_schema_after_the_toolkit_registry_was_used(tmp_path: Path) -> None:
    """The toolkit's registry has resolved references before the host's is derived from it: the host's must see its own schemas."""
    manifest = json.loads((PLAIN_SPEC / "13_extension_manifest.json").read_text(encoding="utf-8"))
    assert validate_data_against_schema(str(ROOT), manifest) == []  # the toolkit registry, used first
    spec = _spec(tmp_path / "spec")
    (spec / "extensions" / "ext_02_cache.schema.json").write_text(json.dumps({
        "$id": "vc:ext-02-cache",
        "type": "object",
        "required": ["caches"],
        "properties": {"$schema": {"type": "string"}, "caches": {"type": "array", "items": {"$ref": f"{URI}#/properties/tables/items/properties/columns"}}},
    }), encoding="utf-8")
    good = {"$schema": "vc:ext-02-cache", "caches": [[{"name": "cache_key", "type": "text"}]]}
    assert validate_data_against_schema(str(ROOT), good, str(spec)) == []
    bad = {"$schema": "vc:ext-02-cache", "caches": ["not columns"]}
    assert [path for path, _message in validate_data_against_schema(str(ROOT), bad, str(spec))] == [("caches", 0)]


# --- X7: a file that is no extension file keeps the texts of 673b5fa -------------------------------------------------


def test_a_file_outside_the_folder_with_an_unknown_schema_gets_the_texts_of_the_base_commit(tmp_path: Path) -> None:
    """``vc:no-such`` is not the URI of an extension and the file is not in an ``extensions`` folder: both texts are those of 673b5fa."""
    other = tmp_path / "spec" / "notes.json"
    other.parent.mkdir()
    other.write_text(json.dumps({"$schema": "vc:no-such", "name": "a"}), encoding="utf-8")
    with pytest.raises(JsonUtilsError) as refused:
        json_utils.json_patch(str(other), ".name", '"b"', repo_root=str(ROOT))
    assert str(refused.value) == (
        f"Could not locate schema for {other} ($schema URI: vc:no-such); "
        "refusing to write. Check --repo-root points to the toolkit root and "
        "that the $schema URI is registered in tools/schema_registry.json."
    )
    with pytest.raises(JsonUtilsError) as unresolved:
        json_schema_discovery(str(other), ".name", str(ROOT))
    assert str(unresolved.value) == (
        f"Could not resolve schema for {other}. "
        "Make sure it has a $schema field and the schema directory is accessible."
    )
    with pytest.raises(FileNotFoundError) as missing:  # the registry itself: the words of 673b5fa (core/registry.py:102-104)
        get_shared_registry(str(ROOT), str(other.parent)).load("vc:no-such")
    assert str(missing.value) == (
        "Schema not found for vc:no-such: expected None. "
        "Check tools/schema_registry.json for the correct URI mapping "
        "and verify --repo-root points to the devspec_toolkit directory."
    )


def test_json_schema_and_json_patch_on_a_data_file_whose_schema_is_missing_both_name_its_place(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    data_file = str(spec / "extensions" / DATA_NAME)
    _schema_path(spec).unlink()
    with pytest.raises(JsonUtilsError) as unresolved:
        json_schema_discovery(data_file, ".tables", str(ROOT))
    with pytest.raises(JsonUtilsError) as refused:
        json_utils.json_patch(data_file, ".tables[0].name", '"reset_tokens"', repo_root=str(ROOT))
    for text in (str(unresolved.value), str(refused.value)):
        assert SCHEMA_PLACE in text and "tools/schema_registry.json" not in text, text
        assert text.startswith("Could not "), text  # a refusal opens as every refusal of these two commands does at 673b5fa


@pytest.mark.parametrize("text", ["5", "[]", '"a string"', "null"])
def test_json_schema_on_a_data_file_that_is_not_an_object_is_a_refusal_and_no_other_exception(tmp_path: Path, text: str) -> None:
    """A data file with no ``$schema`` to read is refused in the command's own words (``JsonUtilsError``): never a traceback."""
    spec = _spec(tmp_path / "spec")
    data_file = spec / "extensions" / DATA_NAME
    data_file.write_text(text, encoding="utf-8")
    with pytest.raises(JsonUtilsError):
        json_schema_discovery(str(data_file), ".", str(ROOT))


def test_json_patch_and_json_schema_do_not_judge_a_data_file_by_the_schema_of_another_extension(tmp_path: Path) -> None:
    """X2 on the two commands that read one file: the ``$schema`` of the data file is the URI its file name gives."""
    spec = _spec(tmp_path / "spec")
    (spec / "extensions" / "ext_02_cache.schema.json").write_text(json.dumps({"$id": "vc:ext-02-cache", "type": "object"}), encoding="utf-8")
    data_file = spec / "extensions" / DATA_NAME
    json_utils.json_patch(str(data_file), ".tables[0].name", '"reset_tokens"', repo_root=str(ROOT))  # its own schema: written
    assert json.loads(data_file.read_text(encoding="utf-8"))["tables"][0]["name"] == "reset_tokens"
    document = json.loads(data_file.read_text(encoding="utf-8"))
    document["$schema"] = "vc:ext-02-cache"  # accepted, and it would let any write through
    data_file.write_text(json.dumps(document), encoding="utf-8")
    before = data_file.read_text(encoding="utf-8")
    with pytest.raises(JsonUtilsError) as refused:
        json_utils.json_patch(str(data_file), ".tables[0].name", '"tokens"', repo_root=str(ROOT))
    with pytest.raises(JsonUtilsError) as unresolved:
        json_schema_discovery(str(data_file), ".tables", str(ROOT))
    for text in (str(refused.value), str(unresolved.value)):
        assert f"extensions/{DATA_NAME}" in text and URI in text and "vc:ext-02-cache" in text, text
        assert text.startswith("Could not "), text
    assert data_file.read_text(encoding="utf-8") == before


# --- X1: the spec folder and the project canon of a file of the extensions folder ----------------------------------


def test_the_spec_folder_of_a_file_is_what_the_caller_knows_and_else_the_folder_above_its_extensions_folder(tmp_path: Path) -> None:
    spec = tmp_path / "host" / "spec"
    (spec / "extensions").mkdir(parents=True)
    data, other = str(spec / "extensions" / DATA_NAME), str(spec / "04_fr_list.json")
    assert spec_root_for(data) == str(spec) and spec_root_for(other) is None  # nothing known: the folder above, or nothing
    assert spec_root_for(data, str(spec)) == str(spec) and spec_root_for(other, str(spec)) == str(spec)
    elsewhere = str(tmp_path / "baseline" / "spec")
    assert spec_root_for(data, elsewhere) == elsewhere  # what the caller knows is kept


def test_with_the_spec_folder_known_the_extensions_folder_is_the_same_folder_however_it_is_reached(tmp_path: Path) -> None:
    """S2 (H5): one file, one answer.  The folder of the file is compared with ``<spec>/extensions`` as a folder on disk."""
    spec = _spec(tmp_path / "host" / "spec")
    known = str(spec)
    (spec / "common").mkdir()
    (tmp_path / "to_the_folder").symlink_to(spec / "extensions", target_is_directory=True)
    (tmp_path / "to_another").symlink_to(spec / "common", target_is_directory=True)
    through = str(tmp_path / "to_the_folder" / DATA_NAME)
    assert is_extension_file(through, known) and get_step_from_path(through, known) == "13"
    assert schema_uri_problem(through, _data(spec), known) is None  # judged as by its plain path: it is the data file
    assert schema_violations(str(ROOT), _data(spec), known) == []
    assert not is_extension_file(str(tmp_path / "to_another" / DATA_NAME), known)
    assert get_step_from_path(str(tmp_path / "to_another" / DATA_NAME), known) == "unknown"
    assert not is_extension_file(through)  # by the path alone the typed name decides
    # a folder that is not on disk is still compared: the place of a file a commit deleted
    gone = tmp_path / "gone" / "spec"
    assert is_extension_file(str(gone / "extensions" / DATA_NAME), str(gone)) and not is_extension_file(str(gone / "other" / DATA_NAME), str(gone))


def test_where_the_file_system_ignores_case_the_extensions_folder_typed_in_another_case_is_the_same_folder(tmp_path: Path) -> None:
    """S2 (H5b): ``spec/Extensions/ext_01_database.json`` with the spec folder known; by the path alone the typed name decides."""
    spec = _spec(tmp_path / "host" / "spec")
    typed = spec / "Extensions" / DATA_NAME
    if not typed.is_file():
        pytest.skip("this file system keeps case: spec/Extensions is another folder")
    assert is_extension_file(str(typed), str(spec)) and get_step_from_path(str(typed), str(spec)) == "13"
    assert schema_uri_problem(str(typed), _data(spec), str(spec)) is None
    assert not is_extension_file(str(typed))


def test_the_data_file_at_the_top_of_a_spec_folder_called_extensions_is_told_the_way_out(tmp_path: Path) -> None:
    """S1: a command run on ``<spec>/extensions`` with no ``--spec-root`` takes that folder for the spec folder it was told.

    The data file then lies at the top of a spec folder, where Y1 refuses it; its text gains the way out (the spec
    folder, ``--spec-root``).  No other file gets the sentence: for no other file is it the way out.
    """
    document = {"$schema": URI}
    handed = tmp_path / "host" / "spec" / "extensions"
    text = schema_uri_problem(str(handed / DATA_NAME), document, str(handed))
    assert text is not None and "move this file there" in text and "--spec-root" in text and "spec folder" in text.split("if it is not")[1], text
    assert schema_uri_problem(str(handed / DATA_NAME), document, str(handed) + os.sep) == text
    others = {
        "the 1.1.1 place in a spec folder of another name": (handed.parent / DATA_NAME, handed.parent),
        "a file of the folder not named for an extension": (handed / "notes.json", handed),
        "a file named for another extension than the one it names": (handed / "ext_02_cache.json", handed),
        "a file below the top of the folder": (handed / "sub" / DATA_NAME, handed),
        "a file of another folder called extensions": (handed.parent / "common" / "extensions" / DATA_NAME, handed.parent),
    }
    for case, (path, known) in others.items():
        text = schema_uri_problem(str(path), document, str(known))
        assert text is not None and "move this file there" in text and "--spec-root" not in text, (case, text)


@pytest.mark.parametrize("spec_name", ["spec", "extensions"])
def test_the_legacy_text_of_a_step_reads_a_captured_path_from_the_spec_folder_and_not_from_the_current_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spec_name: str,
) -> None:
    """S5 (H8): the capture lists paths relative to the spec folder; the step of each is the same from every current folder.

    The spec folder is known there, so its place decides (a spec folder called ``extensions`` too), not the path alone.
    """
    host = tmp_path / "host"
    spec = host / spec_name
    captured = ("04_fr_list.json", "entry_key_registry.json", DATA_NAME, "extensions/notes.json")
    for name in captured:
        (spec / name).parent.mkdir(parents=True, exist_ok=True)
        (spec / name).write_text(json.dumps({"captured": name}), encoding="utf-8")
    git(host, "init", "-q", "-b", "main")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "the spec as it was")
    head = git(host, "rev-parse", "HEAD")
    capture = spec / "extras" / "migration" / "capture.json"
    capture.parent.mkdir(parents=True)
    capture.write_text(json.dumps({"source": {"commit": head, "spec_dir": spec_name, "file_hashes": {name: "x" for name in captured}}}), encoding="utf-8")
    answers = {}
    for current in ("extensions", "spec"):
        folder = tmp_path / "current" / current
        folder.mkdir(parents=True)
        monkeypatch.chdir(folder)
        of_13 = triage.legacy_text(str(spec), str(ROOT), "13", str(host))
        assert "=== extensions/notes.json at" in of_13, of_13  # a file of the folder is step 13's
        assert DATA_NAME not in of_13 and "entry_key_registry.json" not in of_13, (current, of_13)  # a file of no step at the top is not
        answers[current] = (of_13, triage.legacy_text(str(spec), str(ROOT), "04", str(host)))
    assert answers["extensions"] == answers["spec"] and "=== 04_fr_list.json at" in answers["spec"][1]


def test_only_the_data_file_of_an_extension_has_a_schema_uri_its_name_gives(tmp_path: Path) -> None:
    """The rule of X2 at its edges: which files it reads, and which values it takes."""
    folder = tmp_path / "spec" / "extensions"
    right = {"$schema": URI}
    assert schema_uri_problem(str(folder / DATA_NAME), right) is None
    assert schema_uri_problem(str(folder / DATA_NAME), {"$schema": f" {URI} "}) is None  # read as validation reads it: stripped
    for wrong in ({"$schema": "vc:ext-1-database"}, {"$schema": 5}, {"$schema": None}, {"$schema": ""}, {}):
        text = schema_uri_problem(str(folder / DATA_NAME), wrong)
        assert text is not None and f"extensions/{DATA_NAME}" in text and URI in text, (wrong, text)
    assert 'no "$schema"' in str(schema_uri_problem(str(folder / DATA_NAME), {}))
    # not the data file of an extension: the schema file, a file not named for one, a file elsewhere, a document that is no object
    toolkit_uris = [uri for uri, place in get_shared_registry(str(ROOT)).map.items() if place in TOOLKIT_SCHEMA_FILES]
    assert len(toolkit_uris) == len(TOOLKIT_SCHEMA_FILES)
    for uri in ("vc:04-functional-requirements", *toolkit_uris):  # a URI no schema has, and three the toolkit does hold (Z4)
        wrong = {"$schema": uri}
        assert schema_uri_problem(str(folder / SCHEMA_NAME), wrong) is None
        assert schema_uri_problem(str(folder / "notes.json"), wrong) is None
        assert schema_uri_problem(str(tmp_path / "spec" / DATA_NAME), wrong) is None
        assert schema_uri_problem(str(tmp_path / "spec" / "impl_context" / "extensions" / DATA_NAME), wrong) is None
        text = schema_uri_problem(str(folder / DATA_NAME), wrong)  # the data file may name none of them
        assert text is not None and uri in text and URI in text and DATA_PLACE in text, (uri, text)
    assert schema_uri_problem(str(folder / DATA_NAME), ["not an object"]) is None


# --- Y1: json patch and json schema on a file that names an extension schema and is not its data file ---------------

Y1_FILES = ["notes.json", DATA_NAME, "extensions/notes.json", "impl_context/x.json"]
Y1_RUNS = [(relative, True) for relative in Y1_FILES] + [(relative, False) for relative in Y1_FILES if not relative.startswith("extensions/")]


@pytest.mark.parametrize(("relative", "with_the_folder"), Y1_RUNS)
def test_json_patch_and_json_schema_refuse_a_file_that_names_an_extension_schema_and_is_not_its_data_file(
    tmp_path: Path, relative: str, with_the_folder: bool,
) -> None:
    """Y1 on the commands that read one file, with and without a spec folder known: a refusal, in the same words, and no write."""
    spec = _spec(tmp_path / "spec")
    if not with_the_folder:
        shutil.rmtree(spec / "extensions")
    path = spec / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    before = json.dumps({"$schema": URI, "name": "a"})
    after = json.dumps({"$schema": URI, "name": "b"})
    path.write_text(before, encoding="utf-8")
    calls = {
        "json patch": lambda: json_utils.json_patch(str(path), ".name", '"b"', repo_root=str(ROOT)),
        "a write, the spec folder known": lambda: check_edit(str(path), before, after, str(ROOT), spec_root=str(spec)),
        "a write by a path relative to the spec folder": lambda: check_edit(relative, before, after, str(ROOT), spec_root=str(spec)),
        "json schema": lambda: json_schema_discovery(str(path), ".name", str(ROOT)),
        "json schema, the spec folder known": lambda: json_schema_discovery(str(path), ".name", str(ROOT), str(spec)),
    }
    for name, call in calls.items():
        with pytest.raises(JsonUtilsError) as refused:
            call()
        text = str(refused.value)
        assert text.startswith("Could not "), (name, text)
        assert path.name in text and URI in text and DATA_PLACE in text, (name, text)
        assert "tools/schema_registry.json" not in text and "--repo-root" not in text and "write that file" not in text.lower(), (name, text)
    assert path.read_text(encoding="utf-8") == before


def test_json_patch_and_json_schema_on_the_right_data_file_are_unchanged_by_the_rule(tmp_path: Path) -> None:
    """Next to Y1: the data file of the URI, by its own path and by a path relative to the spec folder, is written and read."""
    spec = _spec(tmp_path / "spec")
    data_file = spec / "extensions" / DATA_NAME
    content = data_file.read_text(encoding="utf-8")
    check_edit(str(data_file), content, content, str(ROOT), spec_root=str(spec))
    check_edit(f"extensions/{DATA_NAME}", content, content, str(ROOT), spec_root=str(spec))
    assert "tables" in json_schema_discovery(str(data_file), ".", str(ROOT), str(spec))
    json_utils.json_patch(str(data_file), ".tables[0].name", '"reset_tokens"', repo_root=str(ROOT))
    assert json.loads(data_file.read_text(encoding="utf-8"))["tables"][0]["name"] == "reset_tokens"


def test_a_write_by_a_relative_path_into_a_nested_extensions_folder_is_not_a_write_to_the_data_file(tmp_path: Path) -> None:
    """Y1 with the spec folder known: ``sub/extensions/ext_01_database.json`` relative to it is not ``extensions/ext_01_database.json``."""
    spec = _spec(tmp_path / "spec")
    content = (spec / "extensions" / DATA_NAME).read_text(encoding="utf-8")
    check_edit(f"extensions/{DATA_NAME}", content, content, str(ROOT), spec_root=str(spec))
    with pytest.raises(JsonUtilsError) as refused:
        check_edit(f"sub/extensions/{DATA_NAME}", content, content, str(ROOT), spec_root=str(spec))
    nested = spec / "sub" / "extensions"
    shutil.copytree(spec / "extensions", nested)
    with pytest.raises(JsonUtilsError) as unresolved:
        json_schema_discovery(str(nested / DATA_NAME), ".", str(ROOT), str(spec))
    for text in (str(refused.value), str(unresolved.value)):
        assert text.startswith("Could not ") and URI in text and DATA_PLACE in text, text
    assert "tables" in json_schema_discovery(str(nested / DATA_NAME), ".", str(ROOT))  # by its path alone: the schema beside it


# --- Z1: a path names the same file however it is typed ------------------------------------------------------------

RIGHT_FORMS = {  # name: (the current folder, relative to the spec folder; the path as typed)
    "the bare name, from the folder": ("extensions", DATA_NAME),
    "./name, from the folder": ("extensions", f"./{DATA_NAME}"),
    "../extensions/name, from the folder": ("extensions", f"../extensions/{DATA_NAME}"),
    "extensions/name, from the spec folder": (".", f"extensions/{DATA_NAME}"),
    "the absolute path, from a folder that has nothing to do with the host": (None, None),
}
STRAY_FORMS = {
    "the bare name, from the spec folder": (".", "notes.json"),
    "../name, from the folder": ("extensions", "../notes.json"),
    "the absolute path, from a folder that has nothing to do with the host": (None, None),
}
NEW_RULE = {"name": "a reset token is short-lived", "check": "No row of reset_token has an expires_at more than one day after it was written."}


def _typed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, spec: Path, form: tuple[str | None, str | None], absolute: Path) -> str:
    """Go to the current folder of *form* and give the path as a person types it there."""
    cwd, typed = form
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(exist_ok=True)
    monkeypatch.chdir(elsewhere if cwd is None else spec / cwd)
    return str(absolute) if typed is None else typed


def test_the_right_data_file_is_read_and_written_however_its_path_is_typed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Z1: ``json schema`` prints the schema, ``json patch``, ``json insert`` and ``json delete`` write, ``validate`` says OK; one answer for all five forms."""
    answers = {}
    for index, (name, form) in enumerate(RIGHT_FORMS.items()):
        spec = tmp_path / f"host{index}" / "spec"
        shutil.copytree(PLAIN_SPEC, spec)  # the worked example: the data file names a term of its project canon
        _spec(spec)
        data_file = spec / "extensions" / DATA_NAME
        typed = _typed(monkeypatch, tmp_path, spec, form, data_file)
        root = ("--repo-root", str(ROOT))
        runs = {
            "json schema": run_cli("json", "schema", typed, ".tables", *root),
            "json patch": run_cli("json", "patch", typed, ".datastores[0].name", '"Identity database"', *root),
            "json insert": run_cli("json", "insert", typed, ".validation_rules", json.dumps(NEW_RULE), *root),
            "json delete": run_cli("json", "delete", typed, ".validation_rules[0]", *root),
            "validate": run_cli("validate", typed, *root),
        }
        assert {command: code for command, (code, _output) in runs.items()} == {command: 0 for command in runs}, (name, runs)
        written = json.loads(data_file.read_text(encoding="utf-8"))
        assert written["datastores"][0]["name"] == "Identity database" and written["validation_rules"][-1] == NEW_RULE, name
        assert len(written["validation_rules"]) == 2 and "OK" in runs["validate"][1], (name, runs["validate"])
        answers[name] = (json.loads(runs["json schema"][1]), written)
    first = next(iter(answers.values()))
    assert first[0]["type"] == "array" and all(answer == first for answer in answers.values())


def test_a_stray_file_is_refused_however_its_path_is_typed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Z1 for Y1: ``<spec>/notes.json`` names the extension schema; the refusal is the same from every folder."""
    for index, (name, form) in enumerate(STRAY_FORMS.items()):
        spec = _spec(tmp_path / f"host{index}" / "spec")
        stray = spec / "notes.json"
        before = json.dumps({"$schema": URI, "name": "a"})
        stray.write_text(before, encoding="utf-8")
        typed = _typed(monkeypatch, tmp_path, spec, form, stray)
        root = ("--repo-root", str(ROOT))
        for command in (("json", "schema", typed, ".name"), ("json", "patch", typed, ".name", '"b"'), ("validate", typed)):
            code, output = run_cli(*command, *root)
            assert code == 1 and URI in output and DATA_PLACE in output and "Traceback" not in output, (name, command, output)
            assert command[0] == "validate" or "Could not " in output, (name, command, output)
        assert stray.read_text(encoding="utf-8") == before, name


def test_a_write_named_relative_to_the_spec_folder_is_read_so_from_whatever_folder_it_is_made(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The contract of ``check_edit``: with the spec folder, a relative path is relative to it, not to the current folder."""
    spec = _spec(tmp_path / "spec")
    content = (spec / "extensions" / DATA_NAME).read_text(encoding="utf-8")
    for cwd in (tmp_path, spec, spec / "extensions"):
        monkeypatch.chdir(cwd)
        check_edit(f"extensions/{DATA_NAME}", content, content, str(ROOT), spec_root=str(spec))
        with pytest.raises(JsonUtilsError) as refused:  # <spec>/ext_01_database.json: the 1.1.1 place, not the data file
            check_edit(DATA_NAME, content, content, str(ROOT), spec_root=str(spec))
        assert URI in str(refused.value) and DATA_PLACE in str(refused.value), (cwd, str(refused.value))


def test_a_write_named_relative_to_a_spec_folder_called_extensions_is_judged_by_the_schema_of_its_folder(tmp_path: Path) -> None:
    """Z2(b): what an id-keyed write calls, with the spec folder known."""
    spec = _spec(tmp_path / "host" / "extensions")
    content = (spec / "extensions" / DATA_NAME).read_text(encoding="utf-8")
    check_edit(f"extensions/{DATA_NAME}", content, content, str(ROOT), spec_root=str(spec))
    broken = json.loads(content)
    broken["tables"][0]["columns"] = "x"
    with pytest.raises(JsonUtilsError) as refused:
        check_edit(f"extensions/{DATA_NAME}", content, json.dumps(broken), str(ROOT), spec_root=str(spec))
    assert "columns" in str(refused.value) and "move this file" not in str(refused.value), str(refused.value)


def test_the_project_canon_of_one_extension_file_is_that_of_its_spec_folder(tmp_path: Path) -> None:
    """``validate <file>`` looks for the canon beside the file; for a file of the extensions folder it is one folder up."""
    project_canon_of_file = host_schemas.project_canon_of_file
    spec = tmp_path / "host" / "spec"
    (spec / "extensions").mkdir(parents=True)
    data, top = str(spec / "extensions" / DATA_NAME), str(spec / "04_fr_list.json")
    assert project_canon_of_file(data, None, None) is None and project_canon_of_file(data, str(spec), None) is None  # the spec has no canon
    (spec / "canon").mkdir()
    assert project_canon_of_file(data, None, None) == str(spec / "canon")  # by the path alone
    assert project_canon_of_file(data, str(spec), None) == str(spec / "canon")  # with the spec folder known
    assert project_canon_of_file(data, str(spec), "/the/caller/found") == "/the/caller/found"
    assert project_canon_of_file(top, str(spec), None) is None and project_canon_of_file(top, None, None) is None  # any other file: as handed
    nested = str(spec / "sub" / "extensions" / DATA_NAME)
    assert project_canon_of_file(nested, str(spec), None) is None  # not a file of the folder of the known spec
    step_named = str(spec / "extensions" / "04_notes.json")  # of the folder by its place; by its path alone a step file, canon beside it
    assert project_canon_of_file(step_named, str(spec), None) == str(spec / "canon") and project_canon_of_file(step_named, None, None) is None
    (spec / "canon").rmdir()
    (spec / "canon").write_text("a file, not a folder", encoding="utf-8")
    assert project_canon_of_file(data, None, None) is None


# --- Z5: a schema file that cannot be stat'ed has a signature too ---------------------------------------------------


def test_a_dangling_schema_link_replaced_by_another_is_read_again(tmp_path: Path) -> None:
    folder = tmp_path / "spec" / "extensions"
    folder.mkdir(parents=True)
    (folder / "ext_01_a.schema.json").symlink_to(tmp_path / "nowhere.json")
    first = find_host_schemas(str(tmp_path / "spec"))
    assert first.accepted == {} and list(first.refused) == ["ext_01_a.schema.json"]
    (folder / "ext_01_a.schema.json").unlink()
    (folder / "ext_02_b.schema.json").symlink_to(tmp_path / "nowhere.json")
    second = find_host_schemas(str(tmp_path / "spec"))
    assert second.accepted == {} and list(second.refused) == ["ext_02_b.schema.json"]
    assert "cannot be read" in second.refused["ext_02_b.schema.json"]
