"""Unit tests for _sync_canonical_refs_used and E210 autofix-hint messages."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.canonical.autofix import _sync_canonical_refs_used
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


if __name__ == "__main__":
    unittest.main()
