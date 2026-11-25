"""jq runs without the process environment (DEVSPEC-96); robustness fixes of ``core/json_utils`` (DEVSPEC-97)."""
from __future__ import annotations

import ast
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from specdev_tools.core import json_utils
from specdev_tools.core.json_utils import (
    JsonUtilsError,
    _is_forbidden_path,
    build_id_index,
    json_read,
    json_write_atomic,
    run_jq,
    validate_jq_filter,
)

needs_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="jq is not installed")


@needs_jq
@pytest.mark.parametrize("expression", ["$ENV.SPECDEV_TEST_SECRET", "env.SPECDEV_TEST_SECRET"])
def test_a_filter_cannot_read_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, expression: str) -> None:
    monkeypatch.setenv("SPECDEV_TEST_SECRET", "leakme")
    path = tmp_path / "a.json"
    path.write_text('{"a": 1}', encoding="utf-8")
    try:
        result = json_read(str(path), expression)
    except JsonUtilsError as error:
        result = str(error)
    assert "leakme" not in (result or "")


def test_a_failed_atomic_write_leaves_no_temp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "a.json"
    path.write_text('{"a": 0}\n', encoding="utf-8")

    def boom(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        json_write_atomic(str(path), '{"a": 1}')
    assert os.listdir(tmp_path) == ["a.json"]


def test_build_id_index_skips_a_schema_file_that_is_not_an_object(tmp_path: Path) -> None:
    (tmp_path / "x.schema.json").write_text("5", encoding="utf-8")
    (tmp_path / "y.schema.json").write_text('{"$id": "vc:y"}', encoding="utf-8")
    assert build_id_index(str(tmp_path)) == {"vc:y": str(tmp_path / "y.schema.json")}


def test_build_id_index_skips_a_file_that_is_not_utf8(tmp_path: Path) -> None:
    (tmp_path / "x.schema.json").write_bytes(b"\xff\xfe\x00")
    assert build_id_index(str(tmp_path)) == {}


def test_every_open_names_an_encoding() -> None:
    tree = ast.parse(Path(json_utils.__file__).read_text(encoding="utf-8"))
    opens = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"]
    assert opens
    assert [n.lineno for n in opens if "encoding" not in {k.arg for k in n.keywords}] == []


def test_a_symlink_into_a_forbidden_prefix_is_forbidden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    link = tmp_path / "link"
    link.symlink_to(scratch)
    monkeypatch.setattr(json_utils, "_FORBIDDEN_ABS_PREFIXES", (str(scratch) + "/",))
    monkeypatch.delenv("TMPDIR", raising=False)
    assert _is_forbidden_path(str(link / "x.json")) is not None
    assert _is_forbidden_path(str(tmp_path / "other" / "x.json")) is None
