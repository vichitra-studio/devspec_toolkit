"""``specdev align bind-legacy <spec_dir>`` and ``align propose --kind bindings`` (WI-M10-17): the command, not only the proposers.

Each test runs ``cli.main`` with the argv of a real call on a copy of the migrated mini host.  A person's answer to the
prompt is simulated with a patched ``input`` (an agent never answers it).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from specdev_tools.migration.worklist import WORKLIST_FILE

from ._bindings_support import align, fresh, records, run_line, specdev
from ._support import make_host, migrate, REAL_ROOT, tree_digest

FEE = "fix-late-fee-two-days"
GROUP_ITEM = "wl-08-legacy-binding-npx-jest-tests-fee-spec-ts"
FEE_LINE = f"specdev verify bind {FEE} --command 'npx jest tests/fee.spec.ts' --guard 'tests/fee\\.spec\\.ts'"


@pytest.fixture(scope="module")
def migrated(tmp_path_factory) -> Path:
    return migrate(tmp_path_factory.mktemp("bind_legacy_cli"))[0]


@pytest.fixture
def host(migrated, tmp_path) -> Path:
    return fresh(migrated, tmp_path)


def items(host: Path) -> dict[str, dict]:
    document = json.loads((host / "spec" / WORKLIST_FILE).read_text(encoding="utf-8"))
    return {item["id"]: item for item in document["items"]}


def test_bind_legacy_summary_flag(host):
    code, out, err = align(host, "bind-legacy", "--summary")
    assert code == 0, err
    assert out.splitlines()[:4] == [
        "bindings written: 0",
        "fixtures covered by a binding: 0",
        "fixtures made manual: 0 (0 attested)",
        "fixtures still without a binding or attestation: 6 (must be 0 before the first release)",
    ]
    assert f"  no binding: {FEE}" in out


def test_summary_writes_nothing(host):
    start = tree_digest(host)
    assert align(host, "bind-legacy", "--summary")[0] == 0
    assert tree_digest(host) == start


def test_bind_legacy_marks_a_group_resolved_when_all_its_binds_exist(host):
    assert align(host, "propose", "--kind", "bindings")[0] == 0
    assert items(host)[GROUP_ITEM]["resolved"] is False
    assert run_line(host, FEE_LINE)[0] == 0, "a person (or an agent) ran the printed line itself"
    code, out, err = align(host, "bind-legacy")
    assert code == 0, err
    assert f"closed   {GROUP_ITEM}" in out and "0 certain group(s) offered" in out
    closed = items(host)[GROUP_ITEM]
    assert closed["resolved"] is True and "every `verify bind` line of the group exists" in closed["note"]
    assert align(host, "bind-legacy")[1].count("closed") == 0, "a second run closes nothing again"


def test_nobody_answering_writes_nothing_and_says_so(host):
    code, out, err = align(host, "bind-legacy")
    assert code == 0, err
    assert not records(host)
    assert "not written: no person answered" in out and f"specdev verify bind {FEE}" in out


@pytest.mark.parametrize(("answer", "written"), [("y", 1), ("Y", 1), ("n", 0), ("", 0)])
def test_the_prompt_decides_what_is_written(host, answer, written):
    with patch("builtins.input", return_value=answer) as asked:
        code, out, err = align(host, "bind-legacy", stdin_tty=True)
    assert code == 0, err
    assert asked.call_count == 1 and f"{FEE_LINE.split(' --command')[0]}" in out
    assert len(records(host)) == written
    assert ("confirmed" in out) == bool(written)


def test_an_interrupted_prompt_declines(host):
    with patch("builtins.input", side_effect=EOFError):
        code, out, err = align(host, "bind-legacy", stdin_tty=True)
    assert code == 0, err
    assert not records(host) and "declined: nothing written" in out


def test_yes_writes_the_certain_groups_without_asking(host):
    with patch("builtins.input", side_effect=AssertionError("asked")):
        code, out, err = align(host, "bind-legacy", "--yes")
    assert code == 0, err
    assert list(records(host)) == ["ver-late-fee-two-days.json"]
    assert "written  fix-late-fee-two-days: binding ver-late-fee-two-days (stage prod, extras/verification/ver-late-fee-two-days.json)" in out
    assert "specdev verify run <binding-id>" in out


def test_the_printed_lines_carry_the_roots_that_make_them_run_from_any_folder(host):
    code, out, err = align(host, "bind-legacy")
    line = next(line.strip() for line in out.splitlines() if line.strip().startswith("specdev verify bind"))
    assert f"--repo-root {REAL_ROOT} --spec-root {host / 'spec'} --git-root {host}" in line


def test_json_envelope_lists_what_was_offered_written_and_closed(host):
    code, out, err = align(host, "bind-legacy", "--yes", "--json")
    assert code == 0, err
    document = json.loads(out)
    assert (document["status"], document["command"], document["action"], document["error_count"]) == ("PASS", "align", "bind-legacy", 0)
    assert [w["fixture"] for w in document["written"]] == [FEE] and document["written"][0]["file"] == "extras/verification/ver-late-fee-two-days.json"
    assert document["offered"][0]["answered"] is True and document["offered"][0]["lines"][0].startswith(FEE_LINE)
    assert {group["category"] for group in document["left"]} == {"needs-judgement"}


def test_a_spec_folder_that_is_not_in_migration_is_refused_in_one_line(tmp_path):
    host = make_host(tmp_path)
    code, out, err = align(host, "bind-legacy")
    assert code == 1 and out == ""
    assert err.startswith("align bind-legacy: ") and "is not in migration" in err and err.count("\n") == 1
    code, out, _err = align(host, "bind-legacy", "--json")
    assert code == 1 and "E520" in out


def test_propose_takes_bindings_as_a_kind_and_adds_one_item_per_group_and_case(host):
    code, out, err = align(host, "propose", "--kind", "bindings")
    assert code == 0, err
    assert out.startswith("align propose --kind bindings: 6 fixtures, 1 certain, 4 needs-judgement, 1 manual, 0 bound, 4 groups")
    assert "worklist: 6 item(s) added, 0 already listed" in out
    found = items(host)
    mine = [item for item in found.values() if item["kind"] in ("legacy-binding", "legacy-fixture")]
    assert len(mine) == 6 and {item["step"] for item in mine} == {"08"} and {item["audience"] for item in mine} == {"agent"} and not any(item["blocking"] for item in mine)
    assert FEE_LINE in found[GROUP_ITEM]["proposal"] and found[GROUP_ITEM]["proposal"].startswith("class: certain.")
    again = align(host, "propose", "--kind", "bindings")[1]
    assert "0 item(s) added, 6 already listed" in again


def test_a_resolved_item_stays_resolved_when_proposed_again(host):
    assert align(host, "propose", "--kind", "bindings")[0] == 0
    assert specdev("align", "triage", str(host / "spec"), "--repo-root", str(REAL_ROOT), "--git-root", str(host), "--resolve", GROUP_ITEM, "--note", "bound by hand later")[0] == 0
    assert align(host, "propose", "--kind", "bindings")[0] == 0
    assert items(host)[GROUP_ITEM]["resolved"] is True


def test_the_new_action_and_flag_are_in_the_help():
    code, out, _err = specdev("align", "--help")
    assert code == 0 and "bind-legacy" in out and "--summary" in out
