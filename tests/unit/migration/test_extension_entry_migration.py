"""A 1.1.1 manifest with extension entries, migrated to 1.2.0 (DEVSPEC-245, piece B, decision 4).

1.2.0 requires ``justified_by`` on an entry (the ids of the upstream nodes that make the extension necessary).  A 1.1.1
entry has none and which nodes it means is a person's judgement: the migration invents no id.  The entry is reported by
the step's schema check until the field is written, and the prose-id proposer lists the ids its text names with the
field that takes them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.migration import proposers
from specdev_tools.migration.maps import shape_map
from specdev_tools.migration.proposers import prose_ids
from specdev_tools.validation.validate import validate_file

from specdev_tools.migration import runner
from specdev_tools.migration.runner import STATUS_OK

from ._proposer_support import copy_gold, tree_of
from ._support import REAL_ROOT, git, items, make_host, make_toolkit, migrate, read

MANIFEST = "13_extension_manifest.json"
LABEL = {"id": "cn:core:governance_label:mandatory", "kind": "governance_label"}
CHECKLIST = {row["id"]: row for row in json.loads((REAL_ROOT / "tools" / "schema_changes.json").read_text(encoding="utf-8"))["rows"]}


def _entry(entry_id: str, justification: str) -> dict:
    """A manifest entry as a 1.1.1 host wrote it: every field 1.1.1 required, no ``justified_by``."""
    return {
        "extension_id": entry_id,
        "title": "Barcode Labels",
        "area_of_concern": "Hardware",
        "justification": justification,
        "required_schema_sections": ["label_formats", "printers", "validation_rules"],
        "schema_design_guidelines": "Reuse vc:core:atoms#kebabId for label ids. Include validation_rules that a test can verify.",
        "governance_label_ref": dict(LABEL),
    }


def _declare(*entries: dict):
    def change(manifest: dict) -> None:
        manifest["extension_decision"] = {"status": "extensions-required", "rationale": "The desk prints a label for every tool; no core step describes a print layout."}
        manifest["extensions"] = [dict(entry) for entry in entries]
        manifest["canonical_refs_used"] = [dict(LABEL)]

    return change


def _missing_field_errors(manifest: Path, spec_root: Path | None = None) -> list[str]:
    """The schema errors (E520) of *manifest* that name ``justified_by``, as text."""
    errors = validate_file(
        str(REAL_ROOT), str(manifest), include_quality_lint=False, include_canonical_integrity=False, spec_root=None if spec_root is None else str(spec_root),
    )
    return [error.render() for error in errors if error.code == "E520" and "justified_by" in error.render()]


def test_the_checklist_and_the_map_have_a_row_for_each_new_field_of_an_entry() -> None:
    added = {row["path"]: row for row in CHECKLIST.values() if row["step"] == "13" and row["path"].startswith("extensions[]")}
    assert set(added) == {"extensions[].justified_by", "extensions[].lifecycle"}
    assert {row["change"] for row in added.values()} == {"add"}
    in_map = {row["id"]: row for row in shape_map()["rows"]}
    for row in added.values():
        assert in_map[row["id"]]["path"] == row["path"] and in_map[row["id"]]["disposition"] == "none" and "script" not in in_map[row["id"]]


WITH_ID = _entry("ext-01-barcode-labels", "The desk app prints a barcode label for every tool; fr-checkout-tool needs the label format and no core step describes a print layout.")
WITHOUT_ID = _entry("ext-02-shelf-map", "The store room is mapped shelf by shelf; no core step describes a floor plan.")


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    host, toolkit, report = migrate(tmp_path_factory.mktemp("entries"), (MANIFEST, _declare(WITH_ID, WITHOUT_ID)))
    return host, toolkit, report


def test_the_migration_keeps_an_entry_as_it_was_and_invents_no_justified_by(migrated) -> None:
    host, _toolkit, _report = migrated
    manifest = read(host, MANIFEST)
    assert manifest["extensions"] == [WITH_ID, WITHOUT_ID]
    assert all("justified_by" not in entry for entry in manifest["extensions"])


def test_each_migrated_entry_is_one_schema_error_until_a_person_names_its_nodes(migrated, tmp_path) -> None:
    host, _toolkit, _report = migrated
    errors = _missing_field_errors(host / "spec" / MANIFEST, host / "spec")
    assert len(errors) == 2 and all("required" in error for error in errors)
    assert errors[0] != errors[1]  # one per entry: each names its own place
    manifest = read(host, MANIFEST)
    manifest["extensions"][0]["justified_by"] = ["fr-checkout-tool"]
    fixed = tmp_path / "spec"
    fixed.mkdir()
    (fixed / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    assert len(_missing_field_errors(fixed / MANIFEST)) == 1  # the entry a person completed is no error any more
    manifest["extensions"][1]["justified_by"] = ["desk-app"]
    (fixed / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    assert _missing_field_errors(fixed / MANIFEST) == []


def test_apply_writes_no_worklist_item_about_an_entry(migrated) -> None:
    host, _toolkit, _report = migrated
    assert [item for item in items(host) if item["about"] in (WITH_ID["extension_id"], WITHOUT_ID["extension_id"])] == []


def test_the_prose_id_proposer_lists_the_ids_an_entry_names_under_step_13(migrated) -> None:
    host, _toolkit, _report = migrated
    outcome = proposers.propose(host / "spec", kind=proposers.KIND_PROSE_IDS, toolkit_root=REAL_ROOT, git_root=host, dry_run=False)
    assert outcome.added >= 1
    about = {item["about"]: item for item in items(host, "prose-ids")}
    assert WITHOUT_ID["extension_id"] not in about  # its text names no id
    item = about[WITH_ID["extension_id"]]
    assert item["step"] == "13" and item["resolved"] is False
    assert "fr-checkout-tool (resolved: fr-checkout-tool)" in item["evidence"]
    assert "justified_by" in item["proposal"]


def _gold_with_entry(tmp_path: Path, justification: str, **more) -> Path:
    """The gold host (a migrated tree with no step-13 file) with a manifest that declares one entry."""
    host = copy_gold(tmp_path)
    manifest = {"$schema": "vc:13-extension-manifest", "id": "extension-manifest-packets", "owner": "system", "created_at": "2026-03-02T09:00:00Z", "extensions": []}
    _declare({**_entry("ext-01-barcode-labels", justification), **more})(manifest)
    (host / "spec" / MANIFEST).write_text(json.dumps(manifest, indent=4) + "\n", encoding="utf-8")
    return host


def _mentions(host: Path, about: str) -> dict[str, dict]:
    result = prose_ids.propose(tree_of(host))
    proposal = next(found for found in result.proposals if found.data["about"] == about)
    return {mention["token"]: mention for mention in proposal.data["mentions"]}


def test_an_id_of_a_kind_justified_by_takes_is_proposed_as_that_link_and_another_kind_is_not(tmp_path) -> None:
    host = _gold_with_entry(tmp_path, "The packet desk needs fr-borrow-packet and must never break inv-six-packet-limit; no core step describes a label.")
    mentions = _mentions(host, "ext-01-barcode-labels")
    assert mentions["fr-borrow-packet"]["class"] == prose_ids.RESOLVED
    assert "the declared field justified_by of extension accepts the kind fr" in mentions["fr-borrow-packet"]["proposal"]
    assert mentions["inv-six-packet-limit"]["class"] == prose_ids.RESOLVED
    assert "justified_by" not in mentions["inv-six-packet-limit"]["proposal"]


def test_an_id_the_entry_already_names_in_justified_by_is_proposed_as_a_reword(tmp_path) -> None:
    host = _gold_with_entry(tmp_path, "The packet desk needs fr-borrow-packet; no core step describes a label.", justified_by=["fr-borrow-packet"])
    proposal = _mentions(host, "ext-01-barcode-labels")["fr-borrow-packet"]["proposal"]
    assert "already links fr-borrow-packet through justified_by: reword out" in proposal


# --- a data file of the extensions folder (decision 8: its ambiguities are read; the 1.1.1 file is the host's own) ----------

LEGACY_ITEM = {"id": "amb-label-size", "description": "Which label size?", "severity": "medium", "status": "open", "impact": ["spec/04_functional_requirements.json"]}
DATA_FILES = {
    "no-json": "{ not json",
    "ambiguities-of-the-hosts-own-shape": json.dumps({"label_formats": [], "ambiguities": "none yet"}),
    "an-entry-that-is-no-object": json.dumps({"label_formats": [], "ambiguities": ["amb-label-size"]}),
    "a-1.1.1-item": json.dumps({"label_formats": [], "ambiguities": [LEGACY_ITEM]}, indent=2),
}


@pytest.mark.parametrize("body", DATA_FILES.values(), ids=DATA_FILES.keys())
def test_a_data_file_of_the_extensions_folder_does_not_stop_the_migration_and_stays_as_it_was(tmp_path, body) -> None:
    """1.1.1 never read such a file: whatever it holds, the scripts that read the ambiguity items of the anchor and the plans go on."""
    toolkit, host = make_toolkit(tmp_path), make_host(tmp_path)
    place = host / "spec" / "extensions" / "ext_01_barcode_labels.json"
    place.parent.mkdir()
    place.write_text(body, encoding="utf-8")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "an extension data file")
    report = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host)
    assert report.status == STATUS_OK, report.errors
    assert place.read_text(encoding="utf-8") == body
