"""Every row of the schema-change checklist has exactly one disposition in ``migration/maps/v1_2_0.yaml`` (WI-M10-05 item 1).

The checklist (``tools/schema_changes.json``, generated) is the authority for which field 1.2.0 removed, changed or added; the
map says what the migration does with it.  A row the map lacks, or a map row the checklist does not know, fails here.
"""

from __future__ import annotations

import importlib
import json
import re
from collections import Counter
from pathlib import Path

from specdev_tools.migration.maps import shape_map

ROOT = Path(__file__).resolve().parents[3]
CHECKLIST = {row["id"]: row for row in json.loads((ROOT / "tools" / "schema_changes.json").read_text(encoding="utf-8"))["rows"]}
CAPTURE_SCHEMA = json.loads((ROOT / "schema" / "infra" / "migration_capture.schema.json").read_text(encoding="utf-8"))
DISPOSITIONS = {"convert", "remove", "copy-dropped", "capture-then-remove", "worklist", "none"}
KEYS = {"id", "path", "change", "disposition", "script", "captured_in", "closed_plans", "convert", "note"}
OTHER_BUNDLES = re.compile(r"^p[245]_[a-z0-9_]+$")


def _rows() -> dict[str, dict]:
    rows = shape_map()["rows"]
    assert len({row["id"] for row in rows}) == len(rows), "a checklist row appears twice in the map"
    return {row["id"]: row for row in rows}


def test_every_checklist_row_has_a_disposition():
    rows = _rows()
    assert sorted(set(CHECKLIST) - set(rows)) == [], "checklist rows with no migration disposition"
    assert sorted(set(rows) - set(CHECKLIST)) == [], "map rows the checklist does not know"
    for row_id, row in rows.items():
        assert row["disposition"] in DISPOSITIONS, row_id
        assert (row["path"], row["change"]) == (CHECKLIST[row_id]["path"], CHECKLIST[row_id]["change"]), f"{row_id}: the map copied another path or change"
        assert set(row) <= KEYS, f"{row_id}: unknown keys {sorted(set(row) - KEYS)}"


def test_every_hand_off_row_has_a_map_row():
    """A row that names a replacement (``replaced_by``) is a hand-off: the map row says who converts it, unless it is a schema definition."""
    rows = _rows()
    hand_offs = [r for r in CHECKLIST.values() if r["replaced_by"] and r["change"] == "remove" and not r["path"].startswith("$defs")]
    assert len(hand_offs) > 25
    for hand_off in hand_offs:
        row = rows[hand_off["id"]]
        assert row["disposition"] != "none" and row.get("script"), f"{hand_off['id']} ({hand_off['path']}): a hand-off without a script"


def test_every_remove_row_has_a_drop_or_rename_disposition():
    """Every removed field is converted, dropped, copy-dropped, captured then removed, or sent to the worklist; only a schema definition (``$defs`` or the shared step base, whose fields have a row per step) has none."""
    rows = _rows()
    removed = [r for r in CHECKLIST.values() if r["change"] == "remove"]
    assert removed and {r["id"] for r in removed} <= set(rows), "a removed checklist row the map lacks"
    for entry in removed:
        row = rows[entry["id"]]
        if row["disposition"] == "none":
            assert entry["path"].startswith("$defs") or entry["id"].startswith("SC-core-"), f"{entry['id']} ({entry['path']}): a removed field with no disposition"
        else:
            assert row.get("script"), entry["id"]


def test_the_scripts_a_row_names_exist_or_belong_to_a_later_bundle():
    for row in _rows().values():
        script = row.get("script")
        if script is None:
            assert row["disposition"] == "none", row["id"]
        elif script.startswith("p3_") or script in {"p2_id_mint", "p2_anchor_rows"}:
            importlib.import_module(f"specdev_tools.migration.scripts.v1_2_0.{script}")
        else:
            assert OTHER_BUNDLES.match(script), f"{row['id']}: {script}"


def test_a_captured_field_names_a_section_of_the_capture():
    sections = set(CAPTURE_SCHEMA["properties"])
    for row in _rows().values():
        if row["disposition"] == "capture-then-remove":
            assert row.get("captured_in", "").split(".")[0] in sections, row["id"]


def test_the_disposition_counts_by_script():
    """The shape of the map, printed once: how many rows each script applies."""
    counts = Counter((row["disposition"], row.get("script")) for row in _rows().values())
    assert counts[("none", None)] > 100
    assert counts[("remove", "p3_remove")] + counts[("capture-then-remove", "p3_remove")] > 80
    assert counts[("copy-dropped", "p3_copies")] == 7


def test_the_14_milestone_status_is_left_to_the_legacy_close():
    """The roadmap `status` stays in phase 3: closed_milestones reads it from the live tree, a removal would reopen a closed plan on a rerun."""
    assert _rows()["SC-14-09"]["script"] == "p5_legacy_close"
