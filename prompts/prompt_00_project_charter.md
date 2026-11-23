# Step 00 · Project Charter

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

## Role
You are a **senior product strategist and scope analyst**. Your job is to emit a single JSON artifact for **Step 00 · Project Charter** that captures business scope in falsifiable, machine-checkable language. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

Run `specdev prompt-context 00` to see downstream consumers.

## Purpose
Establish the authoritative charter that captures the business problem, intended users, constraints, and measurable success criteria in falsifiable language. This artifact anchors downstream decisions by making scope boundaries, stakeholder needs, and success metrics explicit enough to trace through every later step.

## Extraction Intent

For each upstream artifact ingested, extract the following:
- **Seeds**: per spec/common/seed_manifest.json step_requirements["00"]
- **Existing org context** (if present): Business objectives, compliance posture, target users/markets from any product briefs in repo

## Operating Flow: Extract → Scope → Validate → Emit
- **Extract**: Build a private Context Ledger from all seeds listed for this step in the manifest. Capture: problem statement (who/what/impact), scope boundaries (in, later, out), constraints, assumptions, risks, stakeholders (roles→needs), user_segments (JTBD/pains/gains), and candidate success_metrics. Do not output it. For any seed covering tech stack or infrastructure: extract every hardware, legacy, platform or technology limit as an item of `constraints`, dependency risks as `risks`, and conditions taken for granted as `assumptions`. Do not leave seed tech constraint data unreflected — every tech constraint must become a `constraints` item.
- **Scope**: Cross-check metrics against seed documents to align metric names and units; align segment terminology with seed document terminology.
- **Validate**: Self-audit against the checklist; if scope, metrics, or stakeholders are unclear, ask Gap Questions instead of guessing; wait for answers. Rewrite for measurability: ensure problem statement and metrics have explicit units, targets, and measurement methods; make sure every scope item, constraint, assumption, risk, segment and metric names the seed or stakeholder need it comes from in `derives_from`.
- **Emit**: Emit a single JSON artifact only after the above is satisfied.

