# P1-C: Seed Manifest, Config Optimisation & Doc Awareness — Findings

## Summary
- Total findings: 15
- Critical: 0 | High: 3 | Medium: 6 | Low: 4 | Info: 2

---

## Findings

### FINDING-C01: `docs_policy` has zero functional consumers after docs_lint.py removal
- **Severity**: HIGH
- **Category**: CONFIG
- **Location**: `spec/common/seed_manifest.json:58-82`
- **Description**: The `docs_policy` block (25 lines, 7 required fields) has only one remaining consumer: `step_16.py:180` reads `doc_paths` to validate documentation impact paths. The `readme_required`, `root_readme_required`, `readme_depth_default`, `readme_depth_by_scope`, `scope`, and `exclusions` fields have zero consumers. The `docs_lint.py` module that consumed these was removed in the prior tool audit.
- **Evidence**:
  - `tools/specdev_tools/validation/validators/step_16.py:180`: `doc_patterns = manifest.get("docs_policy", {}).get("doc_paths", []) or []`
  - `tools/specdev_tools/validation/validators/step_16.py:183`: Warning when `doc_paths` is missing
  - No other file in `tools/specdev_tools/` references `readme_required`, `readme_depth_default`, `scope`, or `exclusions` from `docs_policy`
- **Recommendation**: Extract `doc_paths` into a top-level `doc_paths` field in seed_manifest.json (3 lines vs 25). Remove the entire `docs_policy` block and its schema definition. Update `step_16.py:180` to read from the new location. Remove `docs_policy` from `schema/seed_manifest.schema.json:115-169` and from `required` array. Saves ~22 lines of dead config + ~55 lines of dead schema.

### FINDING-C02: `nested_order` provides zero information beyond `global_seed_order`
- **Severity**: MEDIUM
- **Category**: CONFIG
- **Location**: `spec/common/seed_manifest.json:11-19`
- **Description**: `nested_order` has a single entry ("foundation") containing the same 2 seeds as `global_seed_order`. It has exactly one consumer: `seed_lint.py:261-264` validates referential integrity of seed IDs within layers. This validation is redundant with the `global_seed_order` check at lines 257-259. The prior schema audit (FIX-063, FIX-076) already decided to remove this.
- **Evidence**:
  - `seed_lint.py:261-264`: `for layer in manifest.get("nested_order", []): for sid in layer.get("seed_ids", []): ...`
  - Single layer "foundation" with `["seed-overview", "seed-tech-stack"]` — identical to `global_seed_order`
  - Prior schema audit decision D5: "Remove entirely. Redundant with global_seed_order."
- **Recommendation**: Execute the already-decided removal (FIX-063): delete `nested_order` from data, schema properties, and the `seed_lint.py` consumer. This was approved but not yet executed.

### FINDING-C03: `step_requirements` covers only steps 00-04; steps 05-16c have no seed requirements
- **Severity**: MEDIUM
- **Category**: CONFIG
- **Location**: `spec/common/seed_manifest.json:37-56`
- **Description**: `step_requirements` maps seeds to steps 00, 01, 02, 02a, 03, 04. Steps 05-16c have no entries. However, `_collect_required_seeds()` in `seed_lint.py:48-63` returns empty set for unmapped steps, so seed_lint silently skips them. The "Seed Order & Mandatory Sources" section appears only in prompts 00-04 (6 of 22 prompts), matching the data — but the question is whether later steps should reference seeds.
- **Evidence**:
  - `seed_lint.py:58-59`: `if step_id not in step_requirements: return set()` — steps 05+ are silently skipped
  - Prompts 05-16c have no "Seed Order" section and no `seed_manifest.json` reference
  - Step 09's `tech_stack` field is populated from upstream specs, not directly from seeds
- **Recommendation**: The current design is intentional: seeds feed steps 00-04 which formalize the seed content into structured specs. Steps 05+ consume only those structured specs. Do NOT expand `step_requirements` to later steps. However, document this design decision explicitly in `seed_manifest.schema.json` description for `step_requirements`: "Only early pipeline steps (00-04) ingest raw seed documents. Later steps consume the structured spec artifacts produced by these steps."

