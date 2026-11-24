"""Unit tests for _sync_canonical_refs_used and E210 autofix-hint messages."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from specdev_tools.canonical import autofix
from specdev_tools.canonical.autofix import _sync_canonical_refs_used, canonical_autofix
from specdev_tools.canonical.integrity import validate_canonical_integrity
from specdev_tools.canonical.registry import CanonicalRegistry


def _write_manifest(root: Path, entries: list[dict]) -> None:
    (root / "canon").mkdir(exist_ok=True)
    (root / "canon" / "manifest.json").write_text(
        json.dumps(
            {
                "registry_version": "1.0.0",
                "entries": entries,
                "aliases": [],
            }
        ),
        encoding="utf-8",
    )


def _manifest_entry(cid: str, kind: str) -> dict:
    return {
        "id": cid,
        "kind": kind,
        "version": "1.0.0",
        "status": "active",
        "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
    }


class TestSyncCanonicalRefsUsed(unittest.TestCase):
    def _registry(self, td: Path, entries: list[dict]) -> CanonicalRegistry:
        _write_manifest(td, entries)
        return CanonicalRegistry.load(str(td))

    def test_autofix_adds_missing_canonical_refs_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            registry = self._registry(td, [_manifest_entry("cn:core:metric:latency", "metric")])
            data = {
                "canonical_refs_used": [],
                "metric_ref": {"id": "cn:core:metric:latency", "kind": "metric"},
            }
            file_changes: list = []
            _sync_canonical_refs_used(data, registry, file_changes)
            self.assertEqual(len(data["canonical_refs_used"]), 1)
            self.assertEqual(data["canonical_refs_used"][0]["id"], "cn:core:metric:latency")
            self.assertTrue(any("add canonical_refs_used" in str(c) for c in file_changes))

    def test_autofix_prunes_stale_canonical_refs_used_cn_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            registry = self._registry(td, [])
            data = {
                "canonical_refs_used": [
                    {"id": "cn:core:metric:stale-one", "kind": "metric"}
                ],
            }
            file_changes: list = []
            _sync_canonical_refs_used(data, registry, file_changes)
            self.assertEqual(data["canonical_refs_used"], [])
            self.assertTrue(any("remove canonical_refs_used id=cn:core:metric:stale-one" in str(c) for c in file_changes))

    def test_autofix_preserves_non_cn_canonical_refs_used_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            registry = self._registry(td, [])
            data = {
                "canonical_refs_used": [
                    {"id": "other:namespace:entry", "kind": "custom"}
                ],
            }
            file_changes: list = []
            _sync_canonical_refs_used(data, registry, file_changes)
            self.assertEqual(len(data["canonical_refs_used"]), 1)
            self.assertEqual(data["canonical_refs_used"][0]["id"], "other:namespace:entry")
            self.assertEqual(file_changes, [])


class TestE210AutofixHint(unittest.TestCase):
    def test_e210_message_includes_autofix_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            (td / "spec").mkdir()
            _write_manifest(td, [_manifest_entry("cn:core:metric:used", "metric")])
            (td / "spec" / "07_nfrs.json").write_text(
                json.dumps(
                    {
                        "canonical_refs_used": [],
                        "metric_ref": {"id": "cn:core:metric:used", "kind": "metric"},
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(
                str(td),
                str(td / "spec"),
                require_manifest_schema_registration=False,
            )
            e210s = [e for e in errs if e.code == "E210" and "canonical_refs_used_missing" in e.render()]
            self.assertTrue(e210s, f"expected E210 missing, got: {[e.render() for e in errs]}")
            self.assertTrue(any("canonical-autofix" in e.render() for e in e210s))


class TestAutofixValidatesTheFinishedDocument(unittest.TestCase):
    """The finished document is checked against its schema before anything is written."""

    SCHEMA_URI = "vc:test-autofix-doc"

    def _repo(self, td: Path, document: dict) -> Path:
        (td / "tools").mkdir()
        (td / "schema").mkdir()
        (td / "spec").mkdir()
        _write_manifest(td, [])
        (td / "tools" / "schema_registry.json").write_text(
            json.dumps({self.SCHEMA_URI: "schema/doc.schema.json"}), encoding="utf-8"
        )
        (td / "schema" / "doc.schema.json").write_text(
            json.dumps(
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$id": self.SCHEMA_URI,
                    "type": "object",
                    "properties": {
                        "canonical_refs_used": {"type": "array"},
                        "items": {"type": "array", "minItems": 1},
                        "note": {"type": "string"},
                    },
                }
            ),
            encoding="utf-8",
        )
        target = td / "spec" / "doc.json"
        target.write_text(json.dumps({"$schema": self.SCHEMA_URI, **document}), encoding="utf-8")
        return target

    @staticmethod
    def _edit_with(field: str, value):
        def fake_sync(data, registry, file_changes):
            data[field] = value
            file_changes.append(f"set {field}")

        return patch.object(autofix, "_sync_canonical_refs_used", fake_sync)

    def test_autofix_refuses_to_write_a_result_that_adds_a_schema_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._repo(Path(tmp), {"canonical_refs_used": [], "items": [1]})
            original = target.read_bytes()
            with self._edit_with("canonical_refs_used", "not-a-list"):
                changes = canonical_autofix(tmp, str(Path(tmp) / "spec"), write=True, require_manifest_schema_registration=False)
            rendered = [item.render() if hasattr(item, "render") else str(item) for item in changes[str(target)]]
            self.assertTrue(any("E520" in r and "autofix_result_invalid" in r for r in rendered), rendered)
            self.assertEqual(target.read_bytes(), original)

    def test_a_violation_the_file_already_had_does_not_block_the_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._repo(Path(tmp), {"canonical_refs_used": [], "items": []})
            with self._edit_with("note", "written"):
                changes = canonical_autofix(tmp, str(Path(tmp) / "spec"), write=True, require_manifest_schema_registration=False)
            rendered = [item.render() if hasattr(item, "render") else str(item) for item in changes[str(target)]]
            self.assertFalse(any("autofix_result_invalid" in r for r in rendered), rendered)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["note"], "written")

    def test_autofix_still_writes_a_valid_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._repo(Path(tmp), {"canonical_refs_used": [], "items": [1]})
            with self._edit_with("note", "written"):
                canonical_autofix(tmp, str(Path(tmp) / "spec"), write=True, require_manifest_schema_registration=False)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["note"], "written")


if __name__ == "__main__":
    unittest.main()
