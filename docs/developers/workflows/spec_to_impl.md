# Spec → Implementation Workflow (Steps 13–16c)

Phase II turns validated specs into a running system while keeping runtime behavior traceable back to the artifacts.

All commands in this guide assume you run them from repo root with the toolkit available at [./devspec_toolkit/](../../../).

## AI Assist Flow
Where prompts apply in this phase (e.g., Scaffold updates, Trinity Plan/Review, Drift), use the two‑phase flow:
- Phase A — Clarify: ask targeted questions based on the prompt’s “Self‑Audit Gate”.
- Phase B — Emit: write/update the artifact file at the step path and return concise status (path + validation result).
Clarify responses should be short, bulleted questions grouped by topic (no JSON, no code fences), prioritizing gating items; pause emission until those answers are provided.

## Step Progression
| Step | Purpose | Key Activities |
|------|---------|----------------|
| 13 — Extensions | Define domain-specific schemas | Identify missing domains (AI, DB) and generate `spec/13_extension_manifest.json`. |
| 13a — Completeness | Gate implementation on quality | Verify all specs are complete and actionable via `spec/13a_completeness_assessment.json`. |
| 14 — Roadmap | Sequence the work (Core + Extensions) | Merge Step 09 baseline + Step 13 extensions into a tactical JIT execution plan. |
| 15 — Scaffold | Generate compile-clean skeleton | Implement manually or via framework CLI. |
| 16a — Plan (Trinity) | Checklist & Sec/Ops Planning | Define `summary`, `docs_impact`, `spec_alignment`, `review_requirements`, security fixtures, dashboards, alerts, and drift checks in `spec/impl_context/{step_id}.json`. |
| 16b — Build (Trinity) | Implement & Config | Write Code, Configs, and update Docs. |
| 16c — Review (Trinity) | Audit & Gate | Verify Code/Sec/Ops, run full tests, and emit structured `delivery_status` evidence (`deployments`, `dashboards_verified`, `alerts_verified`) when delivery is planned. |

## Step 16 Artifact Layout
Step 16 uses **two levels** of artifacts:
1. **Trinity Anchor**: `spec/16_impl_context.json` (one file) — a root summary for the active cycle.
2. **Milestone Contexts**: `spec/impl_context/{step_id}.json` — detailed per‑milestone execution files produced by 16a/16b/16c.

## Why Two Planning Steps?
Confusion often arises between **Step 09 (Implementation Plan)** and **Step 14 (Roadmap)**.

| Feature | Step 09 (Impl Plan) | Step 14 (Roadmap) |
| :--- | :--- | :--- |
| **Phase** | Discovery (Planning) | Execution (JIT) |
| **Goal** | **Unlock Downstream Specs** | **Drive Daily Coding** |
| **Key Output** | Tech Stack, Language, CI Cadence | Atomic User Stories, Sprints, Integration Order |
| **Why?** | You need to know the *Language* (e.g. Python) before you can write *CI Gates* (Step 12) or *Red Team* scripts (Step 11). | You need to know the *Extensions* (Step 13) before you can sequence the actual work. |

**Rule of Thumb**: Step 09 is the "Architect's Baseline". Step 14 is the "Project Manager's Schedule".

## Command Cadence
- Generate scaffolds manually or using framework tools, ensuring alignment with `15_scaffold.json`.
- **Verify**: Use `python devspec_toolkit/tests/integration/test_step_15.py <path_to_scaffold>` to check schema compliance, strict method enums, and traceability.
- Run the [core validation commands](../reference.md#core-validation-commands) to track fixture progress and trace coverage as implementation evolves.

## CI Integration
- **validate** — schema + fixture lint
- **test** — executes fixture suite and custom tests
- **redteam** — runs adversarial inputs and adds regressions to fixtures
- **deploy** — deploys via the plan in Step 09/16
- **drift-audit** — compares runtime data to spec assertions as defined in `16_impl_context.json` (Step 16a)

Ensure the generated `.github/workflows/spec_validation.yml` reflects these jobs and references the spec IDs they enforce.


## Outputs
- Current artifacts under `spec/13*` through `spec/16*`
- Implemented scaffold or runtime referencing Step 05 contracts
- Updated monitoring bindings and drift schedules guaranteeing the spec remains the single source of truth
- Review artifacts that include verifiable delivery evidence when `plan.delivery.status == planned`
