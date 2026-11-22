"""``p3_ordering``: the ``implied`` report on the 09 milestone pairs (WI-M10-05 item 1, CD-17 / CD-17m)."""

from __future__ import annotations

from .test_convert_remove import items, migrate, read


def _pairs(report) -> dict[str, str]:
    """``{"later after earlier": "true"|"false"}`` from the report lines of ``p3_ordering``."""
    lines = [line for line in report.to_json()["residue"] if line.startswith("implied: ")]
    return {line.split("  ", 1)[1]: line.split()[1] for line in lines}


def test_the_mini_host_pairs_are_reported_and_use_the_renamed_ids(tmp_path):
    host, _, report = migrate(tmp_path)
    assert _pairs(report) == {
        "milestone-reservations after milestone-catalog-basics": "false",
        "milestone-late-fees after milestone-reservations": "false",
    }, "the 09 id ms-late-fees reaches this script through the capture's renames"


def test_a_pair_the_stored_links_do_not_imply_is_an_item_for_the_step_that_authors_the_link(tmp_path):
    host, _, _ = migrate(tmp_path)
    found = {i["about"]: i for i in items(host, "milestone-order")}
    assert set(found) == {"milestone-reservations-after-milestone-catalog-basics", "milestone-late-fees-after-milestone-reservations"}
    assert {i["step"] for i in found.values()} == {"04"}, "FR pairs go to step 04"
    assert all(i["audience"] == "agent" and "depends_on" in i["proposal"] for i in found.values())


def test_a_pair_the_fr_links_imply_is_reported_true_and_has_no_item(tmp_path):
    def link(data: dict) -> None:
        reserve = next(f for f in data["functional_requirements"] if f["fr_id"] == "fr-reserve-tool")
        reserve["depends_on"] = ["fr-catalog-search"]

    host, _, report = migrate(tmp_path, ("04_fr_list.json", link))
    assert _pairs(report)["milestone-reservations after milestone-catalog-basics"] == "true"
    assert "milestone-reservations-after-milestone-catalog-basics" not in {i["about"] for i in items(host, "milestone-order")}


def test_a_confirmed_schedules_wins_over_the_proposal(tmp_path):
    def confirm(data: dict) -> None:
        reservations = next(m for m in data["milestones"] if m["milestone_id"] == "milestone-reservations")
        reservations["schedules"] = ["fr-reserve-tool"]

    def link(data: dict) -> None:
        next(f for f in data["functional_requirements"] if f["fr_id"] == "fr-reserve-tool")["depends_on"] = ["fr-catalog-search"]

    host, _, report = migrate(tmp_path, ("09_impl_plan.json", confirm), ("04_fr_list.json", link))
    assert _pairs(report)["milestone-reservations after milestone-catalog-basics"] == "true"
    assert "milestone-reservations" not in {i["about"] for i in items(host, "schedules")}, "a milestone that schedules something needs no schedules item"


def test_the_script_writes_no_spec_file_but_the_worklist(tmp_path):
    from specdev_tools.migration import runner
    from specdev_tools.migration.registry import script_from_module
    from specdev_tools.migration.scripts.v1_2_0 import p1_capture, p2_id_collisions, p3_ordering

    from ._support import make_host, make_toolkit, tree_digest

    toolkit, host = make_toolkit(tmp_path), make_host(tmp_path)
    chain = [script_from_module(m, "1.2.0") for m in (p1_capture, p2_id_collisions, p3_ordering)]
    before = tree_digest(host / "spec")
    runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=[chain[0], chain[1]])
    middle = tree_digest(host / "spec")
    runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=[chain[0], chain[1], chain[2]])
    after = tree_digest(host / "spec")
    assert [rel for rel in after if middle.get(rel) != after[rel] and not rel.startswith(("extras/migration/", "specdev_version"))] == []
    assert before != middle


def test_pairs_come_from_the_capture_so_a_removed_depends_on_still_reports(tmp_path):
    host, _, _ = migrate(tmp_path)
    assert "depends_on" not in read(host, "09_impl_plan.json")["milestones"][1]
    assert read(host, "extras/migration/capture.json")["milestone_ordering"]["pairs"], "the captured pairs outlive the removed field"
