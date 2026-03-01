# Plan: Generic Seed Templates & Seed Propagation Trim

## Context

**Problem**: The devspec toolkit's seed templates (`seed_overview.md`, `seed_tech_stack.md`) have two structural issues:

1. **Web-app bias** — Templates hardcode web-app concepts (Frontend/Backend/Database layers, WAF/Firewall, Deploy to Dev/Stage/Prod) making them unusable for libraries, frameworks, desktop apps, mobile apps, CLI tools, or embedded systems.

2. **Unnecessary seed propagation** — All 22 pipeline steps are told to read raw seed documents, even though Steps 00–04 already distill all seed content into structured JSON specs. Steps 05+ work entirely from upstream specs and should use the Clarify→Emit protocol for any gaps, not re-read raw seeds.

Additionally, `seed_overview.md` sections 4.2 (NFRs), 4.3 (Security), 7.1–7.3 (Tech/Deployment/Observability) overlap with `seed_tech_stack.md`, creating conflicting sources of truth with no ownership rule.

**Intended outcome**: Generic seed templates that work for any software type, with seed propagation limited to Steps 00–04 only. No new tooling required.

---

## Design Decisions & Philosophy

These decisions were established through analysis and are the rationale behind every task in this plan.

### D1: Pipeline Role Model
The pipeline has a strict information flow. Seeds are human input; the pipeline distills, discovers, and derives from them:
```
Seeds = WHAT and WHY (human-friendly, founder-accessible)
    ↓
Steps 00–04 = DISTILL seeds into structured JSON specs
    ↓
Steps 05–12 = DERIVE technical decisions from structured specs (Clarify→Emit for gaps)
    ↓
Steps 13–16c = IMPLEMENT from structured specs
```
Seeds never flow past Step 04. If Step 07 (NFRs) needs information not captured in upstream specs, it uses the Clarify→Emit protocol to ask the human — it does NOT re-read the raw seed markdown.

### D2: Seed Ownership Boundary
Each seed owns a distinct domain with no overlap:
- **`seed_overview`** owns **product intent**: problem, users, scenarios, success metrics, scope, domain model, timeline, team. Answers: what are we building and why?
- **`seed_tech_stack`** owns **technical decisions**: system type, technology choices, architecture, components, security boundary, distribution, resilience, dependencies. Answers: how will we build it?

Overlapping sections (security, NFRs, deployment, observability, tech preferences) that currently appear in both seeds are removed from `seed_overview` and consolidated into `seed_tech_stack`.

### D3: Seeds Are Not System Specs
Seeds capture design intent and constraints at a level accessible to non-developers. They are NOT meant to be exhaustive system specs. Detailed technical decisions (business rules, API contracts, invariant expressions, test fixtures, threat models) are DISCOVERED by the pipeline steps, not pre-specified in seeds.

The seeds should give the pipeline enough context to ask smart clarifying questions, not enough answers to skip the questions.

### D4: Drop seed_indexer and seed_reviewer from Build Plan
The original optimization plan (`toolkit_optimisation.txt`) proposed `seed_indexer` and `seed_reviewer` modules for the context package. These are redundant:
- The existing seed_manifest system already handles discovery (which seeds exist, which steps need them)
- The pipeline steps (00–04) already distill seeds into structured specs
- seed-lint already validates references, content overlap, and manifest consistency
- No new tooling is needed — the fix is template quality + propagation trimming

### D5: [UNKNOWN] Protocol Replaces Forced Fabrication
Current templates demand "remove all TBDs" which pressures AI (or hurried humans) to invent plausible-sounding details rather than admitting unknowns. The new templates introduce `[UNKNOWN: reason]` as a sanctioned marker. This makes silence explicit, not implicit, and lets seed-lint detect and flag unknowns downstream.

### D6: System-Type Agnostic Templates
Templates must work for ANY software type: web apps, SaaS, libraries, frameworks, CLI tools, mobile apps, desktop apps, embedded systems. This means:
- No hardcoded architecture layers (Frontend/Backend/Database)
- No assumed deployment model (Dev/Stage/Prod servers)
- No web-specific security (WAF/Firewall)
- Examples should span at least 2 different system types