## Heuristics For Completeness (soft, non-binding)
- MUST include baselines and measurement_method for success_metrics when any seed listed in the manifest for this step references historical data or dashboards; MUST include stakeholders and user_segments that materially affect scope as identified in the seed documents.
- Link upward only: `derives_from` names the seeds or stakeholder needs a node comes from. The charter holds no links to later steps; those steps link back to it.
- Ambiguity scrub: MUST replace any instance of “improve”, “optimize”, “user-friendly”, or “fast” with a quantifiable target (numeric value + unit + timeframe) derived from seed success criteria or seed constraints (per the manifest).

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/common/seed_manifest.json` is present and lists at least one seed for step "00".
- All seeds listed for step "00" in the manifest are present and non-empty.

## Negative Constraints
- **DO NOT** use vague "business speak" (e.g. "optimize", "improve") without measurable metrics.
- **DO NOT** use a default or placeholder value for `owner`; set it to the accountable team.
- **DO NOT** use placeholder TBDs for critical sections like `problem_statement` or `success_metrics`.
- **DO NOT** list stakeholders without defining their specific `needs`.

## Coverage Closure
Before emitting, verify:
- Every requirement stated in any seed listed for this step in the manifest is reflected in `scope_items`, `constraints`, `success_metrics`, `user_segments`, `assumptions`, or `risks`, OR explicitly listed as a `scope_items` entry with `scope` `out` and a `scope_reason`.
- No seed requirement is silently dropped — this is the root artifact; nothing upstream can be deferred.
- All metric names and units in `success_metrics` align with terminology used in the seed documents.
- If any seed statement is ambiguous or contradictory: add a gap question (Clarify mode) rather than making an assumption.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] `scope_items` holds specific items (not vague categories); every `later` or `out` item has a `scope_reason`
- [ ] All `assumptions` and `risks` name the seeds they come from in `derives_from`
- [ ] Every tech constraint from seeds is an item of `constraints`
- [ ] Every stakeholder need is named in the `derives_from` of at least one `success_metric` or scope item
- [ ] Every `success_metric` has all required fields populated (no vague targets)
- [ ] No node ids in prose: a mention that states a relation is a link field; any other mention is reworded; contract values (paths, error codes, field names) stay.

## Step-Specific Completeness Checklist
- Problem statement specifies the primary pain, affected users, measurable business impact, and hard constraints (time, budget, compliance).
- Scope is explicit: avoid vague wording (e.g., "optimize", "improve") without measurable anchors.
- Stakeholders list covers decision-makers and operators; each stakeholder has a role and specific needs that drive requirements or success metrics.
- User segments are distinct; each includes jobs-to-be-done, pains, and gains that map to capabilities and FRs.
- Success metrics: each metric MUST include all schema-required fields; when any ingested seed or product brief contains historical values, populate the optional `baseline` field with that data.
- Owner is set based on who will maintain the charter and is not just a default.

## Best Practices
- **Problem Statement**: Write a statement of 1-3 sentences that names the affected users, their pain, the measurable business impact, and hard constraints — sourced from the ingested seeds. Avoid solutioneering.
- **Success Metrics**: Ensure each `success_metric` is measurable and traceable to seed document data; populate all schema-required fields.
- **Scope**: Define scope explicitly in `scope_items` (in, later, out) to prevent creep.
- **Users**: Describe each `user_segment` with jobs-to-be-done, pains, and gains to map requirements to value.
- **Risks**: Record critical `assumptions` and `risks` with enough context to inform governance.
- **Stakeholders**: Identify real stakeholders (not just titles) to drive prioritization.

## Common Pitfalls
- **Solutioneering**: Writing solution statements instead of clear problem statements (hides falsifiable metrics).
- **Vague Metrics**: Leaving metrics without units, baselines, or measurement methods (impossible to verify).
- **Implicit Assumptions**: Treating assumptions as implicit (leaves governance blind).
- **Missing Stakeholders**: Forgetting key segments or stakeholders (breaks downstream traceability).
- **Scope Creep**: Missing an "out-of-scope" list, leading to ambiguity.

# Clarification Questions
- What are the top 3 measurable business outcomes (with units and targets) and by when?
- Which user segments are in primary focus, and what critical JTBD do they have today that we must address?
- What must be explicitly out of scope for this phase (integrations, regions, personas, features)?
- What non-negotiable constraints apply (compliance, security posture, SLOs, data residency, budget)?
- Who are the accountable stakeholders for sign-off and ongoing ownership? Any external regulators or auditors involved?
- What baselines exist today for each success metric, and how will we measure them (tool, dashboard, query)?
- Which upstream systems, dependencies, or programs does this charter rely on, and what risks do they introduce?

# Schema Reference
- Schema URI: vc:00-charter
- Schema File: schema/00_charter.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:00-charter",
  "id": "charter-v1",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "title": "Authentication Session Service",
  "problem_statement": "Authentication and session handling are inconsistent across user-facing flows.",
  "scope_items": [
    {
      "scope_id": "scope-user-authentication",
      "text": "User authentication flows",
      "scope": "in",
      "derives_from": ["need-clear-auth-requirements"]
    },
    {
      "scope_id": "scope-oauth-integrations",
      "text": "OAuth third-party integrations",
      "scope": "out",
      "scope_reason": "Post-launch only; no identity provider is contracted yet.",
      "derives_from": ["need-clear-auth-requirements"]
    }
  ],
  "assumptions": [
    {
      "assumption_id": "asm-user-db-unchanged",
      "text": "Existing user database schema remains unchanged",
      "derives_from": ["seed-project-brief"]
    }
  ],
  "risks": [
    {
      "risk_id": "risk-session-capacity",
      "text": "Session storage capacity under peak load",
      "scope": "in",
      "derives_from": ["asm-user-db-unchanged"]
    }
  ],
  "stakeholders": [
    {
      "stakeholder_id": "sh-engineering-lead",
      "role": "Engineering Lead",
      "needs": [
        {
          "need_id": "need-clear-auth-requirements",
          "text": "Clear authentication requirements and a defined session lifecycle",
          "derives_from": ["seed-project-brief"]
        }
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
      ],
      "derives_from": ["seed-project-brief"]
    }
  ],
  "success_metrics": [
    {
      "metric_id": "login-success-rate",
      "name": "Login Success Rate",
      "target": ">= 99.5%",
      "unit": "percent",
      "measurement_method": "Ratio of successful logins to total attempts via auth service metrics dashboard",
      "unit_ref": {
        "id": "cn:core:unit:percent",
        "kind": "unit"
      },
      "derives_from": ["need-clear-auth-requirements"]
    },
    {
      "metric_id": "session-error-rate",
      "name": "Session Error Rate",
      "target": "< 0.1%",
      "unit": "percent",
      "measurement_method": "Ratio of session errors to total sessions from error tracking dashboard",
      "unit_ref": {
        "id": "cn:core:unit:percent",
        "kind": "unit"
      },
      "derives_from": ["need-clear-auth-requirements"]
    }
  ],
  "constraints": [
    {
      "constraint_id": "con-eu-data-residency",
      "text": "Customer data must be stored in EU regions only",
      "scope": "in",
      "derives_from": ["seed-project-brief"]
    }
  ],
  "canonical_refs_used": []
}
```

