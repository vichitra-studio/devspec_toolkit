# Findings: Hardcoded Values and Assumptions

SOURCE: T-tools-tests-review-005
DATE: 2026-03-11
SCOPE: tools/specdev_tools/, scripts/init_project.py
CRITERIA: F1 (Magic numbers), F2 (Path assumptions), F3 (Schema URI assumptions), F4 (Step ordering assumptions), F5 (Hallucinated references)

---

## F1 — Magic Numbers

FINDING | F1-01 | LOW | tools/specdev_tools/validation/spec_quality_lint.py:114 | ASSUMPTION_THRESHOLD = 10 for assumption count is a hardcoded magic number with no configuration mechanism; changing it requires a code edit
FINDING | F1-02 | LOW | tools/specdev_tools/validation/hallucination_lint.py:335 | threshold: int = 5 for overlap detection is a hardcoded default parameter; not configurable via env var or config file
FINDING | F1-03 | INFO | tools/specdev_tools/validation/forward_replay_check.py:237 | staleness_threshold: int = 3 is hardcoded as default but overridable via SPECDEV_STALENESS_THRESHOLD env var at line 86 — intentional design
FINDING | F1-04 | INFO | tools/specdev_tools/validation/matrix.py:19 | _DEFAULT_COVERAGE_THRESHOLDS = {"fr_coverage": 80, "mode": "warn"} is a hardcoded default but overridable via step_order.json coverage_thresholds — intentional design
FINDING | F1-05 | INFO | tools/specdev_tools/validation/canon_schema_alignment.py:90 | overlap >= 3 and overlap / len(enum_set) >= 0.8 — thresholds for canon/schema alignment discovery are magic numbers with no external configurability
FINDING | F1-06 | INFO | tools/specdev_tools/canonical/lint.py:82 | registry_version defaults to "1.0.0" hardcoded as string literal in multiple places (lint.py:82, lint.py:282, lint.py:313, registry.py:73, registry.py:254, registry.py:285) — consistent but not derived from a single constant
PASS | F1-SCHEMA-DIFFER | schema_differ.py (1331 LOC) does not contain problematic magic number literals for step counts; step inventories are computed dynamically from directory contents

## F2 — Path Assumptions

FINDING | F2-01 | MEDIUM | scripts/init_project.py:52 | PRE_COMMIT_TEMPLATE hardcodes "devspec_toolkit" as default submodule name; CI_WORKFLOW_TEMPLATE at lines 85-99 hardcodes "devspec_toolkit/tools" and "dev_env" paths — while string-replaced at line 374-375, the CI template embeds the assumption before replacement
FINDING | F2-02 | LOW | scripts/init_project.py:143 | Default toolkit URL "https://github.com/vichitra-studio/devspec_toolkit.git" is hardcoded — overridable via --toolkit-url flag but the org name may be wrong (README says "vichitracollective" at line 406 vs "vichitra-studio" at line 143)
FINDING | F2-03 | LOW | tools/specdev_tools/core/trace_types.py:12 | toolkit_root = str(Path(__file__).resolve().parents[3]) computes toolkit root via hardcoded parent depth assumption (3 levels up from core/trace_types.py); fragile if directory structure changes
FINDING | F2-04 | LOW | tools/specdev_tools/validation/traceability_closure.py:37-43 | SPEC_FILES dict hardcodes spec filenames ("00_charter.json", "01_capabilities.json", "04_fr_list.json", "14_roadmap.json", "16a_impl_planner.json") — not derived from schema_registry.json
FINDING | F2-05 | LOW | tools/specdev_tools/validation/traceability_closure.py:58 | Fallback path "16_impl_context.json" hardcoded as string literal for impl_planner step
FINDING | F2-06 | INFO | tools/specdev_tools/validation/validate.py:356 | _load_monitoring_data iterates over hardcoded filenames ("16_impl_context.json", "16_delivery_monitoring.json") instead of deriving from registry
PASS | F2-REPO-ROOT | --repo-root resolution is consistent; cli.py auto-detects via child directory scan at lines 178-188; all subcommands pass repo_root through properly

## F3 — Schema URI Assumptions

FINDING | F3-01 | MEDIUM | tools/specdev_tools/validation/validators/step_01.py:57 | Schema URI "https://specdev.local/schema/01_capabilities.schema.json" is hardcoded as string literal rather than derived from schema_registry.json lookup by step number
FINDING | F3-02 | MEDIUM | tools/specdev_tools/validation/validators/step_02.py:127 | Schema URI "https://specdev.local/schema/02_system_sketch.schema.json" is hardcoded as string literal rather than derived from schema_registry.json lookup by step number
FINDING | F3-03 | LOW | tools/specdev_tools/canonical/lint.py:15-17 | Three canonical schema URIs hardcoded as module-level constants (CANON_ALIASES_SCHEMA_URI, CANON_KIND_SCHEMA_URI, CANON_MANIFEST_SCHEMA_URI) — these are registered in schema_registry.json but referenced as raw strings
FINDING | F3-04 | INFO | tools/specdev_tools/validation/invariants.py:61 | Schema detection via data.get("$schema","").endswith("/06_invariants.schema.json") uses string suffix matching instead of registry-based step identification
FINDING | F3-05 | INFO | tools/specdev_tools/validation/fixtures_lint.py:43 | Schema detection via data.get("$schema","") with endswith pattern — same pattern as F3-04
PASS | F3-VALIDATE | validate.py:105-120 properly reads $schema from the artifact and resolves it through SchemaRegistry, not hardcoded URIs
PASS | F3-SCHEMA-DIFFER | schema_differ.py resolves schema references dynamically via schema $id fields, not hardcoded URIs

