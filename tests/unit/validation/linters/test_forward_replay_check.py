import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from specdev_tools.validation.forward_replay_check import check_forward_replay
from specdev_tools.context.seed_indexer import build_seed_index
from specdev_tools.core.config import reset_config
from specdev_tools.core.errors import PROMOTABLE_PAIRS, make_error, render_errors
from specdev_tools.validation.validate import _apply_we_promotion


class ForwardReplayCheckTests(unittest.TestCase):

    def test_git_diff_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}), encoding="utf-8"
            )
            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=([], "fatal: bad revision"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("unable_to_compute_diff" in e for e in render_errors(errs)))

    def test_git_diff_failure_can_be_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}), encoding="utf-8"
            )
            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=([], "fatal: bad revision"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main", diff_error_mode="ignore")
            self.assertEqual([], errs)

    def test_invalid_diff_error_mode_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}), encoding="utf-8"
            )
            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=([], "fatal: bad revision"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main", diff_error_mode="warn")
            self.assertTrue(any("invalid_diff_error_mode" in e for e in render_errors(errs)))

    def test_complete_replay_has_no_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            fixture_dir = (
                Path(__file__).resolve().parents[3]
                / "fixtures"
                / "dependency_order"
            )
            complete_changes = (
                fixture_dir / "replay_complete_changed_files.txt"
            ).read_text(encoding="utf-8").splitlines()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"]}), encoding="utf-8"
            )
            (root / "spec" / "00_charter.json").write_text("{}", encoding="utf-8")
            (root / "spec" / "01_capabilities.json").write_text("{}", encoding="utf-8")
            (root / "spec" / "02_system_sketch.json").write_text("{}", encoding="utf-8")
            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(complete_changes, None),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertFalse(any("E550" in e for e in render_errors(errs)))


    def test_not_git_repository_reason_is_compact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00"]}), encoding="utf-8"
            )
            noisy = "warning: Not a git repository.\n" + ("usage: git diff\n" * 50)
            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=([], "not-a-git-repository"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("reason=not-a-git-repository" in e for e in render_errors(errs)))

    def test_semantic_coverage_regression_detected_when_id_dropped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(json.dumps({"steps": ["00", "01"]}), encoding="utf-8")
            (root / "spec" / "00_charter.json").write_text('{}', encoding="utf-8")
            (root / "spec" / "01_capabilities.json").write_text('{"id": "foo-123"}', encoding="utf-8")
            
            with patch("specdev_tools.validation.forward_replay_check._changed_files", return_value=(["spec/00_charter.json", "spec/01_capabilities.json"], None)):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = '{"id": "dropped-id"}'
                    errs = check_forward_replay(str(root), base_ref="origin/main")
                    
            self.assertTrue(any("SEMANTIC_COVERAGE_REGRESSION" in e and "dropped-id" in e for e in render_errors(errs)))

    def test_no_regression_when_ids_preserved_across_replay(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(json.dumps({"steps": ["00", "01"]}), encoding="utf-8")
            (root / "spec" / "00_charter.json").write_text('{"id": "kept-id"}', encoding="utf-8")
            (root / "spec" / "01_capabilities.json").write_text('{"id": "kept-id", "new_id": "added-id"}', encoding="utf-8")

            with patch("specdev_tools.validation.forward_replay_check._changed_files", return_value=(["spec/00_charter.json", "spec/01_capabilities.json"], None)):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = '{"id": "kept-id"}'
                    errs = check_forward_replay(str(root), base_ref="origin/main")
                    
            self.assertFalse(any("SEMANTIC_COVERAGE" in e for e in render_errors(errs)))

    def test_graceful_failure_when_git_show_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(json.dumps({"steps": ["00", "01"]}), encoding="utf-8")
            (root / "spec" / "00_charter.json").write_text('{}', encoding="utf-8")
            (root / "spec" / "01_capabilities.json").write_text('{}', encoding="utf-8")
            
            with patch("specdev_tools.validation.forward_replay_check._changed_files", return_value=(["spec/00_charter.json", "spec/01_capabilities.json"], None)):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 128
                    mock_run.return_value.stdout = ''
                    mock_run.return_value.stderr = 'fatal: bad revision'
                    errs = check_forward_replay(str(root), base_ref="origin/main")
                    
            self.assertTrue(any("W550 SEMANTIC_COVERAGE_SKIP" in e for e in render_errors(errs)))





    def test_id_stability_removal_warning_on_dropped_id(self):
        """W598 ID_STABILITY_REMOVAL fires for each ID removed between base and current."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["04"]}), encoding="utf-8"
            )
            # Current version of 04 is missing fr-removed that was in the base
            (root / "spec" / "04_frs.json").write_text(
                '{"id": "fr-kept"}', encoding="utf-8"
            )

            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(["spec/04_frs.json"], None),
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = '{"id": "fr-kept", "extra_ref": "fr-removed"}'
                    mock_run.return_value.stderr = ""
                    errs = check_forward_replay(str(root), base_ref="origin/main")

            rendered = render_errors(errs)
            stability_warnings = [e for e in rendered if "W598" in e and "ID_STABILITY_REMOVAL" in e]
            self.assertTrue(
                len(stability_warnings) > 0,
                f"Expected W598 ID_STABILITY_REMOVAL warning, got: {rendered}",
            )
            self.assertTrue(
                any("fr-removed" in e for e in stability_warnings),
                f"W598 should name the removed ID, got: {stability_warnings}",
            )

    def test_id_stability_no_warning_when_ids_preserved(self):
        """W598 does not fire when no IDs are removed between base and current."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["04"]}), encoding="utf-8"
            )
            (root / "spec" / "04_frs.json").write_text(
                '{"id": "fr-kept", "extra_ref": "fr-new"}', encoding="utf-8"
            )

            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(["spec/04_frs.json"], None),
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = '{"id": "fr-kept"}'
                    mock_run.return_value.stderr = ""
                    errs = check_forward_replay(str(root), base_ref="origin/main")

            rendered = render_errors(errs)
            stability_warnings = [e for e in rendered if "W598" in e]
            self.assertEqual(
                stability_warnings, [],
                f"Expected no W598 when no IDs removed, got: {stability_warnings}",
            )

    def test_traceability_gaps_surfaced_as_warnings(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(json.dumps({"steps": ["00"]}), encoding="utf-8")
            
            with patch("specdev_tools.validation.forward_replay_check._changed_files", return_value=([], None)):
                with patch("specdev_tools.validation.forward_replay_check.check_traceability_closure", return_value=[make_error("E560", "TRACEABILITY_GAP fake gap")]):
                    errs = check_forward_replay(str(root), base_ref="origin/main")
                    
            self.assertTrue(any("W560 TRACEABILITY_GAP fake gap" in e for e in render_errors(errs)))
            self.assertFalse(any("E560" in e for e in render_errors(errs)))


_TOOLKIT_ROOT = Path(__file__).resolve().parents[4]
_CHANGED = "specdev_tools.validation.forward_replay_check._changed_files"


def _replay_root(tmp_path: Path, steps: list[str], files: dict[str, str]) -> Path:
    (tmp_path / "tools").mkdir()
    (tmp_path / "spec").mkdir()
    (tmp_path / "tools" / "step_order.json").write_text(json.dumps({"steps": steps}), encoding="utf-8")
    for name, text in files.items():
        (tmp_path / "spec" / name).write_text(text, encoding="utf-8")
    return tmp_path


def test_forward_replay_no_longer_emits_e550_w595(tmp_path, monkeypatch):
    """An unknown step in the diff, a missing downstream step and new upstream text give no E550 and no W595; a failed diff still gives E550."""
    monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
    monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
    reset_config()
    root = _replay_root(
        tmp_path,
        ["00", "01", "02"],
        {
            "00_charter.json": json.dumps({"description": "brand new upstream wording about payments gateways"}),
            "01_capabilities.json": "{}",
            "02_system_sketch.json": "{}",
        },
    )
    changed = ["spec/00_charter.json", "spec/99_future.json"]
    with patch(_CHANGED, return_value=(changed, None)):
        errs = check_forward_replay(str(root), base_ref="origin/main")
    codes = {e.code for e in errs}
    assert "E550" not in codes and "W595" not in codes
    with patch(_CHANGED, return_value=([], "bad-revision")):
        failed = check_forward_replay(str(root), base_ref="origin/main")
    assert [e.code for e in failed] == ["E550"]


def test_w550_still_promotable_to_e550_in_strict_mode(tmp_path, monkeypatch):
    """W550 (base file unreadable) stays paired with E550: promotion turns it into E550."""
    assert PROMOTABLE_PAIRS["W550"] == "E550"
    root = _replay_root(tmp_path, ["00"], {"00_charter.json": "{}"})
    with patch(_CHANGED, return_value=(["spec/00_charter.json"], None)):
        with patch("subprocess.run") as run:
            run.return_value.returncode = 128
            run.return_value.stdout = ""
            run.return_value.stderr = "fatal: bad revision"
            errs = check_forward_replay(str(root), base_ref="origin/main")
    skipped = [e for e in errs if e.code == "W550"]
    assert len(skipped) == 1
    monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "W550")
    reset_config()
    try:
        assert [e.code for e in _apply_we_promotion(skipped)] == ["E550"]
    finally:
        monkeypatch.delenv("SPECDEV_PROMOTE_CODES")
        reset_config()


