# Workflow: Feature Extension (The Sequential Cycle)




This guide describes the **Standard Operating Procedure (SOP)** for adding new capabilities to a specced project.
It strictly follows the **Numerical Spec Sequence**: You must check every file from `00` to `16c` (steps: `00, 01, 02, 02a, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 16a, 16b, 16c`) before you execute the Trinity Loop in `16a`.

## The Golden Rule: "Spec First, Code Second"
We never skip steps. If a feature is too small for a step, we explicitly acknowledge it (Step Skipped).

Each spec step uses the **two-phase Clarify/Emit protocol**:

- **Clarify** (if Self-Audit Gate score < 0.9): the AI outputs only short bulleted gap questions. No JSON, no code fences. Stop and wait for answers.
- **Emit**: the AI writes the artifact to disk through the CLI, never as fenced JSON in the response. A step that does not exist yet is written as a whole draft file outside `spec/` and created with `specdev step create NN --from <draft>`; a step that exists is edited with `specdev json patch|insert|delete --id <node-id>` (a new node: `specdev json insert --step NN <collection-path> '<node>'`). A file written by hand into `spec/` gets E761 for each of its links until `specdev attest <node-id> --yes`.

---

## Phase 1: The Intent (Define)
*Files: Docs -> 00 -> 01 -> 02 -> 03 -> 04*

