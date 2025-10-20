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
| 13 — Scaffold | Generate compile-clean skeleton aligned with API contracts and system sketch | Run `python -m specdev_tools.cli scaffold ...`; inspect generated routes and TODO markers for validation. |
| 14 — Fixture Implementation | Drive development with fixtures until they all pass | Implement handlers, update `14_fixture_impl.json`, rerun fixtures. |
| 15 — Red-Team Loop | Add adversarial cases and capture mitigations | Extend `11_redteam.json`, feed new fixtures into `15_redteam_loop.json`. |
| 16 — Delivery & Monitoring | Map NFRs to dashboards, alerts, and deployments | Keep `16_delivery_monitoring.json` synced with operations tooling. |
| 17 — Spec-Drift Audit | Detect runtime vs spec divergence | Schedule checks defined in `17_spec_drift.json` and feed outputs back into governance. |

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
