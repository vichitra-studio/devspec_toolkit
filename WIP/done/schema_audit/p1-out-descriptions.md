# P1-B: Descriptions & LLM Context -- Findings

## Summary

- Total findings: 7
- Critical: 1 | High: 3 | Medium: 2 | Low: 0 | Info: 1

### Methodology

Properties were counted by recursively traversing every schema file's `properties`, `patternProperties`, `items`, `allOf`, `oneOf`, `if`/`then`/`else`, and `$defs` blocks. A property is counted as "having a description" if the property definition object directly contains a `"description"` key. Properties that are purely `$ref` pointers inherit no description from the `$ref` target for the purpose of this count -- the description must be present at the usage site or at the `$defs` definition. `$defs` anchor-level `"description"` (e.g., `atoms.schema.json $defs.metadata`) IS counted. Duplicates within the same file (from conditional branches revisiting the same property path) are deduplicated.

### Verified Counts

| Metric | P0 Baseline | P1-B Verified |
|---|---|---|
| Properties WITH description | 56 | 56 |
| Properties WITHOUT description | 863 | 808 |
| Total properties | 919 | 864 |
| Coverage | 6.1% | 6.5% |

The discrepancy (919 vs 864) is due to P0 counting methodology differences -- likely double-counting properties in conditional branches. The 56 descriptions match exactly.

---

## Findings

### FINDING-001: 93.5% of properties lack descriptions -- critical LLM context gap

- **Severity**: CRITICAL
- **Category**: DESCRIPTION
- **Location**: All 26 schema files
- **Description**: 808 of 864 unique properties across all schema files have no `"description"` field. This means LLMs consuming these schemas for spec generation have almost no semantic context beyond property names. For ambiguous properties (e.g., `scope`, `status`, `target`, `type` -- all of which appear with different semantics in different schemas), the lack of descriptions creates a high risk of hallucination or incorrect field usage.
- **Evidence**: Full inventory in Section "Complete Missing Description Inventory" below.
- **Recommendation**: Add descriptions to all 808 properties. Prioritize: (1) core/ definitions (propagate to all consumers), (2) ambiguous properties, (3) step-specific domain properties. See Question 2 table for draft descriptions.

---

### FINDING-002: 19 of 56 existing descriptions are identical boilerplate ("Optional migration notes...")

- **Severity**: HIGH
- **Category**: DESCRIPTION
- **Location**: `_migration_notes` property in all 19 step schemas
- **Description**: The `_migration_notes` property appears in every step schema and accounts for 19 of the 56 existing descriptions (34%). All 19 have the identical text: "Optional migration notes added during schema version upgrades." (Step 16 has a minor variant: "Optional migration notes added during version upgrades.") This inflates the description coverage metric while providing minimal LLM value -- this property is not used during spec generation.
- **Evidence**:
  - `schema/00_charter.schema.json:184` -- `"description": "Optional migration notes added during schema version upgrades."`
  - (repeated identically in all other step schemas)
  - `schema/16_impl_context.schema.json:1852` -- `"description": "Optional migration notes added during version upgrades."`
- **Recommendation**: These descriptions are adequate for their purpose. The real issue is that when we exclude `_migration_notes`, the effective coverage drops to 37/845 = 4.4%. Focus effort on the 808 properties that actually matter for spec generation.

---

### FINDING-003: core/ definitions have near-zero descriptions -- maximum propagation impact

- **Severity**: HIGH
- **Category**: DESCRIPTION
- **Location**: `schema/core/atoms.schema.json`, `schema/core/collections.schema.json`, `schema/core/errors.schema.json`, `schema/core/canon.schema.json`
- **Description**: Core definitions are referenced by every step schema via `$ref`. Adding descriptions here would propagate context to all consumers. Current state:
  - `core/atoms.schema.json`: 2 descriptions (on `metadata` and `owner` anchors), 4 atoms with zero descriptions (`kebabId`, `timestamp`, `tag`, `screamingSnakeId`)
  - `core/collections.schema.json`: 5 descriptions out of 49 properties (10.2%). Only `traceRef.type`, `seedRef.hash`, `seedRef.version`, `specRefIngested.step_id`, `specRefIngested.hash` have descriptions. 28 collection definitions and 44 sub-properties lack descriptions.
  - `core/errors.schema.json`: 0 of 3 properties have descriptions
  - `core/canon.schema.json`: 0 of 31 properties have descriptions
- **Evidence**: See per-file inventories in "Complete Missing Description Inventory" section.
- **Recommendation**: Prioritize core/ descriptions first. Adding ~80 descriptions to core/ files would provide the highest leverage since these definitions are referenced 448 times across all schemas.

---

### FINDING-004: Ambiguous property names appear with different semantics across schemas -- highest LLM confusion risk

- **Severity**: HIGH
- **Category**: DESCRIPTION
- **Location**: Multiple schemas
- **Description**: Several property names are used across schemas with different types, constraints, or semantic meanings. Without descriptions, an LLM cannot distinguish which semantics apply:

| Property Name | Occurrences | Semantic Variants |
|---|---|---|
| `status` | 13+ schemas | milestone status (pending/in_progress/done/deferred), plan status (active/deferred), docs_impact status (required/not_required), deployment status (pending/success/failed), test status (pass/fail/skip), ci status (green/red), ambiguity status (resolved/tracking/deferred/blocked), execution status (passed/failed/blocked/partial), entry lifecycle (active/deprecated/sunset/retired) |
| `severity` | 9+ schemas | invariant (warn/error), threat (low/medium/high/critical), finding (blocking/major/minor/nit), ambiguity (blocking/non_blocking), error state (info/warn/error/fatal) |
| `type` | 11+ schemas | component type (service/db/...), mitigation type (fr/api/...), specRef type (fr/api/.../code), evidence type (log/snippet/...), action type (file_create/file_edit/...), finding type (bug/gap/...), checklist type (behavior/constraint/...), dependency type (milestone/external) |
| `scope` | 4 schemas | capability scope (in/out/future), invariant scope (object with components/apis), rate_limit scope (ip/client/token/global), seed_manifest scope (stringArray) |
| `description` | 14+ schemas | plain string (most), string with `^\S+\s+\S+.*$` pattern (14_roadmap tasks) |
| `method` | 3 schemas | HTTP verbs 5 (step 05), HTTP verbs 7 (step 15), drift methods (step 16) |
| `id` | 20+ schemas | kebabId (most), screamingSnakeId (step 16 checklist), canonicalId (core/canon) |

- **Evidence**: Step 16 `plan.ambiguities[].severity` uses `["blocking", "non_blocking"]` while `plan.delivery.alerts[].severity` uses `$ref` to `severityLevel` (`["low", "medium", "high", "critical"]`), and `review.findings[].severity` uses `["blocking", "major", "minor", "nit"]`. Without descriptions, an LLM would not know which severity scale applies where.
- **Recommendation**: These properties MUST have descriptions. The draft descriptions in Question 2 below are specifically crafted to disambiguate these cases.

---

### FINDING-005: canon/ schemas and seed_manifest.schema.json have zero description coverage

- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Location**: `canon/kind.schema.json` (0/4), `canon/aliases.schema.json` (0/3), `schema/seed_manifest.schema.json` (0/24), `schema/core/canon.schema.json` (0/31)
- **Description**: These four files have literally zero descriptions on any property. The canon schemas define the canonical registry structure (used by canonical-lint, canonical-integrity, and canonical-autofix tools), and the seed manifest defines the seed document registry (used by seed-lint). Without descriptions, LLMs generating or modifying these structures have no guidance.
- **Evidence**: `canon/kind.schema.json` has properties `$schema`, `registry_version`, `kind`, `entries` -- none with descriptions. `seed_manifest.schema.json` has 24 properties including complex nested structures like `docs_policy` and `nested_order` -- none with descriptions.
- **Recommendation**: Add descriptions to all properties in these files. See Question 2 table.

---

### FINDING-006: $ref-only properties at usage sites lack descriptions -- context lost at point of use

- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Location**: All 19 step schemas
- **Description**: The 10 common required fields (`id`, `owner`, `created_at`, `seed_refs`, `spec_refs_ingested`, `generation_quality`, `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`, `coverage_gaps`) appear in every step schema as pure `$ref` pointers without any description at the usage site. While the `$ref` target (in core/) defines the structural constraints, it does not explain the field's ROLE in the specific step context.

  For example, `owner` in step 00 (charter) means "person responsible for the project charter" while `owner` in step 12 (ci_gates) means "person responsible for CI configuration". An LLM reading only the step schema sees `"owner": {"$ref": "...#owner"}` with no context.

- **Evidence**: In `schema/00_charter.schema.json:12`: `"owner": {"$ref": "https://specdev.local/schema/core/atoms/1#owner"}` -- no description at usage site. The `$ref` target `atoms.schema.json` has a description "Artifact owner -- validated against canon/kinds/owner.json entries." but this is generic.
- **Recommendation**: Add descriptions at the `$ref` usage site in each step schema. These should be step-specific, e.g., "Owner of the project charter artifact. Must be a valid owner from the canonical registry." This is JSON Schema compliant -- `"description"` can coexist with `"$ref"` in Draft 2020-12.

---

### FINDING-007: Step 16 has 240 properties -- 228 without descriptions (95%)

- **Severity**: INFO
- **Category**: DESCRIPTION
- **Location**: `schema/16_impl_context.schema.json`
- **Description**: Step 16 is by far the largest schema (1,868 LOC, 31.1% of total). It has 240 unique properties, of which only 12 have descriptions (5.0%). This single file accounts for 228 of the 808 missing descriptions (28.2%). Additionally, its `$defs` section defines 4 local types (`specRef`, `evidenceObject`, `executionStatus`, `severityLevel`) with 10 properties, none of which have descriptions.

  The 12 existing descriptions in step 16 are:
  1. (top-level) "Unified artifact for the implementation loop..."
  2. `id` -- "The Step ID from the Roadmap..."
  3. `extensions` -- "Structured extensions for domain-specific data."
  4. `plan` -- "Trinity loop plan..."
  5. `plan.summary.target_file_patterns` -- "Explicit list of files/directories..."
  6. `plan.docs_impact` -- "Documentation impact assessment..."
  7. `plan.spec_alignment.requirements_summary` -- "Thematic grouping of requirements."
  8. `plan.spec_alignment.checklist[].implementation` -- "Atomic work definition..."
  9. `plan.context.existing_structures` -- "Known code or non-code structures..."
  10. `plan.drift.checks[].schedule` -- "Named interval or cron expression"
  11. `execution` -- "Global execution summary."
  12. `review.semantic_review.scope_delta` -- "Free-text summary of any scope creep..."

- **Evidence**: See step 16 section in complete inventory below.
- **Recommendation**: Treat step 16 as a dedicated batch in the fix plan due to its size. The 228 descriptions can be added in a single file edit since they are all in one file.

---

## Question 1: Complete Missing Description Inventory

### Methodology
Every `properties` key at every nesting level was traversed. Properties inside `$defs`, `allOf`/`oneOf` branches, `if`/`then`/`else` conditionals, and nested `items` were all included. Deduplication was applied per file by property path.

### Summary by File

