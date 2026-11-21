"""One definition source (WI-M4-05): the linters take the ids a spec defines from the graph, not from a scan of ``*_id``."""
from __future__ import annotations

import importlib
import json
import pkgutil
import re
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.core.loaders import read_json_object
from specdev_tools.graph.build import build_graph
from specdev_tools import trace
from specdev_tools.graph.kinds import load_kind_registry
from specdev_tools.validation.hallucination_lint import lint_hallucinations
from specdev_tools.validation.linter_utils import graph_known_ids
from specdev_tools.validation.spec_quality_lint import lint_spec_quality, lint_spec_quality_file

from specdev_tools.validation.spec_check import run_spec_check_json

from ._synth import EXAMPLE_SPEC, ROOT

NODE_FILE = "04_fr_list.json"
LEGACY_FILE = "99_legacy.json"
EXTERNAL = "external"
# Every string-valued ``*_ref`` / ``*_refs`` property of the step schemas: the node kind it names, or EXTERNAL when its
# value is a URL or a path and so outside the graph.  The linters match these by name, so a new one needs a decision.
STRING_REF_TARGETS = {
    "nfr_ref": "nfr",
    "nfr_refs": "nfr",
    "input_schema_ref": EXTERNAL,
    "output_schema_ref": EXTERNAL,
}
STRING_REF_NAME = re.compile(r"_refs?$")
ID_ATOMS = ("kebabId", "kebabIdArray")


def _write(spec: Path, name: str, document: dict[str, Any]) -> Path:
    spec.mkdir(exist_ok=True)
    path = spec / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _lines(errors: list[SpecError], code: str) -> list[str]:
    return [error.message for error in errors if error.code == code]


def _unresolved_refs(errors: list[SpecError]) -> list[str]:
    """The spec-quality E520 lines that name an unresolved reference (``ref=<id>``), not a missing top-level key."""
    return [line for line in _lines(errors, "E520") if " ref=" in line]


def _fr_file_with_foreign_key(ref: str) -> dict[str, Any]:
    """A node file whose ``coverage_notes`` collection is no node kind but repeats an id in a ``*_id`` field."""
    return {
        "functional_requirements": [{"fr_id": "fr-a"}],
        "coverage_notes": [{"fr_id": "fr-ghost"}],
        "note_ref": ref,
    }


def test_fk_id_field_is_not_a_definition(tmp_path: Path) -> None:
    _write(tmp_path, NODE_FILE, _fr_file_with_foreign_key("fr-ghost"))
    assert any("fr-ghost" in line for line in _lines(lint_hallucinations(str(tmp_path)), "E530"))
    assert any("fr-ghost" in line for line in _unresolved_refs(lint_spec_quality(str(tmp_path))))


def test_node_id_is_still_a_definition(tmp_path: Path) -> None:
    _write(tmp_path, NODE_FILE, _fr_file_with_foreign_key("fr-a"))
    assert _lines(lint_hallucinations(str(tmp_path)), "E530") == []
    assert _unresolved_refs(lint_spec_quality(str(tmp_path))) == []


def test_lints_take_a_given_graph_without_building_one(tmp_path: Path) -> None:
    """A graph handed in is the definition source: an id only the graph knows is not an unknown ref."""
    _write(tmp_path, NODE_FILE, _fr_file_with_foreign_key("fr-elsewhere"))
    other = tmp_path.parent / f"{tmp_path.name}-other"
    _write(other, NODE_FILE, {"functional_requirements": [{"fr_id": "fr-elsewhere"}]})
    graph = build_graph(str(other), str(ROOT))
    assert _lines(lint_hallucinations(str(tmp_path), graph=graph), "E530") == []
    assert _unresolved_refs(lint_spec_quality(str(tmp_path), graph=graph)) == []


@pytest.mark.parametrize(
    ("ref", "expected"),
    [("it-1", False), ("it-unknown", True)],
    ids=["defined-in-file", "unknown"],
)
def test_no_xnode_schema_keeps_legacy_known_ids(tmp_path: Path, ref: str, expected: bool) -> None:
    """A file that contributes no node is scanned for ids as before: a ref to its own id is fine, an unknown one is not."""
    _write(tmp_path, LEGACY_FILE, {"items": [{"item_id": "it-1"}], "link_ref": ref})
    assert bool(_lines(lint_hallucinations(str(tmp_path)), "E530")) is expected
    assert bool(_unresolved_refs(lint_spec_quality(str(tmp_path)))) is expected


@pytest.mark.parametrize(
    ("assumption", "expected"),
    [("fr-login keeps its contract", False), ("fr-unknown keeps its contract", True)],
    ids=["defined-in-file", "unknown"],
)
def test_assumption_unbound_id_single_file_uses_graph_slice(tmp_path: Path, assumption: str, expected: bool) -> None:
    path = _write(
        tmp_path,
        NODE_FILE,
        {"functional_requirements": [{"fr_id": "fr-login"}], "assumptions": [assumption]},
    )
    assert bool(_lines(lint_spec_quality_file(str(path), str(tmp_path)), "W573")) is expected


def test_single_file_foreign_key_is_not_a_definition(tmp_path: Path) -> None:
    """The slice replaces the scan for a file with nodes: an id only a ``*_id`` of a non-node collection holds is unbound."""
    path = _write(
        tmp_path,
        NODE_FILE,
        {
            "functional_requirements": [{"fr_id": "fr-a"}],
            "coverage_notes": [{"fr_id": "fr-ghost"}],
            "assumptions": ["fr-ghost keeps its contract"],
        },
    )
    assert any("fr-ghost" in line for line in _lines(lint_spec_quality_file(str(path), str(tmp_path)), "W573"))


