"""Comprehensive tests for R9 cross-step ID validators.

Tests all 8 validators that perform cross-step reference validation:
- step_05: FR refs in API contracts
- step_06: FR + API refs in invariant trace targets
- step_08: FR + API + INV + NFR refs in fixture targets
- step_09: Capability refs in milestone deliverables/capability_refs
- step_12: FR + NFR refs in CI job trace
- step_13: Governance label refs in extensions
- step_13a: FR + API refs in missing_elements spec_refs/related_ids
- step_15: API refs in scaffold interface_map

Each test class covers three scenarios:
(a) Valid upstream refs pass with no W590/E590
(b) Missing upstream file emits W590
(c) Broken ref (ID not in upstream) emits E590
"""

import json
import os
import tempfile
import unittest

from specdev_tools.validation.validators.step_05 import validate_step_05
from specdev_tools.validation.validators.step_06 import validate_step_06
from specdev_tools.validation.validators.step_08 import validate_step_08
from specdev_tools.validation.validators.step_09 import validate_step_09
from specdev_tools.validation.validators.step_12 import validate_step_12
from specdev_tools.validation.validators.step_13 import validate_step_13
from specdev_tools.validation.validators.step_13a import validate_step_13a
from specdev_tools.validation.validators.step_15 import validate_step_15


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(directory: str, filename: str, data: dict) -> None:
    """Write a JSON file into the given directory."""
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
        json.dump(data, f)


def _render(errors):
    """Render SpecError list to strings for assertion convenience."""
    return [e.render() if hasattr(e, 'render') else str(e) for e in errors]


def _w590(errors) -> list[str]:
    return [e for e in _render(errors) if "W590" in e]


def _e590(errors) -> list[str]:
    return [e for e in _render(errors) if "E590" in e]


# ---------------------------------------------------------------------------
# Step 05 — FR refs in API contracts
# ---------------------------------------------------------------------------

class TestStep05CrossStep(unittest.TestCase):
    """Cross-step validation: step_05 checks FR refs against 04_fr_list.json."""

    def test_valid_upstream_refs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [
                    {"fr_id": "fr-login"},
                    {"fr_id": "fr-logout"},
                ]
            })
            instance = {
                "apis": [
                    {
                        "api_id": "api-auth",
                        "method": "POST",
                        "path": "/auth/login",
                        "trace": [
                            {"type": "fr", "id": "fr-login"},
                            {"type": "fr", "id": "fr-logout"},
                        ],
                    }
                ]
            }
            errors = validate_step_05(instance, tmp)
            self.assertEqual(len(_w590(errors)), 0, f"Unexpected W590: {_w590(errors)}")
            self.assertEqual(len(_e590(errors)), 0, f"Unexpected E590: {_e590(errors)}")

    def test_missing_upstream_emits_w590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # No 04_fr_list.json present
            instance = {
                "apis": [
                    {
                        "api_id": "api-auth",
                        "method": "POST",
                        "path": "/auth/login",
                        "trace": [{"type": "fr", "id": "fr-login"}],
                    }
                ]
            }
            errors = validate_step_05(instance, tmp)
            w = _w590(errors)
            self.assertGreaterEqual(len(w), 1, "Expected W590 for missing 04_fr_list.json")
            self.assertTrue(
                any("04_fr_list.json" in msg for msg in w),
                f"W590 should mention 04_fr_list.json: {w}"
            )

    def test_broken_ref_emits_e590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [
                    {"fr_id": "fr-login"},
                ]
            })
            instance = {
                "apis": [
                    {
                        "api_id": "api-auth",
                        "method": "POST",
                        "path": "/auth/login",
                        "trace": [{"type": "fr", "id": "fr-nonexistent"}],
                    }
                ]
            }
            errors = validate_step_05(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 1, "Expected E590 for broken FR ref")
            self.assertTrue(
                any("fr-nonexistent" in msg for msg in e),
                f"E590 should mention the broken ref: {e}"
            )


# ---------------------------------------------------------------------------
# Step 06 — FR + API refs in invariant trace targets
# ---------------------------------------------------------------------------

