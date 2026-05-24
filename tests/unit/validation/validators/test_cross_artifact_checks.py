"""Tests for cross_artifact_checks.py — error-detection coverage.

Covers the three step-specific integrity checks that were previously executed
during build_trace_matrix runs but whose emitted errors were never asserted:

  - check_step_02_integrity  (system-sketch)
  - check_step_03_integrity  (glossary)
  - check_step_04_integrity  (FR cross-artifact traces)

Each test class has at least one POSITIVE case (malformed / dangling reference
→ specific error code asserted) and one NEGATIVE case (valid input → no error).

The functions accept an ``artifacts`` dict keyed by file path.  The ``$schema``
value controls which step's logic runs; tests use minimal in-memory dicts.
"""
from __future__ import annotations

import unittest

from specdev_tools.validation.cross_artifact_checks import (
    check_step_02_integrity,
    check_step_03_integrity,
    check_step_04_integrity,
    collect_capability_ids,
    collect_glossary_term_ids,
)


# ---------------------------------------------------------------------------
# Shared rendering helpers (mirrors sibling test files)
# ---------------------------------------------------------------------------

def _render(errors) -> list[str]:
    return [e.render() if hasattr(e, "render") else str(e) for e in errors]


def _has_code(errors, code: str) -> bool:
    return any(code in r for r in _render(errors))


def _has_text(errors, text: str) -> bool:
    return any(text in r for r in _render(errors))


# ---------------------------------------------------------------------------
# Minimal artifact builders
# ---------------------------------------------------------------------------

def _step02_artifact(
    *,
    components=None,
    connections=None,
) -> dict:
    """Build a minimal 02_system_sketch artifact dict."""
    return {
        "$schema": "vc:step:02_system_sketch",
        "components": components or [],
        "connections": connections or [],
    }


def _step03_artifact(*, terms=None) -> dict:
    """Build a minimal 03_glossary artifact dict."""
    return {
        "$schema": "vc:step:03_glossary",
        "terms": terms if terms is not None else [],
    }


def _step04_artifact(*, functional_requirements=None) -> dict:
    """Build a minimal 04_fr_list artifact dict."""
    return {
        "$schema": "vc:step:04_fr_list",
        "functional_requirements": functional_requirements or [],
    }


def _step01_artifact(*, capabilities=None) -> dict:
    """Build a minimal 01_capabilities artifact dict."""
    return {
        "$schema": "vc:step:01_capabilities",
        "capabilities": capabilities or [],
    }


def _artifacts(*pairs) -> dict:
    """Build an artifacts dict from (path, data) pairs."""
    return dict(pairs)


# ===========================================================================
# collect_capability_ids helper
# ===========================================================================

class TestCollectCapabilityIds(unittest.TestCase):
    """collect_capability_ids indexes only Step 01 artifacts."""

    def test_collects_capability_ids_from_step01(self):
        arts = _artifacts(
            ("spec/01_capabilities.json", _step01_artifact(capabilities=[
                {"capability_id": "cap-auth"},
                {"capability_id": "cap-dashboard"},
            ])),
        )
        result = collect_capability_ids(arts)
        self.assertEqual(result, {"cap-auth", "cap-dashboard"})

    def test_ignores_non_step01_artifacts(self):
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {"fr_id": "fr-login"}
            ])),
        )
        result = collect_capability_ids(arts)
        self.assertEqual(result, set())

    def test_empty_capabilities_returns_empty_set(self):
        arts = _artifacts(
            ("spec/01_capabilities.json", _step01_artifact(capabilities=[])),
        )
        self.assertEqual(collect_capability_ids(arts), set())


# ===========================================================================
# collect_glossary_term_ids helper
# ===========================================================================

class TestCollectGlossaryTermIds(unittest.TestCase):
    """collect_glossary_term_ids indexes only Step 03 artifacts (lowercased)."""

    def test_collects_term_ids_lowercased(self):
        arts = _artifacts(
            ("spec/03_glossary.json", _step03_artifact(terms=[
                {"term_id": "TERM-Auth", "term": "Authentication"},
                {"term_id": "term-session", "term": "Session"},
            ])),
        )
        result = collect_glossary_term_ids(arts)
        self.assertIn("term-auth", result)
        self.assertIn("term-session", result)

    def test_ignores_non_step03_artifacts(self):
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact()),
        )
        self.assertEqual(collect_glossary_term_ids(arts), set())


