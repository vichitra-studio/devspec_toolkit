<review_prompt>
# Deep Dive System Review: Canonical Drift, Traceability Closure & Prompt Hardening

## Context: Goal & Intent of Changes
**You must evaluate the system against these specific definitions of success:**

### 1. Problem Statement
The DevSpec Toolkit (v0.3.0) has structural gaps in thirteen interconnected areas: seed-to-roadmap traceability, roadmap-to-implementation completeness, cross-step semantic drift detection, test suite hygiene (legacy B* naming), canonical alias lifecycle enforcement, prompt hardening against hallucination and assumption, schema validation path robustness, invariant engine soundness, generation quality self-report trust, environment-dependent validation behavior, submodule integration path integrity, toolkit discovery deficit in prompts, and schema-prompt contract misalignment. These gaps are not isolated — they form a dependency chain where upstream weaknesses (e.g., thin validators, missing traceability checks, untrusted self-reports, git-root mismatch in the primary deployment model) propagate downstream into unreliable implementation artifacts. Additionally, the AI agents generating artifacts have near-zero awareness of the toolkit infrastructure beyond the single prompt they receive — they cannot see downstream consumers, validation rules, or the pipeline DAG, producing artifacts that are structurally valid but poorly optimized for downstream extraction.

### 2. Goal
Produce a **complete, dependency-ordered remediation plan** that closes all identified gaps with zero rework. Every fix must be grounded in verified file paths and line numbers. The plan must be executable by an AI agent without further human consultation.

### 3. Intent
Treat this as a **structural integrity audit** — not a feature review. The question is not "does each piece work in isolation?" but "does the entire pipeline guarantee that upstream requirements flow through every step to implementation without loss, drift, or hallucination?"

### 4. Purpose
Ensure the DevSpec Toolkit enforces a **deterministic, lossless pipeline** from seed documents through roadmap to implementation, where every prompt eliminates assumptions, every validator catches semantic drift, and every canonical reference is lifecycle-managed.

---

## Role
You are a **Principal Systems Architect** and **Specification Integrity Auditor** with deep expertise in schema-driven development pipelines, AI prompt engineering, and deterministic workflow enforcement. Your task is to perform a rigorous, evidence-based review of the `devspec_toolkit` repository and produce two deliverables: a Detailed Review Report (Part A) and a Dependency-Ordered Implementation Plan (Part B).

---

## Repository Context

### Toolkit Structure
```
devspec_toolkit/
├── schema/                          # JSON Schemas for every step + core/ (atoms, collections, errors)
├── canon/                           # Canonical registry (manifest.json, aliases.json)
├── tools/
│   ├── specdev_tools/
│   │   ├── cli.py                   # Entry point
│   │   ├── core/                    # errors, registry, trace_types, changelog_parser
│   │   ├── validation/
│   │   │   ├── validate.py          # Main validation orchestrator
│   │   │   ├── validators/          # Per-step validators (step_00.py .. step_16c.py)
│   │   │   ├── seed_lint.py         # Seed document linter
│   │   │   ├── docs_lint.py         # Documentation linter
│   │   │   ├── quality_lint.py      # Spec quality linter
│   │   │   ├── hallucination_lint.py # Hallucination detection
│   │   │   ├── traceability_closure.py # FR/API/NFR traceability
│   │   │   ├── dependency_order_lint.py # Step ordering
│   │   │   ├── forward_replay_check.py # Forward replay validation
│   │   │   ├── invariants_check.py  # Invariant enforcement
│   │   │   ├── governance_check.py  # Commit governance
│   │   │   └── matrix.py            # Trace matrix generation
│   │   ├── canonical/
│   │   │   ├── lint.py              # Canonical ref linter
│   │   │   ├── integrity.py         # Cross-artifact drift (E210)
│   │   │   ├── registry.py          # Canonical registry + alias resolution
│   │   │   └── autofix.py           # Canonical autofix suggestions
│   │   ├── generation/              # Prompt generator, schema sync, differ
│   │   └── migration/               # Planner, runner
│   ├── schema_registry.json         # Step name → JSON Schema path map
│   ├── step_order.json              # Strict waterfall dependency DAG
│   └── trace_matrix.json            # Generated traceability matrix
├── prompts/                         # Deterministic prompt contracts (prompt_00..prompt_16c)
│   ├── prompt_00_project_charter.md
│   ├── prompt_01_capabilities.md
│   ├── prompt_02_system_sketch.md
│   ├── prompt_02a_delivery_baseline.md
│   ├── prompt_03_glossary.md
│   ├── prompt_04_functional_requirements.md
│   ├── prompt_05_interface_contracts.md
│   ├── prompt_06_invariants.md
│   ├── prompt_07_nfrs.md
│   ├── prompt_08_fixtures.md
│   ├── prompt_09_impl_plan.md
│   ├── prompt_10_governance.md
│   ├── prompt_11_redteam.md
│   ├── prompt_12_ci_gates.md
│   ├── prompt_13_extension_generator.md
│   ├── prompt_13a_completeness_assessment.md
│   ├── prompt_14_roadmap.md
│   ├── prompt_15_scaffold.md
│   ├── prompt_16_impl_context.md
│   ├── prompt_16a_impl_planner.md
│   ├── prompt_16b_impl_coder.md
│   └── prompt_16c_impl_reviewer.md
├── spec/                            # Generated spec artifacts (NN_name.json + NN_name.guide.md)
├── tests/                           # pytest suite
│   ├── fixtures/                    # Per-step valid/invalid JSON fixtures
│   ├── integration/                 # Step-level integration scripts
│   ├── test_schema_contracts.py     # Schema contract tests (contains B4 naming)
│   ├── test_prompt_contracts.py     # Prompt contract tests (contains B4 naming)
│   └── ...
├── docs/
│   ├── audit/                       # Prior review prompts (01_system, 02_tooling, 03_docs)
│   ├── agents/                      # Agent protocol (manifest.json)
│   └── developers/                  # Developer documentation
└── canon/
    ├── manifest.json                # Canonical vocabulary registry
    └── aliases.json                 # Alias → canonical mappings with status
```

### Spec Pipeline (Steps 00–16c)
The workflow is a **strict forward-only waterfall**. Any upstream change requires full replay of all downstream steps. Steps are numbered: `00 01 02 02a 03 04 05 06 07 08 09 10 11 12 13 13a 14 15 16 16a 16b 16c`.

