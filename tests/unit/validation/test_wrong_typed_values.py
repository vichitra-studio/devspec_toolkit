"""No deep validator of steps 06-16 and no guarded reader raises on a wrong-typed value.

The class is proved, not a list of sites: every valid document of the worked example (``tests/fixtures/graph_example``)
and of the 1.1.1 corpus (``tests/fixtures/spec_corpus``) has the value at every JSON path replaced in turn by each of
``_WRONG_VALUES``; the step's deep validator (called directly, not through the E521 wrapper of ``validate.py``) must
return a list.  A validator may report its own finding on a wrong type; raising is the failure.  The same holds for
``check_traceability_closure`` and ``build_trace_matrix`` over a copy of the folder with one file mutated.
"""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest

from specdev_tools.validation.matrix import build_trace_matrix
from specdev_tools.validation.traceability_closure import check_traceability_closure, uncomputed_dimensions
from specdev_tools.validation.validate import DEEP_VALIDATORS

_ROOT = Path(__file__).parents[3]
_EXAMPLE = _ROOT / "tests" / "fixtures" / "graph_example" / "spec"
_CORPUS = _ROOT / "tests" / "fixtures" / "spec_corpus"
_WRONG_VALUES: tuple[Any, ...] = ("x", None, [], {}, 5, [None], ["x"], [[1]])
_STEP_OF_FILE = {
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
    "impl_context/ms_account_recovery_plan.json": "16a",
}
_PLAN = "impl_context/ms_account_recovery_plan.json"


def _paths(value: Any, prefix: tuple = ()) -> Iterator[tuple]:
    """Yield the path (a tuple of keys and indexes) of every value in *value*, the root included."""
    yield prefix
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _paths(item, prefix + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _paths(item, prefix + (index,))


def _mutations(document: dict[str, Any]) -> Iterator[tuple[tuple, Any, dict[str, Any]]]:
    """Yield ``(path, wrong_value, mutated_copy)`` for every path of *document* and every wrong value."""
    for path in _paths(document):
        if not path:
            continue
        for wrong in _WRONG_VALUES:
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


def _call(step: str, document: dict[str, Any], artifact_path: str) -> list:
    context = {"spec_root": str(_EXAMPLE), "artifact_path": artifact_path}
    return DEEP_VALIDATORS[step](document, str(_ROOT), context)


def _raised(step: str, document: dict[str, Any], artifact_path: str, label: str) -> list[str]:
    """Run every mutation of *document* through the deep validator of *step*; return the ones that raise."""
    failures: list[str] = []
    for path, wrong, mutated in _mutations(document):
        try:
            result = _call(step, mutated, artifact_path)
        except Exception as exc:  # noqa: BLE001 - the point of the test is to catch any raise
            failures.append(f"{label} {step} {list(path)} = {wrong!r}: {type(exc).__name__}: {exc}")
        else:
            if not isinstance(result, list):
                failures.append(f"{label} {step} {list(path)} = {wrong!r}: returned {type(result).__name__}")
    return failures


def test_deep_validators_of_the_example_do_not_raise() -> None:
    failures: list[str] = []
    for name, step in _STEP_OF_FILE.items():
        failures += _raised(step, _load(_EXAMPLE, name), str(_EXAMPLE / name), name)
    assert failures == []


def test_deep_validators_of_16b_and_16c_do_not_raise() -> None:
    document = _full_plan()
    path = str(_EXAMPLE / _PLAN)
    failures = _raised("16b", document, path, "plan+execution") + _raised("16c", document, path, "plan+review")
    assert failures == []


def test_deep_validators_of_a_1_1_1_shaped_plan_do_not_raise() -> None:
    document = _legacy_plan()
    path = str(_EXAMPLE / _PLAN)
    failures = _raised("16", document, path, "legacy plan")
    for step in ("16a", "16b", "16c"):
        failures += _raised(step, document, path, "legacy plan")
    assert failures == []


def test_deep_validators_of_the_1_1_1_corpus_do_not_raise() -> None:
    failures: list[str] = []
    for name, step in (("07_nfrs.json", "07"), ("08_fixtures.json", "08"), ("11_redteam.json", "11"), ("14_roadmap.json", "14")):
        failures += _raised(step, _load(_CORPUS, name), str(_CORPUS / name), f"corpus/{name}")
    assert failures == []


def _readers_raise(spec_dir: Path, label: str) -> list[str]:
    try:
        check_traceability_closure(str(spec_dir), str(_ROOT))
        uncomputed_dimensions(str(spec_dir), str(_ROOT))
        build_trace_matrix(str(_ROOT), str(spec_dir))
    except Exception as exc:  # noqa: BLE001
        return [f"{label}: {type(exc).__name__}: {exc}"]
    return []


def _mutate_folder(source: Path, tmp_path: Path, names: tuple[str, ...]) -> list[str]:
    """For each file of *names*, rewrite it once per mutation in a copy of *source* and run the folder readers."""
    folder = tmp_path / source.parent.name / "spec"
    shutil.copytree(source, folder)
    failures: list[str] = []
    for name in names:
        original = (folder / name).read_text(encoding="utf-8")
        for path, wrong, mutated in _mutations(json.loads(original)):
            (folder / name).write_text(json.dumps(mutated), encoding="utf-8")
            failures += _readers_raise(folder, f"{name} {list(path)} = {wrong!r}")
        (folder / name).write_text(original, encoding="utf-8")
    return failures


def test_closure_and_matrix_do_not_raise_on_the_example(tmp_path: Path) -> None:
    names = tuple(sorted(_STEP_OF_FILE)) + ("01_capabilities.json", "04_fr_list.json", "05_interface_contracts.json", "00_charter.json")
    assert _mutate_folder(_EXAMPLE, tmp_path, names) == []


def test_closure_and_matrix_do_not_raise_on_the_1_1_1_corpus(tmp_path: Path) -> None:
    names = tuple(sorted(path.name for path in _CORPUS.glob("*.json")))
    assert _mutate_folder(_CORPUS, tmp_path, names) == []


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
