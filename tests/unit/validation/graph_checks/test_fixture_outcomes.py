"""The fixture outcome rules (E754, E755, E756): a fixture that expects an error status names the error, agrees with its status and with the invariants it verifies.

Every test sets all the inputs it reads on a copy of the worked example, so it holds whatever the example says about errors.
A test marked ``*`` fails when ``check_verifier_rules`` no longer calls ``check_fixture_outcomes``.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from specdev_tools.core.errors import link_target, render_errors
from specdev_tools.validation.fixtures_lint import lint_fixtures
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
SECOND_ERROR = "err-password-reset-confirm-second"
OUTCOME_CODES = (FIXTURE_ERROR_NOT_NAMED, FIXTURE_STATUS_DIFFERS_FROM_ERROR, FIXTURE_ERROR_NOT_CONSTRAINED)

Fields = dict[str, Any]


def _spec(
    tmp_path: Path, *, one: Fields | None = None, two: Fields | None = None, error: Fields | None = None,
    constrains: list[str] | None = None, drop: tuple[str, ...] = (), extra_invariant: bool = False,
    second_error: Fields | None = None, protocol: str | None = None,
) -> Path:
    """The example with every input of the rules set: the two fixtures (*one* verifies the API, *two* the invariant), the error, what the invariant constrains.

    A field set to ``None`` in a dict is removed from the item; *drop* names fields removed from both fixtures.
    *second_error* adds a second error (``SECOND_ERROR``) to the API with those fields; *protocol* turns the API into one of that protocol.
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
        api = doc["apis"][0]
        apply(api["errors"][0], {"protocol_status": 410, **(error or {})})
        if second_error is not None:
            api["errors"].append({**api["errors"][0], "error_id": SECOND_ERROR, "code": "second-error", **second_error})
        if protocol is not None:
            apply(api, {"protocol": protocol, "method": None, "path": None})

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


def test_e754_reads_the_http_error_range_only(tmp_path: Path) -> None:
    """400 to 599 is an error outcome; a number of another protocol (a gRPC code, a WebSocket close code) is not recognised as one."""
    for status, found in ((399, False), (400, True), (599, True), (600, False), (5, False), (1000, False), (4001, False)):
        spec = _spec(tmp_path / str(status), one={"expected": {"status": status}, "expects": None})
        assert bool(_findings(spec, FIXTURE_ERROR_NOT_NAMED)) is found, status


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
    errors = [e for e in check_verifier_rules(context_of_spec(_spec(tmp_path, error={"protocol_status": None})), "merge") if e.code == FIXTURE_STATUS_DIFFERS_FROM_ERROR]
    assert [(e.node_id, e.target, e.owner) for e in errors] == [  # *
        (FIXTURE_ONE, link_target("expects", ERROR), "step:08"), (FIXTURE_TWO, link_target("expects", ERROR), "step:08"),
    ]
    assert "has no protocol_status" in errors[0].message


def test_e755_error_with_another_status(tmp_path: Path) -> None:
    spec = _spec(tmp_path, error={"protocol_status": 409})
    assert _findings(spec) == [  # *
        (FIXTURE_STATUS_DIFFERS_FROM_ERROR, FIXTURE_ONE, link_target("expects", ERROR)),
        (FIXTURE_STATUS_DIFFERS_FROM_ERROR, FIXTURE_TWO, link_target("expects", ERROR)),
    ]
    assert "has protocol_status 409" in [e for e in check_verifier_rules(context_of_spec(spec), "merge") if e.code == "E755"][0].message


def test_e755_same_status_is_clean(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path, one={"expected": {"status": 503}}, two={"expected": {"status": 503}}, error={"protocol_status": 503})) == []


def test_e755_expected_without_status_is_clean(tmp_path: Path) -> None:
    """No integer status in the fixture, nothing to compare: the error keeps its 410 and no finding names it."""
    assert _findings(_spec(tmp_path, one={"expected": {"body": {}}}, two={"expected": "text"})) == []