| Phase | Steps | Purpose |
|---|---|---|
| Phase 0 | Seed docs | `seed_overview.md` + `seed_tech_stack.md` before any formal specs |
| Phase I · Discovery | 00–12 | Charter → Capabilities → System Sketch → Glossary → FRs → APIs → Invariants → NFRs → Fixtures → Impl Plan → Governance → Red Team → CI Gates |
| Phase II · Impl | 13–16c | Extension Generator → Completeness Assessment → Roadmap → Scaffold → Trinity Loop (16a plan / 16b code / 16c review) |

### Prior Review History
- **Review 01 (System)**: Architecture, schema design, error taxonomy, validation pipeline
- **Review 02 (Tooling)**: CLI commands, validators, linters, canonical tools, generation/migration
- **Review 03 (Documentation)**: Docs coverage, audience clarity, context preservation
- **This Review (04)**: Cross-cutting structural integrity — traceability, drift, prompts, hygiene, engine soundness, self-report trust, environment determinism, submodule integration, toolkit discovery, schema-prompt alignment

---

## Review Objectives

You must investigate and report on **all thirteen areas** below. For each area, the "Verified Starting Points" are confirmed gaps with exact file paths and line numbers — use them as anchors but **do not treat them as exhaustive**. You must independently verify each gap still exists and discover additional gaps through your own exploration.

---

### Area 1: Seed → Roadmap Traceability

**Question**: Do all system requirements from seed documents (`seed_overview.md`, `seed_tech_stack.md`) propagate through every step to the roadmap (step 14) without loss?

**What to examine**:
- `tools/step_order.json` (lines 451-459) — Step 14 declares `required_seed_inputs: ["seed-overview"]` but does not include `seed-tech-stack`. Verify whether this is intentional or a gap.
- `tools/specdev_tools/validation/seed_lint.py` (lines 178-193) — The `_collect_required_seeds()` function validates that declared `seed_refs` exist, but does NOT validate that the step actually *consumes* the content of those seeds. A step can declare `seed_refs: ["seed-overview"]` without using any information from it.
- Trace the full chain: seeds → step 00 (charter) → step 01 (capabilities) → ... → step 14 (roadmap). At each link, verify:
  - Does the step's prompt (`prompts/prompt_NN_*.md`) instruct the agent to consume ALL upstream seeds?
  - Does the validator (`tools/specdev_tools/validation/validators/step_NN.py`) enforce that seed-derived content appears in the output?
  - Does `step_order.json` correctly declare all seed dependencies for each step?
- Check `tools/specdev_tools/validation/traceability_closure.py` for whether it validates seed→FR→roadmap chains or only FR→API→fixture chains.

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| Seed consumption not validated | `validation/seed_lint.py:178-193` | Checks seed_refs exist but not that content is consumed |
| Step 14 may omit seed-tech-stack | `step_order.json:451-459` | Only `seed-overview` in required_seed_inputs |
| No end-to-end seed chain validation | `validation/traceability_closure.py:67-76` | Collects FR→capability traces but no seed→roadmap chain |

---

### Area 2: Roadmap → Implementation Completeness

**Question**: Does the Trinity Loop (steps 16a/16b/16c) implement ALL roadmap items with deterministic tests and evidence?

**What to examine**:
- `tools/specdev_tools/validation/traceability_closure.py` (lines 67-76) — Collects FR IDs and capability traces. Check whether it validates that ALL FRs are assigned to roadmap milestones and that all milestones have implementation evidence in step 16a/16b/16c.
- Check for missing E-codes: `traceability_closure.py` should emit errors for:
  - **E561**: FR not assigned to any milestone
  - **E562**: Orphan milestone (milestone with no FR refs)
  - **E563**: Checklist item in 13a has no corresponding roadmap entry
  - Verify whether these E-codes exist in `tools/specdev_tools/core/errors.py` or are defined anywhere.
- Examine `prompts/prompt_14_roadmap.md` — Does it require that every FR from step 04 appears in at least one milestone?
- Examine `prompts/prompt_16a_impl_planner.md`, `prompt_16b_impl_coder.md`, `prompt_16c_impl_reviewer.md` — Do they require mapping back to roadmap milestones?
- Check validators: `validation/validators/step_14.py`, `step_16a.py`, `step_16b.py`, `step_16c.py` — Do they enforce roadmap↔implementation binding?

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| No uncovered-FR detection | `validation/traceability_closure.py:67-76` | Collects FR IDs but doesn't check milestone assignment |
| Missing E-codes | `validation/traceability_closure.py` | No E561/E562/E563 for uncovered FRs, orphan milestones, checklist-roadmap mismatch |
| Thin step validators | `validation/validators/step_04.py` (21 LOC), `step_06.py` (16), `step_07.py` (20), `step_08.py` (16), `step_12.py` (21), `step_13a.py` (17) | Complex spec steps with minimal custom validation logic |

---

### Area 3: Semantic Drift Across Steps

**Question**: Does the toolkit detect when the same concept drifts in meaning, naming, or scope as it flows through the pipeline?

**What to examine**:
- `tools/specdev_tools/canonical/integrity.py` — The E210 `CROSS_ARTIFACT_DRIFT` detection system:
  - Lines 62-66, 110-114: E210 error emission points
  - Lines 214-243: `_collect_observed_semantics()` — gathers `_ref` fields for drift analysis. Check whether this detects **partial drift** (e.g., 2 of 3 references updated to a new term, 1 still using the old term).
  - Lines 162-169: Canonical refs mismatch variant
  - Lines 296-300: Unresolved canonical semantic variant
- `tools/specdev_tools/validation/forward_replay_check.py` — Does it check semantic correctness of replayed artifacts, or only file existence and structural validity?
- Thin validators (Area 2 above) — Steps 04, 06, 07, 08, 12, 13a have minimal custom validation. For complex steps like Functional Requirements (04) and Invariants (06), what semantic checks are missing?
- Cross-reference: If step 04 defines `fr-user-login` and step 05 references it as `fr-login`, is this caught? Where?

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| No partial drift detection | `canonical/integrity.py:214-243` | `_collect_observed_semantics` gathers refs but doesn't detect partial updates (2/3 refs updated, 1/3 stale) |
| Forward replay may be structural only | `validation/forward_replay_check.py` | Verify whether it checks semantic content or only file existence |
| Thin validators for complex steps | `validation/validators/step_04.py` (21 LOC) | FR validation with minimal semantic checks |

