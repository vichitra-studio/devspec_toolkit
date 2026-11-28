"""The prose that describes ``specdev milestone-state`` agrees with what the command prints and accepts.

``.claude/agents/specdev-scope.md`` (the scope agent's milestone_state mode) quotes the output contract; the reference
doc lists the flags.  Both are compared with the engine and the parser, not with a copy of them.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from specdev_tools.cli import build_parser
from specdev_tools.context.milestone_state import ItemView, SpecView, compute_milestone_state, derive_group_state

ROOT = Path(__file__).resolve().parents[3]
SCOPE_AGENT = ROOT / ".claude" / "agents" / "specdev-scope.md"
REFERENCE = ROOT / "docs" / "developers" / "reference.md"
_CONTRACT_BLOCK = re.compile(r"\*\*Output contract\*\*[^\n]*\n```json\n(.*?)\n```", re.DOTALL)
_STATE_ENUM = re.compile(r'"state": "([a-z_|]+)"')
_FLAG_ROW = re.compile(r"^\| `(--[a-z-]+)[^`]*` \| (Yes|No) \|", re.MULTILINE)


def _scope_contract_text() -> str:
    text = SCOPE_AGENT.read_text(encoding="utf-8")
    start = text.index("## Mode: milestone_state")
    match = _CONTRACT_BLOCK.search(text, start)
    assert match is not None, "the scope agent doc has no output contract block in its milestone_state section"
    return match.group(1)


def _emitted_states(tmp_path: Path) -> set[str]:
    """Every group state the engine emits: one group per state, each made by its own input."""
    findings = tmp_path / ".specdev" / "findings"
    findings.mkdir(parents=True)
    (findings / "findings_CONVERGED_1.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
    group = {"realises": ["tc-x"]}
    cases = {
        "pending": ({**group, "id": "PENDING"}, ItemView()),
        "code_converged": ({**group, "id": "CONVERGED"}, ItemView()),
        "blocked": ({**group, "id": "CONVERGED"}, ItemView(chain=frozenset({"node-a"}))),
        "deferred": ({**group, "id": "PENDING"}, ItemView(set_aside="deferred")),
        "wont_do": ({**group, "id": "PENDING"}, ItemView(set_aside="wont_do")),
    }
    ambiguities = [{"id": "amb-one", "about": ["node-a"]}]
    states = {derive_group_state(g, str(findings), ambiguities, view)["state"] for g, view in cases.values()}
    assert states == set(cases), "the engine emits a state the test has no case for"
    return states


def test_scope_agent_doc_lists_the_states_the_cli_emits(tmp_path: Path) -> None:
    contract = _scope_contract_text()
    documented = set(_STATE_ENUM.search(contract).group(1).split("|"))  # type: ignore[union-attr]
    assert documented == _emitted_states(tmp_path)

    plan = {"milestone": "ms-x", "plan": {"spec_alignment": {"checklist": [{"id": "G1", "realises": ["tc-x"]}]}}}
    emitted = compute_milestone_state(plan, str(tmp_path / ".specdev" / "findings"), "batch1", SpecView())
    assert list(re.findall(r'^  "([a-z_]+)":', contract, re.MULTILINE)) == list(emitted)
    assert list(re.findall(r'^      "([a-z_]+)":', contract, re.MULTILINE)) == list(emitted["groups"][0])


def test_scope_agent_doc_names_no_retired_input() -> None:
    text = SCOPE_AGENT.read_text(encoding="utf-8")
    section = text[text.index("## Mode: milestone_state"):]
    for retired in ("implementation.status", "checklist_status", "blocking_amb_health", "well_formed", "fixtures_exercised", "verified"):
        assert retired not in section, retired


def test_reference_doc_milestone_state_entry_matches_the_cli_flags() -> None:
    text = REFERENCE.read_text(encoding="utf-8")
    start = text.index("#### `milestone-state`")
    entry = text[start:start + re.search(r"\n#{2,4} ", text[start + 1:]).start()]  # type: ignore[union-attr]
    documented = {flag: required == "Yes" for flag, required in _FLAG_ROW.findall(entry)}
    subparsers = next(action for action in build_parser()._actions if isinstance(action, argparse._SubParsersAction))
    parser = subparsers.choices["milestone-state"]
    actual = {option: action.required for action in parser._actions for option in action.option_strings if option.startswith("--") and option != "--help"}
    assert documented == actual
