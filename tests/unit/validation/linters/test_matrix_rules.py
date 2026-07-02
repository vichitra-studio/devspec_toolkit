"""Tests for matrix.py: link building, coverage thresholds, milestone coverage, entity dedup.

Covers:
- FR→API link building: APIs carry the authoritative FR trace (API-side iteration)
- Fixture→API→FR cascade: fixtures surface in FR rows via their API links
- Threat→API→FR cascade: threats surface in FR rows via their API links
- NFR direct (FR trace) and indirect (API trace) linking
- Coverage threshold enforcement (_check_coverage_thresholds / _load_coverage_thresholds)
- Milestone coverage mapping from Step 14 artifacts
- Entity deduplication across spec files
"""
import json
import os
import tempfile
import unittest

from specdev_tools.validation.matrix import (
    _check_coverage_thresholds,
    _DEFAULT_COVERAGE_THRESHOLDS,
    _load_coverage_thresholds,
    _MISSING_FILE,
    build_trace_matrix,
)


# ---------------------------------------------------------------------------
# Spec-builder helpers
# ---------------------------------------------------------------------------

def _write_spec_file(spec_dir: str, filename: str, data: dict) -> str:
    """Write *data* as JSON to *spec_dir*/*filename* and return the path."""
    path = os.path.join(spec_dir, filename)
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def _run_matrix(*, frs=None, apis=None, fixtures=None, threats=None, nfrs=None, out_of_scope=None,
                 fixture_out_of_scope=None) -> dict:
    """Write minimal spec files into a temp dir and run build_trace_matrix.

    Only files whose argument is not None are written, so callers can compose
    exactly the entities needed for the behaviour under test.
    """
    with tempfile.TemporaryDirectory() as td:
        spec_dir = os.path.join(td, "spec")
        os.makedirs(spec_dir)
        if frs is not None:
            _write_spec_file(spec_dir, "04_fr_list.json", {
                "$schema": "vc:step:04",
                "functional_requirements": frs,
            })
        if apis is not None or out_of_scope is not None:
            step05: dict = {"$schema": "vc:step:05", "apis": apis if apis is not None else []}
            if out_of_scope is not None:
                step05["out_of_scope"] = out_of_scope
            _write_spec_file(spec_dir, "05_interface_contracts.json", step05)
        if fixtures is not None or fixture_out_of_scope is not None:
            step08: dict = {"$schema": "vc:step:08", "fixtures": fixtures if fixtures is not None else []}
            if fixture_out_of_scope is not None:
                step08["out_of_scope"] = fixture_out_of_scope
            _write_spec_file(spec_dir, "08_fixtures.json", step08)
        if threats is not None:
            _write_spec_file(spec_dir, "11_redteam.json", {
                "$schema": "vc:step:11",
                "threats": threats,
            })
        if nfrs is not None:
            _write_spec_file(spec_dir, "07_nfrs.json", {
                "$schema": "vc:step:07",
                "nfrs": nfrs,
            })
        # td is the repo_root; no step_order.json → threshold check gracefully skips
        return build_trace_matrix(td, spec_dir)


def _row(result: dict, fr_id: str) -> dict:
    """Return the matrix row for *fr_id*. Raises AssertionError with a clear message if absent."""
    row = next((r for r in result["matrix"] if r["fr_id"] == fr_id), None)
    assert row is not None, f"No matrix row found for fr_id={fr_id!r}; matrix={result['matrix']}"
    return row


# ---------------------------------------------------------------------------
# Entity object factories
# ---------------------------------------------------------------------------

def _fr(fr_id: str) -> dict:
    """Minimal FR object. FRs do not trace to APIs — that relationship is on the API side."""
    return {"fr_id": fr_id}


def _api(api_id: str, fr_ids: list) -> dict:
    """Minimal API object tracing to the given FRs (the authoritative direction)."""
    return {"api_id": api_id, "trace": [{"type": "fr", "id": fid} for fid in fr_ids]}


def _fixture(fixture_id: str, api_ids: list) -> dict:
    """Minimal fixture targeting the given APIs."""
    return {"fixture_id": fixture_id, "targets": [{"type": "api", "id": aid} for aid in api_ids]}