---

### Area 4: B0-B8 Cleanup & Repo Hygiene

**Question**: Does the test suite contain legacy naming from prior project phases (B0-B8 batch naming) that should be cleaned up?

**What to examine**:
- `tests/test_schema_contracts.py` (line 19) — Contains `test_all_step_schemas_include_b4_top_level_fields`. The "B4" name refers to a prior project batch, not a meaningful test name. This should be renamed to describe what it actually tests (e.g., `test_all_step_schemas_include_generation_metadata_fields`).
- `tests/test_prompt_contracts.py` (line 17) — Contains `test_output_contract_examples_include_b4_fields`. Same issue.
- Search ALL test files for any `B[0-8]` or `b[0-8]` references in test names, docstrings, comments, or fixture names.
- Check for:
  - Dead test fixtures in `tests/fixtures/` that are no longer referenced
  - Test files that duplicate coverage
  - Inconsistent test naming conventions across the suite
  - Test helper functions that could be shared but are duplicated

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| B4 naming in schema tests | `tests/test_schema_contracts.py:19` | `test_all_step_schemas_include_b4_top_level_fields` |
| B4 naming in prompt tests | `tests/test_prompt_contracts.py:17` | `test_output_contract_examples_include_b4_fields` |

---

### Area 5: Canonical Alias Lifecycle

**Question**: Are deprecated canonical aliases enforced with timelines, sunset dates, and orphan detection?

**What to examine**:
- `tools/specdev_tools/canonical/registry.py` (lines 107-108) — `alias_is_deprecated()` method checks if an alias has `"deprecated"` status. But:
  - Is there a `deprecated_since` or `sunset_date` field in `canon/aliases.json`?
  - Does anything prevent a deprecated alias from being used indefinitely?
  - Is there a warning escalation path (W120 → E-code after sunset)?
- `tools/specdev_tools/canonical/registry.py` (lines 128, 134) — W110 and W120 warning emissions. Are these ever promoted to errors?
- `tools/specdev_tools/canonical/autofix.py` — Does autofix suggest replacing deprecated aliases with their canonical equivalents? (Note: verified that line 129 contains `resolve_alias` but NO deprecated-specific logic exists in autofix.py)
- `canon/aliases.json` — Check the actual structure. Does it support lifecycle fields (deprecated_since, sunset_date, replacement)?
- Orphan detection: Is there a check for canonical terms in `canon/manifest.json` that are never referenced by any spec artifact?

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| No sunset enforcement | `canonical/registry.py:107-108` | `alias_is_deprecated` returns bool but no timeline/escalation |
| Warnings never promoted | `canonical/registry.py:128,134` | W110/W120 are warnings only, no error promotion path |
| Autofix ignores deprecated aliases | `canonical/autofix.py` | No deprecated-specific autofix logic exists in this file |

---

### Area 6: Holistic Prompt Hardening

**Question**: Does every prompt (00–16c) guarantee complete, correct, assumption-free output that is fully compliant with seed documents, system requirements, and ALL upstream artifacts?

**This is the most critical and broadest area.** It is NOT limited to canonical reference enforcement — it covers the entire prompt contract for deterministic, lossless spec generation.

**What to examine for EVERY prompt** (`prompts/prompt_00_project_charter.md` through `prompts/prompt_16c_impl_reviewer.md`):

#### 6a. Exhaustive Upstream Input Consumption
- Does the prompt explicitly list ALL upstream artifacts it must consume (per `step_order.json` dependencies)?
- For each listed upstream artifact, does the prompt specify WHAT to extract and HOW to use it?
- Example: `step_order.json` declares that step 14 requires `09_impl_plan.json`, `00_charter.json`, `04_functional_requirements.json`, `13_extension_generator.json`, `13a_completeness_assessment.json`. Does `prompt_14_roadmap.md` contain explicit extraction instructions for each?

#### 6b. Deterministic Instructions (Zero-Inference Output)
- Are there any instructions that rely on agent judgment, inference, or "best effort"? These must be replaced with deterministic rules.
- Does the prompt use vague language like "consider", "if appropriate", "as needed", "relevant", "may include"? Each of these is a hallucination vector.
- Does the prompt specify exact field-by-field output requirements with no optional or ambiguous fields?

#### 6c. Seed Document Compliance
- Does every prompt that should reference seeds (per `step_order.json` `required_seed_inputs`) explicitly instruct the agent to:
  1. Read the seed document(s)
  2. Extract specific information from them
  3. Reflect that information in specific output fields
  4. Populate `seed_refs` with actually-used seed IDs?

#### 6d. Fallback & Escalation Rules
- When information is missing or ambiguous in upstream artifacts, does the prompt specify:
  - A concrete fallback action (not "use your best judgment")?
  - An escalation mechanism (e.g., emit a clarification question, halt and report)?
- Does the prompt implement the Two-Phase **Clarify → Emit** protocol with a Self-Audit Gate score threshold?

#### 6e. Canonical Reference Enforcement
- Does the prompt instruct the agent to use ONLY terms from `canon/manifest.json` for controlled vocabularies?
- Does the prompt require `canonical_refs_used`, `canonical_proposals`, and `canonical_conflicts` in output?

**Cross-reference with validators**: For each prompt, check whether the corresponding validator (`validation/validators/step_NN.py`) enforces the same requirements. If a prompt requires a field but the validator doesn't check it, that's a gap.

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| Prompts lack exhaustive upstream consumption rules | All `prompts/prompt_*.md` | No systematic enforcement that every declared upstream input is consumed and reflected in output |
| Thin validators can't enforce prompt contracts | `validation/validators/step_04.py` (21 LOC) etc. | If the prompt requires 20 fields, but the validator only checks 3, the prompt contract is unenforceable |
| Step 14 seed consumption gap | `prompts/prompt_14_roadmap.md` + `step_order.json:451-459` | Verify whether prompt instructs consumption of all 5 declared upstream artifacts |

---

### Area 7: Schema Validation Paths

**Question**: Are `$ref` references in JSON Schemas resolved correctly, and are validation paths consistent and robust?

