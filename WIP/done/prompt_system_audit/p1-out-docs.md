# P1-G: Migration Templates & Documentation Gaps -- Findings

## Summary
- Total findings: 18
- Critical: 2 | High: 5 | Medium: 7 | Low: 3 | Info: 1

## Migration Template Analysis

### Overview

19 migration templates exist at `prompts/migration/template_*.md`, covering steps 00 through 16. They are consumed by the migration runner (`tools/specdev_tools/migration/runner.py`) via `_render_prompt()` which loads them when executing AI-assisted migration steps. The planner (`tools/specdev_tools/migration/planner.py`) maps step prefixes to template filenames via `STEP_TO_TEMPLATE` in `tools/specdev_tools/core/constants.py`.

### Missing Templates: 16a, 16b, 16c

Steps 16a, 16b, and 16c are absent from both the template directory and `STEP_TO_TEMPLATE`. This is a genuine gap because:
- The manifest (`docs/agents/manifest.json`) explicitly defines `step_config` for 16a, 16b, and 16c
- `docs/developers/workflows/spec_to_impl.md` documents them as active Trinity Loop steps
- All three use `schema/16_impl_context.schema.json` but have distinct operational semantics (plan/build/review)
- The migration system will silently skip template assignment when encountering diffs for these steps

Without templates, `specdev align prompts` cannot generate migration guidance for Trinity Loop artifacts. Since these steps produce per-milestone `spec/impl_context/{step_id}.json` files, migrations involving these are the most complex and most in need of AI-assisted guidance.

### Template-Schema Drift

All 19 templates show structural drift from current schemas. The templates describe generic field lists that have not been updated to match the schemas hardened by audit rounds R7-R8. Specific examples:

| Template | Describes | Schema Actually Requires |
|---|---|---|
| `template_charter.md` | `project_name`, `vision`, `goals`, `stakeholders`, `constraints` | `problem_statement`, `success_metrics`, `stakeholders`, `user_segments`, `in_scope`, `out_of_scope` |
| `template_frs.md` | `requirements`, `id`, `description`, `priority`, `owner`, `capability_refs`, `acceptance_criteria` | `functional_requirements` (array), each with `fr_id`, `statement`, `trace`, `acceptance_criteria`, `owner` |
| `template_governance.md` | `commit_rules`, `pr_rules`, `branch_rules`, `roles` | `spec_first_policy`, `commit_message_rules`, `pr_rules`, `review_policy` |
| `template_system_sketch.md` | `components[].id, name, type` | `components[].component_id, name, responsibilities, owner, trace_refs` |

Every template follows a static pattern: Schema URI, Required Changes, Output Contract, Optional Fields, Validation, Context. None use Handlebars-style `{{VAR}}` interpolation despite the ADR (`docs/ops/adr_template_engine.md`) discussing this as the chosen approach.

### Template Artifact Name Errors

- `template_frs.md` line 33: references `spec/04_functional_requirements.json` but the correct artifact name is `spec/04_fr_list.json`
- `template_extension_generator.md` line 39: references `spec/13_extension_generator.json` but the actual artifact may be `spec/13_extension_manifest.json` (the agents doc at line 57 uses this name)

### Templates vs Step Prompts: Relationship

Migration templates and step prompts serve distinct but overlapping purposes:
- **Step prompts** (`prompts/prompt_NN_*.md`): Full generation contracts for producing artifacts from scratch (Clarify/Emit protocol, Field-by-Field coverage, Self-Audit Gate)
- **Migration templates** (`prompts/migration/template_*.md`): Lightweight guidance for adapting existing artifacts to a new schema version

The migration runner (`runner.py:198-244`) renders templates into migration prompt files that include the template content plus JSON context from the diff. The step prompts are NOT referenced by the migration system. This means migration prompts lack the detailed field-level coverage, sourcing rules, and self-audit gates that step prompts provide.

## Documentation Evaluation

### Active, Current Documents (12 files)