### FINDING-C04: `allowed_upstream_dependencies` is fully derivable from `steps` array
- **Severity**: HIGH
- **Category**: CONFIG
- **Location**: `tools/step_order.json:41-315` (~275 lines)
- **Description**: Under `strict_waterfall` policy, `allowed_upstream_dependencies[N]` is always `steps[0..indexOf(N)-1]` — every step before N in the array. This is pure redundancy: 275 lines of data that can be computed by a 3-line function. The data has 5 consumers: `cli.py:1039`, `hallucination_lint.py:324`, `extraction_intent_check.py:57`, `dependency_order_lint.py:60`, `dag_lint.py:56`.
- **Evidence**:
  - Step "04" lists `["00", "01", "02", "02a", "03"]` — exactly the first 5 entries of `steps`
  - Step "16c" lists all 21 preceding steps — exactly `steps[0:21]`
  - Pattern holds for all 22 steps with zero exceptions
  - Derivation function: `def allowed_upstream(steps, step_id): idx = steps.index(step_id); return steps[:idx]`
- **Recommendation**: Add a `derive_allowed_upstream(step_id)` function to a shared utility (e.g., `core/constants.py` or a new `core/step_order.py`). Migrate all 5 consumers to call the function instead of reading the JSON key. Remove `allowed_upstream_dependencies` from `step_order.json` (saves ~275 lines). Keep the function as the single source of truth. Add a note in `step_order.json._notes` explaining the derivation. Update `schema/step_order.schema.json` to make the field optional/deprecated.

### FINDING-C05: `coverage_thresholds` is well-consumed and correctly located
- **Severity**: INFO
- **Category**: CONFIG
- **Location**: `tools/step_order.json:317-320`
- **Description**: `coverage_thresholds` has 2 consumers (`matrix.py:308-357`, `cli.py:1095-1159`) and enforces FR coverage with configurable warn/error modes. The prior schema audit confirmed its location is appropriate (AUDIT-059). It is a small, stable config block (4 lines) that governs cross-step traceability behavior.
- **Evidence**:
  - `matrix.py:308`: `_check_coverage_thresholds()` loads thresholds, checks percentage, emits W592/E592
  - `matrix.py:343`: `_load_coverage_thresholds()` gracefully handles missing key with `_MISSING_FILE` sentinel
  - `cli.py:1095-1159`: Loads and passes to matrix generation
- **Recommendation**: No change needed. This is correctly placed and well-consumed.

### FINDING-C06: `downstream_consumers` is curated, not derivable, and serves 3 distinct use cases
- **Severity**: INFO
- **Category**: CONFIG
- **Location**: `tools/step_order.json:321-344`
- **Description**: `downstream_consumers` is manually curated to capture actual (not theoretical) data flow between steps. It differs from the inverse of `allowed_upstream_dependencies` because not all allowed upstream steps are actually consumed. It has 3 consumers: `cli.py:1047-1048` (prompt-context command), `dag_lint.py:55-112` (DAG consistency checks), `forward_replay_check.py:377` (change propagation). Each prompt's header says "Run `specdev prompt-context NN`", making this data user-facing.
- **Evidence**:
  - Step 00 has `allowed_upstream_dependencies: []` but `downstream_consumers: ["01","03","04","07","09","10","13a","14"]` — curated, not derivable
  - `dag_lint.py:66-77`: validates bidirectional consistency between `downstream_consumers` and `allowed_upstream_dependencies`
  - Every prompt header references `prompt-context` command
- **Recommendation**: Keep `downstream_consumers`. It provides curated knowledge about actual data flow that cannot be derived. The `prompt-context` utility is referenced in all 22 prompts and provides actionable context to AI agents. However, if `allowed_upstream_dependencies` is removed (FINDING-C04), update `dag_lint.py` to use the derivation function for consistency checks.