| File | With Desc | Without Desc | Total | Coverage |
|---|---|---|---|---|
| canon/aliases.schema.json | 0 | 3 | 3 | 0.0% |
| canon/kind.schema.json | 0 | 4 | 4 | 0.0% |
| schema/00_charter.schema.json | 1 | 35 | 36 | 2.8% |
| schema/01_capabilities.schema.json | 1 | 26 | 27 | 3.7% |
| schema/02_system_sketch.schema.json | 1 | 34 | 35 | 2.9% |
| schema/02a_delivery_baseline.schema.json | 1 | 18 | 19 | 5.3% |
| schema/03_glossary.schema.json | 1 | 20 | 21 | 4.8% |
| schema/04_fr_list.schema.json | 1 | 25 | 26 | 3.8% |
| schema/05_interface_contracts.schema.json | 3 | 37 | 40 | 7.5% |
| schema/06_invariants.schema.json | 1 | 23 | 24 | 4.2% |
| schema/07_nfrs.schema.json | 1 | 24 | 25 | 4.0% |
| schema/08_fixtures.schema.json | 1 | 19 | 20 | 5.0% |
| schema/09_impl_plan.schema.json | 1 | 26 | 27 | 3.7% |
| schema/10_governance.schema.json | 2 | 29 | 31 | 6.5% |
| schema/11_redteam.schema.json | 1 | 28 | 29 | 3.4% |
| schema/12_ci_gates.schema.json | 6 | 26 | 32 | 18.8% |
| schema/13_extension_generator.schema.json | 4 | 19 | 23 | 17.4% |
| schema/13a_completeness_assessment.schema.json | 1 | 24 | 25 | 4.0% |
| schema/14_roadmap.schema.json | 9 | 36 | 45 | 20.0% |
| schema/15_scaffold.schema.json | 3 | 22 | 25 | 12.0% |
| schema/16_impl_context.schema.json | 12 | 228 | 240 | 5.0% |
| schema/seed_manifest.schema.json | 0 | 24 | 24 | 0.0% |
| schema/core/atoms.schema.json | 0 | 0 | 0 | N/A |
| schema/core/canon.schema.json | 0 | 31 | 31 | 0.0% |
| schema/core/collections.schema.json | 5 | 44 | 49 | 10.2% |
| schema/core/errors.schema.json | 0 | 3 | 3 | 0.0% |
| **TOTAL** | **56** | **808** | **864** | **6.5%** |

Note: `core/atoms.schema.json` has 0 counted properties because its 6 definitions are at `$defs` anchor level (not nested `properties`), and those anchors have descriptions counted only if they contain a `"description"` key at the def level (2 do: `metadata` and `owner` -- but these are anchor-level, not within a `properties` block, so the script counts them differently). The 2 descriptions on atoms anchors ARE included in the 56 total via the existing-description audit.

---

## Question 2: Draft Descriptions for All Missing Properties

### Tier 1: CRITICAL -- core/ definitions (highest propagation leverage)

#### core/atoms.schema.json

| Property Path | Proposed Description |
|---|---|
| `$defs.kebabId` | "Lowercase kebab-case identifier (e.g., 'fr-user-login', 'api-session-create'). Used as the primary ID format for all spec artifacts." |
| `$defs.timestamp` | "ISO 8601 date-time string (e.g., '2025-10-16T22:06:04.202593Z'). Used for creation and update timestamps across all artifacts." |
| `$defs.tag` | "Short alphanumeric tag (1-64 chars, allows dots, underscores, colons, hyphens). Used for categorization and filtering of spec artifacts." |
| `$defs.screamingSnakeId` | "SCREAMING_SNAKE_CASE identifier (e.g., 'TASK_01_INIT'). Used for checklist item IDs in Step 16 implementation context." |

#### core/errors.schema.json

| Property Path | Proposed Description |
|---|---|
| `$defs.errorState.code` | "Machine-readable error code in kebab-case (e.g., 'auth-failed', 'rate-limit-exceeded'). Must be unique within the API." |
| `$defs.errorState.message` | "Human-readable error message describing what went wrong and, when possible, how to resolve it." |
| `$defs.errorState.severity` | "Error severity level: 'info' (informational), 'warn' (degraded but functional), 'error' (operation failed), 'fatal' (system-level failure)." |

#### core/collections.schema.json

| Property Path | Proposed Description |
|---|---|
| `$defs.link.rel` | "Relationship type of the link (e.g., 'documentation', 'source', 'related'). Describes how the linked resource relates to this artifact." |
| `$defs.link.href` | "URL or relative path to the linked resource." |
| `$defs.link.spec_ref` | "Optional kebab-case ID linking to a specific spec artifact (e.g., an FR or API) that this link supports." |
| `$defs.traceRef.id` | "Kebab-case ID of the traced artifact (e.g., 'fr-user-login', 'api-session-create'). Must exist in the referenced step's artifact list." |
| `$defs.traceRef.note` | "Optional free-text note explaining the traceability relationship. Required when type is 'external'." |
| `$defs.canonicalRef.id` | "Canonical registry ID in the format 'cn:<namespace>:<kind>:<slug>' (e.g., 'cn:specdev.core:owner:api'). Must exist in a canon/kinds/*.json file." |
| `$defs.canonicalRef.kind` | "Canonical kind category (e.g., 'owner', 'unit', 'trace_type', 'environment'). Must match a registered kind in canon/manifest.json." |
| `$defs.canonicalRef.version` | "Optional version of the canonical entry being referenced." |
| `$defs.canonicalRef.label` | "Optional human-readable label for the canonical entry (e.g., 'Milliseconds', 'API Owner')." |
| `$defs.canonicalRef.alias_used` | "If an alias was used to look up this canonical entry, record the alias string here for audit trail." |
| `$defs.canonicalRef.note` | "Optional free-text note explaining why this canonical reference was chosen or any caveats." |
| `$defs.canonicalProposal.temp_id` | "Temporary kebab-case ID for the proposed canonical entry. Will be replaced by a permanent cn: ID if accepted." |
| `$defs.canonicalProposal.kind` | "Canonical kind for the proposed entry (e.g., 'unit', 'owner', 'environment')." |
| `$defs.canonicalProposal.proposed_label` | "Human-readable label for the proposed canonical entry (e.g., 'Requests per Second')." |
| `$defs.canonicalProposal.definition` | "Clear definition of the proposed canonical term, sufficient for other spec authors to use it consistently." |
| `$defs.canonicalProposal.source_field` | "JSON path within this spec artifact where the proposed term was first encountered (e.g., 'nfrs[0].unit')." |
| `$defs.canonicalProposal.suggested_namespace` | "Dot-separated namespace for the proposed entry (e.g., 'specdev.core', 'myproject.domain'). Must be lowercase alphanumeric with dots." |
| `$defs.canonicalConflict.field_path` | "JSON path within this spec artifact where the conflicting value was found (e.g., 'nfrs[0].category')." |
| `$defs.canonicalConflict.input_value` | "The actual value found in the spec field that could not be unambiguously resolved to a single canonical entry." |
| `$defs.canonicalConflict.candidate_ids` | "List of canonical IDs that the input_value could potentially map to. The LLM or author must choose one." |
| `$defs.canonicalConflict.reason` | "Explanation of why the conflict exists (e.g., 'Multiple entries match the term', 'Deprecated alias with no replacement')." |
| `$defs.techStackItem.name` | "Name of the technology (e.g., 'Python', 'PostgreSQL', 'Docker'). Use the official capitalization." |
| `$defs.techStackItem.version` | "Version string of the technology (e.g., '3.11', '15.4', 'latest'). Use the format expected by the package manager." |
| `$defs.techStackItem.notes` | "Optional notes about this technology choice (e.g., 'Required for ML pipeline', 'Evaluating alternatives')." |
| `$defs.techStackItem.rationale` | "Justification for choosing this technology over alternatives. Helps future maintainers understand the decision." |
| `$defs.techStackItem.tech_stack_ref` | "Canonical reference linking this tech stack item to the canonical registry for consistent naming and versioning." |
| `$defs.techStack.languages` | "Programming languages used in the project. Must include at least the primary implementation language." |
| `$defs.techStack.frameworks` | "Frameworks used (web, testing, etc.). Must include the primary application framework." |
| `$defs.techStack.infrastructure` | "Infrastructure components (databases, message queues, caches, container orchestration, etc.)." |
| `$defs.techStack.tools` | "Development tools (linters, formatters, CI runners, monitoring, etc.)." |
| `$defs.dependencyItem.type` | "Dependency type: 'milestone' (internal project milestone), 'external' (third-party or cross-team dependency requiring owner and note)." |
| `$defs.dependencyItem.id` | "Kebab-case ID of the dependency. For 'milestone' type, must match a milestone_id in Step 09 or 14." |
| `$defs.dependencyItem.owner` | "Owner of the external dependency. Required when type is 'external'." |
| `$defs.dependencyItem.note` | "Description of the dependency relationship and any risks. Required when type is 'external'. Must contain at least two words." |
| `$defs.dependencyItem.dependency_ref` | "Canonical reference for this dependency, linking to the canonical registry for tracking." |
| `$defs.generationQuality.assumptions` | "List of assumptions the AI made during spec generation. Empty array means no assumptions were needed." |
| `$defs.seedRef.seed_id` | "Kebab-case ID of the seed document referenced (e.g., 'seed-overview', 'seed-tech-stack'). Must match a seed_id in seed_manifest.json." |
| `$defs.seedRef.path` | "File path to the seed document relative to the repository root (e.g., 'spec/seeds/seed_overview.md')." |
| `$defs.seedRef.section` | "Specific section within the seed document that was referenced (e.g., 'Architecture Overview', 'Authentication')." |
| `$defs.seedRef.note` | "Optional note explaining how this seed document influenced the generated spec." |
| `$defs.specRefIngested.artifact_id` | "Kebab-case ID of the specific artifact within the upstream step that was ingested (e.g., 'fr-user-login')." |
| `$defs.coverageGap.upstream_item_id` | "ID of the upstream spec item (FR, API, NFR, etc.) that lacks downstream coverage in this artifact." |
| `$defs.coverageGap.source_step` | "Pipeline step number where the uncovered item originates (e.g., '04' for FRs, '05' for APIs). Pattern: NN or NNa-c." |
| `$defs.coverageGap.reason` | "Explanation (min 10 chars) of why this upstream item lacks coverage (e.g., 'Deferred to next milestone', 'Out of scope for this phase')." |

#### core/canon.schema.json