**What to examine**:
- `tools/specdev_tools/core/registry.py` (64 lines total) — This is a lean `SchemaRegistry` class that maps URIs to file paths and preloads schemas. It does NOT contain `$ref` resolution logic — that is delegated to the `jsonschema` library. Check:
  - Is the `jsonschema` library configured with a custom `RefResolver` that uses `SchemaRegistry`?
  - What happens if a `$ref` in `schema/core/` points to a non-existent file?
  - Is there any circular `$ref` detection? (Not in `registry.py` — check `validate.py` and the `jsonschema` configuration)
- `tools/schema_registry.json` — Does every step in `step_order.json` have a corresponding entry? Are there orphan entries?
- `schema/core/` — Shared atoms, collections, errors. Verify that every `$ref` in step schemas resolves to an actual file in `schema/core/`.
- `tools/specdev_tools/validation/validate.py` — The main validation orchestrator. How does it load schemas? Does it handle `$ref` resolution errors gracefully?
- Canonical path consistency: Do `canonical-lint`, `canonical-integrity`, and the schema validators all resolve canonical references through the same path? Or are there inconsistencies?

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| No $ref resolution logic in registry | `core/registry.py` | 64-line file delegates entirely to jsonschema library; no custom resolution or error handling |
| Unknown circular $ref behavior | `core/registry.py` + `validation/validate.py` | No explicit circular detection; behavior on malformed schemas is undefined |
| Schema registry completeness unverified | `tools/schema_registry.json` + `tools/step_order.json` | No automated check that every step has a schema entry |

---

### Area 8: Invariant Engine Soundness

**Question**: Does the invariant evaluation engine (`_tiny_eval`) produce correct, unambiguous results for all supported expressions, and does it fail visibly on unsupported ones?

**What to examine**:
- `tools/specdev_tools/validation/invariants.py` (lines 5-40) — The `_tiny_eval()` function implements a hand-rolled JSONLogic subset. It supports a fixed set of operators: `>=`, `<=`, `>`, `<`, `==`, `and`, `or`, `not`, `in`, `contains`. Check:
  - **Silent fallthrough on unknown operators**: Line 40 returns `None` for any operator not in the hardcoded set. This `None` propagates to line 63 where `bool(None)` → `False`, recording the invariant as *failed*. But the failure is indistinguishable from a genuinely violated invariant — no warning or error is emitted. Operators like `!=`, `!`, `if`, `merge`, `cat`, `missing`, or any standard JSONLogic operator will silently produce wrong results.
  - **Type safety on comparisons**: Lines 22-28 perform direct comparisons (`vals[0] >= vals[1]`). If a `var` path does not resolve (returns `None` from line 18), the comparison raises `TypeError`, which is caught at line 58 and mapped to `ok = None` → silently treated as failed.
  - **No expression validation**: There is no pre-evaluation check that the expression is well-formed or uses only supported operators. An invariant author has no way to know their expression will be silently misinterpreted.
- `tools/specdev_tools/validation/invariants.py` (lines 42-65) — The `run_invariants()` function:
  - Line 51: Uses `json.load(open(p, ...))` without a `with` statement — file handle leak on exception.
  - Line 57: Attempts to parse string expressions as JSON inline, with a heuristic check (`startswith("{")`) that will miss array-form JSONLogic expressions (e.g., `[">", {"var": "x"}, 5]`).
  - Line 64: The result dict contains `"result": bool(ok)` but no field indicating whether the expression was *supported* vs *unsupported*. Consumers cannot distinguish "invariant violated" from "invariant not evaluable".

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| Silent None on unknown operators | `validation/invariants.py:40` | `_tiny_eval` returns `None` for unrecognized operators; `bool(None)` records as failed invariant with no warning |
| TypeError on None comparisons | `validation/invariants.py:22-28` | Comparisons with unresolved `var` paths raise TypeError, caught silently at line 58 |
| No supported-operator feedback | `validation/invariants.py:60-64` | Result dict has no field to distinguish "violated" from "unsupported expression" |

---

### Area 9: Generation Quality Self-Report — Write-Only Metadata

**Question**: Is the `generation_quality` block in every spec artifact consumed by any downstream step, tool, or validator — or is it write-only dead weight that costs tokens on every AI invocation and storage in every artifact stored in git?

**Context**: Every spec artifact must contain a `generation_quality` object where the AI agent self-reports its quality assessment. The intended purpose is to create an audit trail of the agent's confidence. The critical question is whether any part of the system actually *uses* this audit trail, or whether it exists only because the agent was told to write it.

**What to examine — field-by-field consumption audit**:

Trace each `generation_quality` sub-field through the entire toolchain. For each field, answer: (1) Does any validator read it? (2) Does any downstream prompt consume it from an upstream artifact? (3) Does any tool gate on it?

- **`preflight_passed`** (boolean):
  - `schema/core/collections.schema.json` (line 385-386, 463-464) — Defined as a boolean, and the **only** required sub-field in the `generationQuality` schema definition.
  - Search ALL validators in `tools/specdev_tools/validation/validators/` — verify whether any step validator reads `preflight_passed` from the current or any upstream artifact.
  - Search ALL prompts in `prompts/` — verify whether any prompt instructs the agent to check that an upstream artifact's `preflight_passed` is `true` before proceeding.
  - **Confirmed gap**: No validator, tool, or downstream prompt reads this field. An agent can set `preflight_passed: true` while the artifact contains E510 placeholders, E520 empty critical arrays, or E530 invented IDs. The field is write-only.

- **`evidence_records`** (array of `{field_path, source_kind, source_ref}`):
  - `schema/core/collections.schema.json` (lines 388-417) — Structured array with required fields `field_path`, `source_kind`, `source_ref`. Designed to trace which output fields came from which upstream sources.
  - Search ALL validators and tools — verify whether any code reads `evidence_records` from any artifact.
  - **Confirmed gap**: No validator, tool, or downstream prompt reads this field. Despite having the richest schema definition in the block, it is never consumed. Write-only.

- **`placeholder_scan.tokens_found`** (string array):
  - `tools/specdev_tools/validation/spec_quality_lint.py` (lines 94-114) — The `_check_placeholder_scan_agreement()` function is the **only** code that reads any `generation_quality` sub-field. It compares `tokens_found` against an independent regex scan (E510) and emits E511 if the agent missed tokens.
  - **The circularity problem**: The independent scan (E510, lines 171-191) already finds all placeholders. E511 then checks whether the agent's self-report matches what E510 already knows. If they match → no value added. If they don't match → E510 already caught the placeholders; E511 only adds "and the agent didn't report them honestly." The independent scan is the source of truth regardless.
  - **Confirmed gap**: The self-report adds no detection capability. The independent scan catches everything. The self-report field exists only to verify the agent's honesty about something the system already knows independently.

