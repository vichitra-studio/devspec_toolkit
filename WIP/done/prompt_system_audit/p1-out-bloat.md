# P1-A: Prompt Bloat & Shared Expectations — Findings

**Date**: 2026-03-20
**Analyst**: P1-A agent
**Scope**: User points #3, #7, #8, #10 — shared section extraction, Coverage Gap Reporting, Quick Reference, Metadata Contract, Output Rules, Canonical Registry

---

## Summary
- Total findings: 12
- Critical: 0 | High: 4 | Medium: 5 | Low: 2 | Info: 1

---

## Findings

### FINDING-001: Hardening Protocol is 100% identical across 22 prompts and extractable
- **Severity**: HIGH
- **Category**: BLOAT
- **Location**: All 22 prompts at `## Hardening Protocol` (e.g., `prompts/prompt_00_project_charter.md:163`)
- **Description**: The Hardening Protocol section is verified identical (md5 match) across all 22 prompts. It occupies 6 lines per file = 132 LOC total. It contains zero step-specific content. It can be moved entirely to `shared_expectations.md` with no information loss.
- **Evidence**: Four bullet points are generic:
  - fail-closed preflight
  - No-Invention Rules
  - Completeness Closure
  - blocker report
  These are already semantically covered by shared_expectations.md's "one-go Quality Protocol (fail-closed)" section, which contains the same concepts (preflight, evidence ledger, completeness closure, fail-closed blockers). The Hardening Protocol is a more concise restatement.
- **Recommendation**: Move Hardening Protocol to `shared_expectations.md` as a new section. Replace inline copies in all 22 prompts with a reference: `See shared_expectations.md § Hardening Protocol`. Alternatively, merge it into the existing "one-go Quality Protocol" section since they overlap substantially. **Projected savings: 132 LOC.**

### FINDING-002: Canonical Registry section is extractable; step 12 variant is meaningful but reconcilable
- **Severity**: HIGH
- **Category**: BLOAT
- **Location**: All 22 prompts at `## Canonical Registry (Required Input)` (e.g., `prompts/prompt_12_ci_gates.md:163`)
- **Description**: 21/22 prompts share an identical 5-line Canonical Registry section. Step 12 has a meaningfully different variant that is more prescriptive: it uses a bullet-point format with 8 items including explicit instructions about `preferred_label`, `temp_id` fields, deprecated canonical checking, and `replaced_by`. The standard version uses a numbered list with 4 items.
- **Evidence**:
  - Standard (21 prompts): "Before generating output, you MUST load and search... Use this registry to: 1. Bind `*_ref` fields... 2. Resolve aliases... 3. Propose new entries... 4. Flag conflicts..."
  - Step 12 variant: "- Load `canon/manifest.json`... - For every semantic field you populate, search the manifest for a matching entry by `kind` + `preferred_label` or alias. - If a match exists: populate... - If no match: add entry to `canonical_proposals` with `temp_id`, `kind`, `proposed_label`, `definition`, and `source_field`. - NEVER leave a `*_ref` field empty... - NEVER use a deprecated canonical without checking `replaced_by` first."
- **Analysis**: The step 12 variant is NOT a copy error. It adds two valuable rules not in the standard version: (1) deprecated canonical checking with `replaced_by`, (2) explicit `temp_id`/`proposed_label`/`definition`/`source_field` fields for proposals. These rules SHOULD apply to all prompts.
- **Recommendation**: Merge the step 12 variant's additional rules into the standard version, then extract the unified section to `shared_expectations.md`. The merged version should include both the numbered workflow (standard) and the NEVER rules (step 12). **Projected savings: 154 LOC** (7 lines x 22 prompts).

### FINDING-003: Canonical Binding Rules are 100% identical across 22 prompts and extractable
- **Severity**: HIGH
- **Category**: BLOAT
- **Location**: All 22 prompts at `## Canonical Binding Rules` (e.g., `prompts/prompt_00_project_charter.md:176`)
- **Description**: The Canonical Binding Rules section is verified identical across all 22 prompts. It occupies 6 lines per file = 132 LOC total. Zero step-specific content. Can be fully extracted to `shared_expectations.md`.
- **Evidence**: Four numbered rules: (1) canonical_refs_used REQUIRED, (2) canonical_proposals OPTIONAL, (3) canonical_conflicts OPTIONAL, (4) *_ref fields MUST be populated.
- **Recommendation**: Move to `shared_expectations.md` alongside the Canonical Registry section. **Projected savings: 132 LOC.**

