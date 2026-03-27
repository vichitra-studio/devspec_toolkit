REQ | 0a-01 | schema/09_impl_plan.schema.json | Add optional `depends_on` array to milestone items for dependency ordering and cycle detection
REQ | 0a-02 | schema/14_roadmap.schema.json | Add optional `fr_refs` array to task objects enabling pairwise completeness checks between milestones and FRs
REQ | 0a-03 | schema/00_charter.schema.json | Add in_scope, out_of_scope, assumptions, risks to charter required array
REQ | 0a-04 | schema/05_interface_contracts.schema.json | Add trace to Step 05 API item required array for traceability links to FRs
REQ | 0a-05 | schema/core/atoms.schema.json | Replace owner regex pattern with enum constraint listing 8 canonical owners
REQ | 0b-01 | schema/00_charter.schema.json | Enrich charter schema descriptions per three-tier DEPTH model focusing on problem_statement and success_metrics
REQ | 0b-02 | schema/01_capabilities.schema.json | Enrich Tier 3 fields for capability_id, name, description, goal_id, success_metric_refs
REQ | 0b-03 | schema/04_fr_list.schema.json | Enrich FR schema descriptions for statement, acceptance_criteria, preconditions, postconditions, rationale fields
REQ | 0b-04 | schema/05_interface_contracts.schema.json | Enrich API item fields including endpoints path, method, request_body, responses with Tier 3 focus
REQ | 0b-05 | schema/06_invariants.schema.json | Enrich invariant_id, statement, language, expression, owner, scope, enforcement_point fields
REQ | 0b-06 | schema/07_nfrs.schema.json | Enrich nfr_id, name, category, target, measurement_method, baseline fields per Tier 3 guidance
REQ | 0b-07 | schema/09_impl_plan.schema.json | Enrich milestone fields including new depends_on, tech_stack, deliverables, status fields
REQ | 0b-08 | schema/14_roadmap.schema.json | Enrich milestone and task fields including new fr_refs and differentiate dependencyObjectList from Step 09
REQ | 0b-09 | schema/16_impl_context.schema.json | Differentiate 14+ status_ref descriptions and add enum constraint to emergent_ambiguities severity
REQ | 0b-10 | schema/core/atoms.schema.json | Add examples array to owner listing 8 standard owners and enrich kebabId, isoDate, semVer descriptions
REQ | 0b-11 | schema/core/collections.schema.json | Add examples to traceRef type and clarify distinction between stageName and environmentName
REQ | 0b-12 | schema/02_system_sketch.schema.json | Update connection schema_ref description to explain -tbd placeholder convention
REQ | 0b-13 | schema/02a_delivery_baseline.schema.json | Apply three-tier DEPTH model focusing on Tier 3 semantic content fields
REQ | 0b-14 | schema/03_glossary.schema.json | Apply three-tier DEPTH model focusing on term, definition, domain Tier 3 fields
REQ | 0b-15 | schema/08_fixtures.schema.json | Apply three-tier DEPTH model focusing on targets, test_data, expected_outcomes
REQ | 0b-16 | schema/10_governance.schema.json | Apply three-tier DEPTH model focusing on pr_rules, review_checklist Tier 2 fields
REQ | 0b-17 | schema/11_redteam.schema.json | Apply three-tier DEPTH model focusing on threat_id, target_ids, mitigations Tier 3 fields
REQ | 0b-18 | schema/12_ci_gates.schema.json | Apply three-tier DEPTH model focusing on jobs, dependencies, triggers Tier 2 fields
REQ | 0b-19 | schema/13_extension_generator.schema.json | Apply three-tier DEPTH model focusing on required_schema_sections Tier 2 fields
REQ | 0b-20 | schema/13a_completeness_assessment.schema.json | Apply three-tier DEPTH model focusing on scoring dimensions that will be redesigned in Batch 5
REQ | 0b-21 | schema/15_scaffold.schema.json | Apply three-tier DEPTH model focusing on files, method, interface_ref Tier 2 fields
REQ | 0b-22 | schema/seed_manifest.schema.json | Enrich global_seed_order, step_requirements, and remaining fields with Tier 2 descriptions
REQ | 0c-01 | prompts/prompt_00_project_charter.md,prompts/prompt_01_capabilities.md,prompts/prompt_02_system_sketch.md,prompts/prompt_02a_delivery_baseline.md,prompts/prompt_03_glossary.md,prompts/prompt_04_functional_requirements.md,prompts/prompt_05_interface_contracts.md,prompts/prompt_06_invariants.md,prompts/prompt_07_nfrs.md,prompts/prompt_08_fixtures.md,prompts/prompt_09_impl_plan.md,prompts/prompt_10_governance.md,prompts/prompt_11_redteam.md,prompts/prompt_12_ci_gates.md,prompts/prompt_13a_completeness_assessment.md,prompts/prompt_15_scaffold.md,prompts/prompt_16_impl_context.md | Delete Quick Reference sections from 17 prompts to eliminate schema-duplicated content
REQ | 1-01 | schema/seed_manifest.schema.json | Remove docs_policy property definition from seed_manifest schema
REQ | 1-02 | spec/common/seed_manifest.json | Remove docs_policy JSON block from seed_manifest data file
REQ | 1-03 | tests/fixtures/seed_manifest/valid_minimal.json,tests/fixtures/seed_manifest/invalid_missing_required.json | Remove docs_policy from fixture files
REQ | 1-04 | tools/specdev_tools/core/registry.py | Add derive_allowed_upstream function for runtime derivation of allowed upstream dependencies
REQ | 1-05 | tools/specdev_tools/cli.py,tools/specdev_tools/validation/hallucination_lint.py,tools/specdev_tools/validation/extraction_intent_check.py,tools/specdev_tools/validation/dependency_order_lint.py,tools/specdev_tools/validation/dag_lint.py,tools/step_order.json,schema/step_order.schema.json | Migrate 5 consumers to derived allowed_upstream_dependencies function and delete from JSON
REQ | 1-06 | spec/common/seed_manifest.json,schema/seed_manifest.schema.json | Delete nested_order from seed_manifest
REQ | 1-07 | tools/specdev_tools/validation/validators/step_16c.py | Fix Step 16c semantic_review enforcement to require it when verdict is verified
REQ | 1-08 | prompts/prompt_16c_impl_reviewer.md | Fix verdict enum from verified;deferred;rejected to verified;needs_work;blocked;deferred
REQ | 1-09 | tools/specdev_tools/validation/validators/step_16.py | Fix E304 active milestone filtering bug to use milestone_ref parameter
REQ | 1-10 | tools/step_order.json | Update downstream_consumers for Step 02a from [12] to [04,05,06,07,12]
REQ | 2-01 | docs/prompts/shared_expectations.md | Redesign shared_expectations.md with 11-13 centralized sections covering path variables, schema authority, canonical registry, hardening protocol, output rules, seed order, self-audit gate, step-order policy, tool execution, conflict resolution, and context ledger
REQ | 2-02 | prompts/prompt_00_project_charter.md,prompts/prompt_01_capabilities.md,prompts/prompt_02_system_sketch.md,prompts/prompt_02a_delivery_baseline.md,prompts/prompt_03_glossary.md,prompts/prompt_04_functional_requirements.md,prompts/prompt_05_interface_contracts.md,prompts/prompt_06_invariants.md,prompts/prompt_07_nfrs.md,prompts/prompt_08_fixtures.md,prompts/prompt_09_impl_plan.md,prompts/prompt_10_governance.md,prompts/prompt_11_redteam.md,prompts/prompt_12_ci_gates.md,prompts/prompt_13_extension_generator.md,prompts/prompt_13a_completeness_assessment.md,prompts/prompt_14_roadmap.md,prompts/prompt_15_scaffold.md,prompts/prompt_16_impl_context.md,prompts/prompt_16a_impl_planner.md,prompts/prompt_16b_impl_coder.md,prompts/prompt_16c_impl_reviewer.md | Add shared_expectations inheritance reference to all 22 prompts
REQ | 2-03 | prompts/prompt_00_project_charter.md,prompts/prompt_01_capabilities.md,prompts/prompt_02_system_sketch.md,prompts/prompt_02a_delivery_baseline.md,prompts/prompt_03_glossary.md,prompts/prompt_04_functional_requirements.md,prompts/prompt_05_interface_contracts.md,prompts/prompt_06_invariants.md,prompts/prompt_07_nfrs.md,prompts/prompt_08_fixtures.md,prompts/prompt_09_impl_plan.md,prompts/prompt_10_governance.md,prompts/prompt_11_redteam.md,prompts/prompt_12_ci_gates.md,prompts/prompt_13_extension_generator.md,prompts/prompt_13a_completeness_assessment.md,prompts/prompt_14_roadmap.md,prompts/prompt_15_scaffold.md,prompts/prompt_16_impl_context.md,prompts/prompt_16a_impl_planner.md,prompts/prompt_16b_impl_coder.md,prompts/prompt_16c_impl_reviewer.md | Delete extracted boilerplate from all 22 prompts including path variables, schema authority, tool execution, canonical registry, and output rules
REQ | 2-04 | prompts/prompt_00_project_charter.md,prompts/prompt_01_capabilities.md,prompts/prompt_02_system_sketch.md,prompts/prompt_02a_delivery_baseline.md,prompts/prompt_03_glossary.md,prompts/prompt_04_functional_requirements.md,prompts/prompt_05_interface_contracts.md,prompts/prompt_06_invariants.md,prompts/prompt_07_nfrs.md,prompts/prompt_08_fixtures.md,prompts/prompt_09_impl_plan.md,prompts/prompt_10_governance.md,prompts/prompt_11_redteam.md,prompts/prompt_12_ci_gates.md,prompts/prompt_13_extension_generator.md,prompts/prompt_13a_completeness_assessment.md,prompts/prompt_14_roadmap.md,prompts/prompt_15_scaffold.md | Delete Field-by-Field schema-duplicated content from 18 prompts
REQ | 2-05 | prompts/prompt_00_project_charter.md,prompts/prompt_01_capabilities.md,prompts/prompt_02_system_sketch.md,prompts/prompt_03_glossary.md,prompts/prompt_04_functional_requirements.md | Merge seed triple redundancy by consolidating Seed Order, Context To Ingest, and Extraction Intent sections
REQ | 3-01 | canon/README.md | Document canon namespace convention for cn:core, cn:project, cn:starter namespaces
REQ | 3-02 | canon/manifest.json | Move 18 auth-domain-specific canon entries to examples or mark as starter examples
REQ | 3-03 | tools/specdev_tools/canonical/accept.py,tools/specdev_tools/cli.py | Build specdev canon-accept CLI command to promote glossary canonical_proposals to canon manifest
REQ | 3-04 | prompts/prompt_03_glossary.md | Redesign Step 03 prompt as canon population step with canonical_proposals emission guidance
REQ | 3-05 | canon/kinds/stage.json,canon/kinds/environment.json,schema/core/collections.schema.json | Consolidate stage and environment maintenance with canon as single source of truth
REQ | 4-01 | prompts/prompt_04_functional_requirements.md | Add step-specific synthesis phases and implicit requirements discovery checklist to Step 04
REQ | 4-02 | prompts/prompt_05_interface_contracts.md | Add step-specific synthesis phases and REST design heuristics to Step 05
REQ | 4-03 | prompts/prompt_06_invariants.md | Add step-specific synthesis phases and invariant discovery checklist to Step 06
REQ | 4-04 | prompts/prompt_07_nfrs.md | Add step-specific synthesis phases with granularity heuristics and weak-vs-strong examples to Step 07
REQ | 4-05 | prompts/prompt_08_fixtures.md | Add step-specific synthesis phases and weak-vs-strong examples to Step 08
REQ | 4-06 | prompts/prompt_09_impl_plan.md | Add step-specific synthesis phases and extraction mandate to Step 09 referencing new depends_on field
REQ | 4-07 | prompts/prompt_00_project_charter.md,prompts/prompt_01_capabilities.md,prompts/prompt_02_system_sketch.md,prompts/prompt_03_glossary.md | Enrich Steps 00-03 prompts with synthesis reasoning phases and step-specific checklists
REQ | 4-08 | prompts/prompt_10_governance.md,prompts/prompt_11_redteam.md,prompts/prompt_12_ci_gates.md | Enrich Steps 10-12 prompts with step-specific synthesis reasoning phases
REQ | 4-09 | 14 generic-role prompts | Replace generic specification author role with step-specific roles for 14 prompts
REQ | 4-10 | All 22 prompts | Add 2-3 step-specific reasoning verification items to each prompt's Coverage Closure body
REQ | 4-11 | prompts/prompt_12_ci_gates.md,prompts/prompt_14_roadmap.md,prompts/prompt_15_scaffold.md,prompts/prompt_16_impl_context.md,prompts/prompt_16a_impl_planner.md,prompts/prompt_16b_impl_coder.md,prompts/prompt_16c_impl_reviewer.md | Add extraction intent priority grouping to 7 late-stage prompts distinguishing primary and reference sources
REQ | 4-12 | prompts/prompt_05_interface_contracts.md,prompts/prompt_06_invariants.md,prompts/prompt_07_nfrs.md | Add semantic drift prevention guidance to use exact FR statement text in trace notes
REQ | 4-13 | prompts/prompt_00_project_charter.md,prompts/prompt_01_capabilities.md,prompts/prompt_06_invariants.md,prompts/prompt_07_nfrs.md,prompts/prompt_16_impl_context.md,all prompts | Fix Output Contract examples in multiple prompts for correctness and consistency
REQ | 4-14 | prompts/prompt_14_roadmap.md | Add guidance explaining relationship between FR and task acceptance criteria in Step 14
REQ | 4-15 | prompts/prompt_04_functional_requirements.md,prompts/prompt_05_interface_contracts.md,prompts/prompt_06_invariants.md,prompts/prompt_07_nfrs.md,prompts/prompt_08_fixtures.md,prompts/prompt_14_roadmap.md | Add cross-artifact consistency checks and misc fixes to step prompts
REQ | 5-01 | tools/specdev_tools/validation/traceability_closure.py | Implement capability to FR pairwise completeness check with W561 UNCOVERED_CAPABILITY warning
REQ | 5-02 | tools/specdev_tools/validation/traceability_closure.py | Implement FR to API pairwise completeness check with W564 UNCOVERED_FR_API warning
REQ | 5-03 | tools/specdev_tools/validation/traceability_closure.py | Implement FR to fixture and FR to milestone completeness checks with W565, W566 warnings
REQ | 5-04 | tools/specdev_tools/validation/traceability_closure.py | Implement milestone to task completeness check with W567 INCOMPLETE_MILESTONE_DECOMPOSITION warning
REQ | 5-05 | tools/specdev_tools/validation/validators/step_16c.py | Implement Step 16c FR coverage completeness check for verified verdicts
REQ | 5-06 | tools/specdev_tools/cli.py,tools/specdev_tools/validation/traceability_closure.py | Add specdev completeness-check CLI command for all pairwise completeness checks
REQ | 5-07 | schema/13a_completeness_assessment.schema.json,prompts/prompt_13a_completeness_assessment.md,tools/specdev_tools/validation/validators/step_13a.py | Redesign Step 13a as machine-computed coverage with structured dimensions and threshold validation
REQ | 6-01 | tools/specdev_tools/validation/validators/step_00.py,tools/specdev_tools/validation/validators/step_04.py | Split Self-Audit Gate into separate Critical Path vs Coverage Path with lower threshold for coverage items
REQ | 6-02 | prompts/prompt_00_project_charter.md,prompts/prompt_04_functional_requirements.md | Update prompt self-audit gate items to reflect split critical vs coverage paths
REQ | 6-03 | tools/specdev_tools/validation/validators/step_00.py,tools/specdev_tools/validation/validators/step_04.py,schema/step_base.schema.json | Implement gate bypass mechanism allowing CI/flag override with documentation audit trail
REQ | 6-04 | tools/specdev_tools/validation/validators/step_00.py,tools/specdev_tools/validation/validators/step_04.py,prompts/prompt_00_project_charter.md,prompts/prompt_04_functional_requirements.md | Document Gate Bypass Audit Trail protocol for transparency in gate overrides
REQ | 7-01 | tools/specdev_tools/validation/validators/step_06.py | Fix step_06 invariant language regex that incorrectly blocks valid identifier names
REQ | 7-02 | tools/specdev_tools/validation/ | Add E503 enforcement for required `constraint` property in all invariant objects
REQ | 7-03 | tools/specdev_tools/validation/hallucination_lint.py | Fix hallucination-lint to suppress false positives in canonical multiword references
REQ | 7-04 | tools/specdev_tools/validation/ | Enhance traceability_closure to detect and report loose traceability links (target IDs not found)
REQ | 7-05 | tools/specdev_tools/validation/ | Implement W545 orphaned item detection for fixture targets and roadmap dependencies
REQ | 7-06 | tools/specdev_tools/validation/linters/ | Add schema-aware comment validation for Tier 3 semantic content fields
REQ | 7-07 | tools/specdev_tools/validation/ | Implement validator inter-artifact sync check for Step 12 CI gate dependencies
REQ | 7-08 | tools/specdev_tools/validation/validators/step_08.py | Fix Step 08 fixture test_data validation to support all JSON types not just objects
REQ | 7-09 | tools/specdev_tools/validation/validators/step_09.py | Fix Step 09 schema validation of milestone dependencies when not all referenced milestones exist
REQ | 7-10 | tools/specdev_tools/validation/ | Implement W571 coverage analysis for dependencies vs imports in code scaffold extraction
REQ | 7-11 | tools/specdev_tools/validation/validators/step_15.py | Fix Step 15 scaffold validation to handle relative file paths and import statements
REQ | 7-12 | tools/specdev_tools/validation/ | Add E602 enforcement for method enum validation in Step 15 scaffold interface_ref items
REQ | 8-01 | tools/IMPLEMENTATION_GUIDE.md | Create IMPLEMENTATION_GUIDE documenting Batch 0-8 task execution with troubleshooting
REQ | 8-02 | tools/specdev_tools/validation/ | Build machine-readable validator capability inventory as JSON
REQ | 8-03 | docs/MIGRATION_GUIDE.md | Create MIGRATION_GUIDE for host repos managing breaking changes from Batch 0a
REQ | 8-04 | CHANGELOG.md | Add version 0.5.0 changelog entry documenting all breaking and feature changes
REQ | 8-05 | docs/agents/ | Create agent runner templates for Steps 00-16c workflow automation
REQ | 8-06 | docs/ | Create runbook for prompt-schema sync workflow
REQ | 8-07 | docs/ | Create decision log entries documenting design choices from Batches 0-8
REQ | 8-08 | tests/integration/ | Add integration test suite for pairwise completeness checks and cross-artifact traceability
REQ | 8-09 | tools/specdev_tools/ | Document canonical-integrity check improvements and canon-schema alignment validation
REQ | 8-10 | docs/TROUBLESHOOTING.md | Create troubleshooting guide for common validation failures and remediation steps
URLS | none
