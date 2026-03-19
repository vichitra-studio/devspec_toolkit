# Step 00 · Project Charter

Run `specdev prompt-context 00` to see downstream consumers. This prompt's output feeds 8 downstream steps.

## Schema Authority

The schema at `schema/00_charter.schema.json` is the authoritative source for all
field definitions, types, required vs optional markers, enum values, patterns, and minItems rules.
MUST read the schema before generating output. Do NOT guess field names, types, or valid values —
all structural constraints are defined in the schema. Do NOT output fields not defined in the schema.

## Path Variables
| Variable | Description |
|---|---|
| `$PRODUCT_ROOT` | Root of the consumer/product repository |
| `$TOOLKIT_ROOT` | Root of the devspec_toolkit directory |
| `$SPEC_DIR` | `$PRODUCT_ROOT/spec` — where spec artifacts live |
| `$SCHEMA_DIR` | `$TOOLKIT_ROOT/schema` — where JSON Schemas live |

## Purpose
Establish the authoritative charter that captures the business problem, intended users, constraints, and measurable success criteria in falsifiable language. This artifact anchors downstream decisions by making scope boundaries, stakeholder needs, and success metrics explicit enough to trace through every later step.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 0 · Project Charter** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 0 · Project Charter**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.

## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["00"]`.
- Ingest required seeds in order before any other context.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- **Primary Source:** `docs/seed/seed_overview.md` (required) for project scope boundaries, business objectives, target users, and success criteria.
- **Constraints Source:** `docs/seed/seed_tech_stack.md` (required) to trace hardware/legacy constraints into `out_of_scope` or `assumptions`.
- Existing org context: business objectives, compliance posture, target users/markets (summarize from any product briefs present in repo).
- Specs in `spec/` if present: early drafts of `03_glossary.json`, `07_nfrs.json` (to align metrics/units), and any legacy charter-like docs.
- Guides: Shared expectations `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`, reference `$TOOLKIT_ROOT/docs/developers/reference.md`.
- Schema: `$SCHEMA_DIR/00_charter.schema.json` for Output Contract shape and required fields.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **docs/seed/seed_overview.md**: Project scope boundaries, business objectives, target users, and high-level success criteria
- **docs/seed/seed_tech_stack.md**: Hardware/legacy constraints for `out_of_scope` or `assumptions`; technology constraints informing `risks`

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger containing: problem statement (who/what/impact), in/out-of-scope boundaries, assumptions, risks, stakeholders (roles→needs), user_segments (JTBD/pains/gains), and candidate success_metrics (metric→unit→target→method). Do not output it.
- Cross-check metrics against seed documents to align metric names and units; align segment terminology with seed document terminology.
- Self-audit against the checklist; if scope, metrics, or stakeholders are unclear, ask Gap Questions instead of guessing; wait for answers.
- Rewrite for measurability: ensure problem statement and metrics have explicit units, targets, and measurement methods; propose `links` to anticipated FRs/NFRs where obvious.
- Emit a single JSON artifact only after the above is satisfied.

## Heuristics For Completeness (soft, non-binding)
- MUST include baselines and measurement_method for success_metrics when `docs/seed/seed_overview.md` or `docs/seed/seed_tech_stack.md` references historical data or dashboards; MUST include stakeholders and user_segments that materially affect scope as identified in the seed documents.
- Auto-link seeds: add `links` to downstream FRs (`fr-*` once known) and NFR categories derived from `success_metrics` units (read `canon/manifest.json` for valid NFR category values).
- Ambiguity scrub: MUST replace any instance of “improve”, “optimize”, “user-friendly”, or “fast” with a quantifiable target (numeric value + unit + timeframe) derived from `docs/seed/seed_overview.md` success criteria or `docs/seed/seed_tech_stack.md` constraints.

