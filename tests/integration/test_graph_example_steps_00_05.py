"""The worked example (password reset) for steps 00-05 on the spec-graph shape.

``tests/fixtures/graph_example/`` is the single worked-example corpus of the release: M3 extends it
with steps 06-16, M4 builds its graph tests on it.  These tests pin that the seven files are valid
against the real schemas, validators, registry and ``spec-check``, with a known set of warnings.
"""
from __future__ import annotations

import copy
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

import _graph_example as shared
from specdev_tools.core.changelog_parser import get_toolkit_version
from specdev_tools.core.schema_validate import validate_data_against_schema
from specdev_tools.validation.spec_check import run_spec_check_json
from specdev_tools.validation.validate import DEEP_VALIDATORS
from specdev_tools.validation.graph_checks.codes import GRAPH_CHECK_CODES
from unit.graph._synth import run_cli as _run_cli

_ROOT = shared.ROOT
_EXAMPLE = shared.EXAMPLE
_SPEC = shared.SPEC
_FILES = (
    "00_charter.json",
    "01_capabilities.json",
    "02_system_sketch.json",
    "02a_delivery_baseline.json",
    "03_glossary.json",
    "04_fr_list.json",
    "05_interface_contracts.json",
)
_DEEP_STEPS = {
    "01_capabilities.json": "01",
    "02_system_sketch.json": "02",
    "02a_delivery_baseline.json": "02a",
    "04_fr_list.json": "04",
    "05_interface_contracts.json": "05",
}
_SEED_ID = shared.SEED_ID

_EXPECTED_KINDS: dict[str, str] = {
    "scope-password-reset": "scope-item",
    "scope-sms-reset": "scope-item",
    "asm-member-controls-email": "assumption",
    "risk-reset-link-takeover": "risk",
    "sh-support-lead": "stakeholder",
    "need-fewer-reset-tickets": "need",
    "seg-registered-member": "segment",
    "metric-recovery-time": "metric",
    "metric-reset-completion-rate": "metric",
    "con-staged-delivery": "constraint",
    "cap-account-recovery": "capability",
    "identity-service": "component",
    "conn-identity-to-mailrelay": "connection",
    "tp-argon2": "third-party",
    "tp-mailrelay": "third-party",
    "dev": "environment",
    "ci": "environment",
    "staging": "environment",
    "prod": "environment",
    "contract-tests": "gate",
    "secret-reset-token-signing-key": "secret",
    "secret-mailrelay-api-key": "secret",
    "term-reset-token": "term",
    "term-reset-email-delivery-time-p95": "term",  # step 07's NFR metric must be a glossary term (E590)
    "fr-password-reset": "fr",
    "fr-password-reset-request": "fr",
    "ac-password-reset-1": "criterion",
    "ac-password-reset-2": "criterion",
    "ac-password-reset-3": "criterion",
    "ac-password-reset-request-1": "criterion",
    "ac-password-reset-request-2": "criterion",
    "api-password-reset-confirm": "api",
    "err-password-reset-confirm-token-expired": "api-error",
}

# Warnings about the 00-05 files that the example produces by construction.  The warnings about the files of
# steps 06-16 are pinned in test_graph_example_steps_06_16.py; spec-check runs on the whole folder here too, and
# this test keeps only the findings that name a 00-05 file or the seed.
_PINNED_WARNINGS = Counter(
    {
        "W555": 1,  # the seed has no out-of-scope section (only a prose line), so the lint counts 0 of the 3 it expects
        "W594": 2,  # 01 and 03 restate the design's wording with little token overlap upstream
    }
)

# The same set with the file each warning is about (the errors carry no file attribute, so the subject is a needle
# in the rendered message: a file name, or the code's own name for the seed lint).
_PINNED_WARNING_SUBJECTS = Counter(
    {
        ("W555", "STEP00_SEED_OUT_OF_SCOPE_THIN"): 1,
        ("W594", "01_capabilities.json"): 1,
        ("W594", "03_glossary.json"): 1,
    }
)


def _load(name: str) -> dict[str, Any]:
    return shared.load(name)


def _example_nodes() -> list[shared.Node]:
    return shared.nodes_of(_FILES)


def _validated(doc: dict[str, Any]) -> list[tuple[tuple, str]]:
    return validate_data_against_schema(str(_ROOT), doc)