### FINDING-004: Schema Authority + Path Variables are 100% identical across 22 prompts and extractable
- **Severity**: HIGH
- **Category**: BLOAT
- **Location**: All 22 prompts at `## Schema Authority` and `## Path Variables` (e.g., `prompts/prompt_00_project_charter.md:5-18`)
- **Description**: Schema Authority (7 lines) and Path Variables (8 lines) are verified identical across all 22 prompts except for the step-specific schema filename in Schema Authority line 1. The schema filename is already stated in the Schema Reference section, making the inline mention redundant.
- **Evidence**: Schema Authority text: "The schema at `schema/{NN}_{name}.schema.json` is the authoritative source for all field definitions..." — only the filename differs. Path Variables table is byte-identical.
- **Recommendation**: Extract the generic Schema Authority text (with a `{STEP_SCHEMA}` placeholder filled by Schema Reference) and Path Variables table to `shared_expectations.md`. Each prompt retains only its Schema Reference section (which already exists). **Projected savings: ~286 LOC** (13 lines x 22 prompts, minus 1 line per prompt for the schema path reference = ~264 LOC net). However, Schema Authority contains a critical "MUST read the schema before generating output" instruction that benefits from proximity to the prompt header. A compromise: extract Path Variables (176 LOC savings), keep Schema Authority inline but template it.

### FINDING-005: Coverage Closure has no validator enforcement — purely prompt-driven
- **Severity**: MEDIUM
- **Category**: BLOAT
- **Location**: All 22 prompts at `### Coverage Closure` subsection within Self-Audit Gate
- **Description**: Coverage Closure appears in all 22 prompts as an H3 under Self-Audit Gate. It contains two parts: (A) step-specific coverage checks (unique per prompt) and (B) a generic 3-item checklist that is identical across all 22 prompts. Neither "Coverage Closure" nor "Self-Audit Gate" is consumed by any validator in `tools/specdev_tools/`. No Python code in the tooling references "coverage closure", "self-audit", or "score < 0.9".
- **Evidence**:
  - `grep -r "Coverage Closure\|coverage.closure\|Coverage Gap" tools/` returns zero matches.
  - `grep -r "Self-Audit\|self.audit\|score.*0\.9" tools/` returns zero matches.
  - The generic 3-item checklist (identical in all 22):
    ```
    - [ ] Every upstream ID from ingested context has been consumed
    - [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
    - [ ] All required fields populated from actual upstream data (not hallucinated)
    ```
- **Analysis**: The Coverage Closure section serves as an AI-agent instruction, not a machine-enforced gate. The generic 3-item checklist is duplicated 22 times (66 LOC). The step-specific checks (part A) are valuable and NOT extractable — they name specific upstream files and field mappings unique to each step. The generic checklist (part B) overlaps with the Hardening Protocol's "Completeness Closure" bullet.
- **Recommendation**: Extract the generic 3-item checklist to `shared_expectations.md`. Keep step-specific Coverage Closure checks inline. **Projected savings for generic checklist: 66 LOC.**

### FINDING-006: Metadata Contract is identical across 22 prompts and redundant with Schema Authority
- **Severity**: MEDIUM
- **Category**: BLOAT
- **Location**: All 22 prompts at `## Metadata Contract` (e.g., `prompts/prompt_00_project_charter.md:182`)
- **Description**: The Metadata Contract section is a single paragraph that is identical across all 22 prompts: "This step's output artifact MUST include every field listed in the schema's `required[]` array (see Schema Authority). Do NOT add fields not defined in the schema. Refer to the schema for the complete list of required fields, types, and structural constraints — do NOT restate them here." This is 3 lines x 22 = 66 LOC. It restates rules already covered by Schema Authority ("Do NOT guess field names, types, or valid values — all structural constraints are defined in the schema. Do NOT output fields not defined in the schema.") and Output Rules item 8 ("Do not include any fields outside the schema. `additionalProperties` is false everywhere.").
- **Evidence**: The sentence "Do NOT add fields not defined in the schema" appears verbatim or in near-identical form in Schema Authority, Metadata Contract, AND Output Rules across most prompts. Triple redundancy.
- **Recommendation**: Extract to `shared_expectations.md` or eliminate entirely since it restates Schema Authority + Output Rules. **Projected savings: 66 LOC.**