# ===========================================================================
# check_step_02_integrity
# ===========================================================================

class TestCheckStep02IntegrityNegative(unittest.TestCase):
    """Negative cases: valid input → no errors."""

    def test_no_step02_artifact_returns_empty(self):
        """When no 02_system_sketch artifact is present the function returns []."""
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact()),
        )
        errors = check_step_02_integrity(arts, capability_ids=set())
        self.assertEqual(errors, [])

    def test_valid_components_and_connections_no_errors(self):
        """Valid components with matching connection endpoints emit no errors."""
        arts = _artifacts(
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {"component_id": "comp-api", "type": "service"},
                    {"component_id": "comp-db", "type": "datastore"},
                ],
                connections=[
                    {"from": "comp-api", "to": "comp-db", "trust_boundary": "internal"},
                ],
            )),
        )
        errors = check_step_02_integrity(arts, capability_ids=set())
        self.assertEqual(errors, [], f"Expected no errors; got: {_render(errors)}")

    def test_valid_capability_coverage_no_errors(self):
        """Components that correctly trace known capabilities emit no errors."""
        capability_ids = {"cap-auth", "cap-data"}
        arts = _artifacts(
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {
                        "component_id": "comp-auth-svc",
                        "type": "service",
                        "trace": [
                            {"type": "doc", "id": "cap-auth"},
                            {"type": "doc", "id": "cap-data"},
                        ],
                    }
                ],
            )),
        )
        errors = check_step_02_integrity(arts, capability_ids=capability_ids)
        self.assertEqual(errors, [], f"Expected no errors; got: {_render(errors)}")

    def test_external_component_with_external_dependency_tag_no_errors(self):
        """External component with 'external-dependency' tag does not emit E520."""
        arts = _artifacts(
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {
                        "component_id": "comp-stripe",
                        "type": "external",
                        "tags": ["external-dependency"],
                    }
                ],
            )),
        )
        errors = check_step_02_integrity(arts, capability_ids=set())
        self.assertEqual(errors, [], f"Expected no errors; got: {_render(errors)}")


