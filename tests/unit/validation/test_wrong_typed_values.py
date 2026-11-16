"""No deep validator of steps 01-16, no milestone-state reader, no guarded reader and no graph builder raises on a wrong-typed value.

The class is proved, not a list of sites.  Every valid document of the worked example (``tests/fixtures/graph_example``)
and of the 1.1.1 corpus (``tests/fixtures/spec_corpus``) has the value at every JSON path replaced in turn by each of
``_WRONG_VALUES``; the step's deep validator (called directly, not through the E521 wrapper of ``validate.py``) must
return a list.  The same is done for the files a validator READS besides its own (found by recording the opens of a
run on the unmutated folder): each is mutated on disk while the validator checks its unmutated document.  A validator
may report its own finding on a wrong type; raising is the failure.  ``check_traceability_closure``,
``uncomputed_dimensions`` and ``build_trace_matrix`` run over a copy of the folder with one file mutated, and
``compute_milestone_state`` over the mutated plan.  A whole file of the wrong kind (top level not an object, bytes that
are not UTF-8) is read as an unreadable file by the three folder readers and gives the deep validators no finding;
a sibling file replaced by ``{`` or by non-UTF-8 bytes does not make a validator raise, except through the three
1.1.1 loaders of ``_LOADERS_THAT_RAISE`` (steps 03 and 04), and a present roadmap that cannot be read keeps
``ROADMAP_PARSE_ERROR``.  A free-form payload holding every guarded field name, put in each of
nine free-form locations of the 1.2.0 schemas, leaves the readers' output unchanged.
"""
from __future__ import annotations

import builtins
import copy
import json
import shutil
from pathlib import Path
from typing import Any, Iterator
from unittest import mock

import pytest

from specdev_tools.context.milestone_state import compute_milestone_state
from specdev_tools.context.scope_resolver import resolve_scope
from specdev_tools.core.loaders import read_json_object
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.check import run_graph_check
from specdev_tools.graph.ids import check_unique_ids
from specdev_tools.graph.model import Graph
from specdev_tools.graph.ownership import step_for_file
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.validation import _legacy_shim
from specdev_tools.validation.matrix import build_trace_matrix
from specdev_tools.validation.traceability_closure import check_traceability_closure, uncomputed_dimensions
from specdev_tools.validation.spec_check import run_spec_check_json
from specdev_tools.validation.validate import (
    DEEP_VALIDATORS,
    _build_validation_context,
    _duplicate_id_errors,
    _run_deep_validation,
)

_ROOT = Path(__file__).parents[3]
_EXAMPLE = _ROOT / "tests" / "fixtures" / "graph_example" / "spec"
_CORPUS = _ROOT / "tests" / "fixtures" / "spec_corpus"
_WRONG_VALUES: tuple[Any, ...] = (
    "x", None, [], {}, 5, [None], ["x"], [[1]], "", True, 1.5, {"id": []}, [{"id": []}],
)
# The 1.1.1 readers of closure and matrix are all off on the example (it is graph-shaped), so its paths are mutated
# with four kinds of wrong value (string, null, array, object): this keeps the run short.  The corpus, where the
# readers run, gets every value.
_EXAMPLE_FOLDER_VALUES: tuple[Any, ...] = ("x", None, [], {"id": []})
_PLAN = "impl_context/ms_account_recovery_plan.json"
_STEP_OF_FILE = {
    "01_capabilities.json": "01",
    "02_system_sketch.json": "02",
    "02a_delivery_baseline.json": "02a",
    "03_glossary.json": "03",
    "04_fr_list.json": "04",
    "05_interface_contracts.json": "05",
    "06_invariants.json": "06",
    "07_nfrs.json": "07",
    "08_fixtures.json": "08",
    "09_impl_plan.json": "09",
    "10_governance.json": "10",
    "11_redteam.json": "11",
    "12_ci_gates.json": "12",
    "13_extension_manifest.json": "13",
    "14_roadmap.json": "14",
    "15_scaffold.json": "15",
    "16_impl_context.json": "16",
    _PLAN: "16a",
}
_CORPUS_STEPS = {
    "04_fr_list.json": "04", "05_interface_contracts.json": "05", "07_nfrs.json": "07", "08_fixtures.json": "08",
    "11_redteam.json": "11", "14_roadmap.json": "14",
}