def _threat(threat_id: str, api_ids: list) -> dict:
    """Minimal threat targeting the given APIs."""
    return {"threat_id": threat_id, "target_ids": [{"type": "api", "id": aid} for aid in api_ids]}


def _nfr(nfr_id: str, *, fr_ids=(), api_ids=()) -> dict:
    """Minimal NFR tracing to FRs (direct) and/or APIs (indirect)."""
    trace = [{"type": "fr", "id": fid} for fid in fr_ids]
    trace += [{"type": "api", "id": aid} for aid in api_ids]
    return {"nfr_id": nfr_id, "trace": trace}


# ---------------------------------------------------------------------------
# Coverage-threshold builder helper
# ---------------------------------------------------------------------------

def _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="warn"):
    """Write a minimal tools/step_order.json with coverage_thresholds."""
    tools_dir = os.path.join(repo_root, "tools")
    os.makedirs(tools_dir, exist_ok=True)
    step_order = {
        "steps": ["00"],
        "coverage_thresholds": {
            "fr_coverage": fr_coverage,
            "mode": mode,
        },
    }
    with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
        json.dump(step_order, f)


# ===========================================================================
# Coverage-threshold loader
# ===========================================================================

class TestLoadCoverageThresholds(unittest.TestCase):
    """Tests for _load_coverage_thresholds helper."""

    def test_returns_thresholds_from_step_order(self):
        """Loads coverage_thresholds dict from tools/step_order.json."""
        with tempfile.TemporaryDirectory() as repo_root:
            tools_dir = os.path.join(repo_root, "tools")
            os.makedirs(tools_dir)
            step_order = {
                "steps": ["00"],
                "coverage_thresholds": {
                    "fr_coverage": 80,
                    "mode": "warn",
                },
            }
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump(step_order, f)

            result = _load_coverage_thresholds(repo_root)
            assert isinstance(result, dict)
            self.assertEqual(result["fr_coverage"], 80)
            self.assertEqual(result["mode"], "warn")

    def test_returns_missing_file_sentinel_when_file_absent(self):
        """Returns _MISSING_FILE sentinel when step_order.json does not exist."""
        with tempfile.TemporaryDirectory() as repo_root:
            result = _load_coverage_thresholds(repo_root)
            self.assertIs(result, _MISSING_FILE)

    def test_returns_none_when_key_absent(self):
        """Returns None when coverage_thresholds key is absent from step_order.json."""
        with tempfile.TemporaryDirectory() as repo_root:
            tools_dir = os.path.join(repo_root, "tools")
            os.makedirs(tools_dir)
            step_order = {"steps": ["00"]}
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump(step_order, f)

            result = _load_coverage_thresholds(repo_root)
            self.assertIsNone(result)

    def test_returns_missing_file_sentinel_on_invalid_json(self):
        """Returns _MISSING_FILE sentinel when step_order.json contains invalid JSON."""
        with tempfile.TemporaryDirectory() as repo_root:
            tools_dir = os.path.join(repo_root, "tools")
            os.makedirs(tools_dir)
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                f.write("{not valid json")

            result = _load_coverage_thresholds(repo_root)
            self.assertIs(result, _MISSING_FILE)


# ===========================================================================
# Coverage-threshold enforcement
# ===========================================================================

