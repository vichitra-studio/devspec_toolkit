"""The 1.2.0 changelog and the migration registry agree, and every script a disposition row names is registered (WI-M10-14b).

Which property lives where:

* ``test_migration_dispositions.py`` (WI-M10-05): the checklist and the map agree row for row, every removed row has a
  disposition and a script, the map's counts. It lets a row name a script of a bundle that did not exist yet.
* ``test_changelog_scripts.py`` (WI-M10-14a): the E884 rule itself, on temp changelogs, and over every real changelog.
* this file: the three-way agreement of the registry, the map and ``changelog/unreleased.yaml`` (the 1.2.0 changelog in
  waiting, P1), now that every script exists: each registered 1.2.0 script has exactly one entry, each entry names a
  registered script, each script a map row names is registered and has an entry.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from specdev_tools.core.changelog_parser import load_format, load_version
from specdev_tools.migration.maps import shape_map
from specdev_tools.migration.registry import discover_scripts

ROOT = Path(__file__).resolve().parents[3]
CHANGELOG = ROOT / "changelog"
CHECKLIST = {row["id"]: row for row in json.loads((ROOT / "tools" / "schema_changes.json").read_text(encoding="utf-8"))["rows"]}
TARGET = "1.2.0"


def _scripts_of_the_release() -> dict[str, object]:
    """The scripts that migrate to 1.2.0 (the released ``p3_strip_status_ref`` of 1.1.0 has no entry in this changelog)."""
    return {script.id: script for script in discover_scripts() if script.version == TARGET}


def _entries() -> list:
    """Every ``migration`` block of ``unreleased.yaml`` that names a script."""
    return [change.migration for change in load_version(CHANGELOG, "unreleased").changes if change.migration is not None and change.migration.script]


def _map_rows() -> list[dict]:
    return shape_map()["rows"]


def test_every_registered_script_has_exactly_one_entry_and_every_entry_names_a_registered_script():
    registered = set(_scripts_of_the_release())
    assert len(registered) >= 24, "the registry lost scripts"
    named = Counter(entry.script for entry in _entries())
    assert sorted(registered - set(named)) == [], "registered scripts with no changelog entry"
    assert sorted(set(named) - registered) == [], "changelog entries that name no registered 1.2.0 script"
    assert sorted(script for script, count in named.items() if count > 1) == [], "a script with two entries"


def test_every_auto_entry_names_a_script():
    """Over ``unreleased.yaml``: an ``auto`` entry that migrates host data (kind mechanical or judgement) names a script and a known kind; a ``none`` entry is toolkit-internal."""
    kinds = set(load_format(CHANGELOG).migration_kinds)
    assert {"mechanical", "judgement", "none"} <= kinds
    for change in load_version(CHANGELOG, "unreleased").changes:
        migration = change.migration
        if migration is None or migration.action != "auto":
            continue
        assert migration.kind in kinds, f"{change.description[:60]!r}: kind {migration.kind!r}"
        if migration.kind in ("mechanical", "judgement"):
            assert migration.script, f"{change.description[:60]!r}: an auto entry with kind {migration.kind} names no script"
        else:
            assert not migration.script


def test_every_row_of_the_checklist_has_a_migration_entry_in_the_1_2_0_changelog():
    """A checklist row the migration acts on (a map row with a script) leads, through its script, to a changelog entry that says what the script does."""
    entries = {entry.script: entry for entry in _entries()}
    rows = _map_rows()
    assert {row["id"] for row in rows} == set(CHECKLIST)
    acted_on = [row for row in rows if row.get("script")]
    assert len(acted_on) > 100
    for row in acted_on:
        assert row["script"] in entries, f"{row['id']} ({CHECKLIST[row['id']]['path']}): its script {row['script']} has no changelog entry"
        assert entries[row["script"]].kind in ("mechanical", "judgement")


def test_every_removed_field_has_a_drop_row():
    """A removed field is taken out, converted or listed by a script that is registered, and the entry of that script exists.

    The row-by-row disposition is ``test_migration_dispositions``'s; here the script of every removed row must be one the registry
    has now (that test lets a row name a script of a later bundle).
    """
    registered = set(_scripts_of_the_release())
    entries = {entry.script for entry in _entries()}
    removed = [row for row in _map_rows() if CHECKLIST[row["id"]]["change"] == "remove" and row["disposition"] != "none"]
    assert len(removed) > 100
    for row in removed:
        assert row["script"] in registered, f"{row['id']}: script {row['script']} is not registered"
        assert row["script"] in entries, f"{row['id']}: script {row['script']} has no changelog entry"


def test_every_script_a_row_names_is_registered():
    """Every row that names a script names a registered one, and a row that names none is a ``none`` row."""
    registered = set(_scripts_of_the_release())
    for row in _map_rows():
        if row.get("script") is None:
            assert row["disposition"] == "none", row["id"]
        else:
            assert row["script"] in registered, f"{row['id']}: {row['script']}"