- **`placeholder_scan.has_placeholders`** (boolean):
  - Search ALL validators — verify whether any code reads `has_placeholders`.
  - **Confirmed gap**: No validator reads this field. The independent E510 scan determines placeholder presence directly. Write-only.

- **`unresolved_inputs`** (string array):
  - Search ALL validators — verify whether any code reads `unresolved_inputs` or cross-checks it against `step_order.json` `required_spec_inputs`.
  - **Confirmed gap**: No validator verifies this. The agent self-reports which inputs it couldn't resolve, but nothing checks whether the report is accurate. Write-only.

- **`assumptions`** (string array):
  - `tools/specdev_tools/validation/spec_quality_lint.py` (lines 117-151) — **This field has partial value.** The linter checks: W572 (count > 10), W571 (vague quantifiers like "few", "some", "many"), W573 (references to unbound spec IDs in assumption text). These checks scan the *content* the agent wrote, catching anti-patterns the agent might not self-report.
  - However: these same checks could run on ALL free-text fields in the artifact, not just the `assumptions` array. The value comes from the independent scan logic, not from the agent pre-collecting assumptions into a dedicated array.

- **`self_check_results`** (array of `{check_id, passed, details}`):
  - `schema/core/collections.schema.json` (lines 440-461) — Has structure (`check_id`, `passed` required) but no constraints on what `check_id` values must be used.
  - Search ALL validators and tools — verify whether any code reads `self_check_results`.
  - **Confirmed gap**: No validator reads this field. No required check IDs are defined. The agent can write anything or nothing. Write-only.

**The aggregate finding**: The `generation_quality` block is a **write-only metadata structure** embedded in every spec artifact. Of 7 sub-fields, 5 are never read by any tool. 1 (placeholder_scan.tokens_found) is read only to verify the agent's honesty about something an independent scan already knows. 1 (assumptions) has partial value through content scanning, but the scanning logic doesn't depend on the field existing — it could scan free-text fields directly.

**Cost at scale**: Every AI invocation across 22 steps must generate this block (~15-20 lines of JSON). Every prompt must explain it (~10-15 lines of instructions). Every artifact stores it in git. For a project with 500 spec artifacts, that's ~10,000 lines of write-only metadata in the repository.

**What to evaluate**: Determine whether `generation_quality` should be:
  - (a) **Removed entirely** from the schema and replaced with independent-scan-only validation (prompt instructions remain as cognitive forcing, but the output field is eliminated).
  - (b) **Reduced** to only `assumptions` (the one field with partial downstream value) with independent scans replacing everything else.
  - (c) **Kept but made consumable** by adding validators that actually gate on `preflight_passed`, cross-check `unresolved_inputs`, and require specific `self_check_results` entries.

Note: Option (a) or (b) would be a breaking schema change requiring a v0.4.0 migration across all existing artifacts. The review should assess the cost-benefit of each option.

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| `preflight_passed` is write-only | `validation/spec_quality_lint.py` + all `validation/validators/` | No validator, tool, or downstream prompt reads this field; no independent verification |
| `evidence_records` is write-only | `schema/core/collections.schema.json:388-417` | Richest schema definition in the block; never consumed by any code |
| E511 placeholder cross-check is circular | `validation/spec_quality_lint.py:94-114` | Compares self-report against independent scan that is already the source of truth |
| `self_check_results` is write-only | `schema/core/collections.schema.json:440-461` | No required check IDs; no code reads the array |
| No downstream step consumes upstream `generation_quality` | All `prompts/prompt_*.md` | No prompt instructs agent to check upstream artifact's preflight_passed before proceeding |

---

### Area 10: Environment-Dependent Validation Behavior

**Question**: Does the validation pipeline produce consistent, reproducible results across different execution environments (local dev, CI, non-git contexts), or does it silently disable checks based on runtime conditions?

**What to examine**:
- `tools/specdev_tools/validation/validate.py` (lines 231-238) — Forward replay check environment sensitivity:
  - Lines 233-236: `SPECDEV_REPLAY_DIFF_ERROR_MODE` env var controls whether forward replay errors are emitted. When not set, the mode is determined by `in_ci` (checks `CI` env var) or `_is_git_repo()`. In a non-CI, non-git environment, mode defaults to `"ignore"` — **forward replay validation is silently disabled entirely**.
  - Lines 237-238: `_resolve_replay_base_ref()` falls through multiple candidates: `SPECDEV_REPLAY_BASE_REF` env var → git upstream branch → `origin/main` → `origin/master` → `main` → `master` → current branch. Different developer setups resolve to different base refs, producing different sets of E550 errors for the same artifacts.
- `tools/specdev_tools/validation/validate.py` (lines 244-253) — `SPECDEV_WARNINGS_AS_ERRORS` behavior:
  - Lines 246-247: When set, W560 traceability gaps are promoted to E560 errors. When not set, these gaps pass as warnings only, which are filtered out at line 224 (`failures.extend(e for e in tc_errors if not e.startswith("W"))`). This means **traceability gaps are invisible unless the env var is explicitly set**.
  - The same artifact can pass validation locally (no env var) and fail in CI (env var set), with no indication to the developer that they are running under weaker validation.
- `tools/specdev_tools/validation/validate.py` (lines 395-403) — `_is_git_repo()` check:
  - Shells out to `git rev-parse` with a 10-second timeout. If git is not installed, not in PATH, or the timeout fires, returns `False` — silently disabling all git-dependent validation (forward replay, semantic coverage regression).
- `tools/specdev_tools/validation/forward_replay_check.py` (lines 69-85) — `_changed_files()`:
  - Runs `git diff --name-only` with a 30-second timeout. On timeout or any git error, returns an empty list and an error string. When `diff_error_mode` is `"ignore"` (the local default), this silently skips all replay checks.