class TestCheckCoverageThresholds(unittest.TestCase):
    """Tests for _check_coverage_thresholds enforcement logic."""

    # ------------------------------------------------------------------
    # 1. Coverage above threshold passes (no W592/E592)
    # ------------------------------------------------------------------
    def test_above_threshold_no_errors(self):
        """100% coverage with 80% threshold produces no diagnostics."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="warn")
            coverage = {"fr_total": 10, "fr_with_api": 10}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])

    def test_exactly_at_threshold_no_errors(self):
        """Coverage exactly at threshold (80%) produces no diagnostics."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="warn")
            coverage = {"fr_total": 10, "fr_with_api": 8}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])

    def test_above_threshold_error_mode_no_errors(self):
        """100% coverage in error mode also produces no diagnostics."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="error")
            coverage = {"fr_total": 5, "fr_with_api": 5}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])

    # ------------------------------------------------------------------
    # 2. Coverage below threshold in warn mode emits W592
    # ------------------------------------------------------------------
    def test_below_threshold_warn_mode_emits_w592(self):
        """50% coverage with 80% threshold in warn mode produces W592."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="warn")
            coverage = {"fr_total": 10, "fr_with_api": 5}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(len(errors), 1)
            self.assertIn("W592", errors[0].render())
            self.assertIn("COVERAGE_THRESHOLD_WARN", errors[0].render())
            self.assertIn("fr_coverage", errors[0].render())
            self.assertIn("50.0%", errors[0].render())
            self.assertIn("80%", errors[0].render())

    def test_below_threshold_warn_mode_zero_coverage(self):
        """0% coverage in warn mode still produces W592."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="warn")
            coverage = {"fr_total": 5, "fr_with_api": 0}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(len(errors), 1)
            self.assertIn("W592", errors[0].render())
            self.assertIn("0.0%", errors[0].render())

    # ------------------------------------------------------------------
    # 3. Coverage below threshold in error mode emits E592
    # ------------------------------------------------------------------
    def test_below_threshold_error_mode_emits_e592(self):
        """50% coverage with 80% threshold in error mode produces E592."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="error")
            coverage = {"fr_total": 10, "fr_with_api": 5}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(len(errors), 1)
            self.assertIn("E592", errors[0].render())
            self.assertIn("COVERAGE_THRESHOLD_BREACH", errors[0].render())
            self.assertIn("fr_coverage", errors[0].render())

    def test_below_threshold_error_mode_just_under(self):
        """79.9% coverage with 80% threshold in error mode produces E592."""
        with tempfile.TemporaryDirectory() as repo_root:
            # 799 out of 1000 = 79.9%
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="error")
            coverage = {"fr_total": 1000, "fr_with_api": 799}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(len(errors), 1)
            self.assertIn("E592", errors[0].render())

    # ------------------------------------------------------------------
    # 4. Missing config: file absent → skip; key absent → defaults apply
    # ------------------------------------------------------------------
    def test_missing_step_order_file_no_errors(self):
        """No step_order.json means no config, so no errors."""
        with tempfile.TemporaryDirectory() as repo_root:
            coverage = {"fr_total": 10, "fr_with_api": 0}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])

    def test_missing_coverage_thresholds_key_uses_defaults(self):
        """step_order.json without coverage_thresholds key applies defaults (80%, warn)."""
        with tempfile.TemporaryDirectory() as repo_root:
            tools_dir = os.path.join(repo_root, "tools")
            os.makedirs(tools_dir)
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump({"steps": ["00"]}, f)
            coverage = {"fr_total": 10, "fr_with_api": 0}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(len(errors), 1)
            self.assertIn("W592", errors[0].render())
            self.assertIn("COVERAGE_THRESHOLD_WARN", errors[0].render())
            self.assertIn("0.0%", errors[0].render())
            self.assertIn("80%", errors[0].render())

    def test_default_mode_is_warn(self):
        """When mode is absent from config, defaults to warn (W592, not E592)."""
        with tempfile.TemporaryDirectory() as repo_root:
            tools_dir = os.path.join(repo_root, "tools")
            os.makedirs(tools_dir)
            step_order = {
                "steps": ["00"],
                "coverage_thresholds": {
                    "fr_coverage": 80,
                    # mode intentionally omitted
                },
            }
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump(step_order, f)
            coverage = {"fr_total": 10, "fr_with_api": 5}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(len(errors), 1)
            self.assertIn("W592", errors[0].render())
            self.assertNotIn("E592", errors[0].render())

    # ------------------------------------------------------------------
    # 5. Zero fr_total produces no errors (avoids division by zero)
    # ------------------------------------------------------------------
    def test_zero_fr_total_no_errors(self):
        """fr_total=0 short-circuits with no errors (no division by zero)."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="error")
            coverage = {"fr_total": 0, "fr_with_api": 0}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])

    def test_zero_fr_total_with_warn_mode(self):
        """fr_total=0 in warn mode also produces no errors."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="warn")
            coverage = {"fr_total": 0, "fr_with_api": 0}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])

    def test_missing_fr_total_key_defaults_to_zero(self):
        """Coverage dict missing fr_total key defaults to 0, no errors."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="error")
            coverage = {}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])


# ===========================================================================
# Sentinels & defaults
# ===========================================================================

class TestSentinelsAndDefaults(unittest.TestCase):
    """Tests for _MISSING_FILE sentinel and _DEFAULT_COVERAGE_THRESHOLDS constants."""

    def test_missing_file_sentinel_is_not_none(self):
        """_MISSING_FILE is a unique sentinel distinct from None."""
        self.assertIsNotNone(_MISSING_FILE)
        self.assertIsNot(_MISSING_FILE, None)

    def test_default_coverage_thresholds_values(self):
        """_DEFAULT_COVERAGE_THRESHOLDS equals {'fr_coverage': 80, 'mode': 'warn'}."""
        self.assertEqual(
            _DEFAULT_COVERAGE_THRESHOLDS,
            {"fr_coverage": 80, "mode": "warn"},
        )


# ===========================================================================
# Milestone coverage
# ===========================================================================

class TestMilestoneCoverageInMatrixOutput(unittest.TestCase):
    """build_trace_matrix populates milestone_coverage when Step 14 data is present."""

    def test_milestone_coverage_key_present_when_step14_has_fr_refs(self):
        """milestone_coverage key exists when a Step 14 artifact with fr_refs is present."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = os.path.join(td, "spec")
            os.makedirs(spec_dir)
            roadmap = {
                "$schema": "https://example.com/schema/14-roadmap.json",
                "milestones": [
                    {
                        "milestone_id": "ms-v1",
                        "fr_refs": ["fr-login", "fr-auth"],
                        "tasks": [],
                    }
                ],
            }
            _write_spec_file(spec_dir, "14_roadmap.json", roadmap)

            result = build_trace_matrix(td, spec_dir)
            self.assertIn("milestone_coverage", result)

    def test_milestone_coverage_maps_frs_to_milestone_ids(self):
        """FR IDs map to the correct milestone IDs in milestone_coverage."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = os.path.join(td, "spec")
            os.makedirs(spec_dir)
            roadmap = {
                "$schema": "https://example.com/schema/14-roadmap.json",
                "milestones": [
                    {
                        "milestone_id": "ms-v1",
                        "fr_refs": ["fr-login", "fr-auth"],
                        "tasks": [],
                    },
                    {
                        "milestone_id": "ms-v2",
                        "fr_refs": ["fr-auth"],
                        "tasks": [],
                    },
                ],
            }
            _write_spec_file(spec_dir, "14_roadmap.json", roadmap)

            result = build_trace_matrix(td, spec_dir)
            mc = result.get("milestone_coverage", {})
            self.assertEqual(mc.get("fr-login"), ["ms-v1"])
            self.assertEqual(sorted(mc.get("fr-auth", [])), ["ms-v1", "ms-v2"])

    def test_milestone_coverage_includes_task_level_fr_refs(self):
        """FR refs at task level within milestones are included in milestone_coverage."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = os.path.join(td, "spec")
            os.makedirs(spec_dir)
            roadmap = {
                "$schema": "https://example.com/schema/14_roadmap.json",
                "milestones": [
                    {
                        "milestone_id": "ms-v1",
                        "fr_refs": [],
                        "tasks": [
                            {"task_id": "t-1", "fr_refs": ["fr-login"]},
                            {"task_id": "t-2", "fr_refs": ["fr-signup"]},
                        ],
                    }
                ],
            }
            _write_spec_file(spec_dir, "14_roadmap.json", roadmap)

            result = build_trace_matrix(td, spec_dir)
            mc = result.get("milestone_coverage", {})
            self.assertEqual(mc.get("fr-login"), ["ms-v1"])
            self.assertEqual(mc.get("fr-signup"), ["ms-v1"])

    def test_milestone_coverage_absent_when_no_step14(self):
        """milestone_coverage key is absent when no Step 14 artifact is present."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = os.path.join(td, "spec")
            os.makedirs(spec_dir)

            result = build_trace_matrix(td, spec_dir)
            self.assertNotIn("milestone_coverage", result)

    def test_milestone_coverage_sorted_milestone_ids(self):
        """Milestone IDs in milestone_coverage values are sorted."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = os.path.join(td, "spec")
            os.makedirs(spec_dir)
            roadmap = {
                "$schema": "https://example.com/schema/14-roadmap.json",
                "milestones": [
                    {"milestone_id": "ms-z", "fr_refs": ["fr-x"], "tasks": []},
                    {"milestone_id": "ms-a", "fr_refs": ["fr-x"], "tasks": []},
                    {"milestone_id": "ms-m", "fr_refs": ["fr-x"], "tasks": []},
                ],
            }
            _write_spec_file(spec_dir, "14_roadmap.json", roadmap)

            result = build_trace_matrix(td, spec_dir)
            mc = result.get("milestone_coverage", {})
            self.assertEqual(mc.get("fr-x"), ["ms-a", "ms-m", "ms-z"])


