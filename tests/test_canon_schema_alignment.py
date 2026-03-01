"""Tests for canon <-> schema enum alignment linter."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from specdev_tools.validation.canon_schema_alignment import lint_canon_schema_alignment

_MODULE = "specdev_tools.validation.canon_schema_alignment"


def _make_canon_kind(tmp: str, kind: str, labels: list[str]) -> None:
    """Create a modular canon kind file with the given labels."""
    kinds_dir = os.path.join(tmp, "canon", "kinds")
    os.makedirs(kinds_dir, exist_ok=True)

    entries = []
    for label in labels:
        entry_id = f"{kind}-{label}"
        entries.append(
            {
                "id": entry_id,
                "kind": kind,
                "preferred_label": label,
                "definition": f"Definition for {label}",
                "version": "1.0.0",
                "status": "active",
                "owners": ["system"],
                "aliases": [],
                "tags": [],
                "lifecycle": {"introduced": "0.1.0"},
            }
        )

    kind_doc = {
        "$schema": "https://specdev.local/schema/canon/kind/1",
        "registry_version": "1.0.0",
        "kind": kind,
        "entries": entries,
    }
    with open(os.path.join(kinds_dir, f"{kind}.json"), "w") as f:
        json.dump(kind_doc, f)


def _make_schema(tmp: str, rel_path: str, content: dict) -> None:
    """Write a JSON Schema file at schema/<rel_path>."""
    full = os.path.join(tmp, "schema", rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        json.dump(content, f)


class CanonSchemaAlignmentTests(unittest.TestCase):
    """Verify canon <-> schema enum alignment checks."""

    # ------------------------------------------------------------------
    # 1. Perfect alignment -> zero errors
    # ------------------------------------------------------------------
    def test_aligned_enum_and_canon(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_canon_kind(tmp, "test_kind", ["a", "b", "c"])
            _make_schema(
                tmp,
                "test.schema.json",
                {"properties": {"field": {"enum": ["a", "b", "c"]}}},
            )
            pairings = [
                (
                    "test.schema.json",
                    ["properties", "field", "enum"],
                    "test_kind",
                )
            ]
            with patch(f"{_MODULE}._ENUM_CANON_PAIRINGS", pairings):
                errors = lint_canon_schema_alignment(tmp)

            self.assertEqual(errors, [])

    # ------------------------------------------------------------------
    # 2. Canon has more entries than schema enum -> E550
    # ------------------------------------------------------------------
    def test_canon_enum_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_canon_kind(tmp, "test_kind", ["a", "b", "c", "d"])
            _make_schema(
                tmp,
                "test.schema.json",
                {"properties": {"field": {"enum": ["a", "b", "c"]}}},
            )
            pairings = [
                (
                    "test.schema.json",
                    ["properties", "field", "enum"],
                    "test_kind",
                )
            ]
            with patch(f"{_MODULE}._ENUM_CANON_PAIRINGS", pairings):
                errors = lint_canon_schema_alignment(tmp)

            e550 = [e for e in errors if e.startswith("E550")]
            self.assertEqual(len(e550), 1)
            self.assertIn("d", e550[0])

    # ------------------------------------------------------------------
    # 3. Schema enum has values not in canon -> E551
    # ------------------------------------------------------------------
    def test_schema_enum_extra(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_canon_kind(tmp, "test_kind", ["a", "b"])
            _make_schema(
                tmp,
                "test.schema.json",
                {"properties": {"field": {"enum": ["a", "b", "c"]}}},
            )
            pairings = [
                (
                    "test.schema.json",
                    ["properties", "field", "enum"],
                    "test_kind",
                )
            ]
            with patch(f"{_MODULE}._ENUM_CANON_PAIRINGS", pairings):
                errors = lint_canon_schema_alignment(tmp)

            e551 = [e for e in errors if e.startswith("E551")]
            self.assertEqual(len(e551), 1)
            self.assertIn("c", e551[0])

    # ------------------------------------------------------------------
    # 4. Paired schema file does not exist -> E552
    # ------------------------------------------------------------------
    def test_missing_paired_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_canon_kind(tmp, "test_kind", ["a"])
            # Ensure schema/ dir exists but the file does not.
            os.makedirs(os.path.join(tmp, "schema"), exist_ok=True)
            pairings = [
                (
                    "nonexistent.schema.json",
                    ["properties", "field", "enum"],
                    "test_kind",
                )
            ]
            with patch(f"{_MODULE}._ENUM_CANON_PAIRINGS", pairings):
                errors = lint_canon_schema_alignment(tmp)

            e552 = [e for e in errors if e.startswith("E552")]
            self.assertEqual(len(e552), 1)
            self.assertIn("nonexistent.schema.json", e552[0])

    # ------------------------------------------------------------------
    # 5. Schema file exists but JSON path doesn't resolve -> E553
    # ------------------------------------------------------------------
    def test_missing_enum_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_canon_kind(tmp, "test_kind", ["a"])
            _make_schema(
                tmp,
                "test.schema.json",
                {"properties": {"other": {"type": "string"}}},
            )
            pairings = [
                (
                    "test.schema.json",
                    ["properties", "field", "enum"],
                    "test_kind",
                )
            ]
            with patch(f"{_MODULE}._ENUM_CANON_PAIRINGS", pairings):
                errors = lint_canon_schema_alignment(tmp)

            e553 = [e for e in errors if e.startswith("E553")]
            self.assertEqual(len(e553), 1)
            self.assertIn("test.schema.json", e553[0])

    # ------------------------------------------------------------------
    # 6. Discovery scan finds unregistered overlap >= 80% -> W552
    # ------------------------------------------------------------------
    def test_discovery_scan_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_canon_kind(tmp, "test_kind", ["x", "y", "z", "w"])
            # Schema with enum that matches all 4 canon labels (100% overlap).
            _make_schema(
                tmp,
                "unregistered.schema.json",
                {"properties": {"status": {"enum": ["x", "y", "z", "w"]}}},
            )
            # Empty pairings so nothing is registered; discovery should fire.
            with patch(f"{_MODULE}._ENUM_CANON_PAIRINGS", []):
                errors = lint_canon_schema_alignment(tmp)

            w552 = [e for e in errors if e.startswith("W552")]
            self.assertGreaterEqual(len(w552), 1)
            self.assertIn("test_kind", w552[0])

    # ------------------------------------------------------------------
    # 7. Small enum below both count (<3) and ratio (<0.8) thresholds
    #    -> no false positive warnings
    # ------------------------------------------------------------------
    def test_no_false_positives_on_subset_enum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_canon_kind(tmp, "test_kind", ["a", "b", "c", "d", "e"])
            # Only 2 values overlap -> below count threshold of 3 and
            # 2/2 ratio is 1.0 but len(enum_set) < 3 short-circuits first.
            _make_schema(
                tmp,
                "small.schema.json",
                {"properties": {"x": {"enum": ["a", "b"]}}},
            )
            with patch(f"{_MODULE}._ENUM_CANON_PAIRINGS", []):
                errors = lint_canon_schema_alignment(tmp)

            w552 = [e for e in errors if e.startswith("W552")]
            self.assertEqual(w552, [])


if __name__ == "__main__":
    unittest.main()
