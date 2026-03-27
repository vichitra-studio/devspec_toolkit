REQ | Task-0 | changelog/unreleased.md, changelog/unreleased.yaml | Changelog: Document breaking schema change for tech_stack promotion to required in Step 02
REQ | Task-0a | changelog/unreleased.md | Edit unreleased.md: Add bullet under existing Breaking Changes section documenting tech_stack requirement change and migration steps
REQ | Task-0b | changelog/unreleased.yaml | Create unreleased.yaml with two change entries (add_field, add_constraint) using action: ai_assisted
REQ | Task-1 | schema/02_system_sketch.schema.json | Schema: Add tech_stack to Step 02 with $ref to vc:core:collections#techStack requiring all 4 categories
REQ | Task-2 | prompts/prompt_02_system_sketch.md | Prompt: Add Technology Resolution to Step 02 operating flow as 5-phase process
REQ | Task-2a | prompts/prompt_02_system_sketch.md | Update extraction intent for seed_tech_stack.md to explicitly mention tech_stack population
REQ | Task-2b | prompts/prompt_02_system_sketch.md | Add Resolve Tech phase to operating flow after Decompose
REQ | Task-2c | prompts/prompt_02_system_sketch.md | Update purpose statement to mention technology stack and downstream awareness
REQ | Task-2d | prompts/prompt_02_system_sketch.md | Add heuristics for tech_stack completeness and AUTO-DERIVE marker resolution
REQ | Task-2e | prompts/prompt_02_system_sketch.md | Add coverage closure items for tech_stack validation and AUTO-DERIVE resolution
REQ | Task-2f | prompts/prompt_02_system_sketch.md | Update step-specific completeness checklist with tech_stack coverage requirements
REQ | Task-2g | prompts/prompt_02_system_sketch.md | Add tech_stack example to output contract JSON
REQ | Task-2h | prompts/prompt_02_system_sketch.md | Update downstream consumer count from 6 to 12 at line 8
REQ | Task-3 | prompts/prompt_09_impl_plan.md | Prompt: Step 09 inherits tech_stack from Step 02 instead of generating it
REQ | Task-3a | prompts/prompt_09_impl_plan.md | Update extraction intent to mention tech_stack as inherited baseline from Step 02
REQ | Task-3b | prompts/prompt_09_impl_plan.md | Change Resource phase to inherit and optionally refine tech_stack from Step 02
REQ | Task-3c | prompts/prompt_09_impl_plan.md | Update Reconcile phase to enforce superset rule (Step 09 >= Step 02)
REQ | Task-3d | prompts/prompt_09_impl_plan.md | Update Negative Constraints to reference Step 02 tech_stack
REQ | Task-3e | prompts/prompt_09_impl_plan.md | Update step-specific checklist to reflect inheritance and superset rule
REQ | Task-4 | prompts/prompt_05_interface_contracts.md | Prompt: Step 05 extracts tech_stack from Step 02 for API style determination
REQ | Task-4a | prompts/prompt_05_interface_contracts.md | Update extraction intent to mention tech_stack framework/language choices for API design
REQ | Task-5 | prompts/prompt_07_nfrs.md | Prompt: Step 07 extracts tech_stack from Step 02 for performance baseline expectations
REQ | Task-5a | prompts/prompt_07_nfrs.md | Update extraction intent to mention tech_stack runtime characteristics and performance implications
REQ | Task-6 | prompts/prompt_08_fixtures.md | Prompt: Step 08 extracts tech_stack from Step 02 for test framework determination
REQ | Task-6a | prompts/prompt_08_fixtures.md | Update extraction intent to mention tech_stack framework choices for fixture format and test patterns
REQ | Task-7 | prompts/prompt_11_redteam.md | Prompt: Step 11 extracts tech_stack from Step 02 for security analysis
REQ | Task-7a | prompts/prompt_11_redteam.md | Update extraction intent to mention tech_stack framework/runtime CVE surfaces and security defaults
REQ | Task-8 | prompts/prompt_15_scaffold.md | Prompt: Step 15 sources tech_stack from Step 02 as primary source with Step 09 supplementary
REQ | Task-8a | prompts/prompt_15_scaffold.md | Consolidate Step 02 extraction to include tech_stack and update Step 09 extraction as refinement source
REQ | Task-9 | tests/fixtures/step_02/ | Test Fixtures: Add tech_stack to all Step 02 fixtures
REQ | Task-9a | tests/fixtures/step_02/valid_standard.json | Add realistic tech_stack with all 4 categories (languages, frameworks, infrastructure, tools)
REQ | Task-9b | tests/fixtures/step_02/valid_minimal.json | Add minimal tech_stack with one entry per category
REQ | Task-9c | tests/fixtures/step_02/valid_external_integration.json | Add tech_stack consistent with external integration scenario
REQ | Task-9d | tests/fixtures/step_02/invalid_missing_tech_stack.json | Create new fixture testing missing tech_stack in isolation with valid components
REQ | Task-9e | tests/fixtures/step_02/ | Add minimal tech_stack to all 19 other invalid fixtures to prevent unintended failures
REQ | Task-9f | tests/integration/test_step_02.py | Add invalid_missing_tech_stack.json to hardcoded invalid_fixtures list
REQ | Task-10 | tools/specdev_tools/validation/validators/step_02.py | Deep Validator: Add tech-stack component type cross-checks (optional)
REQ | Task-10-func | tools/specdev_tools/validation/validators/step_02.py, tools/specdev_tools/core/errors.py | Implement check_tech_stack_component_consistency function using W606 error code
REQ | Task-11 | tools/specdev_tools/validation/validators/step_14.py, tools/specdev_tools/core/errors.py | Step 14 Validator: Load and validate tech_stack from Step 02 using new W605 code
REQ | Task-11-step1 | tools/specdev_tools/core/errors.py | Register W605 error code: TECH_STACK_02_MISSING
REQ | Task-11-step2 | tools/specdev_tools/validation/validators/step_14.py | Add _load_step02_tech_stack_names function and cross-check for superset validation
REQ | Task-12 | tools/step_order.json | Update downstream_consumers for Step 02 to include steps extracting tech_stack
REQ | Task-13 | prompts/prompt_03_glossary.md, prompts/prompt_06_invariants.md, prompts/prompt_10_governance.md, prompts/prompt_13_extension_generator.md, prompts/prompt_14_roadmap.md | Prompts: Steps 03, 06, 10, 13, 14 extract tech_stack from Step 02
REQ | Task-13a | prompts/prompt_14_roadmap.md | Update roadmap extraction intent, best practices, and negative constraints to reference Step 02 as tech_stack origin
REQ | Task-13b | prompts/prompt_03_glossary.md | Update glossary extraction to include tech_stack technology names as domain vocabulary
REQ | Task-13c | prompts/prompt_06_invariants.md | Update invariants extraction to include tech_stack for technology-specific constraints
REQ | Task-13d | prompts/prompt_10_governance.md | Update governance extraction to include tech_stack for technology-specific change-control policies
REQ | Task-13e | prompts/prompt_13_extension_generator.md | Update extension generator extraction to recognize tech_stack technology-dependency of extension necessity
REQ | Validation-1 | tests/ | Schema validation: All Step 02 fixtures pass after Tasks 1 and 9
REQ | Validation-2 | tests/ | Full test suite validation: No regressions after implementation
REQ | Validation-3 | tools/step_order.json | DAG lint: downstream_consumers must be consistent
REQ | Validation-4 | spec/ | Seed lint: Seed references remain current
REQ | Validation-5 | spec/ | Canonical integrity: No canonical drift from new tech_stack fields
REQ | Validation-6 | prompts/, tools/step_order.json | Extraction intent check: Prompts match step_order definitions
REQ | Validation-7 | prompts/, schema/ | Prompt-schema sync: Prompt output contracts match schemas
URLS | none