# ===========================================================================
# Entity deduplication
# ===========================================================================

class TestEntityDedup(unittest.TestCase):
    """Entity dedup during build_trace_matrix entity collection."""

    def test_duplicate_fr_dedup(self):
        """FR appearing in two different list arrays across two files is counted once."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = os.path.join(td, "spec")
            os.makedirs(spec_dir)

            fr_obj = {
                "fr_id": "fr-login",
                "statement": "User can log in",
                "acceptance_criteria": ["Given valid creds, login succeeds"],
                "priority": "must-have",
            }
            _write_spec_file(spec_dir, "04_fr_list.json", {
                "$schema": "vc:step:04",
                "functional_requirements": [fr_obj],
            })
            # Same fr_id object repeated in a second file/array
            _write_spec_file(spec_dir, "05_interface_contracts.json", {
                "$schema": "vc:step:05",
                "out_of_scope": [fr_obj],
            })

            result = build_trace_matrix(td, spec_dir)
            self.assertEqual(result["coverage"]["fr_total"], 1)
            fr_ids_in_matrix = [row["fr_id"] for row in result.get("matrix", [])]
            self.assertEqual(len(fr_ids_in_matrix), len(set(fr_ids_in_matrix)))

    def test_aliased_trace_type_dedup(self):
        """FR appearing as entity in one file and reference object in another is counted once."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = os.path.join(td, "spec")
            os.makedirs(spec_dir)

            fr_obj = {
                "fr_id": "fr-login",
                "statement": "User can log in",
                "acceptance_criteria": ["Given valid creds, login succeeds"],
                "priority": "must-have",
            }
            _write_spec_file(spec_dir, "04_fr_list.json", {
                "$schema": "vc:step:04",
                "functional_requirements": [fr_obj],
            })
            # fr_id referenced inside a linked_requirements object in another step
            _write_spec_file(spec_dir, "07_nfrs.json", {
                "$schema": "vc:step:07",
                "nfrs": [],
                "linked_requirements": [{"fr_id": "fr-login", "rationale": "perf target"}],
            })

            result = build_trace_matrix(td, spec_dir)
            self.assertEqual(result["coverage"]["fr_total"], 1)
            fr_ids = [row["fr_id"] for row in result.get("matrix", [])]
            self.assertEqual(fr_ids, ["fr-login"])

    def test_no_false_dedup(self):
        """Two genuinely different FRs both appear in the matrix."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = os.path.join(td, "spec")
            os.makedirs(spec_dir)

            _write_spec_file(spec_dir, "04_fr_list.json", {
                "$schema": "vc:step:04",
                "functional_requirements": [
                    {
                        "fr_id": "fr-login",
                        "statement": "User can log in",
                        "acceptance_criteria": ["Given valid creds, login succeeds"],
                        "priority": "must-have",
                    },
                    {
                        "fr_id": "fr-logout",
                        "statement": "User can log out",
                        "acceptance_criteria": ["Session is terminated"],
                        "priority": "must-have",
                    },
                ],
            })

            result = build_trace_matrix(td, spec_dir)
            self.assertEqual(result["coverage"]["fr_total"], 2)
            fr_ids_in_matrix = [row["fr_id"] for row in result.get("matrix", [])]
            self.assertIn("fr-login", fr_ids_in_matrix)
            self.assertIn("fr-logout", fr_ids_in_matrix)


# ===========================================================================
# fr_coverage denominator exclusions (DEVSPEC-122 follow-up)
# ===========================================================================

class TestFrCoverageDenominatorExclusions(unittest.TestCase):
    """wont-have FRs and Step-05 out-of-scope FRs are excluded from fr_total and
    the fr_with_* numerators -- otherwise either category silently drags down
    fr_coverage and can fail SPECDEV_MATRIX_STRICT=1 CI, even though they were
    never expected to have an API/fixture/threat by design."""

    def test_wont_have_fr_excluded_from_fr_total(self):
        result = _run_matrix(frs=[
            {"fr_id": "fr-must", "priority": "must-have"},
            {"fr_id": "fr-parked", "priority": "wont-have"},
        ])
        self.assertEqual(result["coverage"]["fr_total"], 1)

    def test_wont_have_fr_excluded_from_fr_with_api_numerator(self):
        """A wont-have FR that (unusually) still has an API trace must not
        inflate fr_with_api once it's excluded from the denominator."""
        result = _run_matrix(
            frs=[
                {"fr_id": "fr-must", "priority": "must-have"},
                {"fr_id": "fr-parked", "priority": "wont-have"},
            ],
            apis=[_api("api-legacy", ["fr-parked"])],
        )
        self.assertEqual(result["coverage"]["fr_total"], 1)
        self.assertEqual(result["coverage"]["fr_with_api"], 0)

    def test_step05_out_of_scope_fr_excluded_from_fr_total(self):
        result = _run_matrix(
            frs=[
                {"fr_id": "fr-must", "priority": "must-have"},
                {"fr_id": "fr-infra", "priority": "must-have"},
            ],
            out_of_scope=[{"fr_id": "fr-infra", "rationale": "Background job — no HTTP API surface."}],
        )
        self.assertEqual(result["coverage"]["fr_total"], 1)

    def test_out_of_scope_entry_without_rationale_does_not_exclude(self):
        """An out_of_scope entry missing rationale is not an acknowledged
        exemption -- must not exclude the FR (mirrors traceability_closure.py's
        own requirement that rationale be present)."""
        result = _run_matrix(
            frs=[{"fr_id": "fr-infra", "priority": "must-have"}],
            out_of_scope=[{"fr_id": "fr-infra"}],
        )
        self.assertEqual(result["coverage"]["fr_total"], 1)

    def test_control_normal_frs_all_counted(self):
        """Control: with no wont-have or out-of-scope FRs, fr_total counts everything."""
        result = _run_matrix(frs=[
            {"fr_id": "fr-a", "priority": "must-have"},
            {"fr_id": "fr-b", "priority": "should-have"},
        ])
        self.assertEqual(result["coverage"]["fr_total"], 2)

    def test_step08_fixture_out_of_scope_excluded_from_fixture_total_not_api_total(self):
        """Step 08's out_of_scope[] is a separate exemption from Step 05's -- an
        FR with no fixture expected must not drag down fr_with_fixture's ratio,
        but it still needs an API, so fr_total (the fr_with_api denominator)
        must NOT exclude it."""
        result = _run_matrix(
            frs=[
                {"fr_id": "fr-must", "priority": "must-have"},
                {"fr_id": "fr-no-fixture", "priority": "must-have"},
            ],
            fixture_out_of_scope=[
                {"fr_id": "fr-no-fixture", "rationale": "Pure computation -- no test fixture needed."}
            ],
        )
        self.assertEqual(result["coverage"]["fr_total"], 2)
        self.assertEqual(result["coverage"]["fr_total_fixture"], 1)

    def test_step05_out_of_scope_excluded_from_api_total_not_fixture_total(self):
        """Mirror-image control: a Step 05 API exemption must not exclude the FR
        from fr_total_fixture (fr_with_fixture's denominator) -- it may still
        need a fixture even with no HTTP API surface."""
        result = _run_matrix(
            frs=[
                {"fr_id": "fr-must", "priority": "must-have"},
                {"fr_id": "fr-no-api", "priority": "must-have"},
            ],
            out_of_scope=[
                {"fr_id": "fr-no-api", "rationale": "Background job -- no HTTP API surface."}
            ],
        )
        self.assertEqual(result["coverage"]["fr_total"], 1)
        self.assertEqual(result["coverage"]["fr_total_fixture"], 2)


