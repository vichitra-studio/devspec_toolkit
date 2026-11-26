"""The fixture outcome rules (E754, E755, E756): a fixture that expects an error status names the error, agrees with its status and with the invariants it verifies.

Every test sets all the inputs it reads on a copy of the worked example, so it holds whatever the example says about errors.
A test marked ``*`` fails when ``check_verifier_rules`` no longer calls ``check_fixture_outcomes``.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from specdev_tools.core.errors import link_target
from specdev_tools.validation.graph_checks.codes import GRAPH_CHECK_CODES, ROLE_GAP_CODES
from specdev_tools.validation.graph_checks.codes import (
    FIXTURE_ERROR_NOT_CONSTRAINED, FIXTURE_ERROR_NOT_NAMED, FIXTURE_STATUS_DIFFERS_FROM_ERROR,
)
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.no_dangling import check_no_dangling
from specdev_tools.validation.graph_checks.use_table import Use, use_pairs
from specdev_tools.validation.graph_checks.verifiers import check_verifier_rules

from ._example_support import context_of_spec, edited_example

ERROR = "err-password-reset-confirm-token-expired"
API = "api-password-reset-confirm"
FIXTURE_ONE = "fix-password-reset-expired-token"
FIXTURE_TWO = "fix-password-reset-reused-token"
INVARIANT = "inv-reset-token-single-use"
OUTCOME_CODES = (FIXTURE_ERROR_NOT_NAMED, FIXTURE_STATUS_DIFFERS_FROM_ERROR, FIXTURE_ERROR_NOT_CONSTRAINED)

Fields = dict[str, Any]


def _spec(
    tmp_path: Path, *, one: Fields | None = None, two: Fields | None = None, error: Fields | None = None,
    constrains: list[str] | None = None, drop: tuple[str, ...] = (), extra_invariant: bool = False,
) -> Path:
    """The example with every input of the rules set: the two fixtures (*one* verifies the API, *two* the invariant), the error, what the invariant constrains.

    A field set to ``None`` in a dict is removed from the item; *drop* names fields removed from both fixtures.
    """
    base_one: Fields = {"expected": {"status": 410}, "expects": [ERROR]}
    base_two: Fields = {"expected": {"status": 410}, "expects": [ERROR]}

    def apply(item: dict[str, Any], changes: Fields) -> None:
        for name, value in changes.items():
            if value is None:
                item.pop(name, None)
            else:
                item[name] = value

    def fixtures(doc: dict[str, Any]) -> None:
        apply(doc["fixtures"][0], {**base_one, **(one or {})})
        apply(doc["fixtures"][1], {**base_two, **(two or {})})
        for name in drop:
            doc["fixtures"][0].pop(name, None)
            doc["fixtures"][1].pop(name, None)

    def errors(doc: dict[str, Any]) -> None:
        apply(doc["apis"][0]["errors"][0], {"http_status": 410, **(error or {})})

    def invariants(doc: dict[str, Any]) -> None:
        rule = doc["rules"][0]
        rule["constrains"] = [*(c for c in rule["constrains"] if c != ERROR), *([ERROR] if constrains is None else constrains)]
        if extra_invariant:
            second = {**rule, "inv_id": "inv-reset-extra", "constrains": [API]}
            doc["rules"].append(second)

    edits: dict[str, Callable[[dict[str, Any]], None]] = {
        "08_fixtures.json": fixtures, "05_interface_contracts.json": errors, "06_invariants.json": invariants,
    }
    return edited_example(tmp_path / "spec", **edits)


def _findings(spec: Path, *codes: str) -> list[tuple[str, str | None, str | None]]:
    """(code, node id, target) of the findings of ``check_verifier_rules`` with one of *codes* (the outcome codes by default), in order."""
    wanted = codes or OUTCOME_CODES
    return [(error.code, error.node_id, error.target) for error in check_verifier_rules(context_of_spec(spec), "merge") if error.code in wanted]


def test_a_consistent_example_gives_no_outcome_finding(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path)) == []


def test_e754_names_a_fixture_with_an_error_status_and_no_expects(tmp_path: Path) -> None:
    spec = _spec(tmp_path, one={"expected": {"status": 404}, "expects": None})
    errors = [e for e in check_verifier_rules(context_of_spec(spec), "merge") if e.code == FIXTURE_ERROR_NOT_NAMED]
    assert [(e.node_id, e.target, e.owner) for e in errors] == [(FIXTURE_ONE, None, "step:08")]  # *
    assert "status 404" in errors[0].message and f"specdev attest {FIXTURE_ONE} --yes" in errors[0].message


def test_e754_is_silent_for_status_below_400_non_object_expected_bool_and_string_status(tmp_path: Path) -> None:
    for expected in ({"status": 200}, {"status": 399}, {"status": "404"}, {"status": True}, {"status": 404.0}, "not an object", None):
        spec = _spec(tmp_path / str(abs(hash(str(expected)))), one={"expected": expected, "expects": None})
        assert _findings(spec) == [], expected


def test_e754_is_silent_when_expects_is_present(tmp_path: Path) -> None:
    spec = _spec(tmp_path, one={"expected": {"status": 500}})
    assert _findings(spec, FIXTURE_ERROR_NOT_NAMED) == []
    assert _findings(spec) == [(FIXTURE_STATUS_DIFFERS_FROM_ERROR, FIXTURE_ONE, link_target("expects", ERROR))]


def test_e754_skips_a_removal_fixture(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path, one={"expected": {"status": 404}, "expects": None, "removes": ["api-old-endpoint"]})) == []


def test_e754_skips_a_fixture_out_of_play(tmp_path: Path) -> None:
    spec = _spec(tmp_path, one={"expected": {"status": 404}, "expects": None, "scope": "out", "scope_reason": "not delivered"})
    assert _findings(spec) == []


def test_e755_error_without_status(tmp_path: Path) -> None:
    errors = [e for e in check_verifier_rules(context_of_spec(_spec(tmp_path, error={"http_status": None})), "merge") if e.code == FIXTURE_STATUS_DIFFERS_FROM_ERROR]
    assert [(e.node_id, e.target, e.owner) for e in errors] == [  # *
        (FIXTURE_ONE, link_target("expects", ERROR), "step:08"), (FIXTURE_TWO, link_target("expects", ERROR), "step:08"),
    ]
    assert "has no http_status" in errors[0].message


def test_e755_error_with_another_status(tmp_path: Path) -> None:
    spec = _spec(tmp_path, error={"http_status": 409})
    assert _findings(spec) == [  # *
        (FIXTURE_STATUS_DIFFERS_FROM_ERROR, FIXTURE_ONE, link_target("expects", ERROR)),
        (FIXTURE_STATUS_DIFFERS_FROM_ERROR, FIXTURE_TWO, link_target("expects", ERROR)),
    ]
    assert "has http_status 409" in [e for e in check_verifier_rules(context_of_spec(spec), "merge") if e.code == "E755"][0].message


def test_e755_same_status_is_clean(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path, one={"expected": {"status": 503}}, two={"expected": {"status": 503}}, error={"http_status": 503})) == []


def test_e755_expected_without_status_is_clean(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path, one={"expected": {"body": {}}}, two={"expected": "text"}, error={"http_status": None})) == []


def test_e755_ignores_an_unresolved_or_wrong_kind_target(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path, one={"expects": ["err-nobody-has-this"]}, two={"expects": [API]})) == []


def test_e756_invariant_does_not_constrain_the_expected_error(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path, constrains=[])) == [(FIXTURE_ERROR_NOT_CONSTRAINED, FIXTURE_TWO, link_target("verifies", INVARIANT))]  # *


def test_e756_constrains_it_is_clean(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path, constrains=[ERROR])) == []


def test_e756_one_finding_per_invariant(tmp_path: Path) -> None:
    spec = _spec(tmp_path, constrains=[], extra_invariant=True, two={"verifies": [INVARIANT, "inv-reset-extra"]})
    assert _findings(spec) == [  # *
        (FIXTURE_ERROR_NOT_CONSTRAINED, FIXTURE_TWO, link_target("verifies", INVARIANT)),
        (FIXTURE_ERROR_NOT_CONSTRAINED, FIXTURE_TWO, link_target("verifies", "inv-reset-extra")),
    ]
    both = _spec(tmp_path / "ok", constrains=[ERROR], extra_invariant=True, two={"verifies": [INVARIANT, "inv-reset-extra"]})
    assert _findings(both) == [(FIXTURE_ERROR_NOT_CONSTRAINED, FIXTURE_TWO, link_target("verifies", "inv-reset-extra"))]


def test_e756_skips_an_invariant_out_of_play(tmp_path: Path) -> None:
    spec = _spec(tmp_path, constrains=[])
    path = spec / "06_invariants.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["rules"][0]["lifecycle"] = "not_applicable"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert _findings(spec, FIXTURE_ERROR_NOT_CONSTRAINED) == []  # with the invariant in play this is one E756 (the test above)


def test_e756_needs_both_verifies_invariant_and_expects(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path, constrains=[], two={"expects": None, "expected": {"status": 200}})) == []
    assert _findings(_spec(tmp_path / "b", constrains=[], two={"verifies": ["ac-password-reset-3"]})) == []


def _verdicts(context: GraphCheckContext) -> dict[str, list[str | None]]:
    return {
        "E740": [e.node_id for e in check_no_dangling(context, "merge")],
        "rest": [f"{e.code} {e.node_id} {e.target}" for e in check_verifier_rules(context, "merge") if e.code not in OUTCOME_CODES],
    }


def test_expects_changes_no_existing_verdict(tmp_path: Path) -> None:
    """Naming an error in ``expects`` is not a use of it and not a proof: E740, E742 and E743 stay as they are."""
    without = _verdicts(context_of_spec(_spec(tmp_path / "a", one={"expects": None}, two={"expects": None}, constrains=[])))
    with_expects = _verdicts(context_of_spec(_spec(tmp_path / "b", constrains=[])))
    assert with_expects == without
    assert ERROR in with_expects["E740"] and not any(ERROR in line for line in with_expects["rest"])


def test_constrains_an_error_is_a_use(tmp_path: Path) -> None:
    """An invariant that constrains an error uses it (E740 goes); E743 never names an API error."""
    unused = _verdicts(context_of_spec(_spec(tmp_path / "a", constrains=[])))
    used = _verdicts(context_of_spec(_spec(tmp_path / "b", constrains=[ERROR])))
    assert ERROR in unused["E740"] and ERROR not in used["E740"]
    assert not any(ERROR in line for line in used["rest"])


def test_use_pairs_of_an_api_error(tmp_path: Path) -> None:
    pairs = use_pairs("api-error", context_of_spec(_spec(tmp_path)).graph.decls)
    assert Use("invariant", "constrains") in pairs and Use("fixture", "expects") not in pairs


def test_new_codes_are_graph_check_codes_and_not_coverage_gaps() -> None:
    assert set(OUTCOME_CODES) <= GRAPH_CHECK_CODES
    assert not set(OUTCOME_CODES) & ROLE_GAP_CODES
