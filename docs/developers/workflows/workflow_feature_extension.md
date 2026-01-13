# Workflow: Feature Extension (The Sequential Cycle)

> [!NOTE]
> **Work In Progress**: This document is a **preliminary draft** for rough guidance and is still a work in progress.


This guide describes the **Standard Operating Procedure (SOP)** for adding new capabilities to a specced project.
It strictly follows the **Numerical Spec Sequence**: You must check every file from `00` to `14` before you execute code in `16`.

## The Golden Rule: "Spec First, Code Second"
We never skip steps. If a feature is too small for a step, we explicitly explicitly acknowledge it (Step Skipped).

---

## Phase 1: The Intent (Define)
*Files: Docs -> 00 -> 01 -> 02 -> 03 -> 04*

1.  **Step 00: Seed Docs & Charter**:
    *   **Check**: Does this feature change the `docs/project_overview.md` (Success Metrics/Users)?
    *   **Action**: Update the Markdown first, then update `spec/00_charter.json`.
    *   *Reference*: `prompts/prompt_00_project_charter.md`.
2.  **Step 01: Capabilities & Stack**:
    *   **Check**: Does this introduce a new Tech Stack element (e.g., Redis)?
    *   **Action**: Update `docs/tech_stack.md` first, then update `spec/01_capabilities.json`.
    *   *Reference*: `prompts/prompt_01_capabilities.md`.
3.  **Step 02: System Sketch**: Does this add a new Component? Update the diagram.
    *   *Reference*: `prompts/prompt_02_system_sketch.md`.
4.  **Step 03: Glossary**: New terms? Define them.
    *   *Reference*: `prompts/prompt_03_glossary.md`.
5.  **Step 04: Functional Requirements**: **CRITICAL**. Add the atomic FRs here.
    *   *Reference*: `prompts/prompt_04_functional_requirements.md`.
    *   *Constraint*: Must link back to Capability ID (`trace_refs`).

**User Action:**
> **PROMPT:**
> I am adding feature [Name].
> 1. Check `docs/project_overview.md` and `docs/tech_stack.md`. Do they need updates?
> 2. Iterate through Specs 00, 01, 02, 03, and 04.
> Ask me if updates are needed for each.
> Output the updated JSON for any file that changes.

---

## Phase 2: The Contract (Design)
*Files: 05 -> 06 -> 07 -> 08*

1.  **Step 05: Interfaces**: Define the new API endpoints or Function Signatures.
    *   *Reference*: `prompts/prompt_05_interface_contracts.md`.
    *   *Constraint*: Must trace to `FR-ID`.
2.  **Step 06: Invariants**: Defines the "Musts" (Business Rules).
    *   *Reference*: `prompts/prompt_06_invariants.md`.
3.  **Step 07: NFRs**: Define performance/security constraints.
    *   *Reference*: `prompts/prompt_07_nfrs.md`.
4.  **Step 08: Fixtures**: Add sample data for the new entities.
    *   *Reference*: `prompts/prompt_08_fixtures.md`.

**User Action:**
> **PROMPT:**
> Based on `FR-NEW` (Step 04), help me design the contracts.
> Iterate through Steps 05, 06, 07, 08.
> Update `spec/05_interface_contracts.json` with new endpoints.
> Update `spec/08_fixtures.json` with new data samples.

---

## Phase 3: The Governance (Rules)
*Files: 09 -> 10 -> 11 -> 12 -> 13*

1.  **Step 09**: (Reserved for per-feature Implementation Plans - generated later).
2.  **Step 10: Governance**: Any new compliance needs?
3.  **Step 11: Red Team**: **CRITICAL**. Add potential security threats for the new feature.
    *   *Reference*: `prompts/prompt_11_redteam.md`.
4.  **Step 12: CI Gates**: Do we need a new pipeline check?
    *   *Reference*: `prompts/prompt_12_ci_gates.md`.
5.  **Step 13: Extensions**: Is this a Plugin/Extension?
    *   *Reference*: `prompts/prompt_13_extension_generator.md`.

---

## Phase 4: The Plan (Schedule)
*Files: 14*

Only NOW do we schedule the work.

**Step 14: Roadmap**
*Reference*: `prompts/prompt_14_roadmap.md`.

**User Action:**
> **PROMPT:**
> The specs (00-13) are updated.
> Add a new item to `spec/14_roadmap.json`.
> ID: `step-[feature-name]`.
> Title: One User Story.
> Tasks: Atomic sub-tasks.
> Status: `planned`.

---

## Phase 5: The Execution (Trinity Loop)
*Files: 16a -> 16b -> 16c*

Now we run the machine.

### Step 16a: Planner
*Reference*: `prompts/prompt_16a_impl_planner.md`.

**User Action:**
> **PROMPT:**
> Run Step 16a.
> Target: `step-[feature-name]` (from Roadmap).
> Context: Read the updated Specs 04, 05, 06, 08, 11.
> Output: `spec/impl_context/step-[feature-name].json`.

### Step 16b: Coder
*Reference*: `prompts/prompt_16b_impl_coder.md`.

**User Action:**
> **PROMPT:**
> Run Step 16b.
> Input: `spec/impl_context/step-[feature-name].json`.
> Execute the Checklist.

### Step 16c: Reviewer
*Reference*: `prompts/prompt_16c_impl_reviewer.md`.

**User Action:**
> **PROMPT:**
> Run Step 16c.
> Verify the implementation against the Checklist.

---

## Completion
Update `spec/19_spec_drift.json` to monitor the new feature.
