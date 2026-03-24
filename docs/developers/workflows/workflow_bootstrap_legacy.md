# Workflow: Bootstrapping Legacy Projects (The Hybrid Approach)

This guide describes the rigorous operating procedure for onboarding an existing **Legacy (Brownfield) Codebase** into the DevSpec Toolkit.

## Prerequisites

Activate the virtualenv before running any CLI commands:

```bash
source devspec_env/bin/activate
```

Alternatively, `./tools/run_specdev.sh` enforces virtualenv usage automatically — you can run it without activating the venv first.

---

## The Goal

To reverse-engineer a **100% Complete Spec Suite (Steps 00–16c)** using a **Prose-First** strategy:

1. **Prepare the Seeds**: Fill out `docs/seed/seed_overview.md` and `docs/seed/seed_tech_stack.md` with project-specific context.
2. **Generate the Spec**: Use canonical prompts at `prompts/prompt_NN_name.md` to emit each `spec/NN_name.json` artifact.
3. **Excavate the Code**: Rigorously scan the codebase to backfill the contracts.

Each spec step uses the **two-phase Clarify/Emit protocol**:

- **Clarify** (if Self-Audit Gate score < 0.9): the AI outputs only short bulleted gap questions. No JSON, no code fences. Stop and wait for answers.
- **Emit**: the AI writes the artifact JSON directly to `spec/NN_name.json`. Do not return fenced JSON as the primary output.

---

## Phase 0: Gap Analysis (Pre-Bootstrap)

Before writing any new content, check which spec artifacts are missing.

```bash
# List all spec artifacts and their validation status
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit

# Check the canonical registry for alignment issues
./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit
```

**Why?**

- `validate-all` will show every missing or invalid artifact, giving you a precise checklist.
- `canonical-integrity` surfaces vocabulary drift before you start filling in new content.

---

## Phase 1: The Foundation (Prose & Stack)

### Step 1.1: Project Overview — `spec/00_charter.json`

*Seed: `docs/seed/seed_overview.md`*

Fill in `docs/seed/seed_overview.md` with the project's problem statement, target users, and success metrics. Then use the canonical prompt to emit the charter artifact.

**User Action:**
> Open `prompts/prompt_00_project_charter.md` in your AI assistant.
>
> **Context to supply**:
> - Content of `docs/seed/seed_overview.md`
> - Any existing `README.md` or product brief
>
> The AI will clarify gaps first (if needed), then emit `spec/00_charter.json` directly.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/00_charter.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit
```

### Step 1.2: Capabilities — `spec/01_capabilities.json`

*Seed: `docs/seed/seed_overview.md`*

Scan `package.json`, `pyproject.toml`, `Dockerfile`, `go.mod`, or any infra-as-code files. Fill in `docs/seed/seed_tech_stack.md` with the verified stack.

**User Action:**
> Open `prompts/prompt_01_capabilities.md` in your AI assistant.
>
> **Context to supply**:
> - Content of `docs/seed/seed_overview.md`
> - Dependency manifests (`package.json`, `pyproject.toml`, etc.)
>
> The AI will clarify ambiguous versions (e.g., "Is this Postgres 14 or 15?"), then emit `spec/01_capabilities.json`.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/01_capabilities.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit
```

> **Commit**: After completing this phase, make a governance-compliant commit per `spec/10_governance.json`.

---

## Phase 2: The Architecture & Requirements

### Step 2.1: System Sketch — `spec/02_system_sketch.json`

*Prompt: `prompts/prompt_02_system_sketch.md`*

**User Action:**
> Open `prompts/prompt_02_system_sketch.md` in your AI assistant.
>
> **Context to supply**:
> - `spec/00_charter.json`, `spec/01_capabilities.json`
> - Directory structure of `src/` or equivalent
>
> The AI maps the high-level components and emits `spec/02_system_sketch.json`.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/02_system_sketch.json --repo-root ./devspec_toolkit
```

### Step 2.2: Delivery Baseline (optional) — `spec/02a_delivery_baseline.json`

*Prompt: `prompts/prompt_02a_delivery_baseline.md`*

Use this step if the project has measurable delivery metrics to capture before Phase I specs are complete.

**User Action:**
> Open `prompts/prompt_02a_delivery_baseline.md` in your AI assistant.
>
> **Context to supply**:
> - Content of `docs/seed/seed_tech_stack.md`
> - Any existing delivery metrics, SLAs, or baseline performance data
>
> The AI captures measurable delivery baselines and emits `spec/02a_delivery_baseline.json`.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/02a_delivery_baseline.json --repo-root ./devspec_toolkit
```

