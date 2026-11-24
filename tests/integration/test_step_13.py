#!/usr/bin/env python3
"""Thin CLI wrapper for Step 13 validation.

Invokes the real ``specdev validate`` command against the given fixture.
Exit code mirrors the validator's exit code (0 = pass, 1 = fail).
"""

import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: test_step_13.py <fixture>")
    fixture = Path(sys.argv[1])
    toolkit_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "validate", str(fixture),
         "--repo-root", str(toolkit_root)],
        cwd=str(toolkit_root),
    )
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# E-030 (WI-M1-08): governance_label_ref is checked by canonical-integrity only.
# These are pytest tests; the file keeps its script entry point below.
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[2]
_SECURITY = "cn:core:governance_label:security"


def _build_spec(tmp_path, label_id, label_in_step_10):
    import json

    spec = tmp_path / "spec"
    spec.mkdir()
    ref = {"id": label_id, "kind": "governance_label"}
    manifest = json.loads((_REPO / "tests/fixtures/step_13/valid_manifest.json").read_text())
    manifest["extensions"] = manifest["extensions"][:1]
    manifest["extensions"][0]["governance_label_ref"] = ref
    manifest["canonical_refs_used"] = [ref]
    (spec / "13_extension_manifest.json").write_text(json.dumps(manifest))
    gov = json.loads((_REPO / "tests/fixtures/step_10/valid_with_canonical_refs.json").read_text())
    if label_in_step_10:
        gov["canonical_refs_used"].append(ref)
    (spec / "10_governance.json").write_text(json.dumps(gov))
    return str(spec)


def _spec_check_codes(spec):
    from specdev_tools.validation.spec_check import run_spec_check_json

    errors, _ = run_spec_check_json(str(_REPO), spec, spec_root=spec)
    return errors


def _gov_label_errors(errors, code):
    return [e for e in errors if e.code == code and "governance_label" in str(e)]


def test_e030_label_only_in_13_has_no_e590_or_e210(tmp_path):
    errors = _spec_check_codes(_build_spec(tmp_path, _SECURITY, False))
    assert _gov_label_errors(errors, "E590") == []
    assert not [e for e in errors if e.code == "E590" and "13_extension" in str(e)]
    assert not [e for e in errors if e.code == "E210"]


def test_e030_label_also_in_step_10_still_fires_e210_extra(tmp_path):
    errors = _spec_check_codes(_build_spec(tmp_path, _SECURITY, True))
    e210 = [e for e in errors if e.code == "E210" and "canonical_refs_used_extra" in str(e)]
    assert e210 and all("10_governance" in str(e) for e in e210)


def test_e030_label_not_in_canon_fires_e110(tmp_path):
    errors = _spec_check_codes(_build_spec(tmp_path, "cn:core:governance_label:bogus", False))
    assert any(e.code == "E110" and "governance_label:bogus" in str(e) for e in errors)
    assert not [e for e in errors if e.code == "E590" and "bogus" in str(e)]


def test_extension_with_two_sections_fails():
    from specdev_tools.validation.validate import validate_file

    errors = validate_file(str(_REPO), str(_REPO / "tests/fixtures/step_13/invalid_two_sections.json"))
    assert any(e.code == "E520" and "required_schema_sections" in e.render() for e in errors), [e.render() for e in errors]


if __name__ == "__main__":
    main()