# ===========================================================================
# FR→API link building  (Bug #1 regression gate)
# ===========================================================================

class TestFRToAPILinkBuilding(unittest.TestCase):
    """APIs carry the authoritative FR trace; the matrix must be built from the API side.

    FRs trace to capabilities, not APIs.  Each API lists the FRs it implements
    in its own ``trace`` array.  These tests guard against regressions where
    the link direction is reversed (iterating FR traces instead of API traces).
    """

    def test_api_fr_trace_populates_matrix_row(self):
        """API tracing to an FR causes that FR's matrix row to list the API."""
        result = _run_matrix(
            frs=[_fr("fr-login")],
            apis=[_api("api-session", ["fr-login"])],
        )
        self.assertEqual(_row(result, "fr-login")["apis"], ["api-session"])

    def test_fr_with_no_api_trace_still_linked_when_api_traces_back(self):
        """FR without an api-type trace entry still gets linked when its API traces to it."""
        # This is the key regression scenario: FR traces only to capability, never to API.
        fr = {"fr_id": "fr-publish"}   # no trace field at all
        result = _run_matrix(
            frs=[fr],
            apis=[_api("api-post", ["fr-publish"])],
        )
        self.assertEqual(_row(result, "fr-publish")["apis"], ["api-post"])

    def test_one_api_multiple_frs(self):
        """API tracing to multiple FRs assigns itself to all of them."""
        result = _run_matrix(
            frs=[_fr("fr-read"), _fr("fr-search")],
            apis=[_api("api-list", ["fr-read", "fr-search"])],
        )
        self.assertEqual(_row(result, "fr-read")["apis"], ["api-list"])
        self.assertEqual(_row(result, "fr-search")["apis"], ["api-list"])

    def test_multiple_apis_same_fr(self):
        """FR is linked to all APIs that trace to it."""
        result = _run_matrix(
            frs=[_fr("fr-auth")],
            apis=[
                _api("api-login", ["fr-auth"]),
                _api("api-logout", ["fr-auth"]),
            ],
        )
        self.assertEqual(_row(result, "fr-auth")["apis"], ["api-login", "api-logout"])

    def test_fr_not_traced_by_any_api_has_empty_apis(self):
        """FR that no API traces to has an empty apis list in its matrix row."""
        result = _run_matrix(
            frs=[_fr("fr-orphan")],
            apis=[_api("api-other", ["fr-other"])],
        )
        self.assertEqual(_row(result, "fr-orphan")["apis"], [])


