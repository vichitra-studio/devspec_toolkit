"""The id-in-prose check (E752, WI-M6b-11): what is scanned, what is a mention, who owns the finding, lifecycle and order."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.validation.graph_checks.prose_ids import _all_fixed, _is_fixed, check_prose_ids
from specdev_tools.validation.graph_checks.schema_slots import alternatives_of
from unit.graph._synth import HASH_SEEDS, load_doc

from ._example_support import Edit, context_of_spec, edited_example
from ._order_support import jsonable, seeded

FR_FILE, NFR_FILE = "04_fr_list.json", "07_nfrs.json"
FR_PATH = ".functional_requirements[0]"


def _fr(doc: dict[str, Any]) -> dict[str, Any]:
    return doc["functional_requirements"][0]


def _criteria(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return _fr(doc)["acceptance_criteria"]


def _findings(spec: Path) -> list[SpecError]:
    return check_prose_ids(context_of_spec(spec), "merge")


def _statement(text: str) -> Edit:
    return lambda doc: _fr(doc).__setitem__("statement", text)


def _found(spec: Path) -> list[tuple[str | None, str | None]]:
    return [(error.node_id, error.target) for error in _findings(spec)]


def test_worked_example_has_no_e752(tmp_path: Path) -> None:
    assert _findings(edited_example(tmp_path / "spec")) == []


def test_id_in_a_description_gives_e752(tmp_path: Path) -> None:
    spec = edited_example(tmp_path / "spec", **{FR_FILE: _statement("The system shall serve cap-account-recovery, as agreed.")})
    (error,) = _findings(spec)
    assert (error.code, error.node_id, error.file, error.jq_path) == ("E752", "fr-password-reset", FR_FILE, f"{FR_PATH}.statement")
    assert error.target == link_target("statement", "cap-account-recovery")
    assert "cap-account-recovery" in error.message and "reword" in error.message


PLAN_FILE, ANCHOR_FILE = "impl_context/ms_account_recovery_plan.json", "16_impl_context.json"


def _plan_item_mentions(doc: dict[str, Any]) -> None:
    doc["plan"]["spec_alignment"]["checklist"][0]["description"] += " It serves cap-account-recovery."


def test_a_plan_item_of_an_open_plan_is_read_and_one_of_a_frozen_plan_is_not(tmp_path: Path) -> None:
    open_plan = edited_example(tmp_path / "open", **{PLAN_FILE: _plan_item_mentions})
    assert [error.target for error in _findings(open_plan)] == [link_target("description", "cap-account-recovery")]
    frozen = edited_example(
        tmp_path / "frozen",
        **{PLAN_FILE: _plan_item_mentions, ANCHOR_FILE: lambda doc: doc["plan"]["milestone_index"][0].__setitem__("status", "done")},
    )
    assert _findings(frozen) == [], "a frozen plan is history: nobody may reword it"


def test_unresolved_id_shaped_token_is_not_flagged(tmp_path: Path) -> None:
    assert _findings(edited_example(tmp_path / "spec", **{FR_FILE: _statement("It replaces fr-old-export and fr-password-reset-requests.")})) == []


def test_contract_value_not_equal_to_a_live_id_is_not_flagged(tmp_path: Path) -> None:
    assert _findings(edited_example(tmp_path / "spec", **{FR_FILE: _statement("POST /v1/password-resets/{token} returns err-token-expired.")})) == []


def test_id_in_a_link_field_is_not_flagged(tmp_path: Path) -> None:
    spec = edited_example(tmp_path / "spec")
    assert load_doc(spec, FR_FILE)["functional_requirements"][0]["derives_from"] == ["cap-account-recovery"]
    assert _findings(spec) == []


def test_enum_field_is_not_flagged(tmp_path: Path) -> None:
    spec = edited_example(tmp_path / "spec", **{FR_FILE: lambda doc: _fr(doc).__setitem__("priority", "cap-account-recovery")})
    assert _findings(spec) == []
    prose = edited_example(tmp_path / "prose" / "spec", **{FR_FILE: lambda doc: _fr(doc).__setitem__("rationale", "cap-account-recovery")})
    assert _found(prose) == [("fr-password-reset", link_target("rationale", "cap-account-recovery"))]


def test_alias_of_a_renamed_node_is_flagged(tmp_path: Path) -> None:
    def rename(doc: dict[str, Any]) -> None:
        _fr(doc)["aliases"] = ["fr-reset-old"]
        _criteria(doc)[0]["text"] = "As fr-reset-old says, a link is emailed."

    (error,) = _findings(edited_example(tmp_path / "spec", **{FR_FILE: rename}))
    assert (error.node_id, error.target) == ("ac-password-reset-1", link_target("text", "fr-password-reset"))
    assert "fr-reset-old" in error.message and "fr-password-reset" in error.message


def test_a_node_naming_its_own_retired_name_is_not_flagged(tmp_path: Path) -> None:
    """A link to itself cannot be written: the retired name of the node itself in its text is no finding, a retired name of another node is."""
    def rename(doc: dict[str, Any]) -> None:
        _fr(doc)["aliases"] = ["fr-reset-old"]
        _fr(doc)["statement"] = "This is what fr-reset-old used to say."

    assert _findings(edited_example(tmp_path / "own" / "spec", **{FR_FILE: rename})) == []

    def other(doc: dict[str, Any]) -> None:
        _fr(doc)["aliases"] = ["fr-reset-old"]
        _criteria(doc)[0]["text"] = "This is what fr-reset-old used to say."

    assert _found(edited_example(tmp_path / "other" / "spec", **{FR_FILE: other})) == [("ac-password-reset-1", link_target("text", "fr-password-reset"))]


def test_a_leaf_with_no_schema_slot_is_read_as_prose_and_gives_e752(tmp_path: Path) -> None:
    """The free-form ``input`` of a fixture has no slot in the schema: an id written in it is a mention."""
    spec = edited_example(tmp_path / "spec", **{"08_fixtures.json": lambda doc: doc["fixtures"][0]["input"].__setitem__("method", "POST cap-account-recovery")})
    assert _found(spec) == [("fix-password-reset-expired-token", link_target("input.method", "cap-account-recovery"))]


def test_seed_id_in_prose_is_flagged(tmp_path: Path) -> None:
    assert _found(edited_example(tmp_path / "spec", **{FR_FILE: _statement("As in seed-accounts, a member recovers access.")})) == [
        ("fr-password-reset", link_target("statement", "seed-accounts"))
    ]


def test_name_like_environment_id_in_prose_is_not_flagged(tmp_path: Path) -> None:
    assert _findings(edited_example(tmp_path / "spec", **{FR_FILE: _statement("Runs in dev, ci and staging before prod.")})) == []


def test_e752_owner_is_the_nodes_own_step(tmp_path: Path) -> None:
    spec = edited_example(tmp_path / "spec", **{NFR_FILE: lambda doc: doc["nfrs"][0].__setitem__("measurement_method", "Measured as fr-password-reset behaves.")})
    (error,) = _findings(spec)
    assert (error.node_id, error.owner) == ("nfr-latency-reset-email", "step:07")


def test_leaf_of_a_nested_criterion_is_owned_by_the_criterion(tmp_path: Path) -> None:
    spec = edited_example(tmp_path / "spec", **{FR_FILE: lambda doc: _criteria(doc)[0].__setitem__("text", "Covered by api-password-reset-confirm.")})
    (error,) = _findings(spec)
    assert (error.node_id, error.owner, error.jq_path) == ("ac-password-reset-1", "step:04", f"{FR_PATH}.acceptance_criteria[0].text")


def test_two_ids_in_one_leaf_are_two_findings_with_distinct_identity(tmp_path: Path) -> None:
    spec = edited_example(tmp_path / "spec", **{FR_FILE: _statement("See cap-account-recovery and seed-accounts; again cap-account-recovery.")})
    errors = _findings(spec)
    assert [error.target for error in errors] == [link_target("statement", "cap-account-recovery"), link_target("statement", "seed-accounts")]
    assert len({(error.node_id, error.file, error.jq_path, error.target) for error in errors}) == 2


def test_prose_ids_do_not_read_a_not_applicable_node(tmp_path: Path) -> None:
    def mention(lifecycle: str) -> Edit:
        def edit(doc: dict[str, Any]) -> None:
            _statement("Mentions cap-account-recovery.")(doc)
            _fr(doc)["lifecycle"] = lifecycle

        return edit

    assert _findings(edited_example(tmp_path / "gone" / "spec", **{FR_FILE: mention("not_applicable")})) == []
    assert _found(edited_example(tmp_path / "old" / "spec", **{FR_FILE: mention("deprecated")})) == [("fr-password-reset", link_target("statement", "cap-account-recovery"))]


ROADMAP_FILE, PLAN_FILE = "14_roadmap.json", "impl_context/ms_account_recovery_plan.json"
MENTION = "Mentions cap-account-recovery in its text."


def test_an_id_in_a_task_description_gives_e752(tmp_path: Path) -> None:
    """The slot's pattern (``^\\S+\\s+\\S+.*$``) only asks for two words: the leaf is prose."""
    spec = edited_example(tmp_path / "spec", **{ROADMAP_FILE: lambda doc: doc["milestones"][0]["tasks"][0].__setitem__("description", MENTION)})
    (error,) = _findings(spec)
    assert (error.node_id, error.owner, error.jq_path) == ("task-implement-password-reset-confirm", "step:14", ".milestones[0].tasks[0].description")


