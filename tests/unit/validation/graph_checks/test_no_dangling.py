"""The no-dangling check (E740): the use table of WI-M6b-01 here, the check itself from WI-M6b-02."""
from __future__ import annotations

from specdev_tools.graph.build import build_graph
from specdev_tools.validation.graph_checks.use_table import EXCLUDED_VERBS, USE_TABLE, Use, use_pairs
from unit.graph._synth import EXAMPLE_SPEC, ROOT

# The rows of the design's "Who uses what" table that name holders (DOC L610-L634); segment and metric ("a later
# node's link") and "every other kind" have no row and take any link that is not excluded.
_ASSUMING = {
    "api", "api-error", "capability", "component", "connection", "constraint", "criterion", "edge-case", "environment",
    "fr", "gate", "invariant", "metric", "need", "nfr", "risk", "rule", "scope-item", "secret", "segment", "stakeholder",
    "third-party", "threat",
}
_DOC_ROWS: dict[str, set[Use]] = {
    "assumption": {*(Use(kind, "assumes") for kind in _ASSUMING), Use("risk", "derives_from")},
    "need": {Use("metric", "derives_from"), Use("scope-item", "derives_from"), Use("constraint", "derives_from")},
    "stakeholder": {Use("rule", "derives_from")},
    "component": {
        Use("api", "provided_by"), Use("invariant", "constrains"), Use("nfr", "constrains"), Use("threat", "threatens"),
        Use("connection", "connects_to"), Use("gate", "derives_from"), Use("secret", "derives_from"),
    },
    "connection": {
        Use("invariant", "constrains"), Use("nfr", "constrains"), Use("threat", "threatens"), Use("secret", "derives_from"),
    },
    "third-party": {Use("api", "relies_on"), Use("nfr", "relies_on"), Use("third-party", "part_of"), Use("connection", "connects_to")},
    "environment": {Use("job", "realises")},
    "gate": {Use("job", "realises")},
    "secret": {Use("job", "realises")},
    "term": set(),
    "threat": {Use("task-criterion", "refines")},
    "edge-case": {Use("task-criterion", "refines")},
    "risk": {Use("threat", "derives_from"), Use("rule", "derives_from"), Use("design-milestone", "schedules")},
    "constraint": {
        Use(kind, "derives_from") for kind in ("third-party", "component", "environment", "gate", "secret", "rule")
    },
}


def test_use_matches_doc_rows() -> None:
    """The table is the design's rows, and every (holder kind, verb) pair of it is a link the registry declares for that target kind."""
    assert {kind: set(row) for kind, row in USE_TABLE.items()} == _DOC_ROWS
    decls = build_graph(str(EXAMPLE_SPEC), str(ROOT)).decls
    undeclared = [
        (target, use) for target, row in USE_TABLE.items() for use in row
        if not any(link.field == use.verb and link.accepts(target) for link in decls[use.holder_kind].links)
    ]
    assert undeclared == []


def test_a_kind_without_a_row_is_used_by_any_link_that_is_not_excluded() -> None:
    decls = build_graph(str(EXAMPLE_SPEC), str(ROOT)).decls
    pairs = use_pairs("capability", decls)
    assert Use("fr", "derives_from") in pairs and Use("task-criterion", "refines") in pairs
    assert {use.verb for use in pairs}.isdisjoint(EXCLUDED_VERBS)
    assert {use.holder_kind for use in pairs}.isdisjoint({"fixture", "job", "ambiguity-item", "evidence-record", "verification-record"})
