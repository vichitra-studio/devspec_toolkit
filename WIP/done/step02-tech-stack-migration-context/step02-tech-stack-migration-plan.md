# Step 02 Tech Stack Migration — Implementation & Review Reference

**Goal**: Move technology resolution from Step 09 (Implementation Plan) to Step 02 (System Sketch), so Steps 03–08 have access to technology decisions. Step 09 inherits/confirms the tech stack from Step 02 rather than generating it from scratch.

**Branch**: `codex/canonical-drift-review-plan`
**Date**: 2026-03-25

---

## Design Decision

### Why move tech_stack to Step 02?

Currently, the pipeline's technology decisions are first declared at Step 09 (Implementation Plan). This means Steps 03–08 (Glossary, FRs, Interface Contracts, Invariants, NFRs, Fixtures) operate **blind to technology choices**. This causes:

1. **Interface Contracts (Step 05)** cannot tailor API style (REST vs gRPC vs GraphQL) to the declared framework
2. **NFRs (Step 07)** cannot set framework-specific performance baselines (e.g., FastAPI async vs Django sync)
3. **Fixtures (Step 08)** cannot generate framework-specific test setup (e.g., pytest-django fixtures vs httpx for FastAPI)
4. **Red Team (Step 11)** must guess at technology-specific attack surfaces

### Reuse strategy

We reuse `vc:core:collections#techStack` — the same `$ref` that Step 09 uses. This gives us:
- **techStackItem**: `name` (required), `version` (required), `notes`, `rationale`, `tech_stack_ref`
- **techStack**: `languages` (required), `frameworks` (required), `infrastructure` (optional), `tools` (optional)

