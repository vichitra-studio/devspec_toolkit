# Discovery Workflow (Steps 00–12)

Phase I turns fuzzy product ideas into falsifiable, machine-checkable artifacts.

## Objectives
- Capture scope, users, and measurable success metrics.
- Define system capabilities, contracts, and invariants.
- Establish governance and CI gates that keep the spec authoritative.

## Step Progression
| Step | Goal | Key Outputs |
|------|------|-------------|
| 00 — Charter | Align on problem, scope, stakeholders | `spec/00_charter.json` |
| 01 — Capabilities | Describe system verbs and boundaries | `spec/01_capabilities.json` |
| 02 — System Sketch | Shape components and connections | `spec/02_system_sketch.json` |
| 02a — Delivery Baseline | Nail environments, CI, compliance | `spec/02a_delivery_baseline.json` |
| 03 — Glossary | Eliminate ambiguous terms | `spec/03_glossary.json` |
| 04 — Functional Requirements | Define falsifiable behavior | `spec/04_fr_list.json` |
| 05 — Interface Contracts | Establish API surface | `spec/05_interface_contracts.json` |
| 06 — Invariants | Capture truths that must hold | `spec/06_invariants.json` |
| 07 — NFRs | Set performance/reliability targets | `spec/07_nfrs.json` |
| 08 — Fixtures | Provide traceable test data | `spec/08_fixtures.json` |
| 09 — Implementation Plan | Sequence delivery milestones | `spec/09_impl_plan.json` |
| 10 — Governance | Define change control policies | `spec/10_governance.json` |
| 11 — Red Team | Enumerate threats and mitigations | `spec/11_redteam.json` |
| 12 — CI Gates | Wire automated enforcement | `spec/12_ci_gates.json` |

Consult the matching `spec/NN_name.guide.md` before running the prompt for each step.

## Validation Cadence
Use the [core validation commands](../reference.md#core-validation-commands) after each artifact update to keep discovery outputs consistent before moving to implementation.

## Outputs
- Validated JSON artifacts under `spec/00*` through `spec/12*`.
- Updated trace matrix demonstrating FR ↔ API ↔ fixture ↔ NFR coverage.
- Governance rules embedded in CI to keep the spec authoritative.
