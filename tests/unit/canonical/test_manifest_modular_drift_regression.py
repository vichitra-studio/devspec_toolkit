"""Bug 4 regression: ensure ``lint_canon_dir`` still flags drift when a
modular ``canon/kinds/<kind>.json`` entry exists but is missing from
``canon/manifest.json``.

Reproduces the original host-spec defect where
``cn:project:risk_category:data-privacy`` lived in
``spec/canon/kinds/risk_category.json`` but not in ``spec/canon/manifest.json``.

Tests go through the public ``lint_canon_dir`` entrypoint so the manifest
loading + modular composition path is exercised — a refactor that stopped
calling ``_detect_manifest_modular_drift`` would surface here as a failure.
"""
import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.canonical.lint import lint_canon_dir


def _entry(entry_id: str) -> dict:
    return {
        "id": entry_id,
        "kind": "risk_category",
        "preferred_label": entry_id.rsplit(":", 1)[-1],
        "version": "1.0.0",
        "status": "active",
        "aliases": [],
        "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
    }


def _write_canon_dir(root: Path, manifest_entries, modular_entries) -> None:
    canon = root / "canon"
    (canon / "kinds").mkdir(parents=True)
    (canon / "manifest.json").write_text(
        json.dumps({
            "registry_version": "1.0.0",
            "entries": manifest_entries,
            "aliases": [],
        }),
        encoding="utf-8",
    )
    (canon / "aliases.json").write_text(
        json.dumps({"registry_version": "1.0.0", "aliases": []}),
        encoding="utf-8",
    )
    (canon / "kinds" / "risk_category.json").write_text(
        json.dumps({
            "registry_version": "1.0.0",
            "kind": "risk_category",
            "entries": modular_entries,
        }),
        encoding="utf-8",
    )


class ManifestModularDriftRegression(unittest.TestCase):
    def test_modular_entry_missing_from_manifest_fires_e210(self):
        shared = _entry("cn:project:risk_category:security")
        modular_only = _entry("cn:project:risk_category:data-privacy")
        with tempfile.TemporaryDirectory() as td:
            _write_canon_dir(
                Path(td),
                manifest_entries=[shared],
                modular_entries=[shared, modular_only],
            )
            errs = lint_canon_dir(td, require_manifest_schema_registration=False)
        codes = [e.code for e in errs]
        rendered = [e.render() for e in errs]
        self.assertIn("E210", codes, f"expected E210 drift, got: {rendered}")
        self.assertTrue(
            any("data-privacy" in r or "only_modular" in r for r in rendered),
            f"expected drift message to name missing entry: {rendered}",
        )

    def test_aligned_manifest_and_modular_does_not_drift(self):
        """Sanity: when both files agree, no E210 fires."""
        shared = [
            _entry("cn:project:risk_category:security"),
            _entry("cn:project:risk_category:data-privacy"),
        ]
        with tempfile.TemporaryDirectory() as td:
            _write_canon_dir(Path(td), manifest_entries=shared, modular_entries=shared)
            errs = lint_canon_dir(td, require_manifest_schema_registration=False)
        self.assertFalse(
            any(e.code == "E210" for e in errs),
            f"aligned registry must not fire E210: {[e.render() for e in errs]}",
        )
