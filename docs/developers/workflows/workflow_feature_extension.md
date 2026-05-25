# Workflow: Feature Extension (The Sequential Cycle)




This guide describes the **Standard Operating Procedure (SOP)** for adding new capabilities to a specced project.
It strictly follows the **Numerical Spec Sequence**: You must check every file from `00` to `16c` (steps: `00, 01, 02, 02a, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16, 16a, 16b, 16c`) before you execute the Trinity Loop in `16a`.

## The Golden Rule: "Spec First, Code Second"
We never skip steps. If a feature is too small for a step, we explicitly acknowledge it (Step Skipped).

Each spec step uses the **two-phase Clarify/Emit protocol**:

- **Clarify** (if Self-Audit Gate score < 0.9): the AI outputs only short bulleted gap questions. No JSON, no code fences. Stop and wait for answers.
- **Emit**: the AI writes the artifact JSON directly to `spec/NN_name.json`. Do not return fenced JSON as the primary output.

---

## Phase 1: The Intent (Define)
*Files: Docs -> 00 -> 01 -> 02 -> 03 -> 04*

### Pre-Flight Check
Before starting, ensure your current specs are clean and valid.
```bash
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit
```

1.  **Step 00: Seed Docs & Charter**:
    *   **Check**: Does this feature change the project overview (Success Metrics/Users)?
    *   **Action**: Update the overview seed declared in `spec/common/seed_manifest.json` first, then update `spec/00_charter.json`.
    *   *Reference*: `prompts/prompt_00_project_charter.md`.
2.  **Step 01: Capabilities & Stack**:
    *   **Check**: Does this introduce a new Tech Stack element (e.g., Redis)?
    *   **Action**: Update the tech-stack seed declared in `spec/common/seed_manifest.json` first, then update `spec/01_capabilities.json`.
    *   *Reference*: `prompts/prompt_01_capabilities.md`.
3.  **Step 02: System Sketch**: Does this add a new Component? Update the diagram.
    *   *Reference*: `prompts/prompt_02_system_sketch.md`.
4.  **Step 03: Glossary**: New terms? Define them.
    *   *Reference*: `prompts/prompt_03_glossary.md`.
5.  **Step 04: Functional Requirements**: **CRITICAL**. Add the atomic FRs here.
    *   Target artifact: `spec/04_fr_list.json`
    *   *Reference*: `prompts/prompt_04_functional_requirements.md`.
    *   *Constraint*: Must link back to Capability ID (`trace`).

**User Action:**
> **PROMPT:**
> I am adding feature [Name].
> 1. Check the seeds declared in `spec/common/seed_manifest.json` for steps 00 and 01. Do they need updates?
> 2. Iterate through Specs 00, 01, 02, 03, and 04.
> Ask me if updates are needed for each.
> Use each step's canonical prompt (`prompts/prompt_NN_name.md`) and emit updated JSON directly to `spec/NN_name.json`.

---

## Phase 2: The Contract (Design)
*Files: 05 -> 06 -> 07 -> 08*

1.  **Step 05: Interfaces**: Define the new API endpoints or Function Signatures.
    *   *Reference*: `prompts/prompt_05_interface_contracts.md`.
    *   *Constraint*: Must trace to `fr-kebab-case` (FR ID format from Step 04).
2.  **Step 06: Invariants**: Defines the "Musts" (Business Rules).
    *   *Reference*: `prompts/prompt_06_invariants.md`.
3.  **Step 07: NFRs**: Define performance/security constraints.
    *   *Reference*: `prompts/prompt_07_nfrs.md`.
4.  **Step 08: Fixtures**: Add sample data for the new entities.
    *   *Reference*: `prompts/prompt_08_fixtures.md`.

**User Action:**
> **PROMPT:**
> Based on the new FRs in `spec/04_fr_list.json` (Step 04), help me design the contracts.
> Iterate through Steps 05, 06, 07, 08.
> Update `spec/05_interface_contracts.json` with new endpoints.
> Update `spec/08_fixtures.json` with new data samples.
> Use each step's canonical prompt and emit updated JSON directly to `spec/NN_name.json`.

---

## Phase 3: The Governance & Extension Planning (Steps 09–13)
*Files: 09 -> 10 -> 11 -> 12 -> 13*

