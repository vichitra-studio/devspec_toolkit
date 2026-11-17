"""Tests for the trace lock file (WI-M5-01): format, reading, writing and the write lock."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from specdev_tools.core.constants import TRACE_LOCK_FILENAME
from specdev_tools.core.errors import FindingError
from specdev_tools.core.loaders import iter_spec_artifacts
from specdev_tools.core.schema_validate import validate_data_against_schema
from specdev_tools.trace.lockfile import (
    Lock,
    LockEntry,
    LockError,
    lock_path,
    parse_lock,
    read_lock,
    serialise_lock,
    with_write_lock,
    write_lock,
)
from specdev_tools.validation.validate import validate_dir

ROOT = Path(__file__).parents[3]
EXAMPLE_SPEC = ROOT / "tests" / "fixtures" / "graph_example" / "spec"
TOOLS_DIR = ROOT / "tools"
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def _entry(source: str, target: str, *, field: str = "fr_refs", baseline: bool = False) -> LockEntry:
    return LockEntry(source, field, target, HASH_A, HASH_B, baseline)


def _document(entries: list[dict[str, object]], **overrides: object) -> dict[str, object]:
    return {"$schema": "vc:extras:trace-lock", "version": 1, "entries": entries, **overrides}


def _raw_entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "source": "a", "field": "f", "target": "t", "content_hash": HASH_A, "chain_stamp": HASH_B,
    }
    return {**entry, **overrides}


def _put_lock(spec_dir: Path, text: str) -> Path:
    path = Path(lock_path(str(spec_dir)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_lock_roundtrip_is_byte_stable(tmp_path: Path) -> None:
    lock = Lock((_entry("t-2", "x"), _entry("t-1", "y"), _entry("t-1", "x", baseline=True)))
    write_lock(str(tmp_path), lock)
    path = Path(lock_path(str(tmp_path)))
    first = path.read_bytes()
    write_lock(str(tmp_path), read_lock(str(tmp_path)))
    assert path.read_bytes() == first
    lines = first.decode("utf-8").splitlines()
    assert len(lines) == 3 + 2  # header, three entries, closing line
    assert [json.loads(line.rstrip(","))["source"] for line in lines[1:-1]] == ["t-1", "t-1", "t-2"]
    assert first.endswith(b"\n")


def test_lock_serialisation_has_fixed_key_order_and_baseline_only_when_true() -> None:
    text = serialise_lock(Lock((_entry("a", "t", baseline=True), _entry("b", "t"))))
    first, second = text.splitlines()[1:3]
    assert list(json.loads(first.rstrip(","))) == ["source", "field", "target", "content_hash", "chain_stamp", "baseline"]
    assert "baseline" not in second


def test_missing_lock_file_reads_as_empty_lock(tmp_path: Path) -> None:
    assert read_lock(str(tmp_path)) == Lock()


def test_lock_loads_without_tripping_artifact_loader(tmp_path: Path) -> None:
    spec = tmp_path / "spec"
    spec.mkdir()
    shutil.copy(EXAMPLE_SPEC / "00_charter.json", spec)
    before = validate_dir(str(ROOT), str(spec))
    write_lock(str(spec), Lock(()))  # no entry: an entry with no link would be reported (E762) by the lock check
    verification = spec / "extras" / "verification"
    verification.mkdir(parents=True)
    (verification / "ver-one.json").write_text("{}", encoding="utf-8")
    after = validate_dir(str(ROOT), str(spec))
    assert [str(path) for path in iter_spec_artifacts(str(spec))] == [str(spec / "00_charter.json")]
    assert after == before
    assert not any(TRACE_LOCK_FILENAME in error.render() for error in after)


def test_shipped_schema_accepts_what_the_writer_writes(tmp_path: Path) -> None:
    write_lock(str(tmp_path), Lock((_entry("a", "t", baseline=True), _entry("b", "t"))))
    document = json.loads(Path(lock_path(str(tmp_path))).read_text(encoding="utf-8"))
    assert validate_data_against_schema(str(ROOT), document) == []


@pytest.mark.parametrize(
    "document",
    [
        _document([_raw_entry(content_hash="sha256:" + "A" * 64)]),
        _document([_raw_entry(baseline=False)]),
        _document([_raw_entry(extra="x")]),
        _document([], version=2),
    ],
)
def test_shipped_schema_rejects_what_the_reader_rejects(document: dict[str, object]) -> None:
    assert validate_data_against_schema(str(ROOT), document) != []
    with pytest.raises(LockError):
        parse_lock(json.dumps(document), "lock.json")


def test_conflict_markers_reported_with_repair_text(tmp_path: Path) -> None:
    _put_lock(tmp_path, '<<<<<<< ours\n{"$schema": "vc:extras:trace-lock"}\n=======\n{}\n>>>>>>> theirs\n')
    with pytest.raises(LockError) as caught:
        read_lock(str(tmp_path))
    error = caught.value.error
    assert error.code == "E760"
    assert error.owner == "merge-check"
    assert "git checkout -m -- " in error.message
    assert "git add " in error.message
    assert "git config merge.specdev-trace-lock.driver" in error.message
    assert error.message.index("git checkout -m") < error.message.index("git add ")


def test_lock_error_is_a_finding_error(tmp_path: Path) -> None:
    _put_lock(tmp_path, "{not json")
    with pytest.raises(FindingError) as caught:
        read_lock(str(tmp_path))
    assert caught.value.error.code == "E760"
    assert caught.value.error.file == lock_path(str(tmp_path))


def test_duplicate_key_and_bad_hash_rejected(tmp_path: Path) -> None:
    twice = _document([_raw_entry(), _raw_entry(content_hash=HASH_B)])
    with pytest.raises(LockError, match="two entries for"):
        parse_lock(json.dumps(twice), "lock.json")
    with pytest.raises(LockError, match="occurs twice"):
        parse_lock('{"$schema": "vc:extras:trace-lock", "version": 1, "version": 1, "entries": []}', "lock.json")
    for bad in ("sha256:abc", "md5:" + "a" * 64, "sha256:" + "A" * 64, HASH_A + "0"):
        with pytest.raises(LockError, match="content_hash"):
            parse_lock(json.dumps(_document([_raw_entry(content_hash=bad)])), "lock.json")


@pytest.mark.parametrize(
    "document",
    [
        _document([], version=2),
        _document([], version=True),
        _document([_raw_entry(baseline=False)]),
        _document([_raw_entry(source="")]),
        _document([{"source": "a"}]),
        _document("not a list"),
        {"version": 1, "entries": []},
        [],
    ],
)
def test_malformed_documents_are_e760(document: object) -> None:
    with pytest.raises(LockError) as caught:
        parse_lock(json.dumps(document), "lock.json")
    assert caught.value.error.code == "E760"


def test_non_utf8_file_is_e760(tmp_path: Path) -> None:
    path = _put_lock(tmp_path, "")
    path.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(LockError, match="UTF-8"):
        read_lock(str(tmp_path))


def test_write_lock_creates_missing_extras_dir(tmp_path: Path) -> None:
    spec = tmp_path / "spec"
    spec.mkdir()
    with with_write_lock(str(spec)):
        write_lock(str(spec), Lock((_entry("a", "t"),)))
    assert (spec / "extras").is_dir()
    assert read_lock(str(spec)).entries == (_entry("a", "t"),)
    assert [path.name for path in (spec / "extras").iterdir()] == [TRACE_LOCK_FILENAME]


def test_write_lock_keeps_the_mode_of_an_existing_file(tmp_path: Path) -> None:
    path = _put_lock(tmp_path, serialise_lock(Lock()))
    path.chmod(0o664)
    write_lock(str(tmp_path), Lock((_entry("a", "t"),)))
    assert path.stat().st_mode & 0o777 == 0o664


_HOLDER = (
    "import sys\n"
    "from specdev_tools.trace.lockfile import with_write_lock\n"
    "with with_write_lock(sys.argv[1]):\n"
    "    print('held', flush=True)\n"
    "    sys.stdin.read()\n"
)


def test_advisory_lock_blocks_second_writer(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(TOOLS_DIR)}
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(tmp_path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env,
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "held"
        with pytest.raises(LockError) as caught:
            with with_write_lock(str(tmp_path)):
                pytest.fail("the second writer got the lock")
        assert caught.value.error.code == "E769"
        assert "another specdev write is running" in caught.value.error.message
    finally:
        assert holder.stdin is not None
        holder.stdin.close()
        holder.wait(timeout=30)
    with with_write_lock(str(tmp_path)):
        pass