class TestCheckStep02IntegrityPositive(unittest.TestCase):
    """Positive cases: malformed input → specific error codes asserted."""

    def test_duplicate_component_id_emits_e520(self):
        """Duplicate component_id causes E520."""
        arts = _artifacts(
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {"component_id": "comp-auth"},
                    {"component_id": "comp-auth"},  # duplicate
                ],
            )),
        )
        errors = check_step_02_integrity(arts, capability_ids=set())
        self.assertTrue(_has_code(errors, "E520"), f"Expected E520; got: {_render(errors)}")
        self.assertTrue(_has_text(errors, "comp-auth"), f"E520 should mention the duplicate ID; got: {_render(errors)}")
        self.assertTrue(_has_text(errors, "Duplicate component_id"), f"E520 message should say 'Duplicate component_id'; got: {_render(errors)}")

    def test_connection_from_unknown_component_emits_e590(self):
        """Connection referencing an unknown 'from' component emits E590."""
        arts = _artifacts(
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {"component_id": "comp-api"},
                ],
                connections=[
                    {"from": "comp-ghost", "to": "comp-api"},
                ],
            )),
        )
        errors = check_step_02_integrity(arts, capability_ids=set())
        self.assertTrue(_has_code(errors, "E590"), f"Expected E590; got: {_render(errors)}")
        self.assertTrue(_has_text(errors, "comp-ghost"), f"E590 should mention the unknown component; got: {_render(errors)}")

    def test_connection_to_unknown_component_emits_e590(self):
        """Connection referencing an unknown 'to' component emits E590."""
        arts = _artifacts(
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {"component_id": "comp-api"},
                ],
                connections=[
                    {"from": "comp-api", "to": "comp-nonexistent"},
                ],
            )),
        )
        errors = check_step_02_integrity(arts, capability_ids=set())
        self.assertTrue(_has_code(errors, "E590"), f"Expected E590; got: {_render(errors)}")
        self.assertTrue(_has_text(errors, "comp-nonexistent"), f"E590 should mention the unknown component; got: {_render(errors)}")

    def test_invalid_schema_ref_emits_e520(self):
        """Connection with malformed schema_ref emits E520."""
        arts = _artifacts(
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {"component_id": "comp-a"},
                    {"component_id": "comp-b"},
                ],
                connections=[
                    {"from": "comp-a", "to": "comp-b", "schema_ref": "not-a-valid-ref"},
                ],
            )),
        )
        errors = check_step_02_integrity(arts, capability_ids=set())
        self.assertTrue(_has_code(errors, "E520"), f"Expected E520 for invalid schema_ref; got: {_render(errors)}")
        self.assertTrue(_has_text(errors, "not-a-valid-ref"), f"E520 should mention the bad schema_ref; got: {_render(errors)}")

    def test_external_component_internal_trust_boundary_emits_e520(self):
        """Connection with external component and 'internal' trust_boundary emits E520."""
        arts = _artifacts(
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {"component_id": "comp-internal"},
                    {"component_id": "comp-stripe", "type": "external", "tags": ["external-dependency"]},
                ],
                connections=[
                    {
                        "from": "comp-internal",
                        "to": "comp-stripe",
                        "trust_boundary": "internal",  # invalid for external component
                    },
                ],
            )),
        )
        errors = check_step_02_integrity(arts, capability_ids=set())
        self.assertTrue(_has_code(errors, "E520"), f"Expected E520 for internal trust_boundary with external component; got: {_render(errors)}")
        self.assertTrue(_has_text(errors, "internal trust_boundary"), f"E520 message should mention trust_boundary; got: {_render(errors)}")

    def test_missing_capability_coverage_emits_e590(self):
        """When capability_ids exist but no component traces them, E590 is emitted."""
        capability_ids = {"cap-auth", "cap-data"}
        arts = _artifacts(
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {
                        "component_id": "comp-api",
                        "type": "service",
                        # No trace at all
                    }
                ],
            )),
        )
        errors = check_step_02_integrity(arts, capability_ids=capability_ids)
        self.assertTrue(_has_code(errors, "E590"), f"Expected E590 for missing capability coverage; got: {_render(errors)}")
        self.assertTrue(
            _has_text(errors, "Missing capability coverage"),
            f"E590 should say 'Missing capability coverage'; got: {_render(errors)}"
        )

    def test_capability_trace_wrong_type_emits_e520(self):
        """Tracing a capability with a wrong type (not 'doc' or 'capability') emits E520."""
        capability_ids = {"cap-auth"}
        arts = _artifacts(
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {
                        "component_id": "comp-api",
                        "type": "service",
                        "trace": [
                            {"type": "fr", "id": "cap-auth"},  # wrong type for a capability trace
                        ],
                    }
                ],
            )),
        )
        errors = check_step_02_integrity(arts, capability_ids=capability_ids)
        # This emits E520 ("must use type 'doc' or 'capability'") + E590 (missing coverage)
        self.assertTrue(_has_code(errors, "E520"), f"Expected E520 for wrong trace type; got: {_render(errors)}")
        self.assertTrue(_has_text(errors, "cap-auth"), f"E520 should mention the capability ID; got: {_render(errors)}")

    def test_external_component_without_tag_emits_e520(self):
        """External component lacking 'external-dependency' tag emits E520."""
        arts = _artifacts(
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {
                        "component_id": "comp-stripe",
                        "type": "external",
                        "tags": [],  # missing external-dependency
                    }
                ],
            )),
        )
        errors = check_step_02_integrity(arts, capability_ids=set())
        self.assertTrue(_has_code(errors, "E520"), f"Expected E520 for missing external-dependency tag; got: {_render(errors)}")
        self.assertTrue(
            _has_text(errors, "external-dependency tag"),
            f"E520 should mention 'external-dependency tag'; got: {_render(errors)}"
        )