- Document the full matrix of environment-dependent behavior: For each env var (`SPECDEV_WARNINGS_AS_ERRORS`, `SPECDEV_REPLAY_DIFF_ERROR_MODE`, `SPECDEV_REPLAY_BASE_REF`, `CI`) and each runtime condition (git available, git repo, remote refs exist), document what validation checks are enabled vs disabled.

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| Forward replay silently disabled locally | `validation/validate.py:233-236` | Non-CI, non-git defaults to `mode="ignore"`, skipping all E550 checks |
| Traceability gaps invisible without env var | `validation/validate.py:224,244-253` | W560 gaps filtered out unless `SPECDEV_WARNINGS_AS_ERRORS=1` is set |
| Base ref resolution is non-deterministic | `validation/validate.py:406-419` | `_resolve_replay_base_ref()` produces different results across developer setups |

---

### Area 11: Submodule Integration Path Integrity

**Question**: Do git-aware validators operate against the correct git repository when the toolkit is deployed as a submodule inside a parent project (the primary deployment model)?

**Context**: The toolkit is designed to be vendored at `parent_project/devspec_toolkit/` as a git submodule. Specs live at `parent_project/spec/`, not inside the toolkit. The CLI is invoked with `--repo-root ./devspec_toolkit`, making `repo_root` point to the toolkit directory. But git-aware validators shell out to `git` from `repo_root`, which queries the **toolkit's** git history — not the parent project's where spec changes are tracked.

**What to examine**:
- `tools/specdev_tools/validation/forward_replay_check.py` (lines 21-22, 44, 69-71) — The core of the problem:
  - Line 21-22: `root = Path(os.path.abspath(repo_root))` — sets the git working directory to the toolkit submodule.
  - Line 44: `_step_exists(root / "spec", downstream)` — checks for spec files at `toolkit/spec/`, not `parent_project/spec/`. In the submodule model, the toolkit's `spec/` contains sample/test artifacts, not the project's actual specs. This check either finds the wrong files or finds nothing.
  - Lines 69-71: `_changed_files()` runs `git -C <toolkit_root> diff --name-only`. The diff output reflects changes to the **toolkit** repository, not the parent project. Spec file changes (`spec/04_fr_list.json`) are tracked in the parent project's git, not the submodule's. **Forward replay detection is functionally disabled in the submodule deployment model.**
- `tools/specdev_tools/validation/validate.py` (lines 226-238) — The validate_dir orchestrator:
  - Lines 226-228: Loads `step_order.json` from `root / "tools" / "step_order.json"` — this resolves correctly (toolkit/tools/).
  - Lines 231-238: Calls `check_forward_replay(repo_root, ...)` passing the toolkit root. Forward replay runs git operations against the toolkit's git history.
  - Lines 395-403: `_is_git_repo(root)` checks the toolkit directory. Since the toolkit IS a git submodule, this returns `True` — but the subsequent git operations query the wrong repository's state.
  - Lines 406-419: `_resolve_replay_base_ref(root)` queries the toolkit's upstream branch and remote refs. The toolkit's `origin/main` is the toolkit's GitHub repo, not the parent project's working branch.
- `tools/specdev_tools/validation/seed_lint.py` (lines 76-90) — **Exception: handles this correctly**. The `_project_root_from_spec_dir()` function derives the project root from the spec_dir parent directory, not from repo_root. Verify whether other validators could adopt this pattern.
- `scripts/init_project.py` (lines 13-16, 77) — The generated pre-commit hook and CI workflow both pass `--repo-root ./devspec_toolkit`. Verify that all CLI commands receiving this flag route the correct root to git-aware checks.
- Check whether `traceability_closure.py`, `hallucination_lint.py`, and `spec_quality_lint.py` have any git-dependent behavior that would be affected by the repo_root mismatch. These validators receive `spec_dir` separately and should be immune — verify.

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| Forward replay runs git from toolkit root | `validation/forward_replay_check.py:69-71` | `git diff` executes from submodule directory; parent project spec changes are invisible |
| Spec existence check uses wrong path | `validation/forward_replay_check.py:44` | `_step_exists(root / "spec", ...)` checks toolkit/spec/ not parent_project/spec/ |
| Base ref resolves to toolkit's remote | `validation/validate.py:406-419` | `origin/main` in submodule context points to toolkit repo, not parent project |

---

### Area 12: Toolkit Discovery Deficit in Prompts

**Question**: Do the static prompts (`prompts/prompt_NN_*.md`) give the AI agent sufficient awareness of the toolkit infrastructure — downstream consumers, validation rules, pipeline DAG — to generate artifacts optimized for the full pipeline, or is the AI effectively flying blind past the single prompt it receives?

**Context**: When a user runs step 04, the AI receives `prompt_04_functional_requirements.md` and is told to read the schema, upstream artifacts, seeds, shared expectations, and the canonical registry. That is the AI's entire awareness of the toolkit. It has **zero knowledge** of:
- What downstream steps consume its output and what they extract (despite this being machine-readable in `step_order.json` step_metadata)
- What validation rules will be applied to its output (despite 13+ validators existing)
- The full error taxonomy (E1xx–E5xx, ~40+ codes) and what triggers each code
- The pipeline DAG and waterfall policy
- What other step prompts expect from artifacts this step produces

The data to close this gap already exists in `step_order.json` (step_metadata with extraction_intent per step) and the validation suite. The prompts simply don't surface it.

**What to examine**:

#### 12a. Downstream Consumer Awareness
- `tools/step_order.json` (lines 309-509) — The `step_metadata` section declares `required_spec_inputs` and `extraction_intent` for every step. For each step N, the `extraction_intent` entries in downstream steps describe exactly what those steps will extract from step N's output.
- For each prompt (`prompts/prompt_NN_*.md`):
  - Does the prompt tell the AI which downstream steps consume its output? (Expected: no prompt currently does this.)
  - Does the prompt tell the AI *what* downstream steps will extract? (Expected: no prompt currently does this.)
  - Example: `step_order.json` declares that 12 downstream steps consume step 04's output (steps 05, 06, 08, 09, 11, 13, 13a, 14, 15, 16, 16a, 16c). Step 05's extraction_intent says "Extract FR behaviors and acceptance criteria for API design." Step 08 says "Extract acceptance criteria to derive fixture scenarios." Does `prompt_04_functional_requirements.md` mention any of this? (Expected: no.)
- Quantify the gap: For each step, count how many downstream consumers exist in `step_metadata` vs how many the prompt mentions.

#### 12b. Validation Awareness
- For each prompt, check whether it describes the specific validation checks that will run on the output:
  - Does it mention the error codes (E200, E210, E510, E530, E560) that apply to this step's output?
  - Does it describe what each validator checks in concrete terms?
  - Or does it just say "run validate" without specifying what the validator will look for?