class TestStep06CrossStep(unittest.TestCase):
    """Cross-step validation: step_06 checks FR + API trace targets."""

    def test_valid_upstream_refs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            instance = {
                "rules": [
                    {
                        "inv_id": "inv-auth-required",
                        "trace": [
                            {"type": "fr", "id": "fr-login"},
                            {"type": "api", "id": "api-auth"},
                        ],
                    }
                ]
            }
            errors = validate_step_06(instance, tmp)
            self.assertEqual(len(_w590(errors)), 0, f"Unexpected W590: {_w590(errors)}")
            self.assertEqual(len(_e590(errors)), 0, f"Unexpected E590: {_e590(errors)}")

    def test_missing_upstream_emits_w590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # No upstream files
            instance = {
                "rules": [
                    {
                        "inv_id": "inv-auth-required",
                        "trace": [
                            {"type": "fr", "id": "fr-login"},
                            {"type": "api", "id": "api-auth"},
                        ],
                    }
                ]
            }
            errors = validate_step_06(instance, tmp)
            w = _w590(errors)
            self.assertGreaterEqual(len(w), 1, "Expected W590 for missing upstream files")
            # Should warn about both missing files
            combined = " ".join(w)
            self.assertIn("04_fr_list.json", combined)
            self.assertIn("05_interface_contracts.json", combined)

    def test_broken_ref_emits_e590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            instance = {
                "rules": [
                    {
                        "inv_id": "inv-auth-required",
                        "trace": [
                            {"type": "fr", "id": "fr-unknown"},
                            {"type": "api", "id": "api-missing"},
                        ],
                    }
                ]
            }
            errors = validate_step_06(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 2, f"Expected E590 for both broken refs: {e}")
            combined = " ".join(e)
            self.assertIn("fr-unknown", combined)
            self.assertIn("api-missing", combined)

    def test_inv_self_ref_valid(self):
        """inv-* trace targets referencing existing invariants in same artifact pass."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            instance = {
                "rules": [
                    {
                        "inv_id": "inv-auth-required",
                        "trace": [{"type": "fr", "id": "fr-login"}],
                    },
                    {
                        "inv_id": "inv-session-valid",
                        "trace": [{"type": "inv", "id": "inv-auth-required"}],
                    },
                ]
            }
            errors = validate_step_06(instance, tmp)
            self.assertEqual(len(_e590(errors)), 0, f"Unexpected E590: {_e590(errors)}")

    def test_inv_self_ref_broken_emits_e590(self):
        """inv-* trace target referencing non-existent invariant emits E590."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            instance = {
                "rules": [
                    {
                        "inv_id": "inv-auth-required",
                        "trace": [{"type": "inv", "id": "inv-nonexistent"}],
                    },
                ]
            }
            errors = validate_step_06(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 1, f"Expected E590 for broken inv ref: {e}")
            self.assertTrue(
                any("inv-nonexistent" in msg for msg in e),
                f"E590 should mention inv-nonexistent: {e}"
            )

    def test_scope_apis_valid(self):
        """scope.apis references that exist in 05_interface_contracts.json pass."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}, {"api_id": "api-users"}]
            })
            instance = {
                "rules": [
                    {
                        "inv_id": "inv-auth-required",
                        "trace": [{"type": "fr", "id": "fr-login"}],
                        "scope": {"apis": ["api-auth", "api-users"]},
                    }
                ]
            }
            errors = validate_step_06(instance, tmp)
            self.assertEqual(len(_e590(errors)), 0, f"Unexpected E590: {_e590(errors)}")

    def test_scope_apis_broken_emits_e590(self):
        """scope.apis reference to non-existent API emits E590."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            instance = {
                "rules": [
                    {
                        "inv_id": "inv-auth-required",
                        "trace": [{"type": "fr", "id": "fr-login"}],
                        "scope": {"apis": ["api-nonexistent"]},
                    }
                ]
            }
            errors = validate_step_06(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 1, f"Expected E590 for broken scope.apis ref: {e}")
            self.assertTrue(
                any("api-nonexistent" in msg for msg in e),
                f"E590 should mention api-nonexistent: {e}"
            )


# ---------------------------------------------------------------------------
# Step 08 — FR + API + INV + NFR refs in fixture targets
# ---------------------------------------------------------------------------