| Property Path | Proposed Description |
|---|---|
| `$schema` | "JSON Schema meta-schema URI. Must be 'https://json-schema.org/draft/2020-12/schema' or the canon registry URI." |
| `registry_version` | "Semantic version of this canonical registry file (e.g., '1.0.0'). Incremented when entries are added, modified, or removed." |
| `entries` | "Array of canonical entries in this registry. Each entry defines a shared vocabulary term with its ID, label, definition, and lifecycle." |
| `aliases` | "Array of alias mappings that resolve alternative names to canonical entry IDs. Used for backward compatibility and common abbreviations." |
| `$defs.lifecycle.introduced_at` | "ISO 8601 date-time when this canonical entry was first added to the registry." |
| `$defs.lifecycle.deprecated_since` | "ISO 8601 date-time when this entry was marked as deprecated. Required when entry status is 'deprecated' or 'sunset'." |
| `$defs.lifecycle.sunset_after` | "ISO 8601 date-time after which this deprecated entry should no longer be used. Required when entry status is 'sunset'." |
| `$defs.lifecycle.retired_at` | "ISO 8601 date-time when this entry was fully retired and removed from active use. Required when entry status is 'retired'." |
| `$defs.lifecycle.replaced_by` | "Canonical ID of the entry that replaces this deprecated/retired entry (e.g., 'cn:specdev.core:unit:ms')." |
| `$defs.lifecycle.deprecation_note` | "Human-readable explanation of why this entry was deprecated and guidance for migration." |
| `$defs.aliasLifecycle.deprecated_since` | "ISO 8601 date when this alias was deprecated. Required for deprecated aliases." |
| `$defs.aliasLifecycle.sunset_date` | "ISO 8601 date after which this deprecated alias should no longer be resolved." |
| `$defs.aliasLifecycle.replaced_by` | "Canonical ID of the preferred entry to use instead of this deprecated alias." |
| `$defs.entry.id` | "Unique canonical ID in the format 'cn:<namespace>:<kind>:<slug>' (e.g., 'cn:specdev.core:owner:api')." |
| `$defs.entry.kind` | "Category of this canonical entry (e.g., 'owner', 'unit', 'environment', 'trace_type'). Must match the kind of the registry file it belongs to." |
| `$defs.entry.preferred_label` | "The canonical human-readable label for this entry (e.g., 'Milliseconds', 'API Owner'). This is the label that should be used in specs." |
| `$defs.entry.definition` | "Clear, unambiguous definition of this canonical term. Must be sufficient for consistent usage across all spec artifacts." |
| `$defs.entry.version` | "Semantic version of this canonical entry (e.g., '1.0.0'). Incremented when the entry's definition or constraints change." |
| `$defs.entry.status` | "Lifecycle status: 'active' (in use), 'deprecated' (being phased out), 'sunset' (end-of-life announced), 'retired' (no longer valid)." |
| `$defs.entry.owners` | "Array of owner IDs responsible for maintaining this canonical entry. At least one owner is required." |
| `$defs.entry.constraints` | "Optional array of constraint strings that further restrict how this canonical term may be used (e.g., 'Must be > 0', 'Only for HTTP APIs')." |
| `$defs.entry.examples` | "Optional array of example usage strings to help spec authors understand how to apply this term." |
| `$defs.entry.tags` | "Optional array of tags for categorizing and filtering canonical entries." |
| `$defs.entry.aliases` | "Optional array of alternative names that can be used to refer to this entry. Resolved via aliases.json." |
| `$defs.entry.source_refs` | "Optional seed document references that informed the creation of this canonical entry." |
| `$defs.entry.lifecycle` | "Lifecycle metadata tracking when this entry was introduced, deprecated, sunset, or retired." |
| `$defs.alias.kind` | "Canonical kind that this alias belongs to (e.g., 'owner', 'unit'). Must match a registered kind." |
| `$defs.alias.normalized` | "The normalized form of the alias string used for case-insensitive matching." |
| `$defs.alias.target_id` | "Canonical ID that this alias resolves to (e.g., 'cn:specdev.core:unit:ms')." |
| `$defs.alias.status` | "Alias status: 'active' (resolves normally) or 'deprecated' (deprecated aliases require lifecycle metadata)." |
| `$defs.alias.lifecycle` | "Lifecycle metadata for deprecated aliases, including deprecation date and replacement information." |

### Tier 2: HIGH -- canon/ registry schemas

#### canon/kind.schema.json

| Property Path | Proposed Description |
|---|---|
| `$schema` | "JSON Schema meta-schema URI for validation." |
| `registry_version` | "Semantic version of this kind registry file." |
| `kind` | "The canonical kind category this registry defines (e.g., 'owner', 'unit', 'environment'). Must be lowercase with underscores." |
| `entries` | "Array of canonical entries for this kind. Each entry has a unique cn: ID, label, definition, and lifecycle." |

#### canon/aliases.schema.json

| Property Path | Proposed Description |
|---|---|
| `$schema` | "JSON Schema meta-schema URI for validation." |
| `registry_version` | "Semantic version of this aliases registry file." |
| `aliases` | "Array of alias-to-canonical-ID mappings. Used to resolve alternative names to canonical entries." |

### Tier 3: HIGH -- seed_manifest.schema.json

| Property Path | Proposed Description |
|---|---|
| `seed_manifest_id` | "Unique kebab-case ID for this seed manifest instance (e.g., 'seed-manifest-v1')." |
| `version` | "Semantic version of the seed manifest (e.g., '1.0.0'). Incremented when seeds are added or modified." |
| `created_at` | "ISO 8601 timestamp of when this seed manifest was first created." |
| `last_updated` | "ISO 8601 timestamp of the most recent update to this seed manifest." |
| `global_seed_order` | "Ordered array of seed_ids defining the global ingestion order. Seeds earlier in the array are ingested first." |
| `nested_order` | "Hierarchical grouping of seeds into dependency layers. Seeds within a layer can be ingested in parallel." |
| `nested_order[].level_id` | "Kebab-case ID for this dependency layer (e.g., 'layer-0-foundation', 'layer-1-domain')." |
| `nested_order[].description` | "Human-readable description of what this dependency layer contains and its purpose." |
| `nested_order[].seed_ids` | "Array of seed_ids in this layer. All must exist in the seeds array." |
| `seeds` | "Array of seed document definitions. Each seed represents a source document ingested by the spec pipeline." |
| `seeds[].seed_id` | "Unique kebab-case ID for this seed document (e.g., 'seed-overview', 'seed-tech-stack')." |
| `seeds[].path` | "File path to the seed document relative to the repository root." |
| `seeds[].description` | "Brief description of the seed document's content and purpose." |
| `seeds[].required` | "Whether this seed is required for spec generation (true) or optional supplementary context (false)." |
| `seeds[].source_type` | "Type of seed document: 'doc' (human-written documentation), 'spec' (existing specification), 'config' (configuration file), 'other' (miscellaneous)." |
| `step_requirements` | "Map from pipeline step number (e.g., '00', '04', '13a') to array of seed_ids required for that step." |
| `docs_policy` | "Documentation policy configuration consumed by docs-lint and Step 16 validators." |
| `docs_policy.readme_required` | "Whether README files are required in project directories." |
| `docs_policy.root_readme_required` | "Whether a root-level README.md is required at the repository root." |
| `docs_policy.readme_depth_default` | "Default directory depth at which README files are required (0 = root only, 1 = one level deep, etc.)." |
| `docs_policy.readme_depth_by_scope` | "Per-scope overrides for readme_depth_default. Keys are directory path prefixes ending with '/'; values are depth integers." |
| `docs_policy.scope` | "Array of directory path prefixes to include in documentation coverage checks." |
| `docs_policy.exclusions` | "Array of directory path prefixes to exclude from documentation coverage checks." |
| `docs_policy.doc_paths` | "Array of valid documentation file paths. Used by Step 16 validator to verify docs_impact paths." |

### Tier 4: MEDIUM -- Common required fields in step schemas

These 10 fields appear in every step schema. Descriptions should be added at each usage site, tailored to the step context. For brevity, generic versions are shown:

| Property Path | Proposed Description |
|---|---|
| `id` | "Unique kebab-case identifier for this artifact instance (e.g., 'charter-v1', 'fr-list-v1')." |
| `owner` | "Owner of this spec artifact. Must be a valid owner from the canonical registry (canon/kinds/owner.json)." |
| `created_at` | "ISO 8601 timestamp of when this artifact was generated or last regenerated." |
| `seed_refs` | "Array of seed document references that were ingested to produce this artifact. Validated by seed-lint for hash integrity." |
| `spec_refs_ingested` | "Array of upstream spec artifacts that were ingested to produce this artifact. Tracks cross-step dependencies." |
| `generation_quality` | "AI generation quality metadata. Contains assumptions made during automated spec generation." |
| `canonical_refs_used` | "Array of canonical registry references used in this artifact. Validated by canonical-integrity checks." |
| `canonical_proposals` | "Array of proposed new canonical terms discovered during generation. Empty array if none proposed. Default: []." |
| `canonical_conflicts` | "Array of canonical resolution conflicts encountered during generation. Empty array if none. Default: []." |
| `coverage_gaps` | "Array of upstream spec items that lack coverage in this artifact, with reasons for each gap." |

### Tier 5: MEDIUM -- Step-specific properties

#### 00_charter.schema.json

| Property Path | Proposed Description |
|---|---|
| `title` | "Human-readable title for the project charter (e.g., 'User Authentication Service Charter')." |
| `problem_statement` | "Clear statement (min 20 chars) of the problem this project solves. Must articulate the pain point for stakeholders." |
| `in_scope` | "List of capabilities, features, or concerns that ARE within the scope of this project. Minimum 3 items." |
| `out_of_scope` | "List of capabilities, features, or concerns explicitly EXCLUDED from this project. Minimum 3 items." |
| `assumptions` | "List of assumptions the project is built on (e.g., 'Users have email accounts'). Minimum 1 item." |
| `risks` | "List of identified risks that could impact project success. Minimum 1 item." |
| `stakeholders` | "Array of stakeholder roles and their needs. Each stakeholder has a role name and list of needs." |
| `stakeholders[].role` | "Name of the stakeholder role (e.g., 'Product Manager', 'End User', 'Engineering Lead')." |
| `stakeholders[].needs` | "Array of needs this stakeholder has from the project (e.g., 'Real-time analytics dashboard')." |
| `stakeholders[].role_ref` | "Canonical reference linking this stakeholder role to the canonical registry." |
| `user_segments` | "Array of user segments the project targets. Each segment describes a distinct user group with jobs, pains, and gains." |
| `user_segments[].segment_id` | "Unique kebab-case ID for this user segment (e.g., 'segment-power-user', 'segment-admin')." |
| `user_segments[].description` | "Description of this user segment's characteristics and context." |
| `user_segments[].jobs_to_be_done` | "Array of jobs this user segment is trying to accomplish with the product." |
| `user_segments[].pains` | "Array of pain points this user segment experiences without the product or with current solutions." |
| `user_segments[].gains` | "Array of desired outcomes this user segment hopes to achieve with the product." |
| `success_metrics` | "Array of measurable success criteria for the project. Minimum 2 metrics required." |
| `success_metrics[].metric_id` | "Unique kebab-case ID for this metric (e.g., 'metric-login-latency', 'metric-user-retention')." |
| `success_metrics[].name` | "Human-readable name of the metric (e.g., 'Login Latency P95')." |
| `success_metrics[].baseline` | "Current/starting value of the metric (number or string). Used to measure improvement." |
| `success_metrics[].target` | "Target value the metric should reach for the project to be considered successful." |
| `success_metrics[].unit` | "Unit of measurement (e.g., 'ms', '%', 'requests/s'). Should use canonical units when available." |
| `success_metrics[].measurement_method` | "How this metric will be measured (e.g., 'P95 from APM dashboard', 'Monthly active users from analytics')." |
| `success_metrics[].unit_ref` | "Canonical reference for the unit of measurement, linking to canon/kinds/unit.json." |
| `links` | "Array of related links (documentation, designs, external resources) relevant to this charter." |

