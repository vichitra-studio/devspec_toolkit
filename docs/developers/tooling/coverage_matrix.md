# Coverage Matrix

The coverage matrix ties every requirement to a verifying artifact so that the spec, fixtures, and implementation stay aligned.

## Command
Run `python -m specdev_tools.cli matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json` (documented in the [command cheatsheet](../reference.md#command-cheatsheet)).

- `spec/` — root of the spec artifacts.
- `--out` — optional path for the generated JSON report (`-` to print to stdout).

The output lists each FR ↔ API ↔ fixture ↔ NFR chain. CI can diff this file to detect drift.

## Expected Links
| Spec Step | Artifact | Downstream Target |
|-----------|----------|-------------------|
| `04_fr_list.json` | Functional requirements | Trace to API contracts (`05_interface_contracts.json`) via `traceRef`. |
| `05_interface_contracts.json` | API contracts | Targets fixtures (`08_fixtures.json`) and scaffold routes (`13_scaffold.json`). |
| `06_invariants.json` | Invariants | Referenced by fixtures and runtime validators. |
| `07_nfrs.json` | NFRs | Linked to dashboards/alerts in `16_delivery_monitoring.json`. |
| `08_fixtures.json` | Test fixtures | Assert expectations against implementations catalogued in `14_fixture_impl.json`. |
| `11_redteam.json` | Threat scenarios | Feed additional fixtures and updates in `15_redteam_loop.json`. |
| `17_spec_drift.json` | Drift checks | Backstop runtime verification jobs. |

## CI Integration
Add the matrix command to CI alongside the [core validation commands](../reference.md#core-validation-commands) so drift is detected automatically.

Fail the pipeline if the matrix changes without an accompanying spec update or if required trace links are missing.

## Troubleshooting
- **Missing FR trace**: ensure each FR in `04_fr_list.json` has at least one `traceRef` pointing to an API ID.
- **Dangling API reference**: confirm the API exists in `05_interface_contracts.json` and is targeted by a fixture.
- **Unlinked fixture**: verify `targets` reference valid API IDs and that expectations match schema revisions.
- **Matrix diff noise**: regenerate after legitimate changes and commit the new output to keep CI deterministic.
