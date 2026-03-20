"""Tests for R9 vague language expansion in spec_quality_lint.py.

Covers:
- W593 VAGUE_LANGUAGE_FREE_TEXT emitted for vague terms in free-text fields
- W571 ASSUMPTION_VAGUE_QUANTIFIER still used for assumption fields
- Clean free-text passes without W593
- Metadata fields ($schema, id, owner) are NOT scanned
- All 18 vague terms are detected
- Nested vague terms in objects/arrays are detected
- Both directory mode (lint_spec_quality) and single-file mode (lint_spec_quality_file)
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.core.errors import render_errors
from specdev_tools.validation.spec_quality_lint import (
    _check_free_text_vague,
    _scan_for_vague_language,
    _VAGUE_SCAN_FIELDS,
    _METADATA_FIELDS,
    lint_spec_quality,
    lint_spec_quality_file,
)


def _make_step_artifact(**extra) -> dict:
    """Return a minimal valid step artifact with required top-level fields."""
    base = {
        "$schema": "vc:04-fr-list",
        "id": "fr-test",
        "owner": "system",
        "created_at": "2026-01-01T00:00:00Z",
        "canonical_refs_used": [],
        "canonical_proposals": [],
        "canonical_conflicts": [],
    }
    base.update(extra)
    return base


# All 18 vague terms from the regex
ALL_VAGUE_TERMS = [
    "few", "some", "many", "several", "various",
    "fast", "reliable", "easy", "hard", "quick",
    "appropriate", "adequate", "sufficient", "reasonable",
    "significant", "typical", "generally", "usually",
]


class TestScanForVagueLanguage(unittest.TestCase):
    """Unit tests for the _scan_for_vague_language helper."""

    def test_detects_single_vague_term(self):
        result = _scan_for_vague_language("This has some issues")
        self.assertIn("some", result)

    def test_detects_multiple_vague_terms(self):
        result = _scan_for_vague_language("Many users need fast responses")
        self.assertIn("Many", result)
        self.assertIn("fast", result)

    def test_clean_text_returns_empty(self):
        result = _scan_for_vague_language("The system authenticates users via OAuth2")
        self.assertEqual(result, [])

    def test_all_18_vague_terms_detected(self):
        for term in ALL_VAGUE_TERMS:
            with self.subTest(term=term):
                sentence = f"The system provides {term} behavior"
                result = _scan_for_vague_language(sentence)
                self.assertTrue(
                    any(t.lower() == term.lower() for t in result),
                    f"Expected '{term}' to be detected in: {sentence}",
                )

    def test_case_insensitive(self):
        result = _scan_for_vague_language("SUFFICIENT capacity for REASONABLE load")
        lower_results = [t.lower() for t in result]
        self.assertIn("sufficient", lower_results)
        self.assertIn("reasonable", lower_results)


class TestCheckFreeTextVague(unittest.TestCase):
    """Unit tests for _check_free_text_vague."""

    def test_description_with_vague_term_emits_w593(self):
        data = {"description": "The system should be fast enough"}
        errs = _check_free_text_vague("test.json", data)
        w593_errs = [e for e in render_errors(errs) if "W593" in e]
        self.assertEqual(len(w593_errs), 1)
        self.assertIn("ref=fast", w593_errs[0])
        self.assertIn("description", w593_errs[0])

    def test_statement_with_vague_term_emits_w593(self):
        data = {"statement": "Generally the service is reliable"}
        errs = _check_free_text_vague("test.json", data)
        w593_errs = [e for e in render_errors(errs) if "W593" in e]
        terms_found = {e.split("ref=")[1] for e in w593_errs}
        self.assertIn("Generally", terms_found)
        self.assertIn("reliable", terms_found)

    def test_all_scannable_fields_emit_w593(self):
        """Every field in _VAGUE_SCAN_FIELDS should be scanned."""
        for field in _VAGUE_SCAN_FIELDS:
            with self.subTest(field=field):
                data = {field: "This has several problems"}
                errs = _check_free_text_vague("test.json", data)
                w593_errs = [e for e in render_errors(errs) if "W593" in e]
                self.assertTrue(
                    len(w593_errs) >= 1,
                    f"Expected W593 for field '{field}' but got: {errs}",
                )
                self.assertTrue(
                    any(field in e for e in w593_errs),
                    f"Expected field '{field}' in error path",
                )

    def test_assumptions_field_skipped_by_check_free_text_vague(self):
        """_check_free_text_vague should NOT recurse into 'assumptions'."""
        data = {"assumptions": ["Some things are fast"]}
        errs = _check_free_text_vague("test.json", data)
        self.assertEqual(errs, [], "assumptions should be skipped by _check_free_text_vague")

    def test_metadata_fields_not_scanned(self):
        """Fields in _METADATA_FIELDS must not trigger W593."""
        for field in _METADATA_FIELDS:
            with self.subTest(field=field):
                data = {field: "some fast easy value"}
                errs = _check_free_text_vague("test.json", data)
                self.assertEqual(
                    errs, [],
                    f"Metadata field '{field}' should not be scanned but got: {errs}",
                )

    def test_non_scannable_string_field_not_scanned(self):
        """String fields not in _VAGUE_SCAN_FIELDS at the same level are not scanned."""
        data = {"title": "Some fast overview"}
        errs = _check_free_text_vague("test.json", data)
        # "title" is not in _VAGUE_SCAN_FIELDS, so no W593 should fire
        self.assertEqual(errs, [])

    def test_clean_description_no_w593(self):
        data = {"description": "The system authenticates users via OAuth2"}
        errs = _check_free_text_vague("test.json", data)
        w593_errs = [e for e in render_errors(errs) if "W593" in e]
        self.assertEqual(w593_errs, [])

    def test_nested_object_vague_detected(self):
        """Vague language inside nested objects should be detected."""
        data = {
            "functional_requirements": [
                {"description": "The API returns appropriate errors"}
            ]
        }
        errs = _check_free_text_vague("test.json", data)
        w593_errs = [e for e in render_errors(errs) if "W593" in e]
        self.assertTrue(len(w593_errs) >= 1)
        self.assertIn("ref=appropriate", w593_errs[0])
        self.assertIn("functional_requirements[0].description", w593_errs[0])

    def test_nested_array_of_objects_vague_detected(self):
        """Vague terms deeply nested in arrays of objects are detected."""
        data = {
            "apis": [
                {
                    "endpoints": [
                        {"description": "Provides adequate throughput"}
                    ]
                }
            ]
        }
        errs = _check_free_text_vague("test.json", data)
        w593_errs = [e for e in render_errors(errs) if "W593" in e]
        self.assertTrue(len(w593_errs) >= 1)
        self.assertIn("ref=adequate", w593_errs[0])

    def test_multiple_vague_terms_in_one_field(self):
        data = {"description": "Some users need fast and reliable access"}
        errs = _check_free_text_vague("test.json", data)
        w593_errs = [e for e in render_errors(errs) if "W593" in e]
        terms_found = {e.split("ref=")[1] for e in w593_errs}
        self.assertEqual(terms_found, {"Some", "fast", "reliable"})


class TestVagueLintDirectoryMode(unittest.TestCase):
    """Integration tests using lint_spec_quality (directory mode)."""

    def _write_spec(self, spec_dir: Path, filename: str, data: dict) -> None:
        (spec_dir / filename).write_text(
            json.dumps(data), encoding="utf-8"
        )

    def test_w593_emitted_for_description_in_directory_mode(self):
        with tempfile.TemporaryDirectory() as td:
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            artifact = _make_step_artifact(
                description="The system provides adequate coverage"
            )
            self._write_spec(spec_dir, "04_functional_requirements.json", artifact)
            errs = lint_spec_quality(str(spec_dir))
            w593_errs = [e for e in render_errors(errs) if "W593" in e]
            self.assertTrue(len(w593_errs) >= 1)
            self.assertIn("ref=adequate", w593_errs[0])

    def test_w571_still_emitted_for_assumptions_not_w593(self):
        """Vague terms inside assumptions produce W571, never W593."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            artifact = _make_step_artifact(
                assumptions=["Some users are fast"]
            )
            self._write_spec(spec_dir, "04_functional_requirements.json", artifact)
            errs = lint_spec_quality(str(spec_dir))
            w571_errs = [e for e in render_errors(errs) if "W571" in e]
            w593_errs = [e for e in render_errors(errs) if "W593" in e]
            self.assertTrue(
                len(w571_errs) >= 1,
                f"Expected W571 for assumptions vague term, got: {errs}",
            )
            self.assertEqual(
                w593_errs, [],
                "Assumptions should produce W571, NOT W593",
            )

    def test_clean_spec_no_w593(self):
        with tempfile.TemporaryDirectory() as td:
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            artifact = _make_step_artifact(
                description="The system authenticates users via OAuth2 tokens"
            )
            self._write_spec(spec_dir, "04_functional_requirements.json", artifact)
            errs = lint_spec_quality(str(spec_dir))
            w593_errs = [e for e in render_errors(errs) if "W593" in e]
            self.assertEqual(w593_errs, [])

    def test_metadata_fields_not_scanned_directory_mode(self):
        """$schema, id, owner fields with vague language should NOT trigger W593."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            artifact = _make_step_artifact()
            # id and owner already set; $schema contains "some" is not realistic,
            # but we explicitly set id to a vague-word-containing value
            artifact["id"] = "fr-some-fast-thing"
            artifact["owner"] = "some-team"
            self._write_spec(spec_dir, "04_functional_requirements.json", artifact)
            errs = lint_spec_quality(str(spec_dir))
            w593_errs = [e for e in render_errors(errs) if "W593" in e]
            self.assertEqual(w593_errs, [])

    def test_schema_uri_driven_artifact_scanned(self):
        """Files with a valid $schema URI but non-standard filename are also scanned."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            artifact = _make_step_artifact(
                description="Provides sufficient throughput"
            )
            # Non-standard filename, but valid $schema URI
            self._write_spec(spec_dir, "custom_artifact.json", artifact)
            errs = lint_spec_quality(str(spec_dir))
            w593_errs = [e for e in render_errors(errs) if "W593" in e]
            self.assertTrue(len(w593_errs) >= 1)
            self.assertIn("ref=sufficient", w593_errs[0])

    def test_non_step_artifact_not_scanned(self):
        """Files without step artifact filename or $schema URI are ignored."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            non_step = {"description": "Some fast easy thing", "meta": True}
            self._write_spec(spec_dir, "random_config.json", non_step)
            errs = lint_spec_quality(str(spec_dir))
            w593_errs = [e for e in render_errors(errs) if "W593" in e]
            self.assertEqual(w593_errs, [])


class TestVagueLintSingleFileMode(unittest.TestCase):
    """Integration tests using lint_spec_quality_file (single file mode)."""

    def test_w593_emitted_single_file_mode(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "04_functional_requirements.json"
            artifact = _make_step_artifact(
                rationale="This is a reasonable approach"
            )
            p.write_text(json.dumps(artifact), encoding="utf-8")
            errs = lint_spec_quality_file(str(p))
            w593_errs = [e for e in render_errors(errs) if "W593" in e]
            self.assertTrue(len(w593_errs) >= 1)
            self.assertIn("ref=reasonable", w593_errs[0])

    def test_w571_for_assumptions_in_single_file_mode(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "04_functional_requirements.json"
            artifact = _make_step_artifact(
                assumptions=["Several components depend on this"]
            )
            p.write_text(json.dumps(artifact), encoding="utf-8")
            errs = lint_spec_quality_file(str(p))
            w571_errs = [e for e in render_errors(errs) if "W571" in e]
            w593_errs = [e for e in render_errors(errs) if "W593" in e]
            self.assertTrue(len(w571_errs) >= 1)
            self.assertEqual(w593_errs, [])

    def test_clean_single_file_no_w593(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "04_functional_requirements.json"
            artifact = _make_step_artifact(
                description="Users authenticate with JWT tokens"
            )
            p.write_text(json.dumps(artifact), encoding="utf-8")
            errs = lint_spec_quality_file(str(p))
            w593_errs = [e for e in render_errors(errs) if "W593" in e]
            self.assertEqual(w593_errs, [])

    def test_multiple_fields_with_vague_terms_single_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "04_functional_requirements.json"
            artifact = _make_step_artifact(
                description="Provides significant value",
                rationale="Typically this is the approach",
                notes="Generally this works well",
            )
            p.write_text(json.dumps(artifact), encoding="utf-8")
            errs = lint_spec_quality_file(str(p))
            w593_errs = [e for e in render_errors(errs) if "W593" in e]
            terms_found = {e.split("ref=")[1] for e in w593_errs}
            self.assertIn("significant", terms_found)
            self.assertIn("Generally", terms_found)

    def test_nested_vague_in_single_file_mode(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "04_functional_requirements.json"
            artifact = _make_step_artifact(
                functional_requirements=[
                    {
                        "fr_id": "fr-one",
                        "statement": "Usually the system responds quickly",
                        "description": "This provides various options",
                    }
                ],
            )
            p.write_text(json.dumps(artifact), encoding="utf-8")
            errs = lint_spec_quality_file(str(p))
            w593_errs = [e for e in render_errors(errs) if "W593" in e]
            terms_found = {e.split("ref=")[1] for e in w593_errs}
            self.assertIn("Usually", terms_found)
            self.assertIn("various", terms_found)
            # Note: "quickly" does NOT match \bquick\b because 'l' follows,
            # so word boundary fails — this is correct regex behavior.
            self.assertNotIn("quickly", terms_found)


class TestAllVagueTermsEndToEnd(unittest.TestCase):
    """Verify all 18 vague terms produce W593 in a full artifact via single-file mode."""

    def test_each_vague_term_in_description_produces_w593(self):
        for term in ALL_VAGUE_TERMS:
            with self.subTest(term=term):
                with tempfile.TemporaryDirectory() as td:
                    p = Path(td) / "04_functional_requirements.json"
                    artifact = _make_step_artifact(
                        description=f"The system provides {term} behavior"
                    )
                    p.write_text(json.dumps(artifact), encoding="utf-8")
                    errs = lint_spec_quality_file(str(p))
                    w593_errs = [e for e in render_errors(errs) if "W593" in e]
                    self.assertTrue(
                        len(w593_errs) >= 1,
                        f"Expected W593 for term '{term}' but got: {errs}",
                    )
                    # Verify the matched term is in the error
                    matched_terms = [e.split("ref=")[1] for e in w593_errs]
                    self.assertTrue(
                        any(t.lower() == term.lower() for t in matched_terms),
                        f"Expected ref matching '{term}' in {matched_terms}",
                    )

    def test_each_vague_term_in_assumptions_produces_w571(self):
        """Cross-check: same 18 terms in assumptions produce W571, not W593."""
        for term in ALL_VAGUE_TERMS:
            with self.subTest(term=term):
                with tempfile.TemporaryDirectory() as td:
                    p = Path(td) / "04_functional_requirements.json"
                    artifact = _make_step_artifact(
                        assumptions=[f"The system provides {term} behavior"]
                    )
                    p.write_text(json.dumps(artifact), encoding="utf-8")
                    errs = lint_spec_quality_file(str(p))
                    w571_errs = [e for e in render_errors(errs) if "W571" in e]
                    w593_errs = [e for e in render_errors(errs) if "W593" in e]
                    self.assertTrue(
                        len(w571_errs) >= 1,
                        f"Expected W571 for term '{term}' in assumptions",
                    )
                    self.assertEqual(
                        w593_errs, [],
                        f"Assumptions should not produce W593 for '{term}'",
                    )


class TestVagueScanFieldsCoverage(unittest.TestCase):
    """Verify the _VAGUE_SCAN_FIELDS set contains expected fields."""

    EXPECTED_FIELDS = {
        "description", "statement", "rationale", "justification", "notes",
        "narrative", "postconditions", "preconditions", "risks", "spikes",
        "migration_plan", "definition",
    }

    def test_vague_scan_fields_complete(self):
        self.assertEqual(_VAGUE_SCAN_FIELDS, self.EXPECTED_FIELDS)

    def test_metadata_fields_complete(self):
        expected_meta = {"$schema", "id", "owner", "created_at", "specdev_version"}
        self.assertEqual(_METADATA_FIELDS, expected_meta)

    def test_no_overlap_scan_and_metadata(self):
        overlap = _VAGUE_SCAN_FIELDS & _METADATA_FIELDS
        self.assertEqual(overlap, set(), f"Overlap between scan and metadata: {overlap}")


if __name__ == "__main__":
    unittest.main()