### D7: Cross-Seed Consistency
Removing overlapping sections (D2) addresses the root cause of cross-seed conflicts. A separate cross-seed consistency validator is NOT added in this plan because:
- With no overlapping sections, the surface area for contradiction is minimal
- The cost of building and maintaining the validator exceeds the benefit
- This can be revisited if conflicts are observed in practice

---

## Critical Findings from Inventory

1. **`global_seed_order` in `_collect_required_seeds()`** (seed_lint.py:47–58): Currently unions `global_seed_order` (both seeds) into EVERY step's requirements, regardless of `step_requirements` entries. Even after trimming `step_requirements`, this would still force both seeds on all steps. **Must be fixed.**

2. **`seedRefArray` has `minItems: 1`** (collections.schema.json:427): Steps 05+ with empty `seed_refs: []` would fail schema validation. Must change to `minItems: 0`. Enforcement for Steps 00–04 is handled by seed_lint, not the schema.

3. **`_lint_prompt_manifest_refs()`** (seed_lint.py:61–80): Errors on ANY prompt missing "Seed Order & Mandatory Sources" section. After removing this from Steps 05+ prompts, this function will produce false errors. **Must be made step-aware.**

4. **Prompts 16a, 16b, 16c** have seed_manifest.json references in their body (not just boilerplate) related to manifest management during impl loops. These are about MODIFYING the manifest when adding new seed sources, NOT about reading seeds. **These references must be kept.**

---

## Task Sequence

### Phase 1: Foundation Changes (4 tasks, all parallel, no dependencies)

#### T1: `schema/core/collections.schema.json` — Relax seedRefArray minItems
- **File**: `schema/core/collections.schema.json`
- **Change**: Line 427, change `"minItems": 1` to `"minItems": 0`
- **Rationale**: Allows Steps 05+ to have empty `seed_refs: []`. Steps 00–04 enforcement via seed_lint is unaffected.
- **Risk**: None. Seed_lint is the real enforcer for Steps 00–04. Schema just becomes less restrictive.
- **Subagent**: `general-purpose`, no isolation needed. Single line edit — read line 420–430, edit minItems.

#### T2: `spec/common/seed_manifest.json` — Trim step_requirements
- **File**: `spec/common/seed_manifest.json`
- **Change**: Remove steps 05–16c from `step_requirements` (lines 57–104). Keep only steps 00, 01, 02, 02a, 03, 04.
- **After**:
  ```json
  "step_requirements": {
    "00": ["seed-overview", "seed-tech-stack"],
    "01": ["seed-overview"],
    "02": ["seed-tech-stack"],
    "02a": ["seed-tech-stack"],
    "03": ["seed-overview"],
    "04": ["seed-overview"]
  }
  ```
- **Risk**: Existing spec artifacts for Steps 05+ with populated `seed_refs` still validate (schema allows any valid seedRef; lint just stops enforcing requirements for those steps).
- **Subagent**: `general-purpose`, no isolation needed. Read file, edit step_requirements block.

#### T3: `seed_templates/seed_overview.md` — Generic product intent template
- **File**: `seed_templates/seed_overview.md`
- **Change**: Complete rewrite to remove web-app bias and overlapping technical sections.
- **Sections to KEEP** (with generic language updates):
  - `## 0. Metadata` — as-is
  - `## 1. About This Document` — update purpose to be system-agnostic ("product definition" not "web app definition")
  - `## 2. Problem & Users` — as-is (already generic: problem, personas, scenarios, KPIs)
  - `## 3. Scope` — as-is (already generic: in-scope, out-of-scope, constraints)
  - `## 4. Expected Capabilities` — rename from "Requirements & Quality", keep ONLY 4.1 (high-level behavioral expectations, renamed from "Functional Requirements"). Remove structured format pressure; use plain language.
  - `## 5. Domain Model` — renumber from current §5 (data sources, entities, update strategy)
  - `## 6. Timeline & Milestones` — renumber from current §8
  - `## 7. Team & Process` — renumber from current §9
