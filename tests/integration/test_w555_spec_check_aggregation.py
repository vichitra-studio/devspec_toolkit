"""Integration test: W555 surfaces through the spec-check aggregation path.

DEVSPEC-107 added W555 STEP00_SEED_OUT_OF_SCOPE_THIN to seed_lint.py and proved
it with 17 unit tests that call lint_seeds() directly.  This test exercises the
*spec-check aggregation path* — run_spec_check_json → _run_checks → lint_seeds →
_check_result — to confirm W555 is collected into the seed-lint check findings
and returned in DEFAULT output (no extra verbosity flags required).

The two AC cases:
  - Negative: seeds routed to step "00" have FEWER than 3 substantive
    out-of-scope items → W555 present in checks["seed-lint"]["findings"].
  - Positive: seeds routed to step "00" have EXACTLY 3 substantive
    out-of-scope items → W555 absent.
"""
from __future__ import annotations

import json
import os

import pytest

from specdev_tools.validation.spec_check import run_spec_check_json

# Real toolkit root — schemas, step_order.json, prompts/ all live here.
_TOOLKIT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)


@pytest.fixture()
def _w555_project(tmp_path, request):
    """Build a minimal host project routed so lint_seeds checks step "00".

    ``request.param`` is the seed-overview.md content to write, toggled
    between thin (no out-of-scope section) and rich (≥3 items) by each test.
    """
    spec_dir = tmp_path / "spec"
    common_dir = spec_dir / "common"
    seed_dir = tmp_path / "docs" / "seed"
    for d in [common_dir, seed_dir]:
        d.mkdir(parents=True)

    # Write the seed file with the content supplied by the test.
    (seed_dir / "seed_overview.md").write_text(request.param, encoding="utf-8")

    # Minimal manifest: one seed routed to step "00".
    # No $schema URI → E520 (missing_schema_uri) IS emitted, but it is irrelevant
    # to this test — the assertions check only W555 presence/absence; seed-lint
    # still runs via the project_root/spec/common/seed_manifest.json gate.
    manifest = {
        "seed_manifest_id": "seed-manifest-w555-integration",
        "version": "0.1.0",
        "created_at": "2026-06-25T00:00:00Z",
        "last_updated": "2026-06-25T00:00:00Z",
        "global_seed_order": ["seed-overview"],
        "seeds": [
            {
                "seed_id": "seed-overview",
                "path": "docs/seed/seed_overview.md",
                "description": "Project overview seed.",
                "required": True,
                "source_type": "doc",
            }
        ],
        "step_requirements": {
            "00": ["seed-overview"],
        },
    }
    (common_dir / "seed_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    return {
        "spec_dir": str(spec_dir),
        "project_root": str(tmp_path),
    }


# Seed content with NO out-of-scope section → 0 items < 3 → W555 must fire.
_THIN_SEED = """\
# Project Overview

## In-Scope Goals

- Build authentication service
- Support OAuth2
- Provide REST API

## Tech Stack

Using Node.js and PostgreSQL.
"""

# Seed content with exactly 3 substantive out-of-scope items → W555 must NOT fire.
_RICH_SEED = """\
# Project Overview

## In-Scope Goals

- Build authentication service
- Support OAuth2
- Provide REST API

## Out-of-Scope

- Mobile biometric authentication (Face ID / Touch ID) — post-launch only
- Historical order archive migration — separate initiative
- On-premises deployment — cloud-only for this release

## Tech Stack

Using Node.js and PostgreSQL.
"""


class TestW555SpecCheckAggregation:
    """W555 surfaces through the spec-check aggregation path (DEVSPEC-107)."""

    @pytest.mark.parametrize("_w555_project", [_THIN_SEED], indirect=True)
    def test_w555_present_in_seed_lint_findings_when_thin(self, _w555_project):
        """Thin seed (<3 out-of-scope items) → W555 in seed-lint findings via spec-check.

        Asserts W555 on both surfaces:
          - The combined list returned by run_spec_check_json (mirrors what the
            default CLI renders via _print_and_exit_if_errors).
          - The per-check "seed-lint" findings dict (JSON-mode surface).
        """
        errs, ctx = run_spec_check_json(
            repo_root=_TOOLKIT_ROOT,
            spec_dir=_w555_project["spec_dir"],
        )
        # Combined-list surface: mirrors the default non-JSON CLI render path.
        combined_codes = [e.code for e in errs]
        assert "W555" in combined_codes, (
            f"W555 must appear in the combined error list (default CLI output path) "
            f"for a thin step-00 seed. Got codes: {combined_codes}"
        )
        # Per-check surface: JSON-mode gate (checks["seed-lint"]["findings"]).
        seed_lint_check = ctx["checks"].get("seed-lint", {})
        # seed-lint must run (not SKIP) for this fixture.
        assert seed_lint_check.get("status") != "SKIP", (
            "seed-lint check was unexpectedly SKIPped; "
            "seed_manifest.json must be present at spec/common/seed_manifest.json"
        )
        finding_codes = [f.get("code") for f in seed_lint_check.get("findings", [])]
        assert "W555" in finding_codes, (
            f"W555 must appear in seed-lint findings for a thin step-00 seed. "
            f"Got finding codes: {finding_codes}"
        )

    @pytest.mark.parametrize("_w555_project", [_RICH_SEED], indirect=True)
    def test_w555_absent_in_seed_lint_findings_when_rich(self, _w555_project):
        """Rich seed (≥3 out-of-scope items) → W555 absent from seed-lint findings via spec-check.

        Asserts W555 absent on both surfaces: combined list and per-check findings.
        """
        errs, ctx = run_spec_check_json(
            repo_root=_TOOLKIT_ROOT,
            spec_dir=_w555_project["spec_dir"],
        )
        # Combined-list surface.
        combined_codes = [e.code for e in errs]
        assert "W555" not in combined_codes, (
            f"W555 must NOT appear in the combined error list for a rich step-00 seed. "
            f"Got codes: {combined_codes}"
        )
        # Per-check surface.
        seed_lint_check = ctx["checks"].get("seed-lint", {})
        assert seed_lint_check.get("status") != "SKIP", (
            "seed-lint check was unexpectedly SKIPped"
        )
        finding_codes = [f.get("code") for f in seed_lint_check.get("findings", [])]
        assert "W555" not in finding_codes, (
            f"W555 must NOT appear in seed-lint findings for a rich step-00 seed. "
            f"Got finding codes: {finding_codes}"
        )
