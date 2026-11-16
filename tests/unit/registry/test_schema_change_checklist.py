"""Schema-change rows: shape, closure against the 1.1.1 baseline, design closure, generated checklist (WI-M3-01c)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from specdev_tools.registry.schema_checklist import (
    CHECKLIST_FILE,
    ROWS_FILE,
    ChangeRow,
    ChecklistError,
    covers,
    differing_paths,
    generate_checklist,
    load_baseline,
    load_rows,
    matches,
    parse_rows,
    render_checklist,
    row_holds,
    selects,
    uncovered_paths,
)
from specdev_tools.registry.schema_paths import PathInfo, flatten_schema_dir

_ROOT = Path(__file__).parents[3]
_BASELINE = _ROOT / "tests" / "fixtures" / "schema_baseline" / "paths_1.1.1.json"

#: Schemas that describe the toolkit's own file formats; no host migrates them, so no row covers them.
_TOOLKIT_FORMAT_SCHEMAS = frozenset({"cli_commands", "entry_key_registry", "step_order"})

#: Removals the design names (DS L112, DS L352 H9, DOC L1167-1186): ``(where the design names it, schema, baseline path)``.
_DESIGN_REMOVALS = (
    ("DS L112", "00_charter", "spec_refs_ingested"),
    ("DS L112", "04_fr_list", "seed_refs_ingested"),
    ("DS L112", "02_system_sketch", "tech_stack"),
    ("DS L112", "09_impl_plan", "tech_stack"),
    ("DS L112", "14_roadmap", "tech_stack"),
    ("DS L112", "16_impl_context", "plan.spec_alignment.checklist[].linked_test_expectation"),
    ("DS L112", "16_impl_context", "review.findings[].spec_ref.line_range"),
    ("DS L112", "16_impl_context", "review.findings[].spec_ref.commit_hash"),
    ("DS L112", "16_anchor", "plan.milestone_index[].fr_refs"),
    ("DS L112", "16_anchor", "plan.milestone_index[].context_path"),
    ("DS L112", "16_impl_context", "plan.spec_alignment.checklist[].milestone_ref"),
    ("DS L112", "09_impl_plan", "milestones[].status"),
    ("DS L112", "14_roadmap", "milestones[].status"),
    ("DS L112", "16_impl_context", "review.fixture_status.test_results"),
    ("DS L112", "16_impl_context", "plan.spec_alignment.checklist[].implementation.status"),
    ("DS L112", "05_interface_contracts", "apis[].example_refs"),
    ("DS L112", "09_impl_plan", "trace"),
    ("DS L112", "10_governance", "links"),
    ("DS L352 H9", "16_impl_context", "plan.security.spec_mutations"),
    ("DS L352 H9", "16_impl_context", "plan.security.new_fixtures"),
    ("DS L352 H9", "16_impl_context", "execution.execution_results[].evidence_binding"),
    ("DOC L1167-1186", "14_roadmap", "milestones[].tasks[].status"),
    ("DOC L1167-1186", "14_roadmap", "milestones[].tasks[].assumptions"),
    ("DOC L1167-1186", "14_roadmap", "milestones[].source_milestones"),
    ("DOC L1167-1186", "14_roadmap", "milestones[].deliverables"),
    ("DOC L1167-1186", "09_impl_plan", "milestones[].depends_on"),
    ("DOC L1167-1186", "09_impl_plan", "dependencies"),
    ("DOC L1167-1186", "14_roadmap", "dependencies"),
    ("DOC L1167-1186", "09_impl_plan", "dependencies[].dependency_ref"),
    ("DOC L1167-1186", "14_roadmap", "dependencies[].dependency_ref"),
    ("DOC L1167-1186", "02_system_sketch", "connections[].schema_ref"),
    ("DOC L1167-1186", "02_system_sketch", "connections[].interface_ref"),
    ("DOC L1167-1186", "12_ci_gates", "jobs[].steps[].id"),
    ("DOC L1167-1186", "01_capabilities", "capabilities[].scope"),
    ("DOC L1167-1186", "04_fr_list", "functional_requirements[].priority"),
    ("DOC L1167-1186", "05_interface_contracts", "out_of_scope"),
    ("DOC L1167-1186", "08_fixtures", "out_of_scope"),
    ("DOC L1167-1186", "16_impl_context", "plan.status"),
    ("DOC L1167-1186", "16_impl_context", "plan.spec_alignment.checklist[].checklist_status"),
    ("DOC L1167-1186", "16_impl_context", "plan.spec_alignment.checklist[].deferred_reason"),
    ("DOC L1167-1186", "16_impl_context", "plan.spec_alignment.checklist[].wont_do_reason"),
    ("DOC L1167-1186", "10_governance", "review_policy"),
    ("DOC L1167-1186", "10_governance", "reviewers"),
)


@pytest.fixture(scope="module")
def rows() -> list[ChangeRow]:
    parsed, problems = load_rows(_ROOT / ROWS_FILE)
    assert problems == []
    return parsed


@pytest.fixture(scope="module")
def baseline() -> dict[str, dict[str, PathInfo]]:
    return load_baseline(_BASELINE)


@pytest.fixture(scope="module")
def current() -> dict[str, dict[str, PathInfo]]:
    return flatten_schema_dir(_ROOT / "schema")


def _row(**fields: Any) -> dict[str, Any]:
    base = {"id": "SC-00-01", "step": "00", "path": "a", "change": "add", "replaced_by": None,
            "owner": "M2", "design": [], "tickets": [], "shim": False}
    return {**base, **fields}


def _inventory(**paths: PathInfo) -> dict[str, dict[str, PathInfo]]:
    return {"00_charter": paths}


def test_rows_are_well_formed_and_ids_unique() -> None:
    document_rows, problems = load_rows(_ROOT / ROWS_FILE)
    assert problems == []
    assert len({r.id for r in document_rows}) == len(document_rows) > 0


@pytest.mark.parametrize(
    "raw, fragment",
    [
        ([], "'rows' array"),
        ({"rows": "x"}, "'rows' array"),
        ({"rows": [3]}, "not an object"),
        ({"rows": [_row(change="rename")]}, "change"),
        ({"rows": [_row(owner="M4")]}, "owner"),
        ({"rows": [_row(replaced_by=3)]}, "replaced_by"),
        ({"rows": [_row(design="DS L1")]}, "design"),
        ({"rows": [_row(tickets=[1])]}, "tickets"),
        ({"rows": [_row(shim="no")]}, "shim"),
        ({"rows": [_row(path="")]}, "path"),
        ({"rows": [_row(id=7)]}, "id"),
        ({"rows": [_row(id="SC-01-01")]}, "not SC-<step>-<nn>"),
        ({"rows": [_row(), _row()]}, "duplicate"),
    ],
)
def test_parse_rows_reports_a_wrong_typed_value_without_raising(raw: Any, fragment: str) -> None:
    rows_found, problems = parse_rows(raw)
    assert any(fragment in p for p in problems)
    assert len(rows_found) <= 1


def test_parse_rows_accepts_core_step_ids() -> None:
    parsed, problems = parse_rows({"rows": [_row(id="SC-core-atoms-01", step="core/atoms")]})
    assert problems == [] and [r.step for r in parsed] == ["core/atoms"]


def test_load_baseline_rejects_a_file_without_schemas(tmp_path: Path) -> None:
    broken = tmp_path / "baseline.json"
    broken.write_text('{"ref": "x"}')
    with pytest.raises(ChecklistError):
        load_baseline(broken)


@pytest.mark.parametrize(
    "step, schema, expected",
    [
        ("00", "00_charter", True),
        ("13", "13_extension_manifest", True),
        ("13", "13a_completeness_assessment", False),
        ("13a", "13a_completeness_assessment", True),
        ("16", "16_anchor", True),
        ("16", "16_impl_context", True),
        ("16_anchor", "16_impl_context", False),
        ("core/atoms", "core/atoms", True),
        ("core/atoms", "core/collections", False),
    ],
)
def test_step_selects_schemas_by_equal_or_underscore_prefix(step: str, schema: str, expected: bool) -> None:
    assert selects(step, schema) is expected


@pytest.mark.parametrize(
    "glob, path, whole, below",
    [
        ("a[].b", "a[].b", True, True),
        ("a[].b", "a[].b.c", False, True),
        ("a[].b", "a[].bc", False, False),
        ("**.lifecycle", "x[].y.lifecycle", True, True),
        ("*.lifecycle", "x.lifecycle", True, True),
        ("*.lifecycle", "x[].y.lifecycle", False, False),
        ("$defs.link*", "$defs.linkVerb", True, True),
        ("m{}", "m{}.k", False, True),
    ],
)
def test_glob_matches_whole_paths_and_covers_the_subtree(glob: str, path: str, whole: bool, below: bool) -> None:
    assert (matches(glob, path), covers(glob, path)) == (whole, below)


@pytest.mark.parametrize(
    "before, after",
    [
        (PathInfo("string", None), PathInfo("object", None)),
        (PathInfo("object", "vc:core:atoms#a"), PathInfo("object", "vc:core:atoms#b")),
        (PathInfo("string", None, ("x", "y")), PathInfo("string", None, ("x",))),
    ],
)
def test_change_row_compares_type_or_ref(before: PathInfo, after: PathInfo) -> None:
    row = parse_rows({"rows": [_row(change="change")]})[0][0]
    assert row_holds(row, _inventory(a=before), _inventory(a=after))
    assert not row_holds(row, _inventory(a=before), _inventory(a=before))
    assert not row_holds(row, _inventory(a=before), _inventory())


def test_change_row_holds_on_the_real_object_to_string_scope_change(
    rows: list[ChangeRow], baseline: dict[str, dict[str, PathInfo]], current: dict[str, dict[str, PathInfo]]
) -> None:
    (row,) = [r for r in rows if r.step == "06" and r.path == "rules[].scope"]
    assert (baseline["06_invariants"]["rules[].scope"].type, current["06_invariants"]["rules[].scope"].type) == ("object", "string")
    assert row_holds(row, baseline, current)


def test_add_and_remove_rows_look_at_presence_only() -> None:
    add, remove = (parse_rows({"rows": [_row(change=c)]})[0][0] for c in ("add", "remove"))
    present, absent = _inventory(a=PathInfo("string", None)), _inventory()
    assert row_holds(add, absent, present) and not row_holds(add, present, present)
    assert row_holds(remove, present, absent) and not row_holds(remove, absent, absent)


def test_forward_closure_each_row_change_holds_in_current_schemas(
    rows: list[ChangeRow], baseline: dict[str, dict[str, PathInfo]], current: dict[str, dict[str, PathInfo]]
) -> None:
    assert [r.id for r in rows if not row_holds(r, baseline, current)] == []


def test_backward_closure_every_differing_path_is_covered_by_a_row(
    rows: list[ChangeRow], baseline: dict[str, dict[str, PathInfo]], current: dict[str, dict[str, PathInfo]]
) -> None:
    schemas = (set(baseline) | set(current)) - _TOOLKIT_FORMAT_SCHEMAS
    assert _TOOLKIT_FORMAT_SCHEMAS <= set(baseline) | set(current)
    assert uncovered_paths(rows, baseline, current, schemas) == []


def test_backward_closure_names_a_path_no_row_covers() -> None:
    parsed = parse_rows({"rows": [_row(path="a")]})[0]
    before, after = _inventory(a=PathInfo("string", None)), _inventory(a=PathInfo("string", None), b=PathInfo("string", None))
    assert differing_paths(before, after, "00_charter") == ["b"]
    assert uncovered_paths(parsed, before, after, ["00_charter"]) == ["00_charter:b"]


@pytest.mark.parametrize("source, schema, path", _DESIGN_REMOVALS, ids=[f"{s}-{p}" for _, s, p in _DESIGN_REMOVALS])
def test_design_closure_every_named_removal_has_a_row(
    rows: list[ChangeRow], baseline: dict[str, dict[str, PathInfo]], source: str, schema: str, path: str
) -> None:
    assert path in baseline[schema], f"{source}: {schema} has no {path} in the baseline"
    assert any(
        r.change in ("remove", "change") and selects(r.step, schema) and covers(r.path, path) for r in rows
    ), f"{source}: no remove or change row covers {schema}:{path}"


def test_render_groups_rows_by_step_and_escapes_pipes() -> None:
    parsed = parse_rows({"rows": [
        _row(id="SC-00-01", path="a|b", replaced_by="c"),
        _row(id="SC-01-01", step="01"),
        _row(id="SC-00-02", path="z", design=["DS L1", "DS L2"], tickets=["DEVSPEC-9"], shim=True),
    ]})[0]
    text = render_checklist(parsed)
    assert text.count("\n## ") == 2 and text.index("## 00") < text.index("## 01")
    assert "| ID | Path | Change | Replaced by | Tickets | Shim |" in text
    assert "| SC-00-01 | `a\\|b` | add | c |  |  |" in text
    assert "| SC-00-02 | `z` | add |  | DEVSPEC-9 | yes |" in text
    assert "Owner" not in text and "Design" not in text and "DS L1" not in text


def test_generate_checklist_raises_naming_the_problem(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / ROWS_FILE).write_text('{"rows": [{"id": 1}]}')
    with pytest.raises(ChecklistError, match="rows\\[0\\]"):
        generate_checklist(tmp_path)


def test_generated_markdown_equals_committed_file() -> None:
    assert (_ROOT / CHECKLIST_FILE).read_text(encoding="utf-8") == generate_checklist(_ROOT)