### FINDING-C07: Seed Order, Context To Ingest, and Extraction Intent overlap significantly in steps 00-04
- **Severity**: HIGH
- **Category**: CONFIG
- **Location**: `prompts/prompt_00_project_charter.md:39-55`, similar in prompts 01-04
- **Description**: Steps 00-04 have three sections with overlapping content: (1) **Seed Order & Mandatory Sources** (6/22 prompts) — tells AI to read seed_manifest.json; (2) **Context To Ingest** (6/22 prompts) — lists the same seed docs plus upstream specs; (3) **Extraction Intent** (22/22 prompts) — repeats the same seed docs with extraction details. The seed docs appear in all three sections, creating triple redundancy.
- **Evidence**:
  - Prompt 00: Seed Order says "read seed_manifest.json, follow global_seed_order and step_requirements['00']"
  - Context To Ingest says "Primary Source: docs/seed/seed_overview.md" and "Constraints Source: docs/seed/seed_tech_stack.md"
  - Extraction Intent says "docs/seed/seed_overview.md: Project scope boundaries..." and "docs/seed/seed_tech_stack.md: Hardware/legacy constraints..."
  - Same pattern in prompts 01, 02, 02a, 03, 04
  - Steps 05-16c have only Extraction Intent (no Seed Order, no Context To Ingest as separate section)
- **Recommendation**: Merge "Seed Order & Mandatory Sources" and "Context To Ingest" into the Extraction Intent section for steps 00-04. Add a single line at the top of Extraction Intent: "Read `spec/common/seed_manifest.json` first; ingest seeds in `step_requirements['NN']` order before other context. If a required seed is missing, stop and request it." This eliminates ~12 lines per prompt (72 lines total across 6 prompts) while preserving all information in one place.

### FINDING-C08: `_collect_required_seeds` unions `global_seed_order` into ALL mapped steps
- **Severity**: MEDIUM
- **Category**: CONFIG
- **Location**: `tools/specdev_tools/validation/seed_lint.py:61-62`
- **Description**: `_collect_required_seeds()` unconditionally unions `global_seed_order` (both seeds) into every step that has a `step_requirements` entry. This means step 01 (which only needs `seed-overview` per `step_requirements`) also requires `seed-tech-stack` via `global_seed_order`. The `global_seed_order` field is meant to define ingestion ordering, not to force all seeds on all steps. This contradicts the selective mapping in `step_requirements`.
- **Evidence**:
  - `seed_lint.py:61-62`: `global_required = set(manifest.get("global_seed_order", [])); required.update(global_required)`
  - `step_requirements["01"]` = `["seed-overview"]` — but `_collect_required_seeds("01")` returns `{"seed-overview", "seed-tech-stack"}`
  - The `WIP/trans/seed_update_plan.md:73` already identifies this as a bug: "Must be fixed"
- **Recommendation**: Change `_collect_required_seeds()` to use `global_seed_order` only for ordering, not for expanding requirements. The function should return only the seeds listed in `step_requirements[step_id]`, using `global_seed_order` to sort them. This is a semantic bug where ordering was conflated with requirements.

### FINDING-C09: 46 of 53 docs are never referenced by any prompt
- **Severity**: MEDIUM
- **Category**: CONFIG
- **Location**: `docs/**/*.md` (53 files), `prompts/prompt_*.md` (22 files)
- **Description**: Only 7 docs are referenced by prompts: `docs/prompts/shared_expectations.md` (8 prompts), `docs/developers/reference.md` (1 prompt), `docs/seed/seed_overview.md` (4 prompts via seed system), `docs/seed/seed_tech_stack.md` (4 prompts via seed system). The remaining 46+ docs (audit findings, developer guides, workflow guides, architecture docs, ops docs, tooling docs) are never referenced and invisible to AI agents during spec generation.
- **Evidence**:
  - Docs referenced by prompts: `shared_expectations.md`, `reference.md`, `seed_overview.md`, `seed_tech_stack.md`
  - Docs never referenced: `docs/developers/getting_started.md`, `docs/developers/error-codes.md`, `docs/developers/path_conventions.md`, `docs/developers/extension_schemas.md`, `docs/architecture/governance_architecture.md`, `docs/ops/toolkit_update_checklist.md`, all `docs/audit/` files, all `docs/developers/workflows/` files, all `docs/developers/tools/` files, `docs/developers/tooling/` files
  - No lazy-loading mechanism exists to surface relevant docs to agents at runtime