## F4 — Step Ordering Assumptions

FINDING | F4-01 | MEDIUM | tools/specdev_tools/cli.py:666-674 | STEP_NAMES dict in prompt-context command hardcodes all 22 step IDs and display names; if a step is added/removed this dict must be manually updated separately from step_order.json
FINDING | F4-02 | MEDIUM | tools/specdev_tools/validation/validate.py:376-402 | DEEP_VALIDATORS dict hardcodes step-to-validator mapping for 21 steps (missing step "00"); adding a new step requires updating this dict and the import block at lines 24-46
FINDING | F4-03 | MEDIUM | tools/specdev_tools/generation/prompt_generator.py:523-537 | _STEP_TO_TEMPLATE dict hardcodes step-to-template mapping for a subset of steps (00-10, 14, 16); not derived from step_order.json
FINDING | F4-04 | MEDIUM | tools/specdev_tools/migration/planner.py:38-57 | Duplicate _STEP_TO_TEMPLATE dict hardcodes step-to-template mapping separately from prompt_generator.py — two independent copies that must be kept in sync manually
FINDING | F4-05 | LOW | tools/specdev_tools/generation/prompt_schema_sync.py:377-389 | _SUBSTEP_TO_BASE_SCHEMA, _SUBSTEP_EXPECTED_KEYS, and _SUBSTEP_ORDER hardcode the 16a/16b/16c substep relationship — not derived from step_order.json
FINDING | F4-06 | LOW | tools/specdev_tools/validation/seed_lint.py:40,49-50,94-96 | Step "16" and substeps ("16a", "16b", "16c") hardcoded in multiple conditions for seed lint special-casing
FINDING | F4-07 | INFO | tools/specdev_tools/validation/dag_lint.py:28 | _TERMINAL_STEPS = frozenset({"16c"}) hardcodes the terminal step; if the pipeline is extended beyond 16c this must be manually updated
PASS | F4-DAG-LINT | dag_lint.py at lines 53-55 reads steps, downstream_consumers, and allowed_upstream_dependencies dynamically from step_order.json
PASS | F4-FORWARD-REPLAY | forward_replay_check.py reads step ordering from step_order.json dynamically

## F5 — Hallucinated References

FINDING | F5-01 | LOW | tools/specdev_tools/validation/validators/step_10.py:20 | allowed_owners set {"api", "ui", "system", "ops", "data", "product", "business", "engineering"} is hardcoded in Python; schema/core/atoms.schema.json:35-39 defines owner as a pattern-validated string (^[a-z][a-z0-9_-]*$) not an enum — the validator is more restrictive than the schema, and neither references the canonical owner kind
FINDING | F5-02 | LOW | tools/specdev_tools/validation/validators/step_10.py:43-47 | allowed_rules set for pr_rules is hardcoded but matches the schema enum at schema/10_governance.schema.json:30-44 — currently synchronized but will drift if schema is updated without updating the validator
FINDING | F5-03 | LOW | tools/specdev_tools/validation/validators/step_16.py:7 | VALID_CHECKLIST_LAYERS frozenset hardcodes allowed layers {"db", "model", "service", "api", "integration", "tests", "docs", "config", "security"} — not derived from any schema enum or canonical kind
FINDING | F5-04 | INFO | tools/specdev_tools/validation/validators/step_11.py:17 | _ALLOWED_THREAT_TARGET_TYPES = frozenset({"api", "component"}) and lines 28-29 hardcode trace types — these are validated against canonical registry at runtime via is_valid_trace_type but the local frozen sets could drift
FINDING | F5-05 | INFO | tools/specdev_tools/core/trace_types.py:32-36 | _FALLBACK_TYPES and _FALLBACK_ALIASES are hardcoded but explicitly serve as fallback when canonical registry loading fails — intentional design with appropriate fallback semantics
PASS | F5-TRACE-TYPES | trace_types.py:7-29 dynamically loads from canon/kinds/trace_type.json via CanonicalRegistry; hardcoded values are only fallbacks
PASS | F5-SCHEMA-REGISTRY | schema_registry.json is the single source of truth for schema URI-to-path mappings; validate.py resolves through SchemaRegistry class

---

## Summary

| Criterion | Findings | Pass | Severity Breakdown |
|-----------|----------|------|-------------------|
| F1 Magic numbers | 6 | 1 | 0 HIGH, 0 MEDIUM, 2 LOW, 4 INFO |
| F2 Path assumptions | 6 | 1 | 0 HIGH, 1 MEDIUM, 4 LOW, 1 INFO |
| F3 Schema URI assumptions | 5 | 2 | 0 HIGH, 2 MEDIUM, 1 LOW, 2 INFO |
| F4 Step ordering assumptions | 7 | 2 | 0 HIGH, 4 MEDIUM, 2 LOW, 1 INFO |
| F5 Hallucinated references | 5 | 2 | 0 HIGH, 0 MEDIUM, 3 LOW, 2 INFO |

**Key systemic pattern**: Multiple independent hardcoded step-ID lists (STEP_NAMES, DEEP_VALIDATORS, _STEP_TO_TEMPLATE x2, SPEC_FILES, _SUBSTEP_ORDER) must be manually synchronized with step_order.json. No compile-time or startup-time assertion enforces completeness. This is the highest-risk category of findings (F4-01 through F4-04).