- **Sections to REMOVE entirely** (belong in tech_stack seed or pipeline discovery):
  - `§4.2 Non-Functional Requirements` → discovered by Step 07
  - `§4.3 Security & Privacy` → discovered by Steps 06, 11
  - `§6. Interfaces & Discovery` → discovered by Steps 02, 05
  - `§7.1 Tech Stack Preferences` → belongs in seed_tech_stack
  - `§7.2 Deployment Environments` → belongs in seed_tech_stack
  - `§7.3 Observability` → belongs in seed_tech_stack
- **Meta-prompt update**: Keep "Product Coach" role. Update self-correction checklist to remove references to removed sections. Add `[UNKNOWN: reason]` protocol instruction.
- **Add "UNKNOWN" protocol**: Instruct that `[UNKNOWN: reason]` is a sanctioned marker for genuinely unknown information. Replace "Did I remove all TBDs?" with "Did I mark unknowns with `[UNKNOWN: reason]` instead of guessing?"
- **Subagent**: `general-purpose`, **isolation: worktree**. Full file rewrite — agent needs to read current file and write new version. Use worktree to safely diff the rewrite.

#### T4: `seed_templates/seed_tech_stack.md` — Generic technical decisions template
- **File**: `seed_templates/seed_tech_stack.md`
- **Change**: Complete rewrite to remove web-app bias and use system-agnostic concepts.
- **New section structure**:
  - `## 0. Metadata` — as-is
  - `## 1. About This Document` — update to "system architecture specification" not "web architecture"
  - `## 2. System Type & Core Technology` — NEW, replaces §2
    - `### 2.1 System Type` — what kind of software? (web app, library, CLI tool, mobile app, desktop app, framework, embedded system, etc.)
    - `### 2.2 Core Technology Decisions` — language, runtime, key libraries with version+rationale. Replace the hardcoded OS/Runtime/Language table with a generic table that works for any system.
    - `### 2.3 Architecture Overview` — replace `Frontend|Backend|Database|Infrastructure|CI/CD` layer table with generic "describe the major parts of your system and how they relate." Examples should cover multiple system types.
  - `## 3. Components` — keep but make generic. Replace hardcoded "Component A/B" with guidance: "list each major part of your system." For a library: modules. For a web app: services. For a mobile app: screens + services.
  - `## 4. Constraints & Boundaries` — replaces §4 "Operations & Security"
    - `### 4.1 Security Boundary` — replace WAF/Firewall with generic "what needs protecting and from what?" Works for network security, API safety, input validation, sandboxing, supply chain.
    - `### 4.2 Distribution & Delivery` — NEW, replaces §7.2 from seed_overview. Generic: how does it reach users? (deploy to server, publish to npm/PyPI, app store, installer download, embed in hardware)
    - `### 4.3 Resilience` — replace Backups & DR with generic "what happens when things fail?" Works for server DR, offline sync, crash recovery, graceful degradation, or N/A for a library.
  - `## 5. Dependencies` — keep as-is (already generic enough: system-level + runtime-level)
  - `## 6. Stack Summary` — replace YAML `stack_index` with a simpler prose/table summary. The YAML was never validated by any tool.
- **Meta-prompt update**: Keep "System Architect" role but remove "SRE" (not all systems need SRE). Update self-correction checklist. Add `[UNKNOWN: reason]` protocol.
- **Examples**: Include at least 2 system types in good/bad examples (one web app, one library or CLI tool).
- **Subagent**: `general-purpose`, **isolation: worktree**. Full file rewrite.

---

### Phase 2: Validation Logic + Prompt Batch 1 (3 tasks, all parallel, depends on Phase 1)

