"""``spec-check --step`` and ``--paths`` end to end on host copies of the worked example (WI-M6a-12).

The scenarios are DOC sections 13.2, 13.8 and 13.9 and the cases of the pre-commit hook.  Hook tests run the entry command
of ``templates/pre-commit-config.host.yaml`` in a new process, with the staged filenames after ``--paths``, as pre-commit
does.  The same classification from three places is pinned by ``tests/integration/test_step_gate_layouts.py``; the
open-items waiting rules by ``tests/unit/validation/test_waiting_on.py``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import (
    commit_all,
    hook_config,
    hook_entry_argv,
    host_on_branch,
    insert_delta_items_with_the_cli,
    json_command,
    run_hook,
    run_split,
    start_branch,
    step_gate_host,
)
from specdev_tools.core.errors import make_error
from specdev_tools.validation.open_items import check_open_items
from specdev_tools.validation.touched_steps import SEED_EDIT_NOTE
from specdev_tools.validation.check_registry import check_result, register_check
from specdev_tools.validation.graph_checks.codes import GRAPH_CHECK_CODES
from unit.graph._synth import git
from unit.trace._lock_support import ROOT, run_on_example

SPEC_STEP_FILE = "spec/04_fr_list.json"
SEED_FILE = "docs/seed/seed_accounts.md"
STEP_HEADER = re.compile(r"^step gate: step (\S+)", re.MULTILINE)
BELOW_ITEMS = ["open_items", "broken_links_below_open_items"]
WAITING = {
    "api-below-items": ["amb-reset-seed"],
    "err-below-items-token-expired": ["amb-reset-criterion", "amb-reset-seed"],
}


def _flags(host: Path) -> list[str]:
    return ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]


def _gate(capsys: pytest.CaptureFixture[str], host: Path, *flags: str) -> tuple[int, dict[str, Any]]:
    """``spec-check <flags> --json`` in this process: the exit code and the ``step_gate`` object (``{}`` when none was printed)."""
    code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), *flags, "--json")
    return code, json.loads(out).get("step_gate", {})


def _plain_json(capsys: pytest.CaptureFixture[str], host: Path) -> dict[str, Any]:
    """The JSON of plain ``spec-check`` (no step)."""
    _code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--json")
    return json.loads(out)


def _pairs(findings: list[dict[str, Any]]) -> list[tuple[str, str | None]]:
    return sorted((finding["code"], finding.get("node_id")) for finding in findings)


def _headers(output: str) -> list[str]:
    return STEP_HEADER.findall(output)


# --- DOC 13.2: open items ---------------------------------------------------------------------------------------

def test_doc_13_2_open_items_waiting_backlog_and_merge_gate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host", BELOW_ITEMS)
    code, gate = _gate(capsys, host, "--step", "05")
    assert code == 0 and gate["blocking"] == []
    assert {w["error"]["node_id"]: w["waiting_on"] for w in gate["waiting"]} == WAITING
    assert _pairs(gate["own_warnings"]) == [("W630", "amb-reset-seed")]

    code, gate = _gate(capsys, host, "--step", "08")
    assert code == 1 and gate["waiting"] == []
    assert _pairs(gate["blocking"]) == [("E700", "api-below-items"), ("E700", "err-below-items-token-expired")]
    assert ("W630", "amb-reset-criterion") in _pairs(gate["own_warnings"])

    code, out, _err = run_split(capsys, "upstream-backlog", str(host / "spec"), "--repo-root", str(ROOT), "--json")
    assert code == 0
    assert [(r["group"], r["item_id"]) for r in json.loads(out)["records"]] == [
        ("seed", "amb-reset-seed"), ("04", "amb-reset-criterion")
    ]
    assert [e.code for e in check_open_items(str(host / "spec"), gate="merge")] == ["E631", "E631"]


def test_an_own_error_below_an_open_item_waits_and_blocks_once_the_item_is_deleted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host = step_gate_host(tmp_path / "host", BELOW_ITEMS)
    code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--step", "05")
    assert code == 0 and "WAITING (2)" in out and "RESULT: CLEAR" in out
    for artifact in ("05_interface_contracts", "08_fixtures"):
        json_command(capsys, "delete", str(host / "spec" / f"{artifact}.json"), ".ambiguities[0]")
    code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--step", "05")
    assert code == 1 and "WAITING" not in out
    assert "E700  [05 own]            api-below-items" in out and "RESULT: BLOCKED" in out


def test_clarify_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host")
    insert_delta_items_with_the_cli(host, capsys, "open_items")
    assert [e.code for e in check_open_items(str(host / "spec"), gate="merge")] == ["E631", "E631"]
    code, gate = _gate(capsys, host, "--step", "05")
    assert code == 0 and _pairs(gate["own_warnings"]) == [("W630", "amb-reset-seed")]

    seed = host / SEED_FILE
    seed.write_text(seed.read_text(encoding="utf-8") + "A reset link is sent by email only.\n", encoding="utf-8")
    json_command(
        capsys, "patch", str(host / SPEC_STEP_FILE), ".functional_requirements[0].acceptance_criteria[2].text",
        json.dumps("Given a token older than 30 minutes, when it is used, then the request is rejected."),
    )
    for artifact in ("05_interface_contracts", "08_fixtures"):
        json_command(capsys, "delete", str(host / "spec" / f"{artifact}.json"), ".ambiguities[0]")

    assert check_open_items(str(host / "spec"), gate="merge") == []
    code, gate = _gate(capsys, host, "--step", "05")
    assert code == 0 and gate["blocking"] == [] and gate["own_warnings"] == []
    assert "E763" in {finding["code"] for finding in gate["gate_owned"]}


# --- DOC 13.9: pending and new upstream ---------------------------------------------------------------------------

def test_doc_13_9_rows_3_4_pending_with_stub_and_new_upstream_blocks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], registered_checks: None
) -> None:
    # Row 3: no-dangling error of a requirement that no later step uses yet; the owned error is a stub until M6b.
    stub = make_error("E520", "stub: nothing uses fr-account-export yet", owner="step:08", node_id="fr-account-export")
    register_check("stub-no-dangling", lambda ctx: check_result([stub]))
    host = step_gate_host(tmp_path / "host", ["fr_nothing_uses"])
    code, gate = _gate(capsys, host, "--step", "04")
    assert code == 0 and gate["blocking"] == []
    assert {owner: _pairs(found) for owner, found in gate["pending"].items() if owner == "08"} == {
        "08": [("E520", "fr-account-export")]
    }

    # Row 4: an error added on a branch whose merge-base was clean blocks the next step as new upstream.
    branch = host_on_branch(tmp_path / "branch", on_branch=["broken_link_in_step_04"])
    code, out, _err = run_split(capsys, "spec-check", str(branch / "spec"), *_flags(branch), "--step", "05")
    assert code == 1
    assert "(merge-base)" in out.splitlines()[0]
    assert "E700  [04 new upstream]   fr-broken-link" in out


def test_the_same_error_on_the_default_branch_is_upstream_debt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = host_on_branch(tmp_path / "host", on_default=["broken_link_in_step_04"], on_branch=["fr_nothing_uses"])
    code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--step", "05")
    assert code == 0 and "(merge-base)" in out.splitlines()[0]
    assert "UPSTREAM DEBT (1)" in out and "04: 1" in out and "BLOCKING" not in out
    code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--step", "04")
    assert code == 1 and "E700  [04 own]" in out


def test_a_node_renamed_on_the_branch_keeps_its_old_error_as_debt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # E761 (a link with no lock entry) survives a rename; a broken link (E700) cannot: `node rename` refuses with E770.
    host = step_gate_host(tmp_path / "host", ["fr_nothing_uses"], attested=False, commit=True)
    code, gate = _gate(capsys, host, "--step", "04")
    assert code == 1 and _pairs(gate["blocking"]) == [("E761", "fr-account-export")]
    start_branch(host)
    code, out = run_on_example(host, "node", "rename", "fr-account-export", "fr-account-download")
    assert code == 0, out
    commit_all(host, "rename the requirement")
    code, gate = _gate(capsys, host, "--step", "05")
    assert code == 0 and gate["blocking"] == []
    assert _pairs(gate["upstream_debt"]) == [("E761", "fr-account-download")]


# --- WI-01 cases through the CLI ----------------------------------------------------------------------------------

def test_owner_rows_on_step_gate_corpus(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    deltas = [
        "broken_link_in_step_04", "broken_link_in_step_05", "uncovered_capability", "glossary_drift",
        "missing_seed_file", "open_items",
    ]
    payload = _plain_json(capsys, step_gate_host(tmp_path / "host", deltas))
    findings = [finding for check in payload["checks"].values() for finding in check.get("findings", [])]
    steps = {f"step:{step}" for step in json.loads((ROOT / "tools" / "step_order.json").read_text(encoding="utf-8"))["steps"]}
    assert findings and all(finding.get("owner") in steps | {"merge-check"} for finding in findings)
    owners: dict[str, set[str]] = {}
    for finding in findings:
        owners.setdefault(finding["code"], set()).add(finding["owner"])
    assert {code: owners[code] for code in ("E590", "E607", "E608", "E520", "E700", "W630")} == {
        "E590": {"step:02"},
        "E607": {"step:03"},
        "E608": {"merge-check"},
        "E520": {"merge-check"},
        "E700": {"step:04", "step:05"},
        "W630": {"step:05", "step:08"},
    }


def test_devspec_201_e590_case_through_the_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host", ["uncovered_capability"])
    code, gate = _gate(capsys, host, "--step", "01")
    assert code == 0 and gate["blocking"] == []
    assert _pairs(gate["pending"]["02"]) == [("E590", None)]
    code, gate = _gate(capsys, host, "--step", "02")
    assert code == 1 and _pairs(gate["blocking"]) == [("E590", None)]


def test_e607_blocks_in_step_03_and_is_pending_in_step_02(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host", ["glossary_drift"])
    code, gate = _gate(capsys, host, "--step", "02")
    assert code == 0 and _pairs(gate["pending"]["03"]) == [("E607", None)]
    code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--step", "03")
    assert code == 1 and "E607  [03 own]" in out


@pytest.mark.parametrize("step", ["00", "14"])
def test_e608_is_gate_owned_in_step_00_and_step_14(tmp_path: Path, capsys: pytest.CaptureFixture[str], step: str) -> None:
    host = step_gate_host(tmp_path / "host")
    code, gate = _gate(capsys, host, "--step", step)
    blocking = [f["code"] for f in gate["blocking"]]  # step 14 owns the example's graph-check findings; E608 is never among them
    assert code == (1 if blocking else 0) and set(blocking) <= GRAPH_CHECK_CODES
    assert [(f["code"], f["owner"]) for f in gate["gate_owned"] if f["code"] == "E608"] == [("E608", "merge-check")]


# --- the hook: the entry command of the template with the staged filenames ----------------------------------------

def test_entry_command_is_invoked_with_filenames_as_pre_commit_does(tmp_path: Path) -> None:
    config = hook_config()
    assert config["pass_filenames"] is True and config["require_serial"] is True
    argv = hook_entry_argv()
    assert argv[-1] == "--paths"
    assert {"--repo-root", "--spec-root", "--git-root"} <= set(argv)
    host = step_gate_host(tmp_path / "host")
    done = run_hook(host, [SPEC_STEP_FILE])
    assert done.returncode == 0, done.stderr
    assert "unrecognized arguments" not in done.stderr
    assert _headers(done.stdout) == ["04"]


def test_zero_filenames_after_paths_exits_0_and_runs_no_check(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host")
    done = run_hook(host, [])
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")


def test_listed_paths_that_map_to_no_step_exit_0_and_say_so_on_stderr(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host")
    done = run_hook(host, ["README.md", "sepc/04_fr_list.json"])
    assert (done.returncode, done.stdout) == (0, "")
    assert done.stderr.strip() == "no step gated: no listed path maps to a step"


def test_2000_paths_map_correctly(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host")
    unmapped = [f"src/package{n % 40}/module{n}.py" for n in range(1996)]
    done = run_hook(host, [*unmapped[:1000], SPEC_STEP_FILE, *unmapped[1000:], SEED_FILE, "spec/05_interface_contracts.json", "README.md"])
    assert done.returncode == 0, done.stderr
    assert _headers(done.stdout) == ["00", "02", "04", "05"]
    assert "outside the host root" not in done.stderr


def test_absolute_and_git_root_relative_paths_map_the_same_from_another_cwd(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host")
    relative = run_hook(host, [SPEC_STEP_FILE, SEED_FILE])
    absolute = run_hook(host, [str(host / SPEC_STEP_FILE), str(host / SEED_FILE)], cwd=host / "docs", absolute_roots=True)
    from_docs = run_hook(host, [SPEC_STEP_FILE, SEED_FILE], cwd=host / "docs", absolute_roots=True)
    assert relative.returncode == absolute.returncode == from_docs.returncode == 0, from_docs.stderr
    assert _headers(relative.stdout) == _headers(absolute.stdout) == _headers(from_docs.stdout) == ["00", "02", "04"]


def test_staged_step_and_seed_edit_run_the_mapped_steps(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host", ["broken_link_in_step_04"])
    done = run_hook(host, [SEED_FILE, SPEC_STEP_FILE])
    assert _headers(done.stdout) == ["00", "02", "04"]
    assert done.returncode == 1 and "E700  [04 own]" in done.stdout
    assert SEED_EDIT_NOTE in done.stderr


def test_schema_error_in_the_staged_step_file_exits_1(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host")
    path = host / SPEC_STEP_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    document["functional_requirements"][0]["priority"] = "bogus-priority"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    blocked = run_hook(host, [SPEC_STEP_FILE])
    assert blocked.returncode == 1 and "E520  [04 own]" in blocked.stdout and "RESULT: BLOCKED" in blocked.stdout
    earlier = run_hook(host, ["spec/03_glossary.json"])
    assert earlier.returncode == 0 and "PENDING" in earlier.stdout and "RESULT: CLEAR" in earlier.stdout


def test_merge_check_owned_finding_elsewhere_does_not_block_the_hook(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host", ["missing_seed_file"])
    done = run_hook(host, [SPEC_STEP_FILE], flags=["--detail", "all"])
    assert done.returncode == 0, done.stdout
    assert re.search(r"E520\s+\[merge-check\]\s+-\s+Seed 'seed-ghost'", done.stdout)


# --- DOC 13.8 row 2 ---------------------------------------------------------------------------------------------

def test_doc_13_8_row_2_seed_stage_runs_the_mapped_steps_and_prints_the_suspect_line(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host")
    done = run_hook(host, [SEED_FILE])
    assert done.returncode == 0, done.stdout
    assert _headers(done.stdout) == ["00", "02"]
    assert SEED_EDIT_NOTE in done.stderr


def test_manifest_edit_with_a_missing_seed_file_is_gate_owned_and_the_hook_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host = step_gate_host(tmp_path / "host", ["missing_seed_file"])
    done = run_hook(host, ["spec/common/seed_manifest.json"], flags=["--detail", "all"])
    assert done.returncode == 0, done.stdout
    assert _headers(done.stdout) and "GATE-OWNED" in done.stdout
    assert re.search(r"E520\s+\[merge-check\]\s+-\s+Seed 'seed-ghost'", done.stdout)
    code, out, err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host))
    assert code == 1 and "seed-ghost" in out + err


# --- W630 and the environment -----------------------------------------------------------------------------------

def test_w630_does_not_block_with_warnings_as_errors_or_a_promote_request(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host", ["open_items"])
    env = {"SPECDEV_WARNINGS_AS_ERRORS": "1", "SPECDEV_PROMOTE_CODES": "W630"}
    done = run_hook(host, ["spec/05_interface_contracts.json"], env=env)
    assert done.returncode == 0, done.stdout
    assert "W630  [05 own]" in done.stdout and "RESULT: CLEAR" in done.stdout


# --- new since the baseline is a count per key (F1-1) -----------------------------------------------------------

def _edit_spec_file(host: Path, relative: str, edit: Any) -> None:
    """Apply *edit* to the parsed JSON of ``host/<relative>`` and write it back."""
    path = host / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    edit(document)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _commit_on_branch(host: Path, message: str) -> None:
    from integration._step_gate_support import attest

    attest(host)
    commit_all(host, message)


def test_a_second_schema_error_of_one_file_is_new_upstream_while_the_old_one_is_debt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host = step_gate_host(tmp_path / "host")
    _edit_spec_file(host, SPEC_STEP_FILE, lambda doc: doc["functional_requirements"][0].update(scope="bogus"))
    commit_all(host, "one schema error on the default branch")
    start_branch(host)
    _edit_spec_file(host, SPEC_STEP_FILE, lambda doc: doc["functional_requirements"][1].update(scope="bogus"))
    _commit_on_branch(host, "a second schema error")
    code, gate = _gate(capsys, host, "--step", "05")
    assert code == 1 and gate["result"] == "blocked"
    # the default branch's tree has two E520 (the bad scope and the "unevaluated properties" one that follows from it): both are debt
    assert [f["message"].split(":", 1)[1].split(" is not")[0] for f in gate["blocking"]] == ["functional_requirements/1/scope: 'bogus'"]
    assert len(gate["upstream_debt"]) == 2 and {f["owner"] for f in gate["upstream_debt"]} == {"step:04"}
    code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), "--step", "05")
    assert code == 1 and "BLOCKING (1)" in out and "UPSTREAM DEBT (2)" in out and "[04 new upstream]" in out


def test_an_insert_before_an_old_error_leaves_it_upstream_debt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host", ["broken_link_in_step_04"], commit=True)
    start_branch(host)

    def insert_first(doc: dict[str, Any]) -> None:
        added = json.loads(json.dumps(doc["functional_requirements"][0]))
        added["fr_id"] = "fr-inserted-first"
        for number, criterion in enumerate(added["acceptance_criteria"], 1):
            criterion["criterion_id"] = f"ac-inserted-first-{number}"
        doc["functional_requirements"].insert(0, added)
    _edit_spec_file(host, SPEC_STEP_FILE, insert_first)
    _commit_on_branch(host, "insert a requirement before the broken one")
    code, gate = _gate(capsys, host, "--step", "05")
    assert [(f["code"], f.get("node_id")) for f in gate["upstream_debt"]] == [("E700", "fr-broken-link")]
    assert [f["code"] for f in gate["blocking"] if f["code"] == "E700"] == []
    assert code == 0, gate["blocking"]