def test_e755_compares_the_status_number_of_any_protocol(tmp_path: Path) -> None:
    """A gRPC error carries its status code (5, NOT_FOUND) in ``protocol_status``; the fixture's number is compared with it like an HTTP status."""
    same = _spec(tmp_path / "same", protocol="grpc", error={"protocol_status": 5}, one={"expected": {"status": 5}}, two={"expected": {"status": 5}})
    assert _findings(same) == []
    assert _schema_errors(same) == []
    # both are contract fixtures: one verifies the gRPC API, the other verifies the invariant and names the API through the error it expects
    assert render_errors(lint_fixtures(str(same))) == []
    no_error = _spec(tmp_path / "bare", protocol="grpc", error={"protocol_status": 5}, one={"expected": {"status": 5}}, two={"expected": {"status": 5}, "expects": None})
    assert [FIXTURE_TWO in line and "names that API in verifies, or its error in expects" in line for line in render_errors(lint_fixtures(str(no_error)))] == [True]
    other = _spec(tmp_path / "other", protocol="grpc", error={"protocol_status": 5}, one={"expected": {"status": 13}}, two={"expected": {"status": 5}})
    assert _findings(other) == [(FIXTURE_STATUS_DIFFERS_FROM_ERROR, FIXTURE_ONE, link_target("expects", ERROR))]


def test_the_schema_bounds_the_status_of_an_http_api_only(tmp_path: Path) -> None:
    assert _schema_errors(_spec(tmp_path / "http-410")) == []
    for status, bound in ((5, "minimum of 100"), (99, "minimum of 100"), (600, "maximum of 599")):
        found = [m for m in _schema_errors(_spec(tmp_path / f"http-{status}", error={"protocol_status": status})) if "protocol_status" in m]
        assert len(found) == 1 and bound in found[0], (status, found)
    assert _schema_errors(_spec(tmp_path / "grpc-5", protocol="grpc", error={"protocol_status": 5})) == []
    assert _schema_errors(_spec(tmp_path / "ws-4001", protocol="ws", error={"protocol_status": 4001})) == []
    negative = [m for m in _schema_errors(_spec(tmp_path / "grpc-neg", protocol="grpc", error={"protocol_status": -1})) if "protocol_status" in m]
    assert len(negative) == 1 and "minimum of 0" in negative[0]


def test_e755_one_finding_for_each_named_error_that_differs(tmp_path: Path) -> None:
    """One 410 response that carries two errors: both are named; the one whose number differs is the finding."""
    both = {"expects": [ERROR, SECOND_ERROR]}
    assert _findings(_spec(tmp_path / "same", one=both, second_error={"protocol_status": 410})) == []
    assert _findings(_spec(tmp_path / "differs", one=both, second_error={"protocol_status": 409})) == [
        (FIXTURE_STATUS_DIFFERS_FROM_ERROR, FIXTURE_ONE, link_target("expects", SECOND_ERROR)),
    ]
    assert _findings(_spec(tmp_path / "none", one=both, second_error={"protocol_status": None}, error={"protocol_status": 400})) == [
        (FIXTURE_STATUS_DIFFERS_FROM_ERROR, FIXTURE_ONE, link_target("expects", ERROR)),
        (FIXTURE_STATUS_DIFFERS_FROM_ERROR, FIXTURE_ONE, link_target("expects", SECOND_ERROR)),
        (FIXTURE_STATUS_DIFFERS_FROM_ERROR, FIXTURE_TWO, link_target("expects", ERROR)),
    ]


def test_expects_takes_more_than_one_error(tmp_path: Path) -> None:
    spec = _spec(tmp_path, one={"expects": [ERROR, SECOND_ERROR]}, second_error={"protocol_status": 410})
    assert _schema_errors(spec) == []


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