def test_no_schema_or_validator_mentions_refs_ingested():
    """DEVSPEC-224: no schema and no validator names spec_refs_ingested or seed_refs_ingested (they had no reader)."""
    roots = [_TOOLKIT_ROOT / "schema", _TOOLKIT_ROOT / "tools" / "specdev_tools"]
    hits = [
        str(path.relative_to(_TOOLKIT_ROOT))
        for root in roots
        for path in root.rglob("*")
        if path.suffix in {".json", ".py"} and "refs_ingested" in path.read_text(encoding="utf-8")
    ]
    assert hits == []


def test_seed_freshness_still_emits_w595(tmp_path):
    """W595 is no longer emitted by forward replay but stays emitted by the seed index and promotable to E595."""
    assert PROMOTABLE_PAIRS["W595"] == "E595"
    spec_dir = tmp_path / "spec"
    (spec_dir / "common").mkdir(parents=True)
    manifest = {
        "seeds": [{"seed_id": "seed-gone", "path": "docs/seed/missing.md"}, {"seed_id": "seed-nopath"}],
    }
    (spec_dir / "common" / "seed_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _, warnings = build_seed_index(str(spec_dir), str(_TOOLKIT_ROOT))
    assert any(w.startswith("W595 SEED_NOT_FOUND") for w in warnings)
    assert any(w.startswith("W595 MISSING_PATH") for w in warnings)
