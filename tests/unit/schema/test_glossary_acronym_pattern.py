"""The step 03 `acronym` accepts an inner `/` or `-`, and the `term_ref` description says where a non-term concept goes."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from specdev_tools.validation.validate import validate_file

_ROOT = Path(__file__).resolve().parents[3]
_EXAMPLE = _ROOT / "tests" / "fixtures" / "graph_example" / "spec" / "03_glossary.json"
_SCHEMA = _ROOT / "schema" / "03_glossary.schema.json"


def _acronym_errors(tmp_path: Path, acronym: str) -> list[str]:
    """Rendered schema errors (E520) about `acronym` after the first term of the worked-example glossary gets *acronym*."""
    glossary = copy.deepcopy(json.loads(_EXAMPLE.read_text(encoding="utf-8")))
    glossary["terms"][0]["acronym"] = acronym
    path = tmp_path / "03_glossary.json"
    path.write_text(json.dumps(glossary), encoding="utf-8")
    return [error.render() for error in validate_file(str(_ROOT), str(path)) if error.code == "E520" and "acronym" in error.render().rsplit(".json", 1)[-1]]


@pytest.mark.parametrize("acronym", ["CI/CD", "JSON-LD", "JWT", "A1"])
def test_acronyms_with_an_inner_slash_or_hyphen_validate(tmp_path: Path, acronym: str) -> None:
    assert _acronym_errors(tmp_path, acronym) == []


@pytest.mark.parametrize("acronym", ["a", "x y", "-AB", "AB-", "A"])
def test_malformed_acronyms_are_rejected(tmp_path: Path, acronym: str) -> None:
    assert _acronym_errors(tmp_path, acronym) != []


def test_term_ref_description_names_the_other_kinds() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    term = schema["allOf"][1]["properties"]["terms"]["items"]["properties"]["term_ref"]
    assert "canonical_proposals" in term["description"]