# ===========================================================================
# check_step_03_integrity
# ===========================================================================

class TestCheckStep03IntegrityNegative(unittest.TestCase):
    """Negative cases: valid glossary input → no errors."""

    def test_no_step03_artifact_returns_empty(self):
        """When no 03_glossary artifact is present the function returns []."""
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact()),
        )
        errors = check_step_03_integrity(arts)
        self.assertEqual(errors, [])

    def test_valid_terms_no_errors(self):
        """Unique terms with valid optional fields emit no errors."""
        arts = _artifacts(
            ("spec/03_glossary.json", _step03_artifact(terms=[
                {"term_id": "term-auth", "term": "Authentication", "domain": "security"},
                {"term_id": "term-session", "term": "Session"},
            ])),
        )
        errors = check_step_03_integrity(arts)
        self.assertEqual(errors, [], f"Expected no errors; got: {_render(errors)}")


class TestCheckStep03IntegrityPositive(unittest.TestCase):
    """Positive cases: malformed glossary input → specific error codes asserted."""

    def test_empty_terms_array_emits_e520(self):
        """Empty terms array in a Step 03 artifact emits E520."""
        arts = _artifacts(
            ("spec/03_glossary.json", _step03_artifact(terms=[])),
        )
        errors = check_step_03_integrity(arts)
        self.assertTrue(_has_code(errors, "E520"), f"Expected E520 for empty terms; got: {_render(errors)}")
        self.assertTrue(
            _has_text(errors, "Empty terms array"),
            f"E520 should say 'Empty terms array'; got: {_render(errors)}"
        )

    def test_duplicate_term_id_emits_e520(self):
        """Duplicate term_id (case-insensitive) in terms array emits E520."""
        arts = _artifacts(
            ("spec/03_glossary.json", _step03_artifact(terms=[
                {"term_id": "term-auth", "term": "Authentication"},
                {"term_id": "TERM-AUTH", "term": "Auth alias"},  # duplicate (case-insensitive)
            ])),
        )
        errors = check_step_03_integrity(arts)
        self.assertTrue(_has_code(errors, "E520"), f"Expected E520 for duplicate term_id; got: {_render(errors)}")
        self.assertTrue(
            _has_text(errors, "Duplicate term_id"),
            f"E520 should say 'Duplicate term_id'; got: {_render(errors)}"
        )

    def test_duplicate_term_text_emits_e520(self):
        """Duplicate term text (case-insensitive) in terms array emits E520."""
        arts = _artifacts(
            ("spec/03_glossary.json", _step03_artifact(terms=[
                {"term_id": "term-auth-1", "term": "Authentication"},
                {"term_id": "term-auth-2", "term": "authentication"},  # duplicate text (case)
            ])),
        )
        errors = check_step_03_integrity(arts)
        self.assertTrue(_has_code(errors, "E520"), f"Expected E520 for duplicate term text; got: {_render(errors)}")
        self.assertTrue(
            _has_text(errors, "Duplicate term"),
            f"E520 should say 'Duplicate term'; got: {_render(errors)}"
        )

    def test_empty_domain_string_emits_e520(self):
        """Empty string in the 'domain' field emits E520."""
        arts = _artifacts(
            ("spec/03_glossary.json", _step03_artifact(terms=[
                {"term_id": "term-auth", "term": "Authentication", "domain": ""},  # empty domain
            ])),
        )
        errors = check_step_03_integrity(arts)
        self.assertTrue(_has_code(errors, "E520"), f"Expected E520 for empty domain; got: {_render(errors)}")
        self.assertTrue(
            _has_text(errors, "Empty domain string"),
            f"E520 should say 'Empty domain string'; got: {_render(errors)}"
        )

    def test_empty_units_string_emits_e520(self):
        """Empty string in the 'units' field emits E520."""
        arts = _artifacts(
            ("spec/03_glossary.json", _step03_artifact(terms=[
                {"term_id": "term-latency", "term": "Latency", "units": ""},  # empty units
            ])),
        )
        errors = check_step_03_integrity(arts)
        self.assertTrue(_has_code(errors, "E520"), f"Expected E520 for empty units; got: {_render(errors)}")
        self.assertTrue(
            _has_text(errors, "Empty units string"),
            f"E520 should say 'Empty units string'; got: {_render(errors)}"
        )


