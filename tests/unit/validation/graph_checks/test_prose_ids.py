"""The id-in-prose check (E752, WI-M6b-11): what is scanned, what is a mention, who owns the finding, lifecycle and order."""
from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.graph.build import build_graph
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.prose_ids import check_prose_ids
from unit.graph._synth import HASH_SEEDS, ROOT, copy_example, load_doc, run_python_seeded, write_json

FR_FILE, NFR_FILE = "04_fr_list.json", "07_nfrs.json"
FR_PATH = ".functional_requirements[0]"
Edit = Callable[[dict[str, Any]], None]


def _fr(doc: dict[str, Any]) -> dict[str, Any]:
    return doc["functional_requirements"][0]


def _criteria(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return _fr(doc)["acceptance_criteria"]


def _spec(root: Path, **edits: Edit) -> Path:
    """A copy of the worked example with each edit (file name to function over the parsed document) applied."""
    spec = copy_example(root / "spec")
    for rel, edit in edits.items():
        document = load_doc(spec, rel)
        edit(document)
        write_json(spec, rel, document)
    return spec


def _findings(spec: Path) -> list[SpecError]:
    return check_prose_ids(GraphCheckContext.from_graph(build_graph(str(spec), str(ROOT)), None), "merge")


def _statement(text: str) -> Edit:
    return lambda doc: _fr(doc).__setitem__("statement", text)


def _found(spec: Path) -> list[tuple[str | None, str | None]]:
    return [(error.node_id, error.target) for error in _findings(spec)]


def test_worked_example_has_no_e752(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path)) == []


def test_id_in_a_description_gives_e752(tmp_path: Path) -> None:
    spec = _spec(tmp_path, **{FR_FILE: _statement("The system shall serve cap-account-recovery, as agreed.")})
    (error,) = _findings(spec)
    assert (error.code, error.node_id, error.file, error.jq_path) == ("E752", "fr-password-reset", FR_FILE, f"{FR_PATH}.statement")
    assert error.target == link_target("statement", "cap-account-recovery")
    assert "cap-account-recovery" in error.message and "reword" in error.message


def test_unresolved_id_shaped_token_is_not_flagged(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path, **{FR_FILE: _statement("It replaces fr-old-export and fr-password-reset-requests.")})) == []


def test_contract_value_not_equal_to_a_live_id_is_not_flagged(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path, **{FR_FILE: _statement("POST /v1/password-resets/{token} returns err-token-expired.")})) == []


def test_id_in_a_link_field_is_not_flagged(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    assert load_doc(spec, FR_FILE)["functional_requirements"][0]["derives_from"] == ["cap-account-recovery"]
    assert _findings(spec) == []


def test_enum_field_is_not_flagged(tmp_path: Path) -> None:
    spec = _spec(tmp_path, **{FR_FILE: lambda doc: _fr(doc).__setitem__("priority", "cap-account-recovery")})
    assert _findings(spec) == []
    prose = _spec(tmp_path / "prose", **{FR_FILE: lambda doc: _fr(doc).__setitem__("rationale", "cap-account-recovery")})
    assert _found(prose) == [("fr-password-reset", link_target("rationale", "cap-account-recovery"))]


def test_alias_of_a_renamed_node_is_flagged(tmp_path: Path) -> None:
    def rename(doc: dict[str, Any]) -> None:
        _fr(doc)["aliases"] = ["fr-reset-old"]
        _criteria(doc)[0]["text"] = "As fr-reset-old says, a link is emailed."

    (error,) = _findings(_spec(tmp_path, **{FR_FILE: rename}))
    assert (error.node_id, error.target) == ("ac-password-reset-1", link_target("text", "fr-password-reset"))
    assert "fr-reset-old" in error.message and "fr-password-reset" in error.message


def test_seed_id_in_prose_is_flagged(tmp_path: Path) -> None:
    assert _found(_spec(tmp_path, **{FR_FILE: _statement("As in seed-accounts, a member recovers access.")})) == [
        ("fr-password-reset", link_target("statement", "seed-accounts"))
    ]


def test_name_like_environment_id_in_prose_is_not_flagged(tmp_path: Path) -> None:
    assert _findings(_spec(tmp_path, **{FR_FILE: _statement("Runs in dev, ci and staging before prod.")})) == []


def test_e752_owner_is_the_nodes_own_step(tmp_path: Path) -> None:
    spec = _spec(tmp_path, **{NFR_FILE: lambda doc: doc["nfrs"][0].__setitem__("measurement_method", "Measured as fr-password-reset behaves.")})
    (error,) = _findings(spec)
    assert (error.node_id, error.owner) == ("nfr-latency-reset-email", "step:07")


def test_leaf_of_a_nested_criterion_is_owned_by_the_criterion(tmp_path: Path) -> None:
    spec = _spec(tmp_path, **{FR_FILE: lambda doc: _criteria(doc)[0].__setitem__("text", "Covered by api-password-reset-confirm.")})
    (error,) = _findings(spec)
    assert (error.node_id, error.owner, error.jq_path) == ("ac-password-reset-1", "step:04", f"{FR_PATH}.acceptance_criteria[0].text")


def test_two_ids_in_one_leaf_are_two_findings_with_distinct_identity(tmp_path: Path) -> None:
    spec = _spec(tmp_path, **{FR_FILE: _statement("See cap-account-recovery and seed-accounts; again cap-account-recovery.")})
    errors = _findings(spec)
    assert [error.target for error in errors] == [link_target("statement", "cap-account-recovery"), link_target("statement", "seed-accounts")]
    assert len({(error.node_id, error.file, error.jq_path, error.target) for error in errors}) == 2


def test_prose_ids_do_not_read_a_not_applicable_node(tmp_path: Path) -> None:
    def mention(lifecycle: str) -> Edit:
        def edit(doc: dict[str, Any]) -> None:
            _statement("Mentions cap-account-recovery.")(doc)
            _fr(doc)["lifecycle"] = lifecycle

        return edit

    assert _findings(_spec(tmp_path / "gone", **{FR_FILE: mention("not_applicable")})) == []
    assert _found(_spec(tmp_path / "old", **{FR_FILE: mention("deprecated")})) == [("fr-password-reset", link_target("statement", "cap-account-recovery"))]


def _scenario(reverse: bool) -> list[tuple[str | None, str | None]]:
    def mention(doc: dict[str, Any]) -> None:
        for criterion in _criteria(doc):
            criterion["text"] = f"Mentions {criterion['criterion_id']} and seed-accounts."
        if reverse:
            _fr(doc)["acceptance_criteria"] = list(reversed(_criteria(doc)))

    with tempfile.TemporaryDirectory() as folder:
        return _found(_spec(Path(folder), **{FR_FILE: mention}))


_ORDER_CODE = """
import json
from unit.validation.graph_checks.test_prose_ids import _scenario
print(json.dumps(_scenario(True)))
"""


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_prose_ids_report_in_the_same_order_whatever_the_hash_seed(seed: int) -> None:
    expected = _scenario(False)
    assert [node for node, _ in expected] == ["ac-password-reset-1"] * 2 + ["ac-password-reset-2"] * 2 + ["ac-password-reset-3"] * 2
    assert json.loads(run_python_seeded(seed, _ORDER_CODE)) == [list(item) for item in _scenario(True)] == [list(item) for item in expected]
