# Developer Documentation Index

Use this index to locate the developer-facing material while working through the AI Spec Driven Development Toolkit. Automation-specific instructions live under [../agents/](../agents/).

## Onboarding
- [`getting_started.md`](getting_started.md) — single-path setup guide and workflow primer.
- [`reference.md`](reference.md) — command cheatsheet, naming rules, and troubleshooting steps.

## Workflow Guides
- [`workflows/discovery.md`](workflows/discovery.md) — steps 00–12 overview.
- [`workflows/spec_to_impl.md`](workflows/spec_to_impl.md) — steps 13–17 overview.
- [`workflows/workflow_migration.md`](workflows/workflow_migration.md) — guide for migrating projects after toolkit updates.
- [`workflows/workflow_align.md`](workflows/workflow_align.md) — guide for using the specdev align CLI.
- [`workflows/workflow_bootstrap_legacy.md`](workflows/workflow_bootstrap_legacy.md) — bootstrapping legacy projects.
- [`workflows/workflow_feature_extension.md`](workflows/workflow_feature_extension.md) — adding new features to existing specs.

## Tooling & Diagnostics
- [`tooling/coverage_matrix.md`](tooling/coverage_matrix.md) — traceability mechanics and enforcement.
- [`tooling/gap_hunter_checklist.md`](tooling/gap_hunter_checklist.md) — repeatable gap-hunting process.
- [`tools/changelog_parser.md`](tools/changelog_parser.md) — changelog YAML parser for migration system.

## Step Guides
Each spec step ships with two authoritative files in `spec/`:
- `spec/NN_name.guide.md` — human playbook describing purpose, DoR, checks, and failure modes.
- `spec/NN_name.json` — machine artifact validated against `schema/NN_name.schema.json`.

Refer directly to those guides when authoring or reviewing a given step.

## Related Resources
- CLI and schema registry: [../tools/README.md](../tools/README.md), [../tools/schema_registry.json](../tools/schema_registry.json)


## Contributing Improvements
1. Review open issues for existing documentation requests.
2. Apply the conventions described in [reference.md](reference.md).
3. Open a PR summarizing the problem solved and linking impacted spec steps.