@pytest.fixture(scope="module")
def stamped_example(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A copy of the example with the toolkit version stamped, so it follows every version bump."""
    copied = tmp_path_factory.mktemp("graph_example") / "graph_example"
    shutil.copytree(_EXAMPLE, copied)
    version = get_toolkit_version(_ROOT)
    (copied / "spec" / "specdev_version").write_text(json.dumps({"toolkit_version": version}), encoding="utf-8")
    return copied


@pytest.mark.parametrize("name", _FILES)
def test_all_seven_files_validate_against_schemas(name: str) -> None:
    assert _validated(_load(name)) == []


@pytest.mark.parametrize("name", sorted(_DEEP_STEPS))
def test_deep_validators_return_no_error(name: str) -> None:
    context = {"spec_root": str(_SPEC)}
    errors = DEEP_VALIDATORS[_DEEP_STEPS[name]](_load(name), str(_ROOT), context)
    assert [e for e in errors if not e.code.startswith("W")] == []


def test_registry_lists_every_node_id_with_expected_kind() -> None:
    found = {node.node_id: node.kind for node in _example_nodes()}
    assert found == _EXPECTED_KINDS


def test_each_link_target_is_an_allowed_kind_id() -> None:
    nodes = _example_nodes()
    kind_of = {node.node_id: node.kind for node in nodes} | {_SEED_ID: "seed"}
    checked = 0
    for node in nodes:
        for link in node.links:
            if link["kinds"] == "*":
                continue
            for target in node.item.get(link["field"], []):
                assert target in kind_of, f"{node.node_id}.{link['field']} -> unknown id {target}"
                assert kind_of[target] in link["kinds"], f"{node.node_id}.{link['field']} -> {target} is a {kind_of[target]}"
                checked += 1
    assert checked > 0


def test_every_required_link_is_present() -> None:
    for node in _example_nodes():
        for link in node.links:
            if link["required"]:
                assert node.item.get(link["field"]), f"{node.node_id} has no {link['field']}"


def test_tp_mailrelay_pin_api_v3_passes_schema() -> None:
    sketch = _load("02_system_sketch.json")
    mailrelay = next(tp for tp in sketch["third_parties"] if tp["third_party_id"] == "tp-mailrelay")
    assert mailrelay["pin"] == "api-v3"
    assert _validated(sketch) == []


def test_charter_with_one_in_one_out_scope_item_validates() -> None:
    charter = _load("00_charter.json")
    assert Counter(item["scope"] for item in charter["scope_items"]) == Counter({"in": 1, "out": 1})
    assert _validated(charter) == []


def test_third_party_without_pin_fails_schema() -> None:
    sketch = copy.deepcopy(_load("02_system_sketch.json"))
    del sketch["third_parties"][1]["pin"]
    errors = _validated(sketch)
    assert any("pin" in message for _path, message in errors)


def _is_about_00_05(rendered: str) -> bool:
    """True for a finding that names a 00-05 file or is the seed lint's."""
    return "STEP00_SEED_OUT_OF_SCOPE_THIN" in rendered or any(name in rendered for name in _FILES)


def test_spec_check_warning_set_is_pinned(stamped_example: Path) -> None:
    spec_dir = str(stamped_example / "spec")
    errors, context = run_spec_check_json(
        str(_ROOT), spec_dir, spec_root=spec_dir, project_canon_dir=str(stamped_example / "spec" / "canon")
    )
    other = [e.render() for e in errors if not e.code.startswith("W") and e.code not in GRAPH_CHECK_CODES | {"E566", "E567"}]
    assert other == []  # the graph checks' findings on the example are pinned in test_graph_roles_example.py
    # the milestone numbers (M6c): the example is a partial spec, one FR has no task criterion (ruling C15)
    assert [(e.code, e.node_id, e.owner) for e in errors if e.code in ("E566", "E567")] == [("E566", "fr-password-reset-request", "step:14")]
    about_00_05 = [e for e in errors if _is_about_00_05(e.render())]
    assert Counter(e.code for e in about_00_05) == _PINNED_WARNINGS
    subjects = Counter(
        (e.code, next((n for c, n in _PINNED_WARNING_SUBJECTS if c == e.code and n in e.render()), "?"))
        for e in about_00_05
    )
    assert subjects == _PINNED_WARNING_SUBJECTS, [e.render() for e in about_00_05]
    assert context["checks"]["seed-lint"]["status"] != "SKIP"


@pytest.mark.parametrize("bad_scope", [["in"], {"x": 1}])
def test_wrong_typed_scope_gives_schema_error_not_traceback(stamped_example: Path, tmp_path: Path, bad_scope: Any) -> None:
    work = tmp_path / "bad"
    shutil.copytree(stamped_example, work)
    path = work / "spec" / "04_fr_list.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["functional_requirements"][0]["scope"] = bad_scope
    path.write_text(json.dumps(doc), encoding="utf-8")
    spec = str(work / "spec")
    root = str(_ROOT)
    errors, _context = run_spec_check_json(root, spec, spec_root=spec, project_canon_dir=str(work / "spec" / "canon"))
    assert any(e.code == "E520" and "scope" in e.render() for e in errors)
    code, out = _run_cli("coverage", "--repo-root", root, "--spec-root", spec, "--git-root", str(work), "--json")
    assert "Traceback" not in out and "unhashable" not in out
    assert code == 0
    assert "counts" in json.loads(out)
    code, out = _run_cli("matrix", spec, "--out", str(work / "matrix.json"), "--repo-root", root)
    assert "Traceback" not in out and "unhashable" not in out
    assert code == 0
