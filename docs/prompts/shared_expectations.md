# Shared Template Expectations

Use this page as the canonical reference for guidance that applies across every `template/*.guide.md`. Individual guides can add extra requirements, but they should link back here for the shared baseline.

## Definition of Ready (DoR) / Guardrails

The shared guardrails live in [`definition_of_ready.md`](definition_of_ready.md). Treat those rules as non-negotiable; each step can only add narrower constraints.

## Working Increment

- Store the generated JSON and guide under your host repo’s `spec/` directory using the matching filenames.
- CI runs: schema validation and step-specific checks (see below).

## Checks

- Schema validation: required keys, enums, formats.
- Cross-step traceability: IDs referenced here must exist by their milestone deadlines.
- Quality: keep prose succinct; prefer measurable statements; avoid ambiguity.

## Failure Modes

- Over-broad scope or vague statements that cannot be falsified.
- Broken references to other steps.
- Hidden assumptions not captured in the artifact.