#### T5: `tools/specdev_tools/validation/seed_lint.py` — Make step-aware
- **File**: `tools/specdev_tools/validation/seed_lint.py`
- **Changes**:
  1. **`_collect_required_seeds()` (lines 47–58)**: Add early return of empty set when step_id has no entry in `step_requirements`. `global_seed_order` should only apply to steps that ARE in `step_requirements`. For step "16", check if any of "16a", "16b", "16c" are in step_requirements before applying global.
     ```python
     def _collect_required_seeds(manifest, step_id):
         step_requirements = manifest.get("step_requirements", {})
         if step_id == "16":
             sub_keys = ("16a", "16b", "16c")
             if not any(k in step_requirements for k in sub_keys):
                 return set()
             required = set()
             for key in sub_keys:
                 required.update(step_requirements.get(key, []))
         else:
             if step_id not in step_requirements:
                 return set()
             required = set(step_requirements.get(step_id, []))
         global_required = set(manifest.get("global_seed_order", []))
         required.update(global_required)
         return required
     ```
  2. **`_lint_prompt_manifest_refs()` (lines 61–80)**: Make step-aware. Extract step number from prompt filename. Only enforce "Seed Order & Mandatory Sources" for steps that have entries in `step_requirements`. Steps not in `step_requirements` should NOT be required to have the section. Load step_requirements from the manifest (pass it as parameter or load in function).
     - Extract step from filename: `prompt_05_interface_contracts.md` → `"05"`
     - Steps in step_requirements (00, 01, 02, 02a, 03, 04): enforce section presence
     - Steps NOT in step_requirements: skip enforcement
     - `spec/common/seed_manifest.json` reference check: also make step-aware (only enforce for seed-required steps)
- **Risk**: Must handle edge cases — prompt filenames with letters (02a), step 16 compound, prompts in migration/ subdirectory.
- **Verification**: Run `pytest tests/test_seed_content_overlap.py tests/test_seed_path_validation.py tests/test_seed_strict_mode.py -v` after changes.
- **Subagent**: `general-purpose`, no isolation. Read the file, make targeted edits to the two functions.

#### T6: Prompts Steps 05–10 — Remove seed boilerplate + strengthen Clarify guidance (6 files)
- **Files**:
  - `prompts/prompt_05_interface_contracts.md`
  - `prompts/prompt_06_invariants.md`
  - `prompts/prompt_07_nfrs.md`
  - `prompts/prompt_08_fixtures.md`
  - `prompts/prompt_09_impl_plan.md`
  - `prompts/prompt_10_governance.md`
