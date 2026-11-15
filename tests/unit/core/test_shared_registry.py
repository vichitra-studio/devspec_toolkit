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


class _CountingDict(dict):
    """Counts item assignment: ``get_cached_validator`` assigns once per cache miss."""

    def __init__(self) -> None:
        super().__init__()
        self.sets: list[tuple[str, str]] = []

    def __setitem__(self, key, value) -> None:
        self.sets.append(key)
        super().__setitem__(key, value)


def test_one_spec_check_run_builds_one_registry_per_root_and_one_validator_per_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One real spec-check over the corpus: <=1 SchemaRegistry per repo root, <=1 validator per URI.

    Validators are counted as cache misses (one ``_VALIDATOR_CACHE`` assignment each), not as
    ``Draft202012Validator.__init__`` calls: ``jsonschema`` ``evolve`` re-enters ``__init__``
    for sub-schemas without being a cache miss.
    """
    from specdev_tools.validation.spec_check import run_spec_check_json

    clear_shared_caches()
    reg_ctor: dict[str, int] = {}
    orig_init = SchemaRegistry.__init__

    def _counting_init(self, repo_root):
        key = os.path.realpath(repo_root)
        reg_ctor[key] = reg_ctor.get(key, 0) + 1
        orig_init(self, repo_root)

    monkeypatch.setattr(SchemaRegistry, "__init__", _counting_init)
    misses = _CountingDict()
    monkeypatch.setattr(reg_mod, "_VALIDATOR_CACHE", misses)

    corpus = os.path.join(TOOLKIT_ROOT, "tests", "fixtures", "spec_corpus")
    run_spec_check_json(TOOLKIT_ROOT, corpus)

    assert reg_ctor, "spec-check built no SchemaRegistry: the counter is not wired"
    assert misses.sets, "spec-check built no cached validator: the counter is not wired"
    assert all(n <= 1 for n in reg_ctor.values()), reg_ctor
    assert len(misses.sets) == len(set(misses.sets)), [k for k in misses.sets if misses.sets.count(k) > 1]
    clear_shared_caches()


def test_deleted_schema_file_after_caching_rebuilds_and_load_raises(tmp_path: Path) -> None:
    root = _make_toolkit(tmp_path, _S0)
    first = get_shared_registry(str(root))
    assert first.load("vc:test:s") == _S0
    (root / "schema" / "s.json").unlink()
    second = get_shared_registry(str(root))
    assert second is not first
    with pytest.raises(FileNotFoundError):
        second.load("vc:test:s")


def test_changed_registry_map_file_rebuilds(tmp_path: Path) -> None:
    root = _make_toolkit(tmp_path, _S0)
    first = get_shared_registry(str(root))
    (root / "schema" / "t.json").write_text(json.dumps(_S0), encoding="utf-8")
    (root / "tools" / "schema_registry.json").write_text(
        json.dumps({"vc:test:s": "schema/s.json", "vc:test:t": "schema/t.json"}), encoding="utf-8"
    )
    second = get_shared_registry(str(root))
    assert second is not first
    assert "vc:test:t" in second.map


def test_schema_edited_during_load_is_not_cached_under_new_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _make_toolkit(tmp_path, _S0)
    edited = {**_S0, "required": ["a"]}
    orig_init = SchemaRegistry.__init__

    def _init_then_edit(self, repo_root):
        orig_init(self, repo_root)  # loads the old content
        (Path(repo_root) / "schema" / "s.json").write_text(json.dumps(edited), encoding="utf-8")

    monkeypatch.setattr(SchemaRegistry, "__init__", _init_then_edit)
    stale = get_shared_registry(str(root))
    assert stale.load("vc:test:s") == _S0
    monkeypatch.setattr(SchemaRegistry, "__init__", orig_init)
    fresh = get_shared_registry(str(root))
    assert fresh is not stale
    assert fresh.load("vc:test:s") == edited


def test_threads_share_one_registry_and_one_validator(tmp_path: Path) -> None:
    import threading

    from specdev_tools.core.registry import get_cached_validator

    root = _make_toolkit(tmp_path, _S0)
    regs: list[SchemaRegistry] = []
    vals: list[object] = []
    built: list[int] = []
    barrier = threading.Barrier(8)

    def _work() -> None:
        barrier.wait()
        reg = get_shared_registry(str(root))
        regs.append(reg)
        vals.append(get_cached_validator(str(root), "vc:test:s", reg, lambda: built.append(1) or object()))

    threads = [threading.Thread(target=_work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(regs) == 8 and all(r is regs[0] for r in regs)
    assert len(built) == 1 and all(v is vals[0] for v in vals)