- **Recommendation**: Implement a doc-awareness mechanism with two parts:
  1. Add a `doc_refs` field to `step_requirements` or a new `step_docs` map in `step_order.json` that maps step IDs to relevant doc paths. E.g., step 10 (governance) should reference `docs/architecture/governance_architecture.md`; step 12 (CI gates) should reference `docs/developers/workflows/` guides.
  2. Have prompts include a line: "Optional context: run `specdev doc-context NN` for relevant developer docs." This is lazy-loading — agents fetch docs only when needed, saving tokens.

### FINDING-C10: No validator enforces tech_stack consistency across the pipeline
- **Severity**: MEDIUM
- **Category**: CONFIG
- **Location**: `prompts/prompt_09_impl_plan.md:53-54`, `prompts/prompt_14_roadmap.md:55`
- **Description**: Tech stack flows through: `seed_tech_stack.md` → Step 02 (system sketch) → Step 09 (impl plan `tech_stack` field) → Step 14 (roadmap `tech_stack`). Each step re-declares tech choices with no automated consistency check. Step 09's prompt says "Cross-Check: Verify your tech_stack selection against spec/01_capabilities.json" but does NOT reference `seed_tech_stack.md` or `spec/02_system_sketch.json` for tech_stack alignment. Step 14 says "Technology stack copied from Step 09" but no validator enforces this.
- **Evidence**:
  - `prompt_09_impl_plan.md:54`: Cross-check is against `01_capabilities.json`, not against `02_system_sketch.json` tech choices or `seed_tech_stack.md`
  - Grep for `tech_stack.*consistency` in `tools/specdev_tools/`: 0 matches
  - No validator in `tools/specdev_tools/validation/` checks tech_stack alignment between steps 02, 09, 14
  - Step 02 extraction intent includes `seed_tech_stack.md` for "technology constraints", Step 09 does NOT reference `seed_tech_stack.md` at all
- **Recommendation**: Two actions:
  1. Update Step 09's extraction intent to include: "**02_system_sketch.json**: Component technology choices and architecture patterns for tech_stack alignment validation" — currently missing.
  2. Consider adding a `tech-stack-lint` command or integrating into `spec-quality-lint` that verifies: (a) Step 09 `tech_stack` entries align with Step 02 component technologies, (b) Step 14 `tech_stack` matches Step 09, (c) No technology introduced in Step 09 contradicts `seed_tech_stack.md` constraints.

### FINDING-C11: `prompt-context` utility is referenced in all 22 prompts but has narrow code footprint
- **Severity**: LOW
- **Category**: CONFIG
- **Location**: `tools/specdev_tools/cli.py:1023-1072`
- **Description**: `specdev prompt-context NN` is a simple lookup command (~50 lines) that reads `downstream_consumers` from `step_order.json` and prints a table. It is referenced in the first line of every prompt ("Run `specdev prompt-context NN` to see downstream consumers"). It has 3 code consumers: `cli.py` (the command itself), `dag_lint.py` (validates the underlying data), `forward_replay_check.py` (uses `downstream_consumers` for change propagation). The utility provides genuine value for AI agent context orientation.
- **Evidence**:
  - All 22 prompts: "Run `specdev prompt-context NN` to see downstream consumers. This prompt's output feeds N downstream steps."
  - `cli.py:1023-1072`: Simple implementation using `downstream_consumers` lookup
  - `forward_replay_check.py:377`: `data.get("downstream_consumers", {}).get(step, [])`
- **Recommendation**: Keep `prompt-context`. It is lightweight, referenced universally, and provides actionable context about impact scope. Consider enhancing it to also show required upstream inputs (inverse of `downstream_consumers`) to give agents a complete picture of both "what feeds this step" and "what this step feeds."

### FINDING-C12: `seed_manifest.json` and `step_order.json` have overlapping scope concerns
- **Severity**: LOW
- **Category**: CONFIG
- **Location**: `spec/common/seed_manifest.json` (entire file), `tools/step_order.json` (entire file)
- **Description**: Both files configure per-step behavior: `seed_manifest.json.step_requirements` maps steps to seeds, while `step_order.json` maps steps to dependencies, consumers, and thresholds. The boundary is logical (seed_manifest = seed ingestion config, step_order = pipeline topology), but when `docs_policy` and `nested_order` are removed (FINDING-C01, C02), seed_manifest reduces to just `seeds[]`, `global_seed_order`, and `step_requirements` — a very small file. The question is whether `step_requirements` should migrate to `step_order.json`.
- **Evidence**:
  - After removing `docs_policy` (25 lines) and `nested_order` (9 lines), seed_manifest shrinks from 83 lines to ~49 lines
  - `step_requirements` is consumed by `seed_lint.py` only
  - `step_order.json` already has per-step maps (`allowed_upstream_dependencies`, `downstream_consumers`)