### Step 2.3: Glossary — `spec/03_glossary.json`

*Prompt: `prompts/prompt_03_glossary.md`*

**User Action:**
> Open `prompts/prompt_03_glossary.md` in your AI assistant.
>
> **Context to supply**:
> - Scan results of class names, DB tables, and shared constants from the codebase
>
> The AI defines the top domain terms and emits `spec/03_glossary.json`.

After emitting, promote project-specific terms to the canon registry:

```bash
./tools/run_specdev.sh canon-accept --from spec/03_glossary.json --repo-root ./devspec_toolkit
```

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/03_glossary.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit
```

### Step 2.4: Functional Requirements — `spec/04_fr_list.json`

*Prompt: `prompts/prompt_04_functional_requirements.md`*

**User Action:**
> Open `prompts/prompt_04_functional_requirements.md` in your AI assistant.
>
> **Context to supply**:
> - `spec/00_charter.json`
> - Root `README.md`
> - Any existing feature documentation
>
> The AI extracts every feature and user story, formalizes them into atomic FRs (ID format: `fr-kebab-case`), and emits `spec/04_fr_list.json`.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/04_fr_list.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json
```

> **Commit**: After completing this phase, make a governance-compliant commit per `spec/10_governance.json`.

---

## Phase 3: The Contracts (Exhaustive Excavation)

### Step 3.1: Interface Contracts — `spec/05_interface_contracts.json`

*Prompt: `prompts/prompt_05_interface_contracts.md`*

**User Action:**
> Open `prompts/prompt_05_interface_contracts.md` in your AI assistant.
>
> **Context to supply**:
> - `spec/04_fr_list.json`
> - Full scan of controllers, routers, and resolvers in the API layer
>
> The AI identifies every public endpoint/method, extracts input/output types, and emits `spec/05_interface_contracts.json`.
> Every `trace` field must link to an FR from Step 2.4.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/05_interface_contracts.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json
# Run after Step 08 is complete
./tools/run_specdev.sh fixtures-lint spec --repo-root ./devspec_toolkit
```

### Step 3.2: Invariants — `spec/06_invariants.json`

*Prompt: `prompts/prompt_06_invariants.md`*

**User Action:**
> Open `prompts/prompt_06_invariants.md` in your AI assistant.
>
> **Context to supply**:
> - Scan of `tests/`, `validators/`, and `config/`
>
> The AI extracts business rules and emits `spec/06_invariants.json`.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/06_invariants.json --repo-root ./devspec_toolkit
```

### Step 3.3: NFRs — `spec/07_nfrs.json`

*Prompt: `prompts/prompt_07_nfrs.md`*

**User Action:**
> Open `prompts/prompt_07_nfrs.md` in your AI assistant.
>
> **Context to supply**:
> - Scan of system limits, SLAs, and performance constraints
>
> The AI extracts non-functional requirements and emits `spec/07_nfrs.json`.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/07_nfrs.json --repo-root ./devspec_toolkit
```

### Step 3.4: Data Fixtures — `spec/08_fixtures.json`

*Prompt: `prompts/prompt_08_fixtures.md`*

**User Action:**
> Open `prompts/prompt_08_fixtures.md` in your AI assistant.
>
> **Context to supply**:
> - `db/models`, `tests/conftest`, or equivalent
>
> The AI creates concrete JSON examples for every core entity and emits `spec/08_fixtures.json`.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/08_fixtures.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh fixtures-lint spec --repo-root ./devspec_toolkit
```

> **Commit**: After completing this phase, make a governance-compliant commit per `spec/10_governance.json`.

---

## Phase 4: The Constitution (Process)

*Targets: `09`, `10`, `11`, `12`*

### Step 4.1: Implementation Plan — `spec/09_impl_plan.json`

*Prompt: `prompts/prompt_09_impl_plan.md`*

Use this step to capture milestones and deliverables. Requires `tech_stack` as an object (not array) and `milestones` with a `deliverables` array.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/09_impl_plan.json --repo-root ./devspec_toolkit
```

### Step 4.2: Governance — `spec/10_governance.json`

*Prompt: `prompts/prompt_10_governance.md`*

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/10_governance.json --repo-root ./devspec_toolkit
```

### Step 4.3: Red Team — `spec/11_redteam.json`

*Prompt: `prompts/prompt_11_redteam.md`*