### FINDING-007: Quick Reference is a strict information subset of Field-by-Field Guidance in 15 of 17 prompts
- **Severity**: MEDIUM
- **Category**: BLOAT
- **Location**: 17 prompts with Quick Reference sections (steps 00-12 except 13, plus 13a, 15)
- **Description**: Quick Reference appears in 17/22 prompts. Field-by-Field Guidance appears in 18/22 prompts. In the 15 prompts where BOTH exist, Quick Reference is a strict information subset of Field-by-Field Guidance in all cases — it summarizes the same required fields, ID formats, and allowed values that Field-by-Field already covers in detail.
- **Evidence**: Comparing prompt_03_glossary.md:
  - Quick Reference (L129-131): "Required: `term_id`, `term`, `definition`. Optional but recommended: `domain`, `units`."
  - Field-by-Field (L108-113): Same fields with detailed format guidance for each.

  Comparing prompt_05_interface_contracts.md:
  - Quick Reference (L132-137): "ID Format: `interface_contracts-<descriptor>`; APIs use `api-<resource>-<action>`. Required Fields: each API needs `api_id`, `name`, `version`, `protocol`, and `owner`. Allowed Protocols: `http`, `grpc`, `ws`, `mqtt`. Security Flag: choose from `none`, `api-key`, `oauth2`, `jwt`, `mTLS`."
  - Field-by-Field (L98-108): Same info plus detailed guidance per field.

  Exceptions: Steps 16 and 16a have Quick Reference as a TABLE format with Type/Required/Purpose columns — this provides orthogonal structure-level info not in their Field Definitions sections. These are 2 of the 5 prompts that lack Quick Reference, confirming the pattern differs for late-stage prompts.
- **Analysis**: For standard prompts (00-15), Quick Reference adds ~3-5 LOC of summary that duplicates Field-by-Field. Total: ~55-70 LOC across 15 prompts. For step 16, the table format adds genuine value. For late-stage prompts (16a-16c), neither section exists (they use Field Definitions & Rules instead).
- **Recommendation**: Consider removing Quick Reference from standard prompts (00-15) since Field-by-Field is always present and more complete. Keep it for step 16 where it serves a different structural purpose. Alternatively, if Quick Reference serves as an AI "cheat sheet" that aids attention, document this rationale. **Projected savings: ~55-70 LOC if removed from 15 standard prompts.**

### FINDING-008: Output Rules contain 5 generic items + 0-5 step-specific items per prompt
- **Severity**: MEDIUM
- **Category**: BLOAT
- **Location**: 20 prompts with Output Rules sections
- **Description**: Across the 20 prompts with explicit Output Rules, 5 rules appear in almost all and are generic:
  1. "Write the final JSON artifact directly to disk at the step path under `spec/`..." (20/20)
  2. "The JSON must validate against the referenced step schema..." (18/20)
  3. "All IDs must be unique kebab-case strings." (14/20)
  4. "Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`..." (14/20)
  5. "Do not include any fields outside the schema. `additionalProperties` is false everywhere." (14/20)

  Step-specific rules that embed unique guidance:
  - Step 02: "Include `trace` as required by the schema (Step 02 requires them on components and connections)."
  - Step 07: "Use concrete numbers and metrics; avoid 'fast' or 'secure'."
  - Step 09: "You MUST include a top-level `trace` array linking to the Charter..."
  - Step 11: "Do not dump JSON in the chat thread"; `target_ids` MUST be populated; `mitigations` MUST use traceRef.
  - Step 14: "Include a top-level `$schema` field..."
  - Step 15: "DO NOT invent preconditions..."; "DO NOT guess `build_status`"; "DO NOT duplicate `interface_ref`"
  - Step 16a: "Write/update the artifact file at `spec/impl_context/{step_id}.json`"; "Do not dump JSON in chat thread"
  - Step 16b: "Do NOT modify `plan` outside `checklist[].implementation`..."
- **Evidence**: The 5 generic rules occupy ~5-6 lines per prompt. Across 14 prompts with all 5, that is ~70-84 LOC of duplication.
- **Recommendation**: Extract the 5 generic Output Rules to `shared_expectations.md`. Each prompt retains only its step-specific rules. **Projected savings: ~70-84 LOC across 14 fully-generic prompts.**

### FINDING-009: Tool Execution section is near-identical across all 22 prompts
- **Severity**: MEDIUM
- **Category**: BLOAT
- **Location**: All 22 prompts at `## Tool Execution` (e.g., `prompts/prompt_00_project_charter.md:23`)
- **Description**: The Tool Execution section contains 3-5 lines per prompt. The core pattern is identical: "Validate the generated JSON:\n```bash\n./tools/run_specdev.sh validate <path> --repo-root ./devspec_toolkit\n```". Only 2 prompts add step-specific commands: Step 14 adds `validate-all` and Step 12 references the full tooling context separately under `## Tooling Context`.
- **Evidence**: 20/22 prompts have a single `validate` command only. Steps 12 and 14 have additional commands.
- **Recommendation**: Extract the generic validation command to `shared_expectations.md`. Keep step-specific tool commands (12, 14) inline. **Projected savings: ~66 LOC** (3 lines x 22, minus step-specific additions).

