# Shared Expectations

Use this document as the authoritative baseline for all prompt-level directives. Individual prompts inherit all rules here and may add step-specific requirements or override named sections. Where a prompt defines a section that overlaps with this document (e.g., Role, Task, Output Rules), the prompt's version takes precedence.

## 1. Path Variables

| Variable | Description |
|---|---|
| `$PRODUCT_ROOT` | Root of the consumer/product repository |
| `$TOOLKIT_ROOT` | Root of the devspec_toolkit directory |
| `$SPEC_DIR` | `$PRODUCT_ROOT/spec` — where spec artifacts live |
| `$SCHEMA_DIR` | `$TOOLKIT_ROOT/schema` — where JSON Schemas live |

## 2. Schema Authority & Metadata Contract

The schema at `$SCHEMA_DIR/NN_name.schema.json` is the authoritative source for all field definitions, types, required vs optional markers, enum values, patterns, and minItems rules. MUST read the schema before generating output. Do NOT guess field names, types, or valid values — all structural constraints are defined in the schema. Do NOT output fields not defined in the schema.

This step's output artifact MUST include every field listed in the schema's `required[]` array. Do NOT add fields not defined in the schema. Refer to the schema for the complete list of required fields, types, and structural constraints — do NOT restate them in the prompt.

## 3. Canonical Registry Protocol

Before generating output, you MUST load and search `canon/manifest.json` for existing canonical entries. NEVER use a deprecated canonical without checking `replaced_by` first.

- **Bind**: Map `*_ref` fields to canonical IDs (`cn:<namespace>:<kind>:<slug>`). Resolve aliases via `canon/aliases.json`.
- **Required**: `canonical_refs_used` MUST list every canonical ID referenced by any `*_ref` field. For each `*_ref` in the schema: if the semantic content exists, the ref MUST be populated — not optional.
- **Optional**: `canonical_proposals` for any new term with no registry match; `canonical_conflicts` for ambiguous or contradictory matches.
- **Resolution order**: exact canonical ID → active alias → canonical proposal. If multiple active canonicals match, emit `canonical_conflicts`. Never emit schema fields that invent a new semantic label without a canonical reference or proposal.

## 4. Hardening Protocol

- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

## 5. Default Role & Task Framing

> **Applies to**: Steps 00–10, 12–15. Steps 11, 13, 13a, 16, 16a, 16b, 16c define their own Role/Task and override this default.

**Role**: You are a senior specification author and validator. Your job is to emit a single JSON artifact for **{{STEP_NAME}}** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

**Task**:
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **{{STEP_NAME}}**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.

## 6. Output Rules (Discovery Phase)

> **Applies to**: Steps 00–15. Steps 16–16c have different output rules defined in their own prompts. Note: Steps 11, 13, 13a define their own Role/Task (see Section 5) but still follow these output rules.

1. Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path). Do not return the artifact as a fenced code block in the response.
2. The JSON must validate against the referenced step schema listed in `Schema Reference`.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of the values defined in `schema/core/atoms.schema.json` owner enum.
7. If the schema supports `trace` or `links`, include at least one reference to connect artifacts across steps.
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## 7. Seed Order Protocol

> **Applies to**: Seed-phase steps (00–04) and any step that ingests seed documents.

- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["NN"]`.
- Ingest required seeds in order before any other context.
- If a required seed is missing or stale, stop and request it before proceeding.

## 8. Self-Audit Gate Protocol

### 8.1 Self-Audit Gate (input sufficiency)

Each gate item is a pass/fail check on whether upstream inputs are sufficient to proceed. If ALL items pass → enter Emit mode. If ANY item cannot be satisfied → enter Clarify mode: output only short bulleted gap questions, no JSON, no code fences. Stop and wait for user input.

Output quality verification is in the Coverage Closure section — run Coverage Closure AFTER emitting the artifact.

### 8.2 Universal Coverage Closure Checklist

Each prompt's Coverage Closure section contains step-specific rules. In addition, before emitting, always verify:
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)

## 9. Step-Order Policy

- Use a forward-only execution model.
- Use no refinement mode.
- Any accepted change at step N requires full replay through all downstream steps (N+1...end) before merge.

## 10. Tool Execution

After generating or modifying a spec artifact, run the unified check command to validate schema conformance, canonical integrity, hallucination detection, traceability, and all applicable lints in one pass:
```bash
specdev spec-check <spec_dir> --repo-root ./devspec_toolkit
```

For submodule deployments, add `--spec-root ./spec --git-root .` to resolve seed paths correctly.

For single-file quick validation during iterative editing:
```bash
specdev validate <path_to_artifact> --repo-root ./devspec_toolkit
```

Step-specific additional commands (e.g., `invariants-check`, `fixtures-lint`, `governance-check`) are listed in each prompt's Tool Execution section.

## 11. Conflict Resolution Protocol

When two upstream artifacts contradict each other:
1. Identify the conflict explicitly in the Context Ledger.
2. Apply precedence: seed > charter > capabilities > architecture > delivery > glossary.
3. If same-level artifacts conflict, add a Gap Question — do not guess.
4. Never silently resolve a conflict.

## 12. Context Ledger

Before emitting output, build a private synthesis ledger (Context Ledger) containing all inputs ingested, decisions made, and evidence chains. Do not output it. It serves as internal audit trail for completeness closure and self-audit scoring. Each prompt's Operating Flow section specifies what the Context Ledger should contain for that step.

## 13. Cross-Step Relationships

Cross-step relationships (dependencies, downstream consumers) are derivable from `step_order.json` DAG. Do not restate them in prompts. Use `specdev prompt-context NN` to inspect them at runtime.

## 14. Documentation Resources

Use these resources to orient yourself within the toolkit before emitting output:

- **`docs/README.md`** — index of all documentation; start here to find the right guide.
- **`docs/`** — organized into subdirectories: `workflows/` (how-to guides), `reference/` (CLI and schema reference), `ops/` (operational runbooks), `plans/` (roadmaps and design records), `agents/` (agent manifests and protocols).
- **`tools/step_docs.json`** — machine-readable mapping from step name to its documentation files; use this to locate step-specific guides programmatically.
- **Step guides** — human-readable guidance for each step lives at `docs/spec/NN_name.guide.md` (if present) or inline in the step's prompt file. Check step_docs.json for the authoritative list.