Add potential security threats for the project. `target_ids` must reference API or Component IDs; `mitigations` must be structured objects.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/11_redteam.json --repo-root ./devspec_toolkit
```

### Step 4.4: CI Gates — `spec/12_ci_gates.json`

*Prompt: `prompts/prompt_12_ci_gates.md`*

**User Action:**
> Open each prompt in turn and supply the relevant upstream spec context. Each AI session will clarify gaps then emit the artifact directly.

**Validation ritual after all Phase 4 steps:**
```bash
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh hallucination-lint spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh traceability-check spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh dag-lint --repo-root ./devspec_toolkit
```

> **Commit**: After completing this phase, make a governance-compliant commit per `spec/10_governance.json`.

---

## Phase 5: The Transition (Extension & Roadmap)

*Targets: `13`, `13a`, `14`*

These steps bridge Phase I Discovery into Phase II Implementation. They must be completed before running the Trinity Loop (Steps 16a–16c).

### Step 5.1: Extension Generator — `spec/13_extension_generator.json`

*Prompt: `prompts/prompt_13_extension_generator.md`*

**User Action:**
> Open `prompts/prompt_13_extension_generator.md` in your AI assistant.
>
> **Context to supply**:
> - `spec/04_fr_list.json`, `spec/02_system_sketch.json`, `spec/01_capabilities.json`
> - Any plugin or extension points identified during codebase excavation
>
> The AI identifies all extension points in the system and emits `spec/13_extension_generator.json`.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/13_extension_generator.json --repo-root ./devspec_toolkit
```

### Step 5.2: Completeness Assessment — `spec/13a_completeness_assessment.json`

*Prompt: `prompts/prompt_13a_completeness_assessment.md`*

**User Action:**
> Open `prompts/prompt_13a_completeness_assessment.md` in your AI assistant.
>
> **Context to supply**:
> - All completed Phase I specs (Steps 00–13)
> - `docs/seed/seed_overview.md`
>
> The AI performs a pairwise completeness check across the entire spec suite and emits `spec/13a_completeness_assessment.json`. Address any gaps surfaced before proceeding to Step 14.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/13a_completeness_assessment.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit
```

### Step 5.3: Roadmap — `spec/14_roadmap.json`

*Prompt: `prompts/prompt_14_roadmap.md`*

**User Action:**
> Open `prompts/prompt_14_roadmap.md` in your AI assistant.
>
> **Context to supply**:
> - `spec/09_impl_plan.json`, `spec/04_fr_list.json`, `spec/13a_completeness_assessment.json`
> - `docs/seed/seed_overview.md`
>
> The AI schedules milestones and roadmap items, emitting `spec/14_roadmap.json`.
> Each roadmap item ID uses the format `step-kebab-case`.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/14_roadmap.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
```

> **Commit**: After completing this phase, make a governance-compliant commit per `spec/10_governance.json`.

---

## Phase 6: The Implementation (Scaffold & Trinity Loop)

*Targets: `15`, `16`, `16a`, `16b`, `16c`*

These steps take the fully-bootstrapped spec suite through to working, reviewed implementation. Step 15 generates the project scaffold; Step 16 establishes the Trinity Anchor; Steps 16a–16c iterate as the Trinity Loop until implementation is verified.

### Step 6.1: Scaffold — `spec/15_scaffold.json`

*Prompt: `prompts/prompt_15_scaffold.md`*

**Purpose:** Generate compile-clean service skeletons and route bindings directly from the spec, capturing any manual follow-up required to keep the scaffold aligned. This artifact proves the contracts are implementable and tracks validation tasks before teams start feature work.