def test_an_id_in_a_step_16_evidence_content_gives_e752(tmp_path: Path) -> None:
    """``content`` of an evidence object has the pattern ``\\S`` (not empty): the leaf is prose."""

    def edit(doc: dict[str, Any]) -> None:
        action = doc["plan"]["spec_alignment"]["checklist"][0]["implementation"]["actions"][0]
        action["evidence"] = {"type": "log", "content": "Ran the suite for cap-account-recovery: all green."}

    (error,) = _findings(edited_example(tmp_path / "spec", **{PLAN_FILE: edit}))
    assert (error.node_id, error.owner, error.jq_path) == ("PWRESET_CONFIRM_EXPIRED_01", "step:16a", ".plan.spec_alignment.checklist[0].implementation.actions[0].evidence.content")


def test_a_format_slot_is_a_fixed_value(tmp_path: Path) -> None:
    """A milestone's ``target_date`` is ``format: date``: an id written there is a contract value, not prose."""
    spec = edited_example(tmp_path / "spec", **{ROADMAP_FILE: lambda doc: doc["milestones"][0].__setitem__("target_date", "cap-account-recovery")})
    assert _findings(spec) == []


@pytest.mark.parametrize(
    ("slot", "fixed"),
    [
        ({"type": "string", "enum": ["a"]}, True),
        ({"type": "string", "const": "a"}, True),
        ({"type": "string", "format": "uri"}, True),
        ({"type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"}, True),
        ({"type": "string", "pattern": "^(?P<broken"}, True),
        ({"type": "string", "pattern": "\\S"}, False),
        ({"type": "string", "pattern": "^[a-z ]+$"}, False),
        ({"type": "string", "pattern": "^[A-Z]"}, False),
        ({"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*( [a-z0-9][a-z0-9-]*)*$"}, False),
        ({"type": "string", "pattern": "\\S\\s+\\S"}, False),
        ({"type": "string", "pattern": "^\\S+\\s+\\S+.*$"}, False),
        ({"type": "string"}, False),
    ],
)
def test_a_slot_is_fixed_by_enum_const_format_or_a_pattern_no_sentence_satisfies(slot: dict[str, Any], fixed: bool) -> None:
    assert _is_fixed(slot) is fixed