### Pre-Flight Check
Before starting, ensure your current specs are clean and valid.
```bash
# Or run the unified gate, which resolves project canon and runs every applicable check:
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

0.  **Seeds**:
    *   **Check**: Does the feature need a seed of its own (a new subject, not an edit of the overview or tech-stack seed)?
    *   **Action**: Write the seed by hand, in four moves. (1) Copy `seed_templates/seed_extension.md` to a file under the seed folder (for example `docs/seed/seed_<subject>.md`) and fill every section, including the acceptance posture. (2) Register it: `specdev json insert spec/common/seed_manifest.json .seeds '{"seed_id": "seed-<subject>", "path": "docs/seed/seed_<subject>.md", "description": "...", "required": false, "source_type": "doc"}' --repo-root ./devspec_toolkit`, and add the id to `.global_seed_order`. (3) Route it to the steps that distil it: `specdev json patch spec/common/seed_manifest.json '.step_requirements."04"' '["seed-<subject>"]' --repo-root ./devspec_toolkit` (one entry per step; keep the ids already listed there). (4) Lint it: `./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`. A change to an existing seed is an edit of its file; `specdev stale` then lists the nodes that link to it.
    *   *Reference*: `docs/prompts/shared_expectations.md` section 7.
1.  **Step 00: Seed Docs & Charter**:
    *   **Check**: Does this feature change the project overview (Success Metrics/Users)?
    *   **Action**: Update the overview seed declared in `spec/common/seed_manifest.json` first, then update `spec/00_charter.json`.
    *   *Reference*: `prompts/prompt_00_project_charter.md`.
2.  **Step 01: Capabilities & Stack**:
    *   **Check**: Does this introduce a new Tech Stack element (e.g., Redis)?
    *   **Action**: Update the tech-stack seed declared in `spec/common/seed_manifest.json` first (the template manifest routes it to steps 00, 02 and 02a), then update `spec/01_capabilities.json`.
    *   *Reference*: `prompts/prompt_01_capabilities.md`.
3.  **Step 02: System Sketch**: Does this add a new Component? Update the diagram.
    *   *Reference*: `prompts/prompt_02_system_sketch.md`.
4.  **Step 03: Glossary**: New terms? Define them.
    *   *Reference*: `prompts/prompt_03_glossary.md`.
5.  **Step 04: Functional Requirements**: **CRITICAL**. Add the atomic FRs here.
    *   Target artifact: `spec/04_fr_list.json`
    *   *Reference*: `prompts/prompt_04_functional_requirements.md`.
    *   *Constraint*: Must link back to a capability id in `derives_from`.

**User Action:**
> **PROMPT:**
> I am adding feature [Name].
> 1. Check the seeds declared in `spec/common/seed_manifest.json` for each step the manifest routes them to (`step_requirements`). Do they need updates?
> 2. Iterate through Specs 00, 01, 02, 03, and 04.
> Ask me if updates are needed for each.
> Use each step's canonical prompt (`prompts/prompt_NN_name.md`). Edit a step that exists with `specdev json patch|insert|delete --id <node-id>` (a new node: `specdev json insert --step NN`); create a step that does not exist yet from a draft outside `spec/` with `specdev step create NN --from <draft>`. Never write a file under `spec/` by hand.

---

## Phase 2: The Contract (Design)
*Files: 05 -> 06 -> 07 -> 08*

1.  **Step 05: Interfaces**: Define the new API endpoints or Function Signatures.
    *   *Reference*: `prompts/prompt_05_interface_contracts.md`.
    *   *Constraint*: Must list the FR ids it implements (`fr-kebab-case`, the FR ID format from Step 04) in `derives_from`.
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
> Use each step's canonical prompt. Edit a step that exists with `specdev json patch|insert|delete --id <node-id>` (a new node: `specdev json insert --step NN`); create a step that does not exist yet from a draft outside `spec/` with `specdev step create NN --from <draft>`. Never write a file under `spec/` by hand.

---

## Phase 3: The Governance & Extension Planning (Steps 09–13)
*Files: 09 -> 10 -> 11 -> 12 -> 13*

1.  **Step 09: Implementation Plan**: Does this feature change the milestones or what they schedule?
    *   Target artifact: `spec/09_impl_plan.json`
    *   Every `milestones[]` entry requires `schedules`, an array of at least one id of what the milestone schedules.
    *   *Reference*: `prompts/prompt_09_impl_plan.md`.
2.  **Step 10: Governance**: Any new compliance needs?
    *   *Reference*: `prompts/prompt_10_governance.md`.
3.  **Step 11: Red Team**: **CRITICAL**. Add potential security threats for the new feature.
    *   *Reference*: `prompts/prompt_11_redteam.md`.
4.  **Step 12: CI Gates**: Do we need a new pipeline check?
    *   *Reference*: `prompts/prompt_12_ci_gates.md`.
5.  **Step 13: Extensions**: Does the feature bring a domain the core steps do not describe (a database schema, a model, a queue), or add to one an extension already describes?
    *   *Action*: A new domain is a new entry of the manifest with its two files in `spec/extensions/`. An addition to an existing extension is an edit of its data file by node id, and of its schema file when a new kind or field is needed ([extension_schemas.md](../extension_schemas.md), "The life of an extension").
    *   *Reference*: `prompts/prompt_13_extension_manifest.md`.

---

## Phase 3.5: Completeness Gate
Before scheduling, confirm that all upstream specs are complete and internally consistent. Step 13a (the completeness assessment) was removed in 1.2.0; the checks below replace it.

*   **Action**: Run `specdev coverage` to see the FRs, criteria and capabilities that are not linked, and `specdev spec-check` for the role findings (E740 to E745) and broken links (E700, E701).
*   If gaps are found in a step below 14, return to that step and address them **before** proceeding to Phase 4: `specdev step ready 14` lists the blockers (the findings owned by the steps that the nodes of step 14 link to; `specdev stale` lists those of every step). Gaps that step 14 owns (E566, E742, E744, E745 and the E740 of the nodes a task criterion uses) are not blockers: the task criteria written in Phase 4 clear them.

```bash
./tools/run_specdev.sh coverage --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh step ready 14 --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
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
> Add a new milestone to the roadmap (`spec/14_roadmap.json`) with `specdev json insert --step 14 .milestones '<milestone>'`.
> `milestone_id`: `ms-[feature-name]`, with a `name` and a `target_date`.
> `user_story`: One User Story.
> `tasks`: Atomic sub-tasks, each with `acceptance_criteria` that `refines` the new requirement's criteria.
> (A milestone stores no status; the Trinity Anchor row about it does.)

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

