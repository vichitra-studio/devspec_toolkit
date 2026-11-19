"""A schema finding is known by its file and its place, and its message names the same file in both trees (M6a review round 2, G1-1).

The count rule of the step gate (``validation.step_gate.new_since_baseline``) needs two things of a schema error: its key
holds the file and the place of the violation, and its message is the same in the baseline tree (a temporary folder) and in
the working tree.  Every host here is the worked example with a bad value in ``04_fr_list.json`` or ``05_interface_contracts.json``;
the base commit holds the old defects and the working tree adds, fixes or moves some.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import commit_all, run_split, step_gate_host
from unit.graph._synth import ROOT

FR_FILE = "04_fr_list.json"
BAD_SCOPE = "bogus-scope"


def _edit(host: Path, name: str, change: Any) -> None:
    path = host / "spec" / name
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _fr(index: int, field: str, value: str) -> Any:
    return lambda document: document["functional_requirements"][index].__setitem__(field, value)


def _gate(capsys: pytest.CaptureFixture[str], host: Path, step: str, *flags: str) -> tuple[int, dict[str, Any]]:
    spec = str(host / "spec")
    code, out, _err = run_split(
        capsys, "spec-check", spec, "--repo-root", str(ROOT), "--spec-root", spec, "--git-root", str(host), "--step", step, "--json", *flags
    )
    return code, json.loads(out)["step_gate"]


def _places(findings: list[dict[str, Any]]) -> list[str]:
    """The ``<file> <jq path>`` of each schema E520 of *findings* that has a place (the one of the file as a whole is left out)."""
    return sorted(f"{f['file']} {f['jq_path']}" for f in findings if f["code"] == "E520" and f.get("jq_path") not in (None, "."))


def _host(tmp_path: Path, base: Any, working: Any, name: str = FR_FILE) -> Path:
    host = step_gate_host(tmp_path / "host")
    _edit(host, name, base)
    commit_all(host, "base")
    _edit(host, name, working)
    return host


def _both(*changes: Any) -> Any:
    def apply(document: Any) -> None:
        for change in changes:
            change(document)

    return apply


def test_the_new_error_is_the_one_named_and_the_old_one_is_debt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The base has a bad scope at FR[1]; the branch adds one at FR[0]: FR[0] blocks, FR[1] is debt."""
    host = _host(tmp_path, _fr(1, "scope", BAD_SCOPE), _both(_fr(1, "scope", BAD_SCOPE), _fr(0, "scope", BAD_SCOPE)))

    code, gate = _gate(capsys, host, "05")

    assert code == 1
    assert _places(gate["blocking"]) == [f"{FR_FILE} .functional_requirements[0].scope"]
    assert _places(gate["upstream_debt"]) == [f"{FR_FILE} .functional_requirements[1].scope"]


def test_fixing_the_named_error_clears_the_gate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = _host(tmp_path, _fr(1, "scope", BAD_SCOPE), _both(_fr(1, "scope", BAD_SCOPE), _fr(0, "scope", BAD_SCOPE)))
    assert _gate(capsys, host, "05")[0] == 1

    _edit(host, FR_FILE, _fr(0, "scope", "in"))

    code, gate = _gate(capsys, host, "05")
    assert code == 0 and gate["blocking"] == []
    assert _places(gate["upstream_debt"]) == [f"{FR_FILE} .functional_requirements[1].scope"]


def test_fixing_one_priority_and_adding_a_scope_error_names_the_scope_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The place is in the key: a fixed ``priority`` at FR[0] does not offset a new ``scope`` error at FR[1]."""
    host = _host(tmp_path, _fr(0, "priority", "bogus-priority"), _fr(1, "scope", BAD_SCOPE))

    code, gate = _gate(capsys, host, "05")

    assert code == 1
    assert _places(gate["blocking"]) == [f"{FR_FILE} .functional_requirements[1].scope"]


def test_known_limit_a_fixed_error_and_a_new_one_at_the_same_place_count_as_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The documented limit of the count rule: FR[1].scope fixed and FR[0].scope added is the same key, the count did not grow, so the gate is clear.

    The merge check (``spec-check`` plain) still lists the error; the step gate does not name it.
    """
    host = _host(tmp_path, _fr(1, "scope", BAD_SCOPE), _both(_fr(1, "scope", "in"), _fr(0, "scope", BAD_SCOPE)))

    code, gate = _gate(capsys, host, "05")

    assert code == 0 and gate["blocking"] == []
    assert _places(gate["upstream_debt"]) == [f"{FR_FILE} .functional_requirements[0].scope"]


def test_an_error_fixed_in_step_04_does_not_offset_a_new_one_in_step_05(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Keys differ by file: step 05's new schema error blocks step 06 although step 04 lost one."""
    host = _host(tmp_path, _fr(0, "scope", BAD_SCOPE), _fr(0, "scope", "in"))
    _edit(host, "05_interface_contracts.json", lambda document: document.__setitem__("owner", "bogus-owner"))

    code, gate = _gate(capsys, host, "06")

    assert code == 1
    blocking = [f for f in gate["blocking"] if f["code"] == "E520"]
    assert blocking and {f["file"] for f in blocking} == {"05_interface_contracts.json"}


def test_schema_findings_of_spec_check_json_carry_their_file_and_place(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host")
    _edit(host, FR_FILE, _fr(1, "scope", BAD_SCOPE))
    spec = str(host / "spec")

    _code, out, _err = run_split(capsys, "spec-check", spec, "--repo-root", str(ROOT), "--spec-root", spec, "--git-root", str(host), "--json")

    findings = json.loads(out)["checks"]["schema-validation"]["findings"]
    scope = [f for f in findings if "functional_requirements/1/scope" in f["message"]]
    assert [(f["file"], f["jq_path"]) for f in scope] == [(FR_FILE, ".functional_requirements[1].scope")]