@pytest.mark.parametrize("scope", ["later", "out"])
def test_prose_ids_read_a_node_parked_with_scope_later_or_out(tmp_path: Path, scope: str) -> None:
    def park(doc: dict[str, Any]) -> None:
        _statement("Mentions cap-account-recovery.")(doc)
        _fr(doc)["scope"] = scope
        _fr(doc)["scope_reason"] = "Parked until the next release."

    assert _found(edited_example(tmp_path / "spec", **{FR_FILE: park})) == [("fr-password-reset", link_target("statement", "cap-account-recovery"))]


def _scenario(reverse: bool) -> list[tuple[str | None, str | None]]:
    def mention(doc: dict[str, Any]) -> None:
        for criterion in _criteria(doc):
            criterion["text"] = "Mentions cap-account-recovery and seed-accounts."
        if reverse:
            _fr(doc)["acceptance_criteria"] = list(reversed(_criteria(doc)))

    with tempfile.TemporaryDirectory() as folder:
        return _found(edited_example(Path(folder) / "spec", **{FR_FILE: mention}))


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_prose_ids_report_in_the_same_order_whatever_the_hash_seed(seed: int) -> None:
    expected = _scenario(False)
    assert [node for node, _ in expected] == ["ac-password-reset-1"] * 2 + ["ac-password-reset-2"] * 2 + ["ac-password-reset-3"] * 2
    assert seeded(seed, __name__, "_scenario", True) == jsonable(_scenario(True)) == jsonable(expected)