def _paths(value: Any, prefix: tuple = ()) -> Iterator[tuple]:
    """Yield the path (a tuple of keys and indexes) of every value in *value*, the root included."""
    yield prefix
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _paths(item, prefix + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _paths(item, prefix + (index,))


def _mutations(document: dict[str, Any], values: tuple[Any, ...] = _WRONG_VALUES) -> Iterator[tuple[tuple, Any, dict[str, Any]]]:
    """Yield ``(path, wrong_value, mutated_copy)`` for every path of *document* and every wrong value."""
    for path in _paths(document):
        if not path:
            continue
        for wrong in values:
            mutated = copy.deepcopy(document)
            parent = mutated
            for key in path[:-1]:
                parent = parent[key]
            parent[path[-1]] = copy.deepcopy(wrong)
            yield path, wrong, mutated


def _load(base: Path, name: str) -> dict[str, Any]:
    return json.loads((base / name).read_text(encoding="utf-8"))


def _full_plan() -> dict[str, Any]:
    """The example plan with the execution and review sections of 16b and 16c added, so those validators run."""
    plan = _load(_EXAMPLE, _PLAN)
    plan["execution"] = {
        "execution_results": [{"command": "npm run test:contract", "status": "passed"}],
        "code_artifacts": [],
    }
    plan["review"] = {
        "verdict": "verified",
        "semantic_review": {"fr_coverage": [{"fr_id": "fr-password-reset"}]},
        "findings": [
            {"remediation_task": {"task_id": "rem-1", "checklist_ids": ["PWRESET_CONFIRM_EXPIRED_01"]}},
        ],
    }
    return plan


def _legacy_plan() -> dict[str, Any]:
    """The full plan with the 1.1.1 fields of an executed item (status, evidence, spec_ref) the legacy rules read."""
    plan = _full_plan()
    item = plan["plan"]["spec_alignment"]["checklist"][0]
    item["spec_ref"] = {"type": "fr", "id": "fr-password-reset"}
    item["checklist_status"] = "active"
    item["linked_test_expectation"] = "tests/confirm.test.ts"
    item["implementation"] = {
        "status": "verified",
        "files_touched": ["src/routes/password-resets/confirm.ts"],
        "actions": [{"type": "file_edit", "evidence": {"content": "PASS fr-password-reset " * 4, "stdout": "ok"}}],
    }
    plan["execution"]["files_touched"] = ["src/routes/password-resets/confirm.ts", "src/other.ts"]
    plan["execution"]["final_status"] = {"ci_status": "green"}
    plan["execution"]["critical_evidence"] = {"satisfied_checklist_ids": []}
    plan["review"]["fixture_status"] = {"ci_status": "green"}
    return plan


def _call(step: str, document: dict[str, Any], artifact_path: str, spec_root: Path = _EXAMPLE) -> list:
    if step == "03":  # the only validator that reads the loaded nfrs and monitoring data of the context
        context = _build_validation_context(str(_ROOT), artifact_path, spec_root=str(spec_root))
    else:
        context = {"artifact_path": artifact_path, "spec_root": str(spec_root)}
    return DEEP_VALIDATORS[step](document, str(_ROOT), context)


def _raise_of(label: str, call: Any) -> list[str]:
    try:
        result = call()
    except Exception as exc:  # noqa: BLE001 - the point of the test is to catch any raise
        return [f"{label}: {type(exc).__name__}: {exc}"]
    return [] if isinstance(result, (list, dict)) else [f"{label}: returned {type(result).__name__}"]


def _raised(step: str, document: dict[str, Any], artifact_path: str, label: str, spec_root: Path = _EXAMPLE) -> list[str]:
    """Run every mutation of *document* through the deep validator of *step*; return the ones that raise."""
    failures: list[str] = []
    for path, wrong, mutated in _first_entries(document, _WRONG_VALUES):
        failures += _raise_of(
            f"{label} {step} {list(path)} = {wrong!r}", lambda: _call(step, mutated, artifact_path, spec_root)
        )
    return failures


# Documents checked by the validators of steps 01-16: (label, folder, file name, step, loader of the document).
def _cases() -> list[tuple[str, Path, str, str, Any]]:
    cases = [(f"example/{name}", _EXAMPLE, name, step, lambda name=name: _load(_EXAMPLE, name))
             for name, step in _STEP_OF_FILE.items()]
    cases += [(f"corpus/{name}", _CORPUS, name, step, lambda name=name: _load(_CORPUS, name))
              for name, step in _CORPUS_STEPS.items()]
    cases += [("plan+execution+review", _EXAMPLE, _PLAN, step, _full_plan) for step in ("16a", "16b", "16c")]
    cases += [("1.1.1 plan", _EXAMPLE, _PLAN, step, _legacy_plan) for step in ("16", "16a", "16b", "16c")]
    return cases


def test_deep_validators_do_not_raise_on_a_wrong_value_in_their_document() -> None:
    failures: list[str] = []
    for label, base, name, step, loader in _cases():
        failures += _raised(step, loader(), str(base / name), label, base)
    assert failures == []


def _files_read(step: str, document: dict[str, Any], base: Path, name: str) -> set[str]:
    """The JSON files under *base*, other than *name*, that the validator of *step* opens on the unmutated *document*."""
    opened: set[str] = set()
    real_open = builtins.open

    def recording_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        path = Path(str(file))
        if path.suffix == ".json" and base in path.parents:
            opened.add(str(path.relative_to(base)))
        return real_open(file, *args, **kwargs)

    def recording_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        if self.suffix == ".json" and base in self.parents:
            opened.add(str(self.relative_to(base)))
        return real_read_text(self, *args, **kwargs)

    real_read_text = Path.read_text
    with mock.patch("builtins.open", recording_open), mock.patch("io.open", recording_open), \
            mock.patch.object(Path, "read_text", recording_read_text):
        _call(step, document, str(base / name), base)
    opened.discard(name)
    return opened


# Readers of a sibling file that raise on one that is not JSON or not UTF-8, by documented contract: ``load_upstream_ids``
# (step 04 reading 01; ``tests/unit/core/test_loaders.py`` pins the ``JSONDecodeError``) and the step 03 context loaders of
# ``validate.py`` (07 and 16).  1.1.1 code the milestone did not touch; ``validate.py`` reports the raise as E520 (step 03) or E521 (step 04).
_LOADERS_THAT_RAISE = {("03", "07_nfrs.json"), ("03", "16_impl_context.json"), ("04", "01_capabilities.json")}


def test_deep_validators_do_not_raise_on_a_wrong_value_in_a_file_they_read(tmp_path: Path) -> None:
    """Mutate, on disk, each file a validator reads besides its own; the validator checks its unmutated document."""
    failures: list[str] = []
    folders = {_EXAMPLE: tmp_path / "example", _CORPUS: tmp_path / "corpus"}
    for source, copy_dir in folders.items():
        shutil.copytree(source, copy_dir)
    # The anchor reads the plan files: one folder whose plan is 1.1.1-shaped, so the plan's object `spec_ref` is read.
    legacy = tmp_path / "legacy"
    shutil.copytree(_EXAMPLE, legacy)
    (legacy / _PLAN).write_text(json.dumps(_legacy_plan()), encoding="utf-8")
    cases = [(label, folders[base], name, step, loader) for label, base, name, step, loader in _cases()]
    cases.append(("anchor+1.1.1 plan", legacy, "16_impl_context.json", "16", lambda: _load(legacy, "16_impl_context.json")))
    readers: dict[tuple[Path, str], list[tuple[str, Path, str, str, dict[str, Any]]]] = {}
    for label, folder, name, step, loader in cases:
        document = loader()
        for sibling in _files_read(step, document, folder, name):
            readers.setdefault((folder, sibling), []).append((label, folder, name, step, document))
    siblings_mutated = 0
    for (folder, sibling), users in sorted(readers.items(), key=lambda item: (str(item[0][0]), item[0][1])):
        target = folder / sibling
        original = target.read_text(encoding="utf-8")
        for path, wrong, mutated in _first_entries(json.loads(original), _WRONG_VALUES):
            target.write_text(json.dumps(mutated), encoding="utf-8")
            siblings_mutated += 1
            for label, _folder, name, step, document in users:
                failures += _raise_of(
                    f"{label} {step} reads {sibling} {list(path)} = {wrong!r}",
                    lambda: _call(step, document, str(folder / name), folder),
                )
        for raw in (b"{", _NOT_UTF8):  # a sibling that is not JSON, and one that is not UTF-8
            target.write_bytes(raw)
            for label, _folder, name, step, document in users:
                if (step, sibling) in _LOADERS_THAT_RAISE:
                    continue
                failures += _raise_of(
                    f"{label} {step} reads {sibling} = {raw!r}",
                    lambda: _call(step, document, str(folder / name), folder),
                )
        target.write_text(original, encoding="utf-8")
    assert siblings_mutated > 0
    assert failures == []


def test_a_roadmap_that_is_not_utf8_json_gives_roadmap_parse_error(tmp_path: Path) -> None:
    """A present ``14_roadmap.json`` the reader cannot use keeps its E304; an absent one gives none."""
    folder = tmp_path / "spec"
    shutil.copytree(_EXAMPLE, folder)
    plan = _load(folder, _PLAN)
    for raw in (b"{", _NOT_UTF8, b"[]"):
        (folder / "14_roadmap.json").write_bytes(raw)
        found = [e.render() for e in _call("16a", plan, str(folder / _PLAN), folder)]
        assert any("ROADMAP_PARSE_ERROR" in line for line in found), (raw, found)
    (folder / "14_roadmap.json").unlink()
    assert not any("ROADMAP_" in e.render() for e in _call("16a", plan, str(folder / _PLAN), folder))


def test_milestone_state_does_not_raise_on_a_wrong_value_in_the_plan(tmp_path: Path) -> None:
    failures: list[str] = []
    for label, plan in (("plan", _load(_EXAMPLE, _PLAN)), ("1.1.1 plan", _legacy_plan())):
        for path, wrong, mutated in _mutations(plan):
            failures += _raise_of(
                f"{label} {list(path)} = {wrong!r}", lambda: compute_milestone_state(mutated, str(tmp_path), "account_recovery")
            )
    assert failures == []


def _readers_raise(spec_dir: Path, label: str) -> list[str]:
    return (
        _raise_of(label, lambda: check_traceability_closure(str(spec_dir), str(_ROOT)))
        + _raise_of(label, lambda: uncomputed_dimensions(str(spec_dir), str(_ROOT)))
        + _raise_of(label, lambda: build_trace_matrix(str(_ROOT), str(spec_dir)))
    )


def _first_entries(document: dict[str, Any], values: tuple[Any, ...]) -> Iterator[tuple[tuple, Any, dict[str, Any]]]:
    """The mutations of *document* on the first entry of every array.  Later entries are not mutated (run time);
    a rule that compares the entries of one array is exercised only through its first entry."""
    for path, wrong, mutated in _mutations(document, values):
        if all(key == 0 for key in path if isinstance(key, int)):
            yield path, wrong, mutated


def _mutate_folder(
    source: Path, tmp_path: Path, names: tuple[str, ...], values: tuple[Any, ...]
) -> list[str]:
    """For each file of *names*, rewrite it once per mutation in a copy of *source* and run the folder readers."""
    folder = tmp_path / source.parent.name / "spec"
    shutil.copytree(source, folder)
    failures: list[str] = []
    for name in names:
        original = (folder / name).read_text(encoding="utf-8")
        for path, wrong, mutated in _first_entries(json.loads(original), values):
            (folder / name).write_text(json.dumps(mutated), encoding="utf-8")
            failures += _readers_raise(folder, f"{name} {list(path)} = {wrong!r}")
        (folder / name).write_text(original, encoding="utf-8")
    return failures


def test_closure_and_matrix_do_not_raise_on_the_example(tmp_path: Path) -> None:
    names = tuple(_STEP_OF_FILE) + ("00_charter.json",)
    assert _mutate_folder(_EXAMPLE, tmp_path, names, _EXAMPLE_FOLDER_VALUES) == []


def test_closure_and_matrix_do_not_raise_on_the_1_1_1_corpus(tmp_path: Path) -> None:
    names = tuple(sorted(path.name for path in _CORPUS.glob("*.json")))
    assert _mutate_folder(_CORPUS, tmp_path, names, _WRONG_VALUES) == []


# A whole file of the wrong kind: JSON whose top level is not an object, and bytes that are not UTF-8.
_WHOLE_DOCUMENTS: tuple[Any, ...] = ([], 0, None, "x", True, 1.5)
_NOT_UTF8 = b'{"a": "\xff\xfe"}'


def test_deep_validation_gives_no_finding_on_a_whole_document_of_the_wrong_kind() -> None:
    """``_run_deep_validation`` is where validators are called; it turns a non-object into no finding (the schema reports it)."""
    failures: list[str] = []
    for label, base, name, step, _loader in _cases():
        for document in _WHOLE_DOCUMENTS:
            found = _run_deep_validation(step, document, str(_ROOT), str(base / name), spec_root=str(base))
            if found:
                failures.append(f"{label} {step} = {document!r}: {found}")
    assert failures == []


def _replace_whole_files(source: Path, tmp_path: Path) -> list[str]:
    """Replace each JSON file of *source* in a copy, once per whole document, and run the three folder readers."""
    folder = tmp_path / source.parent.name / "spec"
    shutil.copytree(source, folder)
    failures: list[str] = []
    for target in sorted(folder.rglob("*.json")):
        original = target.read_bytes()
        name = str(target.relative_to(folder))
        for document in (*_WHOLE_DOCUMENTS, _NOT_UTF8):
            target.write_bytes(document if isinstance(document, bytes) else json.dumps(document).encode())
            failures += _readers_raise(folder, f"{name} = {document!r}")
        target.write_bytes(original)
    return failures


def test_folder_readers_do_not_raise_on_a_whole_file_of_the_wrong_kind_in_the_example(tmp_path: Path) -> None:
    assert _replace_whole_files(_EXAMPLE, tmp_path) == []


def test_folder_readers_do_not_raise_on_a_whole_file_of_the_wrong_kind_in_the_corpus(tmp_path: Path) -> None:
    assert _replace_whole_files(_CORPUS, tmp_path) == []


# --- free-form payloads: a key named like a 1.1.1 field inside a value the schema does not describe -----------

_GUARDED_NAMES = sorted(
    {name for const in vars(_legacy_shim).values() if isinstance(const, frozenset) for name in const}
    | {"out_of_scope", "spec_ref", "critical_evidence", "trace_refs"}
)
# Free-form locations of the 1.2.0 schemas: fixture `input` and `expected`, API `parameters` and `errors` entries,
# the plan item's `implementation`, a CI job's `token_permissions`, a plan's `command_overrides` and
# `test_results[]`, the `environments{}` map of 02a.  (file, path of the object that receives the payload keys;
# a missing parent object is created)
_FREE_FORM_LOCATIONS = [
    ("08_fixtures.json", ("fixtures", 0, "input")),
    ("08_fixtures.json", ("fixtures", 0, "expected")),
    ("05_interface_contracts.json", ("apis", 0, "parameters")),
    ("05_interface_contracts.json", ("apis", 0, "errors")),
    (_PLAN, ("plan", "spec_alignment", "checklist", 0, "implementation")),
    ("12_ci_gates.json", ("jobs", 0, "token_permissions")),
    (_PLAN, ("extensions", "execution_context", "command_overrides")),
    (_PLAN, ("execution", "final_status", "test_results")),
    ("02a_delivery_baseline.json", ("environments",)),
]
_ARRAYS_OF_OBJECTS = ("parameters", "errors", "test_results")


def _payload() -> dict[str, Any]:
    """Every guarded field name as a key: at object depth, and inside an array of objects."""
    flat = {name: [] for name in _GUARDED_NAMES}
    return {**flat, "nested": {**flat}, "list": [{**flat}]}


def _outputs(folder: Path) -> dict[str, Any]:
    return {
        "closure": [error.render() for error in check_traceability_closure(str(folder), str(_ROOT))],
        "uncomputed": uncomputed_dimensions(str(folder), str(_ROOT)),
        "matrix": build_trace_matrix(str(_ROOT), str(folder)),
        "scope": resolve_scope("FR-CORPUS-001", str(folder), str(_ROOT)),
    }


@pytest.mark.parametrize(("name", "path"), _FREE_FORM_LOCATIONS, ids=lambda value: str(value))
def test_a_free_form_payload_with_every_guarded_field_name_leaves_every_reader_off(name: str, path: tuple, tmp_path: Path) -> None:
    clean = tmp_path / "clean"
    shutil.copytree(_EXAMPLE, clean)
    expected = _outputs(clean)
    document = json.loads((clean / name).read_text(encoding="utf-8"))
    target = document
    for key in path[:-1]:
        target = target.setdefault(key, {}) if isinstance(target, dict) else target[key]
    existing = target.get(path[-1]) if isinstance(target, dict) else None
    if isinstance(existing, dict):
        existing.update(_payload())
    else:
        target[path[-1]] = [_payload()] if path[-1] in _ARRAYS_OF_OBJECTS else _payload()
    (clean / name).write_text(json.dumps(document), encoding="utf-8")
    assert _outputs(clean) == expected
    assert expected["uncomputed"] == [
        "fr_api_coverage", "fr_fixture_coverage", "fr_milestone_coverage", "capability_fr_coverage"
    ]


@pytest.mark.parametrize("field", ["trace", "targets", "target_ids"])
def test_a_link_entry_whose_id_is_a_list_does_not_raise_in_the_matrix(field: str, tmp_path: Path) -> None:
    """The 1.1.1 readers key a dict by an entry's ``id``; a list id must be skipped, not hashed."""
    folder = tmp_path / "spec"
    shutil.copytree(_CORPUS, folder)
    found = 0
    for path in folder.glob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        for node in _walk(document):
            entries = node.get(field)
            if isinstance(entries, list) and entries and isinstance(entries[0], dict):
                entries[0]["id"] = []
                found += 1
        path.write_text(json.dumps(document), encoding="utf-8")
    assert found, f"the corpus has no {field} list"
    build_trace_matrix(str(_ROOT), str(folder))


def _walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


# --- the graph builder ------------------------------------------------------------------------------------------

_GRAPH_FILES = (*_STEP_OF_FILE, "00_charter.json", "common/seed_manifest.json")


def test_build_graph_does_not_raise_on_a_wrong_value() -> None:
    """Every mutation of every file of the example and the corpus gives a graph (or load errors), never a traceback.

    The mutated document replaces its file through ``overrides`` and ``files`` limits the build to that file.
    """
    failures: list[str] = []
    cases = [(_EXAMPLE, name) for name in _GRAPH_FILES] + [(_CORPUS, name) for name in _CORPUS_STEPS]
    for base, name in cases:
        for path, wrong, mutated in _first_entries(_load(base, name), _WRONG_VALUES):
            failures += _raise_of(
                f"{base.name} {name} {list(path)} = {wrong!r}",
                lambda: _built(base, {name: mutated}, name),
            )
        for document in _WHOLE_DOCUMENTS:
            failures += _raise_of(f"{base.name} {name} = {document!r}", lambda: _built(base, {name: document}, name))
    assert failures == []


def _built(base: Path, overrides: dict[str, Any], name: str) -> dict[str, Any]:
    graph = build_graph(str(base), str(_ROOT), files=[name], overrides=overrides)
    return {"graph": isinstance(graph, Graph)}


def test_build_graph_reads_a_file_that_is_not_utf8_json_as_a_load_error(tmp_path: Path) -> None:
    folder = tmp_path / "spec"
    shutil.copytree(_EXAMPLE, folder)
    for raw in (b"{", _NOT_UTF8, b"[]"):
        (folder / "04_fr_list.json").write_bytes(raw)
        graph = build_graph(str(folder), str(_ROOT))
        assert [error.file for error in graph.load_errors] == ["04_fr_list.json"]


# --- id uniqueness, the link resolver and the graph check of spec-check ---------------------------------------------

_LINK_AND_ID_KEYS = frozenset({
    "fr_id", "criterion_id", "job_id", "task_id", "milestone_id", "id", "derives_from", "depends_on", "refines",
    "realises", "verifies", "verified_by", "about", "schedules", "constrains", "mitigated_by", "threatens",
})


def _graph_documents(base: Path) -> dict[str, Any]:
    """Every JSON file of *base* that the graph reads, parsed, keyed by its path relative to *base*."""
    names = sorted(str(path.relative_to(base)) for path in base.rglob("*.json"))
    return {name: _load(base, name) for name in names}


def _checked(base: Path, documents: dict[str, Any], name: str, mutated: Any) -> dict[str, Any]:
    graph = build_graph(str(base), str(_ROOT), overrides={**documents, name: mutated})
    return {"ids": check_unique_ids(graph), "links": resolve_graph(graph)}


def _mutated_graph_cases() -> list[tuple[Path, str, dict[str, Any], dict[str, Any]]]:
    """``(base, file, documents of base, mutated document)`` for every first-entry mutation of the example and the corpus."""
    cases = []
    for base in (_EXAMPLE, _CORPUS):
        documents = _graph_documents(base)
        for name in [*_GRAPH_FILES, "impl_context/ms_account_recovery_plan.json"] if base is _EXAMPLE else list(_CORPUS_STEPS):
            for _path, _wrong, mutated in _first_entries(documents[name], _EXAMPLE_FOLDER_VALUES):
                cases.append((base, name, documents, mutated))
            cases += [(base, name, documents, whole) for whole in _WHOLE_DOCUMENTS]
    return cases


def test_unique_ids_does_not_raise_on_a_wrong_value() -> None:
    """A wrong-typed id or link value, or a whole file of the wrong kind, gives findings or none from ``check_unique_ids``."""
    failures: list[str] = []
    for base, name, documents, mutated in _mutated_graph_cases():
        failures += _raise_of(
            f"{base.name} {name} = {mutated!r:.80}",
            lambda: check_unique_ids(build_graph(str(base), str(_ROOT), overrides={**documents, name: mutated})),
        )
    assert failures == []


def test_resolve_graph_does_not_raise_on_a_wrong_value() -> None:
    """The same mutations over the whole graph: ``resolve_graph`` gives findings or none, never a traceback."""
    failures: list[str] = []
    for base, name, documents, mutated in _mutated_graph_cases():
        failures += _raise_of(
            f"{base.name} {name} = {mutated!r:.80}",
            lambda: _checked(base, documents, name, mutated),
        )
    assert failures == []


def test_graph_check_and_file_owner_do_not_raise_on_a_wrong_value(tmp_path: Path) -> None:
    """``run_graph_check`` and the ``step_for_file`` read of ``spec-check`` over a spec folder with one id or link value mutated."""
    folder = tmp_path / "spec"
    shutil.copytree(_EXAMPLE, folder)
    failures: list[str] = []
    for name in (*_GRAPH_FILES[:-1], _PLAN):
        original = (folder / name).read_text(encoding="utf-8")
        for path, wrong, mutated in _first_entries(json.loads(original), _EXAMPLE_FOLDER_VALUES):
            if path[-1] not in _LINK_AND_ID_KEYS:
                continue
            (folder / name).write_text(json.dumps(mutated), encoding="utf-8")
            failures += _raise_of(
                f"{name} {list(path)} = {wrong!r}",
                lambda: [run_graph_check(str(folder), str(_ROOT)), step_for_file(str(folder / name), read_json_object(folder / name))],
            )
        (folder / name).write_text(original, encoding="utf-8")
    assert failures == []


def test_spec_check_does_not_raise_on_a_whole_file_of_the_wrong_kind(tmp_path: Path) -> None:
    """``spec-check`` reads each file once for its step and builds the graph: a file that is not an object gives no traceback.

    ``lint_spec_quality`` is stubbed: it raises on a top level that is not an object (1.1.1 code this milestone does
    not touch).  Bytes that are not UTF-8 are covered by the graph check and the step read alone, because
    ``validate_canonical_integrity`` raises on them.
    """
    folder = tmp_path / "spec"
    shutil.copytree(_EXAMPLE, folder)
    failures: list[str] = []
    for name in ("04_fr_list.json", "12_ci_gates.json", "14_roadmap.json", _PLAN):
        original = (folder / name).read_bytes()
        for document in _WHOLE_DOCUMENTS:
            (folder / name).write_bytes(json.dumps(document).encode())
            with mock.patch("specdev_tools.validation.spec_quality_lint.lint_spec_quality", return_value=[]):
                failures += _raise_of(f"{name} = {document!r}", lambda: list(run_spec_check_json(str(_ROOT), str(folder))))
        for raw in (b"{", _NOT_UTF8):
            (folder / name).write_bytes(raw)
            failures += _raise_of(
                f"{name} = {raw!r}",
                lambda: [run_graph_check(str(folder), str(_ROOT)), step_for_file(str(folder / name), read_json_object(folder / name))],
            )
        (folder / name).write_bytes(original)
    assert failures == []


def test_one_file_id_check_does_not_raise_on_a_wrong_value() -> None:
    """The one-file slice of ``validate_file`` (``build_file_graph`` and ``check_unique_ids``) on every first-entry mutation."""
    failures: list[str] = []
    for name in _GRAPH_FILES:
        for _path, _wrong, mutated in _first_entries(_load(_EXAMPLE, name), _EXAMPLE_FOLDER_VALUES):
            failures += _raise_of(f"{name} = {mutated!r:.80}", lambda: _duplicate_id_errors(str(_ROOT), str(_EXAMPLE / name), mutated))
    assert failures == []