- Cross-reference: For each step, map the validators that fire on its output (from `validate.py` routing logic) and compare against what the prompt tells the AI about validation.
- Example: Step 04's output is checked by schema validation (E200), canonical drift (E210), placeholder scan (E510), hallucination lint (E530), and traceability closure (E560). Does `prompt_04_functional_requirements.md` mention these? (Expected: it mentions "run validate" but not the specific checks.)

#### 12c. Enrichment Mechanism Feasibility
- `tools/specdev_tools/generation/prompt_generator.py` — Already has `{{VAR}}` template rendering, `_extract_required_fields()`, and context injection for migration prompts. Assess whether this infrastructure can be extended for static prompt enrichment.
- `tools/step_order.json` — Assess whether `step_metadata.extraction_intent` is complete and accurate for all 22 steps. Are any extraction_intent entries missing, vague, or outdated?
- Propose a mechanism for build-time prompt enrichment:
  - A CLI command (e.g., `specdev prompt-enrich`) that reads `step_order.json` and the validator registry, then injects `<!-- TOOLKIT_CONTEXT:...:START/END -->` marked sections into each prompt with downstream consumer tables and validation gate summaries.
  - A pre-commit hook that triggers enrichment when source files (`step_order.json`, validators, schemas, canonical registry) are staged.
  - Idempotent injection using marker comments so re-runs replace only injected content.
- Assess the token cost: How many lines would the injected sections add per prompt? Is the additional context worth the token cost vs the improvement in artifact quality?

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| Zero downstream consumer awareness | All `prompts/prompt_*.md` | No prompt tells the AI which steps consume its output or what they extract; `step_order.json` step_metadata has this data for all 22 steps |
| Validation described as "run validate" only | All `prompts/prompt_*.md` | Prompts say to run the validator but don't describe the ~6 specific checks (E200, E210, E510, E530, E560, etc.) that apply to each step's output |
| Extraction intent already machine-readable | `tools/step_order.json:309-509` | `step_metadata.extraction_intent` describes what each downstream step extracts from each upstream artifact — this data exists but is never surfaced to prompts |
| Template rendering infrastructure exists | `tools/specdev_tools/generation/prompt_generator.py` | `render_template()`, `_extract_required_fields()`, and `{{VAR}}` substitution already work for migration prompts; could be extended for static prompt enrichment |

---

### Area 13: Schema–Prompt Contract Misalignment

**Question**: Does each step's JSON Schema enforce the same requirements that its prompt demands, or is the schema systematically weaker than the prompt contract — allowing artifacts to pass validation while violating prompt instructions?

**Context**: The pipeline has three layers of enforcement: (1) the prompt instructs the AI what to produce, (2) the schema validates the JSON structure, (3) per-step validators run additional checks. If the prompt demands a field or constraint that the schema doesn't enforce, the requirement is only as strong as the AI's compliance — it becomes an honor-system rule with no automated verification. This is the opposite of deterministic.

**What to examine**:

#### 13a. Required vs Optional Field Alignment
For each step schema (`schema/NN_*.schema.json`), compare the schema's `required` array against what the corresponding prompt treats as mandatory. Look for fields that:
- The prompt says MUST be present, but the schema marks as optional (not in `required`).
- The prompt says are conditional ("include when X"), but the schema marks as required always.

