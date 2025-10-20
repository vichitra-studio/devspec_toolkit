# Spec → Implementation Workflow (Steps 13–17)

Phase II turns validated specs into a running system while keeping runtime behavior traceable back to the artifacts.

## Step Progression
| Step | Purpose | Key Activities |
|------|---------|----------------|
| 13 — Scaffold | Generate compile-clean skeleton aligned with API contracts and system sketch | Run `python -m specdev_tools.cli scaffold ...`; inspect generated routes and validators. |
| 14 — Fixture Implementation | Drive development with fixtures until they all pass | Implement handlers, update `14_fixture_impl.json`, rerun fixtures. |
| 15 — Red-Team Loop | Add adversarial cases and capture mitigations | Extend `11_redteam.json`, feed new fixtures into `15_redteam_loop.json`. |
| 16 — Delivery & Monitoring | Map NFRs to dashboards, alerts, and deployments | Keep `16_delivery_monitoring.json` synced with operations tooling. |
| 17 — Spec-Drift Audit | Detect runtime vs spec divergence | Schedule checks defined in `17_spec_drift.json` and feed outputs back into governance. |

## Command Cadence
```bash
# Generate scaffold and optionally boot it
python -m specdev_tools.cli scaffold spec --out scaffold_out

# Track fixture-driven progress
python -m specdev_tools.cli fixtures-lint spec

# Continuous validation as implementation evolves
python -m specdev_tools.cli validate-all spec
python -m specdev_tools.cli matrix spec --out tools/trace_matrix.json
```

## CI Integration
- **validate** — schema + fixture lint
- **scaffold** — ensures contracts remain compatible with generated stub
- **test** — executes fixture suite and custom tests
- **redteam** — runs adversarial inputs and adds regressions to fixtures
- **deploy** — deploys via the plan in Step 09/16
- **drift-audit** — compares runtime data to spec assertions as defined in Step 17

Ensure `.github/workflows/ci.yml` (generated via `gen-ci`) reflects these jobs and references the spec IDs they enforce. For example:

```bash
python -m specdev_tools.cli gen-ci spec --repo-root tools/ai-spec-toolkit --toolkit-path tools/ai-spec-toolkit --out .github/workflows/ci.yml
```

## Outputs
- Current artifacts under `spec/13*` through `spec/17*`
- Implemented scaffold or runtime referencing Step 05 contracts
- Updated monitoring bindings and drift schedules guaranteeing the spec remains the single source of truth
