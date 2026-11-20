"""The shipped ``tools/error_ownership.json``: every owner rule it uses is one the gate knows (a typo would never block)."""
from __future__ import annotations

from specdev_tools.core.step_order import load_step_order
from specdev_tools.graph.ownership import FIXED_STEP_PREFIX, GATE_OWNERS, load_ownership_table
from unit.graph._synth import ROOT

NODE_RULES = {"holder_step", "node_step", "consumer_step", "binding_step", "furthest_usable_step"}


def test_every_fixed_step_of_the_table_is_a_step_of_the_step_order() -> None:
    steps = set(load_step_order(str(ROOT))["steps"])
    fixed = {row.owner_rule.removeprefix(FIXED_STEP_PREFIX) for row in load_ownership_table(str(ROOT)) if row.owner_rule.startswith(FIXED_STEP_PREFIX)}
    assert fixed and fixed <= steps, sorted(fixed - steps)


def test_every_other_rule_of_the_table_is_a_known_rule() -> None:
    rules = {row.owner_rule for row in load_ownership_table(str(ROOT)) if not row.owner_rule.startswith(FIXED_STEP_PREFIX)}
    assert rules <= NODE_RULES | GATE_OWNERS, sorted(rules - NODE_RULES - GATE_OWNERS)


M6B_OWNERS = {
    "E740": "furthest_usable_step",
    "E741": "fixed_step:14",
    "E742": "fixed_step:14",
    "E743": "fixed_step:08",
    "E744": "fixed_step:14",
    "E745": "fixed_step:14",
    "E746": "fixed_step:15",
    "E747": "fixed_step:00",
    "E748": "node_step",
    "E749": "node_step",
    "E752": "node_step",
}


def test_every_m6b_code_has_a_class_row() -> None:
    """Each code of the graph role checks is listed by exactly one class row, with the owner rule the design gives it."""
    rows = load_ownership_table(str(ROOT))
    found = {code: [row.owner_rule for row in rows if code in row.codes] for code in M6B_OWNERS}
    assert found == {code: [rule] for code, rule in M6B_OWNERS.items()}


def test_no_class_row_uses_the_binding_step_rule() -> None:
    """E743 is owned by step 08 (the fixture is the binding): the rule stays known to the gate but no row uses it."""
    assert "binding_step" not in {row.owner_rule for row in load_ownership_table(str(ROOT))}
