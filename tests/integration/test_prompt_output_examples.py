"""The Output Contract example of each prompt 00 to 15 passes what the toolkit checks (WI-M6c-12, the analogue of DEVSPEC-235).

Each example is read out of its prompt (``prompt_schema_sync._extract_output_contract``) and checked alone, with no
neighbours: (a) against the step schema, (b) by the step's deep validator, (c) by ``spec-check`` for E752 (a node id
written in prose).  Run alone, the examples' illustrative ids raise only isolation findings (W590, E740 ...), which
are not asserted on.  The anchor prompt and 16a to 16c are M8's: they are checked in the second half of this module
(every JSON block under their Output Contract heading, then the commands the prompts name run on the worked example).

``KNOWN_FAILING`` lists the checks a prompt fails today, with the bundle of ``preflight/M6c.md`` that rewrites the
prompt; each such case is ``xfail(strict=True)`` so that the bundle must remove its line when the example is fixed.
"""
from __future__ import annotations

import copy
import glob
import json
import re
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.generation import prompt_schema_sync as sync
from specdev_tools.validation.spec_check import run_spec_check_json
from specdev_tools.validation.validate import _run_deep_validation
from unit.trace._lock_support import EXAMPLE_HOST, ROOT

PROMPTS = ROOT / "prompts"
EXAMPLE_SPEC = EXAMPLE_HOST / "spec"
STEPS = ("00", "01", "02", "02a", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15")
PROSE_ID_CODE = "E752"
SCHEMA_CHECK, DEEP_CHECK, PROSE_CHECK = "schema", "deep", "prose"

KNOWN_FAILING: dict[tuple[str, str], str] = {}
"""``(check, step)`` to the reason and the bundle that fixes it; empty when every prompt passes today."""


def _prompt_path(step: str) -> str:
    (path,) = glob.glob(str(PROMPTS / f"prompt_{step}_*.md"))
    return path


def _example(step: str) -> dict[str, Any]:
    """The Output Contract example of the prompt of *step*; raises ``AssertionError`` when the prompt has none."""
    payload, line, problem = sync._extract_output_contract(_prompt_path(step))
    assert problem is None and isinstance(payload, dict), f"prompt {step} line {line}: {problem}"
    return payload


def _spec_file_name(step: str) -> str:
    """The file name the worked example gives to the artifact of *step* (``05_interface_contracts.json``)."""
    (path,) = [p for p in EXAMPLE_SPEC.glob("*.json") if re.match(rf"{step}_", p.name)]
    return path.name


def _schema_findings(step: str, payload: dict[str, Any]) -> list[SpecError]:
    """What prompt-sync's payload validation says about *payload* against the schema of *step* (JSON Schema validity)."""
    schema_file = next(f for f in sorted(glob.glob(str(ROOT / "schema" / "*.schema.json"))) if sync._schema_step_key(Path(f).name) == step)
    schema = json.loads(Path(schema_file).read_text(encoding="utf-8"))
    registry, problem = sync._schema_registry(ROOT)
    assert problem is None, problem
    body = {key: value for key, value in payload.items() if key != "$schema"}
    return sync._validate_output_payload(_prompt_path(step), 1, body, schema, registry)


def _isolated_spec(tmp_path: Path, step: str, payload: dict[str, Any]) -> Path:
    """A spec folder that holds *payload* alone, under the file name of *step*."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / _spec_file_name(step)).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return spec


def _deep_findings(tmp_path: Path, step: str, payload: dict[str, Any]) -> list[SpecError]:
    spec = _isolated_spec(tmp_path, step, payload)
    return _run_deep_validation(
        step, payload, str(ROOT), str(spec / _spec_file_name(step)), git_root=str(tmp_path), spec_root=str(spec)
    )


def _prose_id_findings(tmp_path: Path, step: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Every finding of code E752 that ``spec-check`` reports on the isolated example."""
    spec = _isolated_spec(tmp_path, step, payload)
    _errors, report = run_spec_check_json(str(ROOT), str(spec), git_root=str(tmp_path))
    return [f for check in report["checks"].values() for f in check.get("findings", []) if f["code"] == PROSE_ID_CODE]


def _cases(check: str) -> list[Any]:
    """One parameter per prompt step, marked ``xfail(strict=True)`` when ``KNOWN_FAILING`` lists it for *check*."""
    return [
        pytest.param(step, id=f"prompt_{step}", marks=pytest.mark.xfail(strict=True, reason=KNOWN_FAILING[(check, step)]))
        if (check, step) in KNOWN_FAILING
        else pytest.param(step, id=f"prompt_{step}")
        for step in STEPS
    ]


def test_prompt_set_is_the_seventeen_in_scope_prompts() -> None:
    names = sorted(Path(p).name for p in glob.glob(str(PROMPTS / "prompt_*.md")))
    in_scope = [n for n in names if re.match(r"prompt_(0\d|1[0-5])[a-z]?_", n)]
    assert [sync._step_from_prompt_name(n) for n in in_scope] == list(STEPS)
    assert not [n for n in in_scope if n.startswith("prompt_16")]
    assert len(in_scope) == 17


@pytest.mark.parametrize("step", _cases(SCHEMA_CHECK))
def test_example_validates_against_step_schema(step: str) -> None:
    assert _schema_findings(step, _example(step)) == []


@pytest.mark.parametrize("step", _cases(DEEP_CHECK))
def test_example_deep_validator_reports_no_error(step: str, tmp_path: Path) -> None:
    """Step 00 has no deep validator: its result is the empty list."""
    assert _deep_findings(tmp_path, step, _example(step)) == []


@pytest.mark.parametrize("step", _cases(PROSE_CHECK))
def test_example_writes_no_node_id_in_prose(step: str, tmp_path: Path) -> None:
    assert _prose_id_findings(tmp_path, step, _example(step)) == []


def test_example_with_a_node_id_in_prose_is_caught_by_the_e752_assertion(tmp_path: Path) -> None:
    """The prompt 05 example with the id of its own API written into the message of an error: E752 names that API."""
    payload = copy.deepcopy(_example("05"))
    api = payload["apis"][0]
    api["errors"][0]["message"] = f"The call to {api['api_id']} carries no valid auth token."
    found = _prose_id_findings(tmp_path, "05", payload)
    assert [f["code"] for f in found] == [PROSE_ID_CODE]
    assert api["api_id"] in found[0]["message"]


def test_example_with_a_removed_field_fails_the_schema_check() -> None:
    """The prompt 05 example with a stored ``trace`` array added (a field of the 1.1.1 shape): the schema check reports it."""
    payload = copy.deepcopy(_example("05"))
    payload["apis"][0]["trace"] = [{"id": "fr-example"}]
    assert _schema_findings("05", _example("05")) == []
    findings = _schema_findings("05", payload)
    assert findings and all(f.code == "E310" for f in findings)


# --- The Trinity prompts (WI-M8-13): the anchor prompt and 16a, 16b, 16c --------------------------------------------

import shutil

from specdev_tools.core.step_paths import refine_impl_context_substep
from unit.graph._synth import run_cli
from unit.trace._lock_support import git_copy_of_example, run_on_example

TRINITY = {
    "16anchor": "prompt_16_impl_context.md",
    "16a": "prompt_16a_impl_planner.md",
    "16b": "prompt_16b_impl_coder.md",
    "16c": "prompt_16c_impl_reviewer.md",
}
PLAN_FILE = "impl_context/ms_account_recovery_plan.json"
ITEM = "PWRESET_CONFIRM_REUSED_01"
TRINITY_BLOCKS = [("16anchor", 0), ("16a", 0), ("16b", 0), ("16b", 1), ("16c", 0), ("16c", 1)]
"""``(prompt, index of the JSON block under its Output Contract heading)``: 16b and 16c carry an input and an output block."""


def _trinity_blocks(key: str) -> list[dict[str, Any]]:
    """Every JSON block under the ``# Output Contract`` heading of the prompt *key* (to the end of the file), parsed."""
    text = (PROMPTS / TRINITY[key]).read_text(encoding="utf-8")
    heading = sync.OUTPUT_CONTRACT_HEADING_RE.search(text)
    assert heading, f"{TRINITY[key]} has no Output Contract heading"
    return [json.loads(m.group(1)) for m in sync.FENCED_JSON_RE.finditer(text[heading.end():])]


def _trinity_example(key: str, index: int) -> dict[str, Any]:
    blocks = _trinity_blocks(key)
    assert len(blocks) > index, f"{TRINITY[key]}: no block {index} under Output Contract"
    return blocks[index]


def _trinity_schema_file(key: str) -> str:
    return "16_anchor.schema.json" if key == "16anchor" else "16_impl_context.schema.json"


def test_trinity_prompts_carry_the_blocks_this_module_checks() -> None:
    assert {key: len(_trinity_blocks(key)) for key in TRINITY} == {"16anchor": 1, "16a": 1, "16b": 2, "16c": 2}


@pytest.mark.parametrize(("key", "index"), TRINITY_BLOCKS, ids=[f"{k}-{i}" for k, i in TRINITY_BLOCKS])
def test_trinity_example_validates_against_its_schema(key: str, index: int) -> None:
    payload = _trinity_example(key, index)
    schema = json.loads((ROOT / "schema" / _trinity_schema_file(key)).read_text(encoding="utf-8"))
    registry, problem = sync._schema_registry(ROOT)
    assert problem is None, problem
    assert sync._validate_output_schema_uri(payload, schema) is None
    body = {k: v for k, v in payload.items() if k != "$schema"}
    assert sync._validate_output_payload(str(PROMPTS / TRINITY[key]), 1, body, schema, registry) == []


def _trinity_spec(tmp_path: Path, key: str, payload: dict[str, Any]) -> tuple[Path, str]:
    """A spec folder holding *payload* alone (the anchor at the root, a plan under ``impl_context/``) and the step its deep validator runs under."""
    spec = tmp_path / "spec"
    if key == "16anchor":
        path, step = spec / "16_impl_context.json", "16"
    else:
        path, step = spec / "impl_context" / "ms_example_plan.json", refine_impl_context_substep("16a", payload)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    shutil.copytree(EXAMPLE_SPEC / "common", spec / "common")  # the seed manifest whose doc paths a plan's docs are checked against (W570 without it)
    return path, step


@pytest.mark.parametrize(("key", "index"), TRINITY_BLOCKS, ids=[f"{k}-{i}" for k, i in TRINITY_BLOCKS])
def test_trinity_example_deep_validator_reports_no_error(key: str, index: int, tmp_path: Path) -> None:
    payload = _trinity_example(key, index)
    path, step = _trinity_spec(tmp_path, key, payload)
    assert _run_deep_validation(step, payload, str(ROOT), str(path), git_root=str(tmp_path), spec_root=str(tmp_path / "spec")) == []


@pytest.mark.parametrize(("key", "index"), TRINITY_BLOCKS, ids=[f"{k}-{i}" for k, i in TRINITY_BLOCKS])
def test_trinity_example_writes_no_node_id_in_prose(key: str, index: int, tmp_path: Path) -> None:
    payload = _trinity_example(key, index)
    path, _step = _trinity_spec(tmp_path, key, payload)
    _errors, report = run_spec_check_json(str(ROOT), str(path.parents[1] if key != "16anchor" else path.parent), git_root=str(tmp_path))
    assert [f for check in report["checks"].values() for f in check.get("findings", []) if f["code"] == PROSE_ID_CODE] == []


def _write_draft(tmp_path: Path, name: str, document: dict[str, Any]) -> str:
    draft = tmp_path / name
    draft.write_text(json.dumps(document), encoding="utf-8")
    return str(draft)


def _clean_checks(host: Path) -> None:
    """``spec-check`` on *host* reports nothing from the checks that read plans, records, links and prose."""
    _errors, report = run_spec_check_json(str(ROOT), str(host / "spec"), git_root=str(host))
    for name in ("graph", "trace-lock", "records", "plan-records", "frozen-plans", "prose-ids", "computed-fields"):
        assert report["checks"][name].get("findings", []) == [], name


@pytest.fixture
def example_author(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Dev One")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "dev.one@example.com")


def _host_without_plan(tmp_path: Path, *, anchor: bool = True) -> Path:
    """The worked example as a git host whose plan (and, with ``anchor=False``, whose anchor) is gone, so the prompts' drafts can create them."""
    host = git_copy_of_example(tmp_path / "host")
    (host / "spec" / PLAN_FILE).unlink()
    if not anchor:
        (host / "spec" / "16_impl_context.json").unlink()
    code, out = run_on_example(host, "attest", "--prune")
    assert code == 0, out
    return host


def test_anchor_example_is_created_by_step_create_16(tmp_path: Path) -> None:
    host = _host_without_plan(tmp_path, anchor=False)
    draft = _write_draft(tmp_path, "anchor.json", _trinity_example("16anchor", 0))
    code, out = run_on_example(host, "step", "create", "16", "--from", draft)
    assert code == 0, out
    _clean_checks(host)
    assert json.loads((host / "spec" / "16_impl_context.json").read_text(encoding="utf-8"))["plan"]["milestone_index"][0]["status"] == "pending"
    code, out = run_on_example(host, "step", "create", "16", "--from", draft)
    assert code == 1 and "E767" in out


def test_anchor_row_form_inserts_a_row(tmp_path: Path) -> None:
    host = _host_without_plan(tmp_path)
    row = {"anchor_id": "anchor-ms-extra", "about": ["ms-account-recovery"], "checklist_id_prefix": "PWEXTRA", "summary": "One more row for the form."}
    code, out = run_on_example(host, "json", "insert", "--step", "16", ".plan.milestone_index", json.dumps(row))
    assert code == 0, out
    assert "anchor-ms-extra" in (host / "spec" / "16_impl_context.json").read_text(encoding="utf-8")


def test_16a_example_is_created_by_step_create_16a(tmp_path: Path) -> None:
    host = _host_without_plan(tmp_path)
    example = _trinity_example("16a", 0)
    code, out = run_on_example(host, "step", "create", "16a", "account_recovery", "--from", _write_draft(tmp_path, "plan.json", example))
    assert code == 0, out
    assert "lock entry written" in out
    _clean_checks(host)
    assert json.loads((host / "spec" / PLAN_FILE).read_text(encoding="utf-8")) == example
    code, out = run_on_example(host, "step", "create", "16a", "account_recovery", "--from", _write_draft(tmp_path, "plan.json", example))
    assert code == 1 and "E767" in out


def _normal(record: dict[str, Any]) -> dict[str, Any]:
    """A record without what the command fills in (the time, the hash, the author), which an example may show with any value."""
    return {k: v for k, v in record.items() if k not in ("recorded_at", "realises_hash", "git_author")}


def test_16b_16c_examples_are_what_the_commands_write(tmp_path: Path, example_author: None) -> None:
    """16b's input is created by ``step create 16a``; the two ``plan record`` calls and the open-item form give its output; 16c's ``review record`` gives its output."""
    host = _host_without_plan(tmp_path)
    plan_in, plan_out = _trinity_example("16b", 0), _trinity_example("16b", 1)
    code, out = run_on_example(host, "step", "create", "16a", "account_recovery", "--from", _write_draft(tmp_path, "plan.json", plan_in))
    assert code == 0, out
    path = host / "spec" / PLAN_FILE
    for record in plan_out["execution"]["records"]:
        code, out = run_on_example(host, "plan", "record", f"{ITEM}/{record['action']}", "--outcome", record["outcome"], "--note", record["note"])
        assert code == 0, out
    # The open item the example shows, written with the form for a block that holds records and no array.
    item = plan_out["execution"]["emergent_ambiguities"][0]
    code, out = run_cli("json", "patch", str(path), ".execution.emergent_ambiguities", json.dumps([item]), "--repo-root", str(ROOT))
    assert code == 0, out
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["plan"] == plan_out["plan"]
    assert [_normal(r) for r in written["execution"]["records"]] == [_normal(r) for r in plan_out["execution"]["records"]]
    assert written["execution"]["emergent_ambiguities"] == plan_out["execution"]["emergent_ambiguities"]
    _clean_checks(host)

    # 16c: the findings file of its section 1 and the command give the example's review block.
    review_in, review_out = _trinity_example("16c", 0), _trinity_example("16c", 1)
    assert review_in["plan"] == plan_out["plan"]
    assert [_normal(r) for r in review_in["execution"]["records"]] == [_normal(r) for r in plan_out["execution"]["records"]]
    text = (PROMPTS / TRINITY["16c"]).read_text(encoding="utf-8")
    findings = next(json.loads(m.group(1)) for m in sync.FENCED_JSON_RE.finditer(text) if '"vc:infra:findings"' in m.group(1))
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(findings), encoding="utf-8")
    block = review_out["review"]
    code, out = run_on_example(
        host, "review", "record", "ms-account-recovery", "--verdict", block["verdict"], "--findings-file", str(findings_path),
        "--next-actions", block["next_actions"], "--security-status", block["security_status"], "--ratings-json", json.dumps(block["ratings"]),
    )
    assert code == 0, out
    recorded = json.loads(path.read_text(encoding="utf-8"))["review"]
    assert {k: v for k, v in recorded.items() if k != "recorded_at"} == {k: v for k, v in block.items() if k != "recorded_at"}
    _clean_checks(host)


def test_open_item_forms_cover_the_three_states_of_the_plan(tmp_path: Path, example_author: None) -> None:
    """The three forms the 16b prompt gives for the first and later open items, in the order it gives them."""
    host = _host_without_plan(tmp_path)
    plan_in = _trinity_example("16b", 0)
    code, out = run_on_example(host, "step", "create", "16a", "account_recovery", "--from", _write_draft(tmp_path, "plan.json", plan_in))
    assert code == 0, out
    path = str(host / "spec" / PLAN_FILE)
    one = {"id": "amb-new-first", "description": "The first question.", "about": ["tc-confirm-reused-token"]}
    two = {"id": "amb-new-second", "description": "The second question.", "about": ["tc-confirm-reused-token"]}
    assert run_cli("json", "read", path, ".execution", "--repo-root", str(ROOT))[1].strip() == "null"
    assert run_cli("json", "patch", path, ".execution", json.dumps({"emergent_ambiguities": [one]}), "--repo-root", str(ROOT))[0] == 0
    assert run_cli("json", "insert", path, ".execution.emergent_ambiguities", json.dumps(two), "--repo-root", str(ROOT))[0] == 0
    assert [i["id"] for i in json.loads(Path(path).read_text(encoding="utf-8"))["execution"]["emergent_ambiguities"]] == ["amb-new-first", "amb-new-second"]
    # The state the prompt warns about: a block that holds records but no array refuses `insert`, `patch` of the array works.
    other = _host_without_plan(tmp_path / "second")
    run_on_example(other, "step", "create", "16a", "account_recovery", "--from", _write_draft(tmp_path, "plan.json", plan_in))
    assert run_on_example(other, "plan", "record", f"{ITEM}/a01", "--outcome", "done")[0] == 0
    other_path = str(other / "spec" / PLAN_FILE)
    assert run_cli("json", "insert", other_path, ".execution.emergent_ambiguities", json.dumps(one), "--repo-root", str(ROOT))[0] != 0
    assert run_cli("json", "patch", other_path, ".execution.emergent_ambiguities", json.dumps([one]), "--repo-root", str(ROOT))[0] == 0
    # The second form also covers a plan with no `execution` block (it creates the block).
    third = _host_without_plan(tmp_path / "third")
    run_on_example(third, "step", "create", "16a", "account_recovery", "--from", _write_draft(tmp_path, "plan.json", plan_in))
    third_path = str(third / "spec" / PLAN_FILE)
    assert run_cli("json", "patch", third_path, ".execution.emergent_ambiguities", json.dumps([one]), "--repo-root", str(ROOT))[0] == 0
    assert json.loads(Path(third_path).read_text(encoding="utf-8"))["execution"] == {"emergent_ambiguities": [one]}