#### 01_capabilities.schema.json

| Property Path | Proposed Description |
|---|---|
| `capabilities` | "Array of system capabilities. Each capability describes a discrete thing the system can do, with scope and traceability." |
| `capabilities[].capability_id` | "Unique kebab-case ID for this capability (e.g., 'cap-user-login', 'cap-export-reports')." |
| `capabilities[].verb` | "Action verb describing the capability (e.g., 'authenticate', 'export', 'notify'). Min 2 characters." |
| `capabilities[].description` | "Human-readable description of what this capability does and why it matters." |
| `capabilities[].scope` | "Scope classification: 'in' (in scope for current phase), 'out' (explicitly excluded), 'future' (planned for later)." |
| `capabilities[].owner` | "Owner responsible for implementing this capability. Must be a valid canonical owner." |
| `capabilities[].inputs` | "Array of inputs this capability requires (e.g., 'username', 'password', 'session token')." |
| `capabilities[].outputs` | "Array of outputs this capability produces (e.g., 'JWT token', 'user profile', 'error response')." |
| `capabilities[].preconditions` | "Conditions that must be true before this capability can execute (e.g., 'User account exists')." |
| `capabilities[].postconditions` | "Conditions guaranteed to be true after successful execution (e.g., 'Session is created')." |
| `capabilities[].error_states` | "Array of error states this capability can produce, each with a code, message, and severity." |
| `capabilities[].trace` | "Traceability references linking this capability to upstream artifacts (e.g., charter stakeholder needs)." |
| `capabilities[].capability_ref` | "Canonical reference for this capability in the canonical registry." |
| `capabilities[].action_ref` | "Canonical reference for the action verb used in this capability." |
| `capabilities[].entity_ref` | "Canonical reference for the primary entity this capability operates on." |
| `capabilities[].role_ref` | "Canonical reference for the user role that uses this capability." |

#### 02_system_sketch.schema.json

| Property Path | Proposed Description |
|---|---|
| `components` | "Array of system components. Each component is a distinct deployable or logical unit with type, responsibilities, and ownership." |
| `components[].component_id` | "Unique kebab-case ID for this component (e.g., 'comp-auth-service', 'comp-postgres-db')." |
| `components[].type` | "Component type: 'service', 'db', 'queue', 'cache', 'job', 'ui', 'lib', 'external'." |
| `components[].responsibilities` | "Array of 3-6 responsibilities this component handles (e.g., 'Validate user credentials', 'Issue JWT tokens')." |
| `components[].owner` | "Owner of this component. Must be a valid canonical owner." |
| `components[].tags` | "Array of classification tags (e.g., 'critical-path', 'stateful', 'pii'). See enum for full list." |
| `components[].trace` | "Traceability references linking this component to capabilities or other upstream artifacts. Min 1 ref." |
| `components[].entity_ref` | "Canonical reference for the primary domain entity this component manages." |
| `connections` | "Array of connections between components. Required when 2+ components exist. Defines protocols, trust boundaries, and reliability." |
| `connections[].from` | "Source component_id of this connection." |
| `connections[].to` | "Target component_id of this connection." |
| `connections[].protocol` | "Communication protocol: 'http', 'grpc', 'event', 'rpc', 'db', 'file'." |
| `connections[].trust_boundary` | "Trust boundary classification: 'internal' (same network), 'partner' (trusted external), 'public' (untrusted). Partner/public require auth and rate_limit." |
| `connections[].schema_ref` | "Reference to the data schema for this connection (file://, https://, glossary:, api: prefix, or '-tbd' if unknown)." |
| `connections[].auth` | "Authentication method: 'none', 'basic', 'oauth2', 'jwt', 'mTLS', 'key'. Required for partner/public trust boundaries." |
| `connections[].rate_limit` | "Rate limiting configuration. Required for partner/public trust boundaries." |
| `connections[].rate_limit.rps` | "Requests per second limit (1-100,000)." |
| `connections[].rate_limit.burst` | "Maximum burst size above the sustained rate (1-200,000)." |
| `connections[].rate_limit.window_s` | "Rate limit window duration in seconds (1-3600)." |
| `connections[].rate_limit.scope` | "Rate limit scope: 'ip' (per IP), 'client' (per client ID), 'token' (per auth token), 'global' (shared across all clients)." |
| `connections[].reliability` | "Message delivery guarantee: 'best-effort', 'at-least-once', 'exactly-once'. Required for 'event' protocol." |
| `connections[].trace` | "Traceability references for this connection. Min 1 ref." |
| `connections[].interface_ref` | "Canonical reference for the interface type used in this connection." |
| `connections[].event_ref` | "Canonical reference for the event type flowing through this connection." |

#### 02a_delivery_baseline.schema.json

| Property Path | Proposed Description |
|---|---|
| `trace` | "Traceability references linking this delivery baseline to upstream artifacts." |
| `environments` | "Environment configurations keyed by environment name (dev, ci, staging, prod). All four are required." |
| `ci_gates` | "Array of CI gate identifiers (kebab-case) that must pass before deployment. Min 1 gate." |
| `secrets` | "Array of secret/credential names required for deployment (e.g., 'DB_PASSWORD', 'API_KEY')." |
| `compliance` | "Array of compliance requirements that apply to the deployment (e.g., 'SOC2', 'GDPR', 'HIPAA')." |
| `environment_ref` | "Canonical reference for the deployment environment configuration." |
| `command_ref` | "Canonical reference for the CI/CD commands used in this delivery baseline." |
| `policy_ref` | "Canonical reference for the deployment policy governing this baseline." |

#### 03_glossary.schema.json

| Property Path | Proposed Description |
|---|---|
| `terms` | "Array of glossary terms. Each term defines domain vocabulary with a unique ID, definition, and optional acronym." |
| `terms[].term_id` | "Unique kebab-case ID for this term (e.g., 'term-jwt', 'term-session')." |
| `terms[].term` | "The glossary term itself (e.g., 'JSON Web Token', 'Session'). Min 2 characters." |
| `terms[].acronym` | "Optional acronym for the term (e.g., 'JWT', 'API'). Must be 2+ uppercase alphanumeric characters." |
| `terms[].definition` | "Clear definition of the term (min 20 chars). Must be understandable by someone unfamiliar with the domain." |
| `terms[].domain` | "Knowledge domain this term belongs to (kebab-case, e.g., 'authentication', 'data-modeling')." |
| `terms[].units` | "Optional unit of measurement associated with this term (e.g., 'ms', 'req/s'). Alphanumeric with slashes." |
| `terms[].term_ref` | "Canonical reference for this glossary term." |
| `terms[].acronym_ref` | "Canonical reference for the acronym, if different from the term reference." |
| `terms[].unit_ref` | "Canonical reference for the unit of measurement associated with this term." |

#### 04_fr_list.schema.json

| Property Path | Proposed Description |
|---|---|
| `functional_requirements` | "Array of functional requirements. Each FR describes a specific system behavior with acceptance criteria and traceability." |
| `functional_requirements[].fr_id` | "Unique kebab-case ID for this FR (e.g., 'fr-user-login', 'fr-export-csv'). Convention: 'fr-' prefix." |
| `functional_requirements[].statement` | "Clear statement (min 20 chars) of what the system must do. Should be testable and unambiguous." |
| `functional_requirements[].rationale` | "Justification for why this FR is needed, linking to business goals or user needs." |
| `functional_requirements[].preconditions` | "Conditions that must be true before this FR can be exercised." |
| `functional_requirements[].postconditions` | "Conditions guaranteed to be true after this FR is successfully executed." |
| `functional_requirements[].acceptance_criteria` | "Array of testable acceptance criteria (min 2). Each defines a specific condition for the FR to be considered complete." |
| `functional_requirements[].acceptance_criteria[].criterion_id` | "Unique kebab-case ID for this criterion (e.g., 'ac-login-success', 'ac-login-invalid-password')." |
| `functional_requirements[].acceptance_criteria[].text` | "Testable criterion statement (min 15 chars). Should follow Given/When/Then or similar pattern." |
| `functional_requirements[].acceptance_criteria[].fixture_ref` | "Optional ID of a test fixture in Step 08 that validates this criterion." |
| `functional_requirements[].trace` | "Traceability references linking this FR to capabilities, charter items, or other upstream artifacts." |
| `functional_requirements[].capability_ref` | "Canonical reference for the capability this FR implements." |
| `functional_requirements[].action_ref` | "Canonical reference for the action verb in this FR." |
| `functional_requirements[].entity_ref` | "Canonical reference for the primary entity this FR operates on." |
| `functional_requirements[].status_ref` | "Canonical reference for the implementation status of this FR." |

#### 05_interface_contracts.schema.json

| Property Path | Proposed Description |
|---|---|
| `apis` | "Array of API/interface contracts. Each defines an endpoint with protocol, method, parameters, and security." |
| `apis[].api_id` | "Unique kebab-case ID for this API (e.g., 'api-login', 'api-create-session')." |
| `apis[].name` | "Human-readable name of this API (e.g., 'User Login', 'Create Session')." |
| `apis[].version` | "API version string (e.g., 'v1', 'v2.1'). Must start with 'v' followed by numeric version." |
| `apis[].protocol` | "Communication protocol: 'http', 'grpc', 'ws' (WebSocket), 'mqtt'." |
| `apis[].route` | "URL route/path for this API (e.g., '/api/v1/login', '/users/{id}'). Include path parameters in curly braces." |
| `apis[].method` | "HTTP method: 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'. Only applicable for HTTP protocol." |
| `apis[].request_schema_ref` | "Reference to the request body JSON schema (e.g., a file path or schema ID)." |
| `apis[].response_schema_ref` | "Reference to the response body JSON schema." |
| `apis[].errors` | "Array of error states this API can return, each with code, message, and severity." |
| `apis[].parameters` | "Array of request parameters (query, path, header) with name, location, and required flag." |
| `apis[].parameters[].name` | "Parameter name (e.g., 'user_id', 'page', 'Authorization')." |
| `apis[].parameters[].in` | "Parameter location: 'query' (URL query string), 'path' (URL path segment), 'header' (HTTP header)." |
| `apis[].parameters[].required` | "Whether this parameter is required (true) or optional (false)." |
| `apis[].parameters[].schema` | "Kebab-case reference to the parameter's data type schema." |
| `apis[].example_refs` | "Array of example reference strings for this API (e.g., fixture IDs, documentation links)." |
| `apis[].security` | "Security mechanism: 'none', 'api-key', 'oauth2', 'jwt', 'mTLS'." |
| `apis[].owner` | "Owner of this API contract. Must be a valid canonical owner." |
| `apis[].trace` | "Traceability references linking this API to FRs, capabilities, or other upstream artifacts." |
| `apis[].interface_ref` | "Canonical reference for this interface contract in the canonical registry." |
| `apis[].event_ref` | "Canonical reference for event types this API emits or consumes." |
| `apis[].entity_ref` | "Canonical reference for the primary entity this API operates on." |
| `apis[].policy_ref` | "Canonical reference for the security/access policy governing this API." |
| `apis[].enum_provenance.source_url` | "URL of the external source for enum values used in this API (e.g., ISO standard page)." |
| `apis[].enum_provenance.source_date` | "ISO date when the external enum source was consulted." |
| `apis[].enum_provenance.resolved_version` | "Version of the external source that was used to resolve enum values." |
| `apis[].enum_provenance.resolved_at` | "ISO 8601 timestamp when the enum values were resolved from the external source." |