# ===========================================================================
# check_step_04_integrity
# ===========================================================================

class TestCheckStep04IntegrityNegative(unittest.TestCase):
    """Negative cases: valid FR traces → no errors."""

    def test_no_step04_artifact_returns_empty(self):
        """When no 04_fr_list artifact is present the function returns []."""
        arts = _artifacts(
            ("spec/03_glossary.json", _step03_artifact(terms=[
                {"term_id": "term-auth", "term": "Authentication"},
            ])),
        )
        errors = check_step_04_integrity(
            arts,
            glossary_term_ids={"term-auth"},
            capability_ids={"cap-auth"},
        )
        self.assertEqual(errors, [])

    def test_valid_glossary_trace_no_errors(self):
        """FR tracing a known glossary term via type 'glossary' emits no errors."""
        glossary_term_ids = {"term-auth"}
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {
                    "fr_id": "fr-login",
                    "trace": [
                        {"type": "glossary", "id": "term-auth"},
                    ],
                }
            ])),
        )
        errors = check_step_04_integrity(arts, glossary_term_ids=glossary_term_ids, capability_ids=set())
        self.assertEqual(errors, [], f"Expected no errors; got: {_render(errors)}")

    def test_valid_capability_trace_no_errors(self):
        """FR tracing a known capability via type 'capability' emits no errors."""
        capability_ids = {"cap-auth"}
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {
                    "fr_id": "fr-login",
                    "trace": [
                        {"type": "capability", "id": "cap-auth"},
                    ],
                }
            ])),
        )
        errors = check_step_04_integrity(arts, glossary_term_ids=set(), capability_ids=capability_ids)
        self.assertEqual(errors, [], f"Expected no errors; got: {_render(errors)}")

    def test_term_prefix_id_matching_known_term_no_errors(self):
        """FR trace with id starting 'term-' matching a known glossary term emits no errors."""
        glossary_term_ids = {"term-session"}
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {
                    "fr_id": "fr-manage-session",
                    "trace": [
                        {"type": "fr", "id": "term-session"},  # id starts with term-
                    ],
                }
            ])),
        )
        errors = check_step_04_integrity(arts, glossary_term_ids=glossary_term_ids, capability_ids=set())
        self.assertEqual(errors, [], f"Expected no errors; got: {_render(errors)}")

    def test_trace_without_id_is_skipped(self):
        """Trace entry missing 'id' is silently skipped (no errors, no crash)."""
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {
                    "fr_id": "fr-login",
                    "trace": [
                        {"type": "glossary"},  # no id field
                    ],
                }
            ])),
        )
        errors = check_step_04_integrity(arts, glossary_term_ids=set(), capability_ids=set())
        self.assertEqual(errors, [], f"Expected no errors for trace without id; got: {_render(errors)}")


