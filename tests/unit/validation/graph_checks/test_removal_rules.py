"""The removal rules of step 14 (E341, E342): the fixture and the criterion agree, and a live removal names an id that is gone."""
from __future__ import annotations

from pathlib import Path

from specdev_tools.core.errors import SpecError
from specdev_tools.trace.lockfile import read_lock
from specdev_tools.validation.graph_checks import run_graph_checks
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from unit.verify._support import example_host, graph_of

from unit.proof._closed import FR, add_milestone, closed_example, criterion, with_removal
from unit.proof._support import add_fixture

GONE, ALSO_GONE = "fr-retired-feature", "fr-retired-extra"


def _findings(host: Path) -> list[SpecError]:
    graph = graph_of(host)
    return run_graph_checks(GraphCheckContext.from_graph(graph, read_lock(str(host / "spec"))), "merge", only={"E341", "E342"})


def _summary(findings: list[SpecError]) -> list[tuple[str, str | None, str | None]]:
    return [(error.code, error.node_id, error.target) for error in findings]


def test_matching_removal_criterion_and_fixture_is_clean(tmp_path: Path) -> None:
    host = example_host(tmp_path)
    with_removal(host, removes=[GONE], done=False)
    assert _findings(host) == []


def test_removal_fixture_criterion_mismatch_is_e341(tmp_path: Path) -> None:
    host = example_host(tmp_path)
    with_removal(host, removes=[GONE], done=False, fixture_removes=[GONE, ALSO_GONE])
    findings = _findings(host)
    assert _summary(findings) == [("E341", "tc-retire-reset", "verified_by->fix-reset-gone"), ("E341", "fix-reset-gone", None)]
    assert findings[0].owner == "step:14" and findings[1].owner == "step:14"
    assert f"removes {GONE} but its removal fixture fix-reset-gone removes {ALSO_GONE}, {GONE}" in findings[0].message


def test_removal_fixture_not_covered_by_a_criterion_is_e341(tmp_path: Path) -> None:
    host = example_host(tmp_path)
    with_removal(host, removes=[GONE], done=False, fixture_removes=[GONE, ALSO_GONE])
    add_milestone(host, "ms-second", [criterion("tc-retire-extra", removes=[ALSO_GONE])], done=False)
    [uncovered] = [error for error in _findings(host) if error.node_id == "fix-reset-gone"]
    assert uncovered.message.startswith(f"removal fixture fix-reset-gone removes {ALSO_GONE} but no task criterion that lists it in verified_by removes it")


def test_removal_fixture_no_criterion_lists_is_e341(tmp_path: Path) -> None:
    host = example_host(tmp_path)
    with_removal(host, removes=[GONE], done=False)
    add_milestone(host, "ms-other", [criterion("tc-other", removes=[GONE])], done=False)
    add_fixture(host, fixture_id="fix-orphan-removal", removes=[ALSO_GONE])
    assert [(error.code, error.node_id) for error in _findings(host)] == [("E341", "fix-orphan-removal")]


def test_live_removes_of_a_present_id_is_e342(tmp_path: Path) -> None:
    host = example_host(tmp_path)
    with_removal(host, removes=[FR], done=False)
    findings = _findings(host)
    assert _summary(findings) == [("E342", "tc-retire-reset", f"removes->{FR}"), ("E342", "fix-reset-gone", f"removes->{FR}")]
    assert findings[0].owner == "step:14" and f"removes {FR}, which is still in the spec" in findings[0].message


def test_historical_removes_is_never_checked(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    with_removal(host, removes=[FR], done=True)
    assert _findings(host) == []


def test_a_removal_fixture_named_by_a_closed_and_an_open_criterion_is_not_closed_work(tmp_path: Path) -> None:
    """The fixture is frozen only when every criterion that lists it is closed: the open one keeps it live (E342 for a removed id still present)."""
    host = closed_example(tmp_path)
    with_removal(host, removes=[FR], done=True)
    assert _findings(host) == []
    add_milestone(host, "ms-again", [criterion("tc-retire-again", removes=[FR], verified_by=["fix-reset-gone"])], done=False)
    assert [(error.code, error.node_id) for error in _findings(host)] == [("E342", "tc-retire-again"), ("E342", "fix-reset-gone")]