#### 06_invariants.schema.json

| Property Path | Proposed Description |
|---|---|
| `rules` | "Array of system invariants. Each rule defines a condition that must always hold true across specified components/APIs." |
| `rules[].inv_id` | "Unique kebab-case ID for this invariant (e.g., 'inv-balance-non-negative', 'inv-session-expiry')." |
| `rules[].description` | "Human-readable description of what this invariant enforces and why it matters." |
| `rules[].language` | "Expression language: 'jsonlogic' (machine-evaluatable), 'cel' (Common Expression Language), 'text' (human-readable only)." |
| `rules[].expression` | "The invariant expression in the specified language. For 'text', a clear natural language statement." |
| `rules[].scope` | "Components and APIs this invariant applies to. At least one of components or apis should be specified." |
| `rules[].scope.components` | "Array of component_ids from Step 02 that this invariant constrains." |
| `rules[].scope.apis` | "Array of api_ids from Step 05 that this invariant constrains." |
| `rules[].severity` | "Invariant violation severity: 'warn' (log and continue) or 'error' (fail the operation)." |
| `rules[].trace` | "Traceability references linking this invariant to FRs, NFRs, or other upstream artifacts." |
| `rules[].policy_ref` | "Canonical reference for the policy that mandates this invariant." |
| `rules[].risk_category_ref` | "Canonical reference for the risk category this invariant mitigates." |
| `rules[].status_ref` | "Canonical reference for the implementation status of this invariant." |

#### 07_nfrs.schema.json

| Property Path | Proposed Description |
|---|---|
| `nfrs` | "Array of non-functional requirements. Each NFR defines a measurable quality attribute with target, unit, and measurement method." |
| `nfrs[].nfr_id` | "Unique ID for this NFR (pattern: 'nfr-<category>-<slug>', e.g., 'nfr-latency-login-p95')." |
| `nfrs[].category` | "NFR category: latency, throughput, availability, durability, cost, security, privacy, maintainability, usability, portability, energy." |
| `nfrs[].metric` | "Name of the metric being measured (e.g., 'P95 response time', 'Uptime percentage', 'Monthly cost')." |
| `nfrs[].target` | "Target value for the metric (number or string containing a number, e.g., 200, '< 500ms', '99.9%')." |
| `nfrs[].unit` | "Unit of measurement (e.g., 'ms', '%', 'req/s', 'USD/month'). Use canonical units when available." |
| `nfrs[].measurement_method` | "How this NFR will be measured (e.g., 'APM P95 percentile', 'Load test with k6', 'AWS Cost Explorer')." |
| `nfrs[].stage` | "Deployment stage where this NFR is measured: 'dev', 'ci', 'staging', 'prod'." |
| `nfrs[].owner` | "Owner responsible for meeting this NFR. Must be a valid canonical owner." |
| `nfrs[].trace` | "Traceability references linking this NFR to FRs, components, or capabilities." |
| `nfrs[].metric_ref` | "Canonical reference for the metric type being measured." |
| `nfrs[].unit_ref` | "Canonical reference for the unit of measurement." |
| `nfrs[].stage_ref` | "Canonical reference for the deployment stage." |
| `nfrs[].environment_ref` | "Canonical reference for the target environment configuration." |

#### 08_fixtures.schema.json

| Property Path | Proposed Description |
|---|---|
| `fixtures` | "Array of test fixtures. Each fixture defines test input, expected output, and the spec items it validates." |
| `fixtures[].fixture_id` | "Unique kebab-case ID for this fixture (e.g., 'fix-login-success', 'fix-rate-limit-exceeded')." |
| `fixtures[].description` | "Human-readable description of what this fixture tests." |
| `fixtures[].targets` | "Array of traceability references to the spec items this fixture validates (FR, API, NFR, invariant). Min 1." |
| `fixtures[].mode` | "Test mode: 'unit' (isolated), 'contract' (API contract), 'e2e' (end-to-end), 'redteam' (adversarial/security)." |
| `fixtures[].input` | "Test input data (any valid JSON). The data provided to the system under test." |
| `fixtures[].expected` | "Expected output data (any valid JSON). The data the system should produce given the input." |
| `fixtures[].tags` | "Array of tags for categorizing and filtering fixtures (e.g., 'auth', 'happy-path', 'edge-case')." |
| `fixtures[].tag_ref` | "Canonical reference for the primary tag category of this fixture." |

#### 09_impl_plan.schema.json

| Property Path | Proposed Description |
|---|---|
| `tech_stack` | "Technology stack for implementation. Must include languages, frameworks, infrastructure, and tools (all four required in Step 09)." |
| `tech_stack_ref` | "Canonical reference for the overall tech stack selection." |
| `milestones` | "Array of implementation milestones with deliverables, dates, and status tracking." |
| `milestones[].milestone_id` | "Unique kebab-case ID for this milestone (e.g., 'ms-auth-core', 'ms-api-gateway')." |
| `milestones[].name` | "Human-readable name of the milestone (e.g., 'Core Authentication Service')." |
| `milestones[].target_date` | "Target completion date in ISO 8601 date format (e.g., '2025-12-31')." |
| `milestones[].status` | "Milestone status: 'pending' (not started), 'in_progress', 'done' (complete), 'deferred' (postponed). Default: 'pending'." |
| `milestones[].risks` | "Array of risk descriptions specific to this milestone." |
| `milestones[].spikes` | "Array of technical spike descriptions needed to reduce uncertainty for this milestone." |
| `milestones[].deliverables` | "Array of traceability references to the artifacts this milestone produces." |
| `milestones[].status_ref` | "Canonical reference for the milestone status." |
| `migration_plan` | "Free-text description of any data or system migration required during implementation." |
| `dependencies` | "Array of milestone or external dependencies. Strings or structured dependency objects." |
| `dependency_ref` | "Canonical reference for the dependency tracking configuration." |
| `environment_ref` | "Canonical reference for the target deployment environment." |
| `trace` | "Traceability references linking this implementation plan to upstream spec artifacts." |

#### 10_governance.schema.json

| Property Path | Proposed Description |
|---|---|
| `versioning` | "Versioning strategy description (e.g., 'Semantic versioning for all spec artifacts')." |
| `pr_rules` | "Array of CI checks required on pull requests. Values must be valid specdev commands (e.g., 'validate-all', 'matrix')." |
| `spec_first_policy` | "Whether spec changes must precede code changes (true = spec-first workflow enforced)." |
| `commit_message_rules` | "Rules governing commit message format and content." |
| `commit_message_rules.require_spec_ids` | "Whether commit messages must reference spec artifact IDs (e.g., '[fr-user-login]')." |
| `commit_message_rules.pattern` | "Regex pattern that commit messages must match (e.g., '^(feat|fix|docs)\\\\(.*\\\\):.*\\\\[.*\\\\]$')." |
| `commit_message_rules.id_pattern_ref` | "Canonical reference for the ID pattern used in commit messages." |
| `review_policy` | "Policy governing spec reviews, verdict requirements, and evidence sources." |
| `review_policy.verdict_requirements` | "Array of requirements that must be met for a review verdict (e.g., 'All fixtures pass', 'No blocking findings')." |
| `review_policy.required_metadata` | "Array of metadata fields required in review artifacts." |
| `review_policy.evidence_source_by_phase` | "Evidence sources required at each deployment phase (dev, staging, prod)." |
| `review_policy.evidence_source_by_phase.dev` | "Evidence source for development phase reviews (e.g., 'unit tests + local integration')." |
| `review_policy.evidence_source_by_phase.staging` | "Evidence source for staging phase reviews (e.g., 'contract tests + staging deployment')." |
| `review_policy.evidence_source_by_phase.prod` | "Evidence source for production phase reviews (e.g., 'canary deployment + monitoring')." |
| `reviewers` | "Array of reviewer identifiers who must approve spec changes." |
| `trace` | "Traceability references linking this governance policy to upstream artifacts." |
| `links` | "Array of related links (policy documents, CI configuration, etc.)." |
| `policy_ref` | "Canonical reference for the governance policy." |
| `command_ref` | "Canonical reference for the governance commands." |

#### 11_redteam.schema.json

| Property Path | Proposed Description |
|---|---|
| `trace` | "Traceability references linking this red team assessment to upstream artifacts." |
| `threats` | "Array of identified threats. Each threat describes an attack vector, targets, and mitigations." |
| `threats[].threat_id` | "Unique kebab-case ID for this threat (e.g., 'threat-sql-injection', 'threat-session-hijack')." |
| `threats[].description` | "Description of the threat scenario and potential impact." |
| `threats[].vector` | "Attack vector description (e.g., 'Malformed SQL in login form', 'Stolen session cookie')." |
| `threats[].target_ids` | "Array of traceability references to the spec items (APIs, components) targeted by this threat." |
| `threats[].category` | "Threat category: 'authn' (authentication), 'authz' (authorization), 'business_logic', 'transport', 'data_privacy'." |
| `threats[].mitigations` | "Array of mitigation measures. Each references a spec artifact (FR, API, invariant, etc.) that addresses the threat." |
| `threats[].mitigations[].type` | "Type of spec artifact providing the mitigation: 'fr', 'api', 'nfr', 'inv', 'fixture', 'doc', 'capability'." |
| `threats[].mitigations[].id` | "Kebab-case ID of the mitigating spec artifact (e.g., 'fr-input-validation', 'inv-session-expiry')." |
| `threats[].mitigations[].note` | "Optional note explaining how this artifact mitigates the threat." |
| `threats[].severity` | "Threat severity: 'low', 'medium', 'high', 'critical'. Determines review priority." |
| `threats[].risk_category_ref` | "Canonical reference for the risk category of this threat." |
| `threats[].policy_ref` | "Canonical reference for the security policy governing this threat's mitigation." |
| `edge_cases` | "Array of edge cases identified during red team review that may need special handling." |
| `edge_cases[].id` | "Unique kebab-case ID for this edge case." |
| `edge_cases[].description` | "Description of the edge case scenario." |
| `edge_cases[].trigger` | "Optional description of what triggers this edge case." |

#### 12_ci_gates.schema.json

