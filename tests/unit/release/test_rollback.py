"""The rollback record (WI-M9-04): a tool-written file under ``spec/extras/releases/``, validated in code, no schema."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.registry.generate import _serialize, generate_registry
from specdev_tools.release.previous import check_next_release
from specdev_tools.release.records import ROLLBACK_SCHEMA, read_rollback, record_problems, rollback_id, rollback_path, write_rollback
from unit.graph._synth import ROOT, git
from unit.release._support import PATTERN, advance, commit, latency_host, release_host, stamp, tag

REPO = str(ROOT)


def _write(host: Path, tag_name: str = "v1.0.0", reason: str = "rolled back before production") -> str:
    return write_rollback(str(host), str(host / "spec"), tag_name, reason, PATTERN)


def _refused(host: Path, code: str, *args: str) -> str:
    with pytest.raises(FindingError) as caught:
        _write(host, *args)
    assert caught.value.error.code == code
    return caught.value.error.message


def _tagged(tmp_path: Path) -> Path:
    host = release_host(tmp_path)
    stamp(host, "1.2.0")
    commit(host, "release one")
    tag(host, "v1.0.0")
    advance(host)
    return host


def test_rollback_record_waives_previous(tmp_path: Path) -> None:
    host = latency_host(tmp_path, run_it=False)
    tag(host, "v1.0.0")
    advance(host)
    assert check_next_release(str(host), str(host / "spec"), REPO).errors
    _write(host)
    assert not check_next_release(str(host), str(host / "spec"), REPO).errors


def test_rollback_unknown_tag_E925(tmp_path: Path) -> None:
    host = _tagged(tmp_path)
    assert "is not a tag of this clone" in _refused(host, "E925", "v7.7.7")
    tag(host, "v1.1.0-stage")
    assert "does not match the release tag pattern" in _refused(host, "E925", "v1.1.0-stage")
    assert not (host / "spec" / "extras" / "releases").exists()


def test_rollback_of_a_branch_that_is_not_a_tag_E925(tmp_path: Path) -> None:
    host = _tagged(tmp_path)
    git(host, "branch", "v2.0.0")
    assert "is not a tag of this clone" in _refused(host, "E925", "v2.0.0")
    assert not (host / "spec" / "extras" / "releases").exists()


def test_rollback_blank_reason_E926(tmp_path: Path) -> None:
    host = _tagged(tmp_path)
    for reason in ("", "   \n"):
        _refused(host, "E926", "v1.0.0", reason)
    assert not (host / "spec" / "extras" / "releases").exists()


def test_rollback_twice_E927(tmp_path: Path) -> None:
    host = _tagged(tmp_path)
    path = _write(host)
    before = Path(path).read_text(encoding="utf-8")
    assert path in _refused(host, "E927")
    assert Path(path).read_text(encoding="utf-8") == before


def test_rollback_record_written_under_spec_extras_and_passes_code_validation(tmp_path: Path) -> None:
    host = _tagged(tmp_path)
    path = Path(_write(host, reason="  the deploy was reverted  "))
    assert path == host / "spec" / "extras" / "releases" / "rollback-v1.0.0.json" == Path(rollback_path(str(host / "spec"), "v1.0.0"))
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["$schema"] == ROLLBACK_SCHEMA and record["id"] == rollback_id("v1.0.0") == "rollback-v1.0.0" and record["tag"] == "v1.0.0"
    assert record["commit"] == git(host, "rev-parse", "v1.0.0^{commit}") and record["reason"] == "the deploy was reverted"
    assert record["recorded_at"].endswith("Z") and record_problems(record, "v1.0.0") == []
    assert read_rollback(str(host / "spec"), "v1.0.0") == record
    assert read_rollback(str(host / "spec"), "v1.1.0") is None
    assert git(host, "status", "--porcelain", "--", "spec/extras/releases").startswith("??")  # written, not committed


def test_a_slash_in_the_tag_becomes_an_underscore_in_the_file_name(tmp_path: Path) -> None:
    assert rollback_path("spec", "rel/v1.0.0").endswith("rollback-rel_v1.0.0.json") and rollback_id("rel/v1.0.0") == "rollback-rel_v1.0.0"


@pytest.mark.parametrize("damage", ["missing-key", "blank-reason", "other-tag", "other-id", "reason-not-text", "not-an-object", "not-json"])
def test_rollback_record_missing_key_or_blank_reason_rejected(tmp_path: Path, damage: str) -> None:
    host = _tagged(tmp_path)
    path = Path(_write(host))
    record = json.loads(path.read_text(encoding="utf-8"))
    if damage == "missing-key":
        del record["commit"]
    elif damage == "blank-reason":
        record["reason"] = " "
    elif damage == "other-tag":
        record["tag"] = "v2.0.0"
    elif damage == "other-id":
        record["id"] = rollback_id("v2.0.0")
    elif damage == "reason-not-text":
        record["reason"] = 5
    path.write_text("{" if damage == "not-json" else json.dumps([] if damage == "not-an-object" else record), encoding="utf-8")
    with pytest.raises(FindingError) as caught:
        read_rollback(str(host / "spec"), "v1.0.0")
    assert caught.value.error.code == "E774" and "rollback-v1.0.0.json" in caught.value.error.message
    with pytest.raises(FindingError):  # a damaged record waives nothing: the check refuses it instead of passing
        check_next_release(str(host), str(host / "spec"), REPO)


def test_m9_adds_no_schema_file_entry_key_registry_unchanged() -> None:
    registry, _extension = generate_registry(str(ROOT))
    assert _serialize(registry) == (ROOT / "tests" / "fixtures" / "entry_key_registry_golden.json").read_text(encoding="utf-8")
    assert not [name for name in (ROOT / "schema").rglob("*") if "rollback" in name.name]
    assert "rollback" not in (ROOT / "tools" / "schema_registry.json").read_text(encoding="utf-8")