*   **Action**: Create or update `spec/16_impl_context.json` — the root Trinity Anchor. No anchor file yet: write the whole artifact as a draft outside `spec/` and run `specdev step create 16 --from <draft>`. Anchor file present: add the row of the new milestone with `specdev json insert --step 16 .plan.milestone_index '<row>'`.
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
> Target: milestone `ms-[feature-name]` (from Roadmap).
> Context: Read the updated Specs 04, 05, 06, 08, 11.
> Output: a draft of the plan outside `spec/` (`.specdev/drafts/plan_<batch>.json`), then `specdev step create 16a <batch> --from .specdev/drafts/plan_<batch>.json`.

The command creates the plan file `spec/impl_context/ms_<batch>_plan.json`. The draft holds `milestone` (the roadmap milestone id the plan is for) and `plan` (checklist, target files, test commands), and no `execution` or `review`. A person approves the plan, then `specdev milestone start <milestone-id>` starts the milestone.

### Step 16b: Coder
*Reference*: `prompts/prompt_16b_impl_coder.md`.

**User Action:**
> **PROMPT:**
> Run Step 16b.
> Input: `spec/impl_context/ms_<batch>_plan.json`.
> Execute the Checklist.

Supply the plan file path. The coder executes each checklist item, writes code, and records each carried-out action with `specdev plan record <ITEM>/<action-id> --outcome done`; `execution` is written by that command only.

### Step 16c: Reviewer
*Reference*: `prompts/prompt_16c_impl_reviewer.md`.

**User Action:**
> **PROMPT:**
> Run Step 16c.
> Verify the implementation against the Checklist.

Supply the plan file path. The reviewer validates execution against the plan and writes a findings file; `review` is written only by `specdev review record <milestone-id> --verdict verified|needs_work|blocked|deferred --findings-file <file>`, whether the reviewer approves or returns a blocking finding.

---

## Changing or Removing a Feature

The phases above add. A change to something the spec already holds uses the same waterfall, with these commands:

*   **Change a node**: edit it at its own step (`specdev json patch --id <id> ...`). `specdev stale` then lists every link that points at it as suspect; replay each step it names and accept each link with `specdev attest`.
*   **Descope an FR or a capability**: set its `scope` to `later` or `out` with a `scope_reason`.
*   **Rename a node**: `specdev node rename <old-id> <new-id>` (the old id stays as an alias).
*   **Remove a node that no work refined**: the loop "Removing a node" in [`error-codes.md`](../error-codes.md#graph-role-checks-74x).
*   **Remove or replace a node that a closed milestone built**: a milestone of its own, with a removal criterion and a removal fixture; the loop "Removing a node through a milestone" in the same section. The release gate reports work that was changed or deleted and that no closed milestone answers (E343, E344).

---

## Completion

1.  **Replay the links**: Run `specdev stale` and read each suspect link: edit the node that holds it, or accept it with `specdev attest`. `specdev matrix` (which rebuilt the trace matrix) was removed in 1.2.0.
    ```bash
    ./tools/run_specdev.sh stale --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
    ```
2.  **Final Validation** (or substitute the unified `spec-check` gate for `validate-all`):
    ```bash
    ./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
    ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
    ./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
    ./tools/run_specdev.sh fixtures-lint spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
    ./tools/run_specdev.sh hallucination-lint spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
    ./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
    ./tools/run_specdev.sh dag-lint --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
    ```
    This confirms that your new feature didn't break any existing traces or schema rules.
3.  **Governance-Compliant Commit**: Commit with a message that matches the pattern defined in `spec/10_governance.json`. Example: `feat(spec): add [feature-name] [fr-feature-id]`.