**Confirmed examples** (use these as anchors, then check ALL 22 step schemas):
- `schema/00_charter.schema.json`: `stakeholders` — prompt says "Stakeholders include at least product/eng/ops/security roles with distinct needs" (Self-Audit Gate), schema does NOT list `stakeholders` in `required` (lines 182-193).
- `schema/00_charter.schema.json`: `user_segments` — prompt says "User segments include JTBD/pains/gains for primary personas" (Self-Audit Gate), schema does NOT list `user_segments` in `required`.
- `schema/04_fr_list.schema.json`: `trace` on FR items — prompt says "Traces to capability and (if known) API/NFR" and "include at least one reference to connect artifacts across steps" (Output Rules #7), schema does NOT list `trace` in the FR item's `required` array (lines 89-94).

#### 13b. Constraint Strength Alignment
For each step schema, compare numeric constraints (`minItems`, `minLength`, `minimum`, `maximum`, `pattern`, `enum`) against what the prompt requires:
- Does the schema enforce the same minimums the prompt states?
- Does the schema enforce `minItems` on arrays the prompt says must be non-empty?

**Confirmed examples**:
- `schema/00_charter.schema.json`: `success_metrics` — prompt says "≥2 metrics" (Self-Audit Gate line 71), schema has NO `minItems` on the array. One metric passes validation.
- `schema/04_fr_list.schema.json`: `acceptance_criteria` — prompt says "top FRs include ≥2" acceptance criteria (Self-Audit Gate line 65), schema has `minItems: 1` (line 48). One criterion passes validation.
- `schema/00_charter.schema.json`: `in_scope` and `out_of_scope` — prompt says "≥3 items each" (Self-Audit Gate line 68), schema has `minItems: 3` (lines 32, 36). **This one aligns** — use it as a positive control.

#### 13c. Cross-Schema Consistency
- Do all 22 step schemas use `$ref` to `schema/core/` for shared types (atoms, collections), or do some inline their own definitions?
- Are there steps that define local versions of types that exist in `schema/core/` (e.g., a local `traceRef` definition instead of referencing `collections.schema.json#traceRef`)?
- Is `additionalProperties: false` set consistently on all objects in all schemas? (Note: grep shows 143 occurrences across 24 files — verify there are no objects missing it.)

#### 13d. Schema-Validator Gap
- For each step, compare what the schema enforces vs what the per-step validator (`validation/validators/step_NN.py`) checks. Are validators checking things the schema already enforces (redundant), or are they checking things the schema cannot express (complementary)?
- Identify step validators that are thin (< 25 LOC) for complex steps. These are steps where the schema is likely the only enforcement, and any prompt requirement not in the schema is unenforced.

**What to recommend**: For each misalignment found, determine whether:
- (a) The **schema should be tightened** to match the prompt (add to `required`, add `minItems`, etc.)
- (b) The **prompt should be relaxed** to match the schema (the schema is intentionally flexible)
- (c) A **per-step validator** should enforce the prompt requirement that the schema cannot express (e.g., conditional requirements, cross-field constraints)

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| `stakeholders` optional in schema, mandatory in prompt | `schema/00_charter.schema.json:182-193` | Not in `required` array; prompt Self-Audit Gate treats as mandatory |
| `user_segments` optional in schema, mandatory in prompt | `schema/00_charter.schema.json:182-193` | Not in `required` array; prompt Self-Audit Gate treats as mandatory |
| `success_metrics` no minItems, prompt says ≥2 | `schema/00_charter.schema.json:99-150` | Array has no `minItems`; prompt says "≥2 metrics" |
| `trace` optional on FR items, prompt says mandatory | `schema/04_fr_list.schema.json:89-94` | Not in FR item `required`; prompt Output Rules #7 says "include at least one reference" |
| `acceptance_criteria` minItems:1, prompt says ≥2 for top FRs | `schema/04_fr_list.schema.json:48` | Schema allows 1; prompt says top FRs should have ≥2 |

---

## Deliverables

You must produce TWO deliverables in a single response:

### Part A: Detailed Review Report

For each of the 13 areas, produce:

```markdown
## Area N: [Title]

### Findings
- **[Finding ID: A-N-01]**: [Description of finding]
  - **File**: [exact file path]
  - **Line(s)**: [line numbers]
  - **Evidence**: [what you observed — quote relevant code]
  - **Impact**: [what breaks or degrades because of this gap]
  - **Severity**: Critical | High | Medium | Low

### Verified Starting Points Status
- [Gap from table]: [CONFIRMED / RESOLVED / MODIFIED — with evidence]

### Discovered Gaps (not in starting points)
- [Any additional gaps you found during exploration]
```

**Rules for Part A**:
1. Every finding must include an exact file path and line number(s).
2. Every finding must include a direct code quote as evidence.
3. Do not speculate — if you cannot verify a gap, state that explicitly.
4. Classify severity based on pipeline impact: Critical = breaks determinism; High = allows silent data loss; Medium = allows drift; Low = hygiene/naming.

### Part B: Dependency-Ordered Implementation Plan

Produce a sequenced list of implementation tasks with **zero rework** — no task should require modifying files changed by a later task.

```markdown
## Implementation Plan

### Task N: [Title]
- **Priority**: P0 (blocker) | P1 (high) | P2 (medium) | P3 (low)
- **Depends on**: [Task IDs that must complete first, or "None"]
- **Files to modify**: [exact paths]
- **Changes**:
  1. [Specific change with file:line reference]
  2. [Specific change with file:line reference]
- **Acceptance criteria**:
  - [ ] [Testable criterion]
  - [ ] [Testable criterion]
- **Addresses findings**: [Finding IDs from Part A]
```

**Rules for Part B**:
1. **Strict dependency ordering**: If Task 5 modifies `registry.py` and Task 8 depends on a function added in Task 5, Task 8 must list Task 5 as a dependency.
2. **One logical change per task**: Do not bundle unrelated changes. A task can touch multiple files only if they are part of the same logical change.
3. **Every finding from Part A must map to at least one task in Part B**.
4. **Acceptance criteria must be machine-verifiable**: "Run `pytest tests/test_X.py` and all pass", not "code looks correct".
5. **Include test tasks**: For every code change, include the corresponding test file modifications or new test files.
6. **P0 tasks first**: Arrange by priority, then by dependency order within each priority level.

---

## Execution Instructions

1. **Read before writing**: Read every file referenced in the Verified Starting Points before making any claims. Use the exact paths provided in the Repository Context section.
2. **Verify, then extend**: Confirm each starting point, then explore adjacent code for additional gaps.
3. **Cross-reference prompts ↔ validators ↔ schemas**: For every step, compare what the prompt requires, what the validator checks, and what the schema enforces. Gaps between these three are findings.
4. **Check `step_order.json` against prompts**: For every step, verify that the prompt's upstream input instructions match the step's declared dependencies.
5. **Run the tools if possible**: Execute `./tools/run_specdev.sh validate-all spec --repo-root .` and `./tools/run_specdev.sh canonical-integrity spec --repo-root .` to see current state.
6. **Be exhaustive on Area 6 (Prompt Hardening)**: This is the highest-impact area. Every prompt must be reviewed individually — do not sample or skip.

---

## Anti-Patterns to Avoid

- **Do not speculate**: If you cannot read a file or verify a gap, say so explicitly. Do not invent findings.
- **Do not propose architectural rewrites**: The goal is targeted fixes within the existing architecture, not redesign.
- **Do not conflate areas**: Each finding belongs to exactly one area. If a finding spans areas, file it under the most impactful one and cross-reference.
- **Do not ignore thin validators**: A 16-line validator for a complex step (e.g., Invariants, NFRs) is almost certainly insufficient. Identify what's missing.
- **Do not treat warnings as acceptable**: W110/W120 warnings for deprecated aliases that have no escalation path are effectively permission to use deprecated terms forever.
- **Do not confuse "fails silently" with "works correctly"**: An invariant that returns `None` and is recorded as `result: false` is not a passing check — it is an undetected evaluation failure. Silent fallthrough is a bug, not a feature.
- **Do not trust self-reported metadata**: When an AI agent sets `preflight_passed: true`, that claim must be independently verifiable. A self-certification with no cross-check is not a quality gate. More fundamentally: if a field is never read by any tool, validator, or downstream step, it is dead weight regardless of how well-structured its schema definition is.
- **Do not assume consistent environments**: If a validation check only runs in CI but not locally, developers will discover failures late. Document every environment-dependent behavior path explicitly.
- **Do not test only from the toolkit root**: The primary deployment model is as a submodule. If a validator works when CWD is the toolkit but breaks when CWD is the parent project with `--repo-root ./devspec_toolkit`, it is broken in production.
- **Do not assume the AI knows the toolkit**: The AI generating an artifact sees only the prompt, the schema, and upstream artifacts it is told to read. It has no awareness of downstream consumers, validation rules, error codes, or the pipeline DAG unless the prompt explicitly surfaces this information. If data exists in `step_order.json` that would improve artifact quality, it should be in the prompt.
- **Do not assume schema validation catches prompt requirements**: If a prompt says "include ≥2 acceptance criteria" but the schema only enforces `minItems: 1`, the requirement is unenforceable by automation. Prompt requirements without schema backing are honor-system rules. Audit every prompt requirement against its schema constraint.

</review_prompt>
