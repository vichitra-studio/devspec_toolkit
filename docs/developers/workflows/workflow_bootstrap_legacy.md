# Workflow: Bootstrapping Legacy Projects (The Hybrid Approach)

> [!NOTE]
> **Work In Progress**: This document is a **preliminary draft** for rough guidance and is still a work in progress.


This guide describes the rigorous operating procedure for onboarding an existing **Legacy (Brownfield) Codebase** into the DevSpec Toolkit.

## The Goal
To reverse-engineer a **100% Complete Spec Suite (Steps 00-12)** using a **Prose-First** strategy:
1.  **Draft the Prose**: Create human-readable `docs/*.md` files using Seed Templates.
2.  **Generate the Spec**: Compile those docs into machine-readable `spec/*.json` files.
3.  **Excavate the Code**: Rigorously scan the codebase to backfill the contracts.

---

## Phase 1: The Foundation (Prose & Stack)

### Step 1.1: Project Overview (The "Why")
*Target: `docs/project_overview.md` -> `spec/00_charter.json`*
*Seed: `devspec_toolkit/seed_templates/seed_overview.md`*

We start by capturing the pure business intent in prose.

**User Action:**
> **PROMPT:**
> Act as the **Project Lead**.
> 
> **Context**:
> - Read `devspec_toolkit/seed_templates/seed_overview.md`.
> 
> **Task**:
> 1. Interview me to fill out the `seed_overview.md` template.
> 2. Focus on "Problem Statement", "Users", and "Success Metrics".
> 3. Once complete, save the file as `docs/project_overview.md`.
> 
> **Output**: The markdown content.

**User Action (Convert to Spec):**
> **PROMPT:**
> Now convert `docs/project_overview.md` into `spec/00_charter.json`.
> Use the schema defined in `devspec_toolkit/prompts/prompt_00_project_charter.md`.

### Step 1.2: The Tech Stack (The "How")
*Target: `docs/tech_stack.md` -> `spec/01_capabilities.json`*
*Seed: `devspec_toolkit/seed_templates/seed_tech_stack.md`*

We define the stack by verifying the code reality against the template.

**User Action:**
> **PROMPT:**
> Act as the **Software Archaeologist**.
> 
> **Context**:
> - Read `devspec_toolkit/seed_templates/seed_tech_stack.md`.
> - **Deep Scan**: Read `package.json`, `pyproject.toml`, `Dockerfile`, `go.mod`, or any infra-as-code files.
> 
> **Task**:
> 1. Analyze the codebase to fill out `seed_tech_stack.md`.
> 2. Ask me to verify any ambiguous versions (e.g., "Is this Postgres 14 or 15?").
> 3. Save the result as `docs/tech_stack.md`.
> 
> **Output**: The markdown content.

**User Action (Convert to Spec):**
> **PROMPT:**
> Convert `docs/tech_stack.md` into `spec/01_capabilities.json`.
> Use the schema defined in `devspec_toolkit/prompts/prompt_01_capabilities.md`.

---

## Phase 2: The Architecture & Requirements

### Step 2.1: System Sketch
*Target: `spec/02_system_sketch.json`*
*Reference: `devspec_toolkit/prompts/prompt_02_system_sketch.md`*

**User Action:**
> **PROMPT:**
> Act as the **Software Architect**.
> 
> **Task**:
> 1. Scan the `src/` directory to map the High-Level Components.
> 2. Create a Mermaid diagram of the existing system.
> 3. Output valid JSON for `spec/02_system_sketch.json`.

### Step 2.2: Glossary
*Target: `spec/03_glossary.json`*
*Reference: `devspec_toolkit/prompts/prompt_03_glossary.md`*

**User Action:**
> **PROMPT:**
> Scan the **Entire Codebase** for ubiquitous domain terms (Class Names, DB Tables, shared constants).
> Define the top 20 terms in `spec/03_glossary.json`.

### Step 2.3: Functional Requirements
*Target: `spec/04_functional_requirements.json`*
*Reference: `devspec_toolkit/prompts/prompt_04_functional_requirements.md`*

**User Action:**
> **PROMPT:**
> **Context**:
> - Read `docs/project_overview.md` (created in Step 1.1).
> - Read the root `README.md`.
> 
> **Task**:
> 1. Extract every Feature and User Story.
> 2. Formalize them into `spec/04_functional_requirements.json` (ID: `FR-XXX`).

---

## Phase 3: The Contracts (Exhaustive Excavation)

### Step 3.1: Interface Contracts (APIs)
*Target: `spec/05_interface_contracts.json`*
*Reference: `devspec_toolkit/prompts/prompt_05_interface_contracts.md`*

**User Action:**
> **PROMPT:**
> Act as the **Contract Auditor**.
> 
> **Task**:
> **Exhaustive Scan**: You must traverse every file in the API layer (Controllers, Routers, Resolvers).
> 1. Identify EVERY public endpoint/method.
> 2. Extract the exact Input/Output Checksums (Pydantic models, Types).
> 3. Generate `spec/05_interface_contracts.json`.
> 4. **Constraint**: Every `trace_ref` must link to an FR from derived in Step 2.3.

### Step 3.2: Invariants & NFRs
*Target: `06`, `07`*

**User Action:**
> **PROMPT:**
> Scan `tests/`, `validators/`, and `config/`.
> 1. Extract Business Rules -> `spec/06_invariants.json`.
> 2. Extract System Limits -> `spec/07_nfrs.json`.

### Step 3.3: Data Fixtures
*Target: `08`*

**User Action:**
> **PROMPT:**
> Scan `db/models` and `tests/conftest`.
> Create concrete JSON examples for every core entity in `spec/08_fixtures.json`.

---

## Phase 4: The Constitution (Process)
*Target: `09` (Empty), `10`, `11`, `12`*

**User Action:**
> **PROMPT:**
> Generate default governance files (`10`, `11`, `12`).

## Completion & Next Steps
1.  Run `python -m specdev_tools.cli validate-all --repo-root .` to confirm coverage.
2.  **You are now Bootstrapped.**
3.  To add a new feature, proceed to the **[Feature Extension Workflow](./workflow_feature_extension.md)**.