| File | Status | Step Relevance |
|---|---|---|
| `docs/agents/agents.md` | CURRENT | All steps (agent operating protocol) |
| `docs/agents/manifest.json` | CURRENT | All steps (machine-readable agent config) |
| `docs/prompts/shared_expectations.md` | CURRENT | All steps (shared baseline expectations) |
| `docs/developers/getting_started.md` | CURRENT | Onboarding (comprehensive, accurate) |
| `docs/developers/reference.md` | CURRENT | All steps (command cheatsheet, troubleshooting) |
| `docs/developers/path_conventions.md` | CURRENT | All steps (path variables, dual-root convention) |
| `docs/developers/error-codes.md` | CURRENT | All steps (error/warning code reference) |
| `docs/developers/index.md` | CURRENT | Navigation hub |
| `docs/architecture/governance_architecture.md` | CURRENT | Steps 04-16c (trace types, DAG, enforcement tiers) |
| `docs/developers/workflows/discovery.md` | CURRENT | Steps 00-12 (troubleshooting, validation cadence) |
| `docs/developers/workflows/spec_to_impl.md` | CURRENT | Steps 13-16c (Trinity Loop, command cadence) |
| `docs/ops/toolkit_update_checklist.md` | CURRENT | Toolkit maintenance (schema/prompt/canon change workflows) |

### Partially Current Documents (8 files)

| File | Status | Issue |
|---|---|---|
| `docs/developers/extension_schemas.md` | PARTIALLY CURRENT | Example JSON uses `$ref: "vc:core:atoms#kebabId"` -- needs verification against current atom names. Content is accurate but not referenced by prompt_13. |
| `docs/developers/workflows/workflow_align.md` | PARTIALLY CURRENT | Describes `specdev align` workflow accurately but references `dev_env` (should be `devspec_env` per memory). |
| `docs/developers/workflows/workflow_migration.md` | PARTIALLY CURRENT | Legacy manual approach still valid; `specdev align` references correct. References `dev_env` venv. |
| `docs/developers/workflows/workflow_bootstrap_legacy.md` | PARTIALLY CURRENT | Workflow is sound but uses old artifact names (`docs/project_overview.md`, `docs/tech_stack.md`) and legacy prompt patterns (does not use two-phase Clarify/Emit). |
| `docs/developers/workflows/workflow_feature_extension.md` | PARTIALLY CURRENT | Step references correct, but prompt patterns are pre-Clarify/Emit and instruct copy-paste rather than disk-write. |
| `docs/ops/adr_template_engine.md` | PARTIALLY CURRENT | Accepted ADR, but says "14 templates" (now 19) and describes Handlebars `{{VAR}}` syntax that no current template uses. |
| `docs/developers/design/migration_system_spec.md` | PARTIALLY CURRENT | Design spec v0.1.0-draft from 2026-01-14. Still useful as architecture reference but implementation has evolved. |
| `docs/README.md` | PARTIALLY CURRENT | Missing links to several docs (error-codes, workflows beyond discovery). |

### Historical/Archived Documents (20 files under `docs/audit/`)

| Category | Files | Status |
|---|---|---|
| Audit plans/prompts | `r1_hygiene_invariants.md` through `r9_validator_ci_closure.md` (9 files) | HISTORICAL -- audit scope documents from R1-R9 review series |
| Audit findings | `findings/r1_plan.md` through `findings/r9_findings.md` (10 files) | HISTORICAL -- completed audit findings |
| Review protocols | `review_index.md`, `review_protocol.md`, `review_prompt_01-04*.md` (6 files) | HISTORICAL -- review process infrastructure |

These 20+ audit files are historical artifacts from the v0.3.0 structural audit. They are NOT living documents -- they record completed work. They should NOT be referenced by prompts or shared_expectations.md.

### Planning Documents (2 files)

| File | Status | Notes |
|---|---|---|
| `docs/plans/phase_0_governance_plan.md` | COMPLETED | Phase 0 governance plan, goals G1-G7. Historical record of completed work. |
| `docs/plans/optimisation_backlog.md` | ACTIVE | OPT-001 through OPT-006. OPT-001/002/003 completed; OPT-004/005/006 open. Living document. |

### Tool-Specific Documents (4 files)

| File | Status | Notes |
|---|---|---|
| `docs/developers/tools/align.md` | CURRENT | `specdev align` CLI documentation |
| `docs/developers/tools/changelog_parser.md` | CURRENT | Changelog parser module documentation |
| `docs/developers/tools/prompt_context.md` | CURRENT | `prompt-context` command documentation |
| `docs/developers/tools/schema_differ.md` | CURRENT | Schema differ library documentation |

### Tooling Guides (2 files)

| File | Status | Notes |
|---|---|---|
| `docs/developers/tooling/coverage_matrix.md` | CURRENT | Trace matrix mechanics and CI integration |
| `docs/developers/tooling/gap_hunter_checklist.md` | CURRENT | Manual gap-hunting procedure |

## Findings