def test_e756_is_silent_when_the_invariant_constrains_one_of_the_expected_errors(tmp_path: Path) -> None:
    both = {"expects": [ERROR, SECOND_ERROR]}
    second = {"protocol_status": 410}
    assert _findings(_spec(tmp_path / "first", two=both, second_error=second, constrains=[ERROR])) == []
    assert _findings(_spec(tmp_path / "second", two=both, second_error=second, constrains=[SECOND_ERROR])) == []
    spec = _spec(tmp_path / "neither", two=both, second_error=second, constrains=[])
    errors = [e for e in check_verifier_rules(context_of_spec(spec), "merge") if e.code == FIXTURE_ERROR_NOT_CONSTRAINED]
    assert [(e.node_id, e.target) for e in errors] == [(FIXTURE_TWO, link_target("verifies", INVARIANT))]
    assert f"expects the API errors {ERROR}, {SECOND_ERROR}, none of which {INVARIANT} constrains: add one of {ERROR}, {SECOND_ERROR} to constrains of {INVARIANT}" in errors[0].message


def test_an_error_named_twice_is_one_error_and_a_brace_in_an_id_breaks_nothing(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "twice", two={"expects": [ERROR, ERROR]}, constrains=[])
    errors = [e for e in check_verifier_rules(context_of_spec(spec), "merge") if e.code == FIXTURE_ERROR_NOT_CONSTRAINED]
    assert len(errors) == 1 and f"expects the API error {ERROR}, which" in errors[0].message
    braces = _spec(tmp_path / "braces", error={"error_id": "err-{x}"}, one={"expects": ["err-{x}"]}, two={"expects": ["err-{x}"]}, constrains=[])
    assert [e[0] for e in _findings(braces, FIXTURE_ERROR_NOT_CONSTRAINED)] == [FIXTURE_ERROR_NOT_CONSTRAINED]


def test_e756_message_of_one_error(tmp_path: Path) -> None:
    errors = [e for e in check_verifier_rules(context_of_spec(_spec(tmp_path, constrains=[])), "merge") if e.code == FIXTURE_ERROR_NOT_CONSTRAINED]
    assert errors[0].message.startswith(
        f"fixture {FIXTURE_TWO} verifies invariant {INVARIANT} but expects the API error {ERROR}, which {INVARIANT} does not constrain: "
        f"add {ERROR} to constrains of {INVARIANT} (then run specdev attest {INVARIANT} --yes), or expect an error it constrains"
    )


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


def _schema_errors(spec: Path) -> list[str]:
    """The schema findings (E520) of steps 05 and 08 of *spec*, as text."""
    from specdev_tools.validation.validate import validate_file
    from unit.graph._synth import ROOT
    found: list[str] = []
    for name in ("05_interface_contracts.json", "08_fixtures.json"):
        found.extend(f"{error.code} {error.message}" for error in validate_file(str(ROOT), str(spec / name)) if error.code == "E520")
    return found


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


def test_e740_of_an_api_error_keeps_its_scope_advice(tmp_path: Path) -> None:
    """The schema restates ``errors`` under a condition; the reader must still see that an API error has a ``scope``."""
    errors = [e for e in check_no_dangling(context_of_spec(_spec(tmp_path, constrains=[])), "merge") if e.node_id == ERROR]
    assert len(errors) == 1 and errors[0].message.endswith("or set scope later or out with a scope_reason")


def test_use_pairs_of_an_api_error(tmp_path: Path) -> None:
    pairs = use_pairs("api-error", context_of_spec(_spec(tmp_path)).graph.decls)
    assert Use("invariant", "constrains") in pairs and Use("fixture", "expects") not in pairs


def test_new_codes_are_graph_check_codes_and_not_coverage_gaps() -> None:
    assert set(OUTCOME_CODES) <= GRAPH_CHECK_CODES
    assert not set(OUTCOME_CODES) & ROLE_GAP_CODES
