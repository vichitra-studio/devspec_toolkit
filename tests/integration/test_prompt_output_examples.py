"""The Output Contract example of each prompt 00 to 15 passes what the toolkit checks (WI-M6c-12, the analogue of DEVSPEC-235).

Each example is read out of its prompt (``prompt_schema_sync._extract_output_contract``) and checked alone, with no
neighbours: (a) against the step schema, (b) by the step's deep validator, (c) by ``spec-check`` for E752 (a node id
written in prose).  Run alone, the examples' illustrative ids raise only isolation findings (W590, E740 ...), which
are not asserted on.  The anchor prompt and 16a to 16c are M8's and are not in the set; 13a is retired by M6c.

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
    in_scope = [n for n in names if re.match(r"prompt_(0\d|1[0-5])[a-z]?_", n) and not n.startswith("prompt_13a_")]
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