# ===========================================================================
# Fixture cascade via API  (Bug #2 regression gate)
# ===========================================================================

class TestFixtureCascadeViaAPI(unittest.TestCase):
    """Fixtures reach FR rows through the FR→API→Fixture chain."""

    def test_fixture_reaches_fr_via_api(self):
        """Fixture targeting API appears in FR row when API traces to that FR."""
        result = _run_matrix(
            frs=[_fr("fr-login")],
            apis=[_api("api-session", ["fr-login"])],
            fixtures=[_fixture("fx-session-create", ["api-session"])],
        )
        self.assertIn("fx-session-create", _row(result, "fr-login")["fixtures"])

    def test_fixture_absent_for_unlinked_fr(self):
        """FR with no API tracing to it has an empty fixtures list."""
        result = _run_matrix(
            frs=[_fr("fr-orphan"), _fr("fr-linked")],
            apis=[_api("api-x", ["fr-linked"])],
            fixtures=[_fixture("fx-x", ["api-x"])],
        )
        self.assertEqual(_row(result, "fr-orphan")["fixtures"], [])

    def test_fixture_targets_correct_fr_only(self):
        """Fixture linked to one API appears only in FR rows that API covers."""
        result = _run_matrix(
            frs=[_fr("fr-a"), _fr("fr-b")],
            apis=[_api("api-a", ["fr-a"]), _api("api-b", ["fr-b"])],
            fixtures=[_fixture("fx-only-b", ["api-b"])],
        )
        self.assertNotIn("fx-only-b", _row(result, "fr-a")["fixtures"])
        self.assertIn("fx-only-b", _row(result, "fr-b")["fixtures"])