- **Change A — Seed removal** (mechanical, identical pattern per file):
  1. Remove the `## Seed Order & Mandatory Sources` section (typically 4–5 lines starting with "Read `spec/common/seed_manifest.json` first...")
  2. In `## Context To Ingest` section: remove any lines referencing `docs/seed/seed_overview.md` or `docs/seed/seed_tech_stack.md`
  3. Search for any other `seed_manifest.json` references in the body and remove them (unless they're about manifest management)
  4. **ALSO search for the word "seed" or "seeds"** (case-insensitive) anywhere in the file. Replace semantic references like "from seeds/project policy docs" with references to upstream structured specs (e.g., "from upstream charter constraints and governance specs"). Do NOT remove references that are about the `seed_refs` JSON field itself.
- **Change B — Clarify improvements** (per-file, system-type agnostic):
  - **prompt_05_interface_contracts.md**: Add to Self-Audit Gate gating items:
    - "Access control for each interface is defined, or explicitly marked as open/public with rationale"
    - "If access control rules, permission boundaries, or identity model are unclear from upstream specs, ask Gap Questions — do not assume a model"
  - **prompt_06_invariants.md**: Add to Operating Flow, after "Build a private Context Ledger":
    - "Beyond FR-derived negative cases, consider: data integrity constraints implied by the domain model (glossary entities), state transition rules for entities with lifecycle stages, access boundary rules from system sketch trust boundaries, and ordering guarantees"
    - Add to Self-Audit Gate: "If the glossary defines entities with lifecycle states, verify that state transition invariants exist or ask Gap Questions"
  - **prompt_07_nfrs.md**: Already has "if units/methods/owners or stage are missing, ask Gap Questions." Add:
    - "If measurement_method cannot be practically implemented with the system's actual infrastructure (as defined in upstream specs), ask for the intended measurement approach rather than inventing one"
  - **prompt_08_fixtures.md**: No Clarify changes needed — coverage mandate is already comprehensive.
  - **prompt_09_impl_plan.md**: Replace "from seeds/project policy docs" with "from upstream charter constraints and governance specs." Add to Self-Audit Gate:
    - "If milestone dates, delivery sequencing, or resource constraints cannot be derived from upstream specs, ask Gap Questions — do not invent timeline commitments"
  - **prompt_10_governance.md**: Add to Self-Audit Gate:
    - "If versioning strategy, review process, or release cadence are not derivable from upstream specs, ask Gap Questions for organizational preferences"
- **All Clarify additions must be system-type agnostic** — no references to web-app concepts (servers, endpoints, deployments). Use generic terms: "interfaces" not "APIs", "access control" not "auth", "distribution" not "deployment".
- **DO NOT change**: Extraction Intent sections or coverage closure checks (beyond the additions above).
- **Subagent**: `general-purpose`, no isolation. For each file: read → remove seed sections → add Clarify improvements → verify no web-app-specific language introduced.

#### T7: Prompts Steps 11–15 — Remove seed boilerplate + strengthen Clarify guidance (6 files)
- **Files**:
  - `prompts/prompt_11_redteam.md`
  - `prompts/prompt_12_ci_gates.md`
  - `prompts/prompt_13_extension_generator.md`
  - `prompts/prompt_13a_completeness_assessment.md`
  - `prompts/prompt_14_roadmap.md`
  - `prompts/prompt_15_scaffold.md`
- **Change A — Seed removal**: Same pattern as T6 Change A (including semantic "seed/seeds" word search).
- **Change B — Clarify improvements** (Steps 11–12 only; Steps 13–15 are implementation-phase and less discovery-dependent):
  - **prompt_11_redteam.md**: Add to Self-Audit Gate:
    - "If the system operates in a regulated, high-risk, or domain-specific context not evident from upstream specs, ask about domain-specific threat categories before finalizing"
    - "If the access control model is not fully specified in upstream interface contracts, ask Gap Questions rather than assuming a threat surface"
  - **prompt_12_ci_gates.md**: Add to Self-Audit Gate:
    - "If coverage thresholds or CI runner infrastructure preferences are not derivable from upstream specs, ask Gap Questions — do not assume default thresholds"
  - **prompt_13/13a/14/15**: Seed removal only, no Clarify changes (implementation-phase steps derive mechanically from upstream specs).
- **Subagent**: `general-purpose`, no isolation. Same approach as T6.

---

### Phase 3: Impl-loop Prompts (1 task, depends on Phase 1)

#### T8: Prompts Steps 16–16c — Remove seed boilerplate, preserve manifest management refs (4 files)
- **Files**:
  - `prompts/prompt_16_impl_context.md`
  - `prompts/prompt_16a_impl_planner.md`
  - `prompts/prompt_16b_impl_coder.md`
  - `prompts/prompt_16c_impl_reviewer.md`
- **Change**:
  1. Remove `## Seed Order & Mandatory Sources` section (same as T6/T7)
  2. Remove seed file references from Context To Ingest (same pattern)
  3. **CRITICAL**: These files have additional `seed_manifest.json` references in the body:
     - `prompt_16a_impl_planner.md` lines ~49, 61, 226, 229 — about adding new seeds during impl loop
     - `prompt_16b_impl_coder.md` line ~66 — spec-change rule about manifest
     - `prompt_16c_impl_reviewer.md` line ~90 — spec-change rule about manifest
  4. **KEEP** any reference that is about MODIFYING/MANAGING the manifest (e.g., "if you add a new seed source, update seed_manifest.json"). These are impl-loop infrastructure, not seed reading.
  5. **REMOVE** any reference that is about READING seeds for context (e.g., "ingest required seeds in order before any other context").
- **Subagent**: `general-purpose`, no isolation. Read each file carefully, distinguish management refs from reading refs, edit accordingly.

---

### Phase 4: Tests (2 tasks, parallel, depends on Phase 2)

#### T9: Update existing seed tests for step-aware behavior
- **Files**:
  - `tests/test_seed_content_overlap.py` — verify still passes (uses `step_requirements: {}` in fixtures, unaffected)
  - `tests/test_seed_path_validation.py` — verify still passes
  - `tests/test_seed_strict_mode.py` — verify still passes
  - `tests/integration/test_seed_manifest.py` — verify still passes (fixture has minimal step_requirements)
- **Change**: Run all existing seed tests. If any fail due to the changes in T5, fix them.
- **Verification**: `pytest tests/test_seed_content_overlap.py tests/test_seed_path_validation.py tests/test_seed_strict_mode.py tests/integration/test_seed_manifest.py -v`
- **Subagent**: `general-purpose`, no isolation. Run tests, read failures, fix.

#### T10: Add new regression tests for trimmed seed propagation
- **File**: `tests/test_seed_propagation_trim.py` (NEW)
- **Tests to add**:
  1. `test_steps_00_04_require_seeds`: Create a manifest with step_requirements for 00–04. Create spec artifacts for steps 00–04 with missing seed_refs. Verify seed_lint errors.
  2. `test_steps_05_plus_no_seed_requirement`: Create a manifest with step_requirements only for 00–04. Create spec artifacts for steps 05, 07, 09 with empty seed_refs. Verify seed_lint produces NO errors for those steps.
  3. `test_global_seed_order_only_applies_to_required_steps`: Create a manifest with `global_seed_order: ["seed-overview"]` and `step_requirements: {"00": ["seed-overview"]}`. Create a step 05 artifact with empty seed_refs. Verify no error. Create a step 00 artifact without seed-overview. Verify error.
  4. `test_lint_prompt_refs_step_aware`: Create prompt files for steps 00 (with seed section) and 05 (without seed section). Verify lint only errors on step 00 if missing, not on step 05.
  5. `test_empty_seed_refs_schema_valid`: Validate a step 05 artifact with `"seed_refs": []` against the schema. Verify it passes (after minItems: 0 change).
- **Subagent**: `general-purpose`, no isolation. Read existing test patterns from `tests/test_seed_content_overlap.py` for fixture setup conventions, then write new test file.

---

### Phase 5: Verification of Prompts 00–04 (1 task, depends on T3, T4)

#### T12: Verify Prompts 00–04 extraction descriptions still align with rewritten seeds
- **Files** (read-only verification, edit only if needed):
  - `prompts/prompt_00_project_charter.md`
  - `prompts/prompt_01_capabilities.md`
  - `prompts/prompt_02_system_sketch.md`
  - `prompts/prompt_02a_delivery_baseline.md`
  - `prompts/prompt_03_glossary.md`
  - `prompts/prompt_04_functional_requirements.md`
- **Check**: Each of these prompts describes what to extract from seed files (e.g., `prompt_00` line 80: "Every requirement stated in `docs/seed/seed_overview.md`..."). After the seed template rewrite (T3, T4), verify that:
  1. Extraction descriptions still match the content available in the rewritten seeds
  2. No prompt references a removed seed section by name or content type
  3. Coverage closure statements (e.g., "every requirement in seed_overview is reflected in...") still make sense with fewer seed sections
- **Action**: If any extraction description references content that no longer exists in the rewritten seed (e.g., "NFR targets from seed_overview" — removed in T3), update the prompt to remove that reference.
- **Subagent**: `general-purpose`, no isolation. Read each prompt, compare extraction descriptions against T3/T4 new section structures, edit if misaligned.

---

### Phase 6: Documentation (1 task, depends on all)

#### T11: Update `toolkit_optimisation.txt`
- **File**: `toolkit_optimisation.txt`
- **Change**: Append a new section documenting:
  1. Seed template analysis findings (web-app bias, overlapping sections, hallucination risks)
  2. Design decision: seeds feed Steps 00–04 only, pipeline discovers rest via Clarify→Emit
  3. Design decision: drop seed_indexer and seed_reviewer modules from build plan (redundant with existing pipeline)
  4. Generic seed template design (system-type agnostic)
  5. Updated build plan reflecting these changes
- **Subagent**: `general-purpose`, no isolation. Read current file end, append new section.

---

## Execution Dependency Graph

```
Phase 1 (parallel):  T1  T2  T3  T4
                      │   │   │   │
                      └───┼───┤   │
                          │   │   │
Phase 2 (parallel):  T5  T6  T7  │
                      │   │   │   │
                      │   └───┘   │
Phase 3:             │   T8      │
                      │   │       │
Phase 4 (parallel):  T9  T10     │
                      │   │       │
Phase 5:             │   T12─────┘
                      │   │
Phase 6:             T11──┘
```

- T1, T2, T3, T4: fully independent, run in parallel
- T5: depends on T2 (needs to know final step_requirements shape)
- T6, T7: depend on T1, T2 (conceptual, not blocking — prompts can be edited independently)
- T8: depends on T1, T2 (same as T6/T7, but sequenced after for careful 16a-c handling)
- T9: depends on T5 (tests run against updated seed_lint)
- T10: depends on T1, T2, T5 (tests validate all foundation changes)
- T12: depends on T3, T4 (verifies prompts 00–04 align with rewritten seeds)
- T11: depends on all (documents final state)

## Files Changed — Complete List

| Task | File(s) | Change Type |
|---|---|---|
| T1 | `schema/core/collections.schema.json` | 1-line edit |
| T2 | `spec/common/seed_manifest.json` | Section removal |
| T3 | `seed_templates/seed_overview.md` | Full rewrite |
| T4 | `seed_templates/seed_tech_stack.md` | Full rewrite |
| T5 | `tools/specdev_tools/validation/seed_lint.py` | 2-function edit |
| T6 | 6 prompt files (05–10) | Section removal |
| T7 | 6 prompt files (11–15, 13a) | Section removal |
| T8 | 4 prompt files (16, 16a–16c) | Section removal + careful review |
| T9 | Existing test files (4) | Fix if broken |
| T10 | `tests/test_seed_propagation_trim.py` | New file |
| T11 | `toolkit_optimisation.txt` | Append section |

| T12 | 6 prompt files (00–04, 02a) | Verify + edit if misaligned |

**Total**: 25+ files touched, 1 new file created

## Files NOT Changed (confirmed safe)

- All 19 step schemas (`schema/00_charter.schema.json` through `schema/16_impl_context.schema.json`) — `seed_refs` stays in `required`, schema allows empty array after T1
- `schema/seed_manifest.schema.json` — `step_requirements` allows any number of keys (no minProperties)
- `tools/specdev_tools/cli.py` — seed-lint command dispatch unchanged
- `tools/specdev_tools/validation/docs_lint.py` — reads manifest for docs_policy only
- `tests/test_prompt_contracts.py` — checks `seed_refs` key exists in schemas, still true
- `tests/test_schema_contracts.py` — test fixtures have populated seed_refs, still valid
- `docs/seed/seed_overview.md` and `docs/seed/seed_tech_stack.md` — these are the toolkit's OWN filled-out seeds, not the templates. They are NOT changed in this plan. They were written against the old template structure but remain valid (the templates guide new projects; existing filled-out seeds don't need to conform to the new template structure)