### FINDING-010: shared_expectations.md is referenced by only 8/22 prompts despite applying to all
- **Severity**: LOW
- **Category**: BLOAT
- **Location**: `docs/prompts/shared_expectations.md`; 14 prompts that do not reference it
- **Description**: The shared_expectations.md file is referenced by only 8 prompts (00, 01, 02, 02a, 03, 04, 16b, 16c) via Context To Ingest or Task sections. The remaining 14 prompts do not reference it. Yet all 22 prompts duplicate content that shared_expectations.md covers (Quality Protocol = Hardening Protocol, Canonical Reuse Rules = Canonical Binding Rules, Step-Order Policy = forward-only waterfall).
- **Evidence**: shared_expectations.md is only 51 LOC. It could grow to ~150-200 LOC if the extractable sections from this analysis are consolidated into it.
- **Recommendation**: After extracting shared sections, add a universal reference to shared_expectations.md in all 22 prompts (either as a header instruction or integrated into Schema Authority). **Impact: consistency improvement, no LOC savings by itself.**

### FINDING-011: shared_expectations.md current content overlaps with but does not supersede inline sections
- **Severity**: LOW
- **Category**: BLOAT
- **Location**: `docs/prompts/shared_expectations.md` (51 LOC)
- **Description**: The current shared_expectations.md contains 7 sections that overlap with inline prompt sections but use different wording:
  - "Canonical Reuse Rules" (L21-25) overlaps with Canonical Binding Rules (inline)
  - "Canonical Resolution Protocol" (L27-32) overlaps with Canonical Registry (inline)
  - "one-go Quality Protocol" (L34-39) overlaps with Hardening Protocol (inline)
  - "Step-Order Policy" (L41-45) overlaps with statements in various prompts about forward-only waterfall
  - "Definition of Ready" (L6-7) references Self-Audit Gate and Coverage Closure by name

  The overlap means the AI agent receives the same guidance twice in different phrasings when shared_expectations.md IS referenced, and misses it entirely when it is NOT referenced (14/22 prompts).
- **Evidence**: "one-go Quality Protocol" says "Evidence Ledger: every non-trivial decision must be traceable to seed input, upstream artifact evidence, or canonical registry evidence." The Hardening Protocol says "No-Invention Rules: do not invent IDs, enums, commands... that are not grounded in provided inputs." Same intent, different words.
- **Recommendation**: When extracting inline sections, reconcile wording with existing shared_expectations.md content to avoid double-statements. The inline versions (Hardening Protocol, Canonical Binding Rules) are generally more specific and action-oriented; prefer them as the canonical text.

### FINDING-012: Projected total extractable LOC and new shared_expectations.md size
- **Severity**: INFO
- **Category**: BLOAT
- **Location**: All 22 prompts + `docs/prompts/shared_expectations.md`
- **Description**: Summary of projected extraction:

  | Section | LOC Saved | Notes |
  |---------|-----------|-------|
  | Hardening Protocol | 132 | 6 lines x 22, 100% identical |
  | Canonical Registry | 154 | 7 lines x 22, merge step-12 variant |
  | Canonical Binding Rules | 132 | 6 lines x 22, 100% identical |
  | Path Variables | 176 | 8 lines x 22, 100% identical |
  | Metadata Contract | 66 | 3 lines x 22, 100% identical, redundant with Schema Authority |
  | Generic Coverage Closure checklist | 66 | 3 lines x 22, 100% identical |
  | Generic Output Rules | ~75 | ~5 lines x ~15 fully-generic prompts |
  | Tool Execution (generic) | ~66 | 3 lines x 22 |
  | Quick Reference (redundant with Field-by-Field) | ~60 | ~4 lines x 15 prompts |
  | **Total extractable** | **~927** | |

  Current prompt LOC: 5,727. After extraction: ~4,800 LOC (~16% reduction).
  Current shared_expectations.md: 51 LOC. New size: ~130-160 LOC (add ~80-110 lines for extracted sections, reconciled with existing overlap).

  Per-prompt reduction: average ~42 lines removed per prompt (~260 LOC → ~218 LOC for a typical standard prompt).

- **Recommendation**: Implement extraction in phases:
  1. **Phase 1** (highest ROI): Extract Hardening Protocol + Canonical Registry + Canonical Binding Rules + Path Variables (594 LOC, zero risk of step-specific loss)
  2. **Phase 2** (moderate ROI): Extract Metadata Contract + generic Output Rules + generic Coverage Closure checklist + Tool Execution (273 LOC)
  3. **Phase 3** (lowest priority): Evaluate Quick Reference removal after measuring AI-agent impact