def test_a_nodes_own_id_in_its_text_is_not_a_finding(tmp_path: Path) -> None:
    """A node cannot link itself, so "turn the mention into the link" could not be followed; another node's id in the same text is still reported."""
    own = edited_example(tmp_path / "own" / "spec", **{FR_FILE: _statement("This is fr-password-reset, as agreed.")})
    assert _findings(own) == []
    both = edited_example(tmp_path / "both" / "spec", **{FR_FILE: _statement("This is fr-password-reset and not fr-password-reset-request.")})
    assert _found(both) == [("fr-password-reset", link_target("statement", "fr-password-reset-request"))]


KEBAB = {"type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"}
SNAKE = {"type": "string", "pattern": "^[A-Z0-9]+(?:_[A-Z0-9]+)*$"}
FREE = {"type": "string"}
DEFS = {"vc:test#kebab": KEBAB, "vc:test#snake": SNAKE, "vc:test#node": {"anyOf": [{"$ref": "vc:test#kebab"}, {"$ref": "vc:test#snake"}]}}


def _resolve(node: dict[str, Any]) -> dict[str, Any] | None:
    return DEFS.get(node["$ref"])


@pytest.mark.parametrize(
    ("slot", "fixed"),
    [
        ({"anyOf": [KEBAB, FREE]}, False),
        ({"anyOf": [KEBAB, SNAKE]}, True),
        ({"oneOf": [KEBAB, SNAKE]}, True),
        ({"$ref": "vc:test#kebab"}, True),
        ({"$ref": "vc:test#node"}, True),
        ({"anyOf": [{"$ref": "vc:test#kebab"}, {"$ref": "vc:test#missing"}]}, False),
        ({"anyOf": [{"$ref": "vc:test#node"}, FREE]}, False),
        ({"type": "string", "enum": ["a", "b"], "anyOf": [KEBAB, FREE]}, True),
    ],
)
def test_a_union_slot_is_fixed_only_when_every_branch_is(slot: dict[str, Any], fixed: bool) -> None:
    assert _all_fixed(alternatives_of(slot, _resolve)) is fixed


def test_a_slot_with_no_alternative_is_not_fixed() -> None:
    assert _all_fixed([]) is False


def _record_text(edit: Any) -> Edit:
    def apply(doc: dict[str, Any]) -> None:
        edit(doc["records"][0])

    return apply


RECORD_FILE = "extras/verification/ver-password-reset-expired-token.json"


def test_the_node_ids_of_a_records_proves_are_not_prose(tmp_path: Path) -> None:
    spec = edited_example(tmp_path / "spec", **{RECORD_FILE: _record_text(lambda record: record.__setitem__("proves", ["ac-password-reset-3", "api-password-reset-confirm"]))})
    assert _findings(spec) == []


def test_a_node_id_in_a_records_free_text_still_gives_e752(tmp_path: Path) -> None:
    def edit(record: dict[str, Any]) -> None:
        record["proves"] = ["ac-password-reset-3"]
        record["output_guard"] = "ac-password-reset-3 passed"

    (error,) = _findings(edited_example(tmp_path / "spec", **{RECORD_FILE: _record_text(edit)}))
    assert (error.code, error.node_id, error.target) == ("E752", "ver-password-reset-expired-token", link_target("output_guard", "ac-password-reset-3"))