Step 02 will require all 4 categories (same as Step 09's overlay). This is a conscious design choice — the base `techStack` schema only requires `languages` and `frameworks`, but Step 02's overlay adds `infrastructure` and `tools` as required to match the breadth of `seed_tech_stack.md`. Note that the seed template doesn't have an explicit "tools" section (CI/CD tools appear in §4.4 "Build, Test & Deploy"), so the "Resolve Tech" prompt phase must map seed sections to `techStack` categories intelligently.

### Ownership model after migration

- **Step 02**: Source of truth for technology decisions. Extracted from `seed_tech_stack.md`.
- **Step 09**: Inherits from Step 02. May refine (e.g., add version pins, add spike-discovered tools). Its schema `tech_stack` field remains (backward compat), but the prompt changes from "decide" to "confirm/refine".

### Breaking change & migration path

Making `tech_stack` required in the Step 02 schema is a **breaking change**. Any host repo with an existing `spec/02_system_sketch.json` that lacks `tech_stack` will fail validation after upgrading the toolkit submodule.

**Required actions**:
1. Add a changelog entry under the next version bump (0.6.0 or 0.5.1) noting the breaking schema change
2. Document migration: "After upgrading, add a `tech_stack` field to your `spec/02_system_sketch.json` with at least one entry per category (languages, frameworks, infrastructure, tools). Re-run `specdev validate spec/02_system_sketch.json` to verify."
3. Consider whether `specdev align` should auto-detect and assist with this migration

> **Note**: The toolkit's own `spec/` directory does NOT contain a `02_system_sketch.json`, so no in-repo artifact breaks.

---

## Change Manifest

### Task 0 — Changelog: Document breaking schema change

**Files** (two files, both required — see `CHANGELOG.md` Contribution Guide):
1. `changelog/unreleased.md` — human-readable note (edit the existing `## [Unreleased]` section)
2. `changelog/unreleased.yaml` — machine spec for `specdev align` (file does not yet exist — create it)

**Batch**: Batch A (parallel with other tasks — no dependencies)

#### 0a. Edit `changelog/unreleased.md`

The actual `changelog/unreleased.md` uses `## Breaking Changes` (h2) as the top-level section
header with bullet entries directly beneath it — NOT a `### Breaking` sub-section under
`## [Unreleased]`. (The CHANGELOG.md Contribution Guide example uses `### Changed` under
`## [Unreleased]`, but the live file already has a different, established structure — follow
the file, not the guide example.)

Add a bullet under the **existing** `## Breaking Changes` section:

```markdown
- **`02_system_sketch` schema — `tech_stack` promoted to required** (BREAKING): `tech_stack`
  is now a required field in `spec/02_system_sketch.json`. Host repos with an existing
  `02_system_sketch.json` that lacks `tech_stack` will fail `specdev validate` after upgrading.
  Migration: add a `tech_stack` object with at least one entry per category (`languages`,
  `frameworks`, `infrastructure`, `tools`). Re-run `specdev validate spec/02_system_sketch.json`
  to verify.
```

#### 0b. Create `changelog/unreleased.yaml`

Create this file (it does not yet exist). The `unreleased.yaml` uses `changes: [...]` at the
top level — no `version`, `release_date`, or `breaking` fields are needed (those are added when
the file is renamed to `vX.Y.Z.yaml` at release time). Refer to `changelog/format.yaml` for
the full `change_types` and `migration_actions` enums.

Valid `change_types` from format.yaml: `add_field`, `add_constraint`, `change_schema`, etc.
Valid `migration_actions` from format.yaml: `none`, `auto`, `ai_assisted`, `merge`, `archive`.
(Note: `add_required_field` and `manual_with_guidance` are NOT valid — they are not in the enum.)

Two changes are needed: one to record adding the field, one to record making it required.

```yaml
changes:
  - type: add_field
    path: "02_system_sketch.tech_stack"
    description: "tech_stack field added to Step 02 system sketch as the authoritative source for technology decisions"
    migration:
      action: ai_assisted
      note: "Use template_infer_missing.md prompt to populate tech_stack from seed_tech_stack.md"
  - type: add_constraint
    path: "02_system_sketch.tech_stack"
    description: "tech_stack promoted to required — all 4 categories (languages, frameworks, infrastructure, tools) required"
    migration:
      action: ai_assisted
      note: "Use template_infer_missing.md prompt to populate all 4 required tech_stack categories"
```

> **Note**: `action: ai_assisted` is correct because populating `tech_stack` from
> `docs/seed/seed_tech_stack.md` requires AI reasoning (resolving `[AUTO-DERIVE]` markers,
> mapping seed sections to categories, inferring versions). The `note:` field records the
> migration template name as guidance text — use `template_infer_missing.md` as a placeholder;
> adjust to the actual template name if a tech-stack-specific template is created.
>
> **Format note (BUG B13/B14 fix)**: The established changelog yaml format (`v0.3.0.yaml`,
> `v0.4.0.yaml`) uses `path:` for fully-qualified field references (not `step_id:`), and uses
> `note:` (not `prompt:`) as the sub-key under `migration:`. Both are corrected above.

**Review checklist**:
- [ ] `changelog/unreleased.md` updated under `## [Unreleased]` section (NOT under a version bump header)
- [ ] Entry clearly flags this as a breaking change
- [ ] Migration instructions included
- [ ] `changelog/unreleased.yaml` created with two entries: `add_field` + `add_constraint` for Step 02 `tech_stack`; `action: ai_assisted` (NOT `manual_with_guidance`); uses `note:` (NOT `prompt:`); uses `path: "02_system_sketch.tech_stack"` (NOT `step_id:` + `path: "tech_stack"`)

---

### Task 1 — Schema: Add `tech_stack` to Step 02

**File**: `schema/02_system_sketch.schema.json`
**Location**: Inside the second `allOf` item (the `type: object` block, lines 10–236), add `tech_stack` to `properties` alongside `components` and `connections`.

**Why `properties` block matters**: The schema uses `unevaluatedProperties: false` (line 260). Any property not declared in `properties` will cause validation to REJECT the artifact. This is not optional — without this change, any Step 02 artifact containing `tech_stack` will fail Tier 1 schema validation.

**Exact change**:

Two edits are required:

**Edit 1 — Add trailing comma to `connections` (line 231)**

Line 231 currently ends with `        }` (8-space indent, no comma) because `connections` is the last property. Since we are adding `tech_stack` after it, change line 231 from:
```
        }
```
to:
```
        },
```
Without this comma, the resulting JSON Schema file will be syntactically invalid.

> **Verify before editing**: Line 231 should read `        }` (8 spaces). Line 232 should
> read `      },` (6 spaces, already has comma) — that is the `properties` block closer, NOT
> the connections closer. Editing line 232 would be wrong.

**Edit 2 — Insert `tech_stack` block after the modified line 231** (before the `},` that closes `properties` at line 232):

```json
"tech_stack": {
  "description": "Technology decisions for the system, extracted from seed_tech_stack.md. Declares the languages, frameworks, infrastructure, and tools that downstream steps (05 Interface Contracts, 07 NFRs, 08 Fixtures, 15 Scaffold) should use when making technology-dependent decisions. Step 09 (Implementation Plan) inherits and may refine these choices.",
  "allOf": [
    {
      "$ref": "vc:core:collections#techStack",
      "description": "Inherits the structured technology stack definition from core collections."
    },
    {
      "required": ["languages", "frameworks", "infrastructure", "tools"]
    }
  ]
}
```

> **Note**: The `$ref` allOf item includes an inline `description` to match the established pattern used by Step 09's `tech_stack` declaration in `schema/09_impl_plan.schema.json`.

> **Result after both edits**: `properties` will contain `components`, `connections,` and `tech_stack`. The `},` at what was line 232 (now shifted down after insertion) still closes `properties`. Validate the resulting JSON is well-formed before committing.

Also update the `required` array (lines 233–235 in the pre-edit file; line numbers shift after Edit 2 inserts the tech_stack block — find by content). The actual file uses multi-line format:

From:
```
      "required": [
        "components"
      ],
```
To:
```
      "required": [
        "components",
        "tech_stack"
      ],
```

> **Format note (BUG B15 fix)**: The single-line form `"required": ["components"]` does NOT appear in the file — the array is multi-line. An Edit tool old_string using the single-line form will fail to match. Preserve the multi-line convention; do not collapse to one line.

**Review checklist**:
- [ ] `tech_stack` is inside the `properties` block of the second `allOf` item (NOT in the third `allOf` conditional item)
- [ ] Uses `$ref: "vc:core:collections#techStack"` — not a copy of the schema
- [ ] Overlay requires all 4 categories: `languages`, `frameworks`, `infrastructure`, `tools`
- [ ] `tech_stack` added to `required` array
- [ ] `unevaluatedProperties: false` at line 260 is NOT modified

---

### Task 2 — Prompt: Add Technology Resolution to Step 02

**File**: `prompts/prompt_02_system_sketch.md`

#### 2a. Extraction Intent (line 15–18)

Current extraction for `seed_tech_stack.md` (line 16):
```
- **docs/seed/seed_tech_stack.md** (required): Architecture patterns, technology constraints, infrastructure decisions, and deployment topology for component design
```

**Change to**:
```
- **docs/seed/seed_tech_stack.md** (required): Technology decisions (languages, frameworks, infrastructure, tools), architecture patterns, deployment topology, and technology constraints for both component design and tech_stack population
```

#### 2b. Operating Flow header (line 20) and bullets (lines 22–25)

Current header at line 20:
```
## Operating Flow: Decompose → Connect → Verify → Emit
```

**Change header to**:
```
## Operating Flow: Decompose → Resolve Tech → Connect → Verify → Emit
```

Current 4-phase flow (bullets at lines 22–25): `Decompose → Connect → Verify → Emit`

**Change to 5-phase flow**: `Decompose → Resolve Tech → Connect → Verify → Emit`

Insert after the `Decompose` bullet (line 22):
```
- **Resolve Tech**: Extract technology decisions from `docs/seed/seed_tech_stack.md` into the `tech_stack` field. For each category (languages, frameworks, infrastructure, tools): resolve `[AUTO-DERIVE]` markers using system type, component types, and charter constraints. Validate consistency — a component of `type: db` should have a matching entry in `tech_stack.infrastructure`. Challenge version specificity: "Python 3" should become "Python 3.12" with rationale.
```

#### 2c. Purpose statement (line 11)

Current:
```
Build a lightweight architecture map that shows the components required to deliver the approved capabilities and how data flows between them. The system sketch communicates ownership, technology choices, and integration contracts early so interface design and delivery planning stay coherent.
```

**Change to**:
```
Build a lightweight architecture map that shows the components required to deliver the approved capabilities, the technology stack that implements them, and how data flows between them. The system sketch communicates ownership, technology choices, and integration contracts early so downstream steps (interface contracts, NFRs, fixtures, scaffold) can make technology-aware decisions.
```

#### 2d. Heuristics For Completeness (line 36–41)

Add after the existing bullets:
```
- MUST populate `tech_stack` with at least one entry in each of `languages`, `frameworks`, `infrastructure`, and `tools`. MUST resolve any `[AUTO-DERIVE]` markers from `docs/seed/seed_tech_stack.md` into concrete technology choices with version and rationale. MUST cross-check that `type: db` components have corresponding `tech_stack.infrastructure` entries.
```

#### 2e. Coverage Closure (add after line 74 — end of section)

> **Note**: The Coverage Closure section runs from line 60 to line 74. Line 65 is a mid-section bullet about tech choices aligning with seed constraints. Append the new items after line 74 (the last checklist item `- [ ] Every external system dependency...`), not after line 65. (Line 75 is blank; line 76 starts `## Step-Specific Completeness Checklist`.)

Add after line 74:
```
- [ ] `tech_stack` has at least one entry per category (languages, frameworks, infrastructure, tools)
- [ ] Every `[AUTO-DERIVE]` marker from seed_tech_stack.md has been resolved to a concrete choice
- [ ] Database/cache/queue component types have matching infrastructure entries in tech_stack
```

#### 2f. Step-Specific Completeness Checklist (after line 82)

Add:
```
- `tech_stack` covers all technology decisions from `docs/seed/seed_tech_stack.md`; each entry has `name`, `version`, and `rationale` (rationale required for all non-obvious choices).
- Infrastructure entries in `tech_stack` are consistent with component types (db, cache, queue) declared in `components`.
```

#### 2h. Downstream consumer count (line 8)

Current:
```
This prompt's output feeds 6 downstream steps.
```

**Change to**:
```
This prompt's output feeds 12 downstream steps.
```

The 6 original consumers (02a, 05, 09, 11, 13, 15) plus 6 new consumers added by this migration (03, 06, 07, 08, 10, 14) = 12 total. This number is derived from the `downstream_consumers["02"]` array in `tools/step_order.json` after Task 12 is applied — verify the count matches before committing.

---

#### 2g. Output Contract (line 117–144)

Add `tech_stack` to the example JSON output, after `connections`:
```json
"tech_stack": {
  "languages": [
    {
      "name": "TypeScript",
      "version": "5.4",
      "rationale": "Team expertise and type safety for API development"
    }
  ],
  "frameworks": [
    {
      "name": "Express",
      "version": "^4.19",
      "rationale": "Lightweight HTTP framework matching team experience"
    }
  ],
  "infrastructure": [
    {
      "name": "PostgreSQL",
      "version": "16",
      "rationale": "JSONB support for flexible schema evolution"
    }
  ],
  "tools": [
    {
      "name": "ESLint",
      "version": "^9.0",
      "rationale": "Standard linting for TypeScript projects"
    }
  ]
},
```

**Review checklist**:
- [ ] Extraction Intent explicitly references `seed_tech_stack.md` for tech_stack population
- [ ] Operating Flow **header** (line 20) updated to 5 phases AND new bullet inserted after Decompose
- [ ] Operating Flow has 5 phases including "Resolve Tech"
- [ ] Heuristics enforce all 4 categories populated and cross-check with component types
- [ ] Output Contract includes a realistic tech_stack example
- [ ] No mention of Step 09 generating tech_stack (Step 02 is now the source of truth)
- [ ] Line 8 updated from "feeds 6 downstream steps" to "feeds 12 downstream steps" (see Task 2h; new consumers: 03, 06, 07, 08, 10, 14 — total: 02a, 03, 05, 06, 07, 08, 09, 10, 11, 13, 14, 15)

---

### Task 3 — Prompt: Step 09 inherits tech_stack from Step 02

**File**: `prompts/prompt_09_impl_plan.md`

#### 3a. Extraction Intent (line 17)

Current Step 02 extraction:
```
- **02_system_sketch.json**: Component IDs, component status (active vs deprecated), and inter-component data flows to inform architecture decisions and trigger migration plan requirements
```

**Change to**:
```
- **02_system_sketch.json**: Component IDs, component status (active vs deprecated), inter-component data flows, and **tech_stack** decisions (languages, frameworks, infrastructure, tools) as the baseline technology stack to inherit and optionally refine
```

#### 3b. Operating Flow — Resource phase (line 29)

Modify the `Resource` bullet (line 29; note: Scope is at line 27, Sequence at line 28):

Current:
```
- **Resource**: Assign effort estimates, owners, and tech stack components per milestone. Validate feasibility against charter constraints.
```

**Change to**:
```
- **Resource**: Inherit `tech_stack` from `spec/02_system_sketch.json` as the baseline. Refine only when implementation planning reveals needs not covered at architecture time (e.g., a testing tool discovered during spike scoping, a version pin change based on compatibility testing). Assign effort estimates and owners per milestone. Validate feasibility against charter constraints.
```

#### 3c. Reconcile phase (line 32)

Current:
```
- Verify `tech_stack` entries are consistent with `spec/02_system_sketch.json` component IDs and technology choices — no tech stack item should contradict the system sketch architecture.
```

**Change to**:
```
  - Verify `tech_stack` entries are a superset of `spec/02_system_sketch.json` `tech_stack` — Step 09 may ADD refinements (version pins, spike-discovered tools) but MUST NOT REMOVE or contradict entries from Step 02. Any tech stack item in Step 02 that is absent from Step 09 is a gap requiring explicit justification.
```

> **Formatting note (Ambiguity A1 fix)**: Line 32 is a sub-bullet of Reconcile. The replacement text must preserve the 2-space leading indent — use `  - Verify` (two spaces + dash), not `- Verify`.

#### 3d. Negative Constraints (line 57)

Current:
```
- **NO Hallucinations**: Do not list technologies in `tech_stack` that are not present in `spec/01_capabilities.json` without a clear "Spike" justification.
```

**Change to**:
```
- **NO Hallucinations**: Do not list technologies in `tech_stack` that are not present in `spec/02_system_sketch.json` `tech_stack` or `spec/01_capabilities.json` without a clear "Spike" justification.
```

#### 3e. Step-Specific Completeness Checklist (line 80)

Current:
```
- `tech_stack` declares languages, frameworks, data stores, and major infra choices with rationale where contentious.
```

**Change to**:
```
- `tech_stack` inherits from `spec/02_system_sketch.json` `tech_stack` and may add implementation-time refinements. All Step 02 `tech_stack` entries must be present (superset rule). New entries require rationale.
```

> **Formatting note**: Use backtick-formatted `` `tech_stack` `` in the replacement text to match the file's existing convention.

**Review checklist**:
- [ ] Extraction Intent lists `tech_stack` as a field extracted from Step 02
- [ ] Operating Flow says "inherit" not "generate"
- [ ] Reconcile enforces superset rule (Step 09 >= Step 02)
- [ ] Negative Constraints reference Step 02 tech_stack
- [ ] Step 09 schema is NOT changed (its `tech_stack` field remains required — it just inherits + refines)

---

### Task 4 — Prompt: Step 05 extracts tech_stack from Step 02

**File**: `prompts/prompt_05_interface_contracts.md`

#### 4a. Extraction Intent (line 17)

Current Step 02 extraction:
```
- **02_system_sketch.json**: Component IDs, trust boundaries, and inter-component communication paths to assign each API to an owning component and enforce correct security at boundary crossings
```

**Change to**:
```
- **02_system_sketch.json**: Component IDs, trust boundaries, inter-component communication paths, and **tech_stack** (framework and language choices that inform API style — e.g., REST with FastAPI, GraphQL with Apollo, gRPC with protobuf) to assign each API to an owning component and enforce correct security at boundary crossings
```

**Review checklist**:
- [ ] `tech_stack` extraction is mentioned with specific examples of how it informs API design
- [ ] No other changes to Step 05 prompt

---

### Task 5 — Prompt: Step 07 extracts tech_stack from Step 02

**File**: `prompts/prompt_07_nfrs.md`

#### 5a. Extraction Intent (line 17)

Current Step 02 extraction:
```
- **02_system_sketch.json**: Component IDs, service boundaries, data store types, and infrastructure topology to assign NFR ownership to specific components and to derive availability, durability, and latency targets for each service tier
```

**Change to**:
```
- **02_system_sketch.json**: Component IDs, service boundaries, data store types, infrastructure topology, and **tech_stack** (language/framework runtime characteristics that inform baseline performance expectations — e.g., async Python frameworks have different latency profiles than JVM-based services) to assign NFR ownership to specific components and to derive availability, durability, and latency targets for each service tier
```

**Review checklist**:
- [ ] `tech_stack` extraction mentions performance implications of technology choices
- [ ] No other changes to Step 07 prompt

---

### Task 6 — Prompt: Step 08 extracts tech_stack from Step 02

**File**: `prompts/prompt_08_fixtures.md`

#### 6a. Extraction Intent (line 23)

Current Step 02 extraction:
```
- **02_system_sketch.json**: Component IDs and inter-component data flow paths to determine which components need contract-mode fixtures and to structure end-to-end fixture chains across service boundaries
```

**Change to**:
```
- **02_system_sketch.json**: Component IDs, inter-component data flow paths, and **tech_stack** (framework choices that determine test runner, fixture format, and setup/teardown patterns — e.g., pytest fixtures for Python, Jest for TypeScript, testcontainers for integration tests) to determine which components need contract-mode fixtures and to structure end-to-end fixture chains across service boundaries
```

**Review checklist**:
- [ ] `tech_stack` extraction mentions test framework implications
- [ ] No other changes to Step 08 prompt

---

### Task 7 — Prompt: Step 11 extracts tech_stack from Step 02

**File**: `prompts/prompt_11_redteam.md`

#### 7a. Extraction Intent (line 38)

Current Step 02 extraction:
```
- **02_system_sketch.json**: Component IDs, trust boundary crossings, inter-component communication paths, and external integration points to map every threat to a concrete target_ids entry
```

**Change to**:
```
- **02_system_sketch.json**: Component IDs, trust boundary crossings, inter-component communication paths, external integration points, and **tech_stack** (specific framework/runtime versions that have known CVE surfaces or security-relevant configuration defaults — e.g., Django CSRF middleware vs manual CSRF in Express) to map every threat to a concrete target_ids entry
```

> **Dual extraction note**: After this change, Step 11 extracts tech_stack from BOTH Step 02 (via this bullet) and Step 09 (existing extraction at line 46: `09_impl_plan.json` technology stack selections). This is intentional: Step 09's tech_stack is a superset (refined). Step 11 should prefer Step 09's tech_stack for threat analysis (it has implementation-time version pins), using Step 02 as a fallback if Step 09 is not yet generated.

**Review checklist**:
- [ ] `tech_stack` extraction mentions CVE and security-configuration implications
- [ ] No other changes to Step 11 prompt
- [ ] Prompt does NOT contradict Step 09's tech_stack extraction (both sources are valid)

---

### Task 8 — Prompt: Step 15 sources tech_stack from Step 02

**File**: `prompts/prompt_15_scaffold.md`

#### 8a. Consolidate Step 02 extraction (line 19) and update Step 09 extraction (line 22)

The existing Step 02 bullet at line 19 and the Step 09 bullet at line 22 both need changes. To avoid creating duplicate `02_system_sketch.json` entries, we consolidate into ONE Step 02 bullet at line 19 and keep line 22 as Step 09 only.

**Line 19 — Step 02 extraction**

Current:
```
- **02_system_sketch.json**: Component IDs and service boundaries used to derive the project_skeleton module structure ensuring each architectural component has a scaffold directory
```

**Change to**:
```
- **02_system_sketch.json**: Component IDs, service boundaries, and **tech_stack** (`tech_stack.languages`, `tech_stack.frameworks`, `tech_stack.infrastructure`, `tech_stack.tools` — primary source of technology decisions) used to derive the project_skeleton module structure, language/framework selection, and scaffold directory conventions
```

**Line 22 — Step 09 extraction**

Current:
```
- **09_implementation_plan.json**: Technology stack decisions (language, framework, tools) directly consumed to set project_skeleton.language and project_skeleton.framework fields and module conventions
```

**Change to**:
```
- **09_implementation_plan.json**: Refined technology stack (version pins, spike-discovered tools) and milestone sequencing consumed to supplement Step 02 tech_stack with implementation-time additions
```

**Review checklist**:
- [ ] Only ONE `02_system_sketch.json` bullet exists in the Extraction Intent section (no duplicates)
- [ ] Step 02 is the primary tech_stack source for scaffold generation
- [ ] Step 09 is a supplementary/refinement source

---

### Task 9 — Test Fixtures: Add tech_stack to Step 02 fixtures

**Files**:
- `tests/fixtures/step_02/valid_minimal.json` — add minimal tech_stack
- `tests/fixtures/step_02/valid_standard.json` — add realistic tech_stack
- `tests/fixtures/step_02/valid_external_integration.json` — add tech_stack
- `tests/fixtures/step_02/invalid_missing_required.json` — verify it fails without tech_stack (if tech_stack is required)

#### 9a. `valid_standard.json`

> **JSON comma note**: The blocks below show the tech_stack value object only. When inserting into a JSON file where another property (`"canonical_refs_used"`) follows, the closing `}` of the tech_stack value must have a trailing comma (`},`). The blocks show `},` where a comma is required.

Add after `"connections": [...]` (line 132), before `"canonical_refs_used"`:

```json
"tech_stack": {
  "languages": [
    { "name": "TypeScript", "version": "5.4", "rationale": "Type safety for service development" }
  ],
  "frameworks": [
    { "name": "Express", "version": "^4.19", "rationale": "HTTP framework for user-service and auth-service" }
  ],
  "infrastructure": [
    { "name": "PostgreSQL", "version": "16", "rationale": "Primary data store for user-db component" }
  ],
  "tools": [
    { "name": "ESLint", "version": "^9.0", "rationale": "Linting for TypeScript codebase" }
  ]
},
```

> The trailing `},` is required because `"canonical_refs_used"` follows immediately after.

#### 9b. `valid_minimal.json`

Read the file first to determine structure. Add a minimal tech_stack using the same technology choices as Task 9e's block:
```json
"tech_stack": {
  "languages": [{ "name": "Python", "version": "3.12" }],
  "frameworks": [{ "name": "FastAPI", "version": "0.111" }],
  "infrastructure": [{ "name": "SQLite", "version": "3" }],
  "tools": [{ "name": "pytest", "version": "8.0" }]
}
```

> **Trailing comma note (Ambiguity A2 fix)**: The block above shows no trailing `,`. Add `},` (trailing comma) after the closing `}` if any other property follows `tech_stack` in the file (e.g., `canonical_refs_used`). Read the file structure first to confirm.

#### 9c. `valid_external_integration.json`

Read the file first. Add tech_stack consistent with the external integration scenario — use the same base block as 9b plus an additional `infrastructure` entry for the external client (e.g., `httpx 0.27` if HTTP-based, or match the external system type shown in the fixture):
```json
"tech_stack": {
  "languages": [{ "name": "Python", "version": "3.12" }],
  "frameworks": [{ "name": "FastAPI", "version": "0.111" }],
  "infrastructure": [
    { "name": "SQLite", "version": "3" },
    { "name": "httpx", "version": "0.27", "rationale": "HTTP client for external integration" }
  ],
  "tools": [{ "name": "pytest", "version": "8.0" }]
}
```

#### 9d. `invalid_missing_required.json`

This fixture tests for missing **component-internal** required fields (`responsibilities`, `owner`, `trace`) — it has a `components` array with a single component missing those fields. It does NOT test for missing top-level fields.

Once `tech_stack` is made required, this fixture will fail for TWO reasons: (1) missing component-internal fields AND (2) missing `tech_stack`. This muddies the test intent.

**REQUIRED**: Create a new `invalid_missing_tech_stack.json` that has valid `components` (with all required component fields) but no `tech_stack` field. Expected error: `'tech_stack' is a required property`. This ensures we have a dedicated fixture testing specifically for the missing `tech_stack` case.

#### 9e. All other invalid fixtures — add `tech_stack` to prevent unintended failures

Making `tech_stack` required at the top level means **every invalid fixture that tests a component-level or connection-level error** will ALSO fail schema validation for missing `tech_stack`, muddying test intent. These fixtures must have a valid `tech_stack` block added so they fail only for their intended reason.

**Affected fixtures** (all in `tests/fixtures/step_02/`):
- `invalid_dangling_connection.json`
- `invalid_duplicate_component_id.json`
- `invalid_empty_components.json`
- `invalid_event_no_reliability.json`
- `invalid_external_internal_trust_boundary.json`
- `invalid_missing_trace_refs.json`
- `invalid_multi_component_no_connections.json`
- `invalid_no_responsibilities.json`
- `invalid_not_enough_responsibilities.json`
- `invalid_rate_limit_bounds.json`
- `invalid_rate_limit_burst_lt_rps.json`
- `invalid_rate_limit_shape.json`
- `invalid_schema_ref_format.json`
- `invalid_tag_vocab.json`
- `invalid_too_many_responsibilities.json`
- `invalid_trust_boundary_enum.json`
- `invalid_trust_boundary_missing_rate_limit.json`
- `invalid_trust_boundary_no_auth.json`
- `invalid_capability_coverage.json`

**For each**: Read the file, add a minimal valid `tech_stack` block (same as `valid_minimal.json` uses). The `tech_stack` should NOT be the thing being tested — it should be valid so the fixture tests only its intended failure mode.

**Minimal tech_stack block for invalid fixtures**:
```json
"tech_stack": {
  "languages": [{ "name": "Python", "version": "3.12" }],
  "frameworks": [{ "name": "FastAPI", "version": "0.111" }],
  "infrastructure": [{ "name": "SQLite", "version": "3" }],
  "tools": [{ "name": "pytest", "version": "8.0" }]
}
```

> **Exception**: `invalid_missing_required.json` does NOT get `tech_stack` — it intentionally tests missing required fields (and now tests for missing `tech_stack` too, alongside missing component fields). The dedicated `invalid_missing_tech_stack.json` (Task 9d) provides a clean single-purpose test.

#### 9f. Test file impact

**`tests/integration/test_step_02.py`** loads all Step 02 fixtures and validates them against the schema. If schema requires `tech_stack` but valid fixtures haven't been updated, this test will break. Schema (Task 1) and fixture updates (Task 9) MUST be deployed atomically — they cannot be in separate batches. See updated Execution Order below.

**REQUIRED — add new fixture to test's hardcoded list**: `tests/integration/test_step_02.py` has a hardcoded `invalid_fixtures` list (lines 85–106). The new `invalid_missing_tech_stack.json` from Task 9d will NOT be tested unless it is explicitly added to this list. Add `"invalid_missing_tech_stack.json"` to the `invalid_fixtures` list (e.g., after `"invalid_missing_required.json"`):

```python
invalid_fixtures = [
    "invalid_empty_components.json",
    "invalid_missing_required.json",
    "invalid_missing_tech_stack.json",   # ← add this (Task 9d)
    "invalid_no_responsibilities.json",
    ...
]
```

> **BUG B17 fix**: The test uses a hardcoded list, not a directory scan. New fixtures are silently ignored unless added here. The review checklist "Run `pytest tests/`" cannot catch this omission — the test would pass without the new fixture by simply never loading it.

**Review checklist**:
- [ ] All 3 valid fixtures include `tech_stack` with all 4 categories
- [ ] Infrastructure entries match component types (e.g., PostgreSQL for `user-db`)
- [ ] New `invalid_missing_tech_stack.json` created (tests missing `tech_stack` in isolation)
- [ ] `invalid_missing_tech_stack.json` added to `invalid_fixtures` list in `tests/integration/test_step_02.py`
- [ ] All 19 other invalid fixtures have a valid minimal `tech_stack` block added
- [ ] Run `pytest tests/` — all tests pass

---

### Task 10 — Step 02 Deep Validator: Tech-stack cross-checks (OPTIONAL)

**File**: `tools/specdev_tools/validation/validators/step_02.py`

**This task is optional for initial rollout.** It adds deeper validation that the schema alone cannot enforce.

> **Before implementing**: Check `tools/specdev_tools/validation/spec_quality_lint.py`. `W574: TECH_STACK_COHERENCE_MISMATCH` already exists and compares Steps 09 and 14 tech_stacks for coherence. Task 10 is a different check (component `type` → `tech_stack` consistency within Step 02), not a duplicate of W574. Use **W606** for the new check.

Add a new function `check_tech_stack_component_consistency`:

```python
def check_tech_stack_component_consistency(
    tech_stack: dict, components: list[dict]
) -> list[SpecError]:
    """Cross-check that infrastructure tech_stack entries match component types.

    Heuristic: if a component has type 'db', 'cache', or 'queue', at least one
    infrastructure tech_stack entry should contain a matching keyword in its name
    (e.g., component type 'db' → infra entries checked for 'postgres', 'mysql',
    'mongo', 'sqlite', 'redis', 'dynamo', 'cassandra', 'db' as substrings).
    Emits W606 if no plausible match is found. This is a best-effort warning
    only — naming is not guaranteed 1:1.
    """
    errors = []
    DB_KEYWORDS = {"postgres", "mysql", "mongo", "sqlite", "db", "dynamo", "cassandra", "rds"}
    CACHE_KEYWORDS = {"redis", "memcache", "cache", "elasticache"}
    QUEUE_KEYWORDS = {"kafka", "sqs", "rabbitmq", "queue", "pubsub", "sns", "event"}
    TYPE_KEYWORDS = {"db": DB_KEYWORDS, "cache": CACHE_KEYWORDS, "queue": QUEUE_KEYWORDS}

    infra_names = {item.get("name", "").lower() for item in tech_stack.get("infrastructure", [])}

    for comp in components:
        ctype = comp.get("type")
        if ctype not in TYPE_KEYWORDS:
            continue
        keywords = TYPE_KEYWORDS[ctype]
        if not any(kw in name for name in infra_names for kw in keywords):
            cid = comp.get("component_id", "<unknown>")
            errors.append(make_error(
                "W606",
                f"TECH_STACK_COMPONENT_TYPE_MISMATCH: component '{cid}' (type: {ctype}) has no "
                f"matching infrastructure entry in tech_stack"
            ))
    return errors
```

Also register **W606** in `tools/specdev_tools/core/errors.py`:
```python
"W606": "TECH_STACK_COMPONENT_TYPE_MISMATCH",
```

Wire it into `validate_step_02()` in the same file:
```python
errors.extend(check_tech_stack_component_consistency(
    instance.get("tech_stack", {}), components
))
```

**Review checklist**:
- [ ] New function follows existing patterns (returns `list[SpecError]`)
- [ ] Uses W606 (W600–W605 are all assigned; W606 is the next available code)
- [ ] W606 registered in `ERROR_CODES` in `tools/specdev_tools/core/errors.py`
- [ ] Does not break existing tests

---

### Task 11 — Step 14 Validator: Also load tech_stack from Step 02

**File**: `tools/specdev_tools/validation/validators/step_14.py`

**Current behavior** (lines 78–95):
- `_load_step09_tech_stack_names()` (line 79) loads from `spec/09_impl_plan.json` → E142 errors
- `_load_step02_component_names()` (line 88) loads **component_id** values from Step 02 → W602 warnings

> **Important context**: The existing W602 check (lines 87–95) compares roadmap tech names against Step 02 **component IDs** (e.g., checking if "TypeScript" is in `{"user-service", "auth-service"}`). This is a conceptually questionable comparison (apples to oranges). The function `_load_step02_component_names()` already exists at line 280 — do NOT confuse it with the new function below which loads **tech_stack** names.

**Change needed**: Add a `_load_step02_tech_stack_names()` function that loads `tech_stack` from `spec/02_system_sketch.json` and validates that Step 14's tech_stack is a superset of Step 02's tech_stack. Use a **new warning code W605** to avoid collision with existing codes (W602 = component-names cross-check, W603 = `FILES_OUTSIDE_TASK_SCOPE`, W604 = `TRACE_MATRIX_STALE`).

**Step 1 — Register W605 in `tools/specdev_tools/core/errors.py`**:

Add to the `ERROR_CODES` dict (after the `W604` entry at line 137):
```python
"W605": "TECH_STACK_02_MISSING",
```

This registration is required before adding the cross-check code below — `make_error("W605", ...)` will raise `ValueError` if the code is not registered.

**Step 2 — Add `_load_step02_tech_stack_names` function** (modeled on `_load_step09_tech_stack_names`, lines 256–277):

```python
def _load_step02_tech_stack_names(toolkit_root: str, artifact_path: str | None) -> set[str]:
    """Load tech_stack names from Step 02 system sketch for cross-ref validation.

    Distinct from _load_step02_component_names() which loads component_id values.
    This function loads technology names from Step 02's tech_stack categories.
    """
    candidates: list[Path] = []
    if artifact_path:
        artifact_dir = Path(artifact_path).resolve().parent
        candidates.append(artifact_dir / "02_system_sketch.json")
    candidates.append(Path(toolkit_root).resolve() / "spec" / "02_system_sketch.json")
    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            continue
        return _collect_tech_names(data.get("tech_stack", {}))
    return set()
```

Add cross-check in `validate_step_14()` after the existing W602 block (after line 95, before the `dependencies` loop at line 96):

```python
# Step 02 tech_stack inheritance check (W605)
step02_tech_names = _load_step02_tech_stack_names(toolkit_root, artifact_path)
if step02_tech_names:
    roadmap_tech_names = _collect_tech_names(instance.get("tech_stack", {}))
    for name in step02_tech_names:
        if name not in roadmap_tech_names:
            errors.append(
                make_error("W605", f"TECH_STACK_02_MISSING: Step 02 declares tech '{name}' but it is absent from roadmap tech_stack")
            )
```

> **Note**: Check if `PROMOTABLE_PAIRS` in `errors.py` needs a corresponding E-code mapping for W605 (likely not needed for initial rollout). Existing W-codes through W604 are all taken: W600=`VERIFIED_ACTION_NO_EVIDENCE`, W601=`EVIDENCE_NO_ARTIFACT_REF`, W602=`TECH_STACK_02_MISMATCH`, W603=`FILES_OUTSIDE_TASK_SCOPE`, W604=`TRACE_MATRIX_STALE`.

**Review checklist**:
- [ ] `"W605": "TECH_STACK_02_MISSING"` added to `ERROR_CODES` dict in `errors.py` (Step 1 — required before the code works)
- [ ] New function is named `_load_step02_tech_stack_names` (distinct from existing `_load_step02_component_names`)
- [ ] New function's docstring explains how it differs from `_load_step02_component_names`
- [ ] Uses **W605** (NOT W602/W603/W604 — all are already assigned to other checks)
- [ ] Cross-check is directional: Step 02 tech_stack entries missing from Step 14 → warning
- [ ] Existing E142 check (Step 09 → Step 14) is NOT modified
- [ ] Existing W602 check (Step 02 component IDs → Step 14) is NOT modified

---

### Task 12 — step_order.json: Update downstream_consumers for Step 02

**File**: `tools/step_order.json`

**Current Step 02 consumers** (lines 69–76):
```json
"02": ["02a", "05", "09", "11", "13", "15"]
```

**New consumers to add**: `"07"`, `"08"`

These steps now extract `tech_stack` from Step 02, making them material consumers.

**Pre-existing gaps found during review**: Multiple steps extract from `02_system_sketch.json` in their prompts but are NOT currently listed in `downstream_consumers["02"]`:

| Step | Extraction level | What it extracts |
|---|---|---|
| **03** (Glossary) | Required | Component names, protocol terms, architectural patterns |
| **04** (FRs) | Should-Extract | Component IDs and trust boundaries |
| **06** (Invariants) | Required | Component IDs, trust boundaries, data flow paths |
| **10** (Governance) | Required | Component boundaries and ownership domains |
| **14** (Roadmap) | Reference | Component architecture for milestone sequencing |
| **16** (Impl Context) | Reference | Component boundaries, trust zones, topology |
| **16a** (Impl Planner) | Reference | Component topology, service boundaries |

These are pre-existing gaps, not introduced by this migration. However, Steps 03, 06, 10, 13, and 14 DO need `tech_stack` extraction updates — see Task 13.

**Change to** (minimum — this migration's new consumers only):
```json
"02": ["02a", "05", "07", "08", "09", "11", "13", "15"]
```

**Change to** (required — includes Task 13's steps 03, 06, 10, 13, 14 which now extract `tech_stack`):
```json
"02": ["02a", "03", "05", "06", "07", "08", "09", "10", "11", "13", "14", "15"]
```

> **Note**: Step 04 uses "Should-Extract" level. Steps 16 and 16a use Step 02 as a "Reference Source" (not Primary). These are excluded from the required update but can be added optionally. Use judgment on whether reference-level extractions warrant DAG inclusion.

> **Caveat**: The `extraction-intent-check` validator checks the REVERSE direction (are all upstream deps in extraction intent?), NOT that extraction intent entries are reflected in `downstream_consumers`. Adding `07`/`08` without updating `step_order.json` would NOT trigger a lint failure. The `step_order.json` update must be verified by manual inspection.

**Review checklist**:
- [ ] Steps `07` and `08` added to Step 02's downstream_consumers
- [ ] Steps `03`, `06`, `10`, `14` also added (required — Task 13 adds `tech_stack` extraction to these prompts)
- [ ] Array is sorted numerically
- [ ] Run `./tools/run_specdev.sh dag-lint --repo-root ./devspec_toolkit` — passes
- [ ] Run `./tools/run_specdev.sh extraction-intent-check --repo-root ./devspec_toolkit` — passes
- [ ] Manually verify: every prompt that extracts from `02_system_sketch.json` has its step listed in `downstream_consumers["02"]`

---

### Task 13 — Prompts: Steps 03, 06, 10, 13, 14 extract `tech_stack` from Step 02

**Why this is in scope**: Step 02 is the source of truth for technology decisions. Downstream steps that don't extract `tech_stack` from Step 02 will generate artifacts blind to technology choices. For example, Step 14's prompt says "copy `tech_stack` from Step 09" without acknowledging Step 02 as the origin, and Step 03 won't include technology names in the glossary even though they're domain vocabulary.

**Files**: `prompts/prompt_03_glossary.md`, `prompts/prompt_06_invariants.md`, `prompts/prompt_10_governance.md`, `prompts/prompt_13_extension_generator.md`, `prompts/prompt_14_roadmap.md`

---

#### Task 13a — prompt_14_roadmap.md (HIGH PRIORITY — validator-enforced)

Step 14 has a validator cross-check (Task 11 / W605) that compares roadmap `tech_stack` against Step 02. If the prompt doesn't instruct the AI to consult Step 02 as the origin, the AI may produce a roadmap `tech_stack` that drifts from Step 02 and triggers W605 warnings in production.

**Change 1**: Extraction Intent, Reference Sources section (line 22):

Current:
```
- **02_system_sketch.json**: Component architecture and subsystem dependencies used to determine milestone sequencing so infrastructure precedes dependent application layers
```

Change to:
```
- **02_system_sketch.json**: Component architecture, subsystem dependencies, and `tech_stack` decisions (Step 02 is the authoritative source for technology choices) used to determine milestone sequencing so infrastructure precedes dependent application layers; the roadmap `tech_stack` must be grounded in Step 02's declarations
```

**Change 2**: Best Practices section (line 94):

Current:
```
- **Reuse Tech Stack**: In most cases, copy the `tech_stack` from `spec/09_impl_plan.json`. Only update it if Step 13 Extensions introduced new mandated tools.
```

Change to:
```
- **Reuse Tech Stack**: Copy the `tech_stack` from `spec/09_impl_plan.json` (Step 09 is a required superset of Step 02's `tech_stack`). Only add entries if Step 13 Extensions introduced new mandated tools. Note: `spec/02_system_sketch.json` is the *origin* of tech stack decisions — Step 09 inherits and may refine them, but MUST NOT remove any Step 02 entries.
```

**Change 3**: Negative Constraints section (line 62):

Current:
```
- **NO Hallucinations**: Do not list technologies not in Step 09/13.
```

Change to:
```
- **NO Hallucinations**: Do not list technologies not in Step 02, Step 09, or Step 13.
```

#### Task 13b — prompt_03_glossary.md

Technology names from `tech_stack` are domain vocabulary (e.g., "PostgreSQL", "FastAPI", "Redis" should be defined in the glossary so downstream steps use consistent terminology).

**Change**: Extraction Intent section (line 18):

Current:
```
- **02_system_sketch.json**: Component names, protocol terms, and architectural patterns for technical vocabulary alignment
```

Change to:
```
- **02_system_sketch.json**: Component names, protocol terms, architectural patterns, and technology names from `tech_stack` (languages, frameworks, infrastructure, tools) for technical vocabulary alignment; technology names are domain terms that downstream specs will reference
```

#### Task 13c — prompt_06_invariants.md

Invariants frequently constrain technology-specific behavior (e.g., "all writes to PostgreSQL must use transactions", "all JWT tokens must use RS256"). Without knowing the tech stack, invariants may be under-scoped.

**Change**: Extraction Intent section (line 23):

Current:
```
- **02_system_sketch.json**: Component IDs, trust boundaries, and data flow paths to scope each invariant to specific components or APIs and derive access boundary rules from architectural separation
```

Change to:
```
- **02_system_sketch.json**: Component IDs, trust boundaries, data flow paths, and `tech_stack` technology decisions to scope each invariant to specific components or APIs, derive access boundary rules from architectural separation, and encode technology-specific constraints (e.g., database transaction guarantees, framework security requirements)
```

#### Task 13d — prompt_10_governance.md

Governance rules are often technology-specific (e.g., "breaking changes to the ORM model require a migration review", "all auth middleware changes require a security reviewer").

**Change**: Extraction Intent section (line 24):

Current:
```
- **02_system_sketch.json**: Component boundaries and ownership domains to map reviewer coverage across system areas and ensure governance rules span all architectural layers
```

Change to:
```
- **02_system_sketch.json**: Component boundaries, ownership domains, and `tech_stack` technology decisions to map reviewer coverage across system areas, ensure governance rules span all architectural layers, and encode technology-specific change-control policies (e.g., database migration gates, framework upgrade procedures)
```

#### Task 13e — prompt_13_extension_generator.md

Extension necessity is directly technology-dependent. A PostgreSQL schema extension is different from a MongoDB schema extension; a FastAPI security extension differs from a Django security extension. Without reading `tech_stack`, the extension generator makes ungrounded technology assumptions.

**Change 1**: Extraction Intent section (line 23):

Current:
```
- **02_system_sketch.json**: Component IDs, subsystem boundaries, and architectural patterns (event sourcing, CQRS, multi-tenancy) evaluated for extension spec necessity
```

Change to:
```
- **02_system_sketch.json**: Component IDs, subsystem boundaries, architectural patterns (event sourcing, CQRS, multi-tenancy), and `tech_stack` technology decisions evaluated for extension spec necessity; technology choices directly determine which extension domains are warranted (e.g., a PostgreSQL choice may require a migrations extension; an ML framework choice may require a model-serving extension)
```

**Change 2**: Note that line 31 references `09_implementation_plan.json` for "Technology stack decisions and milestone structure" — update this to clarify Step 02 is the origin:

Current:
```
- **09_implementation_plan.json**: Technology stack decisions and milestone structure consulted to ensure proposed extensions align with chosen frameworks and implementation sequencing
```

Change to:
```
- **09_implementation_plan.json**: Refined technology stack decisions (superset of Step 02's tech_stack) and milestone structure consulted to ensure proposed extensions align with chosen frameworks and implementation sequencing; Step 02 is the authoritative origin, Step 09 may add version pins or spike-discovered tools
```

**Review checklist**:
- [ ] All 5 prompts updated: `prompt_14_roadmap.md`, `prompt_03_glossary.md`, `prompt_06_invariants.md`, `prompt_10_governance.md`, `prompt_13_extension_generator.md`
- [ ] No duplicate `02_system_sketch.json` entries in any prompt's Extraction Intent (each step has exactly one entry for Step 02)
- [ ] Step 14 Best Practices "copy from Step 09" note retained but updated to reference Step 02 as origin
- [ ] Step 14 Negative Constraints updated to include Step 02 in "No Hallucinations" rule
- [ ] Step 13 (extension generator) correctly identifies Step 02 as origin and Step 09 as refinement

---

## Deferred Items (out of scope for initial rollout)

### D1. Step 09 superset validator (machine enforcement)

The "superset rule" (Step 09 `tech_stack` >= Step 02 `tech_stack`) is enforced by **prompt instructions only** (Task 3c). There is no validator that programmatically loads Step 02's `tech_stack` and checks that all entries are present in Step 09's output.

**Context**: `W574: TECH_STACK_COHERENCE_MISMATCH` already exists in `tools/specdev_tools/validation/spec_quality_lint.py` (`_check_tech_stack_coherence`, lines 221–258). It compares Steps 09 and 14 tech_stacks for coherence. A natural extension would be to also compare Step 02 → Step 09 in the same function (or a sibling check using W607), rather than adding a new validator in `step_09.py`.

**Recommendation**: Extend `_check_tech_stack_coherence` in `spec_quality_lint.py` to also load `spec/02_system_sketch.json` and warn (W607) if any Step 02 tech name is absent from Step 09's `tech_stack`. This is lower priority because:
1. The prompt already enforces this rule (Task 3c)
2. Step 14's validator (Task 11 / W605) catches downstream drift
3. The superset rule is most critical during initial generation, where prompt enforcement is sufficient

### ~~D2. Additional prompt `tech_stack` extraction updates~~ → Resolved as Task 13

Promoted to in-scope. Steps 03, 06, 10, 13, and 14 all need `tech_stack` extraction updates because they generate artifacts that must be grounded in technology decisions. Deferring was incorrect — downstream correctness (not just completeness) depends on this extraction. See Task 13 for the full change manifest.

### D3. Canonical lint awareness

If `tech_stack` entries use `tech_stack_ref` canonical references, the canonical lint/integrity tools (`canonical-lint`, `canonical-integrity`) may need to scan `spec/02_system_sketch.json` for canonical refs in the new `tech_stack` location. Verify this is already handled by the generic canonical ref scanner, or add Step 02 to the scan list.

---

## Execution Order

Tasks have these dependencies:

```
Task 0 (changelog)       ← no deps, do in Batch A
Task 1 (schema)          ← no deps, do first
Task 9 (fixtures)        ← depends on Task 1 (develop in parallel, commit together)
Task 2 (prompt 02)       ← independent of Task 1 (prompt, not schema)
Task 3 (prompt 09)       ← independent
Task 4 (prompt 05)       ← independent
Task 5 (prompt 07)       ← independent
Task 6 (prompt 08)       ← independent
Task 7 (prompt 11)       ← independent
Task 8 (prompt 15)       ← independent
Task 10 (validator 02)   ← depends on Task 1 (optional)
Task 11 (validator 14)   ← independent
Task 12 (step_order)     ← depends on Task 13 (must include 03, 06, 10, 13, 14 in consumers)
Task 13 (prompts 03/06/10/13/14) ← independent
```

**Recommended batches**:
1. **Batch A** (parallel development): Tasks 0, 1, 9, 2, 3, 4, 5, 6, 7, 8, 11, 13
2. **Batch A.5** (after Task 13): Task 12 (step_order must reflect Task 13's new consumers)
3. **Batch B** (optional, after Batch A): Task 10

> **Note**: Task 12 now depends on Task 13. The `step_order.json` update must include Steps 03, 06, 10, 14 as consumers (Task 13 adds `tech_stack` extraction to those prompts). Doing Task 12 before Task 13 would require a second pass to add them.

> **Critical — Atomicity**: Tasks 1 (schema) and 9 (fixtures) MUST be applied in the **same commit**. They can be developed in parallel, but do NOT run `pytest tests/` after applying Task 1 alone — the schema will require `tech_stack` and all 20 invalid fixtures will fail with an unintended second error. Stage both Task 1 and Task 9 changes together before running any test.

---

## Validation After Implementation

Run these in order:

```bash
# 1. Schema validation — all Step 02 fixtures pass
pytest tests/ -k step_02 -v

# 2. Full test suite — no regressions
pytest tests/

# 3. DAG lint — downstream_consumers are consistent
./tools/run_specdev.sh dag-lint --repo-root ./devspec_toolkit

# 3b. Seed lint — seed refs current
./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit

# 3c. Canonical integrity — no canonical drift from new tech_stack fields
./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit

# 4. Extraction intent check — prompts match step_order
./tools/run_specdev.sh extraction-intent-check --repo-root ./devspec_toolkit

# 5. Prompt-schema sync — prompt output contracts match schemas
./tools/run_specdev.sh prompt-sync spec --repo-root ./devspec_toolkit
```

---

## Review Criteria

When reviewing the implementation, verify:

1. **Schema correctness**: `tech_stack` is inside `properties` of the second `allOf` item, NOT floating at the top level
2. **No schema duplication**: Uses `$ref` to `vc:core:collections#techStack`, not a copy. Includes inline `description` on the `$ref` allOf item (matching Step 09's established pattern).
3. **Required enforcement**: `tech_stack` in `required` array AND all 4 categories required via overlay
4. **Prompt consistency**: All prompts that extract from Step 02 mention `tech_stack` in their Extraction Intent. No duplicate `02_system_sketch.json` entries in any prompt's Extraction Intent section.
5. **Ownership clarity**: Step 02 = source of truth, Step 09 = inherit + refine (not generate)
6. **Fixture coverage**: All valid fixtures include `tech_stack`; dedicated `invalid_missing_tech_stack.json` tests missing `tech_stack`
7. **Backward compatibility**: Step 09 schema is NOT changed — it keeps its own `tech_stack` field
8. **Test gates**: `pytest tests/` passes, `dag-lint` passes, `extraction-intent-check` passes
9. **Error codes**: Task 11 uses W605 (new code). W605 is registered in `ERROR_CODES` dict. No reuse of existing codes (W600–W604 are all taken).
10. **DAG consistency**: `step_order.json` downstream_consumers for Step 02 includes all steps whose prompts extract from `02_system_sketch.json`
11. **Invalid fixture completeness**: All 19 invalid fixtures that test component/connection-level errors have valid `tech_stack` added so they don't gain unintended schema failures
12. **Operating Flow header**: `prompt_02_system_sketch.md` line 20 header updated to 5-phase (not just the bullets)
13. **Breaking change**: `changelog/unreleased.md` updated with bullet added under existing `## Breaking Changes` section (no new sub-section header). `changelog/unreleased.yaml` created with two entries (`add_field` + `add_constraint`, both `action: ai_assisted`) — NOT using invalid types `add_required_field` or invalid action `manual_with_guidance`.
14. **Downstream prompt extraction**: All 5 prompts updated in Task 13 mention `tech_stack` in their Step 02 extraction intent. Step 14's "copy from Step 09" best practice references Step 02 as the origin. Step 13 (extension generator) Step 09 extraction clarifies "superset of Step 02". No prompt has duplicate `02_system_sketch.json` entries.
15. **Changelog completeness**: Both `changelog/unreleased.md` (human) and `changelog/unreleased.yaml` (machine spec) updated — not just a single docs/changelog.md entry (which does not exist).