## Explicit Safety Confirmations

1. **W140 content overlap check** (`_check_seed_content_overlap`): Steps 05+ will have empty `seed_refs` after trimming. This function iterates `seed_refs` entries, so empty = no checks = no false positives. Steps 00–04 still have populated `seed_refs` and will continue to be checked. **Safe.**

2. **Existing spec artifacts for Steps 05+**: Projects with existing spec files containing populated `seed_refs` for Steps 05+ will still validate. The schema allows any valid seedRef array; seed_lint just stops enforcing required seeds for those steps. Old specs keep working, new specs can have empty `seed_refs`. **Backward compatible.**

3. **`docs/seed/` filled-out seeds**: The template changes in T3/T4 affect `seed_templates/` (for new projects). The toolkit's own seeds in `docs/seed/` are not touched. If a user wants to realign their existing seeds with the new templates, that's a manual migration — outside this plan's scope.

4. **Prompt 00–04 seed references**: These prompts reference seeds by content type ("for high-level scoping", "for architecture decisions"), not by section number. The content types remain valid after the rewrite. T12 verifies this explicitly and fixes any misalignment.

## Verification Plan

After all tasks complete:

1. **Schema validation**: `pytest tests/test_schema_contracts.py -v` — all step schemas still validate their fixtures
2. **Seed lint**: `pytest tests/test_seed_content_overlap.py tests/test_seed_path_validation.py tests/test_seed_strict_mode.py -v` — existing tests pass
3. **New regression tests**: `pytest tests/test_seed_propagation_trim.py -v` — new tests pass
4. **Integration tests**: `pytest tests/integration/test_seed_manifest.py -v` — manifest validation still works
5. **Full suite**: `pytest tests/ -v` — no regressions across entire test suite
6. **Manual check**: `./tools/run_specdev.sh seed-lint spec --repo-root .` — lint passes on the toolkit's own spec directory