class TestCheckStep04IntegrityPositive(unittest.TestCase):
    """Positive cases: dangling FR traces → E590 asserted."""

    def test_unknown_glossary_term_via_glossary_type_emits_e590(self):
        """FR trace with type='glossary' referencing an unknown term emits E590."""
        glossary_term_ids = {"term-auth"}  # term-session is NOT in here
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {
                    "fr_id": "fr-login",
                    "trace": [
                        {"type": "glossary", "id": "term-session"},  # unknown term
                    ],
                }
            ])),
        )
        errors = check_step_04_integrity(arts, glossary_term_ids=glossary_term_ids, capability_ids=set())
        self.assertTrue(_has_code(errors, "E590"), f"Expected E590 for unknown glossary term; got: {_render(errors)}")
        self.assertTrue(
            _has_text(errors, "term-session"),
            f"E590 should mention 'term-session'; got: {_render(errors)}"
        )
        self.assertTrue(
            _has_text(errors, "unknown glossary term"),
            f"E590 should say 'unknown glossary term'; got: {_render(errors)}"
        )
        self.assertTrue(
            _has_text(errors, "fr-login"),
            f"E590 should identify the FR 'fr-login'; got: {_render(errors)}"
        )

    def test_unknown_glossary_term_via_term_prefix_emits_e590(self):
        """FR trace with id starting 'term-' not in glossary_term_ids emits E590."""
        glossary_term_ids = {"term-auth"}
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {
                    "fr_id": "fr-manage-data",
                    "trace": [
                        {"type": "fr", "id": "term-nonexistent"},  # term- prefix but not in glossary
                    ],
                }
            ])),
        )
        errors = check_step_04_integrity(arts, glossary_term_ids=glossary_term_ids, capability_ids=set())
        self.assertTrue(_has_code(errors, "E590"), f"Expected E590 for unknown term- prefixed id; got: {_render(errors)}")
        self.assertTrue(
            _has_text(errors, "term-nonexistent"),
            f"E590 should mention 'term-nonexistent'; got: {_render(errors)}"
        )

    def test_unknown_capability_via_capability_type_emits_e590(self):
        """FR trace with type='capability' referencing an unknown capability emits E590."""
        capability_ids = {"cap-auth"}  # cap-dashboard is NOT here
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {
                    "fr_id": "fr-view-dashboard",
                    "trace": [
                        {"type": "capability", "id": "cap-dashboard"},  # unknown capability
                    ],
                }
            ])),
        )
        errors = check_step_04_integrity(arts, glossary_term_ids=set(), capability_ids=capability_ids)
        self.assertTrue(_has_code(errors, "E590"), f"Expected E590 for unknown capability; got: {_render(errors)}")
        self.assertTrue(
            _has_text(errors, "cap-dashboard"),
            f"E590 should mention 'cap-dashboard'; got: {_render(errors)}"
        )
        self.assertTrue(
            _has_text(errors, "unknown capability"),
            f"E590 should say 'unknown capability'; got: {_render(errors)}"
        )
        self.assertTrue(
            _has_text(errors, "fr-view-dashboard"),
            f"E590 should identify the FR 'fr-view-dashboard'; got: {_render(errors)}"
        )

    def test_multiple_frs_multiple_errors(self):
        """Multiple FRs with bad traces each emit their own E590."""
        glossary_term_ids = {"term-session"}
        capability_ids = {"cap-auth"}
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {
                    "fr_id": "fr-login",
                    "trace": [
                        {"type": "glossary", "id": "term-ghost"},    # unknown glossary
                        {"type": "capability", "id": "cap-phantom"},  # unknown capability
                    ],
                },
                {
                    "fr_id": "fr-logout",
                    "trace": [
                        {"type": "capability", "id": "cap-does-not-exist"},  # unknown capability
                    ],
                },
            ])),
        )
        errors = check_step_04_integrity(arts, glossary_term_ids=glossary_term_ids, capability_ids=capability_ids)
        rendered = _render(errors)
        # All three bad references should produce E590
        e590s = [r for r in rendered if "E590" in r]
        self.assertGreaterEqual(len(e590s), 3, f"Expected >=3 E590 errors; got: {rendered}")
        combined = " ".join(rendered)
        self.assertIn("term-ghost", combined)
        self.assertIn("cap-phantom", combined)
        self.assertIn("cap-does-not-exist", combined)

    def test_empty_capability_ids_causes_all_capability_traces_to_fail(self):
        """When capability_ids is empty, any capability trace is reported as unknown."""
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {
                    "fr_id": "fr-auth",
                    "trace": [
                        {"type": "capability", "id": "cap-any"},
                    ],
                }
            ])),
        )
        errors = check_step_04_integrity(arts, glossary_term_ids=set(), capability_ids=set())
        self.assertTrue(_has_code(errors, "E590"), f"Expected E590 when capability_ids is empty; got: {_render(errors)}")

    def test_empty_glossary_term_ids_causes_all_glossary_traces_to_fail(self):
        """When glossary_term_ids is empty, any glossary trace is reported as unknown."""
        arts = _artifacts(
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {
                    "fr_id": "fr-auth",
                    "trace": [
                        {"type": "glossary", "id": "term-any"},
                    ],
                }
            ])),
        )
        errors = check_step_04_integrity(arts, glossary_term_ids=set(), capability_ids=set())
        self.assertTrue(_has_code(errors, "E590"), f"Expected E590 when glossary_term_ids is empty; got: {_render(errors)}")