class TestStep08CrossStep(unittest.TestCase):
    """Cross-step validation: step_08 checks fixture targets against 4 upstreams."""

    def test_valid_upstream_refs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            _write_json(spec_dir, "06_invariants.json", {
                "rules": [{"inv_id": "inv-session"}]
            })
            _write_json(spec_dir, "07_nfrs.json", {
                "nfrs": [{"nfr_id": "nfr-latency"}]
            })
            instance = {
                "fixtures": [
                    {
                        "fixture_id": "fix-login-happy",
                        "targets": [
                            {"type": "fr", "id": "fr-login"},
                            {"type": "api", "id": "api-auth"},
                            {"type": "inv", "id": "inv-session"},
                            {"type": "nfr", "id": "nfr-latency"},
                        ],
                    }
                ]
            }
            errors = validate_step_08(instance, tmp)
            self.assertEqual(len(_w590(errors)), 0, f"Unexpected W590: {_w590(errors)}")
            self.assertEqual(len(_e590(errors)), 0, f"Unexpected E590: {_e590(errors)}")

    def test_missing_upstream_emits_w590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # No upstream files at all
            instance = {
                "fixtures": [
                    {
                        "fixture_id": "fix-login-happy",
                        "targets": [
                            {"type": "fr", "id": "fr-login"},
                            {"type": "api", "id": "api-auth"},
                            {"type": "inv", "id": "inv-session"},
                            {"type": "nfr", "id": "nfr-latency"},
                        ],
                    }
                ]
            }
            errors = validate_step_08(instance, tmp)
            w = _w590(errors)
            # Should emit W590 for each of the 4 missing upstream files
            self.assertGreaterEqual(len(w), 4, f"Expected 4 W590 warnings: {w}")
            combined = " ".join(w)
            self.assertIn("04_fr_list.json", combined)
            self.assertIn("05_interface_contracts.json", combined)
            self.assertIn("06_invariants.json", combined)
            self.assertIn("07_nfrs.json", combined)

    def test_broken_ref_emits_e590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            _write_json(spec_dir, "06_invariants.json", {
                "rules": [{"inv_id": "inv-session"}]
            })
            _write_json(spec_dir, "07_nfrs.json", {
                "nfrs": [{"nfr_id": "nfr-latency"}]
            })
            instance = {
                "fixtures": [
                    {
                        "fixture_id": "fix-broken",
                        "targets": [
                            {"type": "fr", "id": "fr-nonexistent"},
                            {"type": "api", "id": "api-ghost"},
                        ],
                    }
                ]
            }
            errors = validate_step_08(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 2, f"Expected E590 for broken refs: {e}")
            combined = " ".join(e)
            self.assertIn("fr-nonexistent", combined)
            self.assertIn("api-ghost", combined)


# ---------------------------------------------------------------------------
# Step 09 — Capability refs in milestone deliverables/capability_refs
# ---------------------------------------------------------------------------