| Property Path | Proposed Description |
|---|---|
| `trace` | "Traceability references linking CI gates to governance rules and upstream artifacts." |
| `jobs` | "Array of CI job definitions. Each job has steps, environment refs, and optional security configuration." |
| `jobs[].job_id` | "Unique kebab-case ID for this CI job (e.g., 'job-lint', 'job-test', 'job-deploy-staging')." |
| `jobs[].name` | "Human-readable name of the CI job (e.g., 'Lint and Format', 'Integration Tests')." |
| `jobs[].requires` | "Array of job_ids that must complete successfully before this job runs (dependency chain)." |
| `jobs[].steps` | "Array of steps within this CI job, executed sequentially." |
| `jobs[].steps[].id` | "Unique kebab-case ID for this CI step (e.g., 'step-checkout', 'step-run-tests')." |
| `jobs[].steps[].name` | "Human-readable name of the CI step (e.g., 'Checkout Code', 'Run Unit Tests')." |
| `jobs[].steps[].command` | "Shell command to execute for this step (e.g., 'pytest tests/ -x', 'npm run lint')." |
| `jobs[].steps[].command_ref` | "Canonical reference for the command used in this step." |
| `jobs[].environment_ref` | "Canonical reference for the CI environment this job runs in." |
| `jobs[].role_ref` | "Canonical reference for the role/permissions this job requires." |
| `jobs[].security.environment_protection` | "Environment protection rules (required reviewers, wait timers) for deployment jobs." |
| `coverage_thresholds` | "Code coverage thresholds for CI gates." |
| `coverage_thresholds.lines` | "Minimum line coverage percentage (0-100) required to pass CI." |
| `coverage_thresholds.branches` | "Minimum branch coverage percentage (0-100) required to pass CI." |

#### 13_extension_generator.schema.json

| Property Path | Proposed Description |
|---|---|
| `extensions` | "Array of extension definitions. Each extension specifies a new spec artifact type for domain-specific concerns." |
| `extensions[].title` | "Human-readable title of the extension (e.g., 'Database Schema Extension', 'AI Model Card')." |
| `extensions[].justification` | "Justification for why this extension is needed beyond the standard 16-step pipeline." |
| `extensions[].required_schema_sections` | "Array of JSON schema sections that the extension schema must include (e.g., 'trace', 'owner')." |
| `extensions[].schema_design_guidelines` | "Guidelines for designing the extension's schema (e.g., 'Use core/atoms for IDs')." |
| `extensions[].tag_ref` | "Canonical reference for the extension's primary tag category." |
| `extensions[].policy_ref` | "Canonical reference for the governance policy governing this extension." |
| `extensions[].id_pattern_ref` | "Canonical reference for the ID naming pattern this extension should use." |
| `extensions[].governance_label_ref` | "Canonical reference for the governance label assigned to this extension." |

#### 13a_completeness_assessment.schema.json

| Property Path | Proposed Description |
|---|---|
| `missing_elements` | "Array of spec completeness gaps. Each element identifies something missing from the spec pipeline." |
| `missing_elements[].element_id` | "Unique kebab-case ID for this missing element (e.g., 'gap-auth-nfr', 'gap-db-invariant')." |
| `missing_elements[].category` | "Gap category: 'traceability' (broken trace chain), 'completeness' (missing artifact), 'quality' (insufficient detail), 'ambiguity' (unclear spec)." |
| `missing_elements[].description` | "Description of what is missing and its impact on spec quality." |
| `missing_elements[].priority` | "Fix priority: 'high' (blocks implementation), 'medium' (causes ambiguity), 'low' (nice to have)." |
| `missing_elements[].impact_on_completeness` | "Numeric impact score (0.0-1.0) estimating how much fixing this gap improves overall completeness." |
| `missing_elements[].specification_source` | "Array of spec file names where the gap was detected (pattern: 'NN_name.json' or 'ext_NN_name.json')." |
| `missing_elements[].risk_category_ref` | "Canonical reference for the risk category associated with this gap." |
| `missing_elements[].completeness_dimension_ref` | "Canonical reference for the completeness dimension this gap affects." |
| `missing_elements[].tag_ref` | "Canonical reference for categorizing this gap." |
| `completeness_rating` | "Overall completeness assessment with current score, target, and confidence level." |
| `completeness_rating.current` | "Current completeness score (0-10). Reflects the spec pipeline's completeness at time of assessment." |
| `completeness_rating.target` | "Target completeness score (0-10) that must be achieved before implementation proceeds." |
| `completeness_rating.confidence_level` | "Confidence in the completeness rating (0.0-1.0). Lower values indicate more uncertainty in the assessment." |

#### 14_roadmap.schema.json

| Property Path | Proposed Description |
|---|---|
| `tech_stack` | "Technology stack (languages and frameworks required). Inherits from Step 09 tech_stack." |
| `tech_stack_ref` | "Canonical reference for the tech stack selection." |
| `milestones` | "Array of implementation milestones with user stories, tasks, dates, and risk tracking." |
| `milestones[].milestone_id` | "Unique kebab-case ID for this roadmap milestone (e.g., 'ms-sprint-1-auth')." |
| `milestones[].name` | "Human-readable milestone name." |
| `milestones[].target_date` | "Target completion date in ISO 8601 date format." |
| `milestones[].status` | "Milestone status: 'pending', 'in_progress', 'done', 'deferred'. Default: 'pending'." |
| `milestones[].risk_status` | "Risk level: 'low', 'medium', 'high', 'critical'. Default: 'low'." |
| `milestones[].tasks[].task_id` | "Unique kebab-case ID for this task within the milestone." |
| `milestones[].tasks[].description` | "Task description (must contain at least two words). Describes the atomic work unit." |
| `milestones[].tasks[].acceptance_criteria` | "Array of acceptance criteria for this task (min 1). Each has a criterion_id and testable text." |
| `milestones[].tasks[].acceptance_criteria[].criterion_id` | "Unique kebab-case ID for this acceptance criterion." |
| `milestones[].tasks[].acceptance_criteria[].text` | "Testable criterion statement (min 15 chars)." |
| `milestones[].tasks[].acceptance_criteria[].fixture_ref` | "Optional kebab-case ID of a fixture that validates this criterion." |
| `milestones[].tasks[].status` | "Task status: 'pending', 'in_progress', 'done'." |
| `milestones[].tasks[].status_ref` | "Canonical reference for this task's status." |
| `milestones[].tasks[].environment_ref` | "Canonical reference for the environment this task targets." |
| `milestones[].tasks[].metric_ref` | "Canonical reference for any metric this task must satisfy." |
| `milestones[].deliverables` | "Array of traceability references to artifacts this milestone produces." |
| `milestones[].risks` | "Array of risk descriptions for this milestone." |
| `milestones[].spikes` | "Array of technical spike descriptions for this milestone." |
| `milestones[].status_ref` | "Canonical reference for the milestone's status." |
| `migration_plan` | "Description of any migration activities (min 1 char). Inherits from Step 09 if applicable." |
| `dependencies` | "Array of structured dependency objects (objects only, not strings -- unlike Step 09)." |
| `dependency_ref` | "Canonical reference for the dependency tracking." |
| `trace` | "Traceability references linking this roadmap to upstream artifacts." |

#### 15_scaffold.schema.json

| Property Path | Proposed Description |
|---|---|
| `service_skeleton` | "Project skeleton configuration: language, framework, and module structure." |
| `service_skeleton.modules` | "Array of module/package names to scaffold (e.g., 'auth', 'api', 'models')." |
| `route_map` | "Array of route definitions mapping API contracts to URL paths and HTTP methods." |
| `route_map[].api_ref` | "Kebab-case ID of the API contract from Step 05 that this route implements." |
| `route_map[].path` | "URL path for this route (e.g., '/api/v1/users', '/health')." |
| `route_map[].method` | "HTTP method: 'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'." |
| `route_map[].interface_ref` | "Canonical reference for the interface this route implements." |
| `validators` | "Array of validation command names to run during scaffold build (e.g., 'pytest', 'mypy', 'eslint')." |
| `command_ref` | "Canonical reference for the build/scaffold commands." |
| `build_status` | "Current build status: 'pending' (not built), 'green' (build passes), 'red' (build fails). Green requires validators." |
| `trace` | "Traceability references linking this scaffold to upstream artifacts." |
| `links` | "Array of related links (build logs, CI dashboards, repository URLs)." |

#### 16_impl_context.schema.json (Step-specific properties only -- $defs and top-level)

Due to the size of Step 16 (228 missing descriptions), only the most critical and ambiguous properties are shown here. The complete table follows the same format.