**User Action:**
> Open `prompts/prompt_15_scaffold.md` in your AI assistant.
>
> **Context to supply**:
> - `spec/02_system_sketch.json`, `spec/05_interface_contracts.json`, `spec/09_impl_plan.json`
> - `spec/12_ci_gates.json`, `spec/14_roadmap.json`
>
> The AI generates the directory layout, stub files, and test scaffolding, then emits `spec/15_scaffold.json`. After generating the artifact, implement the scaffold manually or using your preferred generator/framework CLI.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/15_scaffold.json --repo-root ./devspec_toolkit
```

### Step 6.2: Trinity Anchor — `spec/16_impl_context.json`

*Prompt: `prompts/prompt_16_impl_context.md`*

**Purpose:** Create or update the **canonical Step 16 anchor** — the root reference for the Trinity Loop. It summarizes the current execution scope, declares traceable checklist items for the active implementation cycle, records documentation impact decisions and spec provenance, and acts as the union/root of all active milestone implementation contexts (16a/16b/16c).

**User Action:**
> Open `prompts/prompt_16_impl_context.md` in your AI assistant.
>
> **Context to supply**:
> - `spec/14_roadmap.json` (active milestone, tasks, fr_refs)
> - `spec/04_fr_list.json`, `spec/05_interface_contracts.json`
> - `spec/08_fixtures.json`, `spec/09_impl_plan.json`
>
> The AI produces the root Trinity Anchor artifact and emits `spec/16_impl_context.json`.

**Validation ritual:**
```bash
./tools/run_specdev.sh validate spec/16_impl_context.json --repo-root ./devspec_toolkit
```

### Steps 6.3–6.5: The Trinity Loop (16a / 16b / 16c)

The Trinity Loop iterates over each implementation milestone. All three steps operate on milestone-scoped execution files in `spec/impl_context/`, anchored to `spec/16_impl_context.json`. Loop back to 16a if the reviewer returns an unverified verdict.

#### Step 6.3: Impl Planner — `spec/impl_context/{step_id}.json`

*Prompt: `prompts/prompt_16a_impl_planner.md`*

**Purpose:** Produce a **machine-checkable blueprint** for implementation using the Checklist-Driven Architecture. Every piece of work must be traceable (linked to a specific spec requirement with commit hash), atomic (one checklist item = one testable behavior), explicit (zero "common sense" references), and evidence-bound (every checklist item has a concrete `linked_test_expectation`).

**User Action:**
> Open `prompts/prompt_16a_impl_planner.md` in your AI assistant.
>
> **Context to supply**:
> - `spec/16_impl_context.json` (Trinity Anchor scope)
> - `spec/14_roadmap.json` (active milestone tasks and fr_refs)
> - `spec/04_fr_list.json`, `spec/05_interface_contracts.json`
>
> The AI creates or updates `spec/impl_context/{step_id}.json` with the plan and checklist for the coding agent.

#### Step 6.4: Impl Coder — `spec/impl_context/{step_id}.json`

*Prompt: `prompts/prompt_16b_impl_coder.md`*

**Purpose:** Execute the plan defined in Step 16a. This step acts as the "Builder" that turns the Plan into Reality (Code + Configs + Docs), ensuring rigor and adherence to the specified file boundaries and test contracts.

**User Action:**
> Open `prompts/prompt_16b_impl_coder.md` in your AI assistant.
>
> **Context to supply**:
> - `spec/impl_context/{step_id}.json` (the Plan from 16a)
> - The actual codebase files targeted by `plan.summary.target_file_patterns`
>
> The AI writes code files and updates the artifact's `execution` section. If ambiguities are found, it returns an artifact with `emergent_ambiguities` and no code changes — resolve them and re-run 16a.

#### Step 6.5: Impl Reviewer — `spec/impl_context/{step_id}.json`

*Prompt: `prompts/prompt_16c_impl_reviewer.md`*

**Purpose:** Audit the implementation for completeness, quality, and rigorous adherence to the spec. This step acts as the "Gatekeeper" holding the "Definition of Done" for Code, Security, and Delivery before the cycle closes.

**User Action:**
> Open `prompts/prompt_16c_impl_reviewer.md` in your AI assistant.
>
> **Context to supply**:
> - `spec/impl_context/{step_id}.json` (Plan + Execution)
> - The actual codebase for the implemented milestone
>
> The AI audits the implementation against the plan and spec. If `verdict` is `verified`, it also updates `spec/14_roadmap.json` and `spec/09_impl_plan.json` to set the milestone's status to `done`. If unverified, loop back to Step 16a with the surfaced remediation tasks.

**Validation ritual after each Trinity Loop iteration:**
```bash
./tools/run_specdev.sh validate spec/16_impl_context.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh traceability-check spec --repo-root ./devspec_toolkit
```

> **Commit**: After completing this phase, make a governance-compliant commit per `spec/10_governance.json`.

---

## Completion & Next Steps

1. Run the full validation suite to confirm complete coverage across all phases:
   ```bash
   ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
   ./tools/run_specdev.sh traceability-check spec --repo-root ./devspec_toolkit
   ./tools/run_specdev.sh hallucination-lint spec --repo-root ./devspec_toolkit
   ./tools/run_specdev.sh dag-lint --repo-root ./devspec_toolkit
   ./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit
   ```
2. Commit with a governance-compliant message (see `spec/10_governance.json` for the required pattern).
3. **You are now fully bootstrapped through implementation.** Steps 13, 13a, and 14 are covered in Phase 5; Steps 15–16c are covered in Phase 6.
4. To add a new feature or begin a new implementation cycle, proceed to the **[Feature Extension Workflow](./workflow_feature_extension.md)**.
