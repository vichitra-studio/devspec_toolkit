"""Tests for the shared SchemaRegistry / validator caches (WI-M1-09, DEVSPEC-257)."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import specdev_tools.core.registry as reg_mod
from specdev_tools.core.registry import (
    SchemaRegistry,
    clear_shared_caches,
    get_shared_registry,
)
from specdev_tools.core.schema_validate import validate_data_against_schema

_S0 = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}
TOOLKIT_ROOT = str(Path(__file__).resolve().parents[3])


def _make_toolkit(tmp_path: Path, schema: dict) -> Path:
    root = tmp_path / "tk"
    (root / "tools").mkdir(parents=True)
    (root / "schema").mkdir()
    (root / "schema" / "s.json").write_text(json.dumps(schema), encoding="utf-8")
    (root / "tools" / "schema_registry.json").write_text(
        json.dumps({"vc:test:s": "schema/s.json"}), encoding="utf-8"
    )
    return root


def test_get_shared_registry_returns_same_instance(tmp_path: Path) -> None:
    root = _make_toolkit(tmp_path, _S0)
    assert get_shared_registry(str(root)) is get_shared_registry(str(root))


def test_shared_registry_keyed_by_realpath(tmp_path: Path) -> None:
    root = _make_toolkit(tmp_path, _S0)
    link = tmp_path / "link"
    os.symlink(root, link)
    assert get_shared_registry(str(root)) is get_shared_registry(str(link))


def test_shared_registry_rebuilt_when_schema_rewritten(tmp_path: Path) -> None:
    root = _make_toolkit(tmp_path, _S0)
    first = get_shared_registry(str(root))
    (root / "schema" / "s.json").write_text(
        json.dumps({**_S0, "required": ["a"]}), encoding="utf-8"
    )
    second = get_shared_registry(str(root))
    assert second is not first
    assert second.load("vc:test:s")["required"] == ["a"]


def test_validator_cache_invalidated_by_schema_edit(tmp_path: Path) -> None:
    root = _make_toolkit(tmp_path, _S0)
    doc = {"$schema": "vc:test:s"}
    assert validate_data_against_schema(str(root), doc) == []
    (root / "schema" / "s.json").write_text(
        json.dumps({**_S0, "required": ["a"]}), encoding="utf-8"
    )
    errs = validate_data_against_schema(str(root), doc)
    assert errs and "'a' is a required property" in errs[0][1]


def test_shared_registry_bootstrap_error_not_cached(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    (root / "tools").mkdir(parents=True)
    with pytest.raises(OSError):
        get_shared_registry(str(root))
    (root / "tools" / "schema_registry.json").write_text("{}", encoding="utf-8")
    assert get_shared_registry(str(root)).map == {}


def test_to_referencing_registry_cached_per_instance() -> None:
    r = SchemaRegistry(TOOLKIT_ROOT)
    assert r.to_referencing_registry() is r.to_referencing_registry()
    assert SchemaRegistry(TOOLKIT_ROOT).to_referencing_registry() is not r.to_referencing_registry()


def test_load_serves_from_store_without_file_read(monkeypatch: pytest.MonkeyPatch) -> None:
    r = SchemaRegistry(TOOLKIT_ROOT)
    uri = next(iter(r.store))

    def _no_open(*a, **k):  # pragma: no cover - failure path
        raise AssertionError("load() read a file although the store has the URI")

    monkeypatch.setattr("builtins.open", _no_open)
    assert r.load(uri) is r.store[uri]
    assert r.load(uri) is r.load(uri)


def test_load_missing_uri_still_raises_file_not_found() -> None:
    r = SchemaRegistry(TOOLKIT_ROOT)
    with pytest.raises(FileNotFoundError):
        r.load("vc:does:not:exist")


def test_clear_shared_caches_empties_all() -> None:
    reg = get_shared_registry(TOOLKIT_ROOT)
    reg_mod._VALIDATOR_CACHE[("k", "u")] = (reg, object())
    clear_shared_caches()
    assert not reg_mod._SHARED_REGISTRIES
    assert not reg_mod._VALIDATOR_CACHE
    assert get_shared_registry(TOOLKIT_ROOT) is not reg


def test_spec_check_style_run_constructs_one_registry_and_one_validator_per_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Many validations over one repo_root: <=1 SchemaRegistry, <=1 validator per schema URI."""
    reg_ctor = {"n": 0}
    val_ctor: dict[str, int] = {}
    orig_init = SchemaRegistry.__init__

    def _counting_init(self, repo_root):
        reg_ctor["n"] += 1
        orig_init(self, repo_root)

    monkeypatch.setattr(SchemaRegistry, "__init__", _counting_init)

    import specdev_tools.core.schema_validate as sv

    class _CountingValidator:
        FORMAT_CHECKER = Draft202012Validator.FORMAT_CHECKER

        def __new__(cls, schema, *a, **k):
            key = schema.get("$id", "?")
            val_ctor[key] = val_ctor.get(key, 0) + 1
            return Draft202012Validator(schema, *a, **k)

    monkeypatch.setattr(sv, "Draft202012Validator", _CountingValidator)

    uri = next(iter(SchemaRegistry(TOOLKIT_ROOT).store))
    reg_ctor["n"] = 0
    for _ in range(5):
        validate_data_against_schema(TOOLKIT_ROOT, {"$schema": uri})
        get_shared_registry(TOOLKIT_ROOT)
    assert reg_ctor["n"] <= 1
    assert all(n <= 1 for n in val_ctor.values())
    assert sum(val_ctor.values()) == 1
