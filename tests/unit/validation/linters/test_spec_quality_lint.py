import json
import re
import tempfile
import unittest
from pathlib import Path

import pytest

from specdev_tools.validation.spec_quality_lint import (
    _VAGUE_SCAN_FIELDS,
    PLACEHOLDER_RE,
    _check_assumptions,
    _check_free_text_vague,
    lint_spec_quality,
)
from specdev_tools.core.errors import render_errors


class SpecQualityLintTests(unittest.TestCase):
    def test_detects_placeholder_and_missing_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "00_charter.json").write_text(
                json.dumps(
                    {
                        "id": "charter",
                        "owner": "system",
                        "created_at": "2026-01-01T00:00:00Z",


                        "canonical_refs_used": [],
                        "canonical_proposals": [],
                        "canonical_conflicts": [],
                        "terms": [],
                        "notes": "TODO",
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_spec_quality(str(root / "spec"))
            self.assertTrue(any("E510" in e for e in render_errors(errs)))
            self.assertTrue(any("empty critical array" in e for e in render_errors(errs)))

    def test_invalid_json_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "bad.json").write_text("{bad", encoding="utf-8")
            errs = lint_spec_quality(str(root / "spec"))
            self.assertTrue(any("invalid_json" in e for e in render_errors(errs)))

    def test_non_step_json_is_not_forced_to_step_top_level_keys(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec" / "common").mkdir(parents=True)
            (root / "spec" / "common" / "seed_manifest.json").write_text(
                json.dumps({"global_seed_order": ["seed_overview"]}),
                encoding="utf-8",
            )
            errs = lint_spec_quality(str(root / "spec"))
            self.assertFalse(any("seed_manifest.json missing top-level" in e for e in render_errors(errs)))

    def test_detects_missing_metadata_top_level_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "01_capabilities.json").write_text(
                json.dumps(
                    {
                        "id": "capabilities-test",
                        "owner": "system",
                        "created_at": "2026-01-01T00:00:00Z",

                        "capabilities": [{"capability_id": "cap-one"}],
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_spec_quality(str(root / "spec"))
            self.assertTrue(any("missing top-level 'canonical_refs_used'" in e for e in render_errors(errs)))
            self.assertFalse(any("missing top-level 'generation_quality'" in e for e in render_errors(errs)))
            self.assertFalse(any("missing top-level 'canonical_proposals'" in e for e in render_errors(errs)))
            self.assertFalse(any("missing top-level 'canonical_conflicts'" in e for e in render_errors(errs)))

    def test_schema_uri_drives_step_detection_for_nonstandard_filename(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "artifact.json").write_text(
                json.dumps(
                    {
                        "$schema": "vc:01-capabilities",
                        "id": "capabilities-test",
                        "owner": "system",
                        "created_at": "2026-01-01T00:00:00Z",

                        "capabilities": [{"capability_id": "cap-one"}],
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_spec_quality(str(root / "spec"))
            self.assertTrue(any("artifact.json missing top-level 'canonical_refs_used'" in e for e in render_errors(errs)))
            self.assertFalse(any("artifact.json missing top-level 'generation_quality'" in e for e in render_errors(errs)))

    def test_detects_assumption_vague_quantifier(self):
        errs = _check_assumptions("test.json", {"assumptions": ["Some things are fast"]})
        self.assertTrue(any("W571 ASSUMPTION_VAGUE_QUANTIFIER" in e and "ref=Some" in e for e in render_errors(errs)))
        self.assertTrue(any("W571 ASSUMPTION_VAGUE_QUANTIFIER" in e and "ref=fast" in e for e in render_errors(errs)))

    def test_detects_assumption_placeholder(self):
        errs = _check_assumptions("test.json", {"assumptions": ["This is TBD"]})
        self.assertTrue(any("E512 ASSUMPTION_HAS_PLACEHOLDER" in e for e in render_errors(errs)))

    def test_detects_assumption_count_high(self):
        errs = _check_assumptions("test.json", {"assumptions": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]})
        self.assertTrue(any("W572 ASSUMPTION_COUNT_HIGH" in e for e in render_errors(errs)))

    def test_no_tech_stack_coherence_check(self):
        """Steps 09 and 14 with differing `tech_stack` values raise no warning: the coherence check is gone."""
        with tempfile.TemporaryDirectory() as td:
            spec = Path(td) / "spec"
            spec.mkdir()
            base_meta = {
                "owner": "engineering",
                "created_at": "2026-01-01T00:00:00Z",
                "canonical_refs_used": [],
            }
            step09 = {**base_meta, "id": "impl-plan", "tech_stack": {"framework": "FastAPI"}}
            step14 = {**base_meta, "id": "roadmap", "tech_stack": {"framework": "Django"}}
            (spec / "09_impl_plan.json").write_text(json.dumps(step09), encoding="utf-8")
            (spec / "14_roadmap.json").write_text(json.dumps(step14), encoding="utf-8")
            errs = lint_spec_quality(str(spec))
            self.assertFalse(any("TECH_STACK_COHERENCE" in e for e in render_errors(errs)))

    def test_text_in_angle_brackets_is_not_a_placeholder(self):
        for value in ("<owner>", "Map<string>s", "a<b>c"):
            self.assertIsNone(PLACEHOLDER_RE.search(value), value)
        self.assertIsNotNone(PLACEHOLDER_RE.search("owner: TBD"))


STEP_ARTIFACT_BASE = {
    "id": "charter",
    "owner": "system",
    "created_at": "2026-01-01T00:00:00Z",
    "canonical_refs_used": [],
}


def _quality_lines(tmp_path: Path, **fields: object) -> list[str]:
    """Rendered findings of ``lint_spec_quality`` over one step 00 artifact holding *fields*."""
    spec = tmp_path / "spec"
    spec.mkdir(exist_ok=True)
    (spec / "00_charter.json").write_text(json.dumps({**STEP_ARTIFACT_BASE, **fields}), encoding="utf-8")
    return render_errors(lint_spec_quality(str(spec)))


@pytest.mark.parametrize("value", ["placeholder metadata", "Placeholder image"])
def test_the_english_word_placeholder_is_not_a_marker(value: str) -> None:
    assert PLACEHOLDER_RE.search(value) is None


@pytest.mark.parametrize("value", ["-tbd", "api-x-schema-tbd", "schemas/x/y_tbd"])
def test_the_tbd_sentinel_is_not_a_marker(value: str) -> None:
    assert PLACEHOLDER_RE.search(value) is None


@pytest.mark.parametrize("value", ["TBD", "owner: TBD", "[TODO]", "fixme", "XXX"])
def test_marker_forms_still_match(value: str) -> None:
    assert PLACEHOLDER_RE.search(value) is not None


def test_the_english_word_placeholder_gives_no_e510(tmp_path: Path) -> None:
    assert not any("E510" in line for line in _quality_lines(tmp_path, notes="placeholder metadata"))


def test_a_marker_gives_e510(tmp_path: Path) -> None:
    assert any("E510" in line for line in _quality_lines(tmp_path, notes="TODO"))


@pytest.mark.parametrize("value", ["[AUTO-DERIVE] postgres", "AUTO-DERIVE postgres"])
def test_auto_derive_marker_raises_e510(tmp_path: Path, value: str) -> None:
    assert PLACEHOLDER_RE.search(value) is not None
    assert any("E510" in line for line in _quality_lines(tmp_path, notes=value))


def test_auto_derive_marker_in_assumption_raises_e512() -> None:
    errs = _check_assumptions("test.json", {"assumptions": ["[AUTO-DERIVE] the store is postgres"]})
    assert any("E512 ASSUMPTION_HAS_PLACEHOLDER" in line for line in render_errors(errs))


def test_auto_derive_word_after_hyphen_is_not_a_marker() -> None:
    assert PLACEHOLDER_RE.search("x-auto-derive") is None


def test_w593_scans_a_string_inside_risks_spikes_preconditions_and_postconditions() -> None:
    data = {"frs": [{"statement": "reliable thing", "risks": ["various failures"], "preconditions": ["several users"]}]}
    lines = [line for line in render_errors(_check_free_text_vague("f.json", data)) if "W593" in line]
    assert [re.search(r"f\.json:(\S+)", line).group(1).rsplit(".", 1)[-1] for line in lines] == [
        "statement", "risks[0]", "preconditions[0]",
    ]


def test_w593_still_scans_a_list_of_objects_under_a_scan_field() -> None:
    data = {"risks": [{"description": "various failures"}]}
    assert any("risks[0].description" in line for line in render_errors(_check_free_text_vague("f.json", data)))


def test_narrative_is_not_a_scan_field() -> None:
    assert "narrative" not in _VAGUE_SCAN_FIELDS


if __name__ == "__main__":
    unittest.main()
