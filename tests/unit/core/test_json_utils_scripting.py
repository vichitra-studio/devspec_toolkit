"""``specdev json patch --batch OPS_FILE``: many operations, one validation, one atomic write (DEVSPEC-240)."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from specdev_tools.core import json_utils
from specdev_tools.core.json_utils import JsonUtilsError, json_patch, json_patch_batch
from unit.graph._synth import ROOT
from unit.trace._lock_support import EXAMPLE_HOST


@pytest.fixture
def target(tmp_path: Path) -> Path:
    """A copy of the worked example governance file (schema-bound, three rules)."""
    path = tmp_path / "10_governance.json"
    shutil.copyfile(EXAMPLE_HOST / "spec" / "10_governance.json", path)
    return path


def _ops(tmp_path: Path, ops: list) -> Path:
    path = tmp_path / "ops.json"
    path.write_text(json.dumps(ops), encoding="utf-8")
    return path


def _text_ops(count: int = 3) -> list[dict]:
    return [{"op": "patch", "path": f".rules[{n}].text", "value": f"Rule {n} is checked on every pull request."} for n in range(count)]


def test_batch_equals_sequential_patches(tmp_path: Path, target: Path) -> None:
    sequential = tmp_path / "seq.json"
    sequential.write_bytes(target.read_bytes())
    ops = _text_ops()
    assert json_patch_batch(str(target), str(_ops(tmp_path, ops)), repo_root=str(ROOT)) == f"Applied 3 operations to {target}"
    for op in ops:
        json_patch(str(sequential), op["path"], json.dumps(op["value"]), validate=False)
    assert target.read_bytes() == sequential.read_bytes()


def test_batch_validates_once(tmp_path: Path, target: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(json_utils, "_ws1_differential_check", lambda *args, **kwargs: calls.append("check"))
    json_patch_batch(str(target), str(_ops(tmp_path, _text_ops())))
    assert calls == ["check"]


def test_batch_with_a_bad_item_writes_nothing_and_names_the_item(tmp_path: Path, target: Path) -> None:
    before = target.read_bytes()
    ops = [*_text_ops(1), {"op": "patch", "path": ".rules[", "value": 1}]
    with pytest.raises(JsonUtilsError, match=r"batch item 1 \(patch \.rules\["):
        json_patch_batch(str(target), str(_ops(tmp_path, ops)))
    assert target.read_bytes() == before


@pytest.mark.parametrize("item, reason", [
    ({"op": "rename", "path": ".owner", "value": 1}, "'op' must be one of"),
    ({"op": "patch", "value": 1}, "'path' must be a jq path"),
    ({"op": "patch", "path": ".owner"}, "'value' is missing"),
])
def test_batch_refuses_a_malformed_item(tmp_path: Path, target: Path, item: dict, reason: str) -> None:
    with pytest.raises(JsonUtilsError, match=reason):
        json_patch_batch(str(target), str(_ops(tmp_path, [item])))


def test_batch_refuses_path_with_batch(tmp_path: Path, target: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    ops = _ops(tmp_path, _text_ops(1))
    monkeypatch.setattr(sys, "argv", ["json", "patch", str(target), ".owner", '"x"', "--batch", str(ops)])
    with pytest.raises(SystemExit) as stop:
        json_utils.main()
    assert stop.value.code == 1 and "give no path or value" in capsys.readouterr().err


def test_patch_without_batch_still_needs_path_and_value(target: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["json", "patch", str(target), ".owner"])
    with pytest.raises(SystemExit) as stop:
        json_utils.main()
    assert stop.value.code == 2 and "arguments are required: path, value" in capsys.readouterr().err


def test_batch_mixes_patch_insert_delete(tmp_path: Path, target: Path) -> None:
    rule = json.loads(target.read_text(encoding="utf-8"))["rules"][0]
    ops = [
        *_text_ops(1),
        {"op": "insert", "path": ".rules", "value": {**rule, "rule_id": "rule-new"}},
        {"op": "delete", "path": ".rules[1]"},
    ]
    before = [r["rule_id"] for r in json.loads(target.read_text(encoding="utf-8"))["rules"]]
    json_patch_batch(str(target), str(_ops(tmp_path, ops)), repo_root=str(ROOT))
    rules = json.loads(target.read_text(encoding="utf-8"))["rules"]
    assert rules[0]["text"] == "Rule 0 is checked on every pull request."
    assert [r["rule_id"] for r in rules] == [before[0], before[2], "rule-new"]


def test_batch_dry_run_summarises_and_writes_nothing(tmp_path: Path, target: Path) -> None:
    before = target.read_bytes()
    ops = [{"op": "patch", "path": ".rules[0].text", "value": "Every pull request passes the merge check."}] * 7
    text = json_patch_batch(str(target), str(_ops(tmp_path, ops)), dry_run=True, repo_root=str(ROOT))
    assert text.splitlines()[0] == f"[dry-run] Would apply 7 operations to {target}"
    assert text.splitlines()[-1] == "  ... and 2 more operations"
    whole = json_patch_batch(str(target), str(_ops(tmp_path, ops)), dry_run=True, show_file=True, repo_root=str(ROOT))
    assert json.loads(whole.split(":\n", 1)[1])["rules"][0]["text"] == "Every pull request passes the merge check."
    assert target.read_bytes() == before


def test_read_json_flag_keeps_string_quotes(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    path.write_text('{"title": "Title", "n": null}', encoding="utf-8")
    assert json.loads(json_utils.json_read(str(path), ".title", as_json=True) or "") == "Title"
    assert json_utils.json_read(str(path), ".title", as_json=True) == '"Title"'
    assert json_utils.json_read(str(path), ".n", as_json=True) == "null"


def test_read_without_json_flag_prints_raw_scalar(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    path.write_text('{"title": "Title"}', encoding="utf-8")
    assert json_utils.json_read(str(path), ".title") == "Title"


def test_a_batch_item_that_matches_nothing_refuses_the_batch(tmp_path: Path, target: Path) -> None:
    """H round 1 B1-2: a stale selector in a batch is refused as it is on its own, and nothing is written."""
    before = target.read_bytes()
    for stale in (
        {"op": "patch", "path": '.rules[]|select(.id=="no-such-rule").text', "value": "x"},
        {"op": "delete", "path": ".zzz"},
        {"op": "delete", "path": ".rules[9]"},
    ):
        ops = _ops(tmp_path, [_text_ops(1)[0], stale])
        with pytest.raises(JsonUtilsError, match=r"batch item 1 \(.*matches nothing"):
            json_patch_batch(str(target), str(ops), repo_root=str(ROOT))
        assert target.read_bytes() == before


def test_patch_with_an_index_past_the_end_matches_nothing(tmp_path: Path, target: Path) -> None:
    """H round 1 C-03: an index past the end of an array is "matches nothing", not a padded array."""
    before = target.read_bytes()
    with pytest.raises(JsonUtilsError, match="matches nothing"):
        json_patch(str(target), ".rules[500].text", '"x"', validate=False)
    assert target.read_bytes() == before
    json_patch(str(target), ".rules[-1].text", '"Rule is checked on every pull request."', validate=False)