## Self-Audit Gate (do not output)
- If score < 0.9, output clarifying questions only — do not emit JSON.
- Gating items to check before emitting:
  - Problem statement names users, pain, measurable business impact, and hard constraints.
  - In/out-of-scope each list ≥3 specific items tied to integrations/features/regions.
  - Stakeholders include at least product/eng/ops/security roles with distinct needs.
  - User segments include JTBD/pains/gains for primary personas.
  - Success metrics include unit+target+measurement_method (baseline where available) for ≥2 metrics.
  - Owner reflects accountability for charter maintenance.

### Coverage Closure
Before emitting, verify:
- Every requirement stated in `docs/seed/seed_overview.md` and `docs/seed/seed_tech_stack.md` is reflected in `goals`, `constraints`, `success_metrics`, or `user_segments`, OR explicitly listed in `out_of_scope` with rationale.
- No seed requirement is silently dropped — this is the root artifact; nothing upstream can be deferred.
- All metric names and units in `success_metrics` align with terminology used in the seed documents.
- If any seed statement is ambiguous or contradictory: add a gap question (Clarify mode) rather than making an assumption.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)

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
- Problem statement specifies the primary pain, affected users, measurable business impact, and hard constraints (time, budget, compliance).
- Scope is explicit: at least 3–5 in-scope items and 3–5 out-of-scope items; avoid vague wording (e.g., "optimize", "improve") without measurable anchors.
- Stakeholders list covers decision-makers and operators; each stakeholder has a role and specific needs that drive requirements or success metrics.
- User segments are distinct; each includes jobs-to-be-done, pains, and gains that map to capabilities and FRs.
- Success metrics: each metric MUST include metric_id, name, unit, target, measurement_method, and — when `docs/seed/seed_overview.md` or product briefs contain historical values — baseline sourced from that data.
- Links include at least one cross-reference to downstream steps (e.g., FRs, NFRs) or upstream governance/constraints.
- Owner is set based on who will maintain the charter and is not just a default.

## Negative Constraints
- **DO NOT** use vague "business speak" (e.g. "optimize", "improve") without measurable metrics.
- **DO NOT** omit the `owner` field; accountability is required.
- **DO NOT** use placeholder TBDs for critical sections like `problem_statement` or `success_metrics`.
- **DO NOT** list stakeholders without defining their specific `needs`.

## Field-by-Field Guidance
- id: stable kebab-case; prefer `project_charter-<initiative>`.
- owner: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, or `engineering`; pick the accountable group for charter updates.
- problem_statement: 1–3 sentences, explicit on users, pain, outcome, and constraints.
- in_scope/out_of_scope: concrete bullets; include integrations, data domains, and delivery boundaries.
- assumptions: facts taken for granted (e.g., existing identity provider, data retention rules).
- risks: delivery and operational risks with concise phrasing (e.g., dependency readiness, legal review timelines).
- stakeholders: roles (e.g., Security Lead, Support Manager) with clear needs (e.g., audit logs retained 1 year).
- user_segments: include description and JTBD; pains and gains should be testable or observable later.
- success_metrics: target must be measurable in units; measurement_method states how/where it will be captured (e.g., analytics event, dashboard query).
- links: trace to FRs/NFRs/governance ids when known; use temporary `*-tbd` anchors if not yet defined.

## Best Practices
- **Problem Statement**: Write a statement of 1-3 sentences that names the affected users, their pain, the measurable business impact, and hard constraints — sourced from `docs/seed/seed_overview.md`. Avoid solutioneering.
- **Success Metrics**: Pair each `success_metric` with a realistic baseline, target, unit, and measurement method.
- **Scope**: Define in/out of scope explicitly to prevent creep; capture at least 3 items each.
- **Users**: Describe each `user_segment` with jobs-to-be-done, pains, and gains to map requirements to value.
- **Risks**: Record critical `assumptions` and `risks` with enough context to inform governance.
- **Stakeholders**: Identify real stakeholders (not just titles) to drive prioritization.

