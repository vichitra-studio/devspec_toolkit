"""``triage._finish``: the stamp is rewritten FIRST and the migration files are deleted after (D11 of round 1).

``validate_migration`` promises that a step that fails stops the run with nothing written.  With the delete first, a stamp
write that failed left the capture and the worklist gone and ``migration_status`` still ``in_progress``.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import yaml

from specdev_tools.migration import triage
from specdev_tools.core.constants import STATUS_IN_PROGRESS
from specdev_tools.migration.context import CAPTURE_FILE
from specdev_tools.migration.worklist import WORKLIST_FILE


def _spec(tmp_path: Path) -> tuple[str, dict]:
    spec = tmp_path / "spec"
    (spec / "extras" / "migration").mkdir(parents=True)
    (spec / CAPTURE_FILE).write_text("{}\n", encoding="utf-8")
    (spec / WORKLIST_FILE).write_text("{}\n", encoding="utf-8")
    stamp = {"toolkit_version": "1.1.1", "created_at": "c", "migration_status": STATUS_IN_PROGRESS}
    (spec / "specdev_version").write_text(yaml.dump(stamp), encoding="utf-8")
    return str(spec), stamp


def test_a_failed_stamp_write_leaves_the_capture_and_the_worklist_in_place(tmp_path):
    spec, stamp = _spec(tmp_path)
    report = triage.ValidateReport()
    with patch.object(triage, "stamp_specdev_version", return_value="the disk is full"):
        triage._finish(spec, "1.2.0", stamp, report, False)
    assert report.refused == "the disk is full"
    assert not report.stamp_finished and report.deleted == []
    assert os.path.isfile(os.path.join(spec, CAPTURE_FILE)) and os.path.isfile(os.path.join(spec, WORKLIST_FILE))
    assert yaml.safe_load(Path(spec, "specdev_version").read_text(encoding="utf-8"))["migration_status"] == STATUS_IN_PROGRESS


def test_a_good_stamp_write_is_followed_by_the_delete(tmp_path):
    spec, stamp = _spec(tmp_path)
    report = triage.ValidateReport()
    triage._finish(spec, "1.2.0", stamp, report, False)
    assert report.refused is None and report.stamp_finished
    assert sorted(report.deleted) == sorted([CAPTURE_FILE, WORKLIST_FILE])
    assert not os.path.exists(os.path.join(spec, "extras", "migration"))
    assert "migration_status" not in yaml.safe_load(Path(spec, "specdev_version").read_text(encoding="utf-8"))