### FINDING-G01: Missing migration templates for steps 16a, 16b, 16c
- **Severity**: HIGH
- **Category**: DOCS
- **Location**: `tools/specdev_tools/core/constants.py:15-35`
- **Description**: `STEP_TO_TEMPLATE` has no entries for steps 16a, 16b, or 16c. The migration planner will assign `template=None` for diffs targeting these steps, causing the runner to generate minimal prompts without step-specific guidance.
- **Evidence**: `constants.py` maps "00" through "16" but stops there. `docs/agents/manifest.json` lines 37-51 define `step_config` for 16a/16b/16c confirming they are active steps.
- **Recommendation**: Create `template_impl_planner.md` (16a), `template_impl_coder.md` (16b), `template_impl_reviewer.md` (16c) and add mappings `"16a": "template_impl_planner.md"`, `"16b": "template_impl_coder.md"`, `"16c": "template_impl_reviewer.md"` to `STEP_TO_TEMPLATE`.

### FINDING-G02: All 19 migration templates have significant schema drift
- **Severity**: CRITICAL
- **Category**: DOCS
- **Location**: `prompts/migration/template_charter.md` (and all 18 others)
- **Description**: Templates describe field names and structures that do not match current schemas. The R7-R8 audit rounds significantly changed schema field names, required fields, and structures, but migration templates were never updated.
- **Evidence**: `template_charter.md` lists `project_name`, `vision`, `goals`, `constraints` as required. Schema `00_charter.schema.json` actually requires `problem_statement`, `success_metrics`, `stakeholders`, `user_segments`. Similar drift in `template_frs.md` (uses `requirements` instead of `functional_requirements`), `template_governance.md` (uses `commit_rules`, `branch_rules`, `roles` instead of `spec_first_policy`, `commit_message_rules`), and others.
- **Recommendation**: Regenerate all 19 templates from current schemas. Each template's "Required Changes" section should list actual schema `required` fields and property names.

### FINDING-G03: template_frs.md references wrong artifact filename
- **Severity**: MEDIUM
- **Category**: DOCS
- **Location**: `prompts/migration/template_frs.md:33`
- **Description**: Validation command references `spec/04_functional_requirements.json` but the canonical artifact name is `spec/04_fr_list.json` (per `schema_registry.json` entry `vc:04-fr-list` mapping to `04_fr_list.schema.json`).
- **Evidence**: Line 33: `./tools/run_specdev.sh validate spec/04_functional_requirements.json --repo-root ./devspec_toolkit`
- **Recommendation**: Change to `spec/04_fr_list.json`.

### FINDING-G04: Migration templates use no interpolation variables
- **Severity**: MEDIUM
- **Category**: DOCS
- **Location**: `prompts/migration/template_*.md` (all 19 files)
- **Description**: The ADR at `docs/ops/adr_template_engine.md` documents a Handlebars-style `{{VAR}}` template engine, but zero templates contain any `{{` interpolation markers. All templates are static markdown. The runner (`runner.py:198-244`) renders them by simply reading file contents and appending JSON context -- the Handlebars renderer in `prompt_generator.py` is never invoked for migration templates.
- **Evidence**: `grep '{{' prompts/migration/` returns no matches. ADR lines 11-13 describe `{{VAR_NAME}}` and `{{#each ITEMS}}` syntax.
- **Recommendation**: Either (a) add interpolation variables to templates so they can be context-aware (e.g., `{{SOURCE_VERSION}}`, `{{TARGET_VERSION}}`, `{{DIFF_FIELDS}}`), or (b) update the ADR to clarify that migration templates are static context documents appended to rendered prompts.

### FINDING-G05: extension_schemas.md not referenced by Step 13 prompt
- **Severity**: MEDIUM
- **Category**: DOCS
- **Location**: `docs/developers/extension_schemas.md`
- **Description**: This document explains the extension architecture, naming conventions (`ext_NN_topic.json`), manifest structure, and how to author extension schemas. It is directly relevant to Step 13 (Extension Generator) but `prompts/prompt_13_extension_generator.md` does not reference it. The document would add valuable context for naming patterns, schema authoring guidelines, and the extension-to-roadmap consumption flow.
- **Evidence**: `grep -r 'extension_schemas' prompts/` returns no matches.
- **Recommendation**: Add a reference in `prompt_13_extension_generator.md`'s context/input section: `$TOOLKIT_ROOT/docs/developers/extension_schemas.md` for extension naming conventions and schema authoring guidance.

