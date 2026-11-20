"""``specdev third-party pin`` through the CLI, on a git copy of the worked example."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from unit.trace._lock_support import git_copy_of_example, run_on_example

ARGON = "tp-argon2"
LOCK = Path("spec") / "extras" / "trace.lock.json"
SKETCH = Path("spec") / "02_system_sketch.json"


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return git_copy_of_example(tmp_path / "host")


def test_pin_marks_the_relying_links_suspect_and_stale_lists_them(host: Path) -> None:
    code, out = run_on_example(host, "third-party", "pin", ARGON, "0.42.0")
    assert code == 0, out
    stale_code, stale = run_on_example(host, "stale")
    assert "relies_on -> tp-argon2 (content_changed" in stale
    assert "verifies -> api-password-reset-confirm (upstream_changed, roots: tp-argon2)" in stale


def test_pin_prints_the_suspect_count_by_step_and_the_change_milestone_reminder(host: Path) -> None:
    code, out = run_on_example(host, "third-party", "pin", ARGON, "0.42.0")
    assert code == 0
    assert "patched tp-argon2 (02_system_sketch.json .third_parties[0])" in out
    assert "newly suspect: 14 links (step 05: 1, step 06: 1, step 08: 2" in out
    assert "change milestone whose task criteria refine the obligations that rely on the third party" in out


def test_pin_json_carries_the_suspect_count_and_the_reminder(host: Path) -> None:
    code, out = run_on_example(host, "third-party", "pin", ARGON, "0.42.0", "--json")
    document = json.loads(out)
    assert code == 0 and document["command"] == "third-party pin" and document["written"] is True
    assert sum(item["count"] for item in document["newly_suspect"]) == 14 and "change milestone" in document["reminder"]


def test_pin_writes_no_lock_entry_for_the_pin_edit(host: Path) -> None:
    before = (host / LOCK).read_text(encoding="utf-8")
    code, out = run_on_example(host, "third-party", "pin", ARGON, "0.42.0")
    assert code == 0 and "lock entry" not in out
    assert (host / LOCK).read_text(encoding="utf-8") == before


@pytest.mark.parametrize(("node", "version", "text"), [
    ("api-password-reset-confirm", "1.0", "E706 'api-password-reset-confirm' is of kind api, not a third party"),
    ("tp-nope", "1.0", "E706 no node with the id 'tp-nope'"),
    (ARGON, "latest", "E336 the pin 'latest' of 'tp-argon2' is not an exact version"),
])
def test_pin_of_a_node_that_is_not_a_third_party_is_refused(host: Path, node: str, version: str, text: str) -> None:
    before = (host / SKETCH).read_text(encoding="utf-8")
    code, out = run_on_example(host, "third-party", "pin", node, version)
    assert code == 1 and text in out
    assert (host / SKETCH).read_text(encoding="utf-8") == before


def test_an_unchanged_pin_writes_nothing_and_says_so(host: Path) -> None:
    before = {path: path.read_bytes() for path in (host / "spec").rglob("*.json")}
    code, out = run_on_example(host, "third-party", "pin", ARGON, "0.41.1")
    assert code == 0 and out.strip() == "tp-argon2 already has the pin 0.41.1; nothing written"
    code, out = run_on_example(host, "third-party", "pin", ARGON, "  0.41.1 ", "--json")
    assert code == 0 and json.loads(out) == {"command": "third-party pin", "id": ARGON, "pin": "0.41.1", "written": False}
    assert {path: path.read_bytes() for path in (host / "spec").rglob("*.json")} == before


def test_the_pin_is_written_stripped(host: Path) -> None:
    code, out = run_on_example(host, "third-party", "pin", ARGON, " 0.42.0 ")
    assert code == 0, out
    document = json.loads((host / SKETCH).read_text(encoding="utf-8"))
    assert [item["pin"] for item in document["third_parties"] if item["third_party_id"] == ARGON] == ["0.42.0"]