| Property Path | Proposed Description |
|---|---|
| `$defs.specRef.type` | "Type of spec artifact referenced: 'fr', 'api', 'nfr', 'inv', 'fixture', 'doc', 'code'." |
| `$defs.specRef.id` | "Kebab-case ID of the referenced spec artifact." |
| `$defs.specRef.note` | "Optional note explaining the reference context." |
| `$defs.specRef.line_range` | "Source code line range (e.g., 'L10-L25'). Binds the reference to specific code." |
| `$defs.specRef.commit_hash` | "40-character git commit SHA binding this reference to a specific code version. Cannot be all zeros." |
| `$defs.evidenceObject.type` | "Evidence type: 'log' (command output), 'snippet' (code excerpt), 'screenshot' (visual), 'reference' (external link)." |
| `$defs.evidenceObject.content` | "Evidence content (min 20 chars, must contain non-whitespace). The actual evidence text or description." |
| `$defs.evidenceObject.evidence_ref` | "Optional reference identifier for external evidence storage." |
| `$defs.evidenceObject.path` | "Optional file path associated with this evidence." |
| `$defs.evidenceObject.section` | "Optional section within the file that this evidence relates to." |
| `extensions.review_state` | "Optional review state extension for tracking review workflow." |
| `extensions.review_state.outcome` | "Review outcome string (e.g., 'approved', 'changes_requested')." |
| `extensions.review_state.verified_by` | "Identifier of the person or system that verified the review." |
| `extensions.execution_context` | "Optional execution context extension for runtime configuration." |
| `extensions.execution_context.command_overrides` | "Map of command name to override command string, for customizing test/build commands." |
| `plan.status` | "Plan status: 'active' (ready for implementation) or 'deferred' (postponed, requires deferred_reason)." |
| `plan.deferred_reason` | "Explanation of why this plan was deferred. Required when status is 'deferred'." |
| `plan.summary` | "High-level summary of the implementation scope." |
| `plan.summary.functional_summary` | "Brief description of what will be implemented in this iteration." |
| `plan.summary.scope_in` | "Array of items explicitly in scope for this implementation." |
| `plan.summary.scope_out` | "Array of items explicitly out of scope for this implementation." |
| `plan.docs_impact.status` | "Documentation impact status: 'required' (docs must be updated) or 'not_required' (no doc changes needed)." |
| `plan.docs_impact.rationale` | "Explanation (min 10 chars) of why documentation is or is not required." |
| `plan.docs_impact.docs_touched` | "Array of doc file paths to update. Required when status is 'required', must have min 1 item." |
| `plan.docs_impact.status_ref` | "Canonical reference for the documentation status." |
| `plan.spec_alignment` | "Spec alignment section containing the implementation checklist and requirements summary." |
| `plan.spec_alignment.checklist` | "Array of checklist items. Each maps a spec requirement to implementation actions with evidence." |
| `plan.spec_alignment.checklist[].id` | "SCREAMING_SNAKE_CASE checklist item ID (e.g., 'FR_USER_LOGIN_01')." |
| `plan.spec_alignment.checklist[].spec_ref` | "Reference to the spec artifact this checklist item implements (with code location binding)." |
| `plan.spec_alignment.checklist[].description` | "Description of the requirement this checklist item addresses." |
| `plan.spec_alignment.checklist[].type` | "Checklist item type: behavior, constraint, validation, metadata, perf, logging, docs, security." |
| `plan.spec_alignment.checklist[].layer` | "Implementation layer: db, model, service, api, integration, tests, docs, config, security." |
| `plan.spec_alignment.checklist[].checklist_status` | "Item status: 'active' (to be implemented) or 'deferred' (postponed). Default: 'active'." |
| `plan.spec_alignment.checklist[].linked_test_expectation` | "Test expectation(s) that validate this item. String or array of strings. Required for all items." |
| `plan.spec_alignment.checklist[].nfr_refs` | "Array of NFR IDs this checklist item satisfies. Required for non-deferred items." |
| `plan.spec_alignment.checklist[].fixture_ref` | "Fixture ID from Step 08 that validates this checklist item. Required for non-deferred items." |
| `plan.spec_alignment.checklist[].milestone_ref` | "Milestone ID from Step 14 that this checklist item belongs to." |
| `plan.spec_alignment.checklist[].implementation.status` | "Implementation status: 'pending', 'in_progress', 'verified' (requires evidence), 'deferred'." |
| `plan.spec_alignment.checklist[].implementation.files_touched` | "Array of file paths modified during implementation of this checklist item." |
| `plan.spec_alignment.checklist[].implementation.actions` | "Array of atomic actions taken (min 1). Each action has a type, description, and optional evidence." |
| `plan.spec_alignment.checklist[].implementation.actions[].type` | "Action type: 'file_create', 'file_edit' (require target), 'run_command' (requires command), 'manual_verification'." |
| `plan.spec_alignment.checklist[].implementation.actions[].description` | "Description of what this action does." |
| `plan.spec_alignment.checklist[].implementation.actions[].target` | "File path target. Required for file_create and file_edit actions." |
| `plan.spec_alignment.checklist[].implementation.actions[].command` | "Shell command to execute. Required for run_command actions." |
| `plan.spec_alignment.checklist[].implementation.actions[].evidence` | "Evidence object proving this action was completed. Required when implementation status is 'verified'." |
| `plan.spec_alignment.checklist[].implementation.actions[].command_ref` | "Canonical reference for the command used in this action." |
| `plan.spec_alignment.checklist[].implementation.status_ref` | "Canonical reference for the implementation status." |
| `plan.ambiguities` | "Array of ambiguities discovered during planning or implementation." |
| `plan.ambiguities[].id` | "Unique kebab-case ID for this ambiguity." |
| `plan.ambiguities[].description` | "Description of the ambiguous spec, code, or requirement." |
| `plan.ambiguities[].source` | "Where the ambiguity was found: 'spec', 'code', 'plan', 'mixed', 'review'." |
| `plan.ambiguities[].severity` | "Ambiguity severity: 'blocking' (cannot proceed) or 'non_blocking' (can proceed with mitigation)." |
| `plan.ambiguities[].impact` | "Array of impact descriptions explaining what this ambiguity affects." |
| `plan.ambiguities[].proposed_assumption` | "Proposed assumption to resolve the ambiguity pending stakeholder confirmation." |
| `plan.ambiguities[].mitigation` | "Mitigation strategy (min 10 chars). Required for non_blocking ambiguities." |
| `plan.ambiguities[].status` | "Resolution status: 'resolved', 'tracking', 'deferred', 'blocked'." |
| `plan.ambiguities[].decision` | "Final decision made to resolve the ambiguity." |
| `plan.ambiguities[].resolved` | "Whether the ambiguity is resolved (string explanation or boolean)." |
| `plan.ambiguities[].status_ref` | "Canonical reference for the ambiguity status." |
| `plan.solution` | "High-level solution design for this implementation iteration." |
| `plan.solution.architecture_sketch` | "Text description of the architectural approach (required)." |
| `plan.solution.sequence_of_concerns` | "Ordered list of concerns to address during implementation." |
| `plan.solution.risks` | "Array of identified risks in the proposed solution." |
| `plan.context` | "Implementation context: existing code structures and coding examples." |
| `plan.context.coding_examples` | "Array of coding examples demonstrating patterns to follow." |
| `plan.context.coding_examples[].title` | "Title of the coding example." |
| `plan.context.coding_examples[].description` | "Description of what the example demonstrates." |
| `plan.context.coding_examples[].code` | "The example code string." |
| `plan.context.existing_structures[].signature` | "Code signature (function/class/method) of the existing structure." |
| `plan.context.existing_structures[].source_file` | "Source file path (must end in .py/.ts/.js/.go/.rs, no leading slash)." |
| `plan.context.existing_structures[].line_range` | "Line range in source file (e.g., 'L10-L25')." |
| `plan.review_requirements` | "Requirements for the review phase (test commands, NFR measurements, timeouts)." |
| `plan.review_requirements.guidelines` | "Free-text review guidelines for the reviewer." |
| `plan.review_requirements.test_commands` | "Array of test commands to execute. String or structured command object. Min 1 when plan is active." |
| `plan.review_requirements.nfr_measurement_methods` | "Map of NFR ID to measurement method (command, expected result, description)." |
| `plan.review_requirements.timeout_constants` | "Map of SCREAMING_SNAKE timeout constant names to integer values (seconds)." |
| `plan.docs` | "Documentation update plan: 'not_applicable' (with reason) or 'planned' (with required_updates)." |
| `plan.security` | "Security plan: 'not_applicable' (with reason) or 'planned' (with fixtures and spec mutations)." |
| `plan.delivery` | "Delivery/observability plan: 'not_applicable' (with reason) or 'planned' (with dashboards and alerts)." |
| `plan.drift` | "Drift detection plan: 'not_applicable' (with reason) or 'planned' (with checks)." |
| `plan.coverage_status` | "Checklist coverage summary: total, verified, deferred, and pending counts." |
| `plan.coverage_status.total` | "Total number of checklist items." |
| `plan.coverage_status.verified` | "Number of checklist items with verified implementation." |
| `plan.coverage_status.deferred` | "Number of deferred checklist items." |
| `plan.coverage_status.pending` | "Number of checklist items not yet started." |
| `plan.scope_validation` | "Scope validation tracking in_scope, out_of_scope, and acknowledgment." |
| `plan.scope_validation.in_scope` | "Array of items confirmed as in scope for this iteration." |
| `plan.scope_validation.out_of_scope` | "Array of items confirmed as out of scope. If non-empty, acknowledged must be true." |
| `plan.scope_validation.acknowledged` | "Whether scope exclusions have been acknowledged. Must be true if out_of_scope is non-empty." |
| `plan.status_ref` | "Canonical reference for the overall plan status." |
| `execution` | "Execution phase results: files modified, test results, evidence bindings." |
| `execution.files_touched` | "Array of file paths modified during execution." |
| `execution.execution_results` | "Array of test/command execution results with status, evidence, and bindings." |
| `execution.execution_results[].status` | "Execution status: 'passed', 'failed', 'blocked', 'partial'." |
| `execution.execution_results[].outcome_description` | "Description of the execution outcome." |
| `execution.execution_results[].reasoning` | "Explanation of why the execution produced this result." |
| `execution.execution_results[].command` | "The command that was executed." |
| `execution.execution_results[].evidence` | "Evidence text (min 20 chars). For 'passed' status, must contain success indicators." |
| `execution.execution_results[].evidence_ref` | "Reference to external evidence storage. Required when status is 'passed'." |
| `execution.execution_results[].evidence_binding` | "Cryptographic binding of evidence to specific execution. Required when status is 'passed'." |
| `execution.execution_results[].evidence_binding.timestamp` | "ISO 8601 timestamp of when the evidence was captured." |
| `execution.execution_results[].evidence_binding.sha256` | "SHA-256 hash of the evidence content for integrity verification." |
| `execution.execution_results[].evidence_binding.exit_code` | "Process exit code (0-255). 0 typically indicates success." |
| `execution.execution_results[].evidence_binding.command` | "The exact command that produced this evidence." |
| `execution.execution_results[].evidence_binding.command_ref` | "Canonical reference for the evidence-producing command." |
| `execution.execution_results[].status_ref` | "Canonical reference for the execution status." |
| `execution.execution_results[].command_ref` | "Canonical reference for the executed command." |
| `execution.critical_evidence` | "Summary of critical evidence linking checklist items to test results." |
| `execution.critical_evidence.satisfied_checklist_ids` | "Array of SCREAMING_SNAKE checklist IDs that have been satisfied by evidence." |
| `execution.critical_evidence.passed_test_commands` | "Array of test commands that passed successfully." |
| `execution.config_validation` | "Validation status of configuration artifacts (dashboards, alerts, drift schedules)." |
| `execution.config_validation.dashboard_links_valid` | "Whether all configured dashboard URLs are reachable." |
| `execution.config_validation.alert_rules_valid` | "Whether all configured alert rules are syntactically valid." |
| `execution.config_validation.drift_schedules_valid` | "Whether all configured drift check schedules are valid cron expressions." |
| `execution.config_validation.notes` | "Optional notes about configuration validation results." |
| `execution.emergent_ambiguities` | "Array of new ambiguities discovered during execution (not in the original plan)." |
| `execution.emergent_ambiguities[].id` | "Unique kebab-case ID for this emergent ambiguity." |
| `execution.emergent_ambiguities[].description` | "Description of the newly discovered ambiguity." |
| `execution.emergent_ambiguities[].severity` | "Free-text severity assessment of this emergent ambiguity." |
| `execution.emergent_ambiguities[].impact` | "Array of impact descriptions." |
| `execution.emergent_ambiguities[].status` | "Free-text status of this emergent ambiguity." |
| `execution.emergent_ambiguities[].status_ref` | "Canonical reference for the emergent ambiguity status." |
| `execution.final_status` | "Final execution status summary." |
| `execution.final_status.test_results` | "Array of test result objects (unstructured)." |
| `execution.final_status.ci_status` | "Final CI status: 'green' (all tests pass) or 'red' (failures present)." |
| `review` | "Review phase: findings, ratings, verdict, fixture status, and delivery status." |
| `review.findings` | "Array of review findings (bugs, gaps, scope creep, style issues, etc.)." |
| `review.findings[].id` | "Unique kebab-case ID for this finding." |
| `review.findings[].type` | "Finding type: 'bug', 'gap', 'scope_creep', 'style', 'design', 'tests', 'docs'." |
| `review.findings[].severity` | "Finding severity: 'blocking' (must fix), 'major' (should fix), 'minor' (nice to fix), 'nit' (cosmetic). Blocking/major require remediation_task." |
| `review.findings[].spec_ref` | "Reference to the spec artifact related to this finding (with code location binding)." |
| `review.findings[].description` | "Description of the finding and its impact." |
| `review.findings[].related_checklist_ids` | "Array of SCREAMING_SNAKE checklist IDs affected by this finding." |
| `review.findings[].remediation_task` | "Remediation task definition. Required for blocking and major findings." |
| `review.findings[].remediation_task.task_id` | "Unique kebab-case ID for the remediation task." |
| `review.findings[].remediation_task.summary` | "Summary of remediation work required." |
| `review.findings[].remediation_task.files_to_touch` | "Array of file paths that need modification." |
| `review.findings[].remediation_task.checklist_ids` | "Array of checklist IDs that must be re-verified after remediation." |
| `review.findings[].metadata` | "Finding metadata: source and impact assessment." |
| `review.findings[].metadata.source` | "Source of the finding (e.g., 'automated-lint', 'peer-review', 'self-audit')." |
| `review.findings[].metadata.impact` | "Impact assessment of the finding." |
| `review.ratings` | "Review quality ratings (0-5 scale) across five dimensions." |
| `review.ratings.spec_completeness` | "How completely the implementation covers the spec requirements (0-5)." |
| `review.ratings.code_quality` | "Code quality rating: readability, patterns, error handling (0-5)." |
| `review.ratings.tests_completeness` | "Test coverage and quality rating (0-5)." |
| `review.ratings.docs_completeness` | "Documentation completeness rating (0-5)." |
| `review.ratings.metadata_usage` | "How well the implementation uses spec metadata (traces, refs, etc.) (0-5)." |
| `review.verdict` | "Final review verdict: 'verified' (approved), 'deferred' (needs more work), 'rejected' (fundamental issues)." |
| `review.next_actions` | "Free-text description of next actions after the review verdict." |
| `review.fixture_status` | "Status of fixture/test execution against the implementation." |
| `review.fixture_status.implemented_endpoints` | "Array of endpoint/API IDs that have been implemented." |
| `review.fixture_status.test_results` | "Array of per-fixture test results with pass/fail/skip status." |
| `review.fixture_status.test_results[].fixture_ref` | "Kebab-case ID of the fixture from Step 08." |
| `review.fixture_status.test_results[].status` | "Test result: 'pass', 'fail', 'skip'." |
| `review.fixture_status.test_results[].notes` | "Optional notes about the test result (e.g., skip reason)." |
| `review.fixture_status.test_results[].status_ref` | "Canonical reference for the test result status." |
| `review.fixture_status.ci_status` | "CI status for fixture tests: 'green' (all pass) or 'red' (failures). Must be 'green' for verified verdict." |
| `review.security_status` | "Security assessment status: 'green' (no security issues) or 'red' (security concerns remain)." |
| `review.delivery_status` | "Deployment status tracking across environments." |
| `review.delivery_status.deployments` | "Array of deployment records per environment." |
| `review.delivery_status.deployments[].env` | "Deployment environment: 'dev', 'staging', 'prod' (excludes 'ci' from the full environment enum)." |
| `review.delivery_status.deployments[].build_id` | "Kebab-case ID of the build/deployment." |
| `review.delivery_status.deployments[].status` | "Deployment status: 'pending', 'success', 'failed'." |
| `review.delivery_status.deployments[].status_ref` | "Canonical reference for the deployment status." |
| `review.semantic_review` | "Semantic review verifying FR coverage and detecting hallucinated features. Required for 'verified' verdict." |
| `review.semantic_review.fr_coverage` | "Array of FR coverage assessments. Each FR must have evidence of satisfaction. Min 1." |
| `review.semantic_review.fr_coverage[].fr_id` | "FR ID being assessed (kebab-case)." |
| `review.semantic_review.fr_coverage[].satisfied` | "Whether this FR is satisfied by the implementation (true/false)." |
| `review.semantic_review.fr_coverage[].evidence_summary` | "Summary (min 20 chars) of evidence that this FR is satisfied." |
| `review.semantic_review.fr_coverage[].checklist_ids` | "Array of checklist item IDs that satisfy this FR." |
| `review.semantic_review.hallucinated_features` | "Array of features found in the implementation that were not in the spec (min 10 chars each)." |
| `policy_ref` | "Canonical reference for the overall implementation policy." |
| `risk_category_ref` | "Canonical reference for the risk category of this implementation." |