### FINDING-G06: agents.md not referenced by any step prompt
- **Severity**: LOW
- **Category**: DOCS
- **Location**: `docs/agents/agents.md`
- **Description**: The agent operating contract is referenced by `docs/developers/reference.md` and `docs/developers/getting_started.md` but not by any step prompt. Since step prompts already embed the two-phase protocol inline, this is appropriate -- agents.md serves as a standalone reference for agent runners, not as prompt input. However, the "Runner Tips" section (lines 84-97) contains guidance not replicated in prompts.
- **Evidence**: `grep -r 'agents.md' prompts/` returns no matches.
- **Recommendation**: No change needed for prompt references. The agents.md is correctly positioned as runner infrastructure, not prompt input. Document this boundary in shared_expectations.md for clarity.

### FINDING-G07: ADR template engine doc has stale template count
- **Severity**: LOW
- **Category**: DOCS
- **Location**: `docs/ops/adr_template_engine.md:31,38`
- **Description**: ADR states "14 templates" in rationale (line 31) and alternatives verdict (line 38). The actual count is 19 templates.
- **Evidence**: `ls prompts/migration/template_*.md | wc -l` yields 19.
- **Recommendation**: Update count references from 14 to 19.

### FINDING-G08: workflow_bootstrap_legacy.md uses outdated patterns
- **Severity**: MEDIUM
- **Category**: DOCS
- **Location**: `docs/developers/workflows/workflow_bootstrap_legacy.md`
- **Description**: The bootstrap workflow predates the two-phase Clarify/Emit protocol. It instructs users to copy-paste prompts and paste AI output into spec files, rather than having agents write directly to disk. Artifact names like `docs/project_overview.md` and `docs/tech_stack.md` are not part of the current seed system (which uses `docs/seed/seed_overview.md` and `docs/seed/seed_tech_stack.md`). Step 1.2 incorrectly maps tech stack to `spec/01_capabilities.json`.
- **Evidence**: Lines 37, 69 reference `docs/project_overview.md` (not a canonical seed path). Lines 44-54 use a pre-Clarify/Emit prompt pattern. Line 69: "Convert docs/tech_stack.md into spec/01_capabilities.json" -- capabilities are derived from seed_overview, not tech_stack.
- **Recommendation**: Rewrite to use current seed paths and two-phase protocol. Fix step mapping (tech stack feeds Step 02, not Step 01).

### FINDING-G09: workflow_feature_extension.md uses pre-Clarify/Emit patterns
- **Severity**: MEDIUM
- **Category**: DOCS
- **Location**: `docs/developers/workflows/workflow_feature_extension.md`
- **Description**: Feature extension workflow instructs users with ad-hoc prompt patterns instead of referencing the canonical step prompts' two-phase flow. Lines 41-46 use a "PROMPT: I am adding feature [Name]" pattern that bypasses the Self-Audit Gate.
- **Evidence**: Lines 41-46 instruct copying a generic prompt rather than running the step's canonical prompt with its built-in Clarify/Emit protocol.
- **Recommendation**: Update to reference canonical step prompts and the two-phase protocol. Each step should link to its prompt file rather than inlining ad-hoc prompts.

### FINDING-G10: docs/README.md missing several doc references
- **Severity**: LOW
- **Category**: DOCS
- **Location**: `docs/README.md`
- **Description**: The documentation index omits links to several active documents: `error-codes.md`, `path_conventions.md`, `workflow_migration.md`, `workflow_align.md`, `workflow_bootstrap_legacy.md`, `workflow_feature_extension.md`, `governance_architecture.md`, `optimisation_backlog.md`, and all tool-specific docs.
- **Evidence**: The "For Developers" table has 4 entries. The full developer doc set has 15+ files.
- **Recommendation**: Add missing doc links to the README index, organized by category.

### FINDING-G11: Migration templates lack reference to step prompts
- **Severity**: HIGH
- **Category**: DOCS
- **Location**: `prompts/migration/template_*.md` (all 19)
- **Description**: Migration templates do not reference their corresponding step prompt for full field-level coverage. When a migration requires regenerating substantial content (e.g., all charter fields changed), the template provides only a shallow field checklist. The step prompt has the complete Self-Audit Gate and field-by-field coverage needed for correct output.
- **Evidence**: No template contains a reference like "For complete field coverage, see `prompts/prompt_NN_*.md`".
- **Recommendation**: Add a "Full Generation Reference" section to each template linking to the corresponding step prompt: "For complete field-by-field requirements, refer to `$TOOLKIT_ROOT/prompts/prompt_NN_name.md`."

