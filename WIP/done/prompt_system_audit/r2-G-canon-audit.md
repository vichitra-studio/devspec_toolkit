# R2-G: Canon System Audit — Glossary Merge & Pre-Population Evaluation

**Date**: 2026-03-20
**Scope**: Canon registry infrastructure, glossary step feasibility, pre-population assessment

## Canon Inventory

### 25 kinds, 72 total entries

| Kind | Entries | Truly Universal? | Schema Consumer | Validator Enforcement |
|------|---------|-------------------|-----------------|----------------------|
| trace_type | 8 (capability, fr, api, nfr, invariant, fixture, milestone, task) | Yes — required for traceability mechanics | `traceRef.type` pattern match | canonical-lint, integrity |
| status | 5 (draft, in_review, approved, deprecated, archived) | Yes — pipeline lifecycle | `atoms#status` enum | schema enum |
| completeness_dimension | 6 | Yes — completeness assessment | Step 13a schema | schema enum |
| owner | 8 (api, ui, system, ops, data, product, business, engineering) | Mostly — but projects may have different team structures | `atoms#owner` pattern (NOT enum) | Pattern only, not enforced against canon entries |
| stage | 4 (dev, ci, staging, prod) | Mostly — common but not universal | `collections#stageName` enum | schema enum |
| environment | 4 (dev, ci, staging, prod) | Mostly — near-duplicate of stage | `collections#environmentName` enum | schema enum |
| policy | 3 | Yes — governance mechanics | Step 10 schema | schema enum |
| id_pattern | 5 | Yes — ID format conventions | Referenced by prompts | Prompt-level only |
| acronym | 3 (FR, NFR, API) | Yes — toolkit terminology | None | None |
| role | 3 | Partially — could vary by project | None | None |
| unit | 4 (ms, percent, count, bytes) | Partially — domain-dependent | NFR targets | Pattern match |
| action | 2 | Partially | None | None |
| capability | 1 (authenticate) | **No — auth-domain specific** | None | None |
| command | 2 | Partially | None | None |
| dependency | 1 (jwt) | **No — auth-domain specific** | None | None |
| entity | 2 (user, session) | **No — auth-domain specific** | None | None |
| event | 2 (login-succeeded, login-failed) | **No — auth-domain specific** | None | None |
| governance_label | 2 | Yes — governance mechanics | Step 10 | Referenced |
| interface | 1 (auth-service) | **No — auth-domain specific** | None | None |
| metric | 2 | Partially | None | None |
| nfr_category | 5 | Yes — NFR classification | Step 07 | Referenced |
| risk_category | 4 | Yes — red team classification | Step 11 | Referenced |
| tag | 3 | Partially | None | None |
| tech_stack | 3 | **No — auth-domain specific** | None | None |
| term | 2 | **No — auth-domain specific** | None | None |

### Pre-Population Assessment

| Category | Kinds | Count | Recommendation |
|----------|-------|-------|----------------|
| **Must pre-populate** (toolkit mechanics) | trace_type, status, completeness_dimension, policy, id_pattern, governance_label, nfr_category, risk_category, acronym | ~37 entries | Keep — validators and schemas depend on these |
| **Sensible defaults** (common but overridable) | owner, stage, environment, unit, role | ~17 entries | Keep as defaults, allow project extension |
| **Should NOT pre-populate** (domain-specific) | capability, entity, event, interface, dependency, tech_stack, term, action, command, metric, tag | ~18 entries | Move to starter-kit/examples — these are auth-demo artifacts |

**Key finding**: 25% of canon entries (18/72) are auth-domain specific and meaningless for non-auth projects.

## Canon Schema Infrastructure

### Entry structure (`canon.schema.json`)
- Full lifecycle: `active → deprecated → sunset → retired`
- Required: `id`, `kind`, `preferred_label`, `definition`, `version`, `status`, `owners`, `lifecycle`
- Optional: `constraints`, `examples`, `tags`, `aliases`
- Conditional: deprecated requires `deprecated_since`, sunset requires `sunset_after`, retired requires `retired_at`

### Namespace convention
- Current: ALL entries use `cn:core:` — no separation between toolkit and project
- Canonical ID pattern: `^cn:[a-z0-9.]+:[a-z_]+:[a-z0-9-]+$`
- The pattern SUPPORTS `cn:project:` or `cn:domain:` namespaces — no schema change needed

### Pipeline population infrastructure (`step_base.schema.json`)
Every spec artifact inherits:
- `canonical_refs_used` (required) — canon refs consumed by this artifact
- `canonical_proposals` (optional) — new terms discovered during generation
- `canonical_conflicts` (optional) — ambiguous resolution conflicts

### `canonical_proposals` structure
- `temp_id` — temporary kebab-case ID
- `kind` — which canon kind
- `proposed_label` — human-readable name
- `definition` — what it means
- `source_field` — JSON path where found
- `suggested_namespace` — supports `cn:project:` separation

**The infrastructure for pipeline-populated canons is 80% built.** The gap is acceptance tooling.

## Enforcement Mechanics

### What canonical-lint checks
- Validates `canonical_refs_used` entries resolve to real canon entries
- Validates alias resolution
- Checks lifecycle status (warns on deprecated refs)

