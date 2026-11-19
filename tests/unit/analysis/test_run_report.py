"""``run`` returns a typed report whose exit code comes from the problems found, not from the text of a line."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from specdev_tools.analysis.upstream_backlog import BacklogReport, ItemProblem, load_items, run

from ..graph._synth import write_json

TOOLKIT = Path(__file__).resolve().parents[3]
EXAMPLE_SPEC = TOOLKIT / "tests" / "fixtures" / "graph_example" / "spec"
FIXTURES_FILE = "08_fixtures.json"


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    folder = tmp_path / "spec"
    shutil.copytree(EXAMPLE_SPEC, folder)
    return folder


def _with_items(spec: Path, *items: dict) -> None:
    document = json.loads((spec / FIXTURES_FILE).read_text(encoding="utf-8"))
    document["ambiguities"] = list(items)
    write_json(spec, FIXTURES_FILE, document)


def _run(spec: Path) -> BacklogReport:
    return run(str(spec), repo_root=str(TOOLKIT))


def test_run_returns_a_named_report_that_still_unpacks_as_a_triple(spec: Path) -> None:
    report = _run(spec)
    stdout, stderr_lines, exit_code = report
    assert isinstance(report, BacklogReport)
    assert (stdout, stderr_lines, exit_code) == (report.stdout, report.stderr_lines, report.exit_code) == ("Totals: 0 items / 0 with answer / 0 needing answer.", [], 0)


def test_a_warning_line_never_sets_the_exit_code(spec: Path) -> None:
    _with_items(spec, {"id": "amb-lost", "description": "d", "about": ["fr-does-not-exist"]})
    report = _run(spec)
    assert report.exit_code == 0
    assert [line.split()[0] for line in report.stderr_lines] == ["W613"]


def test_an_item_with_neither_about_nor_severity_says_so_and_the_run_goes_on(spec: Path) -> None:
    _with_items(spec, {"id": "amb-noabout", "description": "na"}, {"id": "amb-ok", "description": "d", "about": ["fr-does-not-exist"]})
    report = _run(spec)
    assert report.exit_code == 2
    (problem_line,) = [line for line in report.stderr_lines if line.startswith("E520")]
    assert "item has neither about nor a valid severity" in problem_line and "invalid_severity" not in problem_line
    assert "08_fixtures.json (step=08, item=amb-noabout)" in problem_line
    assert "amb-ok" in report.stdout


def test_an_item_without_an_id_exits_2(spec: Path) -> None:
    _with_items(spec, {"description": "x", "about": ["fr-does-not-exist"]})
    report = _run(spec)
    assert report.exit_code == 2 and "missing_id" in report.stderr_lines[0] and "item=(no id)" in report.stderr_lines[0]


def test_an_unreadable_file_exits_2_with_one_line(spec: Path) -> None:
    (spec / "04_fr_list.json").unlink()
    (spec / "04_fr_list.json").mkdir()
    report = _run(spec)
    assert (report.stdout, report.exit_code) == ("", 2) and len(report.stderr_lines) == 1


def test_a_missing_spec_folder_exits_2(tmp_path: Path) -> None:
    report = run(str(tmp_path / "nope"), repo_root=str(TOOLKIT))
    assert report.exit_code == 2 and "missing_spec_dir" in report.stderr_lines[0]


def test_load_items_returns_typed_problems(spec: Path) -> None:
    _with_items(spec, {"id": "amb-noabout", "description": "na"})
    items, problems = load_items(str(spec))
    assert [i.id for i in items] == [] and problems == [
        ItemProblem(str(spec / FIXTURES_FILE), "08", "amb-noabout", "item has neither about nor a valid severity")
    ]


def test_the_summary_keeps_its_warnings_as_a_tuple() -> None:
    from specdev_tools.analysis.upstream_backlog import summarise

    assert summarise([], warnings=[{"code": "W613", "target": "a:b"}]).warnings == ({"code": "W613", "target": "a:b"},)
    assert summarise([]).warnings == ()