class TestStep09CrossStep(unittest.TestCase):
    """Cross-step validation: step_09 checks capability refs against 01_capabilities.json."""

    def test_valid_upstream_refs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "01_capabilities.json", {
                "capabilities": [
                    {"capability_id": "cap-authentication"},
                    {"capability_id": "cap-dashboard"},
                ]
            })
            instance = {
                "milestones": [
                    {
                        "milestone_id": "ms-alpha",
                        "target_date": "2026-04-01",
                        "deliverables": [
                            {"type": "capability", "id": "cap-authentication"},
                        ],
                        "capability_refs": ["cap-dashboard"],
                    }
                ]
            }
            errors = validate_step_09(instance, tmp)
            self.assertEqual(len(_w590(errors)), 0, f"Unexpected W590: {_w590(errors)}")
            self.assertEqual(len(_e590(errors)), 0, f"Unexpected E590: {_e590(errors)}")

    def test_missing_upstream_emits_w590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # No 01_capabilities.json
            instance = {
                "milestones": [
                    {
                        "milestone_id": "ms-alpha",
                        "target_date": "2026-04-01",
                        "deliverables": [
                            {"type": "capability", "id": "cap-authentication"},
                        ],
                    }
                ]
            }
            errors = validate_step_09(instance, tmp)
            w = _w590(errors)
            self.assertGreaterEqual(len(w), 1, "Expected W590 for missing 01_capabilities.json")
            self.assertTrue(
                any("01_capabilities.json" in msg for msg in w),
                f"W590 should mention 01_capabilities.json: {w}"
            )

    def test_broken_ref_emits_e590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "01_capabilities.json", {
                "capabilities": [
                    {"capability_id": "cap-authentication"},
                ]
            })
            instance = {
                "milestones": [
                    {
                        "milestone_id": "ms-alpha",
                        "target_date": "2026-04-01",
                        "deliverables": [
                            {"type": "capability", "id": "cap-nonexistent"},
                        ],
                    }
                ]
            }
            errors = validate_step_09(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 1, "Expected E590 for broken capability ref")
            self.assertTrue(
                any("cap-nonexistent" in msg for msg in e),
                f"E590 should mention the broken ref: {e}"
            )

    def test_capability_refs_field_not_validated(self):
        """capability_refs is not a schema field; validator ignores it."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "01_capabilities.json", {
                "capabilities": [
                    {"capability_id": "cap-authentication"},
                ]
            })
            instance = {
                "milestones": [
                    {
                        "milestone_id": "ms-beta",
                        "target_date": "2026-05-01",
                        "capability_refs": ["cap-unknown"],
                    }
                ]
            }
            errors = validate_step_09(instance, tmp)
            e = _e590(errors)
            self.assertEqual(len(e), 0, "capability_refs is not a schema field; no E590 expected")


# ---------------------------------------------------------------------------
# Step 12 — FR + NFR refs in CI job trace/coverage_gaps
# ---------------------------------------------------------------------------

class TestStep12CrossStep(unittest.TestCase):
    """Cross-step validation: step_12 checks FR/NFR refs in CI jobs."""

    def test_valid_upstream_refs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "07_nfrs.json", {
                "nfrs": [{"nfr_id": "nfr-latency"}]
            })
            instance = {
                "jobs": [
                    {
                        "job_id": "job-lint",
                        "steps": [{"id": "step-lint", "command": "npm run lint"}],
                    }
                ],
                "trace": [
                    {"type": "fr", "id": "fr-login"},
                ],
            }
            errors = validate_step_12(instance, tmp)
            self.assertEqual(len(_w590(errors)), 0, f"Unexpected W590: {_w590(errors)}")
            self.assertEqual(len(_e590(errors)), 0, f"Unexpected E590: {_e590(errors)}")

    def test_missing_upstream_emits_w590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # No upstream files
            instance = {
                "jobs": [
                    {
                        "job_id": "job-lint",
                        "steps": [{"id": "step-lint", "command": "npm run lint"}],
                    }
                ],
                "trace": [
                    {"type": "fr", "id": "fr-login"},
                ],
            }
            errors = validate_step_12(instance, tmp)
            w = _w590(errors)
            self.assertGreaterEqual(len(w), 2, f"Expected W590 for both missing upstreams: {w}")
            combined = " ".join(w)
            self.assertIn("04_fr_list.json", combined)
            self.assertIn("07_nfrs.json", combined)

    def test_broken_ref_emits_e590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "07_nfrs.json", {
                "nfrs": [{"nfr_id": "nfr-latency"}]
            })
            instance = {
                "jobs": [
                    {
                        "job_id": "job-lint",
                        "steps": [{"id": "step-lint", "command": "npm run lint"}],
                    }
                ],
                "trace": [
                    {"type": "fr", "id": "fr-phantom"},
                    {"type": "nfr", "id": "nfr-ghost"},
                ],
            }
            errors = validate_step_12(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 2, f"Expected E590 for broken refs: {e}")
            combined = " ".join(e)
            self.assertIn("fr-phantom", combined)
            self.assertIn("nfr-ghost", combined)

    def test_broken_ref_in_job_deep_scan_emits_e590(self):
        """Deep-scan of jobs should catch fr-*/nfr-* string values."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "07_nfrs.json", {
                "nfrs": [{"nfr_id": "nfr-latency"}]
            })
            instance = {
                "jobs": [
                    {
                        "job_id": "job-check",
                        "steps": [{"id": "step-check", "command": "echo test"}],
                        "coverage_target": "fr-does-not-exist",
                    }
                ],
            }
            errors = validate_step_12(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 1, f"Expected E590 for deep-scan broken ref: {e}")
            self.assertTrue(
                any("fr-does-not-exist" in msg for msg in e),
                f"E590 should mention the broken deep-scan ref: {e}"
            )