### What canonical-integrity checks
- Cross-artifact canonical consistency
- Drift detection between spec files and canon registry

### What is NOT enforced
- `owner` field uses regex pattern (`^[a-z][a-z0-9-]*$`), NOT enum — the 8 owner canon entries are documentation only
- Stage/environment ARE enum-enforced in `collections.schema.json` but also have canon kind entries (dual maintenance)
- No validator checks that downstream steps use glossary terms
- No tooling promotes `canonical_proposals` into the registry

## Current Glossary (Step 03) Assessment

### What it produces
- `spec/03_glossary.json` with `terms` array
- Each term: `term_id`, `term`, `definition`, `domain`, `aliases`, `see_also`, `lifecycle_states`
- Domain grouping, synonym tracking, cross-references

### Who consumes it
- Step 04 (FR): `trace_refs` can reference glossary terms — **only enforcement point**
- Steps 05, 07: prompts SAY "use glossary terms" but no validator checks
- All other downstream steps: **zero consumption**

### Verdict
The glossary is structurally decorative. It produces a well-formed artifact that almost nothing enforces.

## Glossary → Canon Feasibility

### What's needed
1. **Acceptance tooling** — CLI command: `specdev canon-accept --from spec/03_glossary.json` that promotes proposals into `canon/manifest.json`
2. **Namespace convention** — `cn:core:` (toolkit, pre-populated), `cn:project:` (pipeline-populated from Step 03)
3. **Step 03 prompt rewrite** — emit `canonical_proposals` array instead of `glossary.json`, or emit both during transition
4. **Kind extension** — project canons may need kinds not in the current 25 (e.g., `domain_concept`, `business_entity`)

### What already works
- `canonical_proposals` schema supports all needed fields
- `suggested_namespace` supports `cn:project:` separation
- `canonical-lint` would automatically enforce project canons once they're in the registry
- Waterfall ordering guarantees Step 03 runs before all downstream consumers

### Can we reliably populate canons at Step 03?
**Yes for domain vocabulary.** The waterfall guarantees Step 03 executes after Steps 00-02a (which define the domain context). Steps 04+ can propose additional terms via `canonical_proposals` if Step 03 missed them.

**Risk**: Steps 04+ discovering terms Step 03 should have captured. Mitigated by `canonical_proposals` on every step — later steps propose, a review/accept step integrates.

## Stage/Environment Duplication

Stage and environment canon kinds have identical entries (dev, ci, staging, prod). Both are also hardcoded as enums in `collections.schema.json` (`stageName`, `environmentName`). This is triple maintenance — canon kind + canon kind + schema enum.

## Findings

### R2-G-001: 25% of canon entries are auth-domain specific
- **Severity**: MEDIUM
- **Evidence**: capability (authenticate), entity (user, session), event (login-succeeded, login-failed), interface (auth-service), dependency (jwt), tech_stack (python, fastapi, postgresql), term (authentication, session-management)
- **Fix**: Move to `canon/examples/` or `canon/starter-kit/`. Keep toolkit-mechanical canons only.

### R2-G-002: No namespace separation between toolkit and project canons
- **Severity**: HIGH
- **Evidence**: All 72 entries use `cn:core:`. Pattern supports other namespaces but none are used.
- **Fix**: Establish `cn:core:` = toolkit, `cn:project:` = pipeline-populated. Document convention.

### R2-G-003: Owner validation is documentation-only
- **Severity**: MEDIUM
- **Evidence**: `atoms#owner` uses regex `^[a-z][a-z0-9-]*$`. The 8 owner canon entries exist but nothing validates against them. Any lowercase string passes.
- **Fix**: Either enforce owner values against canon (preferred) or remove owner canon kind as misleading.

### R2-G-004: Stage and environment are triple-maintained
- **Severity**: LOW
- **Evidence**: Same 4 values in `canon/kinds/stage.json`, `canon/kinds/environment.json`, and hardcoded enums in `collections.schema.json`.
- **Fix**: Single source — either canon-driven enum or schema enum with canon as documentation.

### R2-G-005: No tooling to accept canonical_proposals into registry
- **Severity**: HIGH
- **Evidence**: `canonical_proposals` schema exists in `step_base.schema.json`, supported by `canonicalProposal` in collections. But no CLI command or validator promotes proposals.
- **Fix**: Build `specdev canon-accept` command. This is the critical missing piece for glossary→canon merge.

### R2-G-006: Glossary downstream enforcement is decorative
- **Severity**: HIGH (corroborates R2-E glossary finding)
- **Evidence**: Only Step 04 trace_refs validate glossary terms. Steps 05-16c say "use glossary terms" but no validator checks.
- **Fix**: Once glossary terms are in canon, canonical-lint enforces automatically.

### R2-G-007: canonical_proposals supports the glossary→canon merge
- **Severity**: INFO
- **Evidence**: `canonicalProposal` has `temp_id`, `kind`, `proposed_label`, `definition`, `source_field`, `suggested_namespace` — all fields needed for project canon population.
- **Fix**: Build the acceptance tooling. Schema changes: none needed.
