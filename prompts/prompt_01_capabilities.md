# Step 01 · Capabilities

## Purpose
Translate the charter into a catalog of system capabilities with explicit verbs, scope boundaries, and operating conditions. This step defines what value the system must deliver, when it is intentionally deferred, and how each capability traces back to stakeholders and success metrics.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 1 · Capabilities** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 1 · Capabilities**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["01"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- **Primary Source:** `docs/seed/seed_overview.md` (required) for scope and user persona definitions.
- Charter scope and success metrics from `spec/00_charter.json` to anchor what’s “in” now vs “future”.
- Use canonical nouns/verbs from required seeds and charter language; do not depend on downstream glossary/FR artifacts.
- Draft capability boundaries from charter scope and seed constraints; do not depend on system sketch artifacts.
- Use provided examples only from `example/devspec_kit` for format calibration, never as source truth.
- Guides: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`, developer reference.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger of candidate capabilities as verb–object pairs derived from charter goals, user JTBD, and glossary nouns; include proposed scope (in/out/future), natural owner, inputs/outputs, and key error states. Do not output it.
- **Cross-Check**: Verify capability feasibility against charter scope, constraints, and seed constraints. If feasibility is unclear, ask a Gap Question.
- Rewrite to single, testable behaviors with explicit boundaries and error states; propose `trace` hooks to FRs (if any exist) or leave `*-tbd` anchors.
- Emit JSON after alignment.

## Heuristics For Completeness
- Optional→expected: include pre/postconditions for capabilities with notable prerequisites/side effects; include owner for anything that spans components.
- Auto-trace seeds: if an FR draft exists, add a `trace` to it; otherwise, add a `fr-*-tbd` placeholder.
- Naming: prefer `capability-<verb>-<noun>` from glossary; avoid UI- or table-centric names.

## Self-Audit Gate
- If `generation_quality.preflight_passed` cannot be set to `true` with current evidence, stop and ask targeted questions.
- Gating items:
  - All in-scope charter goals map to at least one capability.
  - Each capability contains a clear verb, scope, owner (if not external), and minimal inputs/outputs.
  - Non-trivial capabilities include either pre/postconditions or error_states.
  - No duplicate or overlapping capabilities (glossary-normalized).

# Output Rules
1. Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2. The JSON must validate against the referenced step schema listed in `Schema Reference`.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`.
7. If the schema supports `trace` or `links`, include at least one reference to connect artifacts across steps.
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Step-Specific Completeness Checklist
- Capabilities cover the full scope of the charter/user segments; each is a single verb-driven behavior (e.g., "search products", "issue refund").
- Each capability has an explicit `scope` of `in`, `out`, or `future`; avoid leaving planned but deferred work as `in`.
- Include `owner` for each capability reflecting the accountable team for delivery.
- Preconditions, postconditions, and error_states are set for non-trivial capabilities.
- Inputs/outputs are concrete (e.g., IDs, payload shapes, key fields), not hand-wavy.
- Trace includes at least one reference to FRs or known interfaces once available; use `*-tbd` if not yet defined.

## Negative Constraints
- **DO NOT** overlap capability scopes; each capability must have a clear boundary.
- **DO NOT** use generic verbs ("manage", "handle") that obscure testable behavior.
- **DO NOT** leave `trace` fields empty; use `*-tbd` if specific links are not yet known.
- **DO NOT** invent capabilities that are not supported by the Charter goals.

## Field-by-Field Guidance
- capability_id: stable kebab-case; prefer `capability-<verb>-<object>`.
- verb: imperative phrasing that is testable; avoid implementation details.
- description: 1–2 sentences defining intent and boundaries.
- scope: `in` (this phase), `out` (explicitly excluded), `future` (later milestone).
- owner: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, or `engineering`—who builds/operates this capability.
- inputs/outputs: lists of key data elements or artifacts exchanged.
- preconditions/postconditions: guardrails for when capability is valid and what becomes true after execution.
- error_states: enumerate meaningful failure modes with messages or codes.
- trace: FRs, APIs, NFRs the capability justifies or is justified by.

## Best Practices
- **Verbs**: Phrase each `verb` as an observable action (e.g., "issue invoice"), avoiding generic "manage" or "handle".
- **Scope**: Set realistic scope (`in`, `out`, `future`) to focus delivery; align with charter.
- **Handshake**: Enumerate `inputs`, `outputs`, `preconditions`, and `postconditions` so downstream FRs and interfaces know the full handshake.
- **Failures**: Capture `error_states` with user-visible impacts to drive fixture coverage.
- **Trace**: Use `trace` to connect capabilities to charter metrics, FRs, or governance requirements.

## Common Pitfalls
- **Marketing Fluff**: Copying marketing language instead of measurable verbs leads to ambiguous FRs.
- **Hidden Dependencies**: Marking items `in` scope without explicit preconditions.
- **Implementation Leak**: Capabilities that mirror UI screens or database tables instead of user value.
- **Duplicate IDs**: Duplicating capabilities with different IDs, breaking traceability.
- **Undefined I/O**: Leaving inputs/outputs undefined makes API generation impossible.

## Quick Reference
- ID Format: `capability-<verb>-<object>`.
- Scope: `in`, `out`, or `future`.
- Owner: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, or `engineering`.

# Clarification Questions
- Which core user jobs require first-class capabilities now vs later? What must not be built?
- For each capability, what are the minimal inputs/outputs needed to prove it works end-to-end?
- What are the typical preconditions and postconditions? Any compliance or data retention implications?
- What are the top 3 error states per high-risk capability and how should they be surfaced?
- Which team owns each capability across build/operate/support? Any shared ownership to flag?
    - *Note:* Owners can be technical (api/ui/ops) or business-facing (product/business/data), as long as they are accountable.
- Which FRs or APIs (existing or anticipated) does each capability map to?

# Schema Reference
- Schema URI: https://specdev.local/schema/01_capabilities.schema.json
- Schema File: schema/01_capabilities.schema.json
- Schema Registry: tools/schema_registry.json

## Hardening Protocol
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

# Output Contract
```json
{
  "id": "capabilities-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [
    {
      "seed_id": "seed-overview"
    }
  ],
  "capabilities": [
    {
      "capability_id": "capability-authentication",
      "verb": "authenticate",
      "scope": "in",
      "capability_ref": {
        "id": "cn:core:capability:example",
        "kind": "capability"
      }
    }
  ],
  "generation_quality": {
    "preflight_passed": true,
    "evidence_records": [],
    "unresolved_inputs": [],
    "assumptions": [],
    "placeholder_scan": {
      "has_placeholders": false,
      "tokens_found": []
    },
    "self_check_results": []
  },
  "canonical_refs_used": [
    {
      "id": "cn:core:capability:example",
      "kind": "capability"
    }
  ],
  "canonical_proposals": [],
  "canonical_conflicts": []
}
```

## Canonical Registry (Required Input)

Before generating output, you MUST load and search `canon/manifest.json` for existing canonical entries. Use this registry to:
1. Bind `*_ref` fields to existing canonical IDs (`cn:<namespace>:<kind>:<slug>`)
2. Resolve aliases via `canon/aliases.json`
3. Propose new entries in `canonical_proposals` when no match exists
4. Flag conflicts in `canonical_conflicts` when ambiguous matches are found
## Canonical Binding Rules
1. `canonical_refs_used` is REQUIRED and must list every canonical ID referenced by any `*_ref` field in this artifact.
2. `canonical_proposals` is REQUIRED (may be empty `[]`). Populate it for any new term, metric, entity, role, etc. that does not exist in the registry.
3. `canonical_conflicts` is REQUIRED (may be empty `[]`). Populate it when a field value matches multiple canonical entries or contradicts an existing definition.
4. `generation_quality` is REQUIRED. Set `preflight_passed: true` only after confirming all canonical bindings are resolved.
5. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.
