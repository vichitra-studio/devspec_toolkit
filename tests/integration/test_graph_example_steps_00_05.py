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
from typing import Any, Iterator, NamedTuple

import pytest

from specdev_tools.core.changelog_parser import get_toolkit_version
from specdev_tools.core.entry_key_registry import iter_nodes, join_nested_path
from specdev_tools.core.schema_validate import validate_data_against_schema
from specdev_tools.validation.spec_check import run_spec_check_json
from specdev_tools.validation.validate import DEEP_VALIDATORS

_ROOT = Path(__file__).parents[2]
_EXAMPLE = _ROOT / "tests" / "fixtures" / "graph_example"
_SPEC = _EXAMPLE / "spec"
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
_SEED_ID = "seed-accounts"

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

# Warnings the example produces by construction: no other code may appear.
_PINNED_WARNINGS = Counter(
    {
        "W555": 1,  # the seed excerpt names one out-of-scope item; the lint expects three
        "W570": 3,  # steps 07, 14 and 16 are absent: the example stops at step 05 until M3
        "W594": 2,  # 01 and 03 restate the design's wording with little token overlap upstream
    }
)


class _Node(NamedTuple):
    node_id: str
    kind: str
    item: dict[str, Any]
    links: list[dict[str, Any]]


def _load(name: str) -> dict[str, Any]:
    return json.loads((_SPEC / name).read_text(encoding="utf-8"))


def _entries(entries: list[dict[str, Any]], parent_path: str | None = None) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield ``(full_array_path, registry_entry)`` for every entry, nested ones included."""
    for entry in entries:
        full = entry["array_path"] if parent_path is None else join_nested_path(parent_path, entry["array_path"])
        yield full, entry
        yield from _entries(entry.get("nested", []), full)


def _example_nodes() -> list[_Node]:
    registry = json.loads((_ROOT / "tools" / "entry_key_registry.json").read_text(encoding="utf-8"))["registry"]
    nodes: list[_Node] = []
    for name in _FILES:
        doc = _load(name)
        for full, entry in _entries(registry[name]["arrays"]):
            for item, _path, key in iter_nodes(doc, full):
                node_id = key if key is not None else item[entry["id_field"]]
                nodes.append(_Node(node_id, entry["kind"], item, entry.get("links", [])))
    return nodes


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


def test_spec_check_warning_set_is_pinned(stamped_example: Path) -> None:
    spec_dir = str(stamped_example / "spec")
    errors, context = run_spec_check_json(
        str(_ROOT), spec_dir, spec_root=spec_dir, project_canon_dir=str(stamped_example / "spec" / "canon")
    )
    assert [e.render() for e in errors if not e.code.startswith("W")] == []
    assert Counter(e.code for e in errors) == _PINNED_WARNINGS
    assert context["checks"]["seed-lint"]["status"] != "SKIP"
