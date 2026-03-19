# Shared Expectations

Use this page as the canonical reference for guidance that applies across every prompt and generated guide. Individual prompts can add extra requirements, but they should link back here for the shared baseline.

## Definition of Ready (DoR) / Guardrails

Each step's prompt defines its specific Definition of Ready (DoR) within the **Self-Audit Gate** and **Coverage Closure** sections. Seed-phase prompts (Steps 00–04) additionally include a **Context To Ingest** section. Treat those rules as non-negotiable.

## Working Increment

- Store the generated JSON and guide under your host repo’s `spec/` directory using the matching filenames (`spec/NN_name.json` and `spec/NN_name.guide.md`).
- CI runs: schema validation and step-specific checks (see below).

## Checks

- Schema validation: required keys, enums, formats.
- Cross-step traceability: IDs referenced here must exist by their milestone deadlines.
- Quality: keep prose succinct; prefer measurable statements; avoid ambiguity.

## Canonical Reuse Rules

- Reuse canonicals first: when a known domain term/entity/role/metric/state/policy matches an existing canonical entry, use the corresponding `*_ref` object and include it in `canonical_refs_used`.
- Do not invent parallel definitions for existing canonicals. If input text conflicts with canonical meaning, add a `canonical_conflicts` entry with `field_path`, `input_value`, candidate ids, and reason.
- If no canonical can be matched with confidence, add a `canonical_proposals` entry instead of guessing.
- Any value with both `<field>` and `<field>_ref` must remain semantically consistent; CI may fail on mismatches.

## Canonical Resolution Protocol

- Resolve in deterministic order: exact canonical ID match, then active alias match, then canonical proposal.
- If multiple active canonicals match the same input, do not pick one implicitly; emit `canonical_conflicts`.
- If no active canonical matches, emit `canonical_proposals` with enough definition context for registry approval.
- Never emit schema fields that invent a new semantic label without either a canonical reference or a proposal.

## one-go Quality Protocol (fail-closed)

- Preflight: before writing output JSON, verify required inputs, allowed enums, and all referenced artifact IDs.
- Evidence Ledger: every non-trivial decision must be traceable to seed input, upstream artifact evidence, or canonical registry evidence.
- Completeness Closure: run an explicit final pass that checks required sections, reference closure, and semantic consistency between `<field>` and `<field>_ref`.
- fail-closed blockers: if any required evidence is missing, any ambiguity is unresolved, or any downstream dependency is unknown, stop and emit a blocker report instead of guessing.

## Step-Order Policy

- Use a forward-only execution model.
- Use no refinement mode.
- Any accepted change at step `N` requires full replay through all downstream steps (`N+1...end`) before merge.

## Failure Modes

- Over-broad scope or vague statements that cannot be falsified.
- Broken references to other steps.
- Hidden assumptions not captured in the artifact.
