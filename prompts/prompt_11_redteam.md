# Step 11 · Red‑Team / Failure Modes

## Purpose
Anticipate how the system can fail, whether through malicious actors, misuse, or rare scenarios, and document mitigations before implementation begins. Red-team findings inform fixtures, monitoring, and governance so the spec remains resilient under stress.

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 11 · Red‑Team / Failure Modes** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 11 · Red‑Team / Failure Modes**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Context To Ingest
- Interface Contracts `spec/05_interface_contracts.json` for attack surface (routes/methods/schemas/security).
- FRs `spec/04_fr_list.json` and Invariants `spec/06_invariants.json` for critical behaviors and rules.
- NFRs `spec/07_nfrs.json` and Monitoring `spec/16_delivery_monitoring.json` for SLO/SLA and alerting context.
- Incident notes or runbooks (if present); Guides: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`, developer reference.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Threat Ledger: enumerate threats per surface (authn, authz, input validation, transport, business logic, data privacy), with vectors, impacted assets, severity, and concrete mitigations; list edge cases. Do not output it.
- Map mitigations to fixtures and invariants; check if monitoring covers detection.
- Self-audit; if any public API lacks at least one plausible threat or mitigation, ask Gap Questions.
- Rewrite threats to specific, testable statements; include mitigations and references.
- Emit JSON when coverage is meaningful.

## Heuristics For Completeness
- Optional→expected: include mitigations for high/critical threats; include edge_cases (timeouts, retries, race conditions).
- Auto-link: reference `fixture-*` and `invariant-*` where feasible; align severities with NFRs and alerting.
- Ambiguity scrub: name vectors (e.g., replay, injection, scraping) and affected assets/services.

## Self-Audit Gate
- If completeness < 0.9, ask.
- Gating items:
  - Each public API has at least one enumerated threat; high/critical entries have mitigations.
  - Edge cases listed for fragile flows; severities assigned with rationale; links to fixtures/invariants where applicable.

# Output Rules
1. Return exactly one fenced code block with language `json`. No prose before or after.
2. The JSON must validate against the Embedded Schema below.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`.
7. If the schema supports `trace` or `links`, include at least one reference to connect artifacts across steps.
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Step-Specific Completeness Checklist
- Threats list covers likely attack vectors and abuse cases across auth, data, transport, and business logic.
- Each threat specifies severity, vector, and actionable mitigations.
- Include `edge_cases` to capture non-malicious but risky scenarios (timeouts, retries, partial failures).
- Align threats with fixtures (Step 8) and invariants (Step 6) where enforcement is possible.

## Field-by-Field Guidance
- threats[*].threat_id: `threat-<area>-<vector>`.
- description: succinct problem statement; include affected assets or flows.
- vector: the entry point or technique (e.g., injection, replay, brute-force, scraping).
- mitigations: concrete steps (rate limiting, input validation, CAPTCHAs, mTLS, content filters).
- severity: `low`, `medium`, `high`, or `critical` based on impact and likelihood.
- edge_cases: non-malicious but failure-prone scenarios.

## Best Practices
- **Threats**: Describe each `threat` with clear attack vectors or failure mechanisms, then prioritize using `severity`.
- **Mitigation**: Tie `mitigations` to specific actions, invariants, or monitoring hooks instead of vague statements.
- **Edge Cases**: Populate `edge_cases` with scenarios (timeouts, retries) that warrant dedicated fixtures or UI handling.
- **Review**: Revisit threats after every major spec update to keep the catalog synchronized with new capabilities.

## Common Pitfalls
- **Alarm Fatigue**: Labeling everything "high" severity without triage, making it impossible to focus mitigation work.
- **Vague Controls**: Listing generic mitigations such as "add logging" without specifying owners or steps.
- **Untested**: Forgetting to propagate serious threats into fixtures or governance, leaving gaps in automation.
- **Drift**: Treating red-team outputs as one-time, leading to drift during implementation.

## Quick Reference
- Threats: `threat_id`, `description`, `vector`, `mitigations`, `severity`.
- Edge cases: list of non-malicious but risky scenarios.

# Clarification Questions
- What are the top abuse cases or attack vectors for our APIs and UIs? How would an adversary exploit them?
- Which controls do we have or plan (authz, rate limits, validation, anomaly detection)?
- Which sensitive data paths exist and how are they protected in transit and at rest?
- Which edge cases often break systems (timeouts, race conditions, idempotency)? How will we detect and handle them?

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/11_redteam.schema.json",
  "title": "11_redteam",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "id": {
      "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
    },
    "owner": {
      "$ref": "https://specdev.local/schema/core/atoms/1#owner"
    },
    "created_at": {
      "$ref": "https://specdev.local/schema/core/atoms/1#timestamp"
    },
    "threats": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "threat_id": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "description": {
            "type": "string"
          },
          "vector": {
            "type": "string"
          },
          "mitigations": {
            "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
          },
          "severity": {
            "type": "string",
            "enum": [
              "low",
              "medium",
              "high",
              "critical"
            ]
          }
        },
        "required": [
          "threat_id",
          "description",
          "severity"
        ]
      }
    },
    "edge_cases": {
      "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "threats"
  ]
}
```

# Output Contract
```json
{
  "id": "redteam-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "threats": []
}
```