---

## Appendix: Answers to Scoped Questions

### Q1: Would extracting shared sections lose step-specific information?

**No**, with the following exceptions requiring attention:
- **Canonical Registry step 12**: Has a meaningful variant with deprecated-canonical checking and explicit proposal field requirements. Must be merged into the shared version, not dropped.
- **Output Rules**: 8 of 22 prompts embed step-specific rules within the generic Output Rules block. These MUST be preserved inline after extracting generics.
- **Schema Authority**: Contains a step-specific schema filename on line 1. This line must remain inline or be templated.
- **Coverage Closure**: The step-specific checks (part A) MUST remain inline. Only the generic 3-item checklist (part B) is extractable.

### Q2: Is Coverage Gap Reporting consumed by any validator?

**No.** Zero validators in `tools/specdev_tools/` reference "Coverage Closure", "Coverage Gap", "Self-Audit Gate", or "score < 0.9". These sections are purely AI-agent instructions. They provide value as prompt-engineering guardrails but are NOT machine-enforced.

The step-specific Coverage Closure checks (e.g., "Every FR in `spec/04_functional_requirements.json` that specifies an observable external behavior is covered by >= 1 `api_id`...") are partially enforced by separate lint mechanisms:
- E560 TRACEABILITY_GAP enforces some of these rules at the lint level
- W561 FR_UNCOVERED enforces FR coverage
- W592 enforces threshold-based coverage

But the Coverage Closure text itself is never parsed or consumed by any tool.

### Q3: Is Quick Reference a strict information subset of Field-by-Field Guidance?

**Yes**, in 15 of 17 prompts where both exist. Quick Reference summarizes required fields, ID formats, and enum values that Field-by-Field already covers comprehensively. The 2 exceptions:
- Step 16: Quick Reference uses a table format with Type/Required/Purpose columns (structural overview vs per-field guidance)
- Step 13a: Quick Reference includes scoring info not in Field-by-Field

For the 5 prompts missing Quick Reference (13, 14, 16a, 16b, 16c), Field-by-Field or Field Definitions sections exist and cover the same ground.

### Q4: Which Output Rules items are truly generic vs step-specific?

**Generic** (appear in 14+ of 20 prompts with Output Rules):
1. Write to disk at spec path (20/20)
2. Validate against schema (18/20)
3. Unique kebab-case IDs (14/20)
4. Owner enum (14/20)
5. No fields outside schema / additionalProperties false (14/20)

**Step-specific** (appear in 1-3 prompts with unique guidance):
- Step 02: trace on components/connections
- Step 07: "concrete numbers and metrics" language
- Step 09: mandatory top-level trace array
- Step 11: no JSON in chat; target_ids and mitigations mandatory
- Step 13: extensions sorted by ID
- Step 13a: completeness_rating.target = 10
- Step 14: $schema field required
- Step 15: no invented preconditions; no duplicate interface_ref
- Step 16a: write to impl_context path; no JSON in chat; populate plan only
- Step 16b: don't modify plan outside implementation fields

### Q5: Projected LOC reduction and new shared_expectations.md size?

See FINDING-012 above. Per-prompt: ~42 lines average reduction. Total: ~927 LOC saved. shared_expectations.md grows from 51 to ~130-160 LOC.

### Q6: Would removing "boilerplate" sections lose step-specific guidance embedded within?

**Yes, in 3 cases that require care:**
1. **Output Rules**: 8 prompts embed step-specific items within the generic list (items 5-10). Solution: extract items 1-5 generically, keep step-specific items inline.
2. **Schema Authority line 1**: Contains step-specific schema filename. Solution: keep this line inline or template it.
3. **Coverage Closure**: Step-specific checks are embedded alongside the generic 3-item checklist. Solution: extract only the generic checklist, keep step-specific checks inline.

### Q7: What is unique about step 12's Canonical Registry section?

Step 12's variant is a **meaningful expansion**, not a copy error. It adds:
1. Explicit instruction to search by `kind` + `preferred_label` or alias (more prescriptive search methodology)
2. Required fields for proposals: `temp_id`, `kind`, `proposed_label`, `definition`, `source_field`
3. "NEVER leave a `*_ref` field empty when a matching canonical entry exists" (explicit prohibition)
4. "NEVER use a deprecated canonical without checking `replaced_by` first" (deprecation handling)

Items 3 and 4 are valuable rules that SHOULD apply to ALL prompts. The standard version assumes these implicitly but does not state them. The recommendation is to merge these rules into the shared version.