def _property_schemas(node: Any) -> Iterator[tuple[str, dict[str, Any]]]:
    """Every ``(name, schema)`` under a ``properties`` keyword, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                yield from ((name, sub) for name, sub in value.items() if isinstance(sub, dict))
            yield from _property_schemas(value)
    elif isinstance(node, list):
        for item in node:
            yield from _property_schemas(item)


def _is_string_valued(schema: dict[str, Any]) -> bool:
    """True when the schema's values are strings (or lists of them): what a name-matched ``*_ref`` field must be."""
    if schema.get("type") == "string" or str(schema.get("$ref", "")).endswith(ID_ATOMS):
        return True
    items = schema.get("items")
    return schema.get("type") == "array" and isinstance(items, dict) and items.get("type") == "string"


def _string_ref_fields() -> set[str]:
    fields: set[str] = set()
    for path in sorted((ROOT / "schema").glob("*.schema.json")):
        document = read_json_object(str(path))
        assert document is not None, path
        fields.update(
            name for name, sub in _property_schemas(document) if STRING_REF_NAME.search(name) and _is_string_valued(sub)
        )
    return fields


def test_ref_field_audit_post_m3_schemas() -> None:
    """Each string ``*_ref(s)`` field of the step schemas has a declared target: a node kind or the outside world."""
    assert _string_ref_fields() == set(STRING_REF_TARGETS)
    kinds = set(load_kind_registry(str(ROOT)).kind_names)
    named = {target for target in STRING_REF_TARGETS.values() if target != EXTERNAL}
    assert named <= kinds


def test_spec_check_builds_the_graph_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lints and the ``graph`` check share one whole-spec build (one-file slices are other readers')."""
    calls: list[str] = []

    def counting_build(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("files") is None and kwargs.get("steps") is None:
            calls.append(str(args[0]))
        return build_graph(*args, **kwargs)

    monkeypatch.setattr("specdev_tools.validation.linter_utils.build_graph", counting_build)
    monkeypatch.setattr("specdev_tools.graph.check.build_graph", counting_build)
    for module in _trace_modules():
        monkeypatch.setattr(module, "build_graph", counting_build, raising=False)
    run_spec_check_json(str(ROOT), str(EXAMPLE_SPEC))
    assert len(calls) == 1


def _trace_modules() -> list[ModuleType]:
    """Every module of ``specdev_tools.trace``: a ``build_graph`` import in any of them is counted by the build test."""
    return [
        importlib.import_module(f"{trace.__name__}.{info.name}") for info in pkgutil.iter_modules(trace.__path__)
    ]


COVERED_ROOT_FILE = "03_glossary.json"
UNCOVERED_ROOT_FILE = "00_charter.json"
_ROOT_FILE_CASES = pytest.mark.parametrize("covered", [True, False], ids=["file-with-a-node", "file-without-a-node"])


def _trace_spec(tmp_path: Path, target: str, root_id: Any = "charter-v1", *, covered: bool = False) -> Path:
    """1.1.1 shape: a file with a root ``id`` and an FR file whose ``trace`` entry names *target*.

    The root-id file holds a node (a glossary term) when *covered*, so the graph covers it and the scan of the file
    adds none of its ids; else it holds none and the scan of the file is what adds its root id as well.
    """
    if covered:
        _write(tmp_path, COVERED_ROOT_FILE, {"id": root_id, "terms": [{"term_id": "term-a"}]})
    else:
        _write(tmp_path, UNCOVERED_ROOT_FILE, {"id": root_id})
    _write(
        tmp_path,
        NODE_FILE,
        {"functional_requirements": [{"fr_id": "fr-a", "trace": [{"type": "capability", "id": target}]}]},
    )
    return tmp_path


@_ROOT_FILE_CASES
def test_artifact_root_id_is_a_known_id(tmp_path: Path, covered: bool) -> None:
    spec = str(_trace_spec(tmp_path, "charter-v1", covered=covered))
    assert _lines(lint_hallucinations(spec), "E530") == []
    assert _unresolved_refs(lint_spec_quality(spec)) == []


def test_the_root_id_of_a_covered_file_comes_from_the_graph_alone(tmp_path: Path) -> None:
    """For a file with nodes the scan adds no id, so ``graph_known_ids`` is the only source of its root id."""
    spec = _trace_spec(tmp_path, "charter-v1", covered=True)
    graph = build_graph(str(spec), str(ROOT))
    assert COVERED_ROOT_FILE in {node.file for node in graph.nodes}
    assert "charter-v1" not in graph.by_id
    assert "charter-v1" in graph_known_ids(graph)


@_ROOT_FILE_CASES
def test_trace_to_an_id_defined_nowhere_is_still_reported(tmp_path: Path, covered: bool) -> None:
    spec = str(_trace_spec(tmp_path, "charter-v9", covered=covered))
    assert any("charter-v9" in line for line in _lines(lint_hallucinations(spec), "E530"))
    assert any("charter-v9" in line for line in _unresolved_refs(lint_spec_quality(spec)))


@_ROOT_FILE_CASES
@pytest.mark.parametrize("root_id", [["charter-v1"], 7], ids=["list", "number"])
def test_wrong_typed_root_id_defines_nothing_and_does_not_raise(tmp_path: Path, root_id: Any, covered: bool) -> None:
    spec = str(_trace_spec(tmp_path, "charter-v1", root_id, covered=covered))
    assert any("charter-v1" in line for line in _lines(lint_hallucinations(spec), "E530"))
    assert any("charter-v1" in line for line in _unresolved_refs(lint_spec_quality(spec)))