## Common Pitfalls
- **Solutioneering**: Writing solution statements instead of clear problem statements (hides falsifiable metrics).
- **Vague Metrics**: Leaving metrics without units, baselines, or measurement methods (impossible to verify).
- **Implicit Assumptions**: Treating assumptions as implicit (leaves governance blind).
- **Missing Stakeholders**: Forgetting key segments or stakeholders (breaks downstream traceability).
- **Scope Creep**: Missing an "out-of-scope" list, leading to ambiguity.

## Quick Reference
- Required: `id`, `owner`, `created_at`, `problem_statement`, `success_metrics`.
- **Validation Gates**: 
  - `stakeholders` MUST have `needs`.
  - `success_metrics` MUST have `measurement_method`.
  - `in_scope` MUST have at least 3 items.
- Stakeholders: list roles and needs; must inform later FRs and NFRs.

# Clarification Questions
- What are the top 3 measurable business outcomes (with units and targets) and by when?
- Which user segments are in primary focus, and what critical JTBD do they have today that we must address?
- What must be explicitly out of scope for this phase (integrations, regions, personas, features)?
- What non-negotiable constraints apply (compliance, security posture, SLOs, data residency, budget)?
- Who are the accountable stakeholders for sign-off and ongoing ownership? Any external regulators or auditors involved?
- What baselines exist today for each success metric, and how will we measure them (tool, dashboard, query)?
- Which upstream systems, dependencies, or programs does this charter rely on, and what risks do they introduce?

# Schema Reference
- Schema URI: https://specdev.local/schema/00_charter.schema.json
- Schema File: schema/00_charter.schema.json
- Schema Registry: tools/schema_registry.json

## Hardening Protocol
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

## Canonical Registry (Required Input)

Before generating output, you MUST load and search `canon/manifest.json` for existing canonical entries. Use this registry to:
1. Bind `*_ref` fields to existing canonical IDs (`cn:<namespace>:<kind>:<slug>`)
2. Resolve aliases via `canon/aliases.json`
3. Propose new entries in `canonical_proposals` when no match exists
4. Flag conflicts in `canonical_conflicts` when ambiguous matches are found
## Canonical Binding Rules
1. `canonical_refs_used` is REQUIRED and must list every canonical ID referenced by any `*_ref` field in this artifact.
2. `canonical_proposals` is OPTIONAL. Populate it for any new term, metric, entity, role, etc. that does not exist in the registry.
3. `canonical_conflicts` is OPTIONAL. Populate it when a field value matches multiple canonical entries or contradicts an existing definition.
4. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.

## Metadata Contract

This step's output artifact MUST include every field listed in the schema's `required[]` array (see Schema Authority). Do NOT add fields not defined in the schema. Refer to the schema for the complete list of required fields, types, and structural constraints — do NOT restate them here.

# Output Contract
```json
{
  "id": "project-charter-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "title": "Project Charter",
  "problem_statement": "Authentication and session handling are inconsistent across user-facing flows.",
  "stakeholders": [
    {
      "role": "Engineering Lead",
      "needs": [
        "Clear authentication requirements",
        "Defined session lifecycle"
      ]
    }
  ],
  "user_segments": [
    {
      "segment_id": "end-user",
      "description": "Registered users who authenticate via standard login flows.",
      "jobs_to_be_done": [
        "Log in securely"
      ],
      "pains": [
        "Inconsistent session handling"
      ],
      "gains": [
        "Reliable authentication"
      ]
    }
  ],
  "success_metrics": [
    {
      "metric_id": "login-success-rate",
      "name": "Login Success Rate",
      "target": "99.5%",
      "unit": "percent",
      "measurement_method": "Ratio of successful logins to total attempts",
      "unit_ref": {
        "id": "cn:core:unit:percent",
        "kind": "unit"
      }
    },
    {
      "metric_id": "session-error-rate",
      "name": "Session Error Rate",
      "target": "< 0.1%",
      "unit": "percent",
      "measurement_method": "Ratio of session errors to total sessions",
      "unit_ref": {
        "id": "cn:core:unit:percent",
        "kind": "unit"
      }
    }
  ],
  "canonical_refs_used": []
}
```

