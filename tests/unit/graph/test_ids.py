"""Tests for the id rules of the spec graph (WI-M4-03): slug minting, suggested prefixes and the uniqueness check."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.ids import check_unique_ids, first_free_id, mint_slug, suggest_prefix
from specdev_tools.graph.kinds import load_kind_registry
from specdev_tools.validation.validate import validate_file

from ._synth import EXAMPLE_SPEC, ROOT, docs_graph, load_doc, write_json


def test_mint_slug_deterministic() -> None:
    taken = {"fr-other"}
    first = mint_slug("Reset the user's password!", taken, prefix="fr-")
    assert first == "fr-reset-the-user-s-password"
    assert mint_slug("Reset the user's password!", taken, prefix="fr-") == first
    assert mint_slug("Reset the user's password!", set(taken), prefix="fr-") == first


def test_mint_slug_numeric_suffix_on_collision() -> None:
    taken = {"fr-login"}
    assert mint_slug("Login", taken, prefix="fr-") == "fr-login-2"
    taken.add("fr-login-2")
    assert mint_slug("Login", taken, prefix="fr-") == "fr-login-3"
    assert first_free_id("fr-login", taken) == "fr-login-3"
    assert first_free_id("fr-free", taken) == "fr-free"


@pytest.mark.parametrize("max_len", [0, -1, -50])
def test_mint_slug_refuses_a_max_len_below_one(max_len: int) -> None:
    with pytest.raises(ValueError, match="max_len must be 1 or more"):
        mint_slug("abc def", set(), max_len=max_len)
    assert mint_slug("abc def", set(), max_len=1) == "a"


def test_mint_slug_never_rederived_for_existing() -> None:
    """A text whose slug is an id that exists gets a new id; the taken set and the existing id are left alone."""
    taken = {"ac-login-1"}
    minted = mint_slug("login 1", taken, prefix="ac-")
    assert minted == "ac-login-1-2"
    assert taken == {"ac-login-1"}


def test_mint_slug_cuts_on_a_word_boundary() -> None:
    text = "the confirm endpoint redeems a reset token and sets the new password for the member"
    slug = mint_slug(text, set(), max_len=30)
    assert slug == "the-confirm-endpoint-redeems-a"
    assert len(slug) <= 30
    assert mint_slug("abcdefghij" * 3, set(), max_len=12) == "abcdefghijab"


def test_mint_slug_keeps_a_slug_of_exactly_max_len_whole() -> None:
    assert mint_slug("ab cd", set(), max_len=5) == "ab-cd"
    assert mint_slug("ab cd", set(), max_len=4) == "ab"


def test_mint_slug_keeps_ascii_letters_of_accented_text() -> None:
    assert mint_slug("Réinitialiser le mot de passe", set()) == "reinitialiser-le-mot-de-passe"


def test_mint_slug_rejects_text_without_letters_or_digits() -> None:
    with pytest.raises(ValueError):
        mint_slug("日本語 --", set())


def test_suggest_prefix_table() -> None:
    expected = {
        "scope-item": "scope-", "assumption": "asm-", "need": "need-", "stakeholder": "sh-", "segment": "seg-",
        "metric": "metric-", "risk": "risk-", "capability": "cap-", "third-party": "tp-", "connection": "conn-",
        "constraint": "con-", "fr": "fr-", "criterion": "ac-", "api": "api-", "api-error": "err-",
        "invariant": "inv-", "nfr": "nfr-", "fixture": "fix-", "design-milestone": "ms-",
        "roadmap-milestone": "ms-", "task": "task-", "task-criterion": "tc-", "threat": "threat-",
        "edge-case": "ec-", "job": "job-", "scaffold-row": "scaffold-", "anchor-row": "anchor-", "rule": "rule-",
        "secret": "secret-",
    }
    assert {kind: suggest_prefix(kind) for kind in expected} == expected
    kinds = set(load_kind_registry(str(ROOT)).kind_names)
    assert set(expected) <= kinds
    for kind in ("gate", "plan-item", "seed", "unknown-kind"):
        assert suggest_prefix(kind) is None


def _error_codes(errors: list[SpecError]) -> list[str]:
    return [error.code for error in errors if error.code.startswith("E")]


def test_plan_item_id_lowercase_fails_schema(tmp_path: Path) -> None:
    """A plan item id is upper-case; the schema rejects a lowercase one."""
    plan = load_doc(EXAMPLE_SPEC, "impl_context/ms_account_recovery_plan.json")
    path = tmp_path / "impl_context" / "ms_account_recovery_plan.json"
    write_json(tmp_path, "impl_context/ms_account_recovery_plan.json", plan)
    assert _error_codes(validate_file(str(ROOT), str(path), include_id_slice=False)) == []
    plan["plan"]["spec_alignment"]["checklist"][0]["id"] = "pwreset_confirm_expired_01"
    path.write_text(json.dumps(plan), encoding="utf-8")
    errors = validate_file(str(ROOT), str(path), include_id_slice=False)
    assert _error_codes(errors) == ["E520"]
    assert any("pwreset_confirm_expired_01" in error.message and "does not match '^[A-Z0-9_]+$'" in error.message for error in errors)


def _fr_doc(*fr_ids: str) -> dict[str, Any]:
    return {"functional_requirements": [{"fr_id": fr_id} for fr_id in fr_ids]}


def test_unique_ids_hint_is_the_first_free_suffixed_id() -> None:
    graph = docs_graph({"04_fr_list.json": _fr_doc("fr-a", "fr-a", "fr-a", "fr-a-2")})
    errors = check_unique_ids(graph)
    assert [error.node_id for error in errors] == ["fr-a", "fr-a"]
    assert "'fr-a-3'" in errors[0].message
    assert "'fr-a-4'" in errors[1].message
    assert {error.jq_path for error in errors} == {".functional_requirements[1]", ".functional_requirements[2]"}


def test_unique_ids_names_both_definitions_and_the_later_step_owns_it() -> None:
    docs = {
        "04_fr_list.json": {"functional_requirements": [{"fr_id": "fr-a", "acceptance_criteria": [{"criterion_id": "ac-a-1"}]}]},
        "14_roadmap.json": {"milestones": [{"milestone_id": "ms-a", "tasks": [{"task_id": "task-a", "acceptance_criteria": [
            {"criterion_id": "ac-a-1"}]}]}]},
    }
    (error,) = check_unique_ids(docs_graph(docs))
    assert (error.code, error.owner, error.node_id, error.file) == ("E704", "step:14", "ac-a-1", "14_roadmap.json")
    assert "04_fr_list.json .functional_requirements[0].acceptance_criteria[0]" in error.message
    assert "14_roadmap.json .milestones[0].tasks[0].acceptance_criteria[0]" in error.message


def test_unique_ids_step_filter_keeps_the_duplicates_of_those_steps() -> None:
    docs = {
        "04_fr_list.json": _fr_doc("fr-a", "fr-a"),
        "07_nfrs.json": {"nfrs": [{"nfr_id": "nfr-a"}, {"nfr_id": "nfr-a"}]},
    }
    graph = docs_graph(docs)
    assert {error.node_id for error in check_unique_ids(graph)} == {"fr-a", "nfr-a"}
    assert [error.node_id for error in check_unique_ids(graph, steps=["07"])] == ["nfr-a"]
    assert check_unique_ids(graph, steps=["12"]) == []


def test_unique_ids_of_a_unique_graph_is_empty() -> None:
    assert check_unique_ids(docs_graph({"04_fr_list.json": _fr_doc("fr-a", "fr-b")})) == []