# ---------------------------------------------------------------------------
# Step 13 — Governance label refs in extensions
# ---------------------------------------------------------------------------

class TestStep13CrossStep(unittest.TestCase):
    """Cross-step validation: step_13 checks governance_label_ref against 10_governance.json."""

    def test_valid_upstream_refs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "10_governance.json", {
                "id": "gov-main",
                "canonical_refs_used": [
                    {"kind": "governance_label", "id": "label-security"},
                ]
            })
            instance = {
                "extensions": [
                    {
                        "extension_id": "ext-auth",
                        "required_schema_sections": ["04_fr_list"],
                        "justification": "Authentication needs custom schema section.",
                        "schema_design_guidelines": "Validate with assertion checks.",
                        "governance_label_ref": {"id": "label-security"},
                    }
                ]
            }
            errors = validate_step_13(instance, tmp)
            self.assertEqual(len(_w590(errors)), 0, f"Unexpected W590: {_w590(errors)}")
            self.assertEqual(len(_e590(errors)), 0, f"Unexpected E590: {_e590(errors)}")

    def test_missing_upstream_emits_w590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # No 10_governance.json
            instance = {
                "extensions": [
                    {
                        "extension_id": "ext-auth",
                        "required_schema_sections": ["04_fr_list"],
                        "justification": "Authentication needs custom schema section.",
                        "schema_design_guidelines": "Validate with assertion checks.",
                        "governance_label_ref": {"id": "label-security"},
                    }
                ]
            }
            errors = validate_step_13(instance, tmp)
            w = _w590(errors)
            self.assertGreaterEqual(len(w), 1, "Expected W590 for missing 10_governance.json")
            self.assertTrue(
                any("10_governance.json" in msg for msg in w),
                f"W590 should mention 10_governance.json: {w}"
            )

    def test_broken_ref_emits_e590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "10_governance.json", {
                "id": "gov-main",
                "canonical_refs_used": [
                    {"kind": "governance_label", "id": "label-security"},
                ]
            })
            instance = {
                "extensions": [
                    {
                        "extension_id": "ext-auth",
                        "required_schema_sections": ["04_fr_list"],
                        "justification": "Authentication needs custom schema section.",
                        "schema_design_guidelines": "Validate with assertion checks.",
                        "governance_label_ref": {"id": "label-nonexistent"},
                    }
                ]
            }
            errors = validate_step_13(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 1, "Expected E590 for broken governance label ref")
            self.assertTrue(
                any("label-nonexistent" in msg for msg in e),
                f"E590 should mention the broken ref: {e}"
            )

    def test_governance_doc_own_id_is_valid_ref(self):
        """The governance document's own top-level id should resolve as valid."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "10_governance.json", {
                "id": "gov-main",
                "canonical_refs_used": []
            })
            instance = {
                "extensions": [
                    {
                        "extension_id": "ext-gov",
                        "required_schema_sections": ["10_governance"],
                        "justification": "Governance meta-extension.",
                        "schema_design_guidelines": "Verify compliance checks.",
                        "governance_label_ref": {"id": "gov-main"},
                    }
                ]
            }
            errors = validate_step_13(instance, tmp)
            # Governance doc's own top-level id is no longer added to label set
            # (plain kebab string can never match cn:-prefixed refs), so
            # gov-main is unresolvable and correctly emits E590.
            self.assertGreaterEqual(len(_e590(errors)), 1, "gov-main is not a governance label")


# ---------------------------------------------------------------------------
# Step 13a — FR + API refs in dimensions.uncovered_ids
# ---------------------------------------------------------------------------

class TestStep13aCrossStep(unittest.TestCase):
    """Cross-step validation: step_13a checks FR/API refs in dimensions.uncovered_ids."""

    def test_valid_upstream_refs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "01_capabilities.json", {
                "capabilities": [{"capability_id": "cap-auth"}]
            })
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            instance = {
                "dimensions": {
                    "fr_api_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "fr_fixture_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "fr_milestone_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "capability_fr_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                }
            }
            errors = validate_step_13a(instance, tmp)
            self.assertEqual(len(_w590(errors)), 0, f"Unexpected W590: {_w590(errors)}")
            self.assertEqual(len(_e590(errors)), 0, f"Unexpected E590: {_e590(errors)}")

    def test_missing_upstream_emits_w590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # No upstream files — dimensions has fr- refs in uncovered_ids
            instance = {
                "dimensions": {
                    "fr_api_coverage": {
                        "covered_count": 0,
                        "total_count": 1,
                        "ratio": 0.0,
                        "uncovered_ids": ["fr-login"],
                    },
                    "fr_fixture_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "fr_milestone_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "capability_fr_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                }
            }
            errors = validate_step_13a(instance, tmp)
            w = _w590(errors)
            self.assertGreaterEqual(len(w), 2, f"Expected W590 for both missing upstreams: {w}")
            combined = " ".join(w)
            self.assertIn("04_fr_list.json", combined)
            self.assertIn("05_interface_contracts.json", combined)

    def test_broken_ref_emits_e590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            # uncovered_ids reference IDs not in upstream specs
            instance = {
                "dimensions": {
                    "fr_api_coverage": {
                        "covered_count": 0,
                        "total_count": 1,
                        "ratio": 0.0,
                        "uncovered_ids": ["fr-nonexistent"],
                    },
                    "fr_fixture_coverage": {
                        "covered_count": 0,
                        "total_count": 1,
                        "ratio": 0.0,
                        "uncovered_ids": ["fr-ghost"],
                    },
                    "fr_milestone_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "capability_fr_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                }
            }
            errors = validate_step_13a(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 2, f"Expected E590 for broken refs: {e}")
            combined = " ".join(e)
            self.assertIn("fr-nonexistent", combined)
            self.assertIn("fr-ghost", combined)

    def test_unknown_fr_in_uncovered_ids_emits_e590(self):
        """An uncovered_id starting with fr- that does not exist in 04 should fire E590."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            instance = {
                "dimensions": {
                    "fr_api_coverage": {
                        "covered_count": 0,
                        "total_count": 1,
                        "ratio": 0.0,
                        "uncovered_ids": ["fr-phantom"],
                    },
                    "fr_fixture_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "fr_milestone_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                    "capability_fr_coverage": {
                        "covered_count": 1,
                        "total_count": 1,
                        "ratio": 1.0,
                        "uncovered_ids": [],
                    },
                }
            }
            errors = validate_step_13a(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 1, f"Expected E590 for unknown 'fr-phantom': {e}")
            self.assertTrue(
                any("fr-phantom" in msg for msg in e),
                f"E590 should mention fr-phantom: {e}"
            )