# ===========================================================================
# Threat cascade via API  (Bug #3 regression gate)
# ===========================================================================

class TestThreatCascadeViaAPI(unittest.TestCase):
    """Threats reach FR rows through the FR→API→Threat chain."""

    def test_threat_reaches_fr_via_api(self):
        """Threat targeting API appears in FR row when API traces to that FR."""
        result = _run_matrix(
            frs=[_fr("fr-auth")],
            apis=[_api("api-session", ["fr-auth"])],
            threats=[_threat("th-brute-force", ["api-session"])],
        )
        self.assertIn("th-brute-force", _row(result, "fr-auth")["threats"])

    def test_threat_absent_for_unlinked_fr(self):
        """FR with no API tracing to it has an empty threats list."""
        result = _run_matrix(
            frs=[_fr("fr-orphan"), _fr("fr-linked")],
            apis=[_api("api-y", ["fr-linked"])],
            threats=[_threat("th-y", ["api-y"])],
        )
        self.assertEqual(_row(result, "fr-orphan")["threats"], [])

    def test_threat_targets_correct_fr_only(self):
        """Threat linked to one API appears only in FR rows that API covers."""
        result = _run_matrix(
            frs=[_fr("fr-a"), _fr("fr-b")],
            apis=[_api("api-a", ["fr-a"]), _api("api-b", ["fr-b"])],
            threats=[_threat("th-only-b", ["api-b"])],
        )
        self.assertNotIn("th-only-b", _row(result, "fr-a")["threats"])
        self.assertIn("th-only-b", _row(result, "fr-b")["threats"])