1.  **Step 09: Implementation Plan**: Does this feature change the tech stack, milestones, or deliverables?
    *   Target artifact: `spec/09_impl_plan.json`
    *   Requires `tech_stack` as an object (not array) and `milestones` with a `deliverables` array.
    *   *Reference*: `prompts/prompt_09_impl_plan.md`.
2.  **Step 10: Governance**: Any new compliance needs?
    *   *Reference*: `prompts/prompt_10_governance.md`.
3.  **Step 11: Red Team**: **CRITICAL**. Add potential security threats for the new feature.
    *   *Reference*: `prompts/prompt_11_redteam.md`.
4.  **Step 12: CI Gates**: Do we need a new pipeline check?
    *   *Reference*: `prompts/prompt_12_ci_gates.md`.
5.  **Step 13: Extensions**: Is this a Plugin/Extension?
    *   *Reference*: `prompts/prompt_13_extension_manifest.md`.

---

## Phase 3.5: Completeness Assessment (Gate)
*Files: 13a*

Before scheduling, confirm that all upstream specs are complete and internally consistent.

**Step 13a: Completeness Assessment**
*Reference*: `prompts/prompt_13a_completeness_assessment.md`.

*   **Action**: Run Step 13a to evaluate coverage gaps, missing requirement links, and completeness scores across Phases 1–3.
*   Target artifact: `spec/13a_completeness_assessment.json`
*   If coverage gaps are found, return to the relevant upstream step and address them **before** proceeding to Phase 4.

```bash
./tools/run_specdev.sh validate spec/13a_completeness_assessment.json --repo-root ./devspec_toolkit
```

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

## Phase 4.5: Scaffold & Trinity Anchor
*Files: 15, 16*

Before running the Trinity Loop, you must create the Scaffold and the Trinity Anchor.

### Step 15: Scaffold
*Reference*: `prompts/prompt_15_scaffold.md`.

*   **Action**: Generate or update the code scaffold for the new feature.
*   Target artifact: `spec/15_scaffold.json`
*   This captures the directory structure, file layout conventions, and scaffold template paths used by Step 16a.

```bash
./tools/run_specdev.sh validate spec/15_scaffold.json --repo-root ./devspec_toolkit
```

### Step 16: Trinity Anchor
*Reference*: `prompts/prompt_16_impl_context.md`.

*   **Action**: Create or update `spec/16_impl_context.json` — the root Trinity Anchor.
*   **REQUIRED** before Step 16a can run. Step 16a uses this anchor to determine `scope_in`, `scope_out`, and the active checklist boundary.
*   Target artifact: `spec/16_impl_context.json`

```bash
./tools/run_specdev.sh validate spec/16_impl_context.json --repo-root ./devspec_toolkit
```

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

Supply the `spec/impl_context/{step_id}.json` path. The planner populates `plan` with checklist, target files, and test commands.

### Step 16b: Coder
*Reference*: `prompts/prompt_16b_impl_coder.md`.

**User Action:**
> **PROMPT:**
> Run Step 16b.
> Input: `spec/impl_context/step-[feature-name].json`.
> Execute the Checklist.

Supply the populated plan artifact path. The coder executes each checklist item, writes code, and populates `execution`.

### Step 16c: Reviewer
*Reference*: `prompts/prompt_16c_impl_reviewer.md`.

**User Action:**
> **PROMPT:**
> Run Step 16c.
> Verify the implementation against the Checklist.

Supply the executed artifact path. The reviewer validates execution against the plan, populates `review`, and either approves or returns a blocking finding.

---

## Completion

1.  **Regenerate Traceability Matrix**: Run the matrix command to rebuild cross-artifact trace links. Do not manually edit spec files for traceability.
    ```bash
    mkdir -p spec/extras && ./tools/run_specdev.sh matrix spec --repo-root ./devspec_toolkit --out spec/extras/trace_matrix.json
    ```
2.  **Final Validation**:
    ```bash
    ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh fixtures-lint spec --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh traceability-check spec --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh hallucination-lint spec --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh dag-lint --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit
    ```
    This confirms that your new feature didn't break any existing traces or schema rules.
3.  **Governance-Compliant Commit**: Commit with a message that matches the pattern defined in `spec/10_governance.json`. Example: `feat(spec): add [feature-name] [fr-feature-id]`.