- **Recommendation**: Keep `seed_manifest.json` as a separate file. It lives in `spec/common/` (product-side) while `step_order.json` lives in `tools/` (toolkit-side). This separation allows different products to have different seed configurations while sharing the same pipeline topology. Moving `step_requirements` to `step_order.json` would couple product-specific seed configuration to toolkit infrastructure.

### FINDING-C13: Step 09 extraction intent omits Step 02 system_sketch for tech_stack alignment
- **Severity**: MEDIUM
- **Category**: CONFIG
- **Location**: `prompts/prompt_09_impl_plan.md:43`
- **Description**: Step 09's extraction intent lists Step 02 as: "Component IDs, component status (active vs deprecated), and inter-component data flows to inform architecture decisions and trigger migration plan requirements." It does NOT mention extracting technology choices from Step 02 components for alignment with the `tech_stack` field. Yet Step 02's system_sketch contains the initial architecture technology decisions from `seed_tech_stack.md`. This creates a gap: Step 09 derives its `tech_stack` without cross-checking against the authoritative architecture decisions made in Step 02.
- **Evidence**:
  - `prompt_09_impl_plan.md:43`: "02_system_sketch.json: Component IDs, component status..." — no mention of technology choices
  - `prompt_09_impl_plan.md:54`: Cross-check is against `01_capabilities.json`, not Step 02
  - `prompt_02_system_sketch.md:52`: "docs/seed/seed_tech_stack.md: Architecture patterns, technology constraints" — Step 02 ingests seed tech stack
  - Step 09 never references `seed_tech_stack.md` directly
- **Recommendation**: Update Step 09's extraction intent for `02_system_sketch.json` to: "Component IDs, technology choices per component, architecture patterns, component status, and inter-component data flows to align tech_stack selections with established architecture decisions and trigger migration plan requirements."