# ===========================================================================
# NFR linking  (direct FR trace + indirect API trace)
# ===========================================================================

class TestNFRLinking(unittest.TestCase):
    """NFRs reach FR rows via direct FR trace or indirectly through an API."""

    def test_nfr_direct_fr_trace_appears_in_nfrs(self):
        """NFR with trace.type=fr directly populates the FR's nfrs list."""
        result = _run_matrix(
            frs=[_fr("fr-perf")],
            nfrs=[_nfr("nfr-latency", fr_ids=["fr-perf"])],
        )
        self.assertIn("nfr-latency", _row(result, "fr-perf")["nfrs"])

    def test_nfr_via_api_appears_in_nfrs(self):
        """NFR tracing to an API appears in FR rows for FRs linked to that API."""
        result = _run_matrix(
            frs=[_fr("fr-auth")],
            apis=[_api("api-session", ["fr-auth"])],
            nfrs=[_nfr("nfr-tls", api_ids=["api-session"])],
        )
        self.assertIn("nfr-tls", _row(result, "fr-auth")["nfrs"])

    def test_nfr_direct_and_indirect_both_surface(self):
        """FR collects NFRs from both a direct FR trace and an API-indirect trace."""
        result = _run_matrix(
            frs=[_fr("fr-auth")],
            apis=[_api("api-session", ["fr-auth"])],
            nfrs=[
                _nfr("nfr-direct", fr_ids=["fr-auth"]),
                _nfr("nfr-indirect", api_ids=["api-session"]),
            ],
        )
        nfrs = _row(result, "fr-auth")["nfrs"]
        self.assertIn("nfr-direct", nfrs)
        self.assertIn("nfr-indirect", nfrs)

    def test_nfr_absent_for_fr_with_no_nfr_link(self):
        """FR with no NFR traces has an empty nfrs list."""
        result = _run_matrix(
            frs=[_fr("fr-orphan")],
            nfrs=[_nfr("nfr-other", fr_ids=["fr-other"])],
        )
        self.assertEqual(_row(result, "fr-orphan")["nfrs"], [])


if __name__ == "__main__":
    unittest.main()
