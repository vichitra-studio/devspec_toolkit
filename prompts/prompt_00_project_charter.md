# Step 00 · Project Charter

> **Inherits**: `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` — all directives apply unless explicitly overridden below.

Run `specdev prompt-context 00` to see downstream consumers. This prompt's output feeds 8 downstream steps.

## Purpose
Establish the authoritative charter that captures the business problem, intended users, constraints, and measurable success criteria in falsifiable language. This artifact anchors downstream decisions by making scope boundaries, stakeholder needs, and success metrics explicit enough to trace through every later step.

## Extraction Intent

For each upstream artifact ingested, extract the following:
- **docs/seed/seed_overview.md** (required): Project scope boundaries, business objectives, target users, and high-level success criteria
- **docs/seed/seed_tech_stack.md** (required): Hardware/legacy constraints for `out_of_scope` or `assumptions`; technology constraints informing `risks`
- **Existing org context** (if present): Business objectives, compliance posture, target users/markets from any product briefs in repo
- **spec/03_glossary.json, spec/07_nfrs.json** (if present): Align metrics/units and terminology with early drafts

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
  "id": "project-charter-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "title": "Project Charter",
  "problem_statement": "Authentication and session handling are inconsistent across user-facing flows.",
  "in_scope": [
    "User authentication flows",
    "Session lifecycle management",
    "Token refresh and expiry handling"
  ],
  "out_of_scope": [
    "OAuth third-party integrations",
    "Legacy SSO migration",
    "Mobile biometric authentication"
  ],
  "assumptions": [
    "Existing user database schema remains unchanged"
  ],
  "risks": [
    "Session storage capacity under peak load"
  ],
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