### FINDING-C14: `global_seed_order` conflates ordering with membership semantics
- **Severity**: LOW
- **Category**: CONFIG
- **Location**: `spec/common/seed_manifest.json:7-10`, `tools/specdev_tools/validation/seed_lint.py:61-62`
- **Description**: `global_seed_order` serves dual purposes: (1) defines the ingestion order for seeds, (2) implicitly defines mandatory membership (via `_collect_required_seeds` which unions it into every mapped step's requirements). The prompts say "follow `global_seed_order`" (ordering), but the code treats it as "require all seeds listed in `global_seed_order`" (membership). With only 2 seeds this causes no visible problem, but semantically the name implies ordering, not requirement expansion.
- **Evidence**:
  - Prompt 00: "follow `global_seed_order` and `step_requirements['00']`" — ordering instruction
  - `seed_lint.py:61`: `global_required = set(manifest.get("global_seed_order", []))` — treated as required set
  - `seed_lint.py:62`: `required.update(global_required)` — expands step requirements with all global seeds
- **Recommendation**: Rename to `seed_ingestion_order` to clarify it is about ordering, and stop using it to expand requirements. Requirements should come solely from `step_requirements`. See also FINDING-C08.

### FINDING-C15: Doc-awareness gap — high-value docs unmapped to relevant steps
- **Severity**: LOW
- **Category**: CONFIG
- **Location**: `docs/**/*.md` (53 files)
- **Description**: Several docs would provide high value to specific steps but are never surfaced. This is a curated assessment of the most impactful gaps.
- **Evidence**:
  - `docs/architecture/governance_architecture.md` — valuable for Step 10 (Governance) and Step 12 (CI Gates)
  - `docs/developers/error-codes.md` — valuable for Step 16b (Impl Coder) and Step 16c (Impl Reviewer) to understand validation errors
  - `docs/developers/path_conventions.md` — valuable for Step 15 (Scaffold) to ensure generated paths follow conventions
  - `docs/developers/extension_schemas.md` — valuable for Step 13 (Extension Generator)
  - `docs/developers/workflows/spec_to_impl.md` — valuable for Steps 16a-16c (Implementation Trinity)
  - `docs/ops/toolkit_update_checklist.md` — valuable for Step 16a (Impl Planner) when planning toolkit integration tasks
  - `docs/developers/workflows/discovery.md` — valuable for Steps 00-04 (Discovery phase)
- **Recommendation**: Create a `step_docs` map (either in `step_order.json` or a new `tools/doc_map.json`) that associates relevant docs with each step. Surface these via an enhanced `prompt-context` command or a new `doc-context` command. This implements lazy-loading: agents fetch docs only when executing a specific step, avoiding token waste from loading all 53 docs upfront.

---

## Answers to Specific Questions

### Q1: For each field in seed_manifest.json — who reads it? What happens if removed?

| Field | Consumers | Impact if removed |
|---|---|---|
| `seed_manifest_id` | Schema validation only | Safe to remove from required; no runtime consumer |
| `version` | Schema validation only | Safe to remove from required; no runtime consumer |
| `created_at` | Schema validation only | Safe to remove from required; no runtime consumer |
| `last_updated` | Schema validation only | Safe to remove from required; no runtime consumer |
| `global_seed_order` | `seed_lint.py:61,257-259`; prompts 00-04 | Breaking — used for seed requirement expansion and referential integrity |
| `nested_order` | `seed_lint.py:261-264` | Non-breaking — gracefully handled via `.get("nested_order", [])` |
| `seeds` | `seed_lint.py:227-254` (path validation, integrity) | Breaking — core seed registry |
| `step_requirements` | `seed_lint.py:48-63,266-269`; CLAUDE.md; prompts 00-04 | Breaking — drives per-step seed validation |
| `docs_policy` | `step_16.py:180` (only `doc_paths` sub-field) | Mostly non-breaking — only `doc_paths` is used; 6 of 7 sub-fields are dead |

### Q2: Can `allowed_upstream_dependencies` be replaced by a derivation function?

Yes. Under `strict_waterfall` policy: `allowed_upstream(steps, step_id) = steps[:steps.index(step_id)]`. This is a 1-line function that produces identical output for all 22 steps. See FINDING-C04.

### Q3: What is the overlap between Seed Order, Context To Ingest, and Extraction Intent?

In steps 00-04, seed documents appear in all three sections:
- **Seed Order**: "Read seed_manifest.json, follow global_seed_order and step_requirements" (3 lines)
- **Context To Ingest**: "Primary Source: docs/seed/seed_overview.md" + other sources (4-6 lines)
- **Extraction Intent**: "docs/seed/seed_overview.md: [extraction details]" (2-4 lines)

Seed docs are mentioned 3 times each. Steps 05-16c have only Extraction Intent — no redundancy. Merging would save ~72 lines across 6 prompts. See FINDING-C07.

### Q4: Which of the 46 unreferenced docs would be valuable to which steps?

See FINDING-C15 for the curated list. Top 7 high-value mappings:
- Step 10: `governance_architecture.md`
- Step 12: `governance_architecture.md`
- Step 13: `extension_schemas.md`
- Step 15: `path_conventions.md`
- Steps 16a-16c: `spec_to_impl.md`, `error-codes.md`
- Steps 00-04: `discovery.md`

### Q5: Can seed_manifest's `step_requirements` be expanded for doc references per step?

Technically yes, but it conflates two concerns (seed ingestion vs doc awareness). Better to create a separate `step_docs` map in `step_order.json` or `tools/doc_map.json`. See FINDING-C09.

### Q6: Is there a validator ensuring Step 09 tech_stack consistency with Step 02?

No. Zero validators check tech_stack consistency across steps 02, 09, 14. See FINDING-C10. The only cross-check is a prompt instruction (Step 09 says "verify against 01_capabilities.json") but this checks capabilities, not architecture technology decisions.

### Q7: Is prompt-context useful enough to justify downstream_consumers data?

Yes. `prompt-context` is referenced in all 22 prompts, has a clean implementation, and `downstream_consumers` additionally serves `dag_lint.py` (consistency validation) and `forward_replay_check.py` (change propagation). The data is curated (not derivable) and captures actual data flow. See FINDING-C06 and FINDING-C11.
