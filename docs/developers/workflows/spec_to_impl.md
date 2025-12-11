# Spec → Implementation Workflow (Steps 13–17)

Phase II turns validated specs into a running system while keeping runtime behavior traceable back to the artifacts.

All commands in this guide assume you run them from repo root with the toolkit available at [./devspec_toolkit/](../../../).

## AI Assist Flow
Where prompts apply in this phase (e.g., Scaffold updates, Red‑Team Loop, Monitoring, Drift), use the two‑phase flow:
- Phase A — Clarify: ask targeted questions based on the prompt’s “Self‑Audit Gate”.
- Phase B — Emit: output exactly one fenced `json` block for the step’s artifact.
Clarify responses should be short, bulleted questions grouped by topic (no JSON, no code fences), prioritizing gating items; pause emission until those answers are provided.

## Step Progression
| Step | Purpose | Key Activities |
|------|---------|----------------|
| 13 — Extensions | Define domain-specific schemas | Identify missing domains (AI, DB) and generate `spec/13_extension_manifest.json`. |
| 13a — Completeness | Gate implementation on quality | Verify all specs are complete and actionable via `spec/13a_completeness_assessment.json`. |
| 14 — Roadmap | Sequence the work (Core + Extensions) | Merge Step 09 baseline + Step 13 extensions into a tactical JIT execution plan. |
| 15 — Scaffold | Generate compile-clean skeleton | Run `python -m specdev_tools.cli scaffold ...`. |
| 16 — Fixture Impl | Drive dev with fixtures | Implement handlers, update `16_fixture_impl.json`. |
| 17 — Red-Team Loop | Add adversarial cases | Feed new threats into `17_redteam_loop.json`. |
| 18 — Monitoring | Map NFRs to operations | Sync `18_delivery_monitoring.json`. |
| 19 — Spec Drift | Detect divergence | Schedule checks in `19_spec_drift.json`. |

## Why Two Planning Steps?
Confusion often arises between **Step 09 (Implementation Plan)** and **Step 14 (Roadmap)**.

| Feature | Step 09 (Impl Plan) | Step 14 (Roadmap) |
| :--- | :--- | :--- |
| **Phase** | Discovery (Planning) | Execution (JIT) |
| **Goal** | **Unlock Downstream Specs** | **Drive Daily Coding** |
| **Key Output** | Tech Stack, Language, CI Cadence | Sprints, Integration Order |
| **Why?** | You need to know the *Language* (e.g. Python) before you can write *CI Gates* (Step 12) or *Red Team* scripts (Step 11). | You need to know the *Extensions* (Step 13) before you can sequence the actual work. |

**Rule of Thumb**: Step 09 is the "Architect's Baseline". Step 14 is the "Project Manager's Schedule".

## Command Cadence
- Generate scaffolds with `python -m specdev_tools.cli scaffold spec --repo-root ./devspec_toolkit --out scaffold_out`.
- Run the [core validation commands](../reference.md#core-validation-commands) to track fixture progress and trace coverage as implementation evolves.

## CI Integration
- **validate** — schema + fixture lint
- **scaffold** — ensures contracts remain compatible with generated stub
- **test** — executes fixture suite and custom tests
- **redteam** — runs adversarial inputs and adds regressions to fixtures
- **deploy** — deploys via the plan in Step 09/16
- **drift-audit** — compares runtime data to spec assertions as defined in Step 17

Ensure [.github/workflows/ci.yml](../../../.github/workflows/ci.yml) (generated via `gen-ci`) reflects these jobs and references the spec IDs they enforce. For example:

```bash
python -m specdev_tools.cli gen-ci spec --repo-root ./devspec_toolkit --toolkit-path ./devspec_toolkit --out .github/workflows/ci.yml
```

## Outputs
- Current artifacts under `spec/13*` through `spec/17*`
- Implemented scaffold or runtime referencing Step 05 contracts
- Updated monitoring bindings and drift schedules guaranteeing the spec remains the single source of truth