### FINDING-G12: No docs map step-to-doc relevance for prompt context
- **Severity**: HIGH
- **Category**: DOCS
- **Location**: N/A (missing artifact)
- **Description**: No document maps which docs are relevant to which steps. This means prompts cannot systematically reference documentation that would improve output quality. For example:
  - Step 02 (System Sketch) would benefit from `governance_architecture.md` sections on component topology
  - Step 05 (Interfaces) would benefit from `coverage_matrix.md` for trace link expectations
  - Step 10 (Governance) would benefit from `governance_architecture.md` for enforcement tiers
  - Step 13 (Extensions) would benefit from `extension_schemas.md` for naming and authoring
  - Steps 14-16c would benefit from `spec_to_impl.md` for workflow context
- **Evidence**: Only `shared_expectations.md` and `reference.md` are referenced by prompts. No other doc-to-step mapping exists.
- **Recommendation**: Create a step-to-doc relevance map (can be in shared_expectations.md or a new section of reference.md) listing which docs add context for each step. This enables both human authors and agent orchestrators to provide relevant context.

### FINDING-G13: audit/ docs are historical but not marked as archived
- **Severity**: INFO
- **Category**: DOCS
- **Location**: `docs/audit/` (20+ files)
- **Description**: The entire `docs/audit/` directory contains completed review artifacts from the v0.3.0 structural audit (R1-R9). These are valuable historical records but are not living documents. They should not be confused with current documentation.
- **Evidence**: `review_index.md` line 1: "Review Series Index -- DevSpec Toolkit v0.3.0 Structural Audit". All findings reference the now-completed R1-R9 reviews.
- **Recommendation**: Consider adding an `_ARCHIVED.md` marker or moving to `docs/audit/archive/` to signal these are completed historical records.

### FINDING-G14: Migration system does not leverage step prompts for semantic migrations
- **Severity**: HIGH
- **Category**: DOCS
- **Location**: `tools/specdev_tools/migration/runner.py:198-244`
- **Description**: The migration runner renders templates as static markdown blocks appended with JSON diff context. For AI-assisted steps, the generated prompt file does not reference the canonical step prompt that contains the complete field-by-field specification, Self-Audit Gate, and Coverage Closure rules. This means AI-assisted migrations operate with significantly less guidance than fresh generation.
- **Evidence**: `_render_prompt()` loads only the template file and step context. It never references `prompts/prompt_NN_*.md`.
- **Recommendation**: Enhance `_render_prompt()` to include a reference to the canonical step prompt path, or better, include the step prompt's field-by-field section directly. This is a code concern but has doc implications since templates should document this integration.

### FINDING-G15: governance_architecture.md relevant to multiple steps but unreferenced
- **Severity**: MEDIUM
- **Category**: DOCS
- **Location**: `docs/architecture/governance_architecture.md`
- **Description**: This document contains authoritative information about trace types, the step dependency DAG, seed propagation boundaries, prompt architecture, and enforcement tiers. This content is directly relevant to steps that deal with traceability (04, 05, 06, 08), governance (10), and the pipeline topology (all steps). No prompt references it.
- **Evidence**: `grep -r 'governance_architecture' prompts/` returns no matches. The document covers: canon-backed trace types (relevant to all trace-producing steps), step dependency DAG (relevant to orchestration), seed propagation boundary (relevant to steps 00-04), enforcement tiers (relevant to step 12 CI Gates).
- **Recommendation**: Reference relevant sections from step prompts that deal with trace types and governance. At minimum, add it as context for steps 10 (governance) and 12 (CI gates).

### FINDING-G16: shared_expectations.md lacks doc loading guidance
- **Severity**: HIGH
- **Category**: DOCS
- **Location**: `docs/prompts/shared_expectations.md`
- **Description**: shared_expectations.md defines canonical reuse rules, quality protocol, and step-order policy, but has no guidance on which documentation files are available or how they relate to steps. Agent orchestrators and human users have no way to discover which docs would improve a step's output without manually browsing the docs directory.
- **Evidence**: The file contains 51 lines covering DoR, working increment, checks, canonical reuse, quality protocol, step-order policy, and failure modes. No section addresses available documentation resources.
- **Recommendation**: Add a "Documentation Resources" section listing key docs and their step relevance. This is the P1-G content evaluation -- P1-C owns the mechanism for how docs are loaded.

