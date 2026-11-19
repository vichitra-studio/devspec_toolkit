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