---

## Completion Status

### Phase 1 — T1–T12 (DONE)

| Task | Summary | Status |
|---|---|---|
| T1 | Relaxed `seedRefArray` `minItems` to 0 in `schema/core/collections.schema.json` | DONE |
| T2 | Trimmed `step_requirements` in `spec/common/seed_manifest.json` to steps 00–04 only | DONE |
| T3 | Rewrote `seed_templates/seed_overview.md` to be system-type agnostic | DONE |
| T4 | Rewrote `seed_templates/seed_tech_stack.md` to be system-type agnostic | DONE |
| T5 | Made `seed_lint.py` step-aware (only enforces seed refs for steps 00–04) | DONE |
| T6 | Removed "Seed Order & Mandatory Sources" sections from prompts 05–10 | DONE |
| T7 | Removed "Seed Order & Mandatory Sources" sections from prompts 11–15 (incl. 13a) | DONE |
| T8 | Removed "Seed Order & Mandatory Sources" sections from prompts 16–16c | DONE |
| T9 | Verified existing tests still pass after changes | DONE |
| T10 | Added `tests/test_seed_propagation_trim.py` with 8 regression tests | DONE |
| T11 | Updated `toolkit_optimisation.txt` with seed propagation section | DONE |
| T12 | Verified prompts 00–04 alignment with seed references | DONE |

