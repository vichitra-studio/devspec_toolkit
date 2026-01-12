# Shared Expectations

Use this page as the canonical reference for guidance that applies across every prompt and generated guide. Individual prompts can add extra requirements, but they should link back here for the shared baseline.

## Definition of Ready (DoR) / Guardrails

Each step's prompt defines its specific Definition of Ready (DoR) within the **Context To Ingest** and **Self-Audit Gate** sections. Treat those rules as non-negotiable.

## Working Increment

- Store the generated JSON and guide under your host repo’s `spec/` directory using the matching filenames (`spec/NN_name.json` and `spec/NN_name.guide.md`).
- CI runs: schema validation and step-specific checks (see below).

## Checks

- Schema validation: required keys, enums, formats.
- Cross-step traceability: IDs referenced here must exist by their milestone deadlines.
- Quality: keep prose succinct; prefer measurable statements; avoid ambiguity.

## Failure Modes

- Over-broad scope or vague statements that cannot be falsified.
- Broken references to other steps.
- Hidden assumptions not captured in the artifact.