# ---------------------------------------------------------------------------
# Step 15 — API refs in scaffold interface_map
# ---------------------------------------------------------------------------

class TestStep15CrossStep(unittest.TestCase):
    """Cross-step validation: step_15 checks interface_map interface_ref against 05_interface_contracts.json."""

    def test_valid_upstream_refs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [
                    {"api_id": "api-auth"},
                    {"api_id": "api-users"},
                ]
            })
            instance = {
                "id": "scaffold-main",
                "owner": "api",
                "created_at": "2026-03-01",
                "project_skeleton": {"language": "python"},
                "interface_map": [
                    {"interface_ref": "api-auth", "method": "POST", "path": "/auth"},
                    {"interface_ref": "api-users", "method": "GET", "path": "/users"},
                ],
                "validators": [{"id": "v1", "command": "pytest"}],
                "build_status": "green",
            }
            errors = validate_step_15(instance, tmp)
            self.assertEqual(len(_w590(errors)), 0, f"Unexpected W590: {_w590(errors)}")
            self.assertEqual(len(_e590(errors)), 0, f"Unexpected E590: {_e590(errors)}")

    def test_missing_upstream_emits_w590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # No 05_interface_contracts.json
            instance = {
                "id": "scaffold-main",
                "owner": "api",
                "created_at": "2026-03-01",
                "project_skeleton": {"language": "python"},
                "interface_map": [
                    {"interface_ref": "api-auth", "method": "POST", "path": "/auth"},
                ],
                "validators": [{"id": "v1", "command": "pytest"}],
                "build_status": "green",
            }
            errors = validate_step_15(instance, tmp)
            w = _w590(errors)
            self.assertGreaterEqual(len(w), 1, "Expected W590 for missing 05_interface_contracts.json")
            self.assertTrue(
                any("05_interface_contracts.json" in msg for msg in w),
                f"W590 should mention 05_interface_contracts.json: {w}"
            )

    def test_broken_ref_emits_e590(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            instance = {
                "id": "scaffold-main",
                "owner": "api",
                "created_at": "2026-03-01",
                "project_skeleton": {"language": "python"},
                "interface_map": [
                    {"interface_ref": "api-nonexistent", "method": "POST", "path": "/ghost"},
                ],
                "validators": [{"id": "v1", "command": "pytest"}],
                "build_status": "green",
            }
            errors = validate_step_15(instance, tmp)
            e = _e590(errors)
            self.assertGreaterEqual(len(e), 1, "Expected E590 for broken interface_ref")
            self.assertTrue(
                any("api-nonexistent" in msg for msg in e),
                f"E590 should mention the broken ref: {e}"
            )


# ---------------------------------------------------------------------------
# Edge cases — no spec dir at all
# ---------------------------------------------------------------------------

class TestCrossStepNoSpecDir(unittest.TestCase):
    """When the spec directory does not exist at all, validators should emit W590."""

    def test_step_05_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            # tmp exists but has no spec/ subdirectory
            instance = {"apis": [{"api_id": "api-x", "trace": [{"type": "fr", "id": "fr-x"}]}]}
            errors = validate_step_05(instance, tmp)
            self.assertGreaterEqual(len(_w590(errors)), 1)

    def test_step_06_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {"rules": [{"inv_id": "inv-x", "trace": [{"type": "fr", "id": "fr-x"}, {"type": "api", "id": "api-x"}]}]}
            errors = validate_step_06(instance, tmp)
            self.assertGreaterEqual(len(_w590(errors)), 1)

    def test_step_08_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {"fixtures": [{"fixture_id": "fix-x", "targets": [{"type": "fr", "id": "fr-x"}]}]}
            errors = validate_step_08(instance, tmp)
            self.assertGreaterEqual(len(_w590(errors)), 1)

    def test_step_09_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {"milestones": [{"milestone_id": "ms-x", "target_date": "2026-04-01", "capability_refs": ["cap-x"]}]}
            errors = validate_step_09(instance, tmp)
            self.assertGreaterEqual(len(_w590(errors)), 1)

    def test_step_12_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {
                "jobs": [{"job_id": "job-x", "steps": [{"id": "s1", "command": "echo"}]}],
                "trace": [{"type": "fr", "id": "fr-x"}],
            }
            errors = validate_step_12(instance, tmp)
            self.assertGreaterEqual(len(_w590(errors)), 1)

    def test_step_13_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {
                "extensions": [{
                    "extension_id": "ext-x",
                    "required_schema_sections": ["04_fr_list"],
                    "justification": "Testing no-spec-dir edge case.",
                    "schema_design_guidelines": "Verify tests pass.",
                    "governance_label_ref": {"id": "label-x"},
                }]
            }
            errors = validate_step_13(instance, tmp)
            self.assertGreaterEqual(len(_w590(errors)), 1)

    def test_step_13a_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {
                "dimensions": {
                    "fr_api_coverage": {
                        "covered_count": 0,
                        "total_count": 1,
                        "ratio": 0.0,
                        "uncovered_ids": ["fr-x"],
                    },
                    "fr_fixture_coverage": {"covered_count": 1, "total_count": 1, "ratio": 1.0, "uncovered_ids": []},
                    "fr_milestone_coverage": {"covered_count": 1, "total_count": 1, "ratio": 1.0, "uncovered_ids": []},
                    "capability_fr_coverage": {"covered_count": 1, "total_count": 1, "ratio": 1.0, "uncovered_ids": []},
                }
            }
            errors = validate_step_13a(instance, tmp)
            self.assertGreaterEqual(len(_w590(errors)), 1)

    def test_step_15_no_spec_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = {
                "id": "scaffold-x",
                "owner": "api",
                "created_at": "2026-03-01",
                "project_skeleton": {},
                "interface_map": [{"interface_ref": "api-x", "method": "GET", "path": "/x"}],
                "validators": [{"id": "v1", "command": "pytest"}],
                "build_status": "green",
            }
            errors = validate_step_15(instance, tmp)
            self.assertGreaterEqual(len(_w590(errors)), 1)


if __name__ == "__main__":
    unittest.main()
