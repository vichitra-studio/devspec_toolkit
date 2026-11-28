"""The static reachability check of the recipe table (WI-M4-09): every kind of the registry is placed in some role's pack."""
from __future__ import annotations

import pytest

from specdev_tools.graph.kinds import SEED_KIND, load_kind_registry
from specdev_tools.graph.recipes import RecipeTable, load_recipes

from ._synth import ROOT

EXEMPT_AS_SETTLED = {SEED_KIND, "extension", "execution-record", "signoff-record", "at-deploy-record"}


@pytest.fixture(scope="module")
def table() -> RecipeTable:
    return load_recipes(str(ROOT))


@pytest.fixture(scope="module")
def registry_kinds() -> frozenset[str]:
    return frozenset(load_kind_registry(str(ROOT)).kind_names)


def _named_kinds(table: RecipeTable) -> set[str]:
    """Every kind the table names anywhere: start kinds, emitted kinds, hop kinds and exemptions."""
    kinds = set(table.start_kinds.values()) | set(table.suffix_fields) | {item.kind for item in table.exempt}
    hops = [hop for section in table.sections for hop in section.hops] + [hop for report in table.reports.values() for hop in report.hops]
    kinds.update(kind for hop in hops for kind in hop.kinds)
    kinds.update(kind for section in table.sections for kind in section.emitted_kinds)
    kinds.update(kind for report in table.reports.values() for kind in report.kinds)
    return kinds


def test_kind_reachability_every_registry_kind(table: RecipeTable, registry_kinds: frozenset[str]) -> None:
    assert SEED_KIND in registry_kinds
    assert registry_kinds - table.placed_kinds() == set()


def test_a_kind_added_to_the_registry_without_a_placement_fails(table: RecipeTable, registry_kinds: frozenset[str]) -> None:
    assert (registry_kinds | {"brand-new-kind"}) - table.placed_kinds() == {"brand-new-kind"}


def test_only_the_settled_kinds_are_exempt(table: RecipeTable) -> None:
    assert {item.kind for item in table.exempt} == EXEMPT_AS_SETTLED
    assert all(item.authority for item in table.exempt)


def test_every_kind_the_table_names_is_a_registry_kind(table: RecipeTable, registry_kinds: frozenset[str]) -> None:
    assert _named_kinds(table) - registry_kinds == set()


def test_exempt_kinds_are_not_also_placed_by_a_section(table: RecipeTable) -> None:
    emitted = {kind for section in table.sections for kind in section.emitted_kinds}
    assert emitted & EXEMPT_AS_SETTLED == set()