### FINDING-G17: workflow_align.md and workflow_migration.md reference wrong venv name
- **Severity**: MEDIUM
- **Category**: DOCS
- **Location**: `docs/developers/workflows/workflow_align.md:38`, `docs/developers/workflows/workflow_migration.md` (by reference)
- **Description**: workflow_align.md line 38 references `source dev_env/bin/activate` but project memory confirms the correct venv name is `devspec_env`.
- **Evidence**: Line 38: `source dev_env/bin/activate`. Memory note: "Virtualenv: `devspec_env` (not `dev_env`)".
- **Recommendation**: Update venv references from `dev_env` to `devspec_env` in both workflow docs.

### FINDING-G18: Template-to-prompt consolidation opportunity
- **Severity**: MEDIUM
- **Category**: DOCS
- **Location**: `prompts/migration/template_*.md` (all 19)
- **Description**: Migration templates and step prompts have significant content overlap (schema URIs, field requirements, validation commands, context about step relationships). Templates could be substantially simplified if they referenced step prompts for field-level detail and focused only on migration-specific concerns (what changed between versions, how to transform existing data, what to preserve). Currently templates duplicate a subset of prompt content -- often an outdated subset.
- **Evidence**: Every template has "Schema URI", "Required Changes", "Output Contract", "Optional Fields", "Validation", "Context" sections. The step prompts cover all of this in more detail and with more accuracy.
- **Recommendation**: Refactor templates to focus on migration-specific concerns: (1) what changed in this schema version, (2) how to transform existing data, (3) what IDs must be preserved. Reference the step prompt for complete field requirements. This reduces maintenance burden and eliminates drift.

## Questions Answered

### 1. Are migration templates for 16a, 16b, 16c needed? What breaks without them?

Yes, they are needed. Without them, `specdev align prompts` generates minimal prompts for Trinity Loop artifacts with no step-specific guidance. The migration runner falls back to a generic prompt containing only JSON context. Since 16a/16b/16c produce the most complex artifacts (per-milestone implementation plans with checklists, security fixtures, delivery monitoring, and drift schedules), the lack of migration templates is most impactful for these steps.

### 2. Do migration templates reflect current schemas?

No. All 19 templates have significant drift from current schemas. Field names, required fields, and structural expectations are outdated. See FINDING-G02 for details.

### 3. Which of the 53 docs are stale vs current?

- **Current (12)**: agents.md, manifest.json, shared_expectations.md, getting_started.md, reference.md, path_conventions.md, error-codes.md, index.md, governance_architecture.md, discovery.md, spec_to_impl.md, toolkit_update_checklist.md
- **Partially current (8)**: extension_schemas.md, workflow_align.md, workflow_migration.md, workflow_bootstrap_legacy.md, workflow_feature_extension.md, adr_template_engine.md, migration_system_spec.md, docs/README.md
- **Historical/archived (20+)**: All docs/audit/ files
- **Active planning (2)**: phase_0_governance_plan.md (completed), optimisation_backlog.md (active)
- **Tool docs (4)**: align.md, changelog_parser.md, prompt_context.md, schema_differ.md (current)
- **Tooling guides (2)**: coverage_matrix.md, gap_hunter_checklist.md (current)

### 4. For each step, which docs would add valuable context if referenced?

| Step(s) | Relevant Unreferenced Docs |
|---|---|
| 00-04 (seed phase) | `governance_architecture.md` (seed propagation boundary) |
| 04, 05, 06, 08 | `coverage_matrix.md` (trace link expectations), `governance_architecture.md` (trace types) |
| 10 | `governance_architecture.md` (enforcement tiers, commit rules) |
| 12 | `governance_architecture.md` (CI integration patterns) |
| 13 | `extension_schemas.md` (naming conventions, schema authoring) |
| 14-16c | `spec_to_impl.md` (workflow context, Trinity Loop mechanics) |
| All | `error-codes.md` (understanding validation failures) |

### 5. Should agents.md be mandatory reading for all steps or just 16a-16c?

agents.md should be read once by the agent orchestrator, not per-step. It defines the two-phase protocol and operational contract that applies to all steps equally. Individual step prompts already embed the necessary protocol instructions inline. agents.md is correctly positioned as runner infrastructure, not step input.

### 6. What is the relationship between migration templates and step prompts? Can they be consolidated?

Migration templates are lightweight guides for adapting existing artifacts. Step prompts are comprehensive generation contracts. They cannot be fully consolidated because they serve different purposes, but templates should be refactored to reference step prompts for field-level detail and focus only on migration-specific concerns (version delta, data transformation, ID preservation). This would eliminate the chronic drift problem where templates describe outdated field structures.
