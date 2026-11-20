"""The glossary-use check (E741, WI-M6b-03): the matcher, the user set, the owner and the lifecycle and order of the finding."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.model import Graph
from specdev_tools.trace.label_rename import label_users, rename_label
from specdev_tools.validation.graph_checks.codes import TERM_NOT_USED_BY_LABEL
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.term_use import check_term_use, label_matches, normalise
from unit.graph._synth import HASH_SEEDS, ROOT, copy_example, load_doc, run_python_seeded, write_json

GLOSSARY = "03_glossary.json"
FR_FILE = "04_fr_list.json"
TERM, OTHER_TERM = "term-reset-token", "term-reset-email-delivery-time-p95"
MARKER = "zq marker"

Edit = Callable[[dict[str, Any]], None]


def _terms(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return doc["terms"]


def _fr(doc: dict[str, Any]) -> dict[str, Any]:
    return doc["functional_requirements"][0]


def _spec(tmp_path: Path, **edits: Edit) -> Path:
    """A copy of the worked example with each edit (file name to function over the parsed document) applied."""
    spec = copy_example(tmp_path / "spec")
    for rel, edit in edits.items():
        document = load_doc(spec, rel)
        edit(document)
        write_json(spec, rel, document)
    return spec


def _context(spec: Path) -> GraphCheckContext:
    return GraphCheckContext.from_graph(build_graph(str(spec), str(ROOT)), None)


def _found(spec: Path) -> list[tuple[str, str | None]]:
    return [(error.node_id, error.owner) for error in check_term_use(_context(spec), "merge") if error.code == TERM_NOT_USED_BY_LABEL]


def _relabel(doc: dict[str, Any], label: str = MARKER) -> None:
    _terms(doc)[0]["term"] = label


def _say(text: str) -> Edit:
    """Edit that puts *text* in the first requirement's statement."""
    return lambda doc: _fr(doc).__setitem__("statement", text)


@pytest.mark.parametrize(
    ("label", "text"),
    [
        ("reset token", "A reset token is spent."),
        ("Reset Token", "the RESET TOKEN is spent"),
        ("reset token", "the reset-token is spent"),
        ("reset-token", "the reset token is spent"),
        ("reset_token", "the reset token is spent"),
        ("reset token", "reset/token pairs"),
        ("reset token", "two reset tokens issued"),
        ("reset token", "the reset  \n token"),
        ("box", "all boxes are shipped"),
        ("reset token", "the reset token."),
        ("Ｒeset token", "the reset token"),  # NFKC: a full-width letter
    ],
)
def test_label_matches_case_hyphen_and_plural(label: str, text: str) -> None:
    assert label_matches(label, text)


@pytest.mark.parametrize(
    ("label", "text"),
    [
        ("Tag", "The Tagline is long."),
        ("Tag", "a pretag value"),
        ("reset token", "a reset tokenizer"),
        ("reset token", "reset tokenx"),
        ("reset token", "the token to reset"),
        ("reset token", "reset-tokenizer"),
        ("reset token", "resettoken"),
        ("   ", "anything"),
    ],
)
def test_label_does_not_match_on_a_longer_word(label: str, text: str) -> None:
    assert not label_matches(label, text)


def test_normalise_folds_case_separators_and_space() -> None:
    assert normalise("  Reset_Token-/ Pairs ") == "reset token pairs"


def test_old_label_does_not_match_after_a_label_rename(tmp_path: Path) -> None:
    """A label changed without its uses leaves the term unused (the old label is no alias); the rename command rewrites the uses and clears it."""
    spec = _spec(tmp_path / "relabelled", **{GLOSSARY: lambda doc: _relabel(doc, "recovery code")})
    assert _found(spec) == [(TERM, "step:14")]
    renamed = copy_example(tmp_path / "renamed")
    result = rename_label(str(renamed), str(ROOT), TERM, "recovery code", apply=True)
    assert result.written and result.uses and _found(renamed) == []
    assert not label_matches("reset token", "A recovery code is single-use.")


def test_term_label_is_read_from_the_term_field(tmp_path: Path) -> None:
    spec = _spec(tmp_path, **{GLOSSARY: _relabel})
    node = build_graph(str(spec), str(ROOT)).by_id[TERM]
    assert node.label == "", "a term has no Node.label: the label is its `term` field"
    assert _found(spec) == [(TERM, "step:14")]
    (error,) = [e for e in check_term_use(_context(spec), "merge")]
    assert f"'{MARKER}'" in error.message and error.node_id == TERM and error.file == GLOSSARY


def test_term_with_no_match_is_e741_with_owner_step_14(tmp_path: Path) -> None:
    assert _found(copy_example(tmp_path / "clean")) == []
    spec = _spec(tmp_path / "unused", **{GLOSSARY: _relabel})
    (error,) = check_term_use(_context(spec), "merge")
    assert (error.code, error.node_id, error.owner) == (TERM_NOT_USED_BY_LABEL, TERM, "step:14")


def test_term_matched_by_task_criterion_text_is_used(tmp_path: Path) -> None:
    def criterion_says_marker(doc: dict[str, Any]) -> None:
        doc["milestones"][0]["tasks"][0]["acceptance_criteria"][0]["text"] = f"The {MARKER}s are rejected."

    spec = _spec(tmp_path, **{GLOSSARY: _relabel})
    assert _found(spec) == [(TERM, "step:14")]
    used = _spec(tmp_path / "used", **{GLOSSARY: _relabel, "14_roadmap.json": criterion_says_marker})
    assert _found(used) == []


