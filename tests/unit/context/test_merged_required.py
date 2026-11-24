"""``merged_required_and_properties``: the allOf-merged required set and properties of a step schema."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.context._utils import merged_required_and_properties

_INLINE_ALLOF = {
    "allOf": [
        {"required": ["name", "id"], "properties": {"name": {"type": "string"}}},
        {"required": ["name"], "properties": {"id": {"type": "string"}}},
    ],
}


@pytest.fixture(params=["none", "empty_dir"])
def repo_root(request: pytest.FixtureRequest, tmp_path: Path) -> Path | None:
    return None if request.param == "none" else tmp_path


def test_inline_allof_is_merged_without_a_registry_in_repo_root(repo_root: Path | None) -> None:
    merged = merged_required_and_properties(_INLINE_ALLOF, repo_root)
    assert set(merged["properties"]) == {"name", "id"}


def test_required_is_deduplicated_and_keeps_order(repo_root: Path | None) -> None:
    assert merged_required_and_properties(_INLINE_ALLOF, repo_root)["required"] == ["name", "id"]


def test_ref_to_step_base_resolves_through_the_package_registry(repo_root: Path | None) -> None:
    schema = {"allOf": [{"$ref": "vc:core:step-base"}, {"required": ["extra"], "properties": {"extra": {}}}]}
    merged = merged_required_and_properties(schema, repo_root)
    assert {"id", "owner", "extra"} <= set(merged["required"])
    assert {"id", "owner", "extra"} <= set(merged["properties"])


def test_an_unloadable_registry_falls_back_to_inline_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(_root: str) -> None:
        raise OSError("no registry")

    monkeypatch.setattr("specdev_tools.context._utils.get_shared_registry", _fail)
    schema = {"allOf": [{"$ref": "vc:core:step-base"}, {"required": ["extra"], "properties": {"extra": {}}}]}
    merged = merged_required_and_properties(schema, None)
    assert merged["required"] == ["extra"]
    assert set(merged["properties"]) == {"extra"}