---

## Question 3: LLM Confusion Risk Ranking

Properties ranked by risk of LLM misinterpretation without a description:

### Tier 1 -- CRITICAL confusion risk (name alone is deeply ambiguous)

1. **`status`** -- 13+ semantic variants. An LLM WILL confuse milestone status values with deployment status values.
2. **`severity`** -- 9 incompatible enums. "blocking" in findings vs "critical" in threats vs "warn" in invariants.
3. **`type`** -- 11 variants. "fr" in mitigations vs "service" in components vs "file_create" in actions.
4. **`scope`** -- 4 incompatible types (enum, object, stringArray). High confusion risk.
5. **`method`** -- HTTP verbs (5 vs 7) vs drift detection methods. Entirely different domains.
6. **`target`** -- number-or-string metric target vs file path target vs drift check target enum.
7. **`id`** -- kebabId vs screamingSnakeId vs canonicalId. Format confusion will cause validation errors.

### Tier 2 -- HIGH confusion risk (domain-specific semantics not obvious from name)

8. **`trace`** / **`trace_ref`** -- Traceability concept unique to this framework; LLMs may interpret as logging.
9. **`coverage_gaps`** -- Not test coverage; refers to upstream spec item coverage.
10. **`canonical_refs_used`** / **`canonical_proposals`** / **`canonical_conflicts`** -- Canonical registry is framework-specific.
11. **`spec_refs_ingested`** -- Framework-specific concept of upstream artifact ingestion.
12. **`generation_quality`** -- Only contains `assumptions`; name implies much more.
13. **`seed_refs`** -- "seed" is framework-specific (source documents, not random seeds).
14. **`evidence_binding`** -- Cryptographic evidence binding is non-obvious.
15. **`linked_test_expectation`** -- String or array, unusual polymorphism.

### Tier 3 -- MEDIUM confusion risk (might guess correctly but not certainly)

16-30. Various `*_ref` canonical references, step-specific domain properties like `vector`, `mitigations`, `spikes`, `deliverables`.

### Tier 4 -- LOW confusion risk (name is reasonably self-evident)

31+. Properties like `name`, `description`, `version`, `command`, `path`, `required`, `notes`, `tags`, `url`, `code`, `title`.

---

## Question 4: Where Should Descriptions Live?

**Recommendation**: Descriptions should live at BOTH levels:

1. **At the `$ref` target (core/)**: Define the STRUCTURAL semantics -- what the type IS, its format, constraints.
   - Example for `core/atoms#kebabId`: "Lowercase kebab-case identifier (e.g., 'fr-user-login'). Pattern: `^[a-z0-9]+(?:-[a-z0-9]+)*$`."

2. **At the `$ref` usage site (step schema)**: Define the CONTEXTUAL semantics -- what the field MEANS in this step.
   - Example for `04_fr_list.properties.functional_requirements[].fr_id`: "Unique kebab-case ID for this functional requirement (e.g., 'fr-user-login'). Convention: 'fr-' prefix."

This is valid in JSON Schema Draft 2020-12 -- `"description"` can coexist with `"$ref"` at the same level.

**Rationale**: Core descriptions provide the base understanding (type, format, constraints). Step descriptions provide the domain context (what does this ID identify? what is this array of?). An LLM needs BOTH to produce correct output.

---

## Question 5: Properties Where Description Would Be Noise

The following properties have names sufficiently self-evident that a description adds minimal value. However, for 100% coverage and LLM consistency, SHORT descriptions are still recommended:

| Property Path | Reason Name Is Sufficient | Recommended Minimal Description |
|---|---|---|
| `name` (in various contexts) | Universally understood | "Human-readable name." |
| `description` (in various contexts) | Universally understood | "Human-readable description." |
| `version` (in various contexts) | Universally understood | "Version string." |
| `notes` (in various contexts) | Universally understood | "Optional notes." |
| `url` (in various contexts) | Universally understood | "URL string." |
| `command` (in CI/test contexts) | Clear in context | "Shell command to execute." |
| `title` (in various contexts) | Universally understood | "Title string." |
| `tags` (when items are `$ref` to `atoms#tag`) | Clear in context | "Array of classification tags." |
| `$schema` (in all schemas) | JSON Schema standard | "JSON Schema URI for validation." |

**Total**: ~15-20 properties where a description is low-value but still recommended for completeness and LLM tool compatibility. Even "obvious" names like `description` benefit from a one-line description when the schema is consumed programmatically by an LLM -- it confirms that the LLM's assumption about the field's purpose is correct.

---

## Existing Description Quality Review

Of the 56 existing descriptions, quality assessment:

### Good (provides LLM-actionable context) -- 18

- `core/atoms.schema.json:$defs.metadata` -- "Generic key-value store for extra context..."
- `core/atoms.schema.json:$defs.owner` -- "Artifact owner -- validated against canon/kinds/owner.json entries."
- `core/collections.schema.json:$defs.traceRef.type` -- "Trace type -- validated against canon/kinds/trace_type.json entries."
- `core/collections.schema.json:$defs.seedRef.hash` -- "SHA-256 hash of the seed document at time of ingestion."
- `core/collections.schema.json:$defs.seedRef.version` -- "Version identifier of the seed document."
- `core/collections.schema.json:$defs.specRefIngested.step_id` -- "Pipeline step number of the ingested artifact."
- `core/collections.schema.json:$defs.specRefIngested.hash` -- "SHA-256 hash of the ingested artifact."
- `05_interface_contracts:apis[].enum_provenance` -- "Provenance tracking for externally-sourced enums..."
- `05_interface_contracts:apis[].enum_provenance.resolver` -- "Tool or person that resolved the enum values."
- `10_governance:commit_message_rules.error_message` -- "Human readable guidance. MUST list allowed types/values..."
- `12_ci_gates:jobs[].security` -- "CI security primitives for this job."
- `12_ci_gates:jobs[].security.runner_labels` -- "Runner isolation labels..."
- `12_ci_gates:jobs[].security.token_permissions` -- "Token permission scopes..."
- `12_ci_gates:jobs[].security.environment_protection.required_reviewers` -- "Number of required approvers..."
- `12_ci_gates:jobs[].security.environment_protection.wait_timer_minutes` -- "Delay in minutes..."
- `13_extension_generator:extensions[].extension_id` -- "Unique ID for the extension..."
- `13_extension_generator:extensions[].file_name` -- "Must follow pattern..."
- All 8 unique descriptions in `14_roadmap` -- Provide upstream traceability context.

### Adequate (correct but could be more specific) -- 17

- `13_extension_generator:extensions[].area_of_concern` -- "Domain (e.g. Data, Security, AI)" -- OK but could specify this is free-text.
- `15_scaffold:service_skeleton.language` -- "Programming language... Use lowercase/kebab-case." -- Good.
- `15_scaffold:service_skeleton.framework` -- "Web framework... Use lowercase/kebab-case." -- Good but "Web framework" shows domain bias.
- `16_impl_context:(top-level)` through all 12 step 16 descriptions -- Adequate, clearly describe purpose.

### Low-Value (boilerplate, identical across files) -- 19

- `_migration_notes` in all 19 step schemas -- "Optional migration notes added during schema version upgrades." Correct but adds minimal LLM value since this field is not used during spec generation.

### Inconsistent -- 2

- `16_impl_context:_migration_notes` says "...during version upgrades" while all others say "...during schema version upgrades." Minor inconsistency but should be unified.
