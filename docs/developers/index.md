# Developer Documentation Index

Use this index to locate the developer-facing material while working through the AI Spec Driven Development Toolkit. Automation-specific instructions live under `../agents/`.

## Onboarding
- [`getting_started.md`](getting_started.md) — single-path setup guide and workflow primer.
- [`reference.md`](reference.md) — command cheatsheet, naming rules, and troubleshooting steps.

## Workflow Guides
- [`workflows/discovery.md`](workflows/discovery.md) — steps 00–12 overview.
- [`workflows/spec_to_impl.md`](workflows/spec_to_impl.md) — steps 13–17 overview.

## Tooling & Diagnostics
- [`tooling/coverage_matrix.md`](tooling/coverage_matrix.md) — traceability mechanics and enforcement.
- [`tooling/gap_hunter_checklist.md`](tooling/gap_hunter_checklist.md) — repeatable gap-hunting process.

## Step Guides
Each spec step ships with two authoritative files in `spec/`:
- `spec/NN_name.guide.md` — human playbook describing purpose, DoR, checks, and failure modes.
- `spec/NN_name.json` — machine artifact validated against `schema/NN_name.schema.json`.

Refer directly to those guides when authoring or reviewing a given step.

## Related Resources
- CLI and schema registry: `../tools/README.md`, `../tools/schema_registry.json`
- Example specs: `../example/`
- Test data: `../tests/fixtures/`, `../tests/samples/`

## Contributing Improvements
1. Review open issues for existing documentation requests.
2. Apply the conventions described in `reference.md`.
3. Open a PR summarizing the problem solved and linking impacted spec steps.