### Phase 2 — T13–T18: Residual Hallucination Vector Cleanup (DONE)

| Task | Summary | Status |
|---|---|---|
| T13 | Updated Output Contract examples + Self-Audit Gate in prompts 05–10 (seed_refs → `[]`) | DONE |
| T14 | Updated Output Contract examples + Self-Audit Gate in prompts 11–15 (seed_refs → `[]`) | DONE |
| T15 | Updated Output Contract examples + Self-Audit Gate in prompts 16–16c (seed_refs → `[]`) | DONE |
| T16 | Cleared `seed_refs` in `spec/05_interface_contracts.json` (toolkit's own spec artifact) | DONE |
| T17 | Full test suite verification — 523 tests pass, 0 regressions | DONE |
| T18 | Updated this plan document with completion status | DONE |

### Three Hallucination Vectors Fixed (T13–T16)

1. **Output Contract examples** — All 16 prompts (05–16c) now show `"seed_refs": []` instead of populated arrays. AI models will no longer copy populated examples and fabricate seed provenance.
2. **Self-Audit Gate** — Changed from `"seed_refs only contains seeds actually referenced in the output"` to `"seed_refs is [] (this step derives from upstream specs, not seeds)"`. This makes the expected behavior explicit rather than ambiguous.
3. **Spec artifact** — `spec/05_interface_contracts.json` no longer claims seed provenance for a step that doesn't read seeds.

### Intentionally NOT Changed (with rationale)

- **Hardening Protocol "seed coverage" line** — Exact string `"seed coverage are complete"` is enforced by `test_all_prompts_include_hardening_protocol_block` across all prompts. Vacuously true for empty arrays. Changing it risks test breakage for zero benefit.
- **Test fixtures** (`tests/fixtures/step_05/` through `step_16/`) — These have populated `seed_refs` but are test data, not AI-facing. Schema allows both populated and empty arrays. No hallucination risk.
- **19 step schemas** — `seed_refs` stays in `required`. Removing it would be a breaking v0.4.0 change, unnecessary since empty arrays satisfy the constraint.