# ===========================================================================
# Integration: combined artifact dict (all three checks run together)
# ===========================================================================

class TestCrossArtifactChecksIntegration(unittest.TestCase):
    """Smoke tests exercising the three checks against a combined artifacts dict."""

    def test_all_clean_artifacts_produce_no_errors(self):
        """A spec with consistent step 01/02/03/04 data produces no cross-artifact errors."""
        capability_ids = {"cap-auth"}
        glossary_term_ids = {"term-session"}

        arts = _artifacts(
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {
                        "component_id": "comp-api",
                        "type": "service",
                        "trace": [{"type": "doc", "id": "cap-auth"}],
                    }
                ],
            )),
            ("spec/03_glossary.json", _step03_artifact(terms=[
                {"term_id": "term-session", "term": "Session"},
            ])),
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {
                    "fr_id": "fr-login",
                    "trace": [
                        {"type": "glossary", "id": "term-session"},
                        {"type": "capability", "id": "cap-auth"},
                    ],
                }
            ])),
        )

        e02 = check_step_02_integrity(arts, capability_ids=capability_ids)
        e03 = check_step_03_integrity(arts)
        e04 = check_step_04_integrity(arts, glossary_term_ids=glossary_term_ids, capability_ids=capability_ids)

        all_errors = e02 + e03 + e04
        self.assertEqual(all_errors, [], f"Expected no errors; got: {_render(all_errors)}")

    def test_broken_references_across_all_steps(self):
        """A spec with broken references across all three steps emits errors for each."""
        capability_ids = {"cap-auth"}
        glossary_term_ids = {"term-session"}

        arts = _artifacts(
            # Step 02: external component missing tag + dangling connection
            ("spec/02_system_sketch.json", _step02_artifact(
                components=[
                    {"component_id": "comp-api"},
                    {"component_id": "comp-stripe", "type": "external", "tags": []},  # missing tag
                ],
                connections=[
                    {"from": "comp-api", "to": "comp-missing"},  # dangling
                ],
            )),
            # Step 03: empty terms
            ("spec/03_glossary.json", _step03_artifact(terms=[])),
            # Step 04: unknown glossary term + unknown capability
            ("spec/04_fr_list.json", _step04_artifact(functional_requirements=[
                {
                    "fr_id": "fr-login",
                    "trace": [
                        {"type": "glossary", "id": "term-unknown"},
                        {"type": "capability", "id": "cap-ghost"},
                    ],
                }
            ])),
        )

        e02 = check_step_02_integrity(arts, capability_ids=capability_ids)
        e03 = check_step_03_integrity(arts)
        e04 = check_step_04_integrity(arts, glossary_term_ids=glossary_term_ids, capability_ids=capability_ids)

        # Step 02 should have E590 (dangling connection) and E520 (missing tag + missing cap coverage)
        self.assertTrue(_has_code(e02, "E590"), f"Step 02 should emit E590; got: {_render(e02)}")
        self.assertTrue(_has_code(e02, "E520"), f"Step 02 should emit E520; got: {_render(e02)}")

        # Step 03 should have E520 (empty terms)
        self.assertTrue(_has_code(e03, "E520"), f"Step 03 should emit E520; got: {_render(e03)}")

        # Step 04 should have E590 for both broken references
        self.assertTrue(_has_code(e04, "E590"), f"Step 04 should emit E590; got: {_render(e04)}")
        combined04 = " ".join(_render(e04))
        self.assertIn("term-unknown", combined04)
        self.assertIn("cap-ghost", combined04)


if __name__ == "__main__":
    unittest.main()