def test_user_set_is_steps_04_to_15_non_record_in_play(tmp_path: Path) -> None:
    """The label is found in a user (a requirement of step 04) but not in step 00, 03, 16, 16a, a record or a not_applicable node."""
    spec = _spec(tmp_path, **{GLOSSARY: _relabel})
    graph = build_graph(str(spec), str(ROOT))
    users = label_users(graph)
    assert users and {node.step for node in users} <= {"04", "05", "06", "07", "08", "09", "10", "11", "12", "13a", "14", "15"}
    assert all(node.role != "record" and node.lifecycle != "not_applicable" for node in users)
    assert {"00", "03", "16", "16a"}.isdisjoint({node.step for node in users})

    def charter(doc: dict[str, Any]) -> None:
        doc["risks"][0]["text"] = f"A {MARKER} could leak."

    def anchor(doc: dict[str, Any]) -> None:
        doc["plan"]["summary"]["functional_summary"] = f"A {MARKER}."

    def plan(doc: dict[str, Any]) -> None:
        doc["plan"]["summary"]["functional_summary"] = f"A {MARKER}."

    def record(doc: dict[str, Any]) -> None:
        doc["records"][0]["commands"][0] = f"check the {MARKER}"

    def retired(doc: dict[str, Any]) -> None:
        _fr(doc)["statement"] = f"The {MARKER} is spent."
        _fr(doc)["lifecycle"] = "not_applicable"

    outside = _spec(
        tmp_path / "outside",
        **{GLOSSARY: _relabel, "00_charter.json": charter, "16_impl_context.json": anchor,
           "impl_context/ms_account_recovery_plan.json": plan, "extras/verification/ver-password-reset-expired-token.json": record,
           FR_FILE: retired},
    )
    assert _found(outside) == [(TERM, "step:14")]
    inside = _spec(tmp_path / "inside", **{GLOSSARY: _relabel, FR_FILE: _say(f"The {MARKER} is spent.")})
    assert _found(inside) == []


def test_not_applicable_term_is_not_checked(tmp_path: Path) -> None:
    """A not_applicable term is not reported, a deprecated one is; scope does not apply to a term."""

    def lifecycle(value: str) -> Edit:
        return lambda doc: (_relabel(doc), _terms(doc)[0].__setitem__("lifecycle", value))

    assert _found(_spec(tmp_path / "na", **{GLOSSARY: lifecycle("not_applicable")})) == []
    assert _found(_spec(tmp_path / "dep", **{GLOSSARY: lifecycle("deprecated")})) == [(TERM, "step:14")]

    def scoped_out(doc: dict[str, Any]) -> None:
        _relabel(doc)
        _terms(doc)[0]["scope"] = "out"

    assert [node for node, _ in _found(_spec(tmp_path / "out", **{GLOSSARY: scoped_out}))] == [TERM]


def test_a_not_applicable_user_is_not_a_use(tmp_path: Path) -> None:
    """The user of the only match is not_applicable: the term is unused (the node is not read)."""

    def retired(doc: dict[str, Any]) -> None:
        _fr(doc)["lifecycle"] = "not_applicable"

    spec = _spec(tmp_path, **{GLOSSARY: _relabel, FR_FILE: lambda doc: (_say(f"The {MARKER} is spent.")(doc), retired(doc))})
    assert _found(spec) == [(TERM, "step:14")]


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_term_use_reports_in_the_same_order_whatever_the_hash_seed(seed: int, tmp_path: Path) -> None:
    """Terms are given in reverse order, three of them unused; the findings come in id order under every hash seed."""

    def reversed_unused(doc: dict[str, Any]) -> None:
        template = _terms(doc)[0]
        extra = [{**template, "term_id": f"term-{name}", "term": f"zq {name}", "term_ref": {**template["term_ref"], "id": f"cn:project:term:{name}"}}
                 for name in ("mmm", "aaa", "zzz")]
        doc["terms"] = [*extra, *_terms(doc)]
        doc["canonical_refs_used"] += [{"id": f"cn:project:term:{name}", "kind": "term", "version": "^1.0.0"} for name in ("mmm", "aaa", "zzz")]

    spec = _spec(tmp_path, **{GLOSSARY: reversed_unused})
    code = (
        "from specdev_tools.graph.build import build_graph\n"
        "from specdev_tools.validation.graph_checks.context import GraphCheckContext\n"
        "from specdev_tools.validation.graph_checks.term_use import check_term_use\n"
        f"graph = build_graph({str(spec)!r}, {str(ROOT)!r})\n"
        "import json\n"
        "print(json.dumps([e.node_id for e in check_term_use(GraphCheckContext.from_graph(graph, None), 'merge')]))\n"
    )
    assert json.loads(run_python_seeded(seed, code)) == ["term-aaa", "term-mmm", "term-zzz"]
    ordered = [e.node_id for e in check_term_use(_context(spec), "merge")]
    assert ordered == ["term-aaa", "term-mmm", "term-zzz"]
